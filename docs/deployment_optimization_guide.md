# LimeClicks Production Deployment Optimization Guide

## Table of Contents
1. [Gunicorn with Gevent Workers](#gunicorn-with-gevent-workers)
2. [Database Optimization](#database-optimization)
3. [Redis Configuration](#redis-configuration)
4. [Nginx Optimization](#nginx-optimization)
5. [System Performance Tuning](#system-performance-tuning)
6. [Monitoring Setup](#monitoring-setup)
7. [Complete Deployment Commands](#complete-deployment-commands)

## Gunicorn with Gevent Workers

### Install Gevent
```bash
pip install gevent
pip install greenlet
pip install psycogreen  # For PostgreSQL async support
```

### Gunicorn Configuration with Gevent
Create `/home/muaaz/enterprise/limeclicks/gunicorn_config.py`:

```python
import multiprocessing
import os

# Server Socket
bind = "127.0.0.1:8000"
backlog = 2048

# Worker Processes - GEVENT CONFIGURATION
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gevent"  # Switch to gevent workers
worker_connections = 1000  # Max simultaneous clients per worker
keepalive = 5

# Gevent specific settings
worker_tmp_dir = "/dev/shm"  # Use RAM for worker heartbeat
max_requests = 1000  # Restart workers after this many requests
max_requests_jitter = 50  # Randomize worker restart

# Timeouts
timeout = 300  # 5 minutes for long-running requests
graceful_timeout = 30

# Logging
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process Naming
proc_name = "limeclicks_gunicorn"

# Server Mechanics
daemon = False
pidfile = "/var/run/gunicorn/limeclicks.pid"
user = "www-data"
group = "www-data"
tmp_upload_dir = None

# SSL (if needed)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# StatsD Metrics (optional)
# statsd_host = "localhost:8125"
# statsd_prefix = "limeclicks"

# Pre-loading application
preload_app = True

# Worker lifecycle hooks
def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def pre_exec(server):
    server.log.info("Forked child, re-executing.")

def on_starting(server):
    server.log.info("Starting Gunicorn server")

def on_reload(server):
    server.log.info("Reloading Gunicorn server")
```

### Django Settings for Gevent
Add to `settings.py`:

```python
# Gevent monkey patching (add at the very top of settings.py)
from gevent import monkey
monkey.patch_all()

# Database connection pooling for gevent
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'limeclicks',
        'USER': 'your_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
        'CONN_MAX_AGE': 0,  # Disable Django's connection pooling
        'OPTIONS': {
            'connect_timeout': 10,
            'options': '-c statement_timeout=300000',  # 5 minutes
        },
    }
}

# Use psycogreen for PostgreSQL async support
if 'gevent' in os.environ.get('SERVER_SOFTWARE', ''):
    from psycogreen.gevent import patch_psycopg
    patch_psycopg()
```

### Systemd Service Configuration
Update `/etc/systemd/system/limeclicks.service`:

```ini
[Unit]
Description=LimeClicks Gunicorn Application
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
Type=notify
User=www-data
Group=www-data
RuntimeDirectory=gunicorn
WorkingDirectory=/home/muaaz/enterprise/limeclicks
Environment="PATH=/home/muaaz/enterprise/limeclicks/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=limeclicks.settings"
Environment="SERVER_SOFTWARE=gevent"

# Use the configuration file
ExecStart=/home/muaaz/enterprise/limeclicks/venv/bin/gunicorn \
    --config /home/muaaz/enterprise/limeclicks/gunicorn_config.py \
    limeclicks.wsgi:application

ExecReload=/bin/kill -s HUP $MAINPID
ExecStop=/bin/kill -s TERM $MAINPID

# Process management
Restart=on-failure
RestartSec=5s
KillMode=mixed
KillSignal=SIGQUIT
PrivateTmp=true

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096

# Security hardening
NoNewPrivileges=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/gunicorn /var/run/gunicorn /home/muaaz/enterprise/limeclicks/media /home/muaaz/enterprise/limeclicks/staticfiles

[Install]
WantedBy=multi-user.target
```

## Database Optimization

### PostgreSQL Configuration
Edit `/etc/postgresql/14/main/postgresql.conf`:

```conf
# Memory Configuration
shared_buffers = 2GB              # 25% of RAM for 8GB system
effective_cache_size = 6GB        # 75% of RAM
maintenance_work_mem = 512MB
work_mem = 16MB                   # Per connection
wal_buffers = 16MB

# Connection Settings
max_connections = 200
superuser_reserved_connections = 3

# Checkpoint Settings
checkpoint_completion_target = 0.9
checkpoint_timeout = 10min
max_wal_size = 2GB
min_wal_size = 1GB

# Query Planner
random_page_cost = 1.1            # For SSD
effective_io_concurrency = 200    # For SSD
default_statistics_target = 100

# Logging
log_min_duration_statement = 100  # Log slow queries > 100ms
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on
log_temp_files = 0

# Autovacuum
autovacuum = on
autovacuum_max_workers = 4
autovacuum_naptime = 30s
autovacuum_vacuum_threshold = 50
autovacuum_analyze_threshold = 50
autovacuum_vacuum_scale_factor = 0.1
autovacuum_analyze_scale_factor = 0.05

# Enable parallel queries
max_parallel_workers_per_gather = 2
max_parallel_workers = 8
max_parallel_maintenance_workers = 2
```

### Database Indexes
Create optimal indexes:

```sql
-- Create indexes for keyword searches
CREATE INDEX CONCURRENTLY idx_keywords_domain ON keywords(domain_id);
CREATE INDEX CONCURRENTLY idx_keywords_keyword_lower ON keywords(LOWER(keyword));
CREATE INDEX CONCURRENTLY idx_keywords_created ON keywords(created_at);
CREATE INDEX CONCURRENTLY idx_keywords_composite ON keywords(domain_id, is_active) WHERE is_active = true;

-- Create indexes for rank history
CREATE INDEX CONCURRENTLY idx_rank_history_keyword ON rank_history(keyword_id, checked_date DESC);
CREATE INDEX CONCURRENTLY idx_rank_history_date ON rank_history(checked_date);

-- Create indexes for domains
CREATE INDEX CONCURRENTLY idx_domains_user ON domains(user_id, is_active) WHERE is_active = true;

-- Analyze tables after creating indexes
ANALYZE keywords;
ANALYZE rank_history;
ANALYZE domains;
```

### Connection Pooling with PgBouncer
Install and configure PgBouncer:

```bash
sudo apt-get install pgbouncer
```

Configure `/etc/pgbouncer/pgbouncer.ini`:

```ini
[databases]
limeclicks = host=localhost port=5432 dbname=limeclicks

[pgbouncer]
listen_addr = 127.0.0.1
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
min_pool_size = 10
reserve_pool_size = 5
reserve_pool_timeout = 3
max_db_connections = 100
max_user_connections = 100
server_lifetime = 3600
server_idle_timeout = 600
server_connect_timeout = 15
server_login_retry = 15
query_timeout = 0
query_wait_timeout = 120
client_idle_timeout = 0
client_login_timeout = 60
admin_users = postgres
stats_users = stats, postgres
ignore_startup_parameters = extra_float_digits
```

## Redis Configuration

### Redis Optimization
Edit `/etc/redis/redis.conf`:

```conf
# Basic settings
bind 127.0.0.1
protected-mode yes
port 6379
tcp-backlog 511
timeout 0
tcp-keepalive 300

# Memory management
maxmemory 2gb
maxmemory-policy allkeys-lru
maxmemory-samples 5

# Persistence
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb
dir /var/lib/redis

# AOF
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
no-appendfsync-on-rewrite no
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# Slow log
slowlog-log-slower-than 10000
slowlog-max-len 128

# Client handling
maxclients 10000

# Threading
io-threads 4
io-threads-do-reads yes
```

### Redis Sentinel for High Availability
Configure `/etc/redis/sentinel.conf`:

```conf
port 26379
bind 127.0.0.1
sentinel monitor mymaster 127.0.0.1 6379 1
sentinel down-after-milliseconds mymaster 5000
sentinel parallel-syncs mymaster 1
sentinel failover-timeout mymaster 10000
```

## Nginx Optimization

### Nginx Configuration
Update `/etc/nginx/sites-available/limeclicks`:

```nginx
upstream limeclicks_app {
    least_conn;
    server 127.0.0.1:8000 fail_timeout=0;
    keepalive 32;
}

# Rate limiting zones
limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
limit_conn_zone $binary_remote_addr zone=addr:10m;

# Cache zones
proxy_cache_path /var/cache/nginx/limeclicks levels=1:2 keys_zone=limeclicks_cache:100m max_size=1g inactive=60m use_temp_path=off;

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;
    
    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Limits
    client_max_body_size 50M;
    client_body_buffer_size 1M;
    limit_conn addr 50;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss application/rss+xml application/atom+xml image/svg+xml text/x-js text/x-cross-domain-policy application/x-font-ttf application/x-font-opentype application/vnd.ms-fontobject image/x-icon;
    gzip_disable "msie6";
    gzip_comp_level 6;
    
    # Brotli compression (if module installed)
    # brotli on;
    # brotli_comp_level 6;
    # brotli_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss;
    
    # Static files with aggressive caching
    location /static/ {
        alias /home/muaaz/enterprise/limeclicks/staticfiles/;
        expires 365d;
        add_header Cache-Control "public, immutable";
        access_log off;
        
        # Enable gzip for static files
        gzip_static on;
        
        # Open file cache
        open_file_cache max=1000 inactive=20s;
        open_file_cache_valid 30s;
        open_file_cache_min_uses 2;
        open_file_cache_errors on;
    }
    
    location /media/ {
        alias /home/muaaz/enterprise/limeclicks/media/;
        expires 30d;
        add_header Cache-Control "public";
        access_log off;
    }
    
    # API endpoints with rate limiting
    location /api/ {
        limit_req zone=api burst=50 nodelay;
        
        proxy_pass http://limeclicks_app;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $http_host;
        proxy_redirect off;
        proxy_buffering off;
        
        # Timeouts for API
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
    
    # WebSocket support
    location /ws/ {
        proxy_pass http://limeclicks_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket timeouts
        proxy_connect_timeout 7d;
        proxy_send_timeout 7d;
        proxy_read_timeout 7d;
    }
    
    # Main application
    location / {
        limit_req zone=general burst=20 nodelay;
        
        # Try cache first for GET requests
        proxy_cache limeclicks_cache;
        proxy_cache_valid 200 302 10m;
        proxy_cache_valid 404 1m;
        proxy_cache_use_stale error timeout updating http_500 http_502 http_503 http_504;
        proxy_cache_background_update on;
        proxy_cache_lock on;
        add_header X-Cache-Status $upstream_cache_status;
        
        proxy_pass http://limeclicks_app;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $http_host;
        proxy_redirect off;
        
        # Connection settings
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        # Buffers
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
    
    # Block bad bots
    if ($http_user_agent ~* (crawler|spider|bot|scraper)) {
        return 403;
    }
    
    # Deny access to hidden files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
```

### Nginx System Configuration
Edit `/etc/nginx/nginx.conf`:

```nginx
user www-data;
worker_processes auto;
worker_rlimit_nofile 65535;
pid /run/nginx.pid;

events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
}

http {
    # Basic Settings
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    keepalive_requests 100;
    types_hash_max_size 2048;
    server_tokens off;
    client_body_timeout 30;
    client_header_timeout 30;
    send_timeout 30;
    
    # MIME Types
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    
    # Logging
    access_log /var/log/nginx/access.log combined buffer=16k flush=2m;
    error_log /var/log/nginx/error.log warn;
    
    # File Cache
    open_file_cache max=2000 inactive=20s;
    open_file_cache_valid 30s;
    open_file_cache_min_uses 2;
    open_file_cache_errors on;
    
    # Gzip Settings
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss application/rss+xml application/atom+xml image/svg+xml text/x-js text/x-cross-domain-policy application/x-font-ttf application/x-font-opentype application/vnd.ms-fontobject image/x-icon;
    
    # Virtual Host Configs
    include /etc/nginx/conf.d/*.conf;
    include /etc/nginx/sites-enabled/*;
}
```

## System Performance Tuning

### Kernel Parameters
Edit `/etc/sysctl.conf`:

```conf
# Network optimizations
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_keepalive_probes = 5
net.ipv4.tcp_keepalive_intvl = 15
net.ipv4.tcp_tw_reuse = 1
net.ipv4.ip_local_port_range = 1024 65535

# Memory optimizations
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5

# File system
fs.file-max = 2097152
fs.nr_open = 1048576

# Enable BBR congestion control
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
```

Apply settings:
```bash
sudo sysctl -p
```

### System Limits
Edit `/etc/security/limits.conf`:

```conf
* soft nofile 65535
* hard nofile 65535
* soft nproc 32768
* hard nproc 32768
www-data soft nofile 65535
www-data hard nofile 65535
```

## Monitoring Setup

### Install Monitoring Tools

```bash
# Prometheus Node Exporter
wget https://github.com/prometheus/node_exporter/releases/download/v1.6.1/node_exporter-1.6.1.linux-amd64.tar.gz
tar xvfz node_exporter-1.6.1.linux-amd64.tar.gz
sudo cp node_exporter-1.6.1.linux-amd64/node_exporter /usr/local/bin/
sudo useradd -rs /bin/false node_exporter

# Create systemd service for node_exporter
sudo tee /etc/systemd/system/node_exporter.service > /dev/null <<EOF
[Unit]
Description=Node Exporter
After=network.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable node_exporter
sudo systemctl start node_exporter

# Install netdata for real-time monitoring
bash <(curl -Ss https://my-netdata.io/kickstart.sh)
```

### Django Monitoring with django-prometheus

```bash
pip install django-prometheus
```

Add to `settings.py`:
```python
INSTALLED_APPS = [
    'django_prometheus',
    # ... other apps
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    # ... other middleware
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

# Database monitoring
DATABASES = {
    'default': {
        'ENGINE': 'django_prometheus.db.backends.postgresql',
        # ... rest of config
    }
}

# Cache monitoring
CACHES = {
    'default': {
        'BACKEND': 'django_prometheus.cache.backends.redis.RedisCache',
        # ... rest of config
    }
}
```

Add to `urls.py`:
```python
from django.urls import include, path

urlpatterns = [
    path('metrics/', include('django_prometheus.urls')),
    # ... other patterns
]
```

### Application Performance Monitoring

Create `/home/muaaz/enterprise/limeclicks/monitoring.py`:

```python
import psutil
import redis
import logging
from django.core.management.base import BaseCommand
from django.db import connection
from django.core.cache import cache
import time

logger = logging.getLogger(__name__)

class HealthCheck:
    @staticmethod
    def check_database():
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True, "Database is healthy"
        except Exception as e:
            return False, f"Database error: {str(e)}"
    
    @staticmethod
    def check_redis():
        try:
            cache.set('health_check', 'ok', 1)
            if cache.get('health_check') == 'ok':
                return True, "Redis is healthy"
            return False, "Redis write/read failed"
        except Exception as e:
            return False, f"Redis error: {str(e)}"
    
    @staticmethod
    def check_disk_space():
        usage = psutil.disk_usage('/')
        if usage.percent > 90:
            return False, f"Disk usage critical: {usage.percent}%"
        elif usage.percent > 80:
            return True, f"Disk usage warning: {usage.percent}%"
        return True, f"Disk usage normal: {usage.percent}%"
    
    @staticmethod
    def check_memory():
        memory = psutil.virtual_memory()
        if memory.percent > 90:
            return False, f"Memory usage critical: {memory.percent}%"
        elif memory.percent > 80:
            return True, f"Memory usage warning: {memory.percent}%"
        return True, f"Memory usage normal: {memory.percent}%"
    
    @staticmethod
    def check_cpu():
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 90:
            return False, f"CPU usage critical: {cpu_percent}%"
        elif cpu_percent > 80:
            return True, f"CPU usage warning: {cpu_percent}%"
        return True, f"CPU usage normal: {cpu_percent}%"

def run_health_checks():
    checks = {
        'database': HealthCheck.check_database(),
        'redis': HealthCheck.check_redis(),
        'disk': HealthCheck.check_disk_space(),
        'memory': HealthCheck.check_memory(),
        'cpu': HealthCheck.check_cpu(),
    }
    
    all_healthy = all(status for status, _ in checks.values())
    return all_healthy, checks
```

## Complete Deployment Commands

### Initial Setup

```bash
# 1. Install system dependencies
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv postgresql postgresql-contrib redis-server nginx supervisor pgbouncer

# 2. Install Python packages
cd /home/muaaz/enterprise/limeclicks
source venv/bin/activate
pip install --upgrade pip
pip install gunicorn gevent greenlet psycogreen django-prometheus psutil
pip install -r requirements.txt

# 3. Create necessary directories
sudo mkdir -p /var/log/gunicorn
sudo mkdir -p /var/run/gunicorn
sudo mkdir -p /var/cache/nginx/limeclicks
sudo chown -R www-data:www-data /var/log/gunicorn /var/run/gunicorn /var/cache/nginx/limeclicks

# 4. Set up database
sudo -u postgres psql -c "CREATE DATABASE limeclicks;"
sudo -u postgres psql -c "CREATE USER limeclicks_user WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE limeclicks TO limeclicks_user;"

# 5. Run migrations
python manage.py migrate
python manage.py collectstatic --noinput

# 6. Create superuser
python manage.py createsuperuser

# 7. Set permissions
sudo chown -R www-data:www-data /home/muaaz/enterprise/limeclicks
sudo chmod -R 755 /home/muaaz/enterprise/limeclicks
```

### Switching to Gevent Workers

```bash
# 1. Stop current service
sudo systemctl stop limeclicks

# 2. Install gevent dependencies
pip install gevent greenlet psycogreen

# 3. Create gunicorn config file
cat > /home/muaaz/enterprise/limeclicks/gunicorn_config.py << 'EOF'
import multiprocessing

bind = "127.0.0.1:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gevent"
worker_connections = 1000
keepalive = 5
timeout = 300
max_requests = 1000
max_requests_jitter = 50
preload_app = True
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
EOF

# 4. Update systemd service
sudo systemctl daemon-reload

# 5. Start service with gevent
sudo systemctl start limeclicks
sudo systemctl enable limeclicks

# 6. Verify gevent is running
sudo systemctl status limeclicks
ps aux | grep gunicorn
```

### Deployment Script

Create `/home/muaaz/enterprise/limeclicks/deploy.sh`:

```bash
#!/bin/bash
set -e

echo "Starting deployment..."

# Variables
PROJECT_DIR="/home/muaaz/enterprise/limeclicks"
VENV_DIR="$PROJECT_DIR/venv"
BACKUP_DIR="/var/backups/limeclicks"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup
echo "Creating backup..."
mkdir -p $BACKUP_DIR
pg_dump limeclicks > "$BACKUP_DIR/db_backup_$TIMESTAMP.sql"

# Activate virtual environment
source $VENV_DIR/bin/activate

# Pull latest code
echo "Pulling latest code..."
cd $PROJECT_DIR
git pull origin main

# Install/update dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Run migrations
echo "Running migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Run tests
echo "Running tests..."
python manage.py test

# Restart services
echo "Restarting services..."
sudo systemctl restart limeclicks
sudo systemctl restart nginx
sudo systemctl restart redis

# Health check
echo "Running health check..."
sleep 5
curl -f http://localhost/health || exit 1

echo "Deployment completed successfully!"
```

Make it executable:
```bash
chmod +x /home/muaaz/enterprise/limeclicks/deploy.sh
```

### Quick Commands Reference

```bash
# Service Management
sudo systemctl start limeclicks
sudo systemctl stop limeclicks
sudo systemctl restart limeclicks
sudo systemctl status limeclicks

# Logs
sudo journalctl -u limeclicks -f
tail -f /var/log/gunicorn/error.log
tail -f /var/log/nginx/error.log

# Performance Monitoring
htop
iostat -x 1
netstat -tupln
ss -tunlp

# Database
sudo -u postgres psql -d limeclicks
python manage.py dbshell

# Cache
redis-cli ping
redis-cli info stats

# Django Management
python manage.py shell
python manage.py showmigrations
python manage.py check --deploy

# Gunicorn Management
kill -HUP $(cat /var/run/gunicorn/limeclicks.pid)  # Graceful reload
kill -TERM $(cat /var/run/gunicorn/limeclicks.pid)  # Graceful shutdown
kill -USR1 $(cat /var/run/gunicorn/limeclicks.pid)  # Reopen log files
```

## Performance Testing

### Load Testing with Locust

```bash
pip install locust
```

Create `locustfile.py`:

```python
from locust import HttpUser, task, between

class WebsiteUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def index_page(self):
        self.client.get("/")
    
    @task(3)
    def view_keywords(self):
        self.client.get("/keywords/")
    
    @task(2)
    def api_endpoint(self):
        self.client.get("/api/keywords/")
```

Run load test:
```bash
locust -H http://localhost:8000 --users 100 --spawn-rate 10
```

## Troubleshooting

### Common Issues and Solutions

1. **High Memory Usage**
```bash
# Check memory usage by process
ps aux --sort=-%mem | head
# Restart Gunicorn workers
sudo systemctl reload limeclicks
```

2. **Slow Database Queries**
```bash
# Enable slow query log in PostgreSQL
sudo -u postgres psql -c "ALTER SYSTEM SET log_min_duration_statement = 100;"
sudo systemctl reload postgresql
# Check slow queries
tail -f /var/log/postgresql/postgresql-*.log | grep duration
```

3. **502 Bad Gateway**
```bash
# Check if Gunicorn is running
sudo systemctl status limeclicks
# Check Nginx error logs
tail -f /var/log/nginx/error.log
# Test Gunicorn directly
curl http://127.0.0.1:8000/health
```

4. **High CPU Usage**
```bash
# Find CPU-intensive processes
top -c
# Check Gunicorn worker status
ps aux | grep gunicorn
# Profile Python code
python -m cProfile manage.py runserver
```

## Security Hardening

### Firewall Configuration

```bash
# Install UFW
sudo apt-get install ufw

# Configure firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### Fail2ban Configuration

```bash
# Install fail2ban
sudo apt-get install fail2ban

# Create jail configuration
sudo tee /etc/fail2ban/jail.local > /dev/null <<EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true

[nginx-http-auth]
enabled = true

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
logpath = /var/log/nginx/error.log
EOF

sudo systemctl restart fail2ban
```

## Backup Strategy

### Automated Backup Script

Create `/home/muaaz/enterprise/limeclicks/backup.sh`:

```bash
#!/bin/bash

# Configuration
BACKUP_DIR="/var/backups/limeclicks"
PROJECT_DIR="/home/muaaz/enterprise/limeclicks"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# Create backup directory
mkdir -p $BACKUP_DIR

# Database backup
pg_dump limeclicks | gzip > "$BACKUP_DIR/db_$TIMESTAMP.sql.gz"

# Media files backup
tar -czf "$BACKUP_DIR/media_$TIMESTAMP.tar.gz" -C $PROJECT_DIR media/

# Configuration backup
tar -czf "$BACKUP_DIR/config_$TIMESTAMP.tar.gz" \
    /etc/nginx/sites-available/limeclicks \
    /etc/systemd/system/limeclicks.service \
    $PROJECT_DIR/.env

# Remove old backups
find $BACKUP_DIR -type f -mtime +$RETENTION_DAYS -delete

# Upload to remote storage (optional)
# aws s3 sync $BACKUP_DIR s3://your-backup-bucket/limeclicks/
```

### Cron Job for Automated Backups

```bash
# Add to crontab
crontab -e

# Daily backup at 2 AM
0 2 * * * /home/muaaz/enterprise/limeclicks/backup.sh
```

## Conclusion

This guide provides comprehensive optimization for your LimeClicks production deployment. The switch to gevent workers will significantly improve concurrent request handling, especially for I/O-bound operations like database queries and external API calls.

Key improvements:
- **Gevent workers**: Better concurrency with lower memory footprint
- **Database optimization**: Connection pooling, indexes, and query optimization
- **Caching**: Redis and Nginx caching for improved response times
- **Monitoring**: Comprehensive monitoring for proactive issue detection
- **Security**: Hardened configuration with SSL, firewall, and fail2ban

Monitor your application after implementing these changes and adjust configurations based on actual usage patterns.