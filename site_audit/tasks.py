"""
Celery tasks for site audits using Screaming Frog
"""

import logging
import shutil
from datetime import timedelta
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import SiteAudit
from .screaming_frog import ScreamingFrogCLI

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    time_limit=1800,  # Hard limit of 30 minutes for site audit jobs
    soft_time_limit=1500,  # Soft limit of 25 minutes
)
def run_site_audit(self, site_audit_id: int) -> dict:
    """
    Run a comprehensive site audit using Screaming Frog.
    
    This task has a 30-minute timeout to accommodate:
    - Screaming Frog subprocess timeout of 15 minutes
    - Additional time for setup, parsing, and database updates
    
    Args:
        site_audit_id: ID of the SiteAudit instance
        
    Returns:
        dict: Results of the audit including pages crawled and issues found
    """
    lock_key = f"lock:site_audit:{site_audit_id}"
    lock_timeout = 2100  # 35 minutes (longer than task timeout)
    
    try:
        # Try to acquire lock
        if not cache.add(lock_key, "locked", timeout=lock_timeout):
            logger.info(f"Site audit already running for id={site_audit_id}, skipping")
            return {"status": "already_running"}
        
        # Fetch site audit
        try:
            site_audit = SiteAudit.objects.get(id=site_audit_id)
        except SiteAudit.DoesNotExist:
            logger.error(f"SiteAudit with id={site_audit_id} not found")
            return {"status": "error", "message": "SiteAudit not found"}
        
        project = site_audit.project
        logger.info(f"Starting site audit for {project.domain}")
        
        # Initialize Screaming Frog
        sf_cli = ScreamingFrogCLI()
        
        # Run the crawl with retry logic for network issues
        max_pages = site_audit.max_pages_to_crawl
        success = False
        output_dir = None
        error_message = None
        
        for attempt in range(3):
            try:
                success, output_dir, error_message = sf_cli.crawl_website(
                    url=f"https://{project.domain}",
                    max_pages=max_pages
                )
                
                if success:
                    break
                    
                logger.warning(f"Crawl attempt {attempt + 1} failed: {error_message}")
                
            except Exception as e:
                logger.error(f"Crawl attempt {attempt + 1} exception: {e}")
                error_message = str(e)
                
            if attempt < 2:  # Don't sleep after last attempt
                # Exponential backoff: 30s, 60s
                sleep_time = 30 * (attempt + 1)
                logger.info(f"Retrying in {sleep_time} seconds...")
                import time
                time.sleep(sleep_time)
        
        if not success:
            logger.error(f"All crawl attempts failed for {project.domain}")
            return {
                "status": "error",
                "message": f"Crawl failed: {error_message}"
            }
        
        # Parse results
        try:
            results = sf_cli.parse_crawl_results(output_dir)
            pages_crawled = results.get('pages_crawled', 0)
            
            # Update site audit with results
            site_audit.total_pages_crawled = pages_crawled
            site_audit.last_audit_date = timezone.now()
            
            # Update audit status and parse CSV overview
            site_audit.status = 'running'
            site_audit.save(update_fields=['status'])
            
            # Parse issues overview from CSV if available
            issues_overview_path = None
            if output_dir:
                potential_csv = Path(output_dir) / 'issues_overview_report.csv'
                if potential_csv.exists():
                    issues_overview_path = str(potential_csv)
            
            if issues_overview_path:
                try:
                    issues_count = site_audit.update_from_csv_overview(issues_overview_path)
                    logger.info(f"Parsed {issues_count} issues from overview CSV")
                except Exception as e:
                    logger.error(f"Failed to parse CSV overview: {e}")
                    site_audit.status = 'failed'
                    site_audit.save(update_fields=['status'])
                    return {
                        "status": "error",
                        "message": f"CSV parsing failed: {str(e)}"
                    }
            
            # Calculate overall site health score from overview data
            site_audit.calculate_overall_score()
            
            # Update next scheduled audit
            site_audit.last_automatic_audit = timezone.now()
            site_audit.next_scheduled_audit = timezone.now() + timedelta(days=site_audit.audit_frequency_days)
            
            # Mark audit as completed
            site_audit.status = 'completed'
            site_audit.save()
            
            total_issues = site_audit.get_total_issues_count()
            logger.info(
                f"Site audit completed for {project.domain}: "
                f"{pages_crawled} pages, {total_issues} issues, "
                f"health score: {site_audit.overall_site_health_score:.1f}%"
            )
            
            # Clean up temporary directory
            if output_dir and Path(output_dir).exists():
                try:
                    shutil.rmtree(output_dir)
                    logger.info(f"Cleaned up temporary directory: {output_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up {output_dir}: {e}")
            
            return {
                "status": "success",
                "pages_crawled": pages_crawled,
                "total_issues": site_audit.get_total_issues_count(),
                "health_score": site_audit.overall_site_health_score,
                "output_files": results.get('files', [])
            }
            
        except Exception as e:
            logger.error(f"Error parsing results: {e}")
            # Mark audit as failed
            try:
                site_audit.status = 'failed'
                site_audit.save(update_fields=['status'])
            except:
                pass
            return {
                "status": "error",
                "message": f"Failed to parse results: {str(e)}"
            }
            
    except Exception as e:
        logger.error(f"Site audit task error for id={site_audit_id}: {e}")
        
        # Mark audit as failed before retrying
        try:
            site_audit = SiteAudit.objects.get(id=site_audit_id)
            site_audit.status = 'failed'
            site_audit.save(update_fields=['status'])
        except:
            pass
            
        # Retry if we haven't exceeded max retries
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying site audit task, attempt {self.request.retries + 1}")
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        return {
            "status": "error",
            "message": f"Task failed: {str(e)}"
        }
        
    finally:
        # Always release the lock
        cache.delete(lock_key)


@shared_task(
    bind=True,
    max_retries=2,
    time_limit=600,  # 10 minutes for manual trigger
    soft_time_limit=540,  # 9 minutes soft limit
)
def trigger_manual_site_audit(self, project_id: int) -> dict:
    """
    Trigger a manual site audit for a project.
    
    This task checks if a manual audit is allowed (respecting frequency limits)
    and then enqueues the actual audit task.
    
    Args:
        project_id: ID of the Project to audit
        
    Returns:
        dict: Status of the trigger operation
    """
    from project.models import Project
    
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        logger.error(f"Project with id={project_id} not found")
        return {"status": "error", "message": "Project not found"}
    
    # Get or create site audit
    site_audit, created = SiteAudit.objects.get_or_create(
        project=project,
        defaults={
            'audit_frequency_days': 30,
            'manual_audit_frequency_days': 3,
            'max_pages_to_crawl': 5000
        }
    )
    
    # Check if manual audit is allowed
    if site_audit.last_manual_audit:
        days_since_last = (timezone.now() - site_audit.last_manual_audit).days
        if days_since_last < site_audit.manual_audit_frequency_days:
            logger.warning(
                f"Manual audit not allowed for {project.domain}. "
                f"Last audit was {days_since_last} days ago, "
                f"minimum is {site_audit.manual_audit_frequency_days} days"
            )
            return {
                "status": "rate_limited",
                "message": f"Please wait {site_audit.manual_audit_frequency_days - days_since_last} more days",
                "days_remaining": site_audit.manual_audit_frequency_days - days_since_last
            }
    
    # Update last manual audit time
    site_audit.last_manual_audit = timezone.now()
    site_audit.save(update_fields=['last_manual_audit'])
    
    # Enqueue the actual audit task
    task = run_site_audit.apply_async(
        args=[site_audit.id],
        queue='audit_scheduled',  # Match the configured queue routing
        priority=5
    )
    
    logger.info(f"Manual site audit triggered for {project.domain}, task_id={task.id}")
    
    return {
        "status": "triggered",
        "task_id": task.id,
        "site_audit_id": site_audit.id,
        "message": f"Site audit started for {project.domain}"
    }


@shared_task
def enqueue_scheduled_site_audits():
    """
    Celery Beat task to enqueue scheduled site audits.
    Runs daily and enqueues audits that are due.
    
    This task itself is quick, just identifies and enqueues the actual audit tasks.
    """
    now = timezone.now()
    
    # Find site audits that are due for automatic audit
    due_audits = SiteAudit.objects.filter(
        is_audit_enabled=True,
        next_scheduled_audit__lte=now
    ).select_related('project')[:10]  # Process max 10 per run to avoid overload
    
    if not due_audits:
        logger.info("No site audits are due")
        return {"total": 0}
    
    enqueued_count = 0
    
    for site_audit in due_audits:
        # Check if project is active
        if not site_audit.project.active:
            logger.info(f"Skipping audit for inactive project: {site_audit.project.domain}")
            continue
        
        # Update next scheduled audit immediately to prevent duplicate enqueuing
        site_audit.next_scheduled_audit = now + timedelta(days=site_audit.audit_frequency_days)
        site_audit.save(update_fields=['next_scheduled_audit'])
        
        # Enqueue the audit task
        task = run_site_audit.apply_async(
            args=[site_audit.id],
            queue='audit_scheduled',
            priority=3  # Lower priority than manual audits
        )
        
        logger.info(
            f"Scheduled site audit enqueued for {site_audit.project.domain}, "
            f"task_id={task.id}"
        )
        enqueued_count += 1
    
    logger.info(f"Enqueued {enqueued_count} scheduled site audits")
    
    return {
        "total": enqueued_count,
        "projects": [audit.project.domain for audit in due_audits[:enqueued_count]]
    }


@shared_task(
    time_limit=300,  # 5 minutes for cleanup
    soft_time_limit=240
)
def cleanup_old_site_audits(days_to_keep=90):
    """
    Clean up old completed site audits to prevent database bloat.
    Keep only the most recent audit for each project.
    
    Args:
        days_to_keep: Number of days of completed audits to keep
        
    Returns:
        dict: Cleanup statistics
    """
    from project.models import Project
    
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    deleted_count = 0
    
    # For each project, keep only the most recent audit and delete older ones
    for project in Project.objects.all():
        old_audits = SiteAudit.objects.filter(
            project=project,
            status='completed',
            last_audit_date__lt=cutoff_date
        ).exclude(
            # Keep the most recent audit for each project
            id__in=SiteAudit.objects.filter(
                project=project
            ).order_by('-last_audit_date').values_list('id', flat=True)[:1]
        )
        
        count_for_project = old_audits.count()
        old_audits.delete()
        deleted_count += count_for_project
    
    logger.info(f"Deleted {deleted_count} old site audits older than {days_to_keep} days")
    
    return {
        "deleted_count": deleted_count,
        "cutoff_date": cutoff_date.isoformat()
    }