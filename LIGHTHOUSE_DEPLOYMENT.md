# Lighthouse Audit System - Production Deployment Guide

## Overview
This guide covers deploying the Lighthouse audit system on production servers without GUI/browser support.

## Prerequisites

### 1. System Requirements
- Ubuntu 20.04+ or Debian 10+ (recommended)
- Minimum 2GB RAM
- Node.js 18+ and npm
- Python 3.10+
- Redis (for Celery)

### 2. Install Headless Chrome

#### Option A: Using the provided script
```bash
cd /path/to/limeclicks
chmod +x scripts/install_chrome_headless.sh
./scripts/install_chrome_headless.sh
```

#### Option B: Manual installation
```bash
# Update system
sudo apt-get update

# Install Chrome dependencies
sudo apt-get install -y \
    wget gnupg ca-certificates apt-transport-https \
    fonts-liberation libasound2 libatk-bridge2.0-0 \
    libatk1.0-0 libatspi2.0-0 libcups2 libdbus-1-3 \
    libdrm2 libgbm1 libgtk-3-0 libnspr4 libnss3 \
    libxcomposite1 libxdamage1 libxfixes3 libxkbcommon0 \
    libxrandr2 xdg-utils

# Install Chromium (lighter alternative)
sudo apt-get install -y chromium-browser

# OR Install Google Chrome
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt-get update
sudo apt-get install -y google-chrome-stable
```

### 3. Install Lighthouse
```bash
# Install globally
sudo npm install -g lighthouse

# Verify installation
lighthouse --version
```

## Environment Configuration

### 1. Set R2/S3 Credentials
Add to your `.env` file:
```env
# Cloudflare R2 Configuration (S3-compatible)
R2_ACCESS_KEY_ID=your_access_key_id
R2_SECRET_ACCESS_KEY=your_secret_access_key
R2_BUCKET_NAME=your_bucket_name
R2_ENDPOINT_URL=https://your-account-id.r2.cloudflarestorage.com

# Optional: Custom domain for R2
R2_CUSTOM_DOMAIN=https://cdn.yourdomain.com
```

### 2. Redis Configuration
```env
REDIS_URL=redis://localhost:6379/0
```

## Django Settings

The system uses AWS S3 settings for R2 (they're compatible):
```python
# AWS S3 Settings for django-storages (Cloudflare R2 is S3-compatible)
AWS_ACCESS_KEY_ID = os.getenv('R2_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('R2_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.getenv('R2_BUCKET_NAME')
AWS_S3_ENDPOINT_URL = os.getenv('R2_ENDPOINT_URL')
AWS_S3_REGION_NAME = 'auto'
AWS_S3_SIGNATURE_VERSION = 's3v4'
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = None  # R2 doesn't support ACLs
AWS_S3_VERIFY = True
```

## Database Migration
```bash
python manage.py migrate audits
```

## Celery Setup

### 1. Start Celery Worker
```bash
# For development
celery -A limeclicks worker -l info --queue=audits,celery

# For production with supervisor
[program:celery_worker]
command=/path/to/venv/bin/celery -A limeclicks worker -l info --queue=audits,celery
directory=/path/to/limeclicks
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/celery/worker.log
```

### 2. Start Celery Beat (for scheduled audits)
```bash
# For development
celery -A limeclicks beat -l info

# For production with supervisor
[program:celery_beat]
command=/path/to/venv/bin/celery -A limeclicks beat -l info
directory=/path/to/limeclicks
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/celery/beat.log
```

## Docker Deployment (Alternative)

### 1. Build Lighthouse Docker Image
```bash
docker build -f Dockerfile.lighthouse -t lighthouse-runner .
```

### 2. Use with Docker Compose
```yaml
version: '3.8'

services:
  web:
    build: .
    environment:
      - R2_ACCESS_KEY_ID=${R2_ACCESS_KEY_ID}
      - R2_SECRET_ACCESS_KEY=${R2_SECRET_ACCESS_KEY}
      - R2_BUCKET_NAME=${R2_BUCKET_NAME}
      - R2_ENDPOINT_URL=${R2_ENDPOINT_URL}
    depends_on:
      - redis
      - lighthouse

  lighthouse:
    image: lighthouse-runner
    volumes:
      - lighthouse-data:/home/lighthouse/reports

  celery:
    build: .
    command: celery -A limeclicks worker -l info --queue=audits,celery
    environment:
      - CHROME_PATH=/usr/bin/chromium-browser
    depends_on:
      - redis
      - lighthouse

  celery-beat:
    build: .
    command: celery -A limeclicks beat -l info
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  lighthouse-data:
```

## Testing the Setup

### 1. Test Chrome/Chromium
```bash
# Test headless Chrome
google-chrome --version
google-chrome --headless --dump-dom https://www.example.com

# OR for Chromium
chromium-browser --version
chromium-browser --headless --dump-dom https://www.example.com
```

### 2. Test Lighthouse
```bash
# Run a test audit
lighthouse https://www.example.com \
  --output=json \
  --chrome-flags="--headless=new --no-sandbox" \
  --preset=desktop \
  --quiet
```

### 3. Test Django Integration
```bash
# Test audit functionality
python manage.py test_audit --url https://example.com --device desktop

# Test R2 storage
python manage.py test_r2_audit

# Run comprehensive tests
python test_audit_system.py
```

## Monitoring

### 1. Check Audit Status
```python
# Django shell
from audits.models import AuditHistory
recent = AuditHistory.objects.order_by('-created_at')[:5]
for audit in recent:
    print(f"{audit.created_at}: {audit.status} - {audit.audit_page.project.domain}")
```

### 2. Monitor Celery Tasks
```bash
# Using Flower (if installed)
celery -A limeclicks flower

# Check task queue
celery -A limeclicks inspect active
```

### 3. Check R2 Storage
```bash
# List audit files in R2
python manage.py test_r2_audit
```

## Troubleshooting

### Issue: Chrome not found
```bash
# Set Chrome path explicitly
export CHROME_PATH=/usr/bin/google-chrome-stable
# OR
export CHROME_PATH=/usr/bin/chromium-browser
```

### Issue: Out of Memory
```bash
# Increase swap if needed
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Issue: Lighthouse timeout
Adjust timeout in `lighthouse_runner.py`:
```python
result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    timeout=180  # Increase from 120 to 180 seconds
)
```

### Issue: R2 Connection Error
Verify credentials:
```bash
aws s3 ls s3://your-bucket/ \
  --endpoint-url=https://your-account.r2.cloudflarestorage.com \
  --region=auto
```

## Security Considerations

1. **Chrome Flags**: The system uses secure headless flags:
   - `--headless=new`: Modern headless mode
   - `--no-sandbox`: Required in containers (use with caution)
   - `--disable-gpu`: Not needed for audits
   - `--disable-dev-shm-usage`: Prevents /dev/shm issues

2. **Rate Limiting**: Manual audits limited to 1 per day per project

3. **Storage**: Files stored in R2 with signed URLs (expire after 1 hour)

## Performance Optimization

1. **Parallel Execution**: Desktop and mobile audits run in parallel
2. **Celery Queues**: Dedicated `audits` queue with priority
3. **Cleanup**: Old audits automatically deleted after 90 days
4. **Caching**: Audit results cached in database for quick access

## Production Checklist

- [ ] Chrome/Chromium installed and verified
- [ ] Lighthouse installed globally
- [ ] R2 credentials configured
- [ ] Database migrated
- [ ] Redis running
- [ ] Celery worker running
- [ ] Celery beat running
- [ ] Test audit successful
- [ ] R2 storage verified
- [ ] Monitoring setup

## Support

For issues:
1. Check logs: `/var/log/celery/worker.log`
2. Run test suite: `python test_audit_system.py`
3. Verify R2: `python manage.py test_r2_audit`
4. Check Chrome: `chromium-browser --version`