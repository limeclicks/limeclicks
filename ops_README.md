# Operations README - SERP Fetching System

## Overview
This system fetches Google SERP HTML for keywords once every 24 hours using Scrape.do API and Celery workers with priority queues.

## Environment Configuration

Add to `.env` file:
```bash
# Already added
SCRAPPER_API_KEY=your_scrape_do_api_key
REDIS_URL=redis://localhost:6379/0

# New settings (optional, defaults shown)
SCRAPE_DO_STORAGE_ROOT=/path/to/storage/outside/repo  # Default: ./storage/scrape_do
SCRAPE_DO_TIMEOUT=60  # seconds
SCRAPE_DO_RETRIES=3   # for network/timeout only
SERP_HISTORY_DAYS=7   # keep last 7 days
FETCH_MIN_INTERVAL_HOURS=24  # minimum hours between fetches
```

## Storage Structure

HTML files are stored locally (outside Git) with the following structure:
```
storage/scrape_do/
├── {project_id}/
│   └── {keyword_id}/
│       ├── 2024-01-15.html  # Latest (position 1)
│       ├── 2024-01-14.html
│       ├── 2024-01-13.html
│       └── ...              # Up to 7 days
```

## Running Celery Workers

### Prerequisites
1. Redis server running: `redis-server`
2. Django migrations applied: `python manage.py migrate`

### Worker Commands

#### High Priority Queue (Cold Keywords)
For keywords with no initial rank or never scraped:
```bash
# Run 2 workers for high priority queue
celery -A limeclicks worker -Q serp_high -n worker_high_1 --concurrency=1 -l info &
celery -A limeclicks worker -Q serp_high -n worker_high_2 --concurrency=1 -l info &
```

#### Default Priority Queue (Regular Keywords)
For all other keywords:
```bash
# Run 4 workers for default queue
celery -A limeclicks worker -Q serp_default -n worker_default_1 --concurrency=1 -l info &
celery -A limeclicks worker -Q serp_default -n worker_default_2 --concurrency=1 -l info &
celery -A limeclicks worker -Q serp_default -n worker_default_3 --concurrency=1 -l info &
celery -A limeclicks worker -Q serp_default -n worker_default_4 --concurrency=1 -l info &
```

#### Combined Worker (Development)
For development, you can run a single worker handling both queues:
```bash
celery -A limeclicks worker -Q serp_high,serp_default,celery --concurrency=4 -l info
```

### Celery Beat Scheduler

Run the beat scheduler for periodic tasks:
```bash
celery -A limeclicks beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### All-in-One Development Command

Using `honcho` or separate terminals:
```bash
# Terminal 1: Redis
redis-server

# Terminal 2: Celery Worker
celery -A limeclicks worker -Q serp_high,serp_default,celery --concurrency=4 -l info

# Terminal 3: Celery Beat
celery -A limeclicks beat -l info

# Terminal 4: Django
python manage.py runserver
```

Or create a `Procfile.celery`:
```
redis: redis-server
worker_high: celery -A limeclicks worker -Q serp_high --concurrency=2 -l info
worker_default: celery -A limeclicks worker -Q serp_default --concurrency=4 -l info
beat: celery -A limeclicks beat -l info
```

Run with: `honcho -f Procfile.celery start`

## Queue Routing Logic

Keywords are routed to queues based on their "cold" status:

- **serp_high** (Priority 10): 
  - Keywords with `initial_rank = NULL` or `0`
  - Keywords with `scraped_at = NULL` (never scraped)
  - 2 dedicated worker processes

- **serp_default** (Priority 5):
  - All other keywords
  - 4 dedicated worker processes

## Task Execution

### Manual Task Execution
```python
# Django shell
from keywords.tasks import fetch_keyword_serp_html
from keywords.models import Keyword

# Fetch specific keyword
keyword = Keyword.objects.get(id=1)
fetch_keyword_serp_html.delay(keyword.id)

# Enqueue all eligible keywords
from keywords.tasks import enqueue_daily_keyword_scrapes
enqueue_daily_keyword_scrapes()
```

### Scheduled Execution
Configure in Django Admin under "Periodic Tasks":
1. Go to `/admin/django_celery_beat/periodictask/`
2. Create new periodic task:
   - Name: "Daily SERP Fetch"
   - Task: `keywords.tasks.enqueue_daily_keyword_scrapes`
   - Schedule: Crontab (0 2 * * *) - Daily at 2 AM
   - Enabled: ✓

## Monitoring

### Check Worker Status
```bash
celery -A limeclicks inspect active
celery -A limeclicks inspect stats
```

### View Queue Lengths
```bash
# Using Redis CLI
redis-cli
> LLEN celery
> LLEN serp_high
> LLEN serp_default
```

### Logs
- Worker logs: Check terminal output or redirect to files
- Task logs: Check Django logs for INFO/WARNING messages
- Success: `INFO: keyword_id=X, status=200, file=path`
- Failure: `WARNING: keyword_id=X, error=message`

## Database Fields Updated

### On Success
- `scraped_at` → current timestamp
- `scrape_do_file_path` → latest file path
- `scrape_do_files` → list with latest at index 0
- `success_api_hit_count` → incremented
- `last_error_message` → NULL

### On Failure
- `failed_api_hit_count` → incremented
- `last_error_message` → minimal error message
- File paths and `scraped_at` remain unchanged

## Testing

Run comprehensive tests:
```bash
# All tests
python manage.py test tests.test_serp_fetch

# Specific test classes
python manage.py test tests.test_serp_fetch.SERPFetchTestCase
python manage.py test tests.test_serp_fetch.CeleryIntegrationTest
```

## Troubleshooting

### Workers not picking up tasks
1. Check Redis is running: `redis-cli ping`
2. Check worker queues: `celery -A limeclicks inspect active_queues`
3. Verify queue names in worker command match configuration

### Files not being created
1. Check storage directory permissions
2. Verify `SCRAPE_DO_STORAGE_ROOT` exists and is writable
3. Check disk space

### Tasks failing with timeout
1. Increase `SCRAPE_DO_TIMEOUT` in settings
2. Check network connectivity to Scrape.do API
3. Review Scrape.do API quota/limits

### 24-hour rule violations
- Tasks check `scraped_at` timestamp
- Minimum interval: `FETCH_MIN_INTERVAL_HOURS` (default 24)
- Tasks skip if scraped too recently

## Important Notes

1. **No Rank Extraction**: This system only fetches and stores HTML. Rank extraction is NOT implemented.
2. **File Rotation**: Automatically maintains last 7 days of HTML files.
3. **Idempotency**: Same-day re-runs don't overwrite existing files.
4. **Error Messages**: Only minimal error messages stored (no stack traces).
5. **Retries**: Network/timeout errors retry up to 3 times. HTTP errors don't retry.
6. **Locking**: Uses Redis locks to prevent concurrent fetches of same keyword.