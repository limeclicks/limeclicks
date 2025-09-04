"""
Views for keyword report management
"""

import json
import logging
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.urls import reverse

from project.models import Project
from services.r2_storage import get_r2_service
from .models_reports import KeywordReport, ReportSchedule
from .models import Keyword
from .tasks_reports import generate_keyword_report

logger = logging.getLogger(__name__)


@login_required
def report_list_view(request, project_id):
    """List all reports for a project"""
    project = get_object_or_404(Project, id=project_id)
    
    # Check permissions
    if not project.has_team_member(request.user):
        messages.error(request, "You don't have access to this project")
        return redirect('project:dashboard')
    
    # Get reports for this project
    reports = KeywordReport.objects.filter(
        project=project
    ).order_by('-created_at')
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter:
        reports = reports.filter(status=status_filter)
    
    # Filter by date range if provided
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            reports = reports.filter(start_date__gte=date_from)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            reports = reports.filter(end_date__lte=date_to)
        except ValueError:
            pass
    
    # Paginate
    paginator = Paginator(reports, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get scheduled reports
    scheduled_reports = ReportSchedule.objects.filter(
        project=project,
        is_active=True
    )
    
    context = {
        'project': project,
        'page_obj': page_obj,
        'reports': page_obj,
        'scheduled_reports': scheduled_reports,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'keywords/reports/list.html', context)


@login_required
def create_report_view(request, project_id):
    """Create a new report"""
    project = get_object_or_404(Project, id=project_id)
    
    # Check permissions
    if not project.has_team_member(request.user):
        messages.error(request, "You don't have access to this project")
        return redirect('project:dashboard')
    
    if request.method == 'POST':
        try:
            # Parse form data
            name = request.POST.get('name', '').strip()
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            report_format = request.POST.get('format', 'both')
            
            # Validate dates
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            # Validate date range (max 60 days)
            date_diff = (end_date - start_date).days
            if date_diff < 0:
                messages.error(request, "End date must be after start date")
                return redirect('keywords:create_report', project_id=project.id)
            
            if date_diff > 60:
                messages.error(request, "Report period cannot exceed 60 days")
                return redirect('keywords:create_report', project_id=project.id)
            
            # Get selected keywords
            keyword_ids = request.POST.getlist('keywords')
            
            # Get report options
            fill_missing_ranks = request.POST.get('fill_missing_ranks') == 'on'
            include_competitors = request.POST.get('include_competitors') == 'on'
            include_graphs = request.POST.get('include_graphs') == 'on'
            send_notification = request.POST.get('send_notification') == 'on'
            
            # Create report
            report = KeywordReport.objects.create(
                project=project,
                name=name or f"{project.domain} Report",
                start_date=start_date,
                end_date=end_date,
                report_format=report_format,
                fill_missing_ranks=fill_missing_ranks,
                include_competitors=include_competitors,
                include_graphs=include_graphs,
                send_email_notification=send_notification,
                created_by=request.user
            )
            
            # Add selected keywords
            if keyword_ids:
                keywords = Keyword.objects.filter(
                    id__in=keyword_ids,
                    project=project
                )
                report.keywords.set(keywords)
            
            # Generate report in background
            generate_keyword_report.delay(report.id)
            
            messages.success(request, f"Report '{report.name}' is being generated. You'll be notified when it's ready.")
            return redirect('keywords:report_detail', project_id=project.id, report_id=report.id)
            
        except ValueError as e:
            messages.error(request, f"Invalid date format: {e}")
            return redirect('keywords:create_report', project_id=project.id)
        except Exception as e:
            logger.error(f"Error creating report: {e}", exc_info=True)
            messages.error(request, f"Error creating report: {e}")
            return redirect('keywords:create_report', project_id=project.id)
    
    # GET request - show form
    keywords = Keyword.objects.filter(
        project=project,
        archive=False
    ).order_by('keyword')
    
    # Calculate default date range (last 7 days)
    default_end_date = timezone.now().date() - timedelta(days=1)  # Yesterday
    default_start_date = default_end_date - timedelta(days=6)  # 7 days ago
    
    context = {
        'project': project,
        'keywords': keywords,
        'default_start_date': default_start_date,
        'default_end_date': default_end_date,
        'max_date': timezone.now().date(),
    }
    
    return render(request, 'keywords/reports/create.html', context)


@login_required
def report_detail_view(request, project_id, report_id):
    """View report details"""
    project = get_object_or_404(Project, id=project_id)
    report = get_object_or_404(KeywordReport, id=report_id, project=project)
    
    # Check permissions
    if not project.has_team_member(request.user):
        messages.error(request, "You don't have access to this project")
        return redirect('project:dashboard')
    
    context = {
        'project': project,
        'report': report,
        'can_download': report.status == 'completed',
    }
    
    return render(request, 'keywords/reports/detail.html', context)


@login_required
def download_report_view(request, project_id, report_id):
    """Download report file"""
    project = get_object_or_404(Project, id=project_id)
    report = get_object_or_404(KeywordReport, id=report_id, project=project)
    
    # Check permissions
    if not project.has_team_member(request.user):
        raise Http404("Report not found")
    
    # Check if report is ready
    if report.status != 'completed':
        messages.error(request, "Report is not ready for download")
        return redirect('keywords:report_detail', project_id=project.id, report_id=report.id)
    
    # Get file type
    file_type = request.GET.get('type', 'csv')
    
    if file_type == 'csv' and report.csv_file_path:
        file_path = report.csv_file_path
        content_type = 'text/csv'
        filename = f"{project.domain}_report_{report.start_date}_{report.end_date}.csv"
    elif file_type == 'pdf' and report.pdf_file_path:
        file_path = report.pdf_file_path
        content_type = 'application/pdf'
        filename = f"{project.domain}_report_{report.start_date}_{report.end_date}.pdf"
    else:
        raise Http404("File not found")
    
    try:
        # Get file from R2
        r2_service = get_r2_service()
        
        # Generate presigned URL for direct download
        url_result = r2_service.generate_presigned_url(file_path, expiry=300)  # 5 minutes
        
        if url_result['success']:
            # Update download count
            report.download_count += 1
            report.last_downloaded_at = timezone.now()
            report.save(update_fields=['download_count', 'last_downloaded_at'])
            
            # Redirect to presigned URL
            return redirect(url_result['url'])
        else:
            # Fallback: Download file content and serve directly
            file_content = r2_service.download_file(file_path)
            
            if file_content:
                # Update download count
                report.download_count += 1
                report.last_downloaded_at = timezone.now()
                report.save(update_fields=['download_count', 'last_downloaded_at'])
                
                # Create response
                response = HttpResponse(file_content, content_type=content_type)
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
            else:
                raise Http404("File not found in storage")
                
    except Exception as e:
        logger.error(f"Error downloading report: {e}", exc_info=True)
        messages.error(request, "Error downloading report")
        return redirect('keywords:report_detail', project_id=project.id, report_id=report.id)


@login_required
@require_http_methods(["POST"])
def delete_report_view(request, project_id, report_id):
    """Delete a report"""
    project = get_object_or_404(Project, id=project_id)
    report = get_object_or_404(KeywordReport, id=report_id, project=project)
    
    # Check permissions
    if not project.has_team_member(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        # Delete R2 files
        r2_service = get_r2_service()
        
        if report.csv_file_path:
            r2_service.delete_file(report.csv_file_path)
        
        if report.pdf_file_path:
            r2_service.delete_file(report.pdf_file_path)
        
        # Delete report
        report.delete()
        
        messages.success(request, "Report deleted successfully")
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"Error deleting report: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def schedule_list_view(request, project_id):
    """List report schedules"""
    project = get_object_or_404(Project, id=project_id)
    
    # Check permissions
    if not project.has_team_member(request.user):
        messages.error(request, "You don't have access to this project")
        return redirect('project:dashboard')
    
    schedules = ReportSchedule.objects.filter(
        project=project
    ).order_by('-created_at')
    
    context = {
        'project': project,
        'schedules': schedules,
    }
    
    return render(request, 'keywords/reports/schedules.html', context)


@login_required
def create_schedule_view(request, project_id):
    """Create a report schedule"""
    project = get_object_or_404(Project, id=project_id)
    
    # Check permissions
    if not project.has_team_member(request.user):
        messages.error(request, "You don't have access to this project")
        return redirect('project:dashboard')
    
    if request.method == 'POST':
        try:
            # Parse form data
            name = request.POST.get('name', '').strip()
            frequency = request.POST.get('frequency', 'weekly')
            report_period_days = int(request.POST.get('report_period_days', 7))
            report_format = request.POST.get('format', 'both')
            time_of_day = request.POST.get('time_of_day', '09:00')
            
            # Parse time
            time_of_day = datetime.strptime(time_of_day, '%H:%M').time()
            
            # Get frequency-specific settings
            day_of_week = None
            day_of_month = None
            
            if frequency in ['weekly', 'biweekly']:
                day_of_week = int(request.POST.get('day_of_week', 0))
            elif frequency == 'monthly':
                day_of_month = int(request.POST.get('day_of_month', 1))
            
            # Get email recipients
            email_recipients = request.POST.get('email_recipients', '')
            email_list = [email.strip() for email in email_recipients.split(',') if email.strip()]
            
            # Get options
            fill_missing_ranks = request.POST.get('fill_missing_ranks') == 'on'
            include_competitors = request.POST.get('include_competitors') == 'on'
            include_graphs = request.POST.get('include_graphs') == 'on'
            
            # Create schedule
            schedule = ReportSchedule.objects.create(
                project=project,
                name=name or f"{project.domain} {frequency} Report",
                frequency=frequency,
                day_of_week=day_of_week,
                day_of_month=day_of_month,
                time_of_day=time_of_day,
                report_period_days=report_period_days,
                report_format=report_format,
                fill_missing_ranks=fill_missing_ranks,
                include_competitors=include_competitors,
                include_graphs=include_graphs,
                email_recipients=email_list,
                created_by=request.user
            )
            
            # Get selected keywords
            keyword_ids = request.POST.getlist('keywords')
            if keyword_ids:
                keywords = Keyword.objects.filter(
                    id__in=keyword_ids,
                    project=project
                )
                schedule.keywords.set(keywords)
            
            # Calculate next run time
            schedule.calculate_next_run()
            schedule.save()
            
            messages.success(request, f"Report schedule '{schedule.name}' created successfully")
            return redirect('keywords:schedule_list', project_id=project.id)
            
        except ValueError as e:
            messages.error(request, f"Invalid value: {e}")
            return redirect('keywords:create_schedule', project_id=project.id)
        except Exception as e:
            logger.error(f"Error creating schedule: {e}", exc_info=True)
            messages.error(request, f"Error creating schedule: {e}")
            return redirect('keywords:create_schedule', project_id=project.id)
    
    # GET request - show form
    keywords = Keyword.objects.filter(
        project=project,
        archive=False
    ).order_by('keyword')
    
    context = {
        'project': project,
        'keywords': keywords,
    }
    
    return render(request, 'keywords/reports/create_schedule.html', context)


@login_required
@require_http_methods(["POST"])
def toggle_schedule_view(request, project_id, schedule_id):
    """Toggle schedule active status"""
    project = get_object_or_404(Project, id=project_id)
    schedule = get_object_or_404(ReportSchedule, id=schedule_id, project=project)
    
    # Check permissions
    if not project.has_team_member(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        schedule.is_active = not schedule.is_active
        
        if schedule.is_active:
            # Recalculate next run time
            schedule.calculate_next_run()
        
        schedule.save()
        
        return JsonResponse({
            'success': True,
            'is_active': schedule.is_active,
            'next_run': schedule.next_run_at.isoformat() if schedule.next_run_at else None
        })
        
    except Exception as e:
        logger.error(f"Error toggling schedule: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def delete_schedule_view(request, project_id, schedule_id):
    """Delete a report schedule"""
    project = get_object_or_404(Project, id=project_id)
    schedule = get_object_or_404(ReportSchedule, id=schedule_id, project=project)
    
    # Check permissions
    if not project.has_team_member(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        schedule.delete()
        messages.success(request, "Schedule deleted successfully")
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"Error deleting schedule: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)