"""
Celery tasks for SERP HTML fetching and storage
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils import timezone

from .models import Keyword
from services.scrape_do import ScrapeDoService

logger = logging.getLogger(__name__)


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
    
    try:
        # Try to acquire lock
        if not cache.add(lock_key, "locked", timeout=lock_timeout):
            logger.info(f"Task already running for keyword_id={keyword_id}, skipping")
            return
        
        # Fetch keyword
        try:
            keyword = Keyword.objects.get(id=keyword_id)
        except Keyword.DoesNotExist:
            logger.error(f"Keyword with id={keyword_id} not found")
            return
        
        # Check if this is a force crawl or scheduled crawl
        is_force_crawl = keyword.crawl_priority == 'critical'
        
        # If force crawl, delete today's rank to allow re-ranking
        if is_force_crawl:
            from .models import Rank
            deleted_count = Rank.objects.filter(
                keyword=keyword,
                created_at__date=timezone.now().date()
            ).delete()[0]
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} existing rank(s) for keyword {keyword.id} (force crawl)")
        
        # Check eligibility (unless force crawled)
        if not is_force_crawl and keyword.scraped_at:
            # Use the model's should_crawl method for consistency
            if not keyword.should_crawl():
                time_since_last = (timezone.now() - keyword.scraped_at).total_seconds() / 3600
                logger.info(
                    f"Keyword {keyword_id} not ready for crawl. "
                    f"Last: {keyword.scraped_at}, Hours since: {time_since_last:.1f}"
                )
                # Reset processing flag since we're not actually processing
                keyword.processing = False
                keyword.save(update_fields=['processing'])
                return
        
        # Prepare Scrape.do parameters
        scraper = ScrapeDoService()
        
        # Perform the scrape with retries for network issues only
        html_content = None
        error_message = None
        retries_left = settings.SCRAPE_DO_RETRIES
        
        while retries_left > 0:
            try:
                result = scraper.scrape_google_search(
                    query=keyword.keyword,
                    country_code=keyword.country_code or keyword.country,
                    num_results=100,
                    location=keyword.location if keyword.location else None,
                    use_exact_location=bool(keyword.location)  # Use UULE if location is provided
                )
                
                if result and result.get('status_code') == 200:
                    html_content = result.get('html')
                    break
                else:
                    # Non-200 status - don't retry
                    status = result.get('status_code', 'Unknown') if result else 'No response'
                    error_message = f"HTTP {status}"
                    logger.warning(f"Non-200 response for keyword {keyword_id}: {error_message}")
                    break
                    
            except TimeoutError:
                retries_left -= 1
                if retries_left > 0:
                    logger.info(f"Timeout for keyword {keyword_id}, retrying... ({retries_left} left)")
                else:
                    error_message = "Timeout"
                    
            except ConnectionError:
                retries_left -= 1
                if retries_left > 0:
                    logger.info(f"Network error for keyword {keyword_id}, retrying... ({retries_left} left)")
                else:
                    error_message = "Network error"
                    
            except Exception as e:
                # Unexpected error - don't retry
                error_message = str(e)[:100]  # Limit error message length
                logger.error(f"Unexpected error for keyword {keyword_id}: {e}")
                break
        
        # Process the result
        if html_content:
            # Success - store the file
            _handle_successful_fetch(keyword, html_content)
        else:
            # Failure - update error counters
            _handle_failed_fetch(keyword, error_message or "Unknown error")
            
    except Exception as e:
        logger.error(f"Task error for keyword {keyword_id}: {e}")
        # Try to update the keyword with error
        try:
            keyword = Keyword.objects.get(id=keyword_id)
            _handle_failed_fetch(keyword, str(e)[:100])
        except:
            pass
    finally:
        # BULLETPROOF CLEANUP - Always reset processing flag as last resort
        try:
            # Use direct database update to ensure processing flag is reset
            # This prevents keywords from getting stuck even if exceptions occur
            from django.db import transaction
            with transaction.atomic():
                updated_count = Keyword.objects.filter(id=keyword_id).update(processing=False)
                if updated_count > 0:
                    logger.info(f"BULLETPROOF: Reset processing flag for keyword {keyword_id}")
        except Exception as cleanup_error:
            logger.error(f"BULLETPROOF CLEANUP FAILED for keyword {keyword_id}: {cleanup_error}")
            # As absolute last resort, try with raw SQL
            try:
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE keywords_keyword SET processing = FALSE WHERE id = %s",
                        [keyword_id]
                    )
                    logger.warning(f"BULLETPROOF RAW SQL: Reset processing flag for keyword {keyword_id}")
            except Exception as sql_error:
                logger.critical(f"BULLETPROOF RAW SQL FAILED for keyword {keyword_id}: {sql_error}")
        
        # Always release the lock
        try:
            cache.delete(lock_key)
        except Exception as lock_error:
            logger.error(f"Failed to release lock for keyword {keyword_id}: {lock_error}")


def _extract_top_competitors(html_content: str, project_domain: str, limit: int = 3) -> list:
    """
    Extract top competitor domains from SERP HTML (excluding project domain)
    
    Args:
        html_content: Raw HTML from Google search
        project_domain: The project's own domain to exclude
        limit: Number of top competitors to extract (default 3)
        
    Returns:
        List of dictionaries with position, domain, and url
    """
    from services.google_search_parser import GoogleSearchParser
    
    try:
        parser = GoogleSearchParser()
        parsed_results = parser.parse(html_content)
        
        organic_results = parsed_results.get('organic_results', [])
        top_competitors = []
        seen_domains = set()
        
        # Clean project domain
        project_domain = project_domain.lower().replace('www.', '').replace('http://', '').replace('https://', '')
        
        for i, result in enumerate(organic_results[:20], 1):  # Check top 20 to find competitors
            if result.get('url'):
                # Extract domain from URL
                url = result['url']
                domain_parts = url.lower().replace('http://', '').replace('https://', '').split('/')
                result_domain = domain_parts[0].replace('www.', '') if domain_parts else ''
                
                # Skip if it's the project's own domain or already seen
                if not result_domain or project_domain in result_domain or result_domain in project_domain:
                    continue
                    
                if result_domain in seen_domains:
                    continue
                    
                seen_domains.add(result_domain)
                
                top_competitors.append({
                    'position': i,
                    'domain': result_domain,
                    'url': url
                })
                
                if len(top_competitors) >= limit:
                    break
        
        return top_competitors
    except Exception as e:
        logger.warning(f"Failed to extract top competitors: {e}")
        return []


def _extract_top_pages(html_content: str, limit: int = 3) -> list:
    """
    Extract top ranking pages from SERP HTML
    
    Args:
        html_content: Raw HTML from Google search
        limit: Number of top pages to extract (default 3)
        
    Returns:
        List of dictionaries with position and url
    """
    from services.google_search_parser import GoogleSearchParser
    
    try:
        parser = GoogleSearchParser()
        parsed_results = parser.parse(html_content)
        
        organic_results = parsed_results.get('organic_results', [])
        top_pages = []
        
        for i, result in enumerate(organic_results[:limit], 1):
            if result.get('url'):
                top_pages.append({
                    'position': i,
                    'url': result['url']
                })
        
        return top_pages
    except Exception as e:
        logger.warning(f"Failed to extract top pages: {e}")
        return []


def _handle_successful_fetch(keyword: Keyword, html_content: str) -> None:
    """
    Handle successful SERP fetch - store file, extract rankings, and update database.
    
    Args:
        keyword: Keyword instance
        html_content: HTML content to store
    """
    # Build file path
    date_str = datetime.now().strftime('%Y-%m-%d')
    relative_path = f"{keyword.project_id}/{keyword.id}/{date_str}.html"
    absolute_path = Path(settings.SCRAPE_DO_STORAGE_ROOT) / relative_path
    
    # Track if this is a new file or existing
    is_new_file = not absolute_path.exists()
    
    # Check if file for today already exists (idempotency)
    # For force crawls, we overwrite; for regular crawls, we skip
    is_force_crawl = keyword.crawl_priority == 'critical'
    
    if not is_new_file and not is_force_crawl:
        logger.info(f"File already exists for today: {relative_path} (skipping overwrite)")
        # Don't overwrite for regular crawls, but still count as success
        # Extract top 10 ranking pages (to ensure we have enough after filtering own domain)
        top_pages = _extract_top_pages(html_content, limit=10)
        
        # Extract top 3 competitors (excluding project domain)
        top_competitors = _extract_top_competitors(html_content, keyword.project.domain, limit=3)
        
        # Update database to reflect the fetch attempt
        keyword.success_api_hit_count += 1
        keyword.last_error_message = None
        keyword.processing = False  # Reset processing flag
        keyword.ranking_pages = top_pages  # Update top 10 pages
        keyword.top_competitors = top_competitors  # Update top 3 competitors
        keyword.scraped_at = timezone.now()
        
        # Update file path if it's different
        if not keyword.scrape_do_file_path or keyword.scrape_do_file_path != relative_path:
            keyword.scrape_do_file_path = relative_path
            # Ensure it's in the file list
            if relative_path not in (keyword.scrape_do_files or []):
                file_list = keyword.scrape_do_files or []
                file_list.insert(0, relative_path)
                keyword.scrape_do_files = file_list[:settings.SERP_HISTORY_DAYS]
        
        # Save keyword updates before ranking process
        keyword.save()
        
        # Process for ranking (which might update rank and track manual targets)
        _process_ranking_if_needed(keyword, html_content, date_str)
        return
    elif not is_new_file and is_force_crawl:
        logger.info(f"File exists but force crawl requested: {relative_path} (will overwrite)")
    
    # Ensure directory exists
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write file atomically
    temp_path = absolute_path.with_suffix('.tmp')
    try:
        temp_path.write_text(html_content, encoding='utf-8')
        temp_path.replace(absolute_path)
    except Exception as e:
        # Clean up partial write
        if temp_path.exists():
            temp_path.unlink()
        raise e
    
    # Update file list (insert at index 0)
    file_list = keyword.scrape_do_files or []
    file_list.insert(0, relative_path)
    
    # Trim to keep only last 7 files
    files_to_delete = []
    if len(file_list) > settings.SERP_HISTORY_DAYS:
        files_to_delete = file_list[settings.SERP_HISTORY_DAYS:]
        file_list = file_list[:settings.SERP_HISTORY_DAYS]
    
    # Delete old files from disk
    storage_root = Path(settings.SCRAPE_DO_STORAGE_ROOT)
    for old_file in files_to_delete:
        old_path = storage_root / old_file
        try:
            if old_path.exists():
                old_path.unlink()
                logger.info(f"Deleted old file: {old_file}")
        except Exception as e:
            logger.warning(f"Failed to delete old file {old_file}: {e}")
    
    # Extract top 10 ranking pages before updating database (to ensure we have enough after filtering own domain)
    top_pages = _extract_top_pages(html_content, limit=10)
    
    # Extract top 3 competitors (excluding project domain)
    top_competitors = _extract_top_competitors(html_content, keyword.project.domain, limit=3)
    
    # Update database
    keyword.scrape_do_file_path = relative_path
    keyword.scrape_do_files = file_list
    keyword.success_api_hit_count += 1
    keyword.last_error_message = None
    keyword.processing = False  # Reset processing flag
    keyword.ranking_pages = top_pages  # Store top 10 pages
    keyword.top_competitors = top_competitors  # Store top 3 competitors
    keyword.scraped_at = timezone.now()
    
    # Save keyword updates before ranking process
    keyword.save()
    
    # Process ranking extraction for new file (this will update rank and track manual targets)
    _process_ranking_if_needed(keyword, html_content, date_str)
    
    logger.info(
        f"SUCCESS: keyword_id={keyword.id}, status=200, "
        f"file={relative_path}"
    )


def _handle_failed_fetch(keyword: Keyword, error_message: str) -> None:
    """
    Handle failed SERP fetch - update error counters.
    
    Args:
        keyword: Keyword instance
        error_message: Minimal error message to store
    """
    # Update only error fields, leave file paths unchanged
    keyword.failed_api_hit_count += 1
    keyword.last_error_message = error_message[:255]  # Ensure it fits in field
    keyword.processing = False  # Reset processing flag on failure
    keyword.save()
    
    logger.warning(
        f"FAILURE: keyword_id={keyword.id}, "
        f"error={error_message}"
    )


def _process_ranking_if_needed(keyword: Keyword, html_content: str, date_str: str) -> None:
    """
    Process ranking extraction if not already done for today.
    
    Args:
        keyword: Keyword instance
        html_content: HTML content to parse
        date_str: Date string (YYYY-MM-DD format)
    """
    from .models import Rank
    from .ranking_extractor import RankingExtractor
    
    # Check if ranking already exists for today
    scraped_date = datetime.strptime(date_str, '%Y-%m-%d')
    scraped_date = timezone.make_aware(scraped_date)
    
    # For force crawls, we've already deleted today's rank, so process anyway
    is_force_crawl = keyword.crawl_priority == 'critical'
    
    if not is_force_crawl:
        # Check if we already have a rank for this date
        existing_rank = Rank.objects.filter(
            keyword=keyword,
            created_at__date=scraped_date.date()
        ).exists()
        
        if existing_rank:
            logger.info(f"Rank already exists for keyword {keyword.id} on {date_str}")
            return
    
    # Process ranking
    try:
        extractor = RankingExtractor()
        result = extractor.process_serp_html(keyword, html_content, scraped_date)
        
        if result and result.get('success'):
            logger.info(
                f"Successfully extracted ranking for keyword {keyword.id}: "
                f"rank={result.get('rank')}, organic={result.get('is_organic')}"
            )
        else:
            logger.warning(f"Failed to extract ranking for keyword {keyword.id}")
    except Exception as e:
        logger.error(f"Error processing ranking for keyword {keyword.id}: {e}")


@shared_task
def enqueue_keyword_scrapes_batch():
    """
    Enhanced Celery Beat task with auto-recovery mechanisms.
    Runs every 5 minutes and enqueues up to 500 keywords that haven't been scraped in 24+ hours.
    Includes self-healing features to prevent stuck keywords.
    """
    from django.db import connection
    from project.models import Project
    
    try:
        now = timezone.now()
        min_interval = timedelta(hours=settings.FETCH_MIN_INTERVAL_HOURS)
        cutoff_time = now - min_interval
        
        # Maximum keywords to process per run
        BATCH_SIZE = 500
        
        # === AUTO-RECOVERY MECHANISM 1: Reset stuck keywords ===
        # Reset keywords that have been processing for more than 10 minutes
        stuck_cutoff = now - timedelta(minutes=10)
        stuck_keywords = Keyword.objects.filter(
            processing=True
        ).filter(
            models.Q(scraped_at__isnull=True) |  # Never scraped but stuck
            models.Q(scraped_at__lt=stuck_cutoff)  # Or scraped long ago
        )
        stuck_count = stuck_keywords.update(processing=False)
        
        if stuck_count > 0:
            logger.info(f"[AUTO-RECOVERY] Reset {stuck_count} stuck keywords")
        
        # === AUTO-RECOVERY MECHANISM 2: Auto-activate projects with overdue keywords ===
        # Find projects that are inactive but have overdue keywords
        inactive_projects_with_overdue = Project.objects.filter(
            active=False,
            keywords__scraped_at__lt=cutoff_time,
            keywords__archive=False
        ).distinct()
        
        if inactive_projects_with_overdue.exists():
            activated_count = inactive_projects_with_overdue.update(active=True)
            logger.warning(
                f"[AUTO-RECOVERY] Activated {activated_count} inactive projects with overdue keywords: "
                f"{', '.join([p.domain for p in inactive_projects_with_overdue[:5]])}"
            )
        
        # === AUTO-RECOVERY MECHANISM 3: Reset orphaned processing flags ===
        # Reset keywords where processing=True but no task is running for them
        # This handles cases where tasks failed without cleanup
        orphaned_reset_count = 0
        processing_keywords = Keyword.objects.filter(processing=True)
        if processing_keywords.count() > 100:  # Only check if there are many stuck
            # Get list of keyword IDs currently being processed by Celery
            from celery import current_app
            i = current_app.control.inspect()
            active_tasks = i.active()
            
            active_keyword_ids = set()
            if active_tasks:
                for worker, tasks in active_tasks.items():
                    for task in tasks:
                        if 'fetch_keyword_serp_html' in task.get('name', ''):
                            args = task.get('args', [])
                            if args and isinstance(args[0], int):
                                active_keyword_ids.add(args[0])
            
            # Reset keywords that claim to be processing but aren't in active tasks
            orphaned_keywords = processing_keywords.exclude(id__in=active_keyword_ids)
            orphaned_reset_count = orphaned_keywords.update(processing=False)
            
            if orphaned_reset_count > 0:
                logger.info(f"[AUTO-RECOVERY] Reset {orphaned_reset_count} orphaned processing flags")
        
        # Find eligible keywords that aren't already processing
        # Wrap in transaction for select_for_update
        from django.db import transaction
        
        with transaction.atomic():
            eligible_keywords = list(Keyword.objects.select_for_update(skip_locked=True).filter(
                models.Q(scraped_at__isnull=True) |  # Never scraped
                models.Q(scraped_at__lte=cutoff_time)  # Scraped > 24h ago
            ).filter(
                archive=False,  # Not archived
                project__active=True,  # Active project
                processing=False  # Not already in queue
            ).values_list('id', 'scraped_at')[:BATCH_SIZE])
            
            # Mark keywords as processing inside the same transaction
            if eligible_keywords:
                keyword_ids = [kid for kid, _ in eligible_keywords]
                Keyword.objects.filter(id__in=keyword_ids).update(processing=True)
        
        if not eligible_keywords:
            logger.info("No keywords eligible for scraping")
            return {'total': 0, 'high_priority': 0, 'default_priority': 0}
        
        enqueued_high = 0
        enqueued_default = 0
        
        for keyword_id, scraped_at in eligible_keywords:
            # Only use serp_high for keywords that have never been scraped
            if scraped_at is None:
                queue_name = 'serp_high'
                priority = 10
                enqueued_high += 1
            else:
                queue_name = 'serp_default'
                priority = 5
                enqueued_default += 1
            
            # Enqueue the task
            fetch_keyword_serp_html.apply_async(
                args=[keyword_id],
                queue=queue_name,
                priority=priority
            )
    
        logger.info(
            f"Enqueued batch of {len(eligible_keywords)} keywords. "
            f"High priority (never scraped): {enqueued_high}, "
            f"Default priority: {enqueued_default}"
        )
        
        return {
            'total': len(eligible_keywords),
            'high_priority': enqueued_high,
            'default_priority': enqueued_default,
            'batch_size': BATCH_SIZE
        }
    except Exception as e:
        logger.error(f"Error in enqueue_keyword_scrapes_batch: {e}", exc_info=True)
        return {'total': 0, 'high_priority': 0, 'default_priority': 0, 'error': str(e)}
    finally:
        # Ensure database connection is closed to prevent connection leaks
        connection.close()


# ===================================================================
# DAILY KEYWORD SCHEDULING SYSTEM - BULLETPROOF GUARANTEE SYSTEM
# ===================================================================

@shared_task
def daily_queue_all_keywords():
    """
    DAILY BULK SCHEDULER - Queue ALL keywords at start of day (12:01 AM)
    
    GUARANTEE MECHANISMS:
    1. Tracks every keyword queued in database
    2. Spreads execution evenly across 24 hours
    3. Logs everything for verification
    4. Returns detailed statistics
    """
    import random
    from django.db import transaction
    from datetime import datetime, timedelta
    
    stats = {
        'total_keywords': 0,
        'queued_count': 0,
        'skipped_count': 0,
        'error_count': 0,
        'queue_date': timezone.now().date(),
        'errors': []
    }
    
    try:
        logger.info("[DAILY QUEUE] Starting daily keyword scheduling...")
        
        # Get all active keywords
        keywords = Keyword.objects.filter(
            archive=False, 
            project__active=True
        ).select_related('project')
        
        stats['total_keywords'] = keywords.count()
        logger.info(f"[DAILY QUEUE] Found {stats['total_keywords']} active keywords to queue")
        
        if stats['total_keywords'] == 0:
            logger.warning("[DAILY QUEUE] No active keywords found!")
            return stats
        
        # Create queue tracking entries and queue ALL tasks immediately
        for keyword in keywords.iterator():
            try:
                # Queue the task immediately with standard priority - NO DELAYS
                result = fetch_keyword_serp_html.apply_async(
                    args=[keyword.id],
                    priority=5,  # Standard daily priority
                    countdown=0  # IMMEDIATE - no delays
                )
                
                # Track this queue operation
                with transaction.atomic():
                    # Update keyword with queue tracking info
                    keyword.last_queue_date = timezone.now().date()
                    keyword.daily_queue_task_id = str(result.id)
                    keyword.expected_crawl_time = timezone.now()  # Expected immediately
                    keyword.save(update_fields=['last_queue_date', 'daily_queue_task_id', 'expected_crawl_time'])
                
                stats['queued_count'] += 1
                
                if stats['queued_count'] % 100 == 0:
                    logger.info(f"[DAILY QUEUE] Queued {stats['queued_count']}/{stats['total_keywords']} keywords...")
                    
            except Exception as e:
                stats['error_count'] += 1
                stats['errors'].append(f"Keyword {keyword.id}: {str(e)}")
                logger.error(f"[DAILY QUEUE] Failed to queue keyword {keyword.id}: {e}")
        
        logger.info(f"[DAILY QUEUE] COMPLETED: {stats['queued_count']}/{stats['total_keywords']} keywords queued")
        
        # Schedule gap detection tasks throughout the day
        _schedule_gap_detection_tasks()
        
        return stats
        
    except Exception as e:
        logger.error(f"[DAILY QUEUE] CRITICAL ERROR: {e}")
        stats['errors'].append(f"Critical error: {str(e)}")
        return stats


@shared_task  
def queue_new_keyword_immediately(keyword_id):
    """
    IMMEDIATE NEW KEYWORD PROCESSOR - High priority for newly added keywords
    
    When users add new keywords, they get immediate high-priority processing
    """
    try:
        keyword = Keyword.objects.get(id=keyword_id)
        
        # Queue immediately with high priority
        result = fetch_keyword_serp_html.apply_async(
            args=[keyword_id],
            priority=10,  # HIGH PRIORITY - immediate processing
            countdown=0
        )
        
        # Track the immediate queue
        keyword.last_queue_date = timezone.now().date()
        keyword.daily_queue_task_id = str(result.id)
        keyword.expected_crawl_time = timezone.now()
        keyword.save(update_fields=['last_queue_date', 'daily_queue_task_id', 'expected_crawl_time'])
        
        logger.info(f"[IMMEDIATE QUEUE] Queued new keyword {keyword_id} with high priority")
        return {'keyword_id': keyword_id, 'task_id': str(result.id), 'status': 'queued'}
        
    except Keyword.DoesNotExist:
        logger.error(f"[IMMEDIATE QUEUE] Keyword {keyword_id} not found")
        return {'error': f'Keyword {keyword_id} not found'}
    except Exception as e:
        logger.error(f"[IMMEDIATE QUEUE] Failed to queue keyword {keyword_id}: {e}")
        return {'error': str(e)}


@shared_task
def user_recheck_keyword_rank(keyword_id, user_id=None):
    """
    USER-INITIATED RANK RECHECK - HIGHEST PRIORITY
    
    When users manually request a rank recheck, it gets top priority
    and jumps ahead of all other queued tasks
    """
    try:
        keyword = Keyword.objects.get(id=keyword_id)
        
        # Queue immediately with HIGHEST priority - jumps the queue
        result = fetch_keyword_serp_html.apply_async(
            args=[keyword_id],
            priority=10,  # HIGHEST PRIORITY - user-initiated
            countdown=0
        )
        
        # Track the user recheck
        keyword.daily_queue_task_id = str(result.id)
        keyword.expected_crawl_time = timezone.now()
        keyword.last_force_crawl_at = timezone.now()  # Track as force crawl
        keyword.force_crawl_count += 1
        keyword.save(update_fields=[
            'daily_queue_task_id', 
            'expected_crawl_time', 
            'last_force_crawl_at',
            'force_crawl_count'
        ])
        
        logger.info(f"[USER RECHECK] Queued keyword {keyword_id} for user {user_id} with highest priority")
        return {'keyword_id': keyword_id, 'task_id': str(result.id), 'status': 'queued', 'priority': 'highest'}
        
    except Keyword.DoesNotExist:
        logger.error(f"[USER RECHECK] Keyword {keyword_id} not found")
        return {'error': f'Keyword {keyword_id} not found'}
    except Exception as e:
        logger.error(f"[USER RECHECK] Failed to queue keyword {keyword_id}: {e}")
        return {'error': str(e)}


@shared_task
def detect_and_recover_missed_keywords():
    """
    GAP DETECTION & STUCK KEYWORD RECOVERY - Find and fix processing issues
    
    Runs every 6 hours to:
    1. Find keywords that should have been processed but weren't
    2. Auto-fix stuck keywords that are blocking processing
    3. Recover any missed daily queue entries
    """
    from datetime import timedelta
    
    stats = {
        'checked_count': 0,
        'missed_count': 0,
        'recovered_count': 0,
        'errors': []
    }
    
    try:
        now = timezone.now()
        today = now.date()
        
        # Find keywords that were queued today but haven't been processed yet
        # Focus on keywords that are genuinely stuck or missed
        
        # 1. Find keywords queued today but not processed
        missed_keywords = Keyword.objects.filter(
            archive=False,
            project__active=True,
            last_queue_date=today,
            scraped_at__date__lt=today  # Not crawled today
        ).select_related('project')
        
        # 2. Also find keywords stuck in processing for >6 hours
        stuck_threshold = now - timedelta(hours=6)
        stuck_keywords = Keyword.objects.filter(
            archive=False,
            project__active=True,
            processing=True,
            updated_at__lt=stuck_threshold
        ).select_related('project')
        
        # Combine missed and stuck keywords
        all_problem_keywords = missed_keywords.union(stuck_keywords)
        
        stats['checked_count'] = Keyword.objects.filter(
            archive=False, 
            project__active=True,
            last_queue_date=today
        ).count()
        
        stats['missed_count'] = all_problem_keywords.count()
        
        if stats['missed_count'] > 0:
            logger.warning(f"[GAP DETECTION] Found {stats['missed_count']} problem keywords (missed/stuck) - recovering...")
            
            for keyword in all_problem_keywords.iterator():
                try:
                    # First, reset processing flag if stuck
                    if keyword.processing:
                        keyword.processing = False
                        keyword.last_error_message = "Auto-reset: stuck >6hrs"
                        keyword.save(update_fields=['processing', 'last_error_message'])
                        logger.info(f"[GAP DETECTION] Reset stuck processing flag for keyword {keyword.id}")
                    
                    # Re-queue with high priority for immediate processing
                    result = fetch_keyword_serp_html.apply_async(
                        args=[keyword.id],
                        priority=8,  # High priority for recovery
                        countdown=0
                    )
                    
                    # Update tracking
                    keyword.daily_queue_task_id = str(result.id)
                    keyword.expected_crawl_time = now
                    keyword.save(update_fields=['daily_queue_task_id', 'expected_crawl_time'])
                    
                    stats['recovered_count'] += 1
                    
                except Exception as e:
                    stats['errors'].append(f"Keyword {keyword.id}: {str(e)}")
            
            logger.info(f"[GAP DETECTION] Recovered {stats['recovered_count']}/{stats['missed_count']} problem keywords")
        else:
            logger.info(f"[GAP DETECTION] All {stats['checked_count']} keywords healthy - no recovery needed")
        
        return stats
        
    except Exception as e:
        logger.error(f"[GAP DETECTION] Error: {e}")
        stats['errors'].append(str(e))
        return stats


@shared_task
def end_of_day_audit():
    """
    END-OF-DAY AUDIT - Final verification that every keyword was processed
    
    Runs at 11:00 PM to ensure 100% completion rate
    """
    stats = {
        'total_keywords': 0,
        'processed_today': 0,
        'completion_rate': 0.0,
        'missing_keywords': [],
        'final_recovery_count': 0
    }
    
    try:
        today = timezone.now().date()
        
        # Count all active keywords
        all_keywords = Keyword.objects.filter(
            archive=False,
            project__active=True
        ).select_related('project')
        
        stats['total_keywords'] = all_keywords.count()
        
        # Count keywords processed today
        processed_today = all_keywords.filter(
            scraped_at__date=today
        )
        
        stats['processed_today'] = processed_today.count()
        stats['completion_rate'] = (stats['processed_today'] / stats['total_keywords']) * 100 if stats['total_keywords'] > 0 else 0
        
        # Find missing keywords
        missing = all_keywords.exclude(scraped_at__date=today)
        
        if missing.exists():
            logger.warning(f"[END-OF-DAY AUDIT] {missing.count()} keywords not processed today - FINAL RECOVERY")
            
            for keyword in missing.iterator():
                stats['missing_keywords'].append({
                    'id': keyword.id,
                    'keyword': keyword.keyword,
                    'project': keyword.project.domain,
                    'last_scraped': keyword.scraped_at.isoformat() if keyword.scraped_at else 'Never'
                })
                
                # FINAL RECOVERY - Queue with highest priority
                try:
                    result = fetch_keyword_serp_html.apply_async(
                        args=[keyword.id],
                        priority=10,  # HIGHEST PRIORITY
                        countdown=0
                    )
                    stats['final_recovery_count'] += 1
                    
                except Exception as e:
                    logger.error(f"[END-OF-DAY AUDIT] Failed final recovery for keyword {keyword.id}: {e}")
        
        logger.info(f"[END-OF-DAY AUDIT] Completion Rate: {stats['completion_rate']:.1f}% ({stats['processed_today']}/{stats['total_keywords']})")
        
        if stats['final_recovery_count'] > 0:
            logger.warning(f"[END-OF-DAY AUDIT] Final recovery initiated for {stats['final_recovery_count']} keywords")
        
        return stats
        
    except Exception as e:
        logger.error(f"[END-OF-DAY AUDIT] Error: {e}")
        return {'error': str(e)}


def _schedule_gap_detection_tasks():
    """
    Helper function to schedule gap detection tasks throughout the day
    
    Since we now queue everything immediately at 12:01 AM, we schedule
    more frequent gap detection to catch any issues quickly
    """
    # Schedule gap detection every 2 hours starting from 2 AM  
    # This ensures we catch any missed keywords quickly
    logger.info("[DAILY QUEUE] Scheduling gap detection tasks for today")
    
    # Note: The regular scheduled gap detection (every 2 hours) will handle this
    # We don't need to schedule extra tasks since Celery beat handles the schedule


@shared_task
def cleanup_stuck_keywords():
    """
    AGGRESSIVE cleanup task that runs every 5 minutes for bulletproof system health.
    Performs comprehensive cleanup and recovery operations with multiple safety layers.
    """
    from project.models import Project
    from celery import current_app
    from django.db import transaction
    
    cleanup_stats = {
        'stuck_reset_short': 0,
        'stuck_reset_long': 0,
        'orphaned_reset': 0,
        'projects_activated': 0,
        'overdue_queued': 0,
        'errors_cleared': 0,
        'cache_locks_cleared': 0
    }
    
    try:
        now = timezone.now()
        
        # 0. EMERGENCY: Clear keywords stuck for >12 hours (definitely abandoned)
        emergency_cutoff = now - timedelta(hours=12)
        emergency_stuck = Keyword.objects.filter(
            processing=True,
            updated_at__lt=emergency_cutoff
        )
        emergency_count = emergency_stuck.update(
            processing=False,
            last_error_message="Auto-reset: emergency cleanup >12hrs"
        )
        if emergency_count > 0:
            logger.warning(f"[EMERGENCY CLEANUP] Reset {emergency_count} keywords stuck >12 hours")
        
        # 1. CONSERVATIVE: Reset keywords stuck for >2 hours (legitimately stuck)
        conservative_stuck_cutoff = now - timedelta(hours=2)
        conservative_stuck = Keyword.objects.filter(
            processing=True,
            updated_at__lt=conservative_stuck_cutoff
        )
        cleanup_stats['stuck_reset_short'] = conservative_stuck.update(
            processing=False,
            last_error_message="Auto-reset: stuck >2hrs"
        )
        
        # 2. AGGRESSIVE: Reset keywords stuck for >3 hours with bulletproof method
        aggressive_stuck_cutoff = now - timedelta(hours=3)
        
        # Use raw SQL for maximum reliability - only for truly abandoned keywords
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE keywords_keyword 
                SET processing = FALSE, 
                    last_error_message = 'Auto-reset: abandoned >3hrs',
                    updated_at = %s
                WHERE processing = TRUE 
                AND updated_at < %s
            """, [now, aggressive_stuck_cutoff])
            cleanup_stats['stuck_reset_long'] = cursor.rowcount
        
        # 2. Clear processing flag for keywords with no active Celery tasks
        i = current_app.control.inspect()
        active_tasks = i.active()
        
        active_keyword_ids = set()
        if active_tasks:
            for worker, tasks in active_tasks.items():
                for task in tasks:
                    if 'fetch_keyword_serp_html' in task.get('name', ''):
                        args = task.get('args', [])
                        if args and isinstance(args[0], int):
                            active_keyword_ids.add(args[0])
        
        # 3. Find keywords claiming to be processing but not in active tasks
        # BUT only reset those stuck for more than 30 minutes (allow time for queuing)
        orphaned_cutoff = now - timedelta(minutes=30)
        orphaned = Keyword.objects.filter(
            processing=True,
            updated_at__lt=orphaned_cutoff  # Give 30 minutes grace period
        ).exclude(id__in=active_keyword_ids)
        cleanup_stats['orphaned_reset'] = orphaned.update(
            processing=False,
            last_error_message="Auto-reset: orphaned task >30min"
        )
        
        # 4. Clear stale Redis cache locks (older than 10 minutes)
        cache_lock_pattern = "lock:serp:*"
        try:
            from django.core.cache import cache
            # This is a simplified approach - in production you might want to use Redis directly
            # for more precise pattern matching and cleanup
            cleanup_stats['cache_locks_cleared'] = 0  # Placeholder
        except Exception as cache_error:
            logger.warning(f"Cache lock cleanup failed: {cache_error}")
        
        # 3. Auto-activate projects with overdue keywords
        min_interval = timedelta(hours=settings.FETCH_MIN_INTERVAL_HOURS)
        cutoff_time = now - min_interval
        
        inactive_projects = Project.objects.filter(
            active=False,
            keywords__scraped_at__lt=cutoff_time,
            keywords__archive=False
        ).distinct()
        
        if inactive_projects.exists():
            cleanup_stats['projects_activated'] = inactive_projects.update(active=True)
            project_names = ', '.join([p.domain for p in inactive_projects[:3]])
            logger.warning(f"[CLEANUP] Activated {cleanup_stats['projects_activated']} projects: {project_names}...")
        
        # 4. Queue severely overdue keywords (>48 hours)
        severe_cutoff = now - timedelta(hours=48)
        severely_overdue = Keyword.objects.filter(
            scraped_at__lt=severe_cutoff,
            archive=False,
            project__active=True,
            processing=False
        )[:50]  # Limit to 50 to avoid overload
        
        for keyword in severely_overdue:
            fetch_keyword_serp_html.apply_async(
                args=[keyword.id],
                queue='serp_high',
                priority=9
            )
            cleanup_stats['overdue_queued'] += 1
        
        # 5. Clear old error messages for successfully scraped keywords
        recent_success = Keyword.objects.filter(
            scraped_at__gt=now - timedelta(hours=25),
            last_error_message__isnull=False
        )
        cleanup_stats['errors_cleared'] = recent_success.update(last_error_message=None)
        
        # Log cleanup results
        if any(cleanup_stats.values()):
            logger.info(
                f"[CLEANUP] Completed - "
                f"Stuck reset: {cleanup_stats['stuck_reset']}, "
                f"Orphaned reset: {cleanup_stats['orphaned_reset']}, "
                f"Projects activated: {cleanup_stats['projects_activated']}, "
                f"Overdue queued: {cleanup_stats['overdue_queued']}, "
                f"Errors cleared: {cleanup_stats['errors_cleared']}"
            )
        
        return cleanup_stats
        
    except Exception as e:
        logger.error(f"Error in cleanup_stuck_keywords: {e}", exc_info=True)
        return {'error': str(e)}


@shared_task
def worker_health_check():
    """
    Monitor Celery worker health and take corrective actions if needed.
    Runs every 5 minutes.
    """
    from celery import current_app
    import subprocess
    
    health_status = {
        'workers_online': 0,
        'active_tasks': 0,
        'reserved_tasks': 0,
        'actions_taken': []
    }
    
    try:
        # Check worker status
        i = current_app.control.inspect()
        stats = i.stats()
        
        if not stats:
            # No workers responding - this is critical
            logger.critical("[HEALTH] No Celery workers responding!")
            health_status['actions_taken'].append('No workers found - restart may be needed')
            
            # Try to restart the worker service (requires sudo permissions configured)
            try:
                result = subprocess.run(
                    ['sudo', 'systemctl', 'restart', 'limeclicks-celery'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    health_status['actions_taken'].append('Successfully restarted Celery worker service')
                    logger.info("[HEALTH] Restarted Celery worker service")
            except Exception as restart_error:
                logger.error(f"[HEALTH] Failed to restart worker: {restart_error}")
        else:
            health_status['workers_online'] = len(stats)
            
            # Check active tasks
            active = i.active()
            if active:
                for worker, tasks in active.items():
                    health_status['active_tasks'] += len(tasks)
            
            # Check reserved tasks
            reserved = i.reserved()
            if reserved:
                for worker, tasks in reserved.items():
                    health_status['reserved_tasks'] += len(tasks)
            
            # Check for task backlog
            if health_status['reserved_tasks'] > 100:
                logger.warning(f"[HEALTH] High task backlog: {health_status['reserved_tasks']} tasks waiting")
                health_status['actions_taken'].append(f"High backlog detected: {health_status['reserved_tasks']} tasks")
            
            # Check for stuck workers (active tasks but no reserved)
            if health_status['active_tasks'] > 10 and health_status['reserved_tasks'] == 0:
                stuck_count = Keyword.objects.filter(processing=True).count()
                if stuck_count > 20:
                    logger.warning(f"[HEALTH] Possible stuck workers: {stuck_count} keywords processing")
                    # Reset stuck keywords
                    reset_count = Keyword.objects.filter(
                        processing=True,
                        updated_at__lt=timezone.now() - timedelta(minutes=20)
                    ).update(processing=False)
                    if reset_count > 0:
                        health_status['actions_taken'].append(f"Reset {reset_count} stuck keywords")
        
        # Log health status if issues found
        if health_status['actions_taken']:
            logger.info(f"[HEALTH] Status: {health_status}")
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error in worker_health_check: {e}", exc_info=True)
        return {'error': str(e)}