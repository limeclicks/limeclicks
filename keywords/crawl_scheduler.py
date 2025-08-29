"""
Keyword crawl scheduling and prioritization system
"""
import logging
from typing import List
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from celery import shared_task

from .models import Keyword
from .tasks import fetch_keyword_serp_html

logger = logging.getLogger(__name__)


class CrawlScheduler:
    """Handle keyword crawl scheduling with priority"""
    
    @staticmethod
    def get_keywords_to_crawl(limit: int = 100) -> List[Keyword]:
        """
        Get keywords that need crawling, ordered by priority
        
        Priority order:
        1. Critical (force crawled)
        2. High (first-time keywords)  
        3. Normal (regular scheduled)
        4. Low
        
        Within same priority, older next_crawl_at comes first
        """
        now = timezone.now()
        
        # Query for keywords that need crawling
        # Note: Can't use F() expressions with timedelta, so we use next_crawl_at instead
        keywords = Keyword.objects.filter(
            Q(scraped_at__isnull=True) |  # Never crawled
            Q(next_crawl_at__lte=now)     # Scheduled time passed
        ).exclude(
            processing=True  # Not already being processed
        ).exclude(
            archive=True  # Not archived
        ).order_by(
            '-crawl_priority',  # Priority first (critical > high > normal > low)
            'next_crawl_at',    # Then by scheduled time
            'scraped_at'        # Then by last crawl time
        )[:limit]
        
        return list(keywords)
    
    @staticmethod
    def schedule_keyword_crawl(keyword: Keyword) -> bool:
        """
        Schedule a keyword for crawling if eligible
        
        Returns:
            True if scheduled, False if not eligible
        """
        if keyword.processing:
            logger.info(f"Keyword {keyword.id} already processing")
            return False
        
        if not keyword.should_crawl():
            logger.info(f"Keyword {keyword.id} not ready for crawl")
            return False
        
        # Mark as processing
        keyword.processing = True
        keyword.save(update_fields=['processing'])
        
        # Queue the task
        fetch_keyword_serp_html.delay(keyword.id)
        logger.info(f"Scheduled crawl for keyword {keyword.id} with priority {keyword.crawl_priority}")
        
        return True
    
    @staticmethod
    def force_crawl_keyword(keyword: Keyword) -> bool:
        """
        Force crawl a keyword if allowed
        
        Returns:
            True if force crawled, False if not allowed
        """
        try:
            keyword.force_crawl()
            
            # Mark as processing
            keyword.processing = True
            keyword.save(update_fields=['processing'])
            
            # Queue with high priority
            fetch_keyword_serp_html.apply_async(
                args=[keyword.id],
                priority=9  # High priority in celery
            )
            
            logger.info(f"Force crawled keyword {keyword.id}")
            return True
            
        except ValueError as e:
            logger.warning(f"Force crawl not allowed for keyword {keyword.id}: {e}")
            return False


@shared_task(name='keywords.schedule_keyword_crawls')
def schedule_keyword_crawls(batch_size: int = 50) -> dict:
    """
    Periodic task to schedule keyword crawls based on priority
    
    This should run every few minutes to check for keywords that need crawling
    """
    scheduler = CrawlScheduler()
    keywords = scheduler.get_keywords_to_crawl(limit=batch_size)
    
    scheduled_count = 0
    skipped_count = 0
    
    for keyword in keywords:
        if scheduler.schedule_keyword_crawl(keyword):
            scheduled_count += 1
        else:
            skipped_count += 1
    
    logger.info(f"Crawl scheduling complete: {scheduled_count} scheduled, {skipped_count} skipped")
    
    return {
        'scheduled': scheduled_count,
        'skipped': skipped_count,
        'total_checked': len(keywords)
    }


@shared_task(name='keywords.update_keyword_priorities')
def update_keyword_priorities() -> dict:
    """
    Periodic task to update keyword priorities based on various factors
    
    This should run daily
    """
    updated_count = 0
    
    # Set high priority for keywords never crawled
    never_crawled = Keyword.objects.filter(
        scraped_at__isnull=True,
        crawl_priority='normal'
    ).update(crawl_priority='high')
    updated_count += never_crawled
    
    # Set low priority for keywords with rank > 50 that haven't changed much
    low_priority = Keyword.objects.filter(
        rank__gt=50,
        rank_status='no_change',
        crawl_priority='normal'
    ).update(crawl_priority='low')
    updated_count += low_priority
    
    # Set high priority for top 10 keywords
    high_priority = Keyword.objects.filter(
        rank__lte=10,
        rank__gt=0,
        crawl_priority='normal'
    ).update(crawl_priority='high')
    updated_count += high_priority
    
    logger.info(f"Updated priorities for {updated_count} keywords")
    
    return {
        'updated': updated_count,
        'never_crawled': never_crawled,
        'low_priority': low_priority,
        'high_priority': high_priority
    }


@shared_task(name='keywords.reset_stuck_keywords')
def reset_stuck_keywords(stuck_hours: int = 2) -> dict:
    """
    Reset keywords that have been stuck in processing state
    
    This handles cases where tasks fail without properly resetting the flag
    """
    cutoff = timezone.now() - timedelta(hours=stuck_hours)
    
    stuck_keywords = Keyword.objects.filter(
        processing=True,
        updated_at__lt=cutoff
    )
    
    count = stuck_keywords.count()
    stuck_keywords.update(processing=False)
    
    logger.warning(f"Reset {count} stuck keywords")
    
    return {'reset_count': count}