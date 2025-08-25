# Batch Processing and Queue Management Implementation

## Overview
Implemented batch processing system for SERP fetching with duplicate prevention, optimized queue routing, and automatic scheduling via Celery Beat.

## Key Changes Implemented

### 1. R2 Storage Path Format Change
**Old Format:** `{project_id}/{keyword_id}/YYYY-MM-DD.json`  
**New Format:** `{domain}/{keyword}/YYYY-MM-DD.json`

Example:
- Old: `123/456/2024-01-15.json`
- New: `example.com/python-tutorial/2024-01-15.json`

Benefits:
- More human-readable paths
- Easier to browse and manage files
- Domain-based organization

### 2. Batch Processing System

#### Batch Size
- **500 keywords per minute** maximum
- Prevents system overload
- Ensures fair distribution across projects

#### Processing Flag
- Added `processing` field to Keyword model
- Prevents duplicate queuing
- Reset automatically after task completion (success or failure)

#### Code Implementation
```python
@shared_task
def enqueue_keyword_scrapes_batch():
    """
    Runs every minute via Celery Beat
    Processes up to 500 eligible keywords
    """
    BATCH_SIZE = 500
    
    eligible_keywords = Keyword.objects.filter(
        Q(scraped_at__isnull=True) |  # Never scraped
        Q(scraped_at__lte=cutoff_time)  # Scraped > 24h ago
    ).filter(
        archive=False,
        project__active=True,
        processing=False  # Not already in queue
    )[:BATCH_SIZE]
    
    # Mark as processing to prevent duplicates
    Keyword.objects.filter(id__in=keyword_ids).update(processing=True)
```

### 3. Queue Routing Logic

#### Two Queue System
1. **serp_high** (Priority 10)
   - Only for keywords with `scraped_at=None` (never scraped)
   - Ensures new keywords get scraped quickly
   
2. **serp_default** (Priority 5)
   - For keywords previously scraped
   - Regular re-scraping after 24 hours

#### Previous Logic vs New Logic
**Before:**
- serp_high: Keywords with no initial_rank OR never scraped
- Could include keywords that were scraped but didn't rank

**After:**
- serp_high: ONLY keywords never scraped (scraped_at=None)
- More efficient resource allocation
- Clearer priority distinction

### 4. Celery Beat Schedule

Added to `settings.py`:
```python
CELERY_BEAT_SCHEDULE = {
    'enqueue-keyword-scrapes': {
        'task': 'keywords.tasks.enqueue_keyword_scrapes_batch',
        'schedule': 60.0,  # Every minute
    },
}
```

### 5. Management Command

Created `reset_processing_flags` command for maintenance:
```bash
# Reset all processing flags
python manage.py reset_processing_flags --all

# Reset only stuck keywords (processing > 1 hour)
python manage.py reset_processing_flags --stuck

# Show status
python manage.py reset_processing_flags
```

## Workflow

### Every Minute (via Celery Beat)
1. Query eligible keywords:
   - Never scraped (scraped_at=None) OR
   - Last scraped > 24 hours ago
   - Not archived
   - From active projects
   - Not already processing

2. Take up to 500 keywords

3. Mark them as `processing=True`

4. Queue to appropriate queue:
   - Never scraped → serp_high
   - Previously scraped → serp_default

### Per Keyword Processing
1. Task starts, checks 24-hour rule
2. If too recent, reset `processing=False` and exit
3. Fetch SERP HTML
4. On completion (success or failure):
   - Reset `processing=False`
   - Update scraped_at timestamp
   - Process ranking extraction

## Testing

### New Test Suite: `test_batch_processing.py`
- **8 test cases** covering:
  - Batch size limits (500 max)
  - Duplicate prevention
  - Queue routing logic
  - Processing flag management
  - Inactive project exclusion
  - Result structure validation

### Updated Tests
- `test_ranking_extraction.py` - Updated R2 path format
- `test_serp_fetch.py` - Updated queue routing tests

### Run Tests
```bash
# All batch processing tests
python manage.py test tests.test_batch_processing

# All SERP-related tests
python manage.py test tests.test_batch_processing tests.test_ranking_extraction tests.test_serp_fetch
```

## Deployment Instructions

### 1. Run Migrations
No new migrations needed (processing field already exists in Keyword model)

### 2. Start Celery Beat
```bash
# Start Celery Beat scheduler
celery -A limeclicks beat -l info

# Start Celery Workers
celery -A limeclicks worker -Q serp_high,serp_default,celery -l info
```

### 3. Monitor Processing
```bash
# Check processing status
python manage.py reset_processing_flags

# Watch logs
tail -f logs/celery.log | grep "Enqueued batch"
```

### 4. Initial Cleanup (if needed)
```bash
# Reset any stuck keywords from previous system
python manage.py reset_processing_flags --all
```

## Performance Metrics

### Throughput
- **500 keywords/minute** maximum
- **30,000 keywords/hour** theoretical maximum
- **720,000 keywords/day** theoretical maximum

### Actual Performance (depends on):
- Scrape.do API response time
- Number of Celery workers
- Network conditions
- HTML size and complexity

### Queue Distribution
- New keywords get priority (serp_high)
- Established keywords maintain 24-hour cycle (serp_default)
- No duplicate processing
- Automatic retry on network failures

## Monitoring Queries

### Django Shell Examples
```python
from keywords.models import Keyword
from django.utils import timezone
from datetime import timedelta

# Keywords currently processing
Keyword.objects.filter(processing=True).count()

# Keywords eligible for scraping
cutoff = timezone.now() - timedelta(hours=24)
Keyword.objects.filter(
    Q(scraped_at__isnull=True) | Q(scraped_at__lte=cutoff),
    archive=False,
    project__active=True,
    processing=False
).count()

# Keywords scraped in last hour
recent = timezone.now() - timedelta(hours=1)
Keyword.objects.filter(scraped_at__gte=recent).count()

# Failed keywords
Keyword.objects.filter(last_error_message__isnull=False).count()
```

## Benefits

1. **No Duplicate Processing**
   - Processing flag prevents re-queuing
   - Saves API calls and resources

2. **Efficient Resource Usage**
   - Only serp_high for truly new keywords
   - Better queue distribution

3. **Scalable Architecture**
   - Batch processing limits prevent overload
   - Can adjust BATCH_SIZE as needed

4. **Automatic Recovery**
   - Processing flags reset on completion
   - Management command for stuck keywords

5. **Clear Monitoring**
   - Easy to track processing status
   - Detailed logging at each step

## Configuration Options

Add to settings if needed:
```python
# Adjust batch size (default 500)
SERP_BATCH_SIZE = 500

# Adjust minimum interval (default 24 hours)
FETCH_MIN_INTERVAL_HOURS = 24

# Adjust Celery Beat schedule (default 60 seconds)
SERP_ENQUEUE_INTERVAL = 60
```

## Troubleshooting

### Keywords Not Being Processed
1. Check Celery Beat is running
2. Check workers are consuming from queues
3. Check for stuck processing flags: `python manage.py reset_processing_flags`
4. Check project is active
5. Check keyword not archived

### High Queue Buildup
1. Increase number of workers
2. Check Scrape.do API status
3. Monitor network connectivity
4. Check for errors in logs

### Processing Flag Stuck
```bash
# Reset specific keyword
from keywords.models import Keyword
Keyword.objects.filter(id=123).update(processing=False)

# Reset all stuck (> 1 hour)
python manage.py reset_processing_flags --stuck
```

## Summary

✅ Changed R2 storage path to `domain/keyword/date.json`  
✅ Implemented batch processing (500 keywords/minute)  
✅ Added duplicate prevention with processing flag  
✅ Set up Celery Beat to run every minute  
✅ Updated queue logic (serp_high only for never scraped)  
✅ Created management command for maintenance  
✅ Comprehensive test coverage (all passing)  

The system is now production-ready with efficient batch processing and duplicate prevention!