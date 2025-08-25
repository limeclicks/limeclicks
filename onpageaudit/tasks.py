from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from django.core.files.base import ContentFile
from django.db import transaction
from datetime import timedelta
import json
import os
from typing import Optional

from .models import OnPageAudit, OnPageAuditHistory, OnPageIssue, ScreamingFrogLicense
from .screaming_frog import ScreamingFrogCLI, ScreamingFrogService

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def run_onpage_audit(self, audit_history_id: str):
    """
    Run a comprehensive on-page SEO audit using Screaming Frog
    
    Args:
        audit_history_id: UUID of the OnPageAuditHistory record
    """
    try:
        audit_history = OnPageAuditHistory.objects.get(id=audit_history_id)
        audit = audit_history.audit
        project = audit.project
        
        # Update status to running
        audit_history.status = 'running'
        audit_history.started_at = timezone.now()
        audit_history.save(update_fields=['status', 'started_at'])
        
        logger.info(f"Starting on-page audit for {project.domain}")
        
        # Check license status
        license_obj = ScreamingFrogLicense.objects.first()
        if not license_obj or license_obj.is_expired():
            logger.warning("Screaming Frog license expired or not found, using free version")
            max_pages = 500
        else:
            max_pages = min(audit.max_pages_to_crawl, license_obj.max_urls or 500)
        
        # Initialize Screaming Frog CLI
        sf_cli = ScreamingFrogCLI()
        
        # Prepare URL
        url = project.domain
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        
        # Configure crawl
        config = {
            'follow_redirects': True,
            'crawl_subdomains': False,
            'check_spelling': True,
            'crawl_depth': audit_history.crawl_depth
        }
        
        # Run crawl
        success, output_dir, error = sf_cli.crawl_website(url, max_pages, config)
        
        if not success:
            raise Exception(error or "Crawl failed with unknown error")
        
        # Parse results
        results = sf_cli.parse_crawl_results(output_dir)
        
        # Save summary data
        audit_history.summary_data = results['summary']
        audit_history.pages_crawled = results['pages_crawled']
        audit_history.issues_summary = {
            'broken_links': results['summary']['broken_links'],
            'redirect_chains': results['summary']['redirect_chains'],
            'missing_titles': results['summary']['missing_titles'],
            'duplicate_titles': results['summary']['duplicate_titles'],
            'missing_meta_descriptions': results['summary']['missing_meta_descriptions'],
            'duplicate_meta_descriptions': results['summary']['duplicate_meta_descriptions'],
            'blocked_by_robots': results['summary']['blocked_by_robots'],
            'missing_hreflang': results['summary']['missing_hreflang'],
            'total_issues': results['summary']['total_issues']
        }
        
        # Compare with previous audit
        comparison = audit_history.compare_with_previous()
        if comparison:
            audit_history.issues_fixed = len(comparison['fixed_issues'])
            audit_history.issues_introduced = len(comparison['new_issues'])
        
        audit_history.total_issues = results['summary']['total_issues']
        
        # Save detailed reports to R2 with proper directory structure
        # Format: project.domain/onpageaudit/date/report.json
        
        # Create the path structure
        domain = project.domain.replace('https://', '').replace('http://', '').replace('/', '_')
        date_str = timezone.now().strftime('%Y%m%d_%H%M%S')
        
        # Full JSON report - Path: domain/onpageaudit/date/full_report.json
        full_report = json.dumps(results, indent=2)
        filename = f"{domain}/onpageaudit/{date_str}/full_report.json"
        audit_history.full_report_json.save(
            filename,
            ContentFile(full_report.encode('utf-8')),
            save=False
        )
        
        # Issues report - Path: domain/onpageaudit/date/issues_report.json
        issues_report = json.dumps(results['details'], indent=2)
        filename = f"{domain}/onpageaudit/{date_str}/issues_report.json"
        audit_history.issues_report_json.save(
            filename,
            ContentFile(issues_report.encode('utf-8')),
            save=False
        )
        
        # Save individual issues to database (for quick filtering)
        _save_individual_issues(audit_history, results['details'])
        
        # Update status
        audit_history.status = 'completed'
        audit_history.completed_at = timezone.now()
        audit_history.save()
        
        # Update main audit model with latest results
        audit.update_from_audit_results(audit_history)
        
        # Schedule next audit if this was scheduled
        if audit_history.trigger_type == 'scheduled':
            audit.schedule_next_audit()
        
        # Cleanup temporary files
        sf_cli.cleanup()
        
        logger.info(f"Successfully completed on-page audit for {project.domain}")
        
        return {
            'success': True,
            'audit_id': str(audit_history.id),
            'pages_crawled': results['pages_crawled'],
            'total_issues': results['summary']['total_issues']
        }
        
    except OnPageAuditHistory.DoesNotExist:
        logger.error(f"OnPageAuditHistory {audit_history_id} not found")
        return {'success': False, 'error': 'Audit history not found'}
        
    except Exception as e:
        logger.error(f"Error running on-page audit: {str(e)}")
        
        # Update audit history with error
        try:
            audit_history = OnPageAuditHistory.objects.get(id=audit_history_id)
            audit_history.status = 'failed'
            audit_history.error_message = str(e)
            audit_history.retry_count += 1
            audit_history.save()
        except:
            pass
        
        # Retry if we haven't exceeded max retries
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying audit (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=300 * (self.request.retries + 1))
        
        return {'success': False, 'error': str(e)}


def _save_individual_issues(audit_history, details):
    """Save individual issues to database"""
    
    # Broken links
    for item in details.get('broken_links', []):
        OnPageIssue.objects.create(
            audit_history=audit_history,
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
        OnPageIssue.objects.create(
            audit_history=audit_history,
            issue_type='missing_title',
            severity='high',
            page_url=item['url'],
            description="Page is missing a title tag",
            recommendation="Add a unique, descriptive title tag (50-60 characters)"
        )
    
    # Duplicate titles
    for item in details.get('duplicate_titles', []):
        for url in item['urls']:
            OnPageIssue.objects.create(
                audit_history=audit_history,
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
        OnPageIssue.objects.create(
            audit_history=audit_history,
            issue_type='missing_meta_description',
            severity='medium',
            page_url=item['url'],
            description="Page is missing a meta description",
            recommendation="Add a compelling meta description (150-160 characters)"
        )
    
    # Duplicate meta descriptions
    for item in details.get('duplicate_meta_descriptions', []):
        for url in item['urls']:
            OnPageIssue.objects.create(
                audit_history=audit_history,
                issue_type='duplicate_meta_description',
                severity='low',
                page_url=url,
                description=f"Duplicate meta description found on {len(item['urls'])} pages",
                recommendation="Write unique meta descriptions for each page",
                duplicate_urls=item['urls']
            )
    
    # Blocked by robots
    for item in details.get('blocked_by_robots', []):
        OnPageIssue.objects.create(
            audit_history=audit_history,
            issue_type='blocked_by_robots',
            severity='high' if 'noindex' in item['directive'] else 'medium',
            page_url=item['url'],
            description=f"Page blocked by robots directive: {item['directive']}",
            recommendation="Review if this page should be blocked from search engines"
        )


@shared_task
def create_onpage_audit_for_project(project_id: int, trigger_type: str = 'project_created'):
    """
    Create and run an on-page audit when a new project is added
    
    Args:
        project_id: ID of the project
        trigger_type: Type of trigger for the audit
    """
    from project.models import Project
    
    try:
        project = Project.objects.get(id=project_id)
        
        # Create or get the on-page audit with 10k page limit
        audit, created = OnPageAudit.objects.get_or_create(
            project=project,
            defaults={
                'max_pages_to_crawl': 10000  # Set to 10,000 pages for new projects
            }
        )
        
        if created:
            logger.info(f"Created new on-page audit for project {project.domain}")
        
        # Check if we can run an automatic audit
        if not audit.can_run_automatic_audit():
            logger.info(f"Skipping automatic audit for {project.domain} - rate limited")
            return {'success': False, 'error': 'Rate limited'}
        
        # Create audit history entry
        audit_history = OnPageAuditHistory.objects.create(
            audit=audit,
            trigger_type=trigger_type,
            status='pending'
        )
        
        # Update rate limiting
        audit.last_automatic_audit = timezone.now()
        audit.save(update_fields=['last_automatic_audit'])
        
        # Queue the audit
        run_onpage_audit.delay(str(audit_history.id))
        
        logger.info(f"Queued on-page audit for project {project.domain}")
        
        return {'success': True, 'project_id': project_id, 'audit_id': str(audit_history.id)}
        
    except Project.DoesNotExist:
        logger.error(f"Project {project_id} not found")
        return {'success': False, 'error': 'Project not found'}
    except Exception as e:
        logger.error(f"Error creating on-page audit for project: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def run_manual_onpage_audit(audit_id: int, user_id: Optional[int] = None):
    """
    Run a manual on-page audit with rate limiting (3 days)
    
    Args:
        audit_id: ID of the OnPageAudit
        user_id: Optional user ID who triggered the audit
    """
    try:
        audit = OnPageAudit.objects.get(id=audit_id)
        
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
        audit_history = OnPageAuditHistory.objects.create(
            audit=audit,
            trigger_type='manual',
            status='pending'
        )
        
        # Queue the audit
        run_onpage_audit.delay(str(audit_history.id))
        
        logger.info(f"Manual on-page audit triggered for {audit.project.domain}")
        
        return {
            'success': True,
            'audit_id': str(audit_history.id),
            'message': 'Manual on-page audit started'
        }
        
    except OnPageAudit.DoesNotExist:
        return {'success': False, 'error': 'Audit not found'}
    except Exception as e:
        logger.error(f"Error running manual on-page audit: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def check_scheduled_onpage_audits():
    """
    Check for on-page audits that need to be run (30-day schedule)
    This should be run periodically (e.g., daily)
    """
    now = timezone.now()
    
    # Find audits that need to run
    audits = OnPageAudit.objects.filter(
        is_audit_enabled=True,
        next_scheduled_audit__lte=now
    )
    
    scheduled_count = 0
    
    for audit in audits:
        try:
            # Check if we can run (30-day limit)
            if not audit.can_run_automatic_audit():
                logger.info(f"Skipping scheduled audit for {audit.project.domain} - rate limited")
                continue
            
            with transaction.atomic():
                # Create audit history entry
                audit_history = OnPageAuditHistory.objects.create(
                    audit=audit,
                    trigger_type='scheduled',
                    status='pending'
                )
                
                # Update rate limiting
                audit.last_automatic_audit = now
                audit.save(update_fields=['last_automatic_audit'])
                
                # Queue the audit
                run_onpage_audit.delay(str(audit_history.id))
                
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
def cleanup_old_onpage_audits(days_to_keep: int = 90):
    """
    Clean up old on-page audit history records
    
    Args:
        days_to_keep: Number of days of history to keep
    """
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    
    # Get audits to delete
    old_audits = OnPageAuditHistory.objects.filter(
        created_at__lt=cutoff_date
    )
    
    deleted_count = 0
    
    for audit in old_audits:
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