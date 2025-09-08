# Database Connection Management Guide

## Problem Prevention

The application experienced "too many clients" PostgreSQL errors due to connection exhaustion. This guide explains how to prevent and manage this issue.

## Current Solutions Implemented

### 1. Task-Level Connection Management
- **Location**: `keywords/tasks.py`
- Each task now properly closes database connections in a `finally` block
- Uses `select_for_update(skip_locked=True)` to prevent race conditions
- Automatically resets stuck keywords (processing > 10 minutes)

### 2. Celery Worker Configuration
- **Location**: `limeclicks/settings.py`
- `CELERY_WORKER_MAX_TASKS_PER_CHILD = 100`: Workers restart after 100 tasks
- `CELERY_WORKER_PREFETCH_MULTIPLIER = 1`: Prevents task hoarding
- `CELERY_BROKER_POOL_LIMIT = 10`: Limits Redis connections

### 3. Schedule Optimization
- Changed keyword fetch job from every minute to every 5 minutes
- Reduces database connection frequency by 80%

## Monitoring Commands

### Check Database Connections
```bash
python manage.py monitor_db_connections --check
```

### Kill Idle Connections
```bash
python manage.py monitor_db_connections --kill-idle
```

### Reset Stuck Keywords
```bash
python manage.py monitor_db_connections --reset-stuck
python manage.py reset_processing_flags --stuck
```

## Production Deployment Recommendations

### 1. Use PgBouncer (Connection Pooler)
```bash
# Install PgBouncer
sudo apt-get install pgbouncer

# Copy configuration
sudo cp deployment/pgbouncer.ini /etc/pgbouncer/

# Update Django settings to connect through PgBouncer
DATABASE_URL=postgresql://user:pass@localhost:6432/limeclicks

# Start PgBouncer
sudo systemctl start pgbouncer
sudo systemctl enable pgbouncer
```

### 2. Update Celery Worker Service
```bash
# Update the systemd service file with optimized settings
sudo nano /etc/systemd/system/limeclicks-celery.service

# Add these arguments to ExecStart:
ExecStart=/path/to/celery -A limeclicks worker \
    --max-tasks-per-child=100 \
    --prefetch-multiplier=1 \
    --concurrency=4 \
    --pool=prefork
```

### 3. Set Up Monitoring Cron Job
```bash
# Add to crontab (runs every 30 minutes)
*/30 * * * * /path/to/python /path/to/manage.py monitor_db_connections --kill-idle

# Daily cleanup of stuck keywords
0 2 * * * /path/to/python /path/to/manage.py monitor_db_connections --reset-stuck
```

## PostgreSQL Tuning

Add to `postgresql.conf`:
```
max_connections = 200
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB

# Connection pooling settings
idle_in_transaction_session_timeout = 300000  # 5 minutes
statement_timeout = 300000  # 5 minutes
```

## Monitoring Queries

### Check Current Connections
```sql
SELECT count(*) as total,
       sum(case when state = 'active' then 1 else 0 end) as active,
       sum(case when state = 'idle' then 1 else 0 end) as idle
FROM pg_stat_activity
WHERE datname = 'limeclicks';
```

### Find Long-Running Queries
```sql
SELECT pid, now() - query_start as duration, state, query
FROM pg_stat_activity
WHERE datname = 'limeclicks'
  AND state != 'idle'
  AND now() - query_start > interval '1 minute'
ORDER BY duration DESC;
```

### Kill Specific Connection
```sql
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE pid = <PID>;
```

## Emergency Recovery

If the database is completely blocked:

1. **Stop all services**:
```bash
sudo systemctl stop limeclicks-celery
sudo systemctl stop limeclicks-celerybeat
sudo systemctl stop limeclicks-gunicorn
```

2. **Kill all database connections**:
```sql
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'limeclicks' AND pid <> pg_backend_pid();
```

3. **Reset all keywords**:
```bash
python manage.py reset_processing_flags --all
```

4. **Restart services with connection limits**:
```bash
sudo systemctl start limeclicks-gunicorn
sudo systemctl start limeclicks-celery
sudo systemctl start limeclicks-celerybeat
```

## Prevention Checklist

- [ ] Database connection pooling enabled (conn_max_age=600)
- [ ] Celery workers configured with max-tasks-per-child
- [ ] PgBouncer installed for production (optional but recommended)
- [ ] Monitoring cron jobs set up
- [ ] PostgreSQL max_connections increased if needed
- [ ] Regular monitoring of connection usage
- [ ] Stuck keyword cleanup automated

## Alerts Setup

Consider setting up alerts when:
- Database connections exceed 80% of max_connections
- Keywords remain in processing state > 30 minutes
- Celery queue backlogs exceed 1000 tasks

## Contact

If issues persist, check:
1. Application logs: `/var/log/celery/worker.log`
2. PostgreSQL logs: `/var/log/postgresql/`
3. System resources: `htop`, `df -h`, `free -m`