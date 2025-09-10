# 🚀 DAILY KEYWORD SYSTEM - VERIFICATION GUIDE

This guide provides step-by-step instructions for verifying that the new daily keyword scheduling system is working correctly. Use this checklist after 12:01 AM to ensure all components are functioning properly.

## 📋 QUICK VERIFICATION CHECKLIST

Run these commands in order and check the results:

### 1. ✅ System Health Check (5 minutes)
```bash
python verify_daily_system.py --quick
```
**Expected Result:** Overall Status should be `PASS` or `WARN`
- ✅ PASS = Everything working perfectly
- ⚠️ WARN = Minor issues, monitor closely  
- ❌ FAIL = Critical issues, immediate attention needed

### 2. 🧹 One-Time System Cleanup (First run only)
```bash
# IMPORTANT: Only run this ONCE before first daily queue
python cleanup_and_prepare.py --dry-run
# Review the output, then run for real:
python cleanup_and_prepare.py
```

### 3. 📊 Real-Time Monitoring
```bash
python monitoring_dashboard.py --refresh 30
```
Press Ctrl+C to exit when done monitoring.

---

## 🔍 DETAILED VERIFICATION PROCESS

### Phase 1: Pre-Verification Setup

**Time to Run:** Before 12:01 AM (ideally around 11:50 PM)

1. **Check Current System State**
   ```bash
   python verify_daily_system.py --detailed --json > pre_verification_$(date +%Y%m%d).json
   ```

2. **Clean Up Existing Issues** (First time only)
   ```bash
   python cleanup_and_prepare.py --dry-run
   # Review output, then:
   python cleanup_and_prepare.py
   ```

### Phase 2: Daily Queue Verification

**Time to Run:** 12:02 AM - 12:10 AM (right after daily queue)

1. **Verify Daily Queue Executed**
   ```bash
   python verify_daily_system.py --quick
   ```
   
   **Look for:**
   - `Daily Queue: PASS - X/Y keywords queued (>95%)`
   - `Processing: PASS` or `WARN`
   - `Celery: PASS - N workers, M active tasks`

2. **Detailed System Analysis**
   ```bash
   python verify_daily_system.py --detailed
   ```
   
   **Check Project Breakdown:**
   - All major projects should show some activity
   - No projects should have 0% completion rate after 2+ hours

### Phase 3: Processing Monitoring  

**Time to Run:** Throughout the day (hourly checks recommended)

1. **Live Monitoring Dashboard**
   ```bash
   python monitoring_dashboard.py --refresh 30
   ```
   
   **Monitor These Metrics:**
   - **System Overview:** Processing rate should be >80% by end of day
   - **Hourly Breakdown:** Should see steady processing throughout day
   - **Project Breakdown:** All projects making progress
   - **Celery Status:** Workers active and processing tasks

2. **Quick Status Checks**
   ```bash
   python monitoring_dashboard.py --quick
   ```

### Phase 4: User Priority System Test

**Time to Run:** After daily queue has started (anytime after 12:01 AM)

1. **Test User Recheck Priority**
   ```bash
   python test_priority_system.py --auto
   ```
   
   **Expected Results:**
   - ✅ Priority Queueing: PASS - Task queued successfully
   - ✅ Processing Speed: PASS - Completed in <3 minutes
   - ✅ Overall Result: PASS

---

## 📊 INTERPRETING RESULTS

### System Status Meanings

| Status | Meaning | Action Required |
|--------|---------|----------------|
| ✅ PASS | Everything working correctly | Continue normal monitoring |
| ⚠️ WARN | Minor issues detected | Monitor closely, may self-resolve |
| ❌ FAIL | Critical problems | Immediate investigation needed |

### Key Metrics to Watch

**Daily Queue Health:**
- **Target:** >95% of keywords queued at 12:01 AM
- **Warning:** <90% queued may indicate Celery issues
- **Critical:** <80% queued requires immediate attention

**Processing Speed:**
- **Healthy:** >80% completion by 6 PM same day
- **Warning:** 20-80% completion (may finish by midnight)
- **Critical:** <20% completion after 12 hours

**Stuck Keywords:**
- **Good:** <50 stuck keywords at any time
- **Warning:** 50-100 stuck keywords
- **Critical:** >100 stuck keywords

### Celery Worker Health
- **Minimum:** 1 worker active at all times
- **Recommended:** 2-4 workers for optimal performance
- **Active Tasks:** Should see consistent task activity during processing hours

---

## 🛠️ TROUBLESHOOTING COMMON ISSUES

### Issue: Daily Queue Shows <95% Completion

**Diagnosis:**
```bash
python verify_daily_system.py --detailed | grep -A5 "Daily Queue"
```

**Common Causes:**
1. Celery Beat not running: `systemctl status celery-beat`
2. No workers available: `celery -A limeclicks inspect stats`
3. Database connection issues: Check Django logs

**Fix:**
1. Restart Celery Beat: `systemctl restart celery-beat`
2. Start workers: `systemctl restart celery-worker`
3. Manual queue trigger: `python manage.py shell -c "from keywords.tasks import daily_queue_all_keywords; daily_queue_all_keywords.delay()"`

### Issue: High Number of Stuck Keywords (>100)

**Diagnosis:**
```bash
python cleanup_and_prepare.py --dry-run | grep -A10 "STUCK KEYWORDS"
```

**Fix:**
```bash
python cleanup_and_prepare.py --force
```

### Issue: User Priority System Not Working

**Diagnosis:**
```bash
python test_priority_system.py --auto
```

**Common Causes:**
1. Missing high-priority task definition
2. Queue routing issues
3. Worker not processing high-priority queue

**Fix:**
1. Check task import: `python manage.py shell -c "from keywords.tasks import user_recheck_keyword_rank; print('OK')"`
2. Restart workers with priority queues enabled

### Issue: No Processing Activity After Several Hours

**Diagnosis:**
```bash
python monitoring_dashboard.py --quick
celery -A limeclicks inspect active
```

**Common Causes:**
1. All workers crashed or stopped
2. Redis connection issues
3. Database locks

**Fix:**
1. Restart all Celery services: `systemctl restart celery-worker celery-beat`
2. Check Redis: `redis-cli ping`
3. Check database connections: `python manage.py dbshell`

---

## 📅 DAILY MONITORING SCHEDULE

### 🌙 Midnight (12:01-12:10 AM)
- Run `python verify_daily_system.py --quick`
- Verify daily queue executed successfully
- Check that processing has begun

### 🌅 Morning (8:00-9:00 AM)  
- Run `python monitoring_dashboard.py --quick`
- Check overnight processing progress (should be >30%)
- Review any stuck keywords

### 🌞 Midday (12:00-1:00 PM)
- Quick status check: ~50-70% completion expected
- Monitor Celery worker health

### 🌆 Evening (6:00-7:00 PM)
- Run `python verify_daily_system.py --detailed`
- Should see >80% completion
- Prepare end-of-day report

### 🌃 Night (11:00-11:30 PM)
- Final status check before next daily queue
- Run cleanup if needed: `python cleanup_and_prepare.py --dry-run`

---

## 📁 LOG FILES AND MONITORING

### Important Log Locations
- **Celery Worker Logs:** `/var/log/celery/worker.log`
- **Celery Beat Logs:** `/var/log/celery/beat.log`
- **Django Application Logs:** Check Django settings for log location
- **Verification Reports:** Files created by verification scripts

### Automated Monitoring Setup
```bash
# Add to crontab for automated daily checks
# Check system health every 6 hours
0 */6 * * * cd /home/muaaz/enterprise/limeclicks && python verify_daily_system.py --json >> /var/log/keyword_verification.log 2>&1

# Daily cleanup check at 11 PM
0 23 * * * cd /home/muaaz/enterprise/limeclicks && python cleanup_and_prepare.py --dry-run >> /var/log/daily_cleanup_check.log 2>&1
```

---

## 🚨 EMERGENCY PROCEDURES

### Complete System Reset (Use Only If Necessary)
```bash
# 1. Stop all processing
systemctl stop celery-worker celery-beat

# 2. Reset all stuck keywords
python cleanup_and_prepare.py --reset-all

# 3. Clear Redis queues
redis-cli FLUSHALL

# 4. Restart services
systemctl start celery-beat
systemctl start celery-worker

# 5. Manual trigger daily queue
python manage.py shell -c "from keywords.tasks import daily_queue_all_keywords; daily_queue_all_keywords.delay()"

# 6. Verify recovery
python verify_daily_system.py --detailed
```

### Contact Information
- **System Administrator:** [Add contact details]
- **Emergency Escalation:** [Add emergency contact]
- **Documentation Location:** This file + scripts in `/home/muaaz/enterprise/limeclicks/`

---

## ✅ SUCCESS CRITERIA

Your daily keyword system is working correctly when:

1. ✅ **Daily Queue:** >95% of keywords queued at 12:01 AM
2. ✅ **Processing Rate:** >80% keywords processed by end of day  
3. ✅ **Stuck Keywords:** <50 stuck at any given time
4. ✅ **Celery Health:** At least 1 worker active continuously
5. ✅ **User Priority:** New keyword requests processed within 5 minutes
6. ✅ **Zero Manual Intervention:** System runs without manual fixes

When all criteria are met consistently for 3+ days, the system is considered stable and production-ready.

---

## 📚 SCRIPT REFERENCE

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `verify_daily_system.py` | Comprehensive system verification | Daily health checks |
| `monitoring_dashboard.py` | Real-time system monitoring | Live status monitoring |
| `test_priority_system.py` | Test user priority features | Verify user recheck works |
| `cleanup_and_prepare.py` | System cleanup and preparation | Before first run or when issues arise |

---

*Last Updated: $(date)*
*System Version: Daily Keyword Scheduling v2.0*