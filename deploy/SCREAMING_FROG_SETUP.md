# Screaming Frog SEO Spider Server Setup Guide

This guide covers installing, configuring, and managing Screaming Frog SEO Spider on an Ubuntu server for headless operation.

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [License Configuration](#license-configuration)
- [Verification](#verification)
- [Usage](#usage)
- [Django Integration](#django-integration)
- [Troubleshooting](#troubleshooting)
- [API Documentation](#api-documentation)
- [Maintenance](#maintenance)

## Overview

Screaming Frog SEO Spider is a website crawler that helps with technical SEO audits. This setup enables running it on a headless server without a GUI.

### Key Features
- Crawl websites up to 500 URLs (free) or unlimited (paid)
- Extract SEO data (titles, meta descriptions, headers, etc.)
- Find broken links and redirects
- Generate XML sitemaps
- Analyze page speed and Core Web Vitals

## Prerequisites

### System Requirements
- Ubuntu 20.04 LTS or 22.04 LTS
- Minimum 4GB RAM (8GB+ recommended for large crawls)
- 10GB+ free disk space
- Java Runtime Environment (installed by script)

### License Requirements (Optional)
- Purchase license from: https://www.screamingfrog.co.uk/seo-spider/
- License format: `EMAIL,XXXX-XXXX-XXXX-XXXX`
- Without license: 500 URL crawl limit

## Installation

### Quick Installation

```bash
# Download and run the setup script
cd /home/limeclicks/limeclicks/deploy
chmod +x setup_screaming_frog.sh

# Install with license
sudo ./setup_screaming_frog.sh --license=your.email@company.com,XXXX-XXXX-XXXX-XXXX

# Or install without license (free mode)
sudo ./setup_screaming_frog.sh
```

### What the Script Does

1. **Installs Dependencies**:
   - Java Runtime Environment
   - Xvfb (virtual display)
   - Required libraries for headless operation

2. **Sets Up Virtual Display**:
   - Creates Xvfb service for display :99
   - Enables automatic startup on boot

3. **Installs Screaming Frog**:
   - Downloads latest version
   - Configures for headless operation
   - Creates wrapper scripts

4. **Configures License** (if provided):
   - Validates license format
   - Saves to correct location
   - Verifies activation

## License Configuration

### Purchase a License

1. Visit: https://www.screamingfrog.co.uk/seo-spider/
2. Choose license type:
   - **Lite** (£149/year) - Single user
   - **Pro** (£449/year) - Up to 5 users
   - **Enterprise** - Custom pricing

### Add License to Server

#### Method 1: During Installation
```bash
sudo ./setup_screaming_frog.sh --license=john.doe@company.com,ABCD-EFGH-IJKL-MNOP
```

#### Method 2: After Installation
```bash
# Create license file manually
echo "john.doe@company.com,ABCD-EFGH-IJKL-MNOP" | sudo tee /home/limeclicks/.ScreamingFrogSEOSpider/licence.txt
sudo chmod 600 /home/limeclicks/.ScreamingFrogSEOSpider/licence.txt
sudo chown limeclicks:limeclicks /home/limeclicks/.ScreamingFrogSEOSpider/licence.txt
```

#### Method 3: Via Python Script
```python
import os
from pathlib import Path

def add_screaming_frog_license(email, license_key):
    """Add Screaming Frog license"""
    license_dir = Path.home() / '.ScreamingFrogSEOSpider'
    license_dir.mkdir(exist_ok=True)
    
    license_file = license_dir / 'licence.txt'
    license_content = f"{email},{license_key}"
    
    license_file.write_text(license_content)
    license_file.chmod(0o600)
    
    return license_file

# Usage
add_screaming_frog_license(
    'john.doe@company.com',
    'ABCD-EFGH-IJKL-MNOP'
)
```

### License Format

The license must be in this exact format:
```
EMAIL,XXXX-XXXX-XXXX-XXXX
```

Example:
```
john.doe@company.com,A1B2-C3D4-E5F6-G7H8
```

## Verification

### 1. Check Installation Status

```bash
# Run monitoring script
sf-monitor
```

Expected output:
```
Screaming Frog SEO Spider Status
================================

Virtual Display (Xvfb) Status:
  ✓ Xvfb is running on display :99

Screaming Frog Installation:
  ✓ Binary installed
  Version: 19.8

License Status:
  ✓ Licensed to: john.doe@company.com
  Mode: Paid (unlimited URLs)

Disk Space:
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        50G   15G   35G  30% /

Recent Crawls:
  No recent crawls found
```

### 2. Verify License

```bash
# Check license file
cat /home/limeclicks/.ScreamingFrogSEOSpider/licence.txt

# Verify via Python
sf-python-wrapper.py --verify-license https://example.com
```

### 3. Test Crawl

```bash
# Small test crawl
sf-crawl https://example.com --max-urls 10
```

### 4. Check Processes

```bash
# Check if Xvfb is running
ps aux | grep Xvfb

# Check Screaming Frog processes during crawl
ps aux | grep screaming
```

## Usage

### Command Line Interface

#### Basic Crawl
```bash
# Crawl a website
sf-crawl https://example.com

# Limit crawl size
sf-crawl https://example.com --max-urls 1000

# Export specific data
sf-crawl https://example.com --export-tabs "Internal:All,External:All,Images:All"
```

#### Available Export Tabs
- `Internal:All` - All internal URLs
- `External:All` - All external URLs
- `Protocol:All` - HTTP/HTTPS URLs
- `Response Codes:All` - All response codes
- `URI:All` - All URIs
- `Page Titles:All` - Page titles
- `Meta Description:All` - Meta descriptions
- `H1:All` - H1 tags
- `H2:All` - H2 tags
- `Images:All` - All images
- `Canonical:All` - Canonical tags
- `Pagination:All` - Pagination tags
- `Hreflang:All` - Hreflang tags
- `Structured Data:All` - Schema markup

#### Python Wrapper
```python
from subprocess import run
import json

# Run crawl via Python
result = run(
    ['sf-python-wrapper.py', 'https://example.com', '--max-urls', '100'],
    capture_output=True,
    text=True
)

data = json.loads(result.stdout)
print(f"Crawl successful: {data['success']}")
print(f"Output files: {data['files']}")
```

## Django Integration

### Update Settings

```python
# settings.py
SCREAMING_FROG_CONFIG = {
    'BINARY_PATH': '/usr/bin/screamingfrogseospider',
    'DISPLAY': ':99',
    'DEFAULT_OUTPUT_DIR': '/tmp/sf_crawls',
    'MAX_CRAWL_TIME': 3600,  # 1 hour
    'DEFAULT_MAX_URLS': 10000,
    'LICENSE_FILE': '/home/limeclicks/.ScreamingFrogSEOSpider/licence.txt'
}
```

### Django Management Command

Create `management/commands/crawl_with_sf.py`:

```python
from django.core.management.base import BaseCommand
from django.conf import settings
import subprocess
import json
import os
from pathlib import Path

class Command(BaseCommand):
    help = 'Crawl website with Screaming Frog'
    
    def add_arguments(self, parser):
        parser.add_argument('url', type=str, help='URL to crawl')
        parser.add_argument('--max-urls', type=int, default=1000)
        parser.add_argument('--export-tabs', type=str, default='Internal:All')
    
    def handle(self, *args, **options):
        # Set display
        os.environ['DISPLAY'] = settings.SCREAMING_FROG_CONFIG['DISPLAY']
        
        # Run crawl
        cmd = [
            settings.SCREAMING_FROG_CONFIG['BINARY_PATH'],
            '--crawl', options['url'],
            '--headless',
            '--output-folder', '/tmp/sf_crawl',
            '--export-tabs', options['export_tabs'],
            '--max-uri', str(options['max_urls']),
            '--overwrite'
        ]
        
        self.stdout.write(f"Starting crawl of {options['url']}...")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=settings.SCREAMING_FROG_CONFIG['MAX_CRAWL_TIME']
            )
            
            if result.returncode == 0:
                self.stdout.write(
                    self.style.SUCCESS('Crawl completed successfully')
                )
                
                # List output files
                output_dir = Path('/tmp/sf_crawl')
                for file in output_dir.glob('*.csv'):
                    self.stdout.write(f"  - {file.name}")
            else:
                self.stdout.write(
                    self.style.ERROR(f'Crawl failed: {result.stderr}')
                )
                
        except subprocess.TimeoutExpired:
            self.stdout.write(
                self.style.ERROR('Crawl timeout exceeded')
            )
```

### Celery Task

```python
# site_audit/tasks.py
from celery import shared_task
from django.conf import settings
import subprocess
import os
import csv
from pathlib import Path

@shared_task
def crawl_with_screaming_frog(url, max_urls=1000):
    """
    Run Screaming Frog crawl as background task
    """
    os.environ['DISPLAY'] = ':99'
    
    output_dir = Path('/tmp/sf_crawls') / f'crawl_{url.replace("://", "_").replace("/", "_")}'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        '/usr/bin/screamingfrogseospider',
        '--crawl', url,
        '--headless',
        '--save-crawl',
        '--output-folder', str(output_dir),
        '--export-tabs', 'Internal:All,Response Codes:Client Error,Response Codes:Server Error',
        '--max-uri', str(max_urls),
        '--overwrite',
        '--timestamped-output'
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600
        )
        
        # Parse results
        results = {
            'success': result.returncode == 0,
            'url': url,
            'output_dir': str(output_dir),
            'files': []
        }
        
        # Read CSV files
        for csv_file in output_dir.glob('*.csv'):
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                data = list(reader)
                
                results['files'].append({
                    'name': csv_file.name,
                    'rows': len(data),
                    'sample': data[:5] if data else []
                })
        
        return results
        
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'Crawl timeout',
            'url': url
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'url': url
        }
```

## Troubleshooting

### Common Issues and Solutions

#### 1. License Not Working

**Problem**: License file exists but crawl still limited to 500 URLs

**Solutions**:
```bash
# Check license file permissions
ls -la /home/limeclicks/.ScreamingFrogSEOSpider/licence.txt
# Should be: -rw------- 1 limeclicks limeclicks

# Fix permissions
sudo chmod 600 /home/limeclicks/.ScreamingFrogSEOSpider/licence.txt
sudo chown limeclicks:limeclicks /home/limeclicks/.ScreamingFrogSEOSpider/licence.txt

# Verify license format (no spaces, correct format)
cat /home/limeclicks/.ScreamingFrogSEOSpider/licence.txt
# Should be: email@company.com,XXXX-XXXX-XXXX-XXXX
```

#### 2. Xvfb Not Running

**Problem**: Error about display :99 not found

**Solutions**:
```bash
# Start Xvfb
sudo systemctl start xvfb

# Check status
sudo systemctl status xvfb

# Enable on boot
sudo systemctl enable xvfb

# Manual start for testing
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99
```

#### 3. Java Memory Issues

**Problem**: OutOfMemoryError during large crawls

**Solutions**:
```bash
# Edit configuration
sudo nano /home/limeclicks/.ScreamingFrogSEOSpider/seospider.config

# Increase memory (in MB)
memory.max=16384  # 16GB

# Or set via environment variable
export JAVA_OPTS="-Xmx16g -Xms4g"
```

#### 4. Crawl Hanging

**Problem**: Crawl starts but doesn't progress

**Solutions**:
```bash
# Check for JavaScript rendering issues
# Disable JavaScript rendering in config
echo "rendering.enabled=false" >> /home/limeclicks/.ScreamingFrogSEOSpider/seospider.config

# Reduce crawl speed
echo "crawl.max.threads=2" >> /home/limeclicks/.ScreamingFrogSEOSpider/seospider.config
```

#### 5. Permission Denied Errors

**Problem**: Cannot write to output directory

**Solutions**:
```bash
# Create output directory with correct permissions
sudo mkdir -p /var/lib/screaming_frog/crawls
sudo chown -R limeclicks:limeclicks /var/lib/screaming_frog
sudo chmod 755 /var/lib/screaming_frog
```

### Debug Mode

Enable debug logging:

```bash
# Create debug configuration
cat > /home/limeclicks/.ScreamingFrogSEOSpider/logback.xml <<EOF
<configuration>
    <appender name="FILE" class="ch.qos.logback.core.FileAppender">
        <file>/var/log/screaming_frog/debug.log</file>
        <encoder>
            <pattern>%d{HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n</pattern>
        </encoder>
    </appender>
    
    <root level="DEBUG">
        <appender-ref ref="FILE" />
    </root>
</configuration>
EOF

# Run with debug logging
screamingfrogseospider --crawl https://example.com --headless --log-config /home/limeclicks/.ScreamingFrogSEOSpider/logback.xml
```

## API Documentation

### Configuration API

```python
class ScreamingFrogConfig:
    """Screaming Frog configuration manager"""
    
    def __init__(self, config_dir='/home/limeclicks/.ScreamingFrogSEOSpider'):
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / 'seospider.config'
        self.license_file = self.config_dir / 'licence.txt'
    
    def set_memory(self, mb):
        """Set maximum memory allocation"""
        self.update_config('memory.max', str(mb))
    
    def set_crawl_speed(self, threads, urls_per_second):
        """Set crawl speed limits"""
        self.update_config('crawl.max.threads', str(threads))
        self.update_config('crawl.max.uri.per.second', str(urls_per_second))
    
    def set_user_agent(self, user_agent):
        """Set custom user agent"""
        self.update_config('user.agent', user_agent)
    
    def enable_javascript(self, enabled=True):
        """Enable/disable JavaScript rendering"""
        self.update_config('rendering.enabled', str(enabled).lower())
    
    def update_config(self, key, value):
        """Update configuration value"""
        config = {}
        
        if self.config_file.exists():
            with open(self.config_file) as f:
                for line in f:
                    if '=' in line:
                        k, v = line.strip().split('=', 1)
                        config[k] = v
        
        config[key] = value
        
        with open(self.config_file, 'w') as f:
            for k, v in config.items():
                f.write(f"{k}={v}\n")
```

### Crawl Result Parser

```python
import csv
import pandas as pd
from pathlib import Path

class ScreamingFrogResults:
    """Parse Screaming Frog export files"""
    
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
    
    def get_internal_urls(self):
        """Get all internal URLs"""
        file = self.output_dir / 'internal_all.csv'
        if file.exists():
            return pd.read_csv(file)
        return None
    
    def get_broken_links(self):
        """Get all broken links (4xx, 5xx)"""
        df = self.get_internal_urls()
        if df is not None:
            return df[df['Status Code'].isin(range(400, 600))]
        return None
    
    def get_redirect_chains(self):
        """Get redirect chains"""
        file = self.output_dir / 'redirect_chains.csv'
        if file.exists():
            return pd.read_csv(file)
        return None
    
    def get_missing_meta(self):
        """Get pages with missing meta descriptions"""
        df = self.get_internal_urls()
        if df is not None:
            return df[df['Meta Description 1 Length'] == 0]
        return None
    
    def get_duplicate_titles(self):
        """Get duplicate page titles"""
        df = self.get_internal_urls()
        if df is not None:
            duplicates = df[df.duplicated('Title 1', keep=False)]
            return duplicates.sort_values('Title 1')
        return None
```

## Maintenance

### Regular Tasks

#### 1. Clean Up Old Crawls
```bash
# Delete crawls older than 7 days
find /tmp/sf_crawls -type d -mtime +7 -exec rm -rf {} \;

# Add to crontab
0 2 * * * find /tmp/sf_crawls -type d -mtime +7 -exec rm -rf {} \;
```

#### 2. Update Screaming Frog
```bash
# Check for updates
curl -s https://www.screamingfrog.co.uk/seo-spider/release-notes/ | grep -o "Version [0-9.]*" | head -1

# Download and install new version
SF_VERSION="19.9"  # New version
wget https://download.screamingfrog.co.uk/products/seo-spider/ScreamingFrogSEOSpider-${SF_VERSION}.x86_64.rpm
sudo alien -d ScreamingFrogSEOSpider-${SF_VERSION}.x86_64.rpm
sudo dpkg -i screamingfrogseospider*.deb
```

#### 3. Monitor Disk Usage
```bash
# Check disk usage
df -h /tmp
du -sh /tmp/sf_crawls

# Set up alert
cat > /usr/local/bin/check_sf_disk.sh <<'EOF'
#!/bin/bash
USAGE=$(df /tmp | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $USAGE -gt 80 ]; then
    echo "Warning: /tmp is ${USAGE}% full" | mail -s "Disk Space Alert" admin@example.com
fi
EOF

chmod +x /usr/local/bin/check_sf_disk.sh
```

#### 4. Backup Configuration
```bash
# Backup configuration and license
tar -czf sf_config_backup_$(date +%Y%m%d).tar.gz \
    /home/limeclicks/.ScreamingFrogSEOSpider \
    /usr/local/bin/sf-* \
    /etc/systemd/system/xvfb.service

# Store in safe location
mv sf_config_backup_*.tar.gz /backup/
```

### Performance Optimization

#### 1. Optimize for Large Crawls
```bash
# Increase system limits
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# Increase memory
echo "memory.max=32768" >> /home/limeclicks/.ScreamingFrogSEOSpider/seospider.config

# Disable unnecessary features
cat >> /home/limeclicks/.ScreamingFrogSEOSpider/seospider.config <<EOF
crawl.store.html=false
crawl.store.rendered.html=false
extraction.extract.css=false
extraction.extract.javascript=false
EOF
```

#### 2. Parallel Crawling
```python
from concurrent.futures import ProcessPoolExecutor
import subprocess

def crawl_site(url):
    """Crawl a single site"""
    cmd = ['sf-crawl', url, '--max-urls', '1000']
    result = subprocess.run(cmd, capture_output=True)
    return {'url': url, 'success': result.returncode == 0}

# Crawl multiple sites in parallel
urls = ['https://site1.com', 'https://site2.com', 'https://site3.com']

with ProcessPoolExecutor(max_workers=3) as executor:
    results = list(executor.map(crawl_site, urls))

print(results)
```

## Summary

This setup provides:
- ✅ Headless Screaming Frog operation on Ubuntu server
- ✅ Automated installation and configuration
- ✅ License management and verification
- ✅ Django/Python integration
- ✅ Monitoring and maintenance scripts
- ✅ Troubleshooting guide

For support, check:
- Official docs: https://www.screamingfrog.co.uk/seo-spider/user-guide/
- Release notes: https://www.screamingfrog.co.uk/seo-spider/release-notes/