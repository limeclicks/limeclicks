from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from django.core.files.base import ContentFile
from django.db import transaction
from datetime import timedelta
import json
import os
from typing import Optional

from .models import SiteAudit, OnPagePerformanceHistory, SiteIssue, ScreamingFrogLicense
from .screaming_frog import ScreamingFrogCLI, ScreamingFrogService

logger = get_task_logger(__name__)


@shared_task(
    bind=True, 
    max_retries=5,  # Increased to 5 retries like performance audit
    default_retry_delay=180,  # 3 minutes default delay
    rate_limit='30/h',  # 30 audits per hour globally for stability
    time_limit=1800,  # 30 minute timeout for crawling
    soft_time_limit=1680  # 28 minute soft timeout
)
def run_site_audit(self, performance_history_id: str):
    """
    Run a comprehensive on-page SEO audit using Screaming Frog
    
    Args:
        performance_history_id: UUID of the OnPagePerformanceHistory record
    """
    try:
        performance_history = OnPagePerformanceHistory.objects.get(id=performance_history_id)
        audit = performance_history.audit
        project = audit.project
        
        # Update status to running
        performance_history.status = 'running'
        performance_history.started_at = timezone.now()
        performance_history.save(update_fields=['status', 'started_at'])
        
        logger.info(f"Starting on-page audit for {project.domain} (attempt {self.request.retries + 1}/{self.max_retries + 1})")
        
        # Check license status - but use audit's configured limit regardless
        license_obj = ScreamingFrogLicense.objects.first()
        if not license_obj or license_obj.is_expired():
            logger.warning("Screaming Frog license expired or not found - using free tier limit")
            # Use the audit's configured limit (max 5000 for our needs)
            max_pages = min(audit.max_pages_to_crawl, 5000)
            logger.info(f"Using limit: {max_pages} pages")
        else:
            # With license, still respect audit's configured limit
            max_pages = min(audit.max_pages_to_crawl, license_obj.max_urls or audit.max_pages_to_crawl, 5000)
            logger.info(f"License found. Using limit: {max_pages} pages")
        
        # Initialize Screaming Frog CLI
        sf_cli = ScreamingFrogCLI()
        
        # Check if Screaming Frog is installed
        if not sf_cli.is_installed():
            error_msg = (
                "Screaming Frog SEO Spider is not installed or not accessible. "
                "Please ensure it's installed and available in the system PATH. "
                "Installation guide: https://www.screamingfrog.co.uk/seo-spider/installation/"
            )
            logger.error(error_msg)
            # Don't retry if not installed
            performance_history.status = 'failed'
            performance_history.error_message = error_msg
            performance_history.completed_at = timezone.now()
            performance_history.save(update_fields=['status', 'error_message', 'completed_at'])
            return {'success': False, 'error': error_msg}
        
        # Prepare URL with better validation
        url = project.domain.strip()
        
        # Remove any trailing slashes
        url = url.rstrip('/')
        
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            # Try HTTPS first
            url = f'https://{url}'
            logger.info(f"Added HTTPS protocol to URL: {url}")
        
        # Configure crawl with more robust settings
        config = {
            'follow_redirects': True,
            'crawl_subdomains': False,
            'check_spelling': False,  # Disable spelling check to reduce failures
            'crawl_depth': performance_history.crawl_depth or 10  # Default depth of 10
        }
        
        logger.info(f"Running crawl for {url} with max_pages={max_pages}")
        
        # Run crawl with retries
        success, output_dir, error = sf_cli.crawl_website(url, max_pages, config)
        
        if not success:
            # Log detailed error
            logger.error(f"Screaming Frog crawl failed for {url}: {error}")
            
            # Check if it's a connection error and retry with HTTP
            if 'connection' in str(error).lower() and url.startswith('https://'):
                http_url = url.replace('https://', 'http://')
                logger.info(f"Retrying with HTTP: {http_url}")
                success, output_dir, error = sf_cli.crawl_website(http_url, max_pages, config)
            
            # If still failing, record the error and fail properly
            if not success:
                error_msg = f"Screaming Frog crawl failed: {error}"
                logger.error(error_msg)
                
                # Update the performance history with error details
                performance_history.error_message = error_msg
                performance_history.save(update_fields=['error_message'])
                
                # Raise exception to trigger retry logic
                raise Exception(error_msg)
        
        # Parse Screaming Frog results
        results = sf_cli.parse_crawl_results(output_dir)
        results['crawler_used'] = 'screaming_frog'
        
        # Save summary data
        performance_history.summary_data = results['summary']
        performance_history.pages_crawled = results['pages_crawled']
        performance_history.issues_summary = {
            'broken_links': results['summary'].get('broken_links', 0),
            'redirect_chains': results['summary'].get('redirect_chains', 0),
            'missing_titles': results['summary'].get('missing_titles', 0),
            'duplicate_titles': results['summary'].get('duplicate_titles', 0),
            'missing_meta_descriptions': results['summary'].get('missing_meta_descriptions', 0),
            'duplicate_meta_descriptions': results['summary'].get('duplicate_meta_descriptions', 0),
            'blocked_by_robots': results['summary'].get('blocked_by_robots', 0),
            'missing_hreflang': results['summary'].get('missing_hreflang', 0),
            'total_issues': results['summary'].get('total_issues', 0)
        }
        
        # Compare with previous audit
        comparison = performance_history.compare_with_previous()
        if comparison:
            performance_history.issues_fixed = len(comparison['fixed_issues'])
            performance_history.issues_introduced = len(comparison['new_issues'])
        
        performance_history.total_issues = results['summary']['total_issues']
        
        # Save detailed reports to R2 with proper directory structure
        # Format: project.domain/site_audit/date/report.json
        
        # Create the path structure
        domain = project.domain.replace('https://', '').replace('http://', '').replace('/', '_')
        date_str = timezone.now().strftime('%Y%m%d_%H%M%S')
        
        # Full JSON report - Path: domain/site_audit/date/full_report.json
        full_report = json.dumps(results, indent=2)
        filename = f"{domain}/site_audit/{date_str}/full_report.json"
        performance_history.full_report_json.save(
            filename,
            ContentFile(full_report.encode('utf-8')),
            save=False
        )
        
        # Issues report - Path: domain/site_audit/date/issues_report.json
        issues_report = json.dumps(results['details'], indent=2)
        filename = f"{domain}/site_audit/{date_str}/issues_report.json"
        performance_history.issues_report_json.save(
            filename,
            ContentFile(issues_report.encode('utf-8')),
            save=False
        )
        
        # Save individual issues to database (for quick filtering)
        _save_individual_issues(performance_history, results['details'])
        
        # Update status
        performance_history.status = 'completed'
        performance_history.completed_at = timezone.now()
        performance_history.save()
        
        # Update main audit model with latest results
        audit.update_from_audit_results(performance_history)
        
        # Schedule next audit if this was scheduled
        if performance_history.trigger_type == 'scheduled':
            audit.schedule_next_audit()
        
        # Cleanup temporary files if using Screaming Frog
        if results.get('crawler_used') == 'screaming_frog':
            try:
                sf_cli.cleanup()
            except Exception as e:
                logger.warning(f"Error cleaning up temporary files: {e}")
        
        logger.info(f"Successfully completed on-page audit for {project.domain} using {results.get('crawler_used', 'unknown')} crawler")
        
        return {
            'success': True,
            'audit_id': str(performance_history.id),
            'pages_crawled': results['pages_crawled'],
            'total_issues': results['summary']['total_issues']
        }
        
    except OnPagePerformanceHistory.DoesNotExist:
        logger.error(f"OnPagePerformanceHistory {performance_history_id} not found")
        return {'success': False, 'error': 'Audit history not found'}
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error running on-page audit: {error_msg}")
        
        # Update audit history with error
        try:
            performance_history = OnPagePerformanceHistory.objects.get(id=performance_history_id)
            performance_history.retry_count = self.request.retries
            
            # If we're going to retry, keep status as running
            if self.request.retries < self.max_retries:
                performance_history.error_message = f"Attempt {self.request.retries + 1} failed: {error_msg}"
                performance_history.save(update_fields=['retry_count', 'error_message'])
            else:
                # Final failure
                performance_history.status = 'failed'
                performance_history.error_message = f"Final failure after {self.max_retries + 1} attempts: {error_msg}"
                performance_history.completed_at = timezone.now()
                performance_history.save(update_fields=['status', 'error_message', 'retry_count', 'completed_at'])
        except Exception as save_error:
            logger.error(f"Failed to update performance history: {save_error}")
        
        # Retry with progressive backoff if we haven't exceeded max retries
        if self.request.retries < self.max_retries:
            # Progressive backoff: 3, 6, 9, 12, 15 minutes
            retry_delay = 180 * (self.request.retries + 1)
            logger.info(f"Retrying audit (attempt {self.request.retries + 2}/{self.max_retries + 1}) in {retry_delay} seconds")
            raise self.retry(exc=e, countdown=retry_delay)
        
        logger.error(f"Site audit failed after {self.max_retries + 1} attempts")
        return {'success': False, 'error': error_msg}


def _save_individual_issues(performance_history, details):
    """Save individual issues to database"""
    
    # Broken links
    for item in details.get('broken_links', []):
        SiteIssue.objects.create(
            performance_history=performance_history,
            issue_type='broken_link',
            severity='high' if item['status_code'] >= 500 else 'medium',
            page_url=item['url'],
            description=f"Broken link with status {item['status_code']}",
            recommendation="Fix or remove this broken link",
            status_code=item['status_code'],
            source_url=item.get('source'),
            anchor_text=item.get('anchor_text')
        )
    
    # Missing titles
    for item in details.get('missing_titles', []):
        SiteIssue.objects.create(
            performance_history=performance_history,
            issue_type='missing_title',
            severity='high',
            page_url=item['url'],
            description="Page is missing a title tag",
            recommendation="Add a unique, descriptive title tag (50-60 characters)"
        )
    
    # Duplicate titles
    for item in details.get('duplicate_titles', []):
        for url in item['urls']:
            SiteIssue.objects.create(
                performance_history=performance_history,
                issue_type='duplicate_title',
                severity='medium',
                page_url=url,
                page_title=item['title'],
                description=f"Duplicate title found on {len(item['urls'])} pages",
                recommendation="Make each page title unique and descriptive",
                duplicate_urls=item['urls']
            )
    
    # Missing meta descriptions
    for item in details.get('missing_meta_descriptions', []):
        SiteIssue.objects.create(
            performance_history=performance_history,
            issue_type='missing_meta_description',
            severity='medium',
            page_url=item['url'],
            description="Page is missing a meta description",
            recommendation="Add a compelling meta description (150-160 characters)"
        )
    
    # Duplicate meta descriptions
    for item in details.get('duplicate_meta_descriptions', []):
        for url in item['urls']:
            SiteIssue.objects.create(
                performance_history=performance_history,
                issue_type='duplicate_meta_description',
                severity='low',
                page_url=url,
                description=f"Duplicate meta description found on {len(item['urls'])} pages",
                recommendation="Write unique meta descriptions for each page",
                duplicate_urls=item['urls']
            )
    
    # Blocked by robots
    for item in details.get('blocked_by_robots', []):
        SiteIssue.objects.create(
            performance_history=performance_history,
            issue_type='blocked_by_robots',
            severity='high' if 'noindex' in item['directive'] else 'medium',
            page_url=item['url'],
            description=f"Page blocked by robots directive: {item['directive']}",
            recommendation="Review if this page should be blocked from search engines"
        )


@shared_task
def create_site_audit_for_project(project_id: int, trigger_type: str = 'project_created'):
    """
    Create and run an on-page audit when a new project is added
    
    Args:
        project_id: ID of the project
        trigger_type: Type of trigger for the audit
    """
    from project.models import Project
    
    try:
        project = Project.objects.get(id=project_id)
        
        # Create or get the on-page audit with default page limit
        # Default to 5000 as requested for fastgenerations.co.uk
        audit, created = SiteAudit.objects.get_or_create(
            project=project,
            defaults={
                'max_pages_to_crawl': 5000  # Default limit of 5000 pages
            }
        )
        
        if created:
            logger.info(f"Created new on-page audit for project {project.domain}")
        
        # Check if we can run an automatic audit
        if not audit.can_run_automatic_audit():
            logger.info(f"Skipping automatic audit for {project.domain} - rate limited")
            return {'success': False, 'error': 'Rate limited'}
        
        # Create audit history entry
        performance_history = OnPagePerformanceHistory.objects.create(
            audit=audit,
            trigger_type=trigger_type,
            status='pending'
        )
        
        # Update rate limiting
        audit.last_automatic_audit = timezone.now()
        audit.save(update_fields=['last_automatic_audit'])
        
        # Queue the audit
        run_site_audit.delay(str(performance_history.id))
        
        logger.info(f"Queued on-page audit for project {project.domain}")
        
        return {'success': True, 'project_id': project_id, 'audit_id': str(performance_history.id)}
        
    except Project.DoesNotExist:
        logger.error(f"Project {project_id} not found")
        return {'success': False, 'error': 'Project not found'}
    except Exception as e:
        logger.error(f"Error creating on-page audit for project: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def run_manual_site_audit(audit_id: int, user_id: Optional[int] = None):
    """
    Run a manual on-page audit with rate limiting (3 days)
    
    Args:
        audit_id: ID of the SiteAudit
        user_id: Optional user ID who triggered the audit
    """
    try:
        audit = SiteAudit.objects.get(id=audit_id)
        
        # Check rate limiting (3 days)
        if not audit.can_run_manual_audit():
            time_until_next = (audit.last_manual_audit + timedelta(days=3)) - timezone.now()
            days_remaining = time_until_next.days
            hours_remaining = time_until_next.seconds // 3600
            return {
                'success': False,
                'error': f'Rate limited. Please wait {days_remaining} days and {hours_remaining} hours before running another manual audit.'
            }
        
        # Update last manual audit time
        audit.last_manual_audit = timezone.now()
        audit.save(update_fields=['last_manual_audit'])
        
        # Create audit history entry
        performance_history = OnPagePerformanceHistory.objects.create(
            audit=audit,
            trigger_type='manual',
            status='pending'
        )
        
        # Queue the audit
        run_site_audit.delay(str(performance_history.id))
        
        logger.info(f"Manual on-page audit triggered for {audit.project.domain}")
        
        return {
            'success': True,
            'audit_id': str(performance_history.id),
            'message': 'Manual on-page audit started'
        }
        
    except SiteAudit.DoesNotExist:
        return {'success': False, 'error': 'Audit not found'}
    except Exception as e:
        logger.error(f"Error running manual on-page audit: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def check_scheduled_site_audits():
    """
    Check for on-page audits that need to be run (30-day schedule)
    This should be run periodically (e.g., daily)
    """
    now = timezone.now()
    
    # Find audits that need to run
    audits = SiteAudit.objects.filter(
        is_audit_enabled=True,
        next_scheduled_audit__lte=now
    )
    
    scheduled_count = 0
    
    for audit in performance_audit:
        try:
            # Check if we can run (30-day limit)
            if not audit.can_run_automatic_audit():
                logger.info(f"Skipping scheduled audit for {audit.project.domain} - rate limited")
                continue
            
            with transaction.atomic():
                # Create audit history entry
                performance_history = OnPagePerformanceHistory.objects.create(
                    audit=audit,
                    trigger_type='scheduled',
                    status='pending'
                )
                
                # Update rate limiting
                audit.last_automatic_audit = now
                audit.save(update_fields=['last_automatic_audit'])
                
                # Queue the audit
                run_site_audit.delay(str(performance_history.id))
                
                # Schedule next audit
                audit.schedule_next_audit()
                
                scheduled_count += 1
                logger.info(f"Scheduled on-page audit for {audit.project.domain}")
                
        except Exception as e:
            logger.error(f"Error scheduling on-page audit for {audit.project.domain}: {str(e)}")
            continue
    
    logger.info(f"Scheduled {scheduled_count} on-page audits")
    
    return {
        'success': True,
        'scheduled_count': scheduled_count,
        'checked_at': now.isoformat()
    }


@shared_task
def validate_screaming_frog_license():
    """
    Validate Screaming Frog license periodically (weekly)
    Updates license status in database
    """
    try:
        license_obj, license_info = ScreamingFrogService.validate_and_save_license()
        
        logger.info(f"License validation complete: {license_info['message']}")
        
        return {
            'success': True,
            'valid': license_info['valid'],
            'type': license_info['type'],
            'expiry_date': str(license_obj.expiry_date) if license_obj.expiry_date else None,
            'days_until_expiry': license_obj.days_until_expiry()
        }
        
    except Exception as e:
        logger.error(f"Error validating license: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def check_license_expiry_reminder():
    """
    Check license expiry and send reminder emails if needed
    This runs daily to check if reminders should be sent
    """
    from django.core.management import call_command
    
    try:
        # Call the management command
        call_command('check_license_expiry')
        
        logger.info("License expiry check completed")
        
        return {
            'success': True,
            'checked_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error checking license expiry: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def cleanup_old_site_audits(days_to_keep: int = 90):
    """
    Clean up old on-page audit history records
    
    Args:
        days_to_keep: Number of days of history to keep
    """
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    
    # Get audits to delete
    old_audits = OnPagePerformanceHistory.objects.filter(
        created_at__lt=cutoff_date
    )
    
    deleted_count = 0
    
    for audit in old_performance_audit:
        try:
            # Delete associated files from R2
            if audit.full_report_json:
                audit.full_report_json.delete()
            if audit.crawl_report_csv:
                audit.crawl_report_csv.delete()
            if audit.issues_report_json:
                audit.issues_report_json.delete()
            
            # Delete associated issues
            audit.issues.all().delete()
            
            # Delete the audit record
            audit.delete()
            deleted_count += 1
            
        except Exception as e:
            logger.error(f"Error deleting on-page audit {audit.id}: {str(e)}")
            continue
    
    logger.info(f"Deleted {deleted_count} old on-page audit records")
    
    return {
        'success': True,
        'deleted_count': deleted_count,
        'cutoff_date': cutoff_date.isoformat()
    }