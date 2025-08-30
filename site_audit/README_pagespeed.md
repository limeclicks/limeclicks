# PageSpeed Insights Integration

This document explains the PageSpeed Insights integration that collects performance data alongside Screaming Frog site audits.

## Overview

The PageSpeed Insights integration automatically collects performance data from Google's PageSpeed Insights API for both mobile and desktop versions of your site's index page. This runs as a background task alongside the main Screaming Frog audit.

## Setup

### 1. Google API Key (Optional but Recommended)

To avoid rate limiting, add your Google PageSpeed Insights API key to your settings:

```python
# In settings.py or environment variables
GOOGLE_PSI_KEY = 'your-google-pagespeed-insights-api-key'
```

**How to get an API key:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the PageSpeed Insights API
4. Create credentials (API key)
5. Restrict the key to PageSpeed Insights API for security

### 2. Environment Variable (Recommended)

```bash
export GOOGLE_PSI_KEY="your-api-key-here"
```

## Data Collected

### 🔑 Scores (0-100)
- **Performance Score** - Overall performance rating
- **Accessibility Score** - Accessibility compliance rating  
- **Best Practices Score** - Web best practices rating
- **SEO Score** - Search engine optimization rating
- **PWA Checks** - Progressive Web App readiness (pass/fail)

### 📊 Core Web Vitals (Lab & Field Data)
- **Largest Contentful Paint (LCP)** - Loading performance
- **Interaction to Next Paint (INP)** - Interactivity (replaces FID)
- **Cumulative Layout Shift (CLS)** - Visual stability

### ⚡ Other Lab Metrics
- **First Contentful Paint (FCP)** - Initial render time
- **Speed Index** - Visual completeness over time
- **Total Blocking Time (TBT)** - Main thread blocking time
- **Time to Interactive (TTI)** - Full interactivity time
- **Server Response Time** - Initial server response

### 🌍 Field Data (Chrome UX Report)
- Real-world performance data from actual users
- 75th percentile metrics for all Core Web Vitals
- Distribution data (Good/Needs Improvement/Poor)

## Database Storage

All PageSpeed Insights data is stored in the `SiteAudit` model:

```python
# JSON fields containing full performance data
desktop_performance = JSONField()  # Complete desktop analysis
mobile_performance = JSONField()   # Complete mobile analysis

# Quick access integer scores
performance_score_mobile = IntegerField()    # 0-100
performance_score_desktop = IntegerField()   # 0-100
```

## Integration with Site Audits

The PageSpeed Insights task automatically runs when a site audit is triggered:

1. **Screaming Frog audit starts** - Main crawl begins
2. **Screaming Frog completes** - Data is processed and saved
3. **PageSpeed Insights task triggers** - Runs in parallel/after main audit
4. **Performance data collected** - For both mobile and desktop
5. **Scores updated** - Overall site health score recalculated

## Usage Examples

### Manual Trigger
```python
from site_audit.tasks import collect_pagespeed_insights

# Trigger PageSpeed collection for a site audit
result = collect_pagespeed_insights.apply_async(args=[site_audit_id])
```

### Accessing Data
```python
from site_audit.models import SiteAudit

site_audit = SiteAudit.objects.get(id=audit_id)

# Quick access to scores
print(f"Mobile Performance: {site_audit.performance_score_mobile}/100")
print(f"Desktop Performance: {site_audit.performance_score_desktop}/100")

# Detailed mobile data
mobile_data = site_audit.mobile_performance
mobile_scores = mobile_data.get('scores', {})
mobile_lab_metrics = mobile_data.get('lab_metrics', {})

# Core Web Vitals
lcp = mobile_lab_metrics.get('lcp', {})
print(f"Mobile LCP: {lcp.get('display_value')} (score: {lcp.get('score')})")
```

## Rate Limiting & Error Handling

- **Without API Key**: Limited to ~25 requests per day
- **With API Key**: Much higher limits (varies by quota)
- **Automatic Retries**: Failed requests retry up to 3 times with exponential backoff
- **Graceful Degradation**: Site audits continue even if PageSpeed data fails

## Testing

Use the test script to verify the integration:

```bash
python manage.py shell -c "from site_audit.test_pagespeed import test_pagespeed_structure; test_pagespeed_structure()"
```

## Monitoring

Check logs for PageSpeed Insights collection:

```bash
# Look for PageSpeed-related log messages
grep -i "pagespeed" /path/to/logs/celery.log
```

## Troubleshooting

### Common Issues

1. **429 Rate Limited**: Add API key or reduce request frequency
2. **API Key Invalid**: Verify key and API enablement in Google Cloud
3. **Network Timeouts**: Task has 5-minute timeout; will retry automatically
4. **No Data Collected**: Check if site is publicly accessible

### Debug Information

The task logs detailed information about each step:
- API requests made
- Response status codes  
- Data parsing results
- Database update operations