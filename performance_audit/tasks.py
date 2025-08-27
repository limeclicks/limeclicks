from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from typing import Optional
import time
from django.core.cache import cache

from .models import PerformancePage, PerformanceHistory, PerformanceSchedule
from .lighthouse_runner import LighthouseRunner, LighthouseService

logger = get_task_logger(__name__)

# Global lighthouse execution lock
LIGHTHOUSE_LOCK_KEY = 'lighthouse_audit_running'
LIGHTHOUSE_LOCK_TIMEOUT = 900  # 15 minutes


@shared_task(
    bind=True, 
    max_retries=5,  # Increased to 5 retries
    default_retry_delay=180,  # 3 minutes default delay
    rate_limit='30/h',  # 30 audits per hour globally for stability
    time_limit=900,  # 15 minute timeout (increased)
    soft_time_limit=780  # 13 minute soft timeout
)
def run_lighthouse_audit(self, performance_history_id: str):
    """
    Run Lighthouse audits for both mobile and desktop in a single record
    
    Args:
        performance_history_id: UUID of the PerformanceHistory record
    """
    # Acquire global lighthouse lock to ensure single process execution
    try:
        # Try to acquire lock with unique task ID
        lock_value = f"{self.request.id}_{time.time()}"
        if not cache.add(LIGHTHOUSE_LOCK_KEY, lock_value, LIGHTHOUSE_LOCK_TIMEOUT):
            # Lock is already held, check if it's expired
            existing_lock = cache.get(LIGHTHOUSE_LOCK_KEY)
            if existing_lock:
                # Lock exists, retry later
                logger.info("Another Lighthouse audit is already running, retrying in 3 minutes...")
                raise self.retry(countdown=180, max_retries=5)
            else:
                # Try to acquire again 
                if not cache.add(LIGHTHOUSE_LOCK_KEY, lock_value, LIGHTHOUSE_LOCK_TIMEOUT):
                    raise self.retry(countdown=180, max_retries=5)
        
        logger.info(f"Acquired Lighthouse lock: {lock_value}")
        
        try:
            performance_history = PerformanceHistory.objects.get(id=performance_history_id)
            performance_page = performance_history.performance_page
            
            # Update status to running
            performance_history.status = 'running'
            performance_history.started_at = timezone.now()
            performance_history.save(update_fields=['status', 'started_at'])
            
            logger.info(f"Starting Lighthouse audits for {performance_page.page_url} (both mobile & desktop)")
            
            # Ensure Lighthouse is installed
            if not LighthouseService.check_lighthouse_installed():
                logger.info("Lighthouse not found, attempting to install...")
                if not LighthouseService.install_lighthouse():
                    raise Exception("Failed to install Lighthouse")
            
            runner = LighthouseRunner()
            audit_results = {'mobile': None, 'desktop': None}
            errors = []
            
            # Run mobile audit first
            logger.info(f"Running mobile audit for {performance_page.page_url}")
            success, mobile_results, error = runner.run_audit(performance_page.page_url, 'mobile')
            if success:
                audit_results['mobile'] = mobile_results
            else:
                errors.append(f"Mobile audit failed: {error}")
                logger.error(f"Mobile audit failed: {error}")
            
            # Run desktop audit
            logger.info(f"Running desktop audit for {performance_page.page_url}")
            success, desktop_results, error = runner.run_audit(performance_page.page_url, 'desktop')
            if success:
                audit_results['desktop'] = desktop_results
            else:
                errors.append(f"Desktop audit failed: {error}")
                logger.error(f"Desktop audit failed: {error}")
            
            # Check if at least one audit succeeded
            if not audit_results['mobile'] and not audit_results['desktop']:
                raise Exception("; ".join(errors) if errors else "Both audits failed with unknown error")
            
            # Save combined results
            runner.save_combined_audit_results(performance_history, audit_results)
            
            logger.info(f"Successfully completed audits for {performance_page.page_url}")
            
            # Schedule next audit if this was a scheduled audit
            if performance_history.trigger_type == 'scheduled':
                performance_page.schedule_next_audit()
            
            # Prepare response with both scores
            response = {
                'success': True,
                'audit_id': str(performance_history.id),
                'scores': {}
            }
            
            if audit_results['mobile']:
                response['scores']['mobile'] = {
                    'performance': audit_results['mobile'].get('performance_score'),
                    'accessibility': audit_results['mobile'].get('accessibility_score'),
                    'best_practices': audit_results['mobile'].get('best_practices_score'),
                    'seo': audit_results['mobile'].get('seo_score'),
                    'pwa': audit_results['mobile'].get('pwa_score')
                }
            
            if audit_results['desktop']:
                response['scores']['desktop'] = {
                    'performance': audit_results['desktop'].get('performance_score'),
                    'accessibility': audit_results['desktop'].get('accessibility_score'),
                    'best_practices': audit_results['desktop'].get('best_practices_score'),
                    'seo': audit_results['desktop'].get('seo_score'),
                    'pwa': audit_results['desktop'].get('pwa_score')
                }
        
            return response
            
        finally:
            # Always release the lock
            try:
                current_lock = cache.get(LIGHTHOUSE_LOCK_KEY)
                if current_lock == lock_value:
                    cache.delete(LIGHTHOUSE_LOCK_KEY)
                    logger.info(f"Released Lighthouse lock: {lock_value}")
            except:
                pass
        
    except PerformanceHistory.DoesNotExist:
        logger.error(f"PerformanceHistory {performance_history_id} not found")
        return {'success': False, 'error': 'Audit history not found'}
        
    except Exception as e:
        logger.error(f"Error running audit: {str(e)}")
        
        # Always release the lock on error
        try:
            cache.delete(LIGHTHOUSE_LOCK_KEY)
        except:
            pass
        
        # Update audit history with error
        try:
            performance_history = PerformanceHistory.objects.get(id=performance_history_id)
            performance_history.status = 'failed'
            performance_history.error_message = str(e)
            performance_history.retry_count += 1
            performance_history.save()
        except:
            pass
        
        # Retry if we haven't exceeded max retries
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying audit (attempt {self.request.retries + 1}/{self.max_retries})")
            # Progressive backoff: 3 minutes, 6 minutes, 12 minutes, 24 minutes, 48 minutes
            countdown = 180 * (2 ** self.request.retries)
            raise self.retry(exc=e, countdown=countdown)
        
        return {'success': False, 'error': str(e)}


@shared_task
def create_audit_for_project(project_id: int, trigger_type: str = 'project_created'):
    """
    Create and run a combined audit (mobile & desktop) when a new project is added
    
    Args:
        project_id: ID of the project
        trigger_type: Type of trigger for the audit
    """
    from project.models import Project
    
    try:
        project = Project.objects.get(id=project_id)
        
        # Create or get the audit page
        performance_page, created = PerformancePage.objects.get_or_create(
            project=project,
            defaults={
                'page_url': f"https://{project.domain}" if not project.domain.startswith('http') else project.domain
            }
        )
        
        if created:
            logger.info(f"Created new audit page for project {project.domain}")
        
        # Check for existing audits today to prevent duplicates
        from datetime import datetime, timedelta
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        # Check if audit already exists for today (any status)
        existing_audit = PerformanceHistory.objects.filter(
            performance_page=performance_page,
            created_at__gte=today_start,
            created_at__lt=today_end
        ).exclude(status='failed').exists()  # Allow retry if failed
        
        if existing_audit:
            logger.info(f"Audit already exists today for {project.domain}, skipping")
            return {'success': True, 'project_id': project_id, 'message': 'Audit already exists today'}
        
        # Create a single audit history record for both mobile and desktop
        performance_history = PerformanceHistory.objects.create(
            performance_page=performance_page,
            trigger_type=trigger_type,
            status='pending'
        )
        
        # Queue the combined audit
        run_lighthouse_audit.delay(str(performance_history.id))
        
        logger.info(f"Queued combined mobile & desktop audit for project {project.domain}")
        
        return {'success': True, 'project_id': project_id, 'audit_id': str(performance_history.id)}
        
    except Project.DoesNotExist:
        logger.error(f"Project {project_id} not found")
        return {'success': False, 'error': 'Project not found'}
    except Exception as e:
        logger.error(f"Error creating audit for project: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def run_manual_audit(performance_page_id: int, user_id: Optional[int] = None):
    """
    Run a manual combined audit with rate limiting
    
    Args:
        performance_page_id: ID of the audit page
        user_id: Optional user ID who triggered the audit
    """
    try:
        performance_page = PerformancePage.objects.get(id=performance_page_id)
        
        # Check rate limiting
        if not performance_page.can_run_manual_audit():
            time_until_next = (performance_page.last_manual_audit + timedelta(days=1)) - timezone.now()
            hours_remaining = int(time_until_next.total_seconds() / 3600)
            return {
                'success': False,
                'error': f'Rate limited. Please wait {hours_remaining} hours before running another manual audit.'
            }
        
        # Check for existing audits today
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        existing_audit = PerformanceHistory.objects.filter(
            performance_page=performance_page,
            created_at__gte=today_start,
            created_at__lt=today_end
        ).exclude(status='failed').exists()
        
        if existing_audit:
            return {
                'success': False,
                'error': 'An audit already exists today. Only one combined audit per day is allowed.'
            }
        
        # Update last manual audit time
        performance_page.last_manual_audit = timezone.now()
        performance_page.save(update_fields=['last_manual_audit'])
        
        # Create a single audit history record for both mobile and desktop
        performance_history = PerformanceHistory.objects.create(
            performance_page=performance_page,
            trigger_type='manual',
            status='pending'
        )
        
        # Queue the combined audit
        run_lighthouse_audit.delay(str(performance_history.id))
        
        logger.info(f"Manual combined audit triggered for {performance_page.page_url}")
        
        return {
            'success': True,
            'audit_id': str(performance_history.id),
            'message': 'Manual audit started for both mobile and desktop'
        }
        
    except PerformancePage.DoesNotExist:
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
    performance_pages = PerformancePage.objects.filter(
        is_audit_enabled=True,
        next_scheduled_audit__lte=now
    )
    
    scheduled_count = 0
    
    for performance_page in performance_pages:
        try:
            with transaction.atomic():
                # Check if we already have audits today
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                today_end = today_start + timedelta(days=1)
                
                existing_today = PerformanceHistory.objects.filter(
                    performance_page=performance_page,
                    created_at__gte=today_start,
                    created_at__lt=today_end
                ).exclude(status='failed').exists()
                
                if existing_today:
                    # Already have audit for today, schedule for next period
                    performance_page.schedule_next_audit()
                    logger.info(f"Audit already exists for {performance_page.page_url} today, scheduling next period")
                    continue
                
                # Check if we already have a schedule for this time
                schedule, created = PerformanceSchedule.objects.get_or_create(
                    performance_page=performance_page,
                    scheduled_for=performance_page.next_scheduled_audit,
                    defaults={'is_processed': False}
                )
                
                if created or not schedule.is_processed:
                    # Create a single combined audit history entry
                    performance_history = PerformanceHistory.objects.create(
                        performance_page=performance_page,
                        trigger_type='scheduled',
                        status='pending'
                    )
                    
                    # Queue the combined audit
                    task = run_lighthouse_audit.delay(str(performance_history.id))
                    schedule.task_id = task.id
                    
                    # Mark schedule as processed
                    schedule.is_processed = True
                    schedule.processed_at = now
                    schedule.save()
                    
                    # Schedule the next audit
                    performance_page.schedule_next_audit()
                    
                    scheduled_count += 1
                    logger.info(f"Scheduled audit for {performance_page.page_url}")
                
        except Exception as e:
            logger.error(f"Error scheduling audit for {performance_page.page_url}: {str(e)}")
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
    old_audits = PerformanceHistory.objects.filter(
        created_at__lt=cutoff_date
    )
    
    deleted_count = 0
    
    for audit in old_performance_audit:
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
def generate_audit_report(performance_page_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """
    Generate a comprehensive audit report for an audit page
    
    Args:
        performance_page_id: ID of the audit page
        start_date: Optional start date for the report
        end_date: Optional end date for the report
    """
    try:
        from datetime import datetime
        
        performance_page = PerformancePage.objects.get(id=performance_page_id)
        
        # Parse dates if provided
        filters = {'performance_page': performance_page, 'status': 'completed'}
        if start_date:
            filters['created_at__gte'] = datetime.fromisoformat(start_date)
        if end_date:
            filters['created_at__lte'] = datetime.fromisoformat(end_date)
        
        # Get audit history
        audits = PerformanceHistory.objects.filter(**filters).order_by('created_at')
        
        # Generate report data
        report = {
            'performance_page': {
                'project': performance_page.project.domain,
                'url': performance_page.page_url,
                'audit_frequency': performance_page.audit_frequency_days
            },
            'summary': {
                'total_audits': performance_audit.count(),
                'desktop_audits': performance_audit.filter(device_type='desktop').count(),
                'mobile_audits': performance_audit.filter(device_type='mobile').count(),
                'failed_audits': PerformanceHistory.objects.filter(
                    performance_page=performance_page,
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
            latest = performance_audit.filter(device_type=device_type).last()
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
                for audit in performance_audit.filter(device_type=device_type)[:10]:  # Last 10 audits
                    report['score_trends'][device_type].append({
                        'date': audit.created_at.isoformat(),
                        'performance': audit.performance_score,
                        'accessibility': audit.accessibility_score,
                        'best_practices': audit.best_practices_score,
                        'seo': audit.seo_score,
                        'pwa': audit.pwa_score
                    })
        
        logger.info(f"Generated report for {performance_page.page_url}")
        
        return {
            'success': True,
            'report': report
        }
        
    except PerformancePage.DoesNotExist:
        return {'success': False, 'error': 'Audit page not found'}
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        return {'success': False, 'error': str(e)}