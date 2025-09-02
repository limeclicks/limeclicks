# LimeClicks Installation and Deployment Guide

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Local Development Setup](#local-development-setup)
3. [Production Deployment](#production-deployment)
4. [Performance Optimizations](#performance-optimizations)
5. [Monitoring and Maintenance](#monitoring-and-maintenance)
6. [Troubleshooting](#troubleshooting)

## System Requirements

### Minimum Requirements
- **CPU**: 4 cores
- **RAM**: 8GB
- **Storage**: 50GB SSD
- **OS**: Ubuntu 22.04 LTS
- **Python**: 3.12.2
- **Node.js**: 22.18.0
- **PostgreSQL**: 14+
- **Redis**: 6+

### Recommended Production Requirements
- **CPU**: 8+ cores
- **RAM**: 16-32GB
- **Storage**: 200GB+ SSD
- **Network**: 1Gbps

## Local Development Setup

### 1. Clone Repository
```bash
git clone https://github.com/limeclicks/limeclicks.git
cd limeclicks
```

### 2. Install Python with pyenv
```bash
# Install pyenv
curl https://pyenv.run | bash

# Add to ~/.bashrc
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
source ~/.bashrc

# Install Python 3.12.2
pyenv install 3.12.2
pyenv local 3.12.2
```

### 3. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 4. Install Dependencies
```bash
# Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install gevent for better concurrency
pip install gevent greenlet psycogreen gunicorn
```

### 5. Install Node.js with nvm
```bash
# Install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc

# Install Node.js
nvm install 22.18.0
nvm use 22.18.0

# Install Node dependencies
npm install
```

### 6. Database Setup
```bash
# Install PostgreSQL
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# Create database
sudo -u postgres psql
CREATE DATABASE limeclicks;
CREATE USER limeclicks_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE limeclicks TO limeclicks_user;
\q

# Run migrations
python manage.py migrate
python manage.py createsuperuser
```

### 7. Redis Setup
```bash
# Install Redis
sudo apt-get install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

### 8. Environment Configuration
Create `.env` file:
```env
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_DOMAINS=['localhost', '127.0.0.1']
DATABASE_URL=postgres://limeclicks_user:your_password@localhost/limeclicks
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### 9. Build Frontend Assets
```bash
npm run build-css
python manage.py collectstatic --noinput
```

### 10. Run Development Server
```bash
# Terminal 1: Django with Gevent
gunicorn --config gunicorn_config.py limeclicks.wsgi:application

# Terminal 2: Celery Worker
celery -A limeclicks worker --loglevel=info

# Terminal 3: Celery Beat
celery -A limeclicks beat --loglevel=info

# Or use Django development server
python manage.py runserver
```

## Production Deployment

### 1. Server Setup
```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install required packages
sudo apt-get install -y \
    build-essential \
    python3-dev \
    postgresql \
    postgresql-contrib \
    redis-server \
    nginx \
    supervisor \
    git \
    curl \
    wget \
    htop \
    ufw
```

### 2. Clone and Setup Application
```bash
# Clone repository
cd /home/ubuntu
git clone https://github.com/limeclicks/limeclicks.git new-limeclicks
cd new-limeclicks

# Setup Python with pyenv
pyenv install 3.12.2
pyenv local 3.12.2

# Install dependencies
pip install -r requirements.txt
pip install gevent greenlet psycogreen gunicorn
```

### 3. Production Environment Configuration
Create production `.env`:
```env
SECRET_KEY=strong-production-secret-key
DEBUG=False
ALLOWED_DOMAINS=['portal.limeclicks.com', 'your-domain.com']
DATABASE_URL=postgres://prod_user:prod_password@localhost/limeclicks_prod
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### 4. Gunicorn with Gevent Configuration
Create `gunicorn_config_production.py`:
```python
import multiprocessing

bind = "127.0.0.1:8000"
workers = min(multiprocessing.cpu_count() * 2 + 1, 9)
worker_class = "gevent"
worker_connections = 1000
keepalive = 5
timeout = 300
max_requests = 1000
max_requests_jitter = 50
preload_app = True
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"
```

### 5. Systemd Service Configuration

#### Gunicorn Service
`/etc/systemd/system/limeclicks-gunicorn.service`:
```ini
[Unit]
Description=LimeClicks Gunicorn with Gevent
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/new-limeclicks
Environment="PATH=/home/ubuntu/.pyenv/versions/3.12.2/bin:/usr/bin"
Environment="DJANGO_SETTINGS_MODULE=limeclicks.settings"
ExecStart=/home/ubuntu/.pyenv/versions/3.12.2/bin/gunicorn \
    --config /home/ubuntu/new-limeclicks/gunicorn_config_production.py \
    limeclicks.wsgi:application
Restart=on-failure
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

#### Celery Service
`/etc/systemd/system/limeclicks-celery.service`:
```ini
[Unit]
Description=LimeClicks Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/new-limeclicks
Environment="PATH=/home/ubuntu/.pyenv/versions/3.12.2/bin:/usr/bin"
ExecStart=/home/ubuntu/.pyenv/versions/3.12.2/bin/celery \
    -A limeclicks worker \
    --loglevel=info \
    --concurrency=4
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### 6. Nginx Configuration
`/etc/nginx/sites-available/limeclicks`:
```nginx
server {
    listen 80;
    server_name portal.limeclicks.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name portal.limeclicks.com;
    
    ssl_certificate /etc/letsencrypt/live/portal.limeclicks.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/portal.limeclicks.com/privkey.pem;
    
    client_max_body_size 50M;
    
    location /static/ {
        alias /home/ubuntu/new-limeclicks/staticfiles/;
        expires 365d;
    }
    
    location /media/ {
        alias /home/ubuntu/new-limeclicks/media/;
        expires 30d;
    }
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 300s;
        proxy_read_timeout 300s;
    }
}
```

### 7. SSL Certificate Setup
```bash
# Install Certbot
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot

# Get SSL certificate
sudo certbot --nginx -d portal.limeclicks.com
```

### 8. Start Services
```bash
# Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable limeclicks-gunicorn limeclicks-celery limeclicks-celerybeat
sudo systemctl start limeclicks-gunicorn limeclicks-celery limeclicks-celerybeat
sudo systemctl restart nginx
```

## Performance Optimizations

### PostgreSQL Optimization (30GB RAM Server)
Create `/etc/postgresql/14/main/conf.d/optimization.conf`:
```conf
# Memory Configuration
shared_buffers = 7680MB              # 25% of RAM
effective_cache_size = 23GB          # 75% of RAM
maintenance_work_mem = 1GB
work_mem = 32MB
wal_buffers = 16MB

# Connection Settings
max_connections = 200
superuser_reserved_connections = 3

# Checkpoint Settings
checkpoint_completion_target = 0.9
checkpoint_timeout = 15min
max_wal_size = 4GB
min_wal_size = 1GB

# Query Planner (SSD optimized)
random_page_cost = 1.1
effective_io_concurrency = 200
default_statistics_target = 100

# Parallel Query Execution
max_parallel_workers_per_gather = 4
max_parallel_workers = 8

# Logging
log_min_duration_statement = 100
log_checkpoints = on
log_lock_waits = on

# Autovacuum
autovacuum = on
autovacuum_max_workers = 4
autovacuum_vacuum_scale_factor = 0.1
autovacuum_analyze_scale_factor = 0.05
```

### System Kernel Optimization
Create `/etc/sysctl.d/99-limeclicks.conf`:
```conf
# Network optimizations
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_tw_reuse = 1
net.ipv4.ip_local_port_range = 1024 65535

# Memory optimizations
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5

# File system
fs.file-max = 2097152
fs.nr_open = 1048576
```

Apply with: `sudo sysctl -p /etc/sysctl.d/99-limeclicks.conf`

### Redis Optimization
Add to `/etc/redis/redis.conf`:
```conf
maxmemory 4gb
maxmemory-policy allkeys-lru
tcp-backlog 511
timeout 0
tcp-keepalive 300
```

## Monitoring and Maintenance

### Health Check Script
Create `/home/ubuntu/new-limeclicks/monitor.sh`:
```bash
#!/bin/bash
echo "=== System Health Check ==="
echo "[Memory]"
free -h | grep Mem
echo "[CPU Load]"
uptime
echo "[Services]"
systemctl is-active limeclicks-gunicorn limeclicks-celery limeclicks-celerybeat
echo "[Disk Usage]"
df -h /
```

### Log Locations
- **Gunicorn**: `/var/log/gunicorn/error.log`
- **Celery**: `/home/ubuntu/new-limeclicks/logs/celery-worker.log`
- **Nginx**: `/var/log/nginx/error.log`
- **PostgreSQL**: `/var/log/postgresql/postgresql-14-main.log`

### Backup Script
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/limeclicks"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Database backup
pg_dump limeclicks | gzip > "$BACKUP_DIR/db_$TIMESTAMP.sql.gz"

# Media files backup
tar -czf "$BACKUP_DIR/media_$TIMESTAMP.tar.gz" -C /home/ubuntu/new-limeclicks media/

# Keep only last 30 days
find $BACKUP_DIR -type f -mtime +30 -delete
```

Add to crontab: `0 2 * * * /home/ubuntu/backup.sh`

## Troubleshooting

### Common Issues

#### 502 Bad Gateway
```bash
# Check if Gunicorn is running
sudo systemctl status limeclicks-gunicorn

# Check Nginx error logs
tail -f /var/log/nginx/error.log

# Restart services
sudo systemctl restart limeclicks-gunicorn nginx
```

#### High Memory Usage
```bash
# Check memory usage
ps aux --sort=-%mem | head

# Restart Gunicorn workers
sudo systemctl reload limeclicks-gunicorn
```

#### Slow Database Queries
```bash
# Check slow queries
sudo -u postgres psql -d limeclicks
SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;

# Run VACUUM and ANALYZE
VACUUM ANALYZE;
```

#### Celery Tasks Not Running
```bash
# Check Celery status
sudo systemctl status limeclicks-celery limeclicks-celerybeat

# Check Redis connectivity
redis-cli ping

# Restart Celery
sudo systemctl restart limeclicks-celery limeclicks-celerybeat
```

### Performance Testing
```bash
# Install Apache Bench
sudo apt-get install apache2-utils

# Test endpoint
ab -n 1000 -c 10 https://portal.limeclicks.com/

# Monitor during test
htop
tail -f /var/log/gunicorn/access.log
```

## GitHub Actions Deployment

The project includes automated deployment via GitHub Actions. When you push to the `main` branch:

1. Code is automatically pulled on the production server
2. Dependencies are installed (including gevent)
3. Database migrations are run
4. Static files are collected
5. Services are restarted
6. Gevent workers are verified

See `.github/workflows/deploy.yml` for the complete deployment pipeline.

## Security Best Practices

1. **Environment Variables**: Never commit `.env` files
2. **Secret Keys**: Use strong, unique secret keys in production
3. **Database**: Use separate database users with minimal privileges
4. **Firewall**: Configure UFW to only allow necessary ports
5. **SSL**: Always use HTTPS in production
6. **Updates**: Regularly update system packages and dependencies
7. **Monitoring**: Set up alerts for unusual activity
8. **Backups**: Regular automated backups with offsite storage

## Support

For issues or questions:
- GitHub Issues: https://github.com/limeclicks/limeclicks/issues
- Documentation: This guide
- Logs: Check service logs for detailed error messages