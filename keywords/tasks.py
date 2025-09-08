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
        # Always release the lock
        cache.delete(lock_key)


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
    Celery Beat task to enqueue eligible keywords for scraping.
    Runs every 5 minutes and enqueues up to 500 keywords that haven't been scraped in 24+ hours.
    Prevents duplicate queuing using the processing flag.
    """
    from django.db import connection
    
    try:
        now = timezone.now()
        min_interval = timedelta(hours=settings.FETCH_MIN_INTERVAL_HOURS)
        cutoff_time = now - min_interval
        
        # Maximum keywords to process per run
        BATCH_SIZE = 500
        
        # Reset stuck keywords (processing for more than 10 minutes)
        stuck_cutoff = now - timedelta(minutes=10)
        stuck_count = Keyword.objects.filter(
            processing=True,
            scraped_at__lt=stuck_cutoff
        ).update(processing=False)
        
        if stuck_count > 0:
            logger.info(f"Reset {stuck_count} stuck keywords")
        
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