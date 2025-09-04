"""
Main reports list view showing all reports across projects
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q

from project.models import Project
from .models_reports import KeywordReport, ReportSchedule


@login_required
def reports_main_list(request):
    """Show all reports across all user's projects"""
    
    # Get all projects the user has access to
    user_projects = Project.objects.filter(
        Q(user=request.user) | Q(members=request.user)
    ).distinct().order_by('domain')
    
    # Get all reports for these projects
    reports = KeywordReport.objects.filter(
        project__in=user_projects
    ).select_related('project', 'created_by').order_by('-created_at')
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter:
        reports = reports.filter(status=status_filter)
    
    # Filter by project if provided
    project_filter = request.GET.get('project')
    if project_filter:
        reports = reports.filter(project_id=project_filter)
    
    # Search by name
    search = request.GET.get('search')
    if search:
        reports = reports.filter(
            Q(name__icontains=search) |
            Q(project__domain__icontains=search)
        )
    
    # Paginate
    paginator = Paginator(reports, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get schedules count
    schedules = ReportSchedule.objects.filter(
        project__in=user_projects,
        is_active=True
    ).count()
    
    # Calculate statistics
    all_reports = KeywordReport.objects.filter(project__in=user_projects)
    completed_count = all_reports.filter(status='completed').count()
    processing_count = all_reports.filter(status='processing').count()
    
    context = {
        'page_obj': page_obj,
        'reports': page_obj,
        'user_projects': user_projects,
        'status_filter': status_filter,
        'project_filter': project_filter,
        'search': search,
        'active_schedules': schedules,
        'completed_count': completed_count,
        'processing_count': processing_count,
        'page_title': 'Keyword Reports',
    }
    
    return render(request, 'keywords/reports/main_list.html', context)