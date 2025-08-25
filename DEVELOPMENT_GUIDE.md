# LimeClicks Development Guide

## Quick Start Options

### 1. Basic Development (Django + CSS only)
```bash
honcho -f Procfile.dev.basic start
```
- Just Django and Tailwind CSS
- No background processing
- Good for frontend development

### 2. Full Development Environment
```bash
./start-dev.sh
# OR
honcho -f Procfile.dev start
```
- All services including Celery workers and Beat
- Email sending, SERP fetching, background tasks
- Full application functionality

### 3. SERP-Focused Development
```bash
./start-serp-dev.sh
# OR with stuck flag reset
./start-serp-dev.sh --reset
```
- Optimized for SERP fetching and ranking development
- Multiple specialized workers for better throughput
- Shows current processing status on startup
- Automatic keyword queuing every minute

## Service Breakdown

### Core Services
- **web**: Django development server (port 8000)
- **css**: Tailwind CSS watcher (auto-compiles on change)

### Background Processing
- **worker**: General Celery worker for all queues
- **beat**: Celery Beat scheduler (runs periodic tasks)
- **flower**: Celery monitoring dashboard (port 5555)

### SERP-Specific Workers (Procfile.dev.serp)
- **worker_high**: Handles high-priority queue (new keywords)
- **worker_default**: Handles default queue (re-scraping)
- **worker_general**: Handles other tasks (email, etc.)

## Celery Beat Schedule

The following tasks run automatically:

### Every Minute
- `enqueue_keyword_scrapes_batch`: Queues up to 500 eligible keywords for SERP fetching

### Every Hour
- `cleanup_expired_tokens`: Removes expired email verification tokens

## Queue System

### SERP Queues
1. **serp_high** (Priority 10)
   - For keywords never scraped (scraped_at=None)
   - Ensures new keywords get processed quickly

2. **serp_default** (Priority 5)
   - For keywords being re-scraped
   - Maintains 24-hour update cycle

### Other Queues
- **accounts**: User account related tasks
- **default**: General tasks
- **celery**: Default Celery queue

## Monitoring

### Django Admin
- http://localhost:8000/admin/
- Monitor keywords, projects, users

### Flower (Celery Monitor)
- http://localhost:5555
- Real-time task monitoring
- Worker status
- Queue statistics

### Command Line Monitoring
```bash
# Check keyword processing status
python manage.py reset_processing_flags

# Watch Celery logs
tail -f logs/celery*.log

# Monitor specific queue
celery -A limeclicks inspect active_queues

# Check scheduled tasks
celery -A limeclicks inspect scheduled
```

## Troubleshooting

### Keywords Not Being Processed
1. Check Celery Beat is running:
   ```bash
   ps aux | grep "celery.*beat"
   ```

2. Check workers are running:
   ```bash
   ps aux | grep "celery.*worker"
   ```

3. Reset stuck processing flags:
   ```bash
   python manage.py reset_processing_flags --stuck
   ```

4. Check Redis connection:
   ```bash
   redis-cli ping
   ```

### High Memory Usage
- Reduce worker concurrency in Procfile
- Use `--max-tasks-per-child=100` to restart workers periodically

### Debugging SERP Fetches
```python
# Django shell
python manage.py shell

from keywords.models import Keyword
from keywords.tasks import fetch_keyword_serp_html

# Test single keyword
k = Keyword.objects.filter(scraped_at__isnull=True).first()
if k:
    fetch_keyword_serp_html(k.id)
```

## Environment Variables

Required for SERP functionality:
```env
# Scrape.do API
SCRAPE_DO_API_KEY=your_api_key_here

# R2 Storage (for ranking JSON)
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key
R2_BUCKET_NAME=your_bucket_name
R2_ENDPOINT_URL=https://your-account-id.r2.cloudflarestorage.com

# Redis (for Celery)
REDIS_URL=redis://localhost:6379/0

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

## Performance Tuning

### Adjust Batch Size
In `keywords/tasks.py`:
```python
BATCH_SIZE = 500  # Adjust based on your needs
```

### Adjust Worker Concurrency
In Procfile:
```
worker: celery -A limeclicks worker --concurrency=8  # Increase for more throughput
```

### Adjust Fetch Interval
In settings.py:
```python
FETCH_MIN_INTERVAL_HOURS = 24  # Minimum hours between fetches
```

## Development Tips

1. **Test with small batches first**:
   ```python
   # Temporarily reduce batch size for testing
   BATCH_SIZE = 10
   ```

2. **Use Flower to monitor task execution**:
   - Watch task success/failure rates
   - Monitor queue lengths
   - Check worker utilization

3. **Enable debug logging**:
   ```python
   # In settings.py
   LOGGING['loggers']['keywords']['level'] = 'DEBUG'
   ```

4. **Test individual components**:
   ```bash
   # Test batch enqueue without processing
   python manage.py shell -c "from keywords.tasks import enqueue_keyword_scrapes_batch; print(enqueue_keyword_scrapes_batch())"
   ```

## Common Commands

```bash
# Start development
./start-dev.sh

# Start SERP development
./start-serp-dev.sh

# Reset all processing flags
python manage.py reset_processing_flags --all

# Check processing status
python manage.py reset_processing_flags

# Run tests
python manage.py test tests.test_batch_processing

# Create superuser
python manage.py createsuperuser

# Make migrations
python manage.py makemigrations
python manage.py migrate
```

## Production Deployment

For production, use:
- Gunicorn/uWSGI instead of Django dev server
- Supervisor/systemd for process management
- Separate Celery workers on different machines
- Redis Sentinel for high availability
- PostgreSQL connection pooling

See `DEPLOYMENT.md` for full production setup.