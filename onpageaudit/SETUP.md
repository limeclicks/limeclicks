# OnPageAudit Setup Guide

## Overview
OnPageAudit is a comprehensive on-page SEO auditing system using Screaming Frog SEO Spider. It provides automated audits with rate limiting, license management, and detailed issue tracking.

## Features
- **Automatic Audits**: Run every 30 days when projects are created
- **Manual Audits**: Rate-limited to once every 3 days per project
- **License Management**: Automatic validation and expiry tracking
- **Issue Detection**: 
  - Broken links (404s, 500s)
  - Missing/duplicate titles
  - Missing/duplicate meta descriptions
  - Redirect chains
  - Robots.txt blocking
  - Hreflang issues
  - Spelling errors
- **R2 Storage**: Full reports stored in Cloudflare R2
- **History Tracking**: Compare audits to track fixed/new issues

## Installation

### 1. Install Screaming Frog SEO Spider

#### Linux (Ubuntu/Debian):
```bash
sudo bash scripts/install_screaming_frog.sh
```

#### macOS:
Download from: https://www.screamingfrog.co.uk/seo-spider/

#### Windows:
Download installer from: https://www.screamingfrog.co.uk/seo-spider/

### 2. Set Environment Variable
Add to your `.env` file:
```env
SCREAMING_FROG_LICENSE=your-license-key-here
```

### 3. Run Migrations
```bash
python manage.py migrate onpageaudit
```

### 4. Validate License
```bash
python manage.py test_screaming_frog --validate-license
```

## Usage

### Management Commands

#### Test Screaming Frog Installation
```bash
# Validate license only
python manage.py test_screaming_frog --validate-license

# Test crawl
python manage.py test_screaming_frog --test-crawl --url https://example.com --max-pages 10
```

#### Run Manual Audit
```bash
# Run asynchronously (via Celery)
python manage.py run_onpage_audit example.com --manual

# Run synchronously (for testing)
python manage.py run_onpage_audit example.com --sync

# Force audit (bypass rate limiting - admin only)
python manage.py run_onpage_audit example.com --force
```

### Celery Tasks

The following tasks run automatically:

1. **check_scheduled_onpage_audits**: Runs every 6 hours to check for scheduled audits
2. **cleanup_old_onpage_audits**: Runs daily at 3 AM to clean audits older than 90 days
3. **validate_screaming_frog_license**: Runs weekly to validate license status

### Django Admin

Access the OnPageAudit admin at: `/admin/onpageaudit/`

Features:
- **License Status**: View current license status in the dashboard
- **Audit History**: Browse all audit runs with issue summaries
- **Issue Details**: Filter and search specific issues
- **Comparison View**: See fixed vs new issues between audits

## Rate Limiting

- **Automatic Audits**: Maximum once every 30 days per project
- **Manual Audits**: Maximum once every 3 days per project
- **Scheduled Audits**: Follow the 30-day automatic limit

## R2 Storage

Reports are stored in Cloudflare R2:
- **Full Report**: `{domain}_{audit_id}_full.json`
- **Issues Report**: `{domain}_{audit_id}_issues.json`
- **CSV Report**: `{domain}_{audit_id}_crawl.csv` (if generated)

## Troubleshooting

### License Issues
- Check license key in `.env` file
- Run validation: `python manage.py test_screaming_frog --validate-license`
- License status shown in Django admin dashboard

### Crawl Failures
- Ensure Screaming Frog is installed: `which screamingfrogseospider`
- Check available memory (Screaming Frog requires significant RAM for large sites)
- Review logs: `tail -f logs/celery.log`

### Rate Limiting
- Check last audit dates in Django admin
- Manual audits: 3-day cooldown
- Automatic audits: 30-day cooldown

## API Integration

The system automatically triggers audits via signals:
```python
# When a new project is created
@receiver(post_save, sender=Project)
def trigger_onpage_audit(sender, instance, created, **kwargs):
    if created:
        create_onpage_audit_for_project.delay(instance.id)
```

## License Types

- **Free**: Limited to 500 URLs per crawl
- **Paid**: Unlimited URLs (or as per license terms)
- **Expired**: Falls back to free version limits

## Performance Considerations

- Large sites (>10,000 pages) may take significant time
- Adjust `max_pages_to_crawl` based on your needs
- Use Celery workers for background processing
- Monitor R2 storage usage for large reports