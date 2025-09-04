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
from .pagespeed_insights import collect_pagespeed_data

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
        success = False
        output_dir = None
        error_message = None

        site_audit.status = 'running'
        site_audit.save(update_fields=['status'])

        for attempt in range(3):
            try:
                success, output_dir, error_message = sf_cli.crawl_website(
                    url=f"https://{project.domain}"
                )
                
                if success:
                    # Find the timestamped subdirectory (e.g., 2025.08.29.14.34.06)
                    actual_output_dir = output_dir
                    if output_dir and Path(output_dir).exists():
                        subdirs = [d for d in Path(output_dir).iterdir() if d.is_dir()]
                        if subdirs:
                            # Get the first subdirectory (should be the timestamped one)
                            # Screaming Frog creates a timestamped folder like YYYY.MM.DD.HH.MM.SS
                            timestamped_dir = subdirs[0]
                            actual_output_dir = str(timestamped_dir)
                            logger.info(f"Found timestamped subdirectory: {timestamped_dir.name}")
                    
                    # Save the actual output directory path (including timestamped subdir) to the site audit
                    site_audit.temp_audit_dir = actual_output_dir
                    site_audit.save(update_fields=['temp_audit_dir'])
                    logger.info(f"Saved output directory path to site audit: {actual_output_dir}")
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
            site_audit.status = 'failed'
            site_audit.save(update_fields=['status'])
            return {
                "status": "error",
                "message": f"Crawl failed: {error_message}"
            }
        
        # Process results using new method
        try:
            # Print output directory path for debugging
            logger.error(f"🔍 DEBUG: Output directory path: {site_audit.temp_audit_dir}")
            print(f"🔍 DEBUG: Output directory path: {site_audit.temp_audit_dir}")
            
            # Hand over to new process_results method
            result = site_audit.process_results()
            
            # Upload CSV files to R2 after processing results
            try:
                from .r2_upload import AuditFileUploader
                uploader = AuditFileUploader(site_audit)
                
                # Upload all CSV files from the audit directory
                upload_results = uploader.upload_audit_files(site_audit.temp_audit_dir)
                
                if upload_results.get('file_count', 0) > 0:
                    logger.info(
                        f"Uploaded {upload_results['file_count']} CSV files to R2, "
                        f"total size: {upload_results['total_size'] / 1024 / 1024:.2f} MB"
                    )
                    result['r2_upload'] = {
                        'status': 'success',
                        'files_uploaded': upload_results['file_count'],
                        'total_size_mb': round(upload_results['total_size'] / 1024 / 1024, 2)
                    }
                else:
                    logger.warning("No CSV files uploaded to R2")
                    result['r2_upload'] = {
                        'status': 'no_files',
                        'message': 'No CSV files found to upload'
                    }
                    
                # Get summary of uploaded files
                files_summary = uploader.get_audit_files_summary()
                result['r2_files_summary'] = files_summary
                
            except Exception as e:
                logger.error(f"Failed to upload CSV files to R2: {e}")
                result['r2_upload'] = {
                    'status': 'error',
                    'message': str(e)
                }
            
            # PageSpeed Insights is now triggered separately in parallel
            # No longer triggered from within this task to enable simultaneous execution
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing results: {e}")
            try:
                site_audit.status = 'failed'
                site_audit.save(update_fields=['status'])
            except:
                pass
            return {
                "status": "error",
                "message": f"Failed to process results: {str(e)}"
            }
        finally:
            # Clean up temporary directory after successful processing
            if output_dir and Path(output_dir).exists():
                try:
                    logger.info(f"Cleaning up temporary audit directory: {output_dir}")
                    shutil.rmtree(output_dir)
                    logger.info(f"Successfully cleaned up {output_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up {output_dir}: {e}")
            
            # Clear the temp_audit_dir field after cleanup
            try:
                site_audit.temp_audit_dir = None
                site_audit.save(update_fields=['temp_audit_dir'])
            except:
                pass
            
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
    
    # Update last manual audit time and set status to pending
    site_audit.last_manual_audit = timezone.now()
    site_audit.status = 'pending'
    site_audit.save(update_fields=['last_manual_audit', 'status'])
    
    # Enqueue both audit tasks simultaneously
    site_audit_task = run_site_audit.apply_async(
        args=[site_audit.id],
        queue='audit_scheduled',  # Match the configured queue routing
        priority=5
    )
    
    psi_task = collect_pagespeed_insights.apply_async(
        args=[site_audit.id],
        queue='audit_scheduled',  # Same queue for simultaneous execution
        priority=5,  # Same priority for parallel execution
        countdown=2  # Small delay to ensure SiteAudit state is consistent
    )
    
    logger.info(f"Manual site audit triggered for {project.domain}, task_id={site_audit_task.id}")
    logger.info(f"Manual PageSpeed audit triggered for {project.domain}, task_id={psi_task.id}")
    
    return {
        "status": "triggered",
        "site_audit_task_id": site_audit_task.id,
        "psi_task_id": psi_task.id,
        "site_audit_id": site_audit.id,
        "message": f"Site audit and PageSpeed audit started for {project.domain}"
    }


# REMOVED: enqueue_scheduled_site_audits task
# Site audits are now only triggered:
# 1. Automatically when a project is first created (via signal)
# 2. Manually by users through the UI


@shared_task(
    time_limit=300,  # 5 minutes for cleanup
    soft_time_limit=240
)
def cleanup_old_site_audits(days_to_keep=90):
    """
    Clean up old completed site audits to prevent database bloat.
    Keep only the most recent audit for each project.
    Also cleans up associated R2 files.
    
    Args:
        days_to_keep: Number of days of completed audits to keep
        
    Returns:
        dict: Cleanup statistics
    """
    from project.models import Project
    from .models import AuditFile
    from .r2_upload import cleanup_old_r2_files
    
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    deleted_count = 0
    r2_files_deleted = 0
    
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
        
        # Delete associated R2 files before deleting audits
        for audit in old_audits:
            audit_files = AuditFile.objects.filter(site_audit=audit)
            r2_files_deleted += audit_files.count()
            # Files will be deleted via cascade when audit is deleted
        
        count_for_project = old_audits.count()
        old_audits.delete()
        deleted_count += count_for_project
    
    # Also run general R2 cleanup for orphaned files
    try:
        orphaned_files_deleted = cleanup_old_r2_files(days_to_keep)
        r2_files_deleted += orphaned_files_deleted
    except Exception as e:
        logger.warning(f"Failed to cleanup orphaned R2 files: {e}")
    
    logger.info(f"Deleted {deleted_count} old site audits and {r2_files_deleted} R2 files older than {days_to_keep} days")
    
    return {
        "deleted_count": deleted_count,
        "r2_files_deleted": r2_files_deleted,
        "cutoff_date": cutoff_date.isoformat()
    }


@shared_task(
    time_limit=600,  # 10 minutes for comprehensive cleanup
    soft_time_limit=540
)
def cleanup_screaming_frog_data(hours_old=24):
    """
    Clean up temporary Screaming Frog crawl data and application cache.
    
    This task:
    1. Removes orphaned temporary crawl directories in /tmp
    2. Cleans up old ProjectInstanceData in Screaming Frog home directory
    3. Clears any temporary audit directories referenced by completed audits
    
    Args:
        hours_old: Clean up data older than this many hours
        
    Returns:
        dict: Cleanup statistics
    """
    import os
    import glob
    from datetime import datetime
    
    cleanup_stats = {
        "temp_dirs_removed": 0,
        "temp_dirs_size_freed": 0,
        "sf_instances_removed": 0,
        "sf_instances_size_freed": 0,
        "errors": []
    }
    
    cutoff_time = timezone.now() - timedelta(hours=hours_old)
    
    # 1. Clean up orphaned /tmp/sf_crawl_* directories
    logger.info(f"Cleaning up temporary crawl directories older than {hours_old} hours")
    
    temp_dirs = glob.glob('/tmp/sf_crawl_*')
    for temp_dir in temp_dirs:
        try:
            # Check directory age
            dir_path = Path(temp_dir)
            if not dir_path.exists():
                continue
                
            # Get directory modification time
            mtime = datetime.fromtimestamp(dir_path.stat().st_mtime, tz=timezone.utc)
            
            if mtime < cutoff_time:
                # Calculate size before deletion
                dir_size = sum(f.stat().st_size for f in dir_path.rglob('*') if f.is_file())
                cleanup_stats["temp_dirs_size_freed"] += dir_size
                
                # Remove directory
                shutil.rmtree(temp_dir)
                cleanup_stats["temp_dirs_removed"] += 1
                logger.info(f"Removed old temporary directory: {temp_dir} (freed {dir_size/1024/1024:.2f} MB)")
                
        except Exception as e:
            error_msg = f"Failed to clean up {temp_dir}: {e}"
            logger.warning(error_msg)
            cleanup_stats["errors"].append(error_msg)
    
    # 2. Clean up Screaming Frog ProjectInstanceData
    sf_home = Path.home() / '.ScreamingFrogSEOSpider'
    project_data_dir = sf_home / 'ProjectInstanceData'
    
    if project_data_dir.exists():
        logger.info("Cleaning up Screaming Frog ProjectInstanceData")
        
        for instance_dir in project_data_dir.iterdir():
            if not instance_dir.is_dir():
                continue
                
            try:
                # Check directory age
                mtime = datetime.fromtimestamp(instance_dir.stat().st_mtime, tz=timezone.utc)
                
                if mtime < cutoff_time:
                    # Calculate size before deletion
                    dir_size = sum(f.stat().st_size for f in instance_dir.rglob('*') if f.is_file())
                    cleanup_stats["sf_instances_size_freed"] += dir_size
                    
                    # Remove directory
                    shutil.rmtree(instance_dir)
                    cleanup_stats["sf_instances_removed"] += 1
                    logger.info(f"Removed old SF instance: {instance_dir.name} (freed {dir_size/1024/1024:.2f} MB)")
                    
            except Exception as e:
                error_msg = f"Failed to clean up SF instance {instance_dir}: {e}"
                logger.warning(error_msg)
                cleanup_stats["errors"].append(error_msg)
    
    # 3. Clean up any temp directories still referenced by completed audits
    completed_audits = SiteAudit.objects.filter(
        status='completed',
        temp_audit_dir__isnull=False
    ).exclude(temp_audit_dir='')
    
    for audit in completed_audits:
        if audit.temp_audit_dir and Path(audit.temp_audit_dir).exists():
            try:
                # Get the parent directory (the actual temp dir)
                temp_dir = Path(audit.temp_audit_dir).parent
                if temp_dir.exists() and str(temp_dir).startswith('/tmp/sf_crawl_'):
                    shutil.rmtree(temp_dir)
                    logger.info(f"Cleaned up audit temp directory: {temp_dir}")
                    cleanup_stats["temp_dirs_removed"] += 1
            except Exception as e:
                logger.warning(f"Failed to clean up audit temp dir {audit.temp_audit_dir}: {e}")
        
        # Clear the reference
        audit.temp_audit_dir = None
        audit.save(update_fields=['temp_audit_dir'])
    
    # Log summary
    logger.info(
        f"Cleanup complete: Removed {cleanup_stats['temp_dirs_removed']} temp dirs "
        f"({cleanup_stats['temp_dirs_size_freed']/1024/1024:.2f} MB), "
        f"{cleanup_stats['sf_instances_removed']} SF instances "
        f"({cleanup_stats['sf_instances_size_freed']/1024/1024:.2f} MB)"
    )
    
    return cleanup_stats


@shared_task(
    bind=True,
    max_retries=3,
    time_limit=720,  # 12 minutes for PageSpeed Insights (5 mins per strategy + buffer)
    soft_time_limit=600  # 10 minutes soft limit
)
def collect_pagespeed_insights(self, site_audit_id: int) -> dict:
    """
    Collect PageSpeed Insights data for a site audit.
    
    This task runs alongside the main site audit to gather performance data
    from Google PageSpeed Insights API for both mobile and desktop.
    
    Args:
        site_audit_id: ID of the SiteAudit instance
        
    Returns:
        dict: Results of the PageSpeed Insights collection
    """
    import json
    import io
    from datetime import datetime
    from limeclicks.storage_backends import CloudflareR2Storage
    
    try:
        # Fetch site audit with retry logic for simultaneous execution
        try:
            site_audit = SiteAudit.objects.get(id=site_audit_id)
        except SiteAudit.DoesNotExist:
            # When running simultaneously, the SiteAudit might not be ready yet
            # Retry up to 3 times with increasing delays
            if self.request.retries < 3:
                logger.info(f"SiteAudit with id={site_audit_id} not ready yet, retrying in {10 * (self.request.retries + 1)} seconds")
                raise self.retry(countdown=10 * (self.request.retries + 1), max_retries=3)
            logger.error(f"SiteAudit with id={site_audit_id} not found after retries")
            return {"status": "error", "message": "SiteAudit not found"}
        
        project = site_audit.project
        url = f"https://{project.domain}"
        
        logger.info(f"Collecting PageSpeed Insights data for {url}")
        
        # Collect PageSpeed data for both mobile and desktop (with raw responses)
        psi_data_with_raw = collect_pagespeed_data(url, return_raw=True)
        psi_data = psi_data_with_raw['parsed'] if psi_data_with_raw else {}
        raw_responses = psi_data_with_raw.get('raw', {}) if psi_data_with_raw else {}
        
        if not psi_data:
            logger.warning(f"No PageSpeed Insights data collected for {url}")
            return {"status": "no_data", "message": "No PageSpeed data available"}
        
        # Save raw API responses to R2 if we have data
        if raw_responses:
            try:
                storage = CloudflareR2Storage()
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                
                # Save mobile response if available
                if raw_responses.get('mobile'):
                    try:
                        mobile_file_name = f"pagespeed_insights/{project.domain}/mobile_psi_{timestamp}.json"
                        mobile_response = {
                            'url': url,
                            'strategy': 'mobile',
                            'timestamp': timestamp,
                            'data': raw_responses['mobile']
                        }
                        mobile_json = json.dumps(mobile_response, indent=2)
                        mobile_file = io.BytesIO(mobile_json.encode('utf-8'))
                        
                        mobile_path = storage.save(mobile_file_name, mobile_file)
                        site_audit.pagespeed_mobile_response_r2_path = mobile_path
                        logger.info(f"Saved mobile PageSpeed Insights raw response to R2: {mobile_path}")
                    except Exception as e:
                        logger.error(f"Failed to save mobile PageSpeed response to R2: {e}")
                
                # Save desktop response if available
                if raw_responses.get('desktop'):
                    try:
                        desktop_file_name = f"pagespeed_insights/{project.domain}/desktop_psi_{timestamp}.json"
                        desktop_response = {
                            'url': url,
                            'strategy': 'desktop',
                            'timestamp': timestamp,
                            'data': raw_responses['desktop']
                        }
                        desktop_json = json.dumps(desktop_response, indent=2)
                        desktop_file = io.BytesIO(desktop_json.encode('utf-8'))
                        
                        desktop_path = storage.save(desktop_file_name, desktop_file)
                        site_audit.pagespeed_desktop_response_r2_path = desktop_path
                        logger.info(f"Saved desktop PageSpeed Insights raw response to R2: {desktop_path}")
                    except Exception as e:
                        logger.error(f"Failed to save desktop PageSpeed response to R2: {e}")
                        
            except Exception as e:
                logger.error(f"Failed to initialize R2 storage: {e}")
                # Continue processing even if R2 save fails
        
        # Update site audit with collected data
        updates = []
        
        # Extract and store performance scores only (not full data)
        if 'mobile' in psi_data and psi_data['mobile']:
            # The scores are already at the top level of the parsed data
            mobile_scores = psi_data['mobile'].get('scores', {})
            mobile_score = mobile_scores.get('performance') if mobile_scores else None
            if mobile_score is not None:
                site_audit.performance_score_mobile = mobile_score
                updates.append('performance_score_mobile')
            logger.info(f"Mobile PageSpeed score: {mobile_score}, Full scores: {mobile_scores}")
        
        # Store desktop performance scores only
        if 'desktop' in psi_data and psi_data['desktop']:
            # The scores are already at the top level of the parsed data
            desktop_scores = psi_data['desktop'].get('scores', {})
            desktop_score = desktop_scores.get('performance') if desktop_scores else None
            if desktop_score is not None:
                site_audit.performance_score_desktop = desktop_score
                updates.append('performance_score_desktop')
            logger.info(f"Desktop PageSpeed score: {desktop_score}, Full scores: {desktop_scores}")
        
        # Add R2 paths to updates if they were saved
        if hasattr(site_audit, 'pagespeed_mobile_response_r2_path') and site_audit.pagespeed_mobile_response_r2_path:
            updates.append('pagespeed_mobile_response_r2_path')
        if hasattr(site_audit, 'pagespeed_desktop_response_r2_path') and site_audit.pagespeed_desktop_response_r2_path:
            updates.append('pagespeed_desktop_response_r2_path')
        
        # Save the updates
        if updates:
            update_fields = list(set(updates))  # Remove duplicates
            site_audit.save(update_fields=update_fields)
            logger.info(f"Updated site audit with PageSpeed Insights data: {update_fields}")
        
        # Don't recalculate score here - it's based on SEO issues only, not PageSpeed
        # The score was already calculated when processing issues_overview.csv
        
        return {
            "status": "success",
            "message": f"PageSpeed Insights data collected for {url}",
            "mobile_score": site_audit.performance_score_mobile,
            "desktop_score": site_audit.performance_score_desktop,
            "data_collected": {
                "mobile": bool(psi_data.get('mobile')),
                "desktop": bool(psi_data.get('desktop'))
            },
            "raw_response_paths": {
                "mobile": site_audit.pagespeed_mobile_response_r2_path if hasattr(site_audit, 'pagespeed_mobile_response_r2_path') else None,
                "desktop": site_audit.pagespeed_desktop_response_r2_path if hasattr(site_audit, 'pagespeed_desktop_response_r2_path') else None
            }
        }
        
    except Exception as e:
        logger.error(f"PageSpeed Insights task error for id={site_audit_id}: {e}")
        
        # Retry if we haven't exceeded max retries
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying PageSpeed Insights task, attempt {self.request.retries + 1}")
            raise self.retry(exc=e, countdown=30 * (self.request.retries + 1))
        
        return {
            "status": "error",
            "message": f"Failed to collect PageSpeed Insights data: {str(e)}"
        }


@shared_task(
    bind=True,
    max_retries=3,
    time_limit=1800,
    soft_time_limit=1500,
    queue='audit_high_priority'  # Use high priority queue for new projects
)
def create_site_audit_for_new_project(self, project_id: int) -> dict:
    """
    Create and run a site audit for a newly created project.
    This is triggered automatically when a new project is created.
    
    Args:
        project_id: ID of the newly created project
        
    Returns:
        dict: Results of the audit task
    """
    from project.models import Project
    
    try:
        # Get the project
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            logger.error(f"Project with id={project_id} not found")
            return {"status": "error", "message": "Project not found"}
        
        logger.info(f"Creating site audit for new project: {project.domain}")
        
        # Check if a site audit already exists
        site_audit = SiteAudit.objects.filter(project=project).first()
        
        if not site_audit:
            # Create a new site audit with default settings
            site_audit = SiteAudit.objects.create(
                project=project,
                audit_frequency_days=30,
                manual_audit_frequency_days=1,
                is_audit_enabled=True,
                status='pending'
            )
            logger.info(f"Created new SiteAudit id={site_audit.id} for project {project.domain}")
        else:
            # Update existing audit to pending status
            site_audit.status = 'pending'
            site_audit.save()
            logger.info(f"Using existing SiteAudit id={site_audit.id} for project {project.domain}")
        
        # Trigger both site audit and PageSpeed audit simultaneously
        site_audit_result = run_site_audit.apply_async(
            args=[site_audit.id],
            queue='audit_high_priority'  # Use high priority queue
        )
        
        psi_result = collect_pagespeed_insights.apply_async(
            args=[site_audit.id],
            queue='audit_high_priority',  # Use same high priority queue for simultaneous execution
            countdown=2  # Small delay to ensure SiteAudit is fully saved
        )
        
        logger.info(f"Triggered HIGH PRIORITY site audit task {site_audit_result.id} for project {project.domain}")
        logger.info(f"Triggered HIGH PRIORITY PageSpeed audit task {psi_result.id} for project {project.domain}")
        
        return {
            "status": "success",
            "site_audit_id": site_audit.id,
            "site_audit_task_id": site_audit_result.id,
            "psi_task_id": psi_result.id,
            "message": f"Site audit and PageSpeed audit created and triggered for {project.domain}"
        }
        
    except Exception as e:
        logger.error(f"Failed to create site audit for project id={project_id}: {e}")
        
        # Retry if we haven't exceeded max retries
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying create_site_audit_for_new_project, attempt {self.request.retries + 1}")
            raise self.retry(exc=e, countdown=10 * (self.request.retries + 1))
        
        return {
            "status": "error",
            "message": f"Failed to create site audit: {str(e)}"
        }