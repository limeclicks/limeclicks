from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .models import AuditPage, AuditHistory
from .tasks import run_manual_audit, generate_audit_report
from project.models import Project


@login_required
def audit_dashboard(request, project_id):
    """Display audit dashboard for a project"""
    project = get_object_or_404(Project, id=project_id, user=request.user)
    
    # Get or create audit page
    audit_page, created = AuditPage.objects.get_or_create(
        project=project,
        defaults={
            'page_url': f"https://{project.domain}" if not project.domain.startswith('http') else project.domain
        }
    )
    
    # Get audit history
    audit_history = AuditHistory.objects.filter(
        audit_page=audit_page
    ).order_by('-created_at')
    
    # Separate by device type
    desktop_audits = audit_history.filter(device_type='desktop')[:5]
    mobile_audits = audit_history.filter(device_type='mobile')[:5]
    
    # Get latest scores
    latest_desktop = desktop_audits.first()
    latest_mobile = mobile_audits.first()
    
    # Check if manual audit can be run
    can_run_manual = audit_page.can_run_manual_audit()
    time_until_manual = None
    if not can_run_manual and audit_page.last_manual_audit:
        time_until_manual = (audit_page.last_manual_audit + timedelta(days=1)) - timezone.now()
    
    context = {
        'project': project,
        'audit_page': audit_page,
        'latest_desktop': latest_desktop,
        'latest_mobile': latest_mobile,
        'desktop_audits': desktop_audits,
        'mobile_audits': mobile_audits,
        'can_run_manual': can_run_manual,
        'time_until_manual': time_until_manual,
    }
    
    return render(request, 'audits/dashboard.html', context)


@login_required
@require_POST
def trigger_manual_audit(request, project_id):
    """Trigger a manual audit for a project"""
    project = get_object_or_404(Project, id=project_id, user=request.user)
    
    # Get the audit page
    audit_page = get_object_or_404(AuditPage, project=project)
    
    # Trigger the manual audit
    result = run_manual_audit.delay(audit_page.id, request.user.id)
    
    if result:
        messages.success(request, 'Manual audit started successfully. Results will be available soon.')
    else:
        messages.error(request, 'Failed to start audit. Please try again.')
    
    return redirect('audits:dashboard', project_id=project.id)
