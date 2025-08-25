from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from typing import Optional

from .models import AuditPage, AuditHistory, AuditSchedule
from .lighthouse_runner import LighthouseRunner, LighthouseService

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_lighthouse_audit(self, audit_history_id: str, device_type: str = 'desktop'):
    """
    Run a Lighthouse audit for a specific audit history entry
    
    Args:
        audit_history_id: UUID of the AuditHistory record
        device_type: 'desktop' or 'mobile'
    """
    try:
        audit_history = AuditHistory.objects.get(id=audit_history_id)
        audit_page = audit_history.audit_page
        
        # Update status to running
        audit_history.status = 'running'
        audit_history.started_at = timezone.now()
        audit_history.save(update_fields=['status', 'started_at'])
        
        logger.info(f"Starting Lighthouse audit for {audit_page.page_url} ({device_type})")
        
        # Ensure Lighthouse is installed
        if not LighthouseService.check_lighthouse_installed():
            logger.info("Lighthouse not found, attempting to install...")
            if not LighthouseService.install_lighthouse():
                raise Exception("Failed to install Lighthouse")
        
        # Run the audit
        runner = LighthouseRunner()
        success, results, error = runner.run_audit(audit_page.page_url, device_type)
        
        if not success:
            raise Exception(error or "Audit failed with unknown error")
        
        # Save results
        runner.save_audit_results(audit_history, results)
        
        logger.info(f"Successfully completed audit for {audit_page.page_url}")
        
        # Schedule next audit if this was a scheduled audit
        if audit_history.trigger_type == 'scheduled':
            audit_page.schedule_next_audit()
        
        return {
            'success': True,
            'audit_id': str(audit_history.id),
            'scores': {
                'performance': results.get('performance_score'),
                'accessibility': results.get('accessibility_score'),
                'best_practices': results.get('best_practices_score'),
                'seo': results.get('seo_score'),
                'pwa': results.get('pwa_score')
            }
        }
        
    except AuditHistory.DoesNotExist:
        logger.error(f"AuditHistory {audit_history_id} not found")
        return {'success': False, 'error': 'Audit history not found'}
        
    except Exception as e:
        logger.error(f"Error running audit: {str(e)}")
        
        # Update audit history with error
        try:
            audit_history = AuditHistory.objects.get(id=audit_history_id)
            audit_history.status = 'failed'
            audit_history.error_message = str(e)
            audit_history.retry_count += 1
            audit_history.save()
        except:
            pass
        
        # Retry if we haven't exceeded max retries
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying audit (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        return {'success': False, 'error': str(e)}


@shared_task
def create_audit_for_project(project_id: int, trigger_type: str = 'project_created'):
    """
    Create and run an audit when a new project is added
    
    Args:
        project_id: ID of the project
        trigger_type: Type of trigger for the audit
    """
    from project.models import Project
    
    try:
        project = Project.objects.get(id=project_id)
        
        # Create or get the audit page
        audit_page, created = AuditPage.objects.get_or_create(
            project=project,
            defaults={
                'page_url': f"https://{project.domain}" if not project.domain.startswith('http') else project.domain
            }
        )
        
        if created:
            logger.info(f"Created new audit page for project {project.domain}")
        
        # Create audit history entries for both desktop and mobile
        for device_type in ['desktop', 'mobile']:
            audit_history = AuditHistory.objects.create(
                audit_page=audit_page,
                trigger_type=trigger_type,
                device_type=device_type,
                status='pending'
            )
            
            # Queue the audit
            run_lighthouse_audit.delay(str(audit_history.id), device_type)
            
            logger.info(f"Queued {device_type} audit for project {project.domain}")
        
        return {'success': True, 'project_id': project_id}
        
    except Project.DoesNotExist:
        logger.error(f"Project {project_id} not found")
        return {'success': False, 'error': 'Project not found'}
    except Exception as e:
        logger.error(f"Error creating audit for project: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def run_manual_audit(audit_page_id: int, user_id: Optional[int] = None):
    """
    Run a manual audit with rate limiting
    
    Args:
        audit_page_id: ID of the audit page
        user_id: Optional user ID who triggered the audit
    """
    try:
        audit_page = AuditPage.objects.get(id=audit_page_id)
        
        # Check rate limiting
        if not audit_page.can_run_manual_audit():
            time_until_next = (audit_page.last_manual_audit + timedelta(days=1)) - timezone.now()
            hours_remaining = int(time_until_next.total_seconds() / 3600)
            return {
                'success': False,
                'error': f'Rate limited. Please wait {hours_remaining} hours before running another manual audit.'
            }
        
        # Update last manual audit time
        audit_page.last_manual_audit = timezone.now()
        audit_page.save(update_fields=['last_manual_audit'])
        
        # Create audit history entries for both desktop and mobile
        audit_ids = []
        for device_type in ['desktop', 'mobile']:
            audit_history = AuditHistory.objects.create(
                audit_page=audit_page,
                trigger_type='manual',
                device_type=device_type,
                status='pending'
            )
            audit_ids.append(str(audit_history.id))
            
            # Queue the audit
            run_lighthouse_audit.delay(str(audit_history.id), device_type)
        
        logger.info(f"Manual audit triggered for {audit_page.page_url}")
        
        return {
            'success': True,
            'audit_ids': audit_ids,
            'message': 'Manual audit started for both desktop and mobile'
        }
        
    except AuditPage.DoesNotExist:
        return {'success': False, 'error': 'Audit page not found'}
    except Exception as e:
        logger.error(f"Error running manual audit: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def check_scheduled_audits():
    """
    Check for audit pages that need scheduled audits and queue them
    This should be run periodically (e.g., every hour)
    """
    now = timezone.now()
    
    # Find audit pages that need audits
    audit_pages = AuditPage.objects.filter(
        is_audit_enabled=True,
        next_scheduled_audit__lte=now
    )
    
    scheduled_count = 0
    
    for audit_page in audit_pages:
        try:
            with transaction.atomic():
                # Check if we already have a schedule for this time
                schedule, created = AuditSchedule.objects.get_or_create(
                    audit_page=audit_page,
                    scheduled_for=audit_page.next_scheduled_audit,
                    defaults={'is_processed': False}
                )
                
                if created or not schedule.is_processed:
                    # Create audit history entries for both desktop and mobile
                    for device_type in ['desktop', 'mobile']:
                        audit_history = AuditHistory.objects.create(
                            audit_page=audit_page,
                            trigger_type='scheduled',
                            device_type=device_type,
                            status='pending'
                        )
                        
                        # Queue the audit
                        task = run_lighthouse_audit.delay(str(audit_history.id), device_type)
                        
                        if device_type == 'desktop':
                            schedule.task_id = task.id
                    
                    # Mark schedule as processed
                    schedule.is_processed = True
                    schedule.processed_at = now
                    schedule.save()
                    
                    # Schedule the next audit
                    audit_page.schedule_next_audit()
                    
                    scheduled_count += 1
                    logger.info(f"Scheduled audit for {audit_page.page_url}")
                
        except Exception as e:
            logger.error(f"Error scheduling audit for {audit_page.page_url}: {str(e)}")
            continue
    
    logger.info(f"Scheduled {scheduled_count} audits")
    
    return {
        'success': True,
        'scheduled_count': scheduled_count,
        'checked_at': now.isoformat()
    }


@shared_task
def cleanup_old_audits(days_to_keep: int = 90):
    """
    Clean up old audit history records
    
    Args:
        days_to_keep: Number of days of history to keep
    """
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    
    # Get audits to delete
    old_audits = AuditHistory.objects.filter(
        created_at__lt=cutoff_date
    )
    
    deleted_count = 0
    
    for audit in old_audits:
        try:
            # Delete associated files from R2
            if audit.json_report:
                audit.json_report.delete()
            if audit.html_report:
                audit.html_report.delete()
            
            # Delete the audit record
            audit.delete()
            deleted_count += 1
            
        except Exception as e:
            logger.error(f"Error deleting audit {audit.id}: {str(e)}")
            continue
    
    logger.info(f"Deleted {deleted_count} old audit records")
    
    return {
        'success': True,
        'deleted_count': deleted_count,
        'cutoff_date': cutoff_date.isoformat()
    }


@shared_task
def generate_audit_report(audit_page_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """
    Generate a comprehensive audit report for an audit page
    
    Args:
        audit_page_id: ID of the audit page
        start_date: Optional start date for the report
        end_date: Optional end date for the report
    """
    try:
        from datetime import datetime
        
        audit_page = AuditPage.objects.get(id=audit_page_id)
        
        # Parse dates if provided
        filters = {'audit_page': audit_page, 'status': 'completed'}
        if start_date:
            filters['created_at__gte'] = datetime.fromisoformat(start_date)
        if end_date:
            filters['created_at__lte'] = datetime.fromisoformat(end_date)
        
        # Get audit history
        audits = AuditHistory.objects.filter(**filters).order_by('created_at')
        
        # Generate report data
        report = {
            'audit_page': {
                'project': audit_page.project.domain,
                'url': audit_page.page_url,
                'audit_frequency': audit_page.audit_frequency_days
            },
            'summary': {
                'total_audits': audits.count(),
                'desktop_audits': audits.filter(device_type='desktop').count(),
                'mobile_audits': audits.filter(device_type='mobile').count(),
                'failed_audits': AuditHistory.objects.filter(
                    audit_page=audit_page,
                    status='failed'
                ).count()
            },
            'latest_scores': {
                'desktop': {},
                'mobile': {}
            },
            'score_trends': {
                'desktop': [],
                'mobile': []
            }
        }
        
        # Get latest scores for each device type
        for device_type in ['desktop', 'mobile']:
            latest = audits.filter(device_type=device_type).last()
            if latest:
                report['latest_scores'][device_type] = {
                    'performance': latest.performance_score,
                    'accessibility': latest.accessibility_score,
                    'best_practices': latest.best_practices_score,
                    'seo': latest.seo_score,
                    'pwa': latest.pwa_score,
                    'date': latest.created_at.isoformat()
                }
                
                # Get score trends
                for audit in audits.filter(device_type=device_type)[:10]:  # Last 10 audits
                    report['score_trends'][device_type].append({
                        'date': audit.created_at.isoformat(),
                        'performance': audit.performance_score,
                        'accessibility': audit.accessibility_score,
                        'best_practices': audit.best_practices_score,
                        'seo': audit.seo_score,
                        'pwa': audit.pwa_score
                    })
        
        logger.info(f"Generated report for {audit_page.page_url}")
        
        return {
            'success': True,
            'report': report
        }
        
    except AuditPage.DoesNotExist:
        return {'success': False, 'error': 'Audit page not found'}
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        return {'success': False, 'error': str(e)}