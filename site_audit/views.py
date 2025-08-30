from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count, Avg, F, Case, When, IntegerField
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
import json
import time
import re
import boto3
from django.conf import settings

from project.models import Project
from .models import SiteAudit, SiteIssue
from .tasks import trigger_manual_site_audit


def fetch_pagespeed_data_from_r2(r2_path):
    """Fetch PageSpeed Insights data from R2 storage"""
    if not r2_path:
        return None
    
    try:
        # Initialize R2 client using AWS settings
        s3_client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name='auto'
        )
        
        # Download and parse the JSON file
        response = s3_client.get_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=r2_path
        )
        
        content = response['Body'].read()
        return json.loads(content)
    except Exception as e:
        print(f"Error fetching PageSpeed data from R2: {e}")
        return None


@login_required
def site_audit_list(request):
    """List all site audits for the current user"""
    # Get all projects for the current user
    projects = Project.objects.filter(user=request.user).select_related()
    
    # Get search query and filter
    search_query = request.GET.get('search', '').strip()
    filter_status = request.GET.get('filter', 'all')
    
    # Filter projects based on search
    if search_query:
        projects = projects.filter(
            Q(domain__icontains=search_query) |
            Q(title__icontains=search_query)
        )
    
    # Get latest completed audit for each project (or most recent if none completed)
    all_projects_with_audits = []
    for project in projects:
        # Try to get the most recent completed audit first
        latest_audit = project.site_audits.filter(status='completed').order_by('-last_audit_date', '-created_at').first()
        # If no completed audit, get the most recent audit regardless of status
        if not latest_audit:
            latest_audit = project.site_audits.order_by('-created_at').first()
        all_projects_with_audits.append({
            'project': project,
            'audit': latest_audit
        })
    
    # Calculate statistics from ALL projects (before filtering)
    total_projects = len(all_projects_with_audits)
    
    # Categorize projects by health (only count completed audits)
    healthy_count = 0
    attention_count = 0
    critical_count = 0
    
    for item in all_projects_with_audits:
        if item['audit'] and item['audit'].status == 'completed' and item['audit'].overall_site_health_score is not None:
            score = item['audit'].overall_site_health_score
            if score >= 80:
                healthy_count += 1
            elif score >= 60:
                attention_count += 1
            else:
                critical_count += 1
    
    # Apply health score filter to get filtered list for display
    projects_with_audits = all_projects_with_audits
    if filter_status != 'all':
        filtered_projects = []
        for item in all_projects_with_audits:
            if item['audit'] and item['audit'].status == 'completed' and item['audit'].overall_site_health_score is not None:
                score = item['audit'].overall_site_health_score
                if filter_status == 'healthy' and score >= 80:
                    filtered_projects.append(item)
                elif filter_status == 'attention' and 60 <= score < 80:
                    filtered_projects.append(item)
                elif filter_status == 'critical' and score < 60:
                    filtered_projects.append(item)
        projects_with_audits = filtered_projects
    
    # Handle HTMX requests for filtering and pagination
    if request.headers.get('HX-Request'):
        page_number = request.GET.get('page', 1)
        per_page = 25
        
        paginator = Paginator(projects_with_audits, per_page)
        page_obj = paginator.get_page(page_number)
        
        html = render_to_string('site_audit/partials/audit_list_items.html', {
            'projects_with_audits': page_obj.object_list,
            'has_next': page_obj.has_next(),
            'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
            'filter_status': filter_status,
            'search_query': search_query
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
        'search_query': search_query,
        'filter_status': filter_status
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
            'manual_audit_frequency_days': 1
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
        # Track previous states and scores to detect changes
        audit_states = {}
        is_initial_load = True
        
        while True:
            # Get all audits for the user's projects
            user_projects = Project.objects.filter(user=request.user).values_list('id', flat=True)
            audits = SiteAudit.objects.filter(
                project_id__in=user_projects
            ).select_related('project')
            
            # Check for status or score changes
            for audit in audits:
                audit_key = f"audit_{audit.id}"
                
                # Create a state tuple to track all changes
                current_state = (
                    audit.status,
                    audit.overall_site_health_score,
                    audit.performance_score_mobile,
                    audit.performance_score_desktop,
                    audit.total_pages_crawled
                )
                
                previous_state = audit_states.get(audit_key)
                
                # Detect any change (status, scores, or pages)
                if previous_state != current_state:
                    # On initial load, just populate the state without sending updates
                    # This prevents notifications for already completed audits
                    if is_initial_load:
                        audit_states[audit_key] = current_state
                    else:
                        # Send update for any change
                        data = {
                            'project_id': audit.project.id,
                            'audit_id': audit.id,
                            'status': audit.status,
                            'previous_status': previous_state[0] if previous_state else None,
                            'health_score': audit.overall_site_health_score,
                            'pages_crawled': audit.total_pages_crawled,
                            'issues_count': audit.get_total_issues_count(),
                            'performance_mobile': audit.performance_score_mobile,
                            'performance_desktop': audit.performance_score_desktop,
                            'update_type': 'score_update' if previous_state and previous_state[0] == audit.status else 'status_update',
                            'is_new_completion': previous_state and previous_state[0] != 'completed' and audit.status == 'completed'
                        }
                        
                        # Send as named event for HTMX SSE
                        yield f"event: audit_update\ndata: {json.dumps(data)}\n\n"
                        
                        # Update tracked state
                        audit_states[audit_key] = current_state
            
            # After first iteration, mark as no longer initial load
            is_initial_load = False
            
            # Also send heartbeat to keep connection alive
            yield f": heartbeat\n\n"
            
            # Wait before next check
            time.sleep(3)  # Check every 3 seconds for faster updates
    
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


def clean_domain_input(domain_input):
    """Clean and validate domain input"""
    if not domain_input:
        return None, "Domain is required"
    
    # Remove whitespace and convert to lowercase
    domain = domain_input.strip().lower()
    
    # Remove common prefixes and suffixes
    prefixes_to_remove = ['http://', 'https://', 'www.']
    for prefix in prefixes_to_remove:
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    
    # Remove trailing slash and paths
    domain = domain.split('/')[0]
    
    # Remove port numbers
    domain = domain.split(':')[0]
    
    # Basic domain validation pattern (supports subdomains)
    domain_pattern = re.compile(
        r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.[a-zA-Z]{2,}$'
    )
    
    if not domain_pattern.match(domain):
        return None, "Please enter a valid domain or subdomain (e.g., example.com or blog.example.com)"
    
    # Check for minimum domain length
    if len(domain) < 4:
        return None, "Domain must be at least 4 characters long"
    
    # Check for maximum domain length
    if len(domain) > 255:
        return None, "Domain is too long (maximum 255 characters)"
    
    return domain, None


@login_required
def add_project_modal(request):
    """Render the add project modal via HTMX"""
    return render(request, 'site_audit/partials/add_project_modal.html')


@login_required
@require_http_methods(["POST"])
def add_project(request):
    """Add a new project via HTMX"""
    domain_input = request.POST.get('domain', '').strip()
    title = request.POST.get('title', '').strip()
    active = True  # Always active for user-created projects, admin can change later
    run_audit = True  # Always run initial audit automatically
    
    # Clean and validate domain
    cleaned_domain, error = clean_domain_input(domain_input)
    if error:
        return HttpResponse(error, status=400)
    
    # Check if project already exists for this user
    if Project.objects.filter(user=request.user, domain=cleaned_domain).exists():
        return HttpResponse('A project with this domain already exists in your account', status=400)
    
    try:
        # Create the project
        project = Project.objects.create(
            user=request.user,
            domain=cleaned_domain,
            title=title or cleaned_domain.title(),
            active=active
        )
        
        # Create initial site audit
        site_audit = SiteAudit.objects.create(
            project=project,
            audit_frequency_days=30,
            manual_audit_frequency_days=1,
            is_audit_enabled=active,
            status='pending' if run_audit else 'completed'
        )
        
        # Trigger initial audit if requested
        if run_audit:
            try:
                trigger_manual_site_audit.apply_async(args=[project.id])
                site_audit.status = 'pending'
                site_audit.save()
            except Exception as e:
                # Don't fail project creation if audit trigger fails
                pass
        
        # Check if this is the user's first project
        user_project_count = Project.objects.filter(user=request.user).count()
        
        # Prepare the response HTML
        if user_project_count == 1:
            # First project - include both the project card and the "Add New Project" card
            project_html = render_to_string('site_audit/partials/audit_card.html', {
                'item': {
                    'project': project,
                    'audit': site_audit
                }
            })
            add_card_html = render_to_string('site_audit/partials/add_project_card.html')
            # Combine both cards
            html = project_html + add_card_html
        else:
            # Not the first project - just return the project card
            html = render_to_string('site_audit/partials/audit_card.html', {
                'item': {
                    'project': project,
                    'audit': site_audit
                }
            })
        
        # Add HX-Trigger header to close modal
        response = HttpResponse(html)
        response['HX-Trigger'] = 'projectAdded'
        return response
        
    except Exception as e:
        return HttpResponse(f'Error creating project: {str(e)}', status=500)


@login_required
def audit_detail(request, audit_id):
    """View detailed audit results with tabbed interface"""
    audit = get_object_or_404(
        SiteAudit,
        id=audit_id,
        project__user=request.user
    )
    
    # Get the requested tab (default to overview)
    tab = request.GET.get('tab', 'overview')
    
    # First try to get issues from database (new approach)
    from site_audit.models import SiteIssue
    from django.db.models import Count
    
    # Get issues from database with proper ordering (Critical -> High -> Medium -> Low)
    from django.db.models import Case, When, IntegerField
    severity_order = Case(
        When(severity='critical', then=0),
        When(severity='high', then=1),
        When(severity='medium', then=2),
        When(severity='low', then=3),
        When(severity='info', then=4),
        default=5,
        output_field=IntegerField()
    )
    
    issues_qs = SiteIssue.objects.filter(site_audit=audit).select_related('site_audit').annotate(
        severity_order=severity_order
    ).order_by('severity_order', 'issue_type', 'url')
    
    # Apply filters if on issues tab
    if tab == 'issues':
        search_query = request.GET.get('search', '')
        severity_filter = request.GET.get('severity', '')
        category_filter = request.GET.get('category', '')
        
        if search_query:
            from django.db.models import Q
            issues_qs = issues_qs.filter(
                Q(issue_type__icontains=search_query) |
                Q(url__icontains=search_query)
            )
        
        if severity_filter:
            issues_qs = issues_qs.filter(severity=severity_filter.lower())
        
        if category_filter:
            issues_qs = issues_qs.filter(issue_category=category_filter)
    
    # Pagination support
    page = request.GET.get('page', 1)
    try:
        page = int(page)
    except:
        page = 1
    
    items_per_page = 50
    offset = (page - 1) * items_per_page
    
    # Get issues list with pagination - database only
    issues = list(issues_qs[offset:offset + items_per_page])
    
    # Calculate issues by category from database only
    category_counts = issues_qs.values('issue_category').annotate(
        count=Count('id')
    ).order_by('-count')
    issues_by_category = list(category_counts)
    
    # Get issues by severity using the existing model method
    issues_by_severity = audit.get_issues_by_priority()
    
    # Get total count from database only
    total_issues = SiteIssue.objects.filter(site_audit=audit).count()
    
    # Get issue lifecycle statistics from database only
    from django.db.models import Count, Q
    lifecycle_stats = SiteIssue.objects.filter(site_audit=audit).aggregate(
        new_count=Count('id', filter=Q(status='new')),
        persisting_count=Count('id', filter=Q(status='persisting')),
        resolved_count=Count('id', filter=Q(status='resolved'))
    )
    
    # Calculate pagination info
    import math
    total_pages = math.ceil(total_issues / items_per_page) if total_issues else 1
    has_more = page < total_pages
    
    # Calculate issue range for display
    issues_start = ((page - 1) * items_per_page) + 1 if total_issues > 0 else 0
    issues_end = min(page * items_per_page, total_issues)
    
    # Generate page range for pagination display (with ellipsis for many pages)
    def get_page_range(current, total):
        if total <= 7:
            return list(range(1, total + 1))
        
        # Always show first, last, current and 2 neighbors
        pages = []
        
        # First pages
        if current <= 3:
            pages.extend(range(1, 5))
            if total > 5:
                pages.append('...')
            pages.append(total)
        # Last pages
        elif current >= total - 2:
            pages.append(1)
            pages.append('...')
            pages.extend(range(total - 3, total + 1))
        # Middle pages
        else:
            pages.append(1)
            pages.append('...')
            pages.extend(range(current - 1, current + 2))
            pages.append('...')
            pages.append(total)
        
        return pages
    
    page_range = get_page_range(page, total_pages)
    
    # Fetch PageSpeed data from R2 if on performance tab
    mobile_pagespeed_data = None
    desktop_pagespeed_data = None
    
    if tab == 'performance':
        # Fetch mobile PageSpeed data
        if audit.pagespeed_mobile_response_r2_path:
            mobile_pagespeed_data = fetch_pagespeed_data_from_r2(audit.pagespeed_mobile_response_r2_path)
        
        # Fetch desktop PageSpeed data
        if audit.pagespeed_desktop_response_r2_path:
            desktop_pagespeed_data = fetch_pagespeed_data_from_r2(audit.pagespeed_desktop_response_r2_path)
    
    context = {
        'audit': audit,
        'project': audit.project,
        'issues': issues,  # Paginated issues
        'issues_by_category': issues_by_category,
        'issues_by_severity': issues_by_severity,
        'total_issues': total_issues,
        'lifecycle_stats': lifecycle_stats,
        'tab': tab,
        'current_page': page,
        'total_pages': total_pages,
        'has_more': has_more,
        'items_per_page': items_per_page,
        'issues_start': issues_start,
        'issues_end': issues_end,
        'page_range': page_range,
        'mobile_pagespeed_data': mobile_pagespeed_data,
        'desktop_pagespeed_data': desktop_pagespeed_data
    }
    
    # Handle HTMX requests for tab switching and pagination
    if request.headers.get('HX-Request'):
        # For pagination requests (page > 1 or with filters), return only the content area
        if tab == 'issues' and (page > 1 or request.GET.get('severity') or request.GET.get('category') or request.GET.get('search')):
            return render(request, 'site_audit/partials/issues_content.html', context)
        
        # For initial tab switching, return the full tab content
        template_map = {
            'overview': 'site_audit/partials/tab_overview.html',
            'issues': 'site_audit/partials/tab_issues.html',
            'performance': 'site_audit/partials/tab_performance.html'
        }
        template = template_map.get(tab, 'site_audit/partials/tab_overview.html')
        return render(request, template, context)
    
    return render(request, 'site_audit/detail.html', context)