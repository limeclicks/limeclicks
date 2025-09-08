# PostgreSQL Connection Exhaustion Fixes - Deployment Guide

## Changes Made to Prevent Server Crashes

### 1. SSE Endpoints Fixed (Permanent Solution)
**Files Modified:**
- `/keywords/views.py` - `keyword_updates_sse()` function
- `/site_audit/views.py` - `audit_status_stream()` function

**Changes:**
- Added `connection.close()` after each database query iteration
- Limited SSE streams to 1 hour maximum (auto-reconnect after)
- Added error handling and connection cleanup
- Added keepalive messages every 20-30 seconds
- Connections now properly released every 2-3 seconds instead of being held forever

### 2. Django Database Settings
**File:** `/limeclicks/settings.py`

**Changed from:**
```python
conn_max_age=600  # 10 minutes
```

**Changed to:**
```python
conn_max_age=0  # Close immediately
conn_health_checks=True  # Enable health checks
autocommit=True  # Ensure autocommit
```

### 3. Gunicorn Configuration
**File:** `/gunicorn_config_production.py`

**Changed from:**
- `worker_class = "gevent"` (async workers)
- `workers = 9`
- `worker_connections = 1000`

**Changed to:**
- `worker_class = "sync"` (synchronous workers)
- `workers = 6` (reduced)
- Removed worker_connections (not applicable to sync)
- `max_requests = 500` (restart workers more frequently)

### 4. Celery Tasks Connection Management
**Files Modified:**
- `/backlinks/tasks.py` - All `@shared_task` functions
- `/keywords/tasks.py` - Already had connection.close()

**Added:**
- `finally` blocks with `connection.close()`
- Connection cleanup in exception handlers

### 5. Database Connection Monitor
**New File:** `/scripts/monitor_db_connections.py`

**Features:**
- Monitors connection count every 30 seconds
- Logs warnings at 100 connections, critical at 150
- Auto-closes idle connections > 5 minutes when critical
- Writes metrics to `/logs/db_metrics.json`

## Deployment Instructions

### Step 1: Deploy Code Changes
```bash
cd /home/ubuntu/new-limeclicks
git pull origin main
```

### Step 2: Restart Services
```bash
# Restart Gunicorn with new configuration
sudo systemctl restart limeclicks-gunicorn

# Restart Celery workers to apply connection management
sudo systemctl restart limeclicks-celery
sudo systemctl restart limeclicks-celerybeat
```

### Step 3: Start Connection Monitor (Optional but Recommended)
```bash
# Run in background with nohup
cd /home/ubuntu/new-limeclicks
nohup python scripts/monitor_db_connections.py --interval 30 --auto-close > /dev/null 2>&1 &

# Or create a systemd service for permanent monitoring
```

### Step 4: Verify Fixes
```bash
# Check current connections
python scripts/monitor_db_connections.py --once

# Monitor connections in real-time
watch -n 5 "psql -U postgres -h localhost -c 'SELECT count(*), state FROM pg_stat_activity GROUP BY state'"

# Check service status
sudo systemctl status limeclicks-gunicorn
sudo systemctl status limeclicks-celery
```

## How These Fixes Prevent Crashes

1. **SSE connections no longer accumulate** - Each iteration closes its connection
2. **Sync workers prevent multiplication** - Each worker uses 1 connection at a time
3. **conn_max_age=0** - No persistent idle connections
4. **Celery cleanup** - Tasks always close connections after completion
5. **1-hour SSE timeout** - Prevents infinite connection holding
6. **Monitoring** - Early warning and auto-cleanup of problematic connections

## Expected Results

**Before Fixes:**
- 200+ connections with 50-100 users
- Server crashes with "too many clients"
- Idle connections accumulating

**After Fixes:**
- < 50 connections with 100+ users
- No connection exhaustion
- Automatic cleanup of idle connections
- SSE still works but doesn't leak connections

## Monitoring Commands

```bash
# Check connection count
psql -U postgres -h localhost -c "SELECT count(*) FROM pg_stat_activity"

# View connections by state
psql -U postgres -h localhost -c "SELECT state, count(*) FROM pg_stat_activity GROUP BY state"

# Find long idle connections
psql -U postgres -h localhost -c "SELECT pid, state, now()-state_change as idle_time FROM pg_stat_activity WHERE state='idle' ORDER BY idle_time DESC LIMIT 10"

# Kill all idle connections (emergency)
psql -U postgres -h localhost -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state='idle'"
```

## Rollback Plan

If issues occur after deployment:

1. **Revert Gunicorn to gevent** (if performance issues):
   - Edit `/gunicorn_config_production.py`
   - Change `worker_class = "sync"` back to `"gevent"`
   - Reduce workers to 4
   - Restart: `sudo systemctl restart limeclicks-gunicorn`

2. **Increase conn_max_age** (if too many connection opens/closes):
   - Edit `/limeclicks/settings.py`
   - Change `conn_max_age=0` to `conn_max_age=30`
   - Restart services

## Notes

- SSE functionality preserved but with connection management
- Performance impact minimal due to connection pooling at Django level
- Monitor for 24-48 hours after deployment
- Consider adding PgBouncer later for even better connection pooling