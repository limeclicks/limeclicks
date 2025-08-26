# Keyword Crawl Scheduling System

## Overview
The keyword crawl scheduling system implements intelligent, priority-based crawling with automatic 24-hour intervals, force crawl capabilities, and rate limiting.

## Key Features

### 1. **Priority-Based Crawling**
Keywords are assigned priorities that determine crawl order:
- **Critical** (4): Force-crawled keywords (highest priority)
- **High** (3): First-time keywords that have never been crawled
- **Normal** (2): Regular keywords with standard intervals
- **Low** (1): Keywords with low importance (rank > 50, no changes)

### 2. **Automatic 24-Hour Crawling**
- Keywords are automatically crawled every 24 hours by default
- Configurable per-keyword via `crawl_interval_hours` field
- Next crawl time is automatically scheduled after each successful crawl

### 3. **Force Crawl with Rate Limiting**
- Users can force an immediate crawl of any keyword
- Rate limited to once per hour per keyword
- Force crawls get "critical" priority for immediate processing
- Tracks force crawl count for analytics

## Database Schema Changes

### New Fields Added to Keyword Model

```python
# Scheduling fields
next_crawl_at = DateTimeField(db_index=True)          # Next scheduled crawl time
last_force_crawl_at = DateTimeField()                 # Last force crawl timestamp
crawl_priority = CharField(choices=PRIORITY_CHOICES)   # Crawl priority level
crawl_interval_hours = IntegerField(default=24)       # Hours between crawls
force_crawl_count = IntegerField(default=0)           # Number of force crawls

# New indexes for performance
Index(fields=['crawl_priority', 'next_crawl_at'])
Index(fields=['next_crawl_at', 'processing'])
```

## API Endpoints

### 1. Force Crawl Endpoint
```
POST /keywords/api/keyword/<keyword_id>/force-crawl/
```
**Response:**
```json
{
  "success": true,
  "message": "Force crawl initiated successfully",
  "data": {
    "keyword_id": 123,
    "keyword": "seo services",
    "crawl_priority": "critical",
    "force_crawl_count": 1
  }
}
```

### 2. Crawl Status Endpoint
```
GET /keywords/api/keyword/<keyword_id>/crawl-status/
```
**Response:**
```json
{
  "success": true,
  "data": {
    "keyword_id": 123,
    "keyword": "seo services",
    "crawl_priority": "normal",
    "processing": false,
    "scraped_at": "2024-01-15T10:30:00Z",
    "next_crawl_at": "2024-01-16T10:30:00Z",
    "can_force_crawl": true,
    "force_crawl_count": 0,
    "time_until_crawl": 86400,
    "time_until_force": 0,
    "crawl_interval_hours": 24,
    "should_crawl": false
  }
}
```

### 3. Crawl Queue Endpoint
```
GET /keywords/api/crawl-queue/
```
**Response:**
```json
{
  "success": true,
  "data": {
    "queue": [
      {
        "id": 123,
        "keyword": "seo services",
        "project": "example.com",
        "priority": "high",
        "processing": false,
        "next_crawl_at": "2024-01-15T10:30:00Z",
        "scraped_at": null
      }
    ],
    "total": 1
  }
}
```

## Celery Periodic Tasks

### 1. Schedule Keyword Crawls (Every 5 minutes)
```python
'schedule-keyword-crawls': {
    'task': 'keywords.schedule_keyword_crawls',
    'schedule': crontab(minute='*/5'),
    'kwargs': {'batch_size': 50}
}
```
Checks for keywords that need crawling and queues them based on priority.

### 2. Update Keyword Priorities (Daily at 1 AM)
```python
'update-keyword-priorities': {
    'task': 'keywords.update_keyword_priorities',
    'schedule': crontab(hour=1, minute=0)
}
```
Updates priorities based on:
- Never crawled → High priority
- Rank > 50 with no changes → Low priority
- Top 10 rankings → High priority

### 3. Reset Stuck Keywords (Every 30 minutes)
```python
'reset-stuck-keywords': {
    'task': 'keywords.reset_stuck_keywords',
    'schedule': crontab(minute='*/30'),
    'kwargs': {'stuck_hours': 2}
}
```
Resets keywords stuck in "processing" state for more than 2 hours.

## Usage Examples

### Python Code Examples

#### Check if Keyword Should Crawl
```python
keyword = Keyword.objects.get(id=123)

# Check if ready for crawl
if keyword.should_crawl():
    print("Keyword needs crawling")

# Check time until next crawl
time_until = keyword.next_crawl_at - timezone.now()
hours_until = time_until.total_seconds() / 3600
print(f"Next crawl in {hours_until:.1f} hours")
```

#### Force Crawl a Keyword
```python
keyword = Keyword.objects.get(id=123)

# Check if force crawl allowed
if keyword.can_force_crawl():
    try:
        keyword.force_crawl()
        print("Force crawl initiated")
    except ValueError as e:
        print(f"Cannot force crawl: {e}")
else:
    print("Must wait 1 hour between force crawls")
```

#### Schedule Keywords for Crawling
```python
from keywords.crawl_scheduler import CrawlScheduler

scheduler = CrawlScheduler()

# Get keywords ready for crawl
keywords = scheduler.get_keywords_to_crawl(limit=100)

# Schedule a specific keyword
keyword = Keyword.objects.get(id=123)
if scheduler.schedule_keyword_crawl(keyword):
    print("Keyword scheduled for crawling")
```

### JavaScript/AJAX Examples

#### Force Crawl via AJAX
```javascript
function forceCrawl(keywordId) {
    fetch(`/keywords/api/keyword/${keywordId}/force-crawl/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Force crawl initiated!');
        } else {
            alert(`Error: ${data.message}`);
        }
    });
}
```

#### Check Crawl Status
```javascript
function checkCrawlStatus(keywordId) {
    fetch(`/keywords/api/keyword/${keywordId}/crawl-status/`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const status = data.data;
                console.log(`Priority: ${status.crawl_priority}`);
                console.log(`Can force crawl: ${status.can_force_crawl}`);
                console.log(`Next crawl in: ${status.time_until_crawl} seconds`);
            }
        });
}
```

## Crawl Priority Logic

### Priority Assignment Rules

1. **First-Time Keywords (Never Crawled)**
   - Automatically assigned "high" priority
   - Ensures new keywords get ranked quickly

2. **Force Crawled Keywords**
   - Temporarily assigned "critical" priority
   - Resets to "normal" after successful crawl

3. **Top Rankings (Position 1-10)**
   - Can be set to "high" priority via periodic task
   - Ensures important rankings are monitored closely

4. **Low Impact Keywords (Position 50+)**
   - Can be set to "low" priority if no changes detected
   - Reduces unnecessary API calls

### Crawl Order
Keywords are processed in the following order:
1. Priority (Critical → High → Normal → Low)
2. Next crawl time (oldest first)
3. Last crawled time (oldest first)

## Performance Optimizations

### Database Indexes
- `(crawl_priority, next_crawl_at)` - Fast priority-based queries
- `(next_crawl_at, processing)` - Efficient crawl queue queries
- `crawl_priority` - Quick filtering by priority
- `next_crawl_at` - Fast scheduling queries

### Query Optimization
```python
# Efficient query for crawl candidates
keywords = Keyword.objects.filter(
    Q(scraped_at__isnull=True) |
    Q(next_crawl_at__lte=now)
).exclude(
    processing=True
).exclude(
    archive=True
).order_by(
    '-crawl_priority',
    'next_crawl_at'
)[:batch_size]
```

## Configuration

### Settings (in settings.py)
```python
# Keyword crawl settings
KEYWORD_CRAWL_INTERVAL_HOURS = 24  # Default interval
KEYWORD_FORCE_CRAWL_COOLDOWN = 60  # Minutes between force crawls
KEYWORD_CRAWL_BATCH_SIZE = 50      # Keywords per batch
```

### Customizing Per Keyword
```python
# Set custom interval for specific keyword
keyword.crawl_interval_hours = 12  # Crawl every 12 hours
keyword.save()

# Change priority manually
keyword.crawl_priority = 'high'
keyword.save()
```

## Monitoring and Debugging

### Check Crawl Queue Status
```python
from keywords.models import Keyword
from django.utils import timezone

# Keywords needing crawl
needs_crawl = Keyword.objects.filter(
    next_crawl_at__lte=timezone.now(),
    processing=False
).count()
print(f"Keywords ready for crawl: {needs_crawl}")

# Currently processing
processing = Keyword.objects.filter(processing=True).count()
print(f"Keywords being processed: {processing}")

# Force crawl usage
force_crawled = Keyword.objects.filter(
    force_crawl_count__gt=0
).count()
print(f"Keywords force crawled: {force_crawled}")
```

### Debug Specific Keyword
```python
keyword = Keyword.objects.get(id=123)

print(f"Keyword: {keyword.keyword}")
print(f"Priority: {keyword.crawl_priority}")
print(f"Should crawl: {keyword.should_crawl()}")
print(f"Can force crawl: {keyword.can_force_crawl()}")
print(f"Last crawled: {keyword.scraped_at}")
print(f"Next crawl: {keyword.next_crawl_at}")
print(f"Force count: {keyword.force_crawl_count}")
```

## Best Practices

1. **Don't Abuse Force Crawl**
   - Limited to once per hour for a reason
   - Excessive use may hit API rate limits

2. **Monitor High Priority Keywords**
   - Review keywords with "high" priority regularly
   - Adjust priorities based on business needs

3. **Clean Up Old Keywords**
   - Archive keywords no longer needed
   - Reduces unnecessary crawl queue processing

4. **Batch Processing**
   - Process keywords in batches to avoid overwhelming the system
   - Default batch size is 50 keywords

5. **Handle Failures Gracefully**
   - Failed crawls don't update next_crawl_at
   - Keywords remain in queue for retry

## Troubleshooting

### Keywords Not Being Crawled
1. Check if `processing` flag is stuck (run reset_stuck_keywords task)
2. Verify `next_crawl_at` is in the past
3. Ensure keyword is not archived
4. Check Celery workers are running

### Force Crawl Not Working
1. Verify 1-hour cooldown has passed
2. Check user permissions for the keyword
3. Ensure Celery queue is processing

### Priority Not Updating
1. Run `update_keyword_priorities` task manually
2. Check task scheduler is running
3. Verify priority update logic matches your needs

## Summary

The keyword crawl scheduling system provides:
- ✅ Automatic 24-hour crawling intervals
- ✅ High priority for first-time keywords
- ✅ Force crawl with 1-hour rate limiting
- ✅ Priority-based queue processing
- ✅ API endpoints for management
- ✅ Periodic task automation
- ✅ Performance optimized with indexes
- ✅ Comprehensive monitoring capabilities

This ensures efficient use of crawling resources while maintaining up-to-date ranking data for all tracked keywords.