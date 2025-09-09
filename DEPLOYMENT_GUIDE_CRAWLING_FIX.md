# 🚨 CRITICAL: Keyword Crawling Fix Deployment Guide

## Overview
This guide provides step-by-step instructions to fix the keyword crawling issue where keywords get stuck with `processing=True` flag, preventing them from being re-crawled.

## Root Cause
- Keywords get stuck with `processing=True` when Celery tasks fail/timeout
- Cleanup task runs too infrequently (every 15 minutes)
- No proper error handling in fetch tasks
- Missing atomic transactions for flag management

---

## 📋 PRE-DEPLOYMENT CHECKLIST

- [ ] Backup database
- [ ] Note current stuck keyword count
- [ ] Check Celery worker status
- [ ] Verify Redis is running
- [ ] Have rollback plan ready

---

## 🚀 DEPLOYMENT STEPS

### Step 1: Immediate Recovery (5 minutes)

```bash
# SSH to production
ssh ubuntu@91.230.110.86
cd /home/ubuntu/new-limeclicks

# Copy recovery script
scp immediate_recovery.py ubuntu@91.230.110.86:/home/ubuntu/new-limeclicks/

# Check current status (dry run)
python immediate_recovery.py --status

# Apply immediate fixes
python immediate_recovery.py --apply

# Fix Project 7 specifically
python immediate_recovery.py --project 7 --apply
```

### Step 2: Deploy Enhanced Code (10 minutes)

```bash
# 1. Update keywords/tasks.py with enhanced version
cp keywords/tasks.py keywords/tasks_backup.py
cp keywords/tasks_enhanced.py keywords/tasks.py

# 2. Update celery.py with aggressive cleanup
cp limeclicks/celery.py limeclicks/celery_backup.py
cp celery_enhanced.py limeclicks/celery.py

# 3. Restart Celery workers
sudo systemctl restart limeclicks-celery
sudo systemctl restart limeclicks-celery-beat

# 4. Verify services are running
sudo systemctl status limeclicks-celery
sudo systemctl status limeclicks-celery-beat
```

### Step 3: Verify Immediate Impact (5 minutes)

```bash
# Run monitoring script
python monitor_crawling_health.py

# Check if keywords are being processed
python manage.py shell
```

```python
from keywords.models import Keyword
from django.utils import timezone
from datetime import timedelta

# Check stuck keywords
stuck = Keyword.objects.filter(processing=True).count()
print(f"Stuck keywords: {stuck}")

# Check recently crawled
recent = Keyword.objects.filter(
    scraped_at__gte=timezone.now() - timedelta(hours=1)
).count()
print(f"Crawled in last hour: {recent}")
```

### Step 4: Apply Permanent Fix to Code

Edit `/home/ubuntu/new-limeclicks/keywords/tasks.py`:

```python
# Add to fetch_keyword_serp_html task
finally:
    # ALWAYS reset processing flag
    if keyword:
        try:
            with transaction.atomic():
                keyword.refresh_from_db()
                keyword.processing = False
                keyword.save(update_fields=['processing', 'updated_at'])
        except:
            # Direct update as last resort
            Keyword.objects.filter(id=keyword_id).update(processing=False)
    
    # Always release lock
    cache.delete(lock_key)
```

Update cleanup task frequency in `/home/ubuntu/new-limeclicks/limeclicks/celery.py`:

```python
'cleanup-stuck-keywords-aggressive': {
    'task': 'keywords.tasks.cleanup_stuck_keywords',
    'schedule': crontab(minute='*/5'),  # Every 5 minutes (was 15)
    'options': {'queue': 'celery', 'priority': 9}
},
```

---

## 📊 MONITORING CHECKLIST (24 Hours)

### Hour 1: Initial Verification
- [ ] No keywords stuck for >1 hour
- [ ] Crawl velocity >50 keywords/hour
- [ ] Project 7 keywords updating
- [ ] No Celery task errors

### Hour 6: Stability Check
```bash
python monitor_crawling_health.py --report
```
- [ ] Health score >80
- [ ] <100 keywords overdue
- [ ] All projects showing activity
- [ ] Error rate <5%

### Hour 12: Performance Check
- [ ] Consistent crawl velocity
- [ ] No growing backlog
- [ ] Cleanup tasks running every 5 min
- [ ] Worker memory usage stable

### Hour 24: Full Verification
```bash
# Generate detailed report
python monitor_crawling_health.py --report

# Check Project 7 specifically
python diagnose_project7.py
```

- [ ] All keywords crawled within 24h
- [ ] Zero stuck keywords
- [ ] Health score >90
- [ ] Project 7 fully recovered

---

## 🔄 CONTINUOUS MONITORING

Set up automated monitoring:

```bash
# Start continuous monitoring (runs every 5 minutes)
nohup python monitor_crawling_health.py --watch --interval 300 > monitoring.log 2>&1 &

# Check monitoring log
tail -f monitoring.log

# Review health metrics
tail -n 100 crawling_health_log.jsonl | jq .
```

---

## ⚠️ ROLLBACK PLAN

If issues occur:

```bash
# 1. Restore original files
cp keywords/tasks_backup.py keywords/tasks.py
cp limeclicks/celery_backup.py limeclicks/celery.py

# 2. Restart services
sudo systemctl restart limeclicks-celery
sudo systemctl restart limeclicks-celery-beat

# 3. Run immediate recovery
python immediate_recovery.py --apply
```

---

## 📝 POST-DEPLOYMENT NOTES

### Success Criteria
- ✅ Zero keywords stuck >1 hour
- ✅ All keywords crawled within 24 hours
- ✅ Health score consistently >80
- ✅ Project 7 showing fresh data

### Known Issues Resolved
- ✅ Processing flags getting stuck
- ✅ Cleanup task too infrequent
- ✅ Missing error handling
- ✅ Race conditions in flag updates

### Future Improvements
1. Implement database-level locks instead of flags
2. Add Prometheus metrics for monitoring
3. Create automated alerting for stuck keywords
4. Implement circuit breaker for API failures

---

## 📞 ESCALATION

If critical issues persist:

1. Check Celery worker logs:
   ```bash
   sudo journalctl -u limeclicks-celery -n 100
   ```

2. Check Redis status:
   ```bash
   redis-cli ping
   redis-cli INFO
   ```

3. Reset everything:
   ```bash
   python immediate_recovery.py --apply
   sudo systemctl restart limeclicks-celery
   sudo systemctl restart limeclicks-celery-beat
   sudo systemctl restart redis
   ```

---

## ✅ SIGN-OFF

- [ ] Deployment completed successfully
- [ ] Monitoring shows healthy status
- [ ] Project 7 crawling normally
- [ ] Documentation updated
- [ ] Team notified of changes

**Deployed by:** _________________  
**Date/Time:** _________________  
**Health Score:** _________________  

---

## 📌 REMEMBER TO CHECK AFTER 24 HOURS!

Set a reminder to run:
```bash
python monitor_crawling_health.py --report
```

This will confirm the permanent fix is working correctly.