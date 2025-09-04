"""
Background tasks for keyword report generation
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from services.r2_storage import get_r2_service
from services.email_service import send_brevo_email

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generate_keyword_report(self, report_id: int) -> Dict[str, Any]:
    """
    Generate keyword report in background
    
    Args:
        report_id: ID of KeywordReport to generate
        
    Returns:
        Dict with generation results
    """
    from .models_reports import KeywordReport
    from .report_generator import KeywordReportGenerator
    
    try:
        # Get report instance
        report = KeywordReport.objects.get(id=report_id)
        
        # Mark as processing
        report.mark_as_processing()
        
        # Initialize generator
        generator = KeywordReportGenerator(report)
        
        # Generate reports
        results = generator.generate_reports()
        
        if not results['success']:
            raise Exception(results.get('error', 'Unknown error generating report'))
        
        # Initialize R2 storage
        r2_service = get_r2_service()
        
        # Generate base path for files
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_path = f"keyword_reports/{report.project.domain}/{timestamp}"
        
        # Upload CSV if generated
        if 'csv_content' in results:
            csv_filename = f"{report.project.domain}_{report.start_date.strftime('%Y%m%d')}_{report.end_date.strftime('%Y%m%d')}.csv"
            csv_key = f"{base_path}/{csv_filename}"
            
            upload_result = r2_service.upload_file(
                results['csv_content'],  # file_obj
                csv_key,  # key
                metadata={
                    'report_id': str(report.id),
                    'project_id': str(report.project.id),
                    'type': 'keyword_report_csv'
                },
                content_type='text/csv'
            )
            
            if upload_result['success']:
                report.csv_file_path = csv_key
                report.csv_file_size = results['csv_size']
                logger.info(f"CSV uploaded to R2: {csv_key}")
            else:
                logger.error(f"Failed to upload CSV: {upload_result.get('error')}")
        
        # Upload PDF if generated
        if 'pdf_content' in results:
            pdf_filename = f"{report.project.domain}_{report.start_date.strftime('%Y%m%d')}_{report.end_date.strftime('%Y%m%d')}.pdf"
            pdf_key = f"{base_path}/{pdf_filename}"
            
            upload_result = r2_service.upload_file(
                results['pdf_content'],  # file_obj
                pdf_key,  # key
                metadata={
                    'report_id': str(report.id),
                    'project_id': str(report.project.id),
                    'type': 'keyword_report_pdf'
                },
                content_type='application/pdf'
            )
            
            if upload_result['success']:
                report.pdf_file_path = pdf_key
                report.pdf_file_size = results['pdf_size']
                logger.info(f"PDF uploaded to R2: {pdf_key}")
            else:
                logger.error(f"Failed to upload PDF: {upload_result.get('error')}")
        
        # Save file paths to database
        if report.csv_file_path or report.pdf_file_path:
            report.save(update_fields=['csv_file_path', 'csv_file_size', 'pdf_file_path', 'pdf_file_size'])
        
        # Mark as completed
        report.mark_as_completed()
        
        # Send email notification if configured
        if report.send_email_notification and report.created_by:
            send_report_ready_email.delay(report.id)
        
        return {
            'success': True,
            'report_id': report.id,
            'csv_path': report.csv_file_path,
            'pdf_path': report.pdf_file_path,
            'summary': results.get('summary', {})
        }
        
    except KeywordReport.DoesNotExist:
        logger.error(f"Report {report_id} not found")
        return {'success': False, 'error': 'Report not found'}
        
    except Exception as e:
        logger.error(f"Error generating report {report_id}: {e}", exc_info=True)
        
        # Mark as failed
        try:
            report = KeywordReport.objects.get(id=report_id)
            report.mark_as_failed(str(e))
        except:
            pass
        
        # Retry if possible
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        return {'success': False, 'error': str(e)}


@shared_task
def send_report_ready_email(report_id: int) -> bool:
    """
    Send email notification when report is ready
    
    Args:
        report_id: ID of completed report
        
    Returns:
        True if email sent successfully
    """
    from .models_reports import KeywordReport
    
    try:
        report = KeywordReport.objects.get(id=report_id)
        
        if not report.created_by or not report.created_by.email:
            logger.warning(f"No email address for report {report_id}")
            return False
        
        # Prepare email data using Brevo template 6
        email_data = {
            'to': [{'email': report.created_by.email, 'name': report.created_by.get_full_name() or report.created_by.username}],
            'templateId': 6,  # Brevo template ID as specified
            'params': {
                'report_name': report.name or f"{report.project.domain} Keyword Report"
            }
        }
        
        # Send via Brevo
        result = send_brevo_email(email_data)
        
        if result:
            # Update report
            report.email_sent = True
            report.email_sent_at = timezone.now()
            report.save(update_fields=['email_sent', 'email_sent_at'])
            
            logger.info(f"Report ready email sent for report {report_id}")
            return True
        else:
            logger.error(f"Failed to send report ready email for report {report_id}")
            return False
            
    except KeywordReport.DoesNotExist:
        logger.error(f"Report {report_id} not found")
        return False
    except Exception as e:
        logger.error(f"Error sending report email: {e}", exc_info=True)
        return False


@shared_task
def process_scheduled_reports() -> Dict[str, Any]:
    """
    Process all scheduled reports that are due to run
    Called by celery beat periodically
    
    Returns:
        Dict with processing summary
    """
    from .models_reports import ReportSchedule, KeywordReport
    
    processed = 0
    failed = 0
    
    try:
        # Get all active schedules that should run now
        due_schedules = ReportSchedule.objects.filter(
            is_active=True,
            next_run_at__lte=timezone.now()
        )
        
        logger.info(f"Found {due_schedules.count()} scheduled reports to process")
        
        for schedule in due_schedules:
            try:
                # Calculate report date range based on configuration
                end_date = timezone.now().date() - timedelta(days=1)  # Yesterday
                start_date = end_date - timedelta(days=schedule.report_period_days - 1)
                
                # Create report instance
                report = KeywordReport.objects.create(
                    project=schedule.project,
                    name=f"{schedule.name} - {end_date.strftime('%B %d, %Y')}",
                    start_date=start_date,
                    end_date=end_date,
                    report_format=schedule.report_format,
                    fill_missing_ranks=schedule.fill_missing_ranks,
                    include_competitors=schedule.include_competitors,
                    include_graphs=schedule.include_graphs,
                    created_by=schedule.created_by,
                    send_email_notification=True  # Always send for scheduled reports
                )
                
                # Copy keyword configuration
                if schedule.keywords.exists():
                    report.keywords.set(schedule.keywords.all())
                
                report.include_tags = schedule.include_tags
                report.exclude_tags = schedule.exclude_tags
                report.save()
                
                # Generate report in background
                generate_keyword_report.delay(report.id)
                
                # Update schedule
                schedule.last_run_at = timezone.now()
                schedule.last_report = report
                schedule.calculate_next_run()
                schedule.save()
                
                # Send to additional recipients if configured
                if schedule.email_recipients:
                    send_scheduled_report_emails.delay(report.id, schedule.email_recipients)
                
                processed += 1
                logger.info(f"Scheduled report {schedule.id} queued for generation")
                
            except Exception as e:
                logger.error(f"Error processing schedule {schedule.id}: {e}", exc_info=True)
                failed += 1
                
                # Still update next run time to avoid getting stuck
                try:
                    schedule.calculate_next_run()
                    schedule.save(update_fields=['next_run_at'])
                except:
                    pass
        
        return {
            'processed': processed,
            'failed': failed,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in process_scheduled_reports: {e}", exc_info=True)
        return {
            'processed': processed,
            'failed': failed,
            'error': str(e)
        }


@shared_task
def send_scheduled_report_emails(report_id: int, email_recipients: List[str]) -> int:
    """
    Send scheduled report to additional email recipients
    
    Args:
        report_id: ID of the report
        email_recipients: List of email addresses
        
    Returns:
        Number of emails sent successfully
    """
    from .models_reports import KeywordReport
    
    sent_count = 0
    
    try:
        report = KeywordReport.objects.get(id=report_id)
        
        for email in email_recipients:
            try:
                # Send using Brevo template 6
                email_data = {
                    'to': [{'email': email}],
                    'templateId': 6,
                    'params': {
                        'report_name': report.name or f"{report.project.domain} Keyword Report"
                    }
                }
                
                result = send_brevo_email(email_data)
                if result:
                    sent_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to send to {email}: {e}")
        
        logger.info(f"Sent scheduled report {report_id} to {sent_count}/{len(email_recipients)} recipients")
        
    except KeywordReport.DoesNotExist:
        logger.error(f"Report {report_id} not found")
    except Exception as e:
        logger.error(f"Error sending scheduled report emails: {e}", exc_info=True)
    
    return sent_count


@shared_task
def cleanup_old_reports(days_to_keep: int = 90) -> Dict[str, int]:
    """
    Clean up old reports and their R2 files
    
    Args:
        days_to_keep: Number of days to keep reports
        
    Returns:
        Dict with cleanup statistics
    """
    from .models_reports import KeywordReport
    
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    r2_service = get_r2_service()
    
    deleted_reports = 0
    deleted_files = 0
    
    try:
        # Find old reports
        old_reports = KeywordReport.objects.filter(
            created_at__lt=cutoff_date,
            status='completed'
        )
        
        for report in old_reports:
            # Delete R2 files
            if report.csv_file_path:
                if r2_service.delete_file(report.csv_file_path):
                    deleted_files += 1
                    logger.info(f"Deleted CSV from R2: {report.csv_file_path}")
            
            if report.pdf_file_path:
                if r2_service.delete_file(report.pdf_file_path):
                    deleted_files += 1
                    logger.info(f"Deleted PDF from R2: {report.pdf_file_path}")
        
        # Delete reports
        deleted_reports = old_reports.count()
        old_reports.delete()
        
        logger.info(f"Cleaned up {deleted_reports} old reports and {deleted_files} R2 files")
        
    except Exception as e:
        logger.error(f"Error cleaning up old reports: {e}", exc_info=True)
    
    return {
        'deleted_reports': deleted_reports,
        'deleted_files': deleted_files,
        'cutoff_date': cutoff_date.isoformat()
    }