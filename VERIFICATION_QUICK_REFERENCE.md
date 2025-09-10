# 🎯 DAILY SYSTEM - QUICK REFERENCE CARD

## 🚀 TOMORROW'S VERIFICATION CHECKLIST

### Step 1: Pre-Check (11:50 PM Tonight)
```bash
cd /home/muaaz/enterprise/limeclicks
python cleanup_and_prepare.py --dry-run
# If safe, run: python cleanup_and_prepare.py
```

### Step 2: Verify Daily Queue (12:02 AM)
```bash
python verify_daily_system.py --quick
```
✅ Look for: `Overall Status: ✅ PASS`

### Step 3: Monitor Progress (Throughout Day)
```bash
# Live dashboard (Ctrl+C to exit)
python monitoring_dashboard.py --refresh 30

# Quick status check
python monitoring_dashboard.py --quick
```

### Step 4: Test User Priority (Anytime After 12:01 AM)
```bash
python test_priority_system.py --auto
```
✅ Look for: `Overall Result: ✅ PASS`

## 📊 KEY METRICS TO WATCH

| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| Daily Queue | >95% | 90-95% | <90% |
| Processing Rate | >80% by 6 PM | 20-80% | <20% after 12h |
| Stuck Keywords | <50 | 50-100 | >100 |
| Celery Workers | 1+ active | - | 0 active |

## 🛠️ Emergency Fix Commands
```bash
# Reset stuck keywords
python cleanup_and_prepare.py --force

# Restart services  
sudo systemctl restart celery-worker celery-beat

# Manual queue trigger
python manage.py shell -c "from keywords.tasks import daily_queue_all_keywords; daily_queue_all_keywords.delay()"
```

## 📱 Script Purposes
- `verify_daily_system.py` = Health check & diagnostics
- `monitoring_dashboard.py` = Live monitoring (CLI interface)  
- `test_priority_system.py` = User priority testing
- `cleanup_and_prepare.py` = System cleanup & preparation

---
**Full Guide:** See `DAILY_SYSTEM_VERIFICATION_GUIDE.md`