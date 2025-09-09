"""
Enhanced Celery tasks for SERP HTML fetching with improved error handling and recovery
This file contains the permanent fix for keyword crawling issues
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.core.cache import cache
from django.db import models, transaction
from django.utils import timezone

from .models import Keyword
from services.scrape_do import ScrapeDoService

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    time_limit=300,  # Hard limit: 5 minutes
    soft_time_limit=240,  # Soft limit: 4 minutes
    default_retry_delay=60
)
def fetch_keyword_serp_html_enhanced(self, keyword_id: int) -> None:
    """
    Enhanced version with proper error handling and guaranteed flag reset.
    
    Key improvements:
    1. Always resets processing flag in finally block
    2. Handles soft time limit exceptions
    3. Uses atomic transactions for flag updates
    4. Better error logging and recovery
    """
    lock_key = f"lock:serp:{keyword_id}"
    lock_timeout = 360  # 6 minutes
    keyword = None
    
    try:
        # Try to acquire lock
        if not cache.add(lock_key, "locked", timeout=lock_timeout):
            logger.info(f"Task already running for keyword_id={keyword_id}, skipping")
            return
        
        # Fetch keyword with select_for_update to prevent race conditions
        with transaction.atomic():
            try:
                keyword = Keyword.objects.select_for_update().get(id=keyword_id)
                
                # Double-check not already processing (race condition prevention)
                if keyword.processing:
                    logger.warning(f"Keyword {keyword_id} already processing, skipping")
                    return
                
                # Set processing flag atomically
                keyword.processing = True
                keyword.save(update_fields=['processing', 'updated_at'])
                
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
            if not keyword.should_crawl():
                time_since_last = (timezone.now() - keyword.scraped_at).total_seconds() / 3600
                logger.info(
                    f"Keyword {keyword_id} not ready for crawl. "
                    f"Last: {keyword.scraped_at}, Hours since: {time_since_last:.1f}"
                )
                return  # Processing flag will be reset in finally
        
        # Prepare Scrape.do parameters
        scraper = ScrapeDoService()
        
        # Perform the scrape with retries
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
                    use_exact_location=bool(keyword.location)
                )
                
                if result and result.get('status_code') == 200:
                    html_content = result.get('html')
                    break
                else:
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
                error_message = str(e)[:100]
                logger.error(f"Unexpected error for keyword {keyword_id}: {e}")
                break
        
        # Process the result
        if html_content:
            _handle_successful_fetch(keyword, html_content)
        else:
            _handle_failed_fetch(keyword, error_message or "Unknown error")
            
    except SoftTimeLimitExceeded:
        logger.error(f"Task timeout (soft limit) for keyword {keyword_id}")
        if keyword:
            keyword.last_error_message = "Task timeout"
            keyword.failed_api_hit_count += 1
            keyword.save(update_fields=['last_error_message', 'failed_api_hit_count'])
        raise
        
    except Exception as e:
        logger.error(f"Task error for keyword {keyword_id}: {e}", exc_info=True)
        if keyword:
            keyword.last_error_message = str(e)[:100]
            keyword.failed_api_hit_count += 1
            keyword.save(update_fields=['last_error_message', 'failed_api_hit_count'])
        
        # Retry the task if we have retries left
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
            
    finally:
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


def _handle_successful_fetch(keyword: Keyword, html_content: str) -> None:
    """Handle successful SERP fetch - store file and update database."""
    # Build file path
    date_str = datetime.now().strftime('%Y-%m-%d')
    relative_path = f"{keyword.project_id}/{keyword.id}/{date_str}.html"
    absolute_path = Path(settings.SCRAPE_DO_STORAGE_ROOT) / relative_path
    
    # Check if file already exists
    is_force_crawl = keyword.crawl_priority == 'critical'
    
    if absolute_path.exists() and not is_force_crawl:
        logger.info(f"File already exists for today: {relative_path} (skipping overwrite)")
    else:
        # Ensure directory exists
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file atomically
        temp_path = absolute_path.with_suffix('.tmp')
        try:
            temp_path.write_text(html_content, encoding='utf-8')
            temp_path.replace(absolute_path)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise e
    
    # Update file list
    file_list = keyword.scrape_do_files or []
    if relative_path not in file_list:
        file_list.insert(0, relative_path)
    
    # Trim to keep only last 7 files
    if len(file_list) > settings.SERP_HISTORY_DAYS:
        files_to_delete = file_list[settings.SERP_HISTORY_DAYS:]
        file_list = file_list[:settings.SERP_HISTORY_DAYS]
        
        # Delete old files
        storage_root = Path(settings.SCRAPE_DO_STORAGE_ROOT)
        for old_file in files_to_delete:
            old_path = storage_root / old_file
            try:
                if old_path.exists():
                    old_path.unlink()
                    logger.info(f"Deleted old file: {old_file}")
            except Exception as e:
                logger.warning(f"Failed to delete old file {old_file}: {e}")
    
    # Extract ranking data
    from services.google_search_parser import GoogleSearchParser
    
    try:
        parser = GoogleSearchParser()
        parsed_results = parser.parse(html_content)
        
        # Extract top pages and competitors
        organic_results = parsed_results.get('organic_results', [])
        top_pages = []
        top_competitors = []
        seen_domains = set()
        project_domain = keyword.project.domain.lower().replace('www.', '')
        
        for i, result in enumerate(organic_results[:20], 1):
            if result.get('url'):
                # Add to top pages
                if len(top_pages) < 10:
                    top_pages.append({
                        'position': i,
                        'url': result['url']
                    })
                
                # Extract domain for competitors
                url = result['url']
                domain_parts = url.lower().replace('http://', '').replace('https://', '').split('/')
                result_domain = domain_parts[0].replace('www.', '') if domain_parts else ''
                
                # Add to competitors if not project domain and not seen
                if (result_domain and 
                    project_domain not in result_domain and 
                    result_domain not in project_domain and
                    result_domain not in seen_domains and
                    len(top_competitors) < 3):
                    
                    seen_domains.add(result_domain)
                    top_competitors.append({
                        'position': i,
                        'domain': result_domain,
                        'url': url
                    })
        
        keyword.ranking_pages = top_pages
        keyword.top_competitors = top_competitors
        
    except Exception as e:
        logger.warning(f"Failed to extract ranking data: {e}")
    
    # Update database
    keyword.scrape_do_file_path = relative_path
    keyword.scrape_do_files = file_list
    keyword.success_api_hit_count += 1
    keyword.last_error_message = None
    keyword.scraped_at = timezone.now()
    
    # Reset priority if it was critical (force crawl)
    if keyword.crawl_priority == 'critical':
        keyword.crawl_priority = 'normal'
    
    keyword.save()
    
    # Process ranking
    _process_ranking_if_needed(keyword, html_content, date_str)
    
    logger.info(f"SUCCESS: keyword_id={keyword.id}, file={relative_path}")


def _handle_failed_fetch(keyword: Keyword, error_message: str) -> None:
    """Handle failed SERP fetch - update error counters."""
    keyword.failed_api_hit_count += 1
    keyword.last_error_message = error_message[:255]
    keyword.save(update_fields=['failed_api_hit_count', 'last_error_message', 'updated_at'])
    
    logger.warning(f"FAILURE: keyword_id={keyword.id}, error={error_message}")


def _process_ranking_if_needed(keyword: Keyword, html_content: str, date_str: str) -> None:
    """Process ranking extraction if not already done for today."""
    from .models import Rank
    from .ranking_extractor import RankingExtractor
    
    scraped_date = datetime.strptime(date_str, '%Y-%m-%d')
    scraped_date = timezone.make_aware(scraped_date)
    
    is_force_crawl = keyword.crawl_priority == 'critical'
    
    if not is_force_crawl:
        existing_rank = Rank.objects.filter(
            keyword=keyword,
            created_at__date=scraped_date.date()
        ).exists()
        
        if existing_rank:
            logger.info(f"Rank already exists for keyword {keyword.id} on {date_str}")
            return
    
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
def cleanup_stuck_keywords_aggressive():
    """
    More aggressive cleanup task - runs every 5 minutes.
    Resets keywords stuck for just 1 hour (not 2).
    """
    from project.models import Project
    from celery import current_app
    
    cleanup_stats = {
        'stuck_reset': 0,
        'orphaned_reset': 0,
        'null_next_crawl': 0,
        'projects_activated': 0,
        'very_old_queued': 0
    }
    
    try:
        now = timezone.now()
        
        # 1. Reset keywords stuck for >1 hour (more aggressive)
        one_hour_ago = now - timedelta(hours=1)
        stuck_keywords = Keyword.objects.filter(
            processing=True,
            updated_at__lt=one_hour_ago
        )
        
        count = stuck_keywords.count()
        if count > 0:
            logger.warning(f"[AGGRESSIVE CLEANUP] Resetting {count} stuck keywords (1+ hour old)")
            
            # Log which projects are affected
            affected_projects = stuck_keywords.values('project__domain').annotate(
                count=models.Count('id')
            ).order_by('-count')[:5]
            
            for proj in affected_projects:
                logger.info(f"  - {proj['project__domain']}: {proj['count']} keywords")
            
            cleanup_stats['stuck_reset'] = stuck_keywords.update(
                processing=False,
                last_error_message="Auto-reset: stuck >1 hour",
                updated_at=now
            )
        
        # 2. Check for orphaned processing flags
        i = current_app.control.inspect()
        active_tasks = i.active() if i else None
        
        if active_tasks:
            active_keyword_ids = set()
            for worker, tasks in active_tasks.items():
                for task in tasks:
                    if 'fetch_keyword_serp_html' in task.get('name', ''):
                        args = task.get('args', [])
                        if args and isinstance(args[0], int):
                            active_keyword_ids.add(args[0])
            
            orphaned = Keyword.objects.filter(
                processing=True
            ).exclude(id__in=active_keyword_ids)
            
            cleanup_stats['orphaned_reset'] = orphaned.update(
                processing=False,
                updated_at=now
            )
        
        # 3. Fix keywords with NULL next_crawl_at
        null_next = Keyword.objects.filter(
            next_crawl_at__isnull=True,
            archive=False
        )
        cleanup_stats['null_next_crawl'] = null_next.update(
            next_crawl_at=now,
            updated_at=now
        )
        
        # 4. Auto-activate inactive projects with overdue keywords
        cutoff = now - timedelta(hours=24)
        inactive_projects = Project.objects.filter(
            active=False,
            keyword__scraped_at__lt=cutoff,
            keyword__archive=False
        ).distinct()
        
        if inactive_projects.exists():
            cleanup_stats['projects_activated'] = inactive_projects.update(active=True)
            logger.warning(f"[CLEANUP] Activated {cleanup_stats['projects_activated']} inactive projects")
        
        # 5. Force queue very old keywords (>48 hours)
        two_days_ago = now - timedelta(hours=48)
        very_old = Keyword.objects.filter(
            scraped_at__lt=two_days_ago,
            archive=False,
            project__active=True,
            processing=False
        )[:30]  # Limit to prevent overload
        
        for keyword in very_old:
            keyword.processing = True
            keyword.save(update_fields=['processing'])
            
            fetch_keyword_serp_html_enhanced.apply_async(
                args=[keyword.id],
                queue='serp_high',
                priority=10
            )
            cleanup_stats['very_old_queued'] += 1
        
        # Log results
        if any(cleanup_stats.values()):
            logger.info(
                f"[AGGRESSIVE CLEANUP] "
                f"Stuck: {cleanup_stats['stuck_reset']}, "
                f"Orphaned: {cleanup_stats['orphaned_reset']}, "
                f"NULL fixed: {cleanup_stats['null_next_crawl']}, "
                f"Projects: {cleanup_stats['projects_activated']}, "
                f"Queued: {cleanup_stats['very_old_queued']}"
            )
        
        return cleanup_stats
        
    except Exception as e:
        logger.error(f"Error in aggressive cleanup: {e}", exc_info=True)
        return {'error': str(e)}