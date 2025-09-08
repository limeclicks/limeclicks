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
from core.utils import simple_paginate
from django.db.models import Q
from django.utils import timezone
from django.urls import reverse

from project.models import Project
from core.permissions import require_project_access, require_project_owner
from services.r2_storage import get_r2_service
from .models_reports import KeywordReport, ReportSchedule
from .models import Keyword
from .tasks_reports import generate_keyword_report

logger = logging.getLogger(__name__)


@require_project_access
def report_list_view(request, project_id, project=None):
    """List all reports for a project"""
    # project is automatically injected by the decorator
    
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
    
    # Paginate using centralized utility
    pagination_context = simple_paginate(request, reports, 20)
    page_obj = pagination_context['page_obj']
    
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


@require_project_access
def create_report_view(request, project_id, project=None):
    """Create a new report"""
    # project is automatically injected by the decorator
    
    if request.method == 'POST':
        try:
            # Parse form data
            name = request.POST.get('name', '').strip()
            report_type = request.POST.get('report_type', 'keyword_rankings')
            report_format = request.POST.get('format', 'both')
            
            # Date validation only for keyword_rankings type
            start_date = None
            end_date = None
            
            if report_type == 'keyword_rankings':
                start_date_str = request.POST.get('start_date')
                end_date_str = request.POST.get('end_date')
                
                if not start_date_str or not end_date_str:
                    messages.error(request, "Start and end dates are required for keyword rankings reports")
                    return redirect('keywords:create_report', project_id=project.id)
                
                # Validate dates
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                
                # Validate date range (max 60 days)
                date_diff = (end_date - start_date).days
                if date_diff < 0:
                    messages.error(request, "End date must be after start date")
                    return redirect('keywords:create_report', project_id=project.id)
                
                if date_diff > 60:
                    messages.error(request, "Report period cannot exceed 60 days")
                    return redirect('keywords:create_report', project_id=project.id)
            
            # Get filter options (only for keyword_rankings type)
            selected_countries = []
            selected_tags = []
            if report_type == 'keyword_rankings':
                selected_countries = request.POST.getlist('countries')
                selected_tags = request.POST.getlist('tags')
            
            # Get report options
            include_competitors = request.POST.get('include_competitors') == 'on' if report_type == 'keyword_rankings' else False
            include_graphs = request.POST.get('include_graphs') == 'on' if report_type == 'keyword_rankings' else False
            send_notification = request.POST.get('send_notification') == 'on'
            
            # Create report
            # Generate default name based on report type
            if not name:
                if report_type == 'keyword_rankings':
                    name = f"{project.domain} Keyword Rankings - {end_date.strftime('%B %Y')}" if end_date else f"{project.domain} Keyword Rankings"
                elif report_type == 'page_rankings':
                    name = f"{project.domain} Page Rankings Report"
                elif report_type == 'top_competitors':
                    name = f"{project.domain} Top Competitors Report"
                elif report_type == 'competitors_targets':
                    name = f"{project.domain} Competitor Targets Report"
                else:
                    name = f"{project.domain} Report"
            
            report = KeywordReport.objects.create(
                project=project,
                name=name,
                report_type=report_type,
                start_date=start_date,
                end_date=end_date,
                report_format=report_format,
                include_competitors=include_competitors,
                include_graphs=include_graphs,
                send_email_notification=send_notification,
                created_by=request.user
            )
            
            # Filter keywords based on selections
            keywords = Keyword.objects.filter(
                project=project,
                archive=False
            )
            
            # Don't apply country filter - include all countries in reports
            # Country information will be included with each keyword in the report
            # if selected_countries:
            #     keywords = keywords.filter(country__in=selected_countries)
            
            # Apply tag filter
            if selected_tags:
                keywords = keywords.filter(keyword_tags__tag_id__in=selected_tags).distinct()
            
            # Store filter information in report (for reference)
            if selected_tags:
                report.include_tags = list(map(int, selected_tags))
            # Don't store country filter since we're including all countries
            # if selected_countries:
            #     report.exclude_tags = selected_countries
            if selected_tags or selected_countries:
                report.save(update_fields=['include_tags', 'exclude_tags'])
            
            # Add filtered keywords to report (or all if no filters applied)
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
    # Get unique countries from project keywords (no need to load all keywords)
    countries = Keyword.objects.filter(
        project=project,
        archive=False
    ).values_list('country', 'country_code').distinct().order_by('country')
    
    # Get all tags used by project keywords
    from .models import Tag
    tags = Tag.objects.filter(
        keyword_tags__keyword__project=project,
        is_active=True
    ).distinct().order_by('name')
    
    # Calculate default date range (last 30 days)
    default_end_date = timezone.now().date() - timedelta(days=1)  # Yesterday
    default_start_date = default_end_date - timedelta(days=29)  # 30 days ago
    
    # Get keyword count for display
    keyword_count = Keyword.objects.filter(
        project=project,
        archive=False
    ).count()
    
    context = {
        'project': project,
        'keyword_count': keyword_count,
        'countries': countries,
        'tags': tags,
        'default_start_date': default_start_date,
        'default_end_date': default_end_date,
        'max_date': timezone.now().date(),
    }
    
    return render(request, 'keywords/reports/create.html', context)


@require_project_access
def report_detail_view(request, project_id, report_id, project=None):
    """View report details"""
    report = get_object_or_404(KeywordReport, id=report_id, project=project)
    
    context = {
        'project': project,
        'report': report,
        'can_download': report.status == 'completed',
    }
    
    return render(request, 'keywords/reports/detail.html', context)


@require_project_access
def download_report_view(request, project_id, report_id, project=None):
    """Download report file"""
    report = get_object_or_404(KeywordReport, id=report_id, project=project)
    
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


@require_project_owner
@require_http_methods(["POST"])
def delete_report_view(request, project_id, report_id, project=None):
    """Delete a report and its associated R2 files"""
    report = get_object_or_404(KeywordReport, id=report_id, project=project)
    
    try:
        # Delete R2 files if they exist
        deleted_files = []
        try:
            r2_service = get_r2_service()
            
            if report.csv_file_path:
                try:
                    r2_service.delete_file(report.csv_file_path)
                    deleted_files.append(f"CSV: {report.csv_file_path}")
                    logger.info(f"Deleted R2 file: {report.csv_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete CSV from R2: {e}")
            
            if report.pdf_file_path:
                try:
                    r2_service.delete_file(report.pdf_file_path)
                    deleted_files.append(f"PDF: {report.pdf_file_path}")
                    logger.info(f"Deleted R2 file: {report.pdf_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete PDF from R2: {e}")
                    
        except Exception as e:
            logger.error(f"R2 service error: {e}")
            # Continue with report deletion even if R2 deletion fails
        
        # Store report info for logging
        report_info = f"Report #{report.id} for {report.project.domain}"
        
        # Delete the database record
        report.delete()
        
        logger.info(f"Deleted {report_info}. Removed files: {deleted_files}")
        messages.success(request, f"Report deleted successfully")
        
        # Return success with redirect URL for HTMX
        return JsonResponse({
            'success': True,
            'message': 'Report deleted successfully',
            'redirect': reverse('keywords:report_list', args=[project_id])
        })
        
    except Exception as e:
        logger.error(f"Error deleting report {report_id}: {e}", exc_info=True)
        messages.error(request, f"Error deleting report: {str(e)}")
        return JsonResponse({'error': f'Failed to delete report: {str(e)}'}, status=500)


@require_project_access
def schedule_list_view(request, project_id, project=None):
    """List report schedules"""
    # project is automatically injected by the decorator
    
    schedules = ReportSchedule.objects.filter(
        project=project
    ).order_by('-created_at')
    
    context = {
        'project': project,
        'schedules': schedules,
    }
    
    return render(request, 'keywords/reports/schedules.html', context)


@require_project_access
def create_schedule_view(request, project_id, project=None):
    """Create a report schedule"""
    # project is automatically injected by the decorator
    
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
            fill_missing_ranks = True  # Always fill missing ranks by default
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
            
            # Get filter options
            selected_countries = request.POST.getlist('countries')
            selected_tags = request.POST.getlist('tags')
            
            # Store filter information
            if selected_tags:
                schedule.include_tags = list(map(int, selected_tags))
            if selected_countries:
                schedule.exclude_tags = selected_countries  # Using exclude_tags for countries temporarily
            if selected_tags or selected_countries:
                schedule.save(update_fields=['include_tags', 'exclude_tags'])
            
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
    # Get unique countries from project keywords
    countries = Keyword.objects.filter(
        project=project,
        archive=False
    ).values_list('country', 'country_code').distinct().order_by('country')
    
    # Get all tags used by project keywords
    from .models import Tag
    tags = Tag.objects.filter(
        keyword_tags__keyword__project=project,
        is_active=True
    ).distinct().order_by('name')
    
    context = {
        'project': project,
        'countries': countries,
        'tags': tags,
    }
    
    return render(request, 'keywords/reports/create_schedule.html', context)


@require_project_access
@require_http_methods(["POST"])
def toggle_schedule_view(request, project_id, schedule_id, project=None):
    """Toggle schedule active status"""
    schedule = get_object_or_404(ReportSchedule, id=schedule_id, project=project)
    
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


@require_project_access
@require_http_methods(["POST"])
def delete_schedule_view(request, project_id, schedule_id, project=None):
    """Delete a report schedule"""
    schedule = get_object_or_404(ReportSchedule, id=schedule_id, project=project)
    
    try:
        schedule.delete()
        messages.success(request, "Schedule deleted successfully")
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"Error deleting schedule: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)