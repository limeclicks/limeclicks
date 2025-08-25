# Lighthouse Audit System Documentation

## Overview
A comprehensive Lighthouse audit system has been implemented for the LimeClicks project. This system automatically runs performance, accessibility, SEO, and best practices audits on project websites.

## Features Implemented

### 1. **Automatic Audit Triggering**
- ✅ Audits are triggered automatically when a new project is created
- ✅ Both desktop and mobile audits are run for comprehensive coverage

### 2. **Scheduled Audits**
- ✅ Audits run every 30 days automatically (configurable per project)
- ✅ Celery Beat integration for periodic task scheduling
- ✅ Prevents duplicate scheduled audits

### 3. **Manual Audits**
- ✅ Users can trigger manual audits via admin interface
- ✅ Rate limiting: One manual audit per day per project
- ✅ Clear feedback on rate limit status

### 4. **Audit Data Storage**
- ✅ Full Lighthouse JSON reports stored in Cloudflare R2
- ✅ HTML reports for visual inspection
- ✅ Summary scores stored in database for quick access
- ✅ Performance metrics (FCP, LCP, TTI, Speed Index, TBT, CLS)

### 5. **Admin Interface**
- ✅ Comprehensive Django Admin interface
- ✅ Visual score badges with color coding:
  - Green (90+): Excellent
  - Yellow (50-89): Needs improvement
  - Red (<50): Poor
- ✅ Audit history with comparisons
- ✅ Direct links to view JSON/HTML reports
- ✅ Manual audit triggers from admin

## Models

### AuditPage
- One-to-one relationship with Project
- Stores latest audit summary
- Manages audit settings (frequency, enabled status)
- Rate limiting for manual audits

### AuditHistory
- Complete audit history for each page
- Stores all Lighthouse scores and metrics
- Links to R2-stored reports
- Tracks trigger type (scheduled/manual/project_created)
- Device type (desktop/mobile)

### AuditSchedule
- Prevents duplicate scheduled audits
- Tracks processing status

## Celery Tasks

1. **run_lighthouse_audit**: Core audit execution
2. **create_audit_for_project**: Triggered on project creation
3. **run_manual_audit**: Manual audits with rate limiting
4. **check_scheduled_audits**: Hourly check for due audits
5. **cleanup_old_audits**: Daily cleanup of old records
6. **generate_audit_report**: Comprehensive reporting

## Configuration

### Settings Required
```python
# Cloudflare R2 Configuration
CLOUDFLARE_R2_ACCESS_KEY_ID = 'your-access-key'
CLOUDFLARE_R2_SECRET_ACCESS_KEY = 'your-secret-key'
CLOUDFLARE_R2_BUCKET_NAME = 'your-bucket-name'
CLOUDFLARE_R2_ENDPOINT_URL = 'https://your-account.r2.cloudflarestorage.com'
CLOUDFLARE_R2_CUSTOM_DOMAIN = 'optional-custom-domain'
```

### Celery Beat Schedule
```python
# Runs every hour
'check-scheduled-audits': {
    'task': 'audits.tasks.check_scheduled_audits',
    'schedule': crontab(minute=0),
}

# Runs daily at 2 AM
'cleanup-old-audits': {
    'task': 'audits.tasks.cleanup_old_audits',
    'schedule': crontab(hour=2, minute=0),
    'kwargs': {'days_to_keep': 90}
}
```

## Usage

### Via Django Admin
1. Navigate to **Audits → Audit Pages**
2. View scores, history, and settings
3. Click "Run Manual" to trigger immediate audit
4. Click "View History" to see all past audits

### Via Management Command
```bash
# Test audit functionality
python manage.py test_audit --url https://example.com --device desktop

# With project association
python manage.py test_audit --url https://example.com --device mobile --project-id 1
```

### Via API (if views are enabled)
```python
# Trigger manual audit
POST /audits/project/{project_id}/audits/trigger/

# View dashboard
GET /audits/project/{project_id}/audits/
```

## Testing

Run the comprehensive test suite:
```bash
python test_audit_system.py
```

Test coverage:
- ✅ Lighthouse installation verification
- ✅ Direct audit execution
- ✅ Project creation triggers
- ✅ Manual audit with rate limiting
- ✅ Scheduled audit system
- ✅ Report generation
- ✅ Admin interface registration

## Performance Considerations

1. **Audit Execution**: Runs in background via Celery
2. **Storage**: R2 for large JSON/HTML files, database for summaries
3. **Rate Limiting**: Prevents abuse of manual audits
4. **Cleanup**: Automatic removal of old audits after 90 days

## Monitoring

Monitor audit system via:
1. Django Admin audit history
2. Celery task monitoring
3. R2 storage usage
4. Database audit_history table

## Troubleshooting

### Lighthouse Not Found
```bash
npm install -g lighthouse
```

### Audits Failing
Check:
1. Chrome/Chromium is installed
2. Sufficient memory available
3. Network connectivity to target sites
4. R2 credentials are valid

### Manual Audit Rate Limited
Wait 24 hours or adjust `last_manual_audit` in database

## Future Enhancements

Potential improvements:
1. Email notifications for score drops
2. Webhook integrations
3. Custom audit presets
4. Bulk audit operations
5. Score trend visualizations
6. Competitive analysis features

## Dependencies

- **lighthouse**: NPM package for audits
- **boto3**: AWS SDK for R2 storage
- **django-storages**: Storage backend abstraction
- **celery**: Async task processing
- **django-celery-beat**: Periodic task scheduling

## Security Notes

- R2 credentials stored in environment variables
- No public access to audit reports by default
- Rate limiting prevents DoS via manual audits
- User ownership verified for all operations