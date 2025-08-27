from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, F
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import timedelta
import json
import time

from .models import SiteAudit, OnPagePerformanceHistory, SiteIssue
from project.models import Project
from .tasks import run_manual_site_audit


@login_required
def site_audit_list(request):
    """List all site audits for the user's projects"""
    
    # Get search query
    search_query = request.GET.get('q', '').strip()
    
    # Get all site audits for user's projects
    site_audits = SiteAudit.objects.filter(
        project__user=request.user
    ).select_related('project').annotate(
        pages_crawled=Count('performance_history__pages_crawled', distinct=True),
        errors_count=F('broken_links_count') + F('missing_titles_count') + 
                    F('duplicate_titles_count') + F('missing_meta_descriptions_count')
    ).order_by('-last_audit_date', 'project__domain')
    
    # Apply search filter
    if search_query:
        site_audits = site_audits.filter(
            Q(project__domain__icontains=search_query) |
            Q(project__title__icontains=search_query)
        )
    
    # Initialize counters for stats
    healthy_sites = 0
    warning_sites = 0
    critical_sites = 0
    
    # Check for running audits
    from .models import OnPagePerformanceHistory
    from performance_audit.models import PerformancePage, PerformanceHistory
    
    running_audits = OnPagePerformanceHistory.objects.filter(
        audit__in=site_audits,
        status__in=['pending', 'running']
    ).values('audit_id').distinct()
    running_audit_ids = {item['audit_id'] for item in running_audits}
    
    # Get performance scores for all projects
    performance_scores = {}
    for audit in site_audits:
        try:
            perf_page = PerformancePage.objects.filter(project=audit.project).first()
            if perf_page:
                latest_perf = PerformanceHistory.objects.filter(
                    performance_page=perf_page,
                    status='completed'
                ).order_by('-created_at').first()
                if latest_perf:
                    performance_scores[audit.project_id] = {
                        'mobile': latest_perf.mobile_performance_score,
                        'desktop': latest_perf.desktop_performance_score
                    }
        except:
            pass
    
    # Calculate statistics for each audit
    for audit in site_audits:
        # Check if audit has running tasks
        audit.has_running_audit = audit.id in running_audit_ids
        
        # Add performance scores
        if audit.project_id in performance_scores:
            audit.performance_score_mobile = performance_scores[audit.project_id]['mobile']
            audit.performance_score_desktop = performance_scores[audit.project_id]['desktop']
        else:
            audit.performance_score_mobile = None
            audit.performance_score_desktop = None
        
        # Fix last audit date - use PerformancePage data if SiteAudit date is missing
        if not audit.last_audit_date:
            try:
                perf_page = PerformancePage.objects.filter(project=audit.project).first()
                if perf_page and perf_page.last_audit_date:
                    audit.display_last_audit_date = perf_page.last_audit_date
                else:
                    audit.display_last_audit_date = None
            except:
                audit.display_last_audit_date = None
        else:
            audit.display_last_audit_date = audit.last_audit_date
        
        # Check site audit status (OnPagePerformanceHistory)
        # Get the latest site audit history
        latest_site_audit = OnPagePerformanceHistory.objects.filter(
            audit=audit
        ).order_by('-created_at').first()
        
        if latest_site_audit:
            if latest_site_audit.status in ['pending', 'running']:
                audit.site_audit_status = 'running'
            elif latest_site_audit.status == 'completed':
                audit.site_audit_status = 'complete'
            elif latest_site_audit.status == 'failed':
                audit.site_audit_status = 'failed'
            else:
                audit.site_audit_status = 'pending'
        else:
            # No site audit history at all
            audit.site_audit_status = 'pending'
        
        # Check if site audit has actually run (has completed history)
        has_completed_audit = OnPagePerformanceHistory.objects.filter(
            audit=audit,
            status='completed'
        ).exists()
        
        if has_completed_audit and audit.total_pages_crawled and audit.total_pages_crawled > 0:
            # Calculate health based on issue density
            issues_per_page = audit.total_issues_count / audit.total_pages_crawled
            # Convert to percentage (0.1 issues per page = 90% health, 1 issue per page = 0% health)
            technical_health = max(0, min(100, 100 - (issues_per_page * 100)))
            audit.site_health = technical_health
        elif has_completed_audit and audit.total_pages_crawled == 0:
            # Audit ran but no pages crawled - likely an error
            audit.site_health = 0
        else:
            # No completed audit yet - show N/A
            audit.site_health = None
        
        # Use desktop performance score from the SiteAudit model directly
        if audit.performance_score_desktop is not None:
            audit.site_performance = audit.performance_score_desktop
        else:
            audit.site_performance = 0
        
        # Count sites by health category (only for completed audits)
        if audit.site_health is not None:
            if audit.site_health >= 80:
                healthy_sites += 1
            elif audit.site_health >= 60:
                warning_sites += 1
            else:
                critical_sites += 1
        
        # Calculate crawlability
        if audit.total_pages_crawled:
            audit.crawlability = min(97, (audit.total_pages_crawled / 100) * 97)  # Max 97% as shown
        else:
            audit.crawlability = 0
        
        # HTTPS status (simplified - you might want to check actual URLs)
        audit.https_percentage = 98 if 'https' in audit.project.domain or not audit.project.domain.startswith('http') else 0
        
        # Internal linking score (based on pages crawled)
        audit.internal_linking = min(91, (audit.total_pages_crawled / 50) * 91) if audit.total_pages_crawled else 0
    
    # Pagination
    paginator = Paginator(site_audits, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Check if any audits are currently running for auto-refresh
    has_running_audits = len(running_audit_ids) > 0
    
    return render(request, 'site_audit/site_audit_list.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'total_audits': site_audits.count(),
        'healthy_sites': healthy_sites,
        'warning_sites': warning_sites,
        'critical_sites': critical_sites,
        'has_running_audits': has_running_audits,
    })


@login_required
def site_audit_detail(request, audit_id):
    """Show detailed site audit information with comprehensive overview"""
    audit = get_object_or_404(
        SiteAudit,
        id=audit_id,
        project__user=request.user
    )
    
    # Get recent audit history
    recent_history = OnPagePerformanceHistory.objects.filter(
        audit=audit
    ).order_by('-created_at')[:5]
    
    # Get latest completed audit history for detailed data
    latest_history = OnPagePerformanceHistory.objects.filter(
        audit=audit,
        status='completed'
    ).order_by('-created_at').first()
    
    # Load JSON data from R2 if available
    audit_json_data = None
    if latest_history and latest_history.full_report_json:
        try:
            import json
            # Read the JSON report from R2 storage
            with latest_history.full_report_json.open('r') as f:
                audit_json_data = json.load(f)
        except Exception as e:
            print(f"Error loading JSON report: {e}")
    
    # Get performance audit data
    performance_data = {
        'mobile': None,
        'desktop': None,
        'combined_audit': None,
        'performance_page': None
    }
    
    try:
        from performance_audit.models import PerformancePage, PerformanceHistory
        performance_page = PerformancePage.objects.filter(project=audit.project).first()
        
        if performance_page:
            performance_data['performance_page'] = performance_page
            # Get latest combined audit (contains both mobile and desktop)
            combined_audit = PerformanceHistory.objects.filter(
                performance_page=performance_page,
                status='completed'
            ).order_by('-created_at').first()
            
            if combined_audit:
                performance_data['combined_audit'] = combined_audit
                
                # Load mobile JSON report from R2
                if combined_audit.mobile_json_report:
                    try:
                        with combined_audit.mobile_json_report.open('r') as f:
                            performance_data['mobile'] = json.load(f)
                    except:
                        pass
                
                # Load desktop JSON report from R2
                if combined_audit.desktop_json_report:
                    try:
                        with combined_audit.desktop_json_report.open('r') as f:
                            performance_data['desktop'] = json.load(f)
                    except:
                        pass
                
                # For backward compatibility, create audit-like objects with scores
                class AuditProxy:
                    def __init__(self, audit, device):
                        self.audit = audit
                        self.device = device
                        
                    def __getattr__(self, name):
                        # Map score attributes to the prefixed versions
                        if name == 'performance_score':
                            return getattr(self.audit, f'{self.device}_performance_score')
                        elif name == 'accessibility_score':
                            return getattr(self.audit, f'{self.device}_accessibility_score')
                        elif name == 'best_practices_score':
                            return getattr(self.audit, f'{self.device}_best_practices_score')
                        elif name == 'seo_score':
                            return getattr(self.audit, f'{self.device}_seo_score')
                        elif name == 'pwa_score':
                            return getattr(self.audit, f'{self.device}_pwa_score')
                        # Core Web Vitals mapping
                        elif name == 'largest_contentful_paint':
                            return getattr(self.audit, f'{self.device}_largest_contentful_paint')
                        elif name == 'interaction_to_next_paint':
                            return getattr(self.audit, f'{self.device}_interaction_to_next_paint')
                        elif name == 'cumulative_layout_shift':
                            return getattr(self.audit, f'{self.device}_cumulative_layout_shift')
                        elif name == 'first_contentful_paint':
                            return getattr(self.audit, f'{self.device}_first_contentful_paint')
                        elif name == 'speed_index':
                            return getattr(self.audit, f'{self.device}_speed_index')
                        elif name == 'time_to_interactive':
                            return getattr(self.audit, f'{self.device}_time_to_interactive')
                        elif name == 'total_blocking_time':
                            return getattr(self.audit, f'{self.device}_total_blocking_time')
                        elif name == 'first_input_delay':
                            return getattr(self.audit, f'{self.device}_first_input_delay')
                        elif name == 'time_to_first_byte':
                            return getattr(self.audit, f'{self.device}_time_to_first_byte')
                        return getattr(self.audit, name)
                
                performance_data['mobile_audit'] = AuditProxy(combined_audit, 'mobile')
                performance_data['desktop_audit'] = AuditProxy(combined_audit, 'desktop')
    except:
        pass
    
    # Prepare history data for History tab
    history_data = []
    all_history = OnPagePerformanceHistory.objects.filter(
        audit=audit
    ).order_by('-created_at')[:20]  # Get last 20 audits
    
    for history_item in all_history:
        # Calculate audit duration
        audit_duration = None
        if history_item.completed_at and history_item.created_at:
            audit_duration = int((history_item.completed_at - history_item.created_at).total_seconds())
        
        # Get issue breakdown by severity for this audit
        issue_breakdown = {}
        if history_item.status == 'completed':
            severity_counts = SiteIssue.objects.filter(
                performance_history=history_item
            ).values('severity').annotate(count=Count('id'))
            
            for item in severity_counts:
                issue_breakdown[item['severity']] = item['count']
        
        # Get performance scores if available (from related PerformanceHistory)
        performance_scores = {}
        try:
            from performance_audit.models import PerformanceHistory as PerfHistory
            # Check if there's a performance audit around the same time
            perf_audit = PerfHistory.objects.filter(
                performance_page__project=audit.project,
                created_at__date=history_item.created_at.date(),
                status='completed'
            ).first()
            
            if perf_audit:
                performance_scores = {
                    'mobile': perf_audit.mobile_performance_score,
                    'desktop': perf_audit.desktop_performance_score
                }
        except:
            pass
        
        history_data.append({
            'id': history_item.id,
            'status': history_item.status,
            'created_at': history_item.created_at,
            'completed_at': history_item.completed_at,
            'pages_crawled': history_item.pages_crawled,
            'total_issues': history_item.total_issues,
            'audit_duration': audit_duration,
            'trigger_type': getattr(history_item, 'trigger_type', 'manual'),
            'error_message': history_item.error_message,
            'retry_count': history_item.retry_count,
            'issue_breakdown': issue_breakdown,
            'performance_scores': performance_scores,
            'health_score': getattr(history_item, 'overall_score', audit.overall_site_health_score)
        })
    
    # Get issues grouped by type and severity
    issues_by_type = SiteIssue.objects.filter(
        performance_history=latest_history
    ).values('issue_type', 'severity').annotate(
        count=Count('id')
    ).order_by('-severity', '-count') if latest_history else []
    
    # Get all issues for detailed breakdown with severity counts
    all_issues = []
    critical_count = high_count = medium_count = low_count = info_count = 0
    issue_types_with_counts = []
    
    if latest_history:
        # Create custom ordering for severity (critical -> info)
        from django.db.models import Case, When, IntegerField
        severity_order = Case(
            When(severity='critical', then=1),
            When(severity='high', then=2),
            When(severity='medium', then=3),
            When(severity='low', then=4),
            When(severity='info', then=5),
            default=6,
            output_field=IntegerField()
        )
        
        all_issues = SiteIssue.objects.filter(
            performance_history=latest_history
        ).annotate(
            severity_order=severity_order
        ).order_by('severity_order', 'issue_type', 'page_url')[:50]
        
        # Count by severity
        severity_counts = SiteIssue.objects.filter(
            performance_history=latest_history
        ).values('severity').annotate(count=Count('id'))
        
        for item in severity_counts:
            if item['severity'] == 'critical':
                critical_count = item['count']
            elif item['severity'] == 'high':
                high_count = item['count']
            elif item['severity'] == 'medium':
                medium_count = item['count']
            elif item['severity'] == 'low':
                low_count = item['count']
            elif item['severity'] == 'info':
                info_count = item['count']
        
        # Get issue types with counts and descriptions
        from site_audit.issue_templates import ISSUE_TEMPLATES
        issue_type_counts = SiteIssue.objects.filter(
            performance_history=latest_history
        ).values('issue_type').annotate(count=Count('id')).order_by('-count')
        
        for item in issue_type_counts:
            issue_type = item['issue_type']
            template = ISSUE_TEMPLATES.get(issue_type, {})
            
            # Get the actual severity from the template or from actual issues
            severity = template.get('severity', None)
            if not severity:
                # Fallback: get the most common severity for this issue type from actual issues
                severity_item = SiteIssue.objects.filter(
                    performance_history=latest_history,
                    issue_type=issue_type
                ).values('severity').annotate(count=Count('id')).order_by('-count').first()
                severity = severity_item['severity'] if severity_item else 'info'
            
            issue_types_with_counts.append({
                'issue_type': issue_type,
                'count': item['count'],
                'display_name': issue_type.replace('_', ' ').title(),
                'description': template.get('description', f'Issues related to {issue_type.replace("_", " ")}'),
                'impact': template.get('impact', ''),
                'severity': severity,  # Add severity for coloring
            })
        
        # Sort issue types by severity (critical -> high -> medium -> low -> info), then by count
        severity_priority = {'critical': 1, 'high': 2, 'medium': 3, 'low': 4, 'info': 5}
        issue_types_with_counts.sort(key=lambda x: (severity_priority.get(x['severity'], 6), -x['count']))
    
    # Calculate improvements if there's previous history
    previous_history = OnPagePerformanceHistory.objects.filter(
        audit=audit,
        status='completed'
    ).order_by('-created_at')[1:2]
    
    improvements = None
    if previous_history and latest_history:
        prev = previous_history[0]
        pages_diff = latest_history.pages_crawled - prev.pages_crawled
        improvements = {
            'issues_fixed': max(0, prev.total_issues - latest_history.total_issues),
            'issues_new': max(0, latest_history.total_issues - prev.total_issues),
            'pages_change': pages_diff,
            'pages_change_abs': abs(pages_diff),
            'score_change': (audit.overall_site_health_score or 0) - (
                prev.overall_score or 0
            ) if hasattr(prev, 'overall_score') else 0
        }
    
    # Calculate metrics for overview
    # Map issue counts directly from audit model fields (more reliable than querying issues)
    # Broken links (404s) are typically critical/high severity
    # Missing/duplicate meta are typically medium severity
    # Other issues are typically low/info severity
    critical_issues = audit.broken_links_count  # 404s and 5xx errors are critical
    warning_issues = (audit.missing_titles_count + audit.duplicate_titles_count + 
                     audit.missing_meta_descriptions_count + audit.duplicate_meta_descriptions_count +
                     audit.redirect_chains_count)
    info_issues = max(0, audit.total_issues_count - critical_issues - warning_issues)
    
    metrics = {
        'total_pages': audit.total_pages_crawled,
        'total_issues': audit.total_issues_count,
        'critical_issues': critical_issues,
        'warning_issues': warning_issues,
        'info_issues': info_issues,
        'avg_page_size': audit.average_page_size_kb or 0,
        'avg_load_time': audit.average_load_time_ms or 0,
        'broken_links': audit.broken_links_count,
        'missing_titles': audit.missing_titles_count,
        'duplicate_titles': audit.duplicate_titles_count,
        'missing_meta': audit.missing_meta_descriptions_count,
        'duplicate_meta': audit.duplicate_meta_descriptions_count,
        'redirect_chains': audit.redirect_chains_count,
    }
    
    # Check if audit is currently running
    is_audit_running = OnPagePerformanceHistory.objects.filter(
        audit=audit,
        status__in=['pending', 'running']
    ).exists()
    
    # Get filter parameters to preserve them
    severity_filter = request.GET.get('severity', '')
    issue_type_filter = request.GET.get('issue_type', '')
    search_query = request.GET.get('search', '')
    
    # Handle HTMX tab requests
    tab = request.GET.get('tab', 'overview')
    if request.headers.get('HX-Request'):
        template_map = {
            'overview': 'site_audit/partials/_overview_tab.html',
            'issues': 'site_audit/partials/_issues_tab.html',
            'performance': 'site_audit/partials/_performance_tab.html',
            'history': 'site_audit/partials/_history_tab.html',
        }
        template = template_map.get(tab, 'site_audit/partials/_overview_tab.html')
        return render(request, template, {
            'audit': audit,
            'recent_history': recent_history,
            'latest_history': latest_history,
            'history_data': history_data,
            'issues_by_type': issues_by_type,
            'all_issues': all_issues,
            'improvements': improvements,
            'metrics': metrics,
            'performance_data': performance_data,
            'audit_json_data': audit_json_data,
            'critical_count': critical_count,
            'high_count': high_count,
            'medium_count': medium_count,
            'low_count': low_count,
            'info_count': info_count,
            'issue_types_with_counts': issue_types_with_counts,
            'has_more_issues': latest_history and SiteIssue.objects.filter(
                performance_history=latest_history
            ).count() > 50,
            'severity_filter': severity_filter,
            'issue_type_filter': issue_type_filter,
            'search_query': search_query,
            'is_audit_running': is_audit_running,
        })
    
    return render(request, 'site_audit/site_audit_detail.html', {
        'audit': audit,
        'recent_history': recent_history,
        'latest_history': latest_history,
        'history_data': history_data,
        'issues_by_type': issues_by_type,
        'all_issues': all_issues,
        'improvements': improvements,
        'metrics': metrics,
        'performance_data': performance_data,
        'audit_json_data': audit_json_data,
        'critical_count': critical_count,
        'high_count': high_count,
        'medium_count': medium_count,
        'low_count': low_count,
        'info_count': info_count,
        'issue_types_with_counts': issue_types_with_counts,
        'has_more_issues': latest_history and SiteIssue.objects.filter(
            performance_history=latest_history
        ).count() > 50,
        'severity_filter': severity_filter,
        'issue_type_filter': issue_type_filter,
        'search_query': search_query,
        'is_audit_running': is_audit_running,
    })


@login_required
@require_http_methods(["POST"])
def run_manual_audit(request, audit_id):
    """Trigger a manual site audit"""
    audit = get_object_or_404(
        SiteAudit,
        id=audit_id,
        project__user=request.user
    )
    
    # Check if can run manual audit
    if not audit.can_run_manual_audit():
        time_until = audit.last_manual_audit + timedelta(days=audit.manual_audit_frequency_days) - timezone.now()
        hours = int(time_until.total_seconds() / 3600)
        
        return JsonResponse({
            'success': False,
            'error': f'Rate limited. Please wait {hours} hours before running another manual audit.'
        })
    
    # Queue the audit
    task = run_manual_site_audit.delay(audit.id)
    
    # Update last manual audit time
    audit.last_manual_audit = timezone.now()
    audit.save(update_fields=['last_manual_audit'])
    
    messages.success(request, f'Manual audit started for {audit.project.domain}')
    
    return JsonResponse({
        'success': True,
        'message': 'Manual audit started successfully',
        'task_id': str(task.id)
    })


@login_required
def load_more_issues(request, audit_id):
    """Load issues with HTMX pagination"""
    audit = get_object_or_404(
        SiteAudit,
        id=audit_id,
        project__user=request.user
    )
    
    # Get page number from request
    page = int(request.GET.get('page', 1))
    
    # Get per_page parameter with validation
    try:
        per_page = int(request.GET.get('per_page', 25))
        if per_page not in [25, 50, 100]:
            per_page = 25
    except (ValueError, TypeError):
        per_page = 25
    
    # Get filter parameters
    severity_filter = request.GET.get('severity', '')
    issue_type_filter = request.GET.get('issue_type', '')
    search_query = request.GET.get('search', '')
    
    # Get latest history
    latest_history = OnPagePerformanceHistory.objects.filter(
        audit=audit,
        status='completed'
    ).order_by('-created_at').first()
    
    if not latest_history:
        # Check if audit is currently running (even if no completed history)
        is_audit_running = OnPagePerformanceHistory.objects.filter(
            audit=audit,
            status__in=['pending', 'running']
        ).exists()
        
        return render(request, 'site_audit/partials/_issues_content.html', {
            'page_obj': None,
            'audit': audit,
            'per_page': per_page,
            'total_issues': 0,
            'is_audit_running': is_audit_running,
        })
    
    # Create custom ordering for severity
    from django.db.models import Case, When, IntegerField, Q
    severity_order = Case(
        When(severity='critical', then=1),
        When(severity='high', then=2),
        When(severity='medium', then=3),
        When(severity='low', then=4),
        When(severity='info', then=5),
        default=6,
        output_field=IntegerField()
    )
    
    # Build query
    issues_query = SiteIssue.objects.filter(
        performance_history=latest_history
    )
    
    # Apply filters
    if severity_filter:
        issues_query = issues_query.filter(severity=severity_filter)
    
    if issue_type_filter:
        issues_query = issues_query.filter(issue_type=issue_type_filter)
    
    if search_query:
        issues_query = issues_query.filter(
            Q(page_url__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(issue_type__icontains=search_query)
        )
    
    # Get issues with proper ordering
    issues_query = issues_query.annotate(
        severity_order=severity_order
    ).order_by('severity_order', 'issue_type', 'page_url')
    
    # Get total count for display
    total_issues = issues_query.count()
    
    # Check if audit is currently running
    is_audit_running = OnPagePerformanceHistory.objects.filter(
        audit=audit,
        status__in=['pending', 'running']
    ).exists()
    
    # Paginate
    paginator = Paginator(issues_query, per_page)
    page_obj = paginator.get_page(page)
    
    # For HTMX requests, return only the issues content
    if request.headers.get('HX-Request'):
        return render(request, 'site_audit/partials/_issues_content.html', {
            'page_obj': page_obj,
            'audit': audit,
            'severity_filter': severity_filter,
            'issue_type_filter': issue_type_filter,
            'search_query': search_query,
            'per_page': per_page,
            'total_issues': total_issues,
            'is_audit_running': is_audit_running,
        })
    
    # For regular requests, return full response
    return render(request, 'site_audit/partials/_issues_tab.html', {
        'page_obj': page_obj,
        'audit': audit,
        'severity_filter': severity_filter,
        'issue_type_filter': issue_type_filter,
        'search_query': search_query,
        'per_page': per_page,
        'total_issues': total_issues,
    })

@login_required
def site_audit_issues(request, audit_id):
    """Show all issues for a site audit"""
    audit = get_object_or_404(
        SiteAudit,
        id=audit_id,
        project__user=request.user
    )
    
    # Get filter parameters
    issue_type = request.GET.get('type', '')
    severity = request.GET.get('severity', '')
    
    # Get all issues for the latest audit
    latest_history = OnPagePerformanceHistory.objects.filter(
        audit=audit,
        status='completed'
    ).order_by('-created_at').first()
    
    if latest_history:
        issues = SiteIssue.objects.filter(
            performance_history=latest_history
        )
        
        # Apply filters
        if issue_type:
            issues = issues.filter(issue_type=issue_type)
        if severity:
            issues = issues.filter(severity=severity)
        
        issues = issues.order_by('-severity', 'issue_type', 'page_url')
    else:
        issues = SiteIssue.objects.none()
    
    # Get issue type counts
    issue_counts = SiteIssue.objects.filter(
        performance_history=latest_history
    ).values('issue_type').annotate(
        count=Count('id')
    ) if latest_history else []
    
    # Pagination
    paginator = Paginator(issues, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'site_audit/site_audit_issues.html', {
        'audit': audit,
        'page_obj': page_obj,
        'issue_type': issue_type,
        'severity': severity,
        'issue_counts': issue_counts,
        'total_issues': issues.count(),
    })


@login_required
@require_http_methods(["POST"])
def create_site_audit(request):
    """Create a new site audit for a project"""
    try:
        data = json.loads(request.body)
        project_id = data.get('project_id')
        
        if not project_id:
            return JsonResponse({
                'success': False,
                'error': 'Project ID is required'
            })
        
        # Get the project
        project = get_object_or_404(Project, id=project_id, user=request.user)
        
        # Check if audit already exists
        if SiteAudit.objects.filter(project=project).exists():
            return JsonResponse({
                'success': False,
                'error': 'Site audit already exists for this project'
            })
        
        # Create the audit
        from site_audit.tasks import create_site_audit_for_project
        result = create_site_audit_for_project.delay(project.id, 'manual')
        
        return JsonResponse({
            'success': True,
            'message': f'Site audit created for {project.domain}',
            'task_id': str(result.id)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def audit_status_stream(request, audit_id):
    """Server-Sent Events stream for audit status updates"""
    audit = get_object_or_404(
        SiteAudit,
        id=audit_id,
        project__user=request.user
    )
    
    def event_stream():
        """Generator for SSE events"""
        last_status = None
        last_progress = None
        consecutive_same = 0
        max_duration = 600  # 10 minutes maximum
        start_time = time.time()
        
        while time.time() - start_time < max_duration:
            try:
                # Get latest audit history
                latest_history = OnPagePerformanceHistory.objects.filter(
                    audit=audit
                ).order_by('-created_at').first()
                
                # Get latest performance audit
                from performance_audit.models import PerformancePage, PerformanceHistory
                perf_page = PerformancePage.objects.filter(project=audit.project).first()
                latest_perf = None
                if perf_page:
                    latest_perf = PerformanceHistory.objects.filter(
                        performance_page=perf_page
                    ).order_by('-created_at').first()
                
                # Prepare status data
                status_data = {
                    'audit_id': audit_id,
                    'timestamp': int(time.time()),
                }
                
                # Site audit status
                if latest_history:
                    site_status = latest_history.status
                    site_progress = 0
                    
                    # Calculate progress based on status and time
                    if site_status == 'pending':
                        site_progress = 5
                    elif site_status == 'running':
                        # Estimate progress based on time elapsed and retry count
                        elapsed = (timezone.now() - latest_history.created_at).total_seconds()
                        base_progress = min(30, int(elapsed / 60) * 10)  # 10% per minute, max 30%
                        retry_bonus = latest_history.retry_count * 15  # 15% per retry
                        site_progress = min(85, base_progress + retry_bonus)  # Max 85% during running
                    elif site_status == 'completed':
                        site_progress = 100
                    elif site_status == 'failed':
                        site_progress = 100  # Show complete but failed
                    
                    status_data['site_audit'] = {
                        'status': site_status,
                        'progress': site_progress,
                        'pages_crawled': latest_history.pages_crawled or 0,
                        'retry_count': latest_history.retry_count,
                        'error_message': latest_history.error_message,
                        'created_at': latest_history.created_at.isoformat() if latest_history.created_at else None
                    }
                else:
                    status_data['site_audit'] = {
                        'status': 'not_started',
                        'progress': 0,
                        'pages_crawled': 0,
                        'retry_count': 0,
                        'error_message': None,
                        'created_at': None
                    }
                
                # Performance audit status
                if latest_perf:
                    perf_status = latest_perf.status
                    perf_progress = 0
                    
                    if perf_status == 'pending':
                        perf_progress = 5
                    elif perf_status == 'running':
                        # Estimate progress for performance audit
                        elapsed = (timezone.now() - latest_perf.created_at).total_seconds()
                        perf_progress = min(90, int(elapsed / 30) * 20)  # 20% per 30 seconds, max 90%
                    elif perf_status == 'completed':
                        perf_progress = 100
                    elif perf_status == 'failed':
                        perf_progress = 100
                    
                    status_data['performance_audit'] = {
                        'status': perf_status,
                        'progress': perf_progress,
                        'mobile_score': latest_perf.mobile_performance_score,
                        'desktop_score': latest_perf.desktop_performance_score,
                        'created_at': latest_perf.created_at.isoformat() if latest_perf.created_at else None
                    }
                else:
                    status_data['performance_audit'] = {
                        'status': 'not_started',
                        'progress': 0,
                        'mobile_score': None,
                        'desktop_score': None,
                        'created_at': None
                    }
                
                # Check if both audits are completed
                both_completed = (
                    status_data['site_audit']['status'] in ['completed', 'failed'] and
                    status_data['performance_audit']['status'] in ['completed', 'failed']
                )
                
                current_status = f"{status_data['site_audit']['status']}_{status_data['performance_audit']['status']}"
                current_progress = f"{status_data['site_audit']['progress']}_{status_data['performance_audit']['progress']}"
                
                # Only send update if status changed or progress changed significantly
                if (current_status != last_status or 
                    current_progress != last_progress or 
                    consecutive_same < 3):  # Send at least 3 updates even if same
                    
                    yield f"data: {json.dumps(status_data)}\\n\\n"
                    last_status = current_status
                    last_progress = current_progress
                    consecutive_same = 0
                else:
                    consecutive_same += 1
                
                # Exit if both audits are completed
                if both_completed:
                    # Send final update
                    status_data['final'] = True
                    yield f"data: {json.dumps(status_data)}\\n\\n"
                    break
                
                # Wait before next check
                time.sleep(2)  # Check every 2 seconds
                
            except Exception as e:
                # Send error event
                error_data = {
                    'error': str(e),
                    'audit_id': audit_id,
                    'timestamp': int(time.time())
                }
                yield f"data: {json.dumps(error_data)}\\n\\n"
                break
        
        # Send final close event
        yield f"data: {json.dumps({'close': True, 'audit_id': audit_id})}\\n\\n"
    
    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Headers'] = 'Cache-Control'
    
    return response