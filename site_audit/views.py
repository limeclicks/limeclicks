from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count, Avg, F, Case, When, IntegerField
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta
import json
import time

from project.models import Project
from .models import SiteAudit, SiteIssue
from .tasks import trigger_manual_site_audit


@login_required
def site_audit_list(request):
    """List all site audits for the current user"""
    # Get all projects for the current user
    projects = Project.objects.filter(user=request.user).select_related()
    
    # Get search query
    search_query = request.GET.get('search', '').strip()
    
    # Filter projects based on search
    if search_query:
        projects = projects.filter(
            Q(domain__icontains=search_query) |
            Q(title__icontains=search_query)
        )
    
    # Get latest audit for each project
    projects_with_audits = []
    for project in projects:
        latest_audit = project.site_audits.order_by('-created_at').first()
        projects_with_audits.append({
            'project': project,
            'audit': latest_audit
        })
    
    # Calculate statistics
    total_projects = len(projects_with_audits)
    
    # Categorize projects by health
    healthy_count = 0
    attention_count = 0
    critical_count = 0
    
    for item in projects_with_audits:
        if item['audit'] and item['audit'].overall_site_health_score:
            score = item['audit'].overall_site_health_score
            if score >= 80:
                healthy_count += 1
            elif score >= 60:
                attention_count += 1
            else:
                critical_count += 1
    
    # Handle HTMX requests for pagination
    if request.headers.get('HX-Request'):
        page_number = request.GET.get('page', 1)
        per_page = 25
        
        paginator = Paginator(projects_with_audits, per_page)
        page_obj = paginator.get_page(page_number)
        
        html = render_to_string('site_audit/partials/audit_list_items.html', {
            'projects_with_audits': page_obj.object_list,
            'has_next': page_obj.has_next(),
            'next_page': page_obj.next_page_number() if page_obj.has_next() else None
        })
        
        return HttpResponse(html)
    
    # Initial page load
    per_page = 25
    paginator = Paginator(projects_with_audits, per_page)
    page_obj = paginator.get_page(1)
    
    context = {
        'projects_with_audits': page_obj.object_list,
        'total_projects': total_projects,
        'healthy_count': healthy_count,
        'attention_count': attention_count,
        'critical_count': critical_count,
        'has_next': page_obj.has_next(),
        'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
        'search_query': search_query
    }
    
    return render(request, 'site_audit/list.html', context)


@login_required
@require_http_methods(["POST"])
def trigger_audit(request, project_id):
    """Trigger a manual site audit for a project"""
    project = get_object_or_404(Project, id=project_id, user=request.user)
    
    # Check if audit can be triggered
    site_audit, created = SiteAudit.objects.get_or_create(
        project=project,
        defaults={
            'audit_frequency_days': 30,
            'manual_audit_frequency_days': 1,
            'max_pages_to_crawl': 5000
        }
    )
    
    # Check rate limiting
    if not site_audit.can_run_manual_audit():
        days_since_last = (timezone.now() - site_audit.last_manual_audit).days if site_audit.last_manual_audit else 0
        days_remaining = site_audit.manual_audit_frequency_days - days_since_last
        
        if request.headers.get('HX-Request'):
            return HttpResponse(
                f'<div class="alert alert-warning">Please wait {days_remaining} more days before running another audit.</div>',
                status=429
            )
        return JsonResponse({
            'status': 'error',
            'message': f'Please wait {days_remaining} more days'
        }, status=429)
    
    # Trigger the audit
    try:
        result = trigger_manual_site_audit.apply_async(args=[project.id])
        
        # Update audit status immediately
        site_audit.status = 'pending'
        site_audit.save()
        
        if request.headers.get('HX-Request'):
            # Return updated project card with loading state
            latest_audit = project.site_audits.order_by('-created_at').first()
            html = render_to_string('site_audit/partials/audit_card.html', {
                'item': {
                    'project': project,
                    'audit': latest_audit
                }
            })
            return HttpResponse(html)
        
        return JsonResponse({
            'status': 'success',
            'task_id': result.id,
            'message': 'Audit triggered successfully'
        })
        
    except Exception as e:
        if request.headers.get('HX-Request'):
            return HttpResponse(
                f'<div class="alert alert-error">Failed to trigger audit: {str(e)}</div>',
                status=500
            )
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
def audit_status_stream(request):
    """Server-sent events stream for real-time audit status updates"""
    def event_stream():
        """Generate server-sent events"""
        while True:
            # Get all running audits for the user's projects
            user_projects = Project.objects.filter(user=request.user).values_list('id', flat=True)
            running_audits = SiteAudit.objects.filter(
                project_id__in=user_projects,
                status__in=['running', 'pending']
            ).select_related('project')
            
            # Check for status changes
            for audit in running_audits:
                # Refresh from database
                audit.refresh_from_db()
                
                # If status changed to completed or failed, send update
                if audit.status in ['completed', 'failed']:
                    data = {
                        'project_id': audit.project.id,
                        'status': audit.status,
                        'health_score': audit.overall_site_health_score,
                        'pages_crawled': audit.total_pages_crawled,
                        'issues_count': audit.get_total_issues_count()
                    }
                    
                    yield f"data: {json.dumps(data)}\n\n"
            
            # Also send heartbeat to keep connection alive
            yield f": heartbeat\n\n"
            
            # Wait before next check
            time.sleep(5)  # Check every 5 seconds
    
    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@login_required
def get_audit_card(request, project_id):
    """Get updated audit card HTML for a project"""
    project = get_object_or_404(Project, id=project_id, user=request.user)
    latest_audit = project.site_audits.order_by('-created_at').first()
    
    html = render_to_string('site_audit/partials/audit_card.html', {
        'item': {
            'project': project,
            'audit': latest_audit
        }
    })
    
    return HttpResponse(html)


@login_required
def audit_detail(request, audit_id):
    """View detailed audit results"""
    audit = get_object_or_404(
        SiteAudit,
        id=audit_id,
        project__user=request.user
    )
    
    # Get issues breakdown
    issues = audit.issues.all()
    issues_by_category = issues.values('issue_category').annotate(
        count=Count('id')
    ).order_by('-count')
    
    issues_by_severity = issues.values('severity').annotate(
        count=Count('id')
    ).order_by('severity')
    
    context = {
        'audit': audit,
        'project': audit.project,
        'issues': issues[:50],  # Show first 50 issues
        'issues_by_category': issues_by_category,
        'issues_by_severity': issues_by_severity,
        'total_issues': issues.count()
    }
    
    return render(request, 'site_audit/detail.html', context)