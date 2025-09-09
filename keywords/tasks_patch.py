"""
PATCH FILE: Minimal changes needed for keywords/tasks.py
This shows only the modifications needed, not a full duplicate file

Apply these changes to the existing fetch_keyword_serp_html function
"""

# CHANGE 1: Import additions at the top of the file
from celery.exceptions import SoftTimeLimitExceeded
from django.db import transaction

# CHANGE 2: Modify the fetch_keyword_serp_html function
# Add keyword = None before the try block and enhance the finally block

@shared_task(
    bind=True,
    max_retries=0,  # We handle retries internally for network issues only
    time_limit=300,  # Hard limit of 5 minutes for keyword jobs
    soft_time_limit=240,  # Soft limit of 4 minutes
)
def fetch_keyword_serp_html(self, keyword_id: int) -> None:
    """
    Fetch SERP HTML for a keyword and store it locally with rotation.
    
    Args:
        keyword_id: ID of the keyword to fetch SERP for
    """
    lock_key = f"lock:serp:{keyword_id}"
    lock_timeout = 360  # 6 minutes (slightly longer than task timeout)
    keyword = None  # ADD THIS LINE - Initialize keyword variable
    
    try:
        # Try to acquire lock
        if not cache.add(lock_key, "locked", timeout=lock_timeout):
            logger.info(f"Task already running for keyword_id={keyword_id}, skipping")
            return
        
        # MODIFY: Use select_for_update to prevent race conditions
        with transaction.atomic():
            try:
                keyword = Keyword.objects.select_for_update().get(id=keyword_id)
            except Keyword.DoesNotExist:
                logger.error(f"Keyword with id={keyword_id} not found")
                return
        
        # ... rest of the existing try block code remains the same ...
        
    except SoftTimeLimitExceeded:  # ADD THIS EXCEPTION HANDLER
        logger.error(f"Task timeout (soft limit) for keyword {keyword_id}")
        if keyword:
            keyword.processing = False
            keyword.last_error_message = "Task timeout"
            keyword.failed_api_hit_count += 1
            keyword.save(update_fields=['processing', 'last_error_message', 'failed_api_hit_count'])
        raise
        
    except Exception as e:
        logger.error(f"Task error for keyword {keyword_id}: {e}")
        # Try to update the keyword with error
        try:
            if not keyword:  # Only fetch if we don't have it
                keyword = Keyword.objects.get(id=keyword_id)
            _handle_failed_fetch(keyword, str(e)[:100])
        except:
            pass
            
    finally:  # ENHANCE THE FINALLY BLOCK
        # ALWAYS reset processing flag and release lock
        if keyword:
            try:
                with transaction.atomic():
                    # Re-fetch to avoid stale data
                    keyword.refresh_from_db()
                    keyword.processing = False
                    keyword.save(update_fields=['processing', 'updated_at'])
                    logger.debug(f"Reset processing flag for keyword {keyword_id}")
            except Exception as e:
                logger.error(f"Failed to reset processing flag for keyword {keyword_id}: {e}")
                # Try direct update as last resort
                try:
                    Keyword.objects.filter(id=keyword_id).update(processing=False)
                except:
                    pass
        
        # Always release the lock
        cache.delete(lock_key)


# CHANGE 3: Enhance the cleanup_stuck_keywords function to be more aggressive
@shared_task
def cleanup_stuck_keywords():
    """
    Dedicated cleanup task that runs every 15 minutes to ensure system health.
    Performs comprehensive cleanup and recovery operations.
    """
    from project.models import Project
    from celery import current_app
    
    cleanup_stats = {
        'stuck_reset': 0,
        'orphaned_reset': 0,
        'projects_activated': 0,
        'overdue_queued': 0,
        'errors_cleared': 0
    }
    
    try:
        now = timezone.now()
        
        # CHANGE: More aggressive - reset after 1 hour instead of 15 minutes
        stuck_cutoff = now - timedelta(hours=1)  # Changed from minutes=15
        stuck_keywords = Keyword.objects.filter(
            processing=True,
            updated_at__lt=stuck_cutoff
        )
        
        # Log affected projects before resetting
        if stuck_keywords.exists():
            affected_projects = stuck_keywords.values('project__domain').annotate(
                count=models.Count('id')
            ).order_by('-count')[:5]
            
            for proj in affected_projects:
                logger.warning(f"[CLEANUP] Project {proj['project__domain']}: {proj['count']} stuck keywords")
        
        cleanup_stats['stuck_reset'] = stuck_keywords.update(
            processing=False,
            last_error_message="Auto-reset: stuck >1 hour",
            updated_at=now
        )
        
        # ... rest of the cleanup function remains the same ...
        
        # ADD: Fix NULL next_crawl_at values
        null_next = Keyword.objects.filter(
            next_crawl_at__isnull=True,
            archive=False
        )
        null_count = null_next.update(
            next_crawl_at=now,
            updated_at=now
        )
        if null_count > 0:
            logger.info(f"[CLEANUP] Fixed {null_count} keywords with NULL next_crawl_at")
            cleanup_stats['null_next_fixed'] = null_count
        
        return cleanup_stats
        
    except Exception as e:
        logger.error(f"Error in cleanup_stuck_keywords: {e}", exc_info=True)
        return {'error': str(e)}


# CHANGE 4: Update celery.py beat schedule to run cleanup more frequently
"""
In limeclicks/celery.py, update the cleanup task schedule:

'cleanup-stuck-keywords': {
    'task': 'keywords.tasks.cleanup_stuck_keywords',
    'schedule': crontab(minute='*/5'),  # Change from */15 to */5
    'options': {'queue': 'celery', 'priority': 9}
},
"""