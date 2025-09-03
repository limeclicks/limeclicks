# LimeClicks Deployment Instructions

## Prerequisites
- Ubuntu Server (20.04 or higher)
- Python 3.12.2 (via pyenv)
- Node.js 22.x (via nvm)
- PostgreSQL
- Redis
- Nginx

## 1. Python Environment Setup

### Install Python 3.12.2 via pyenv
```bash
# Set Python version for the project
cd /home/ubuntu/new-limeclicks
pyenv local 3.12.2
```

### Install Python Dependencies
```bash
# No virtual environment needed - using pyenv directly
export PATH="$HOME/.pyenv/shims:$PATH"
export PYENV_VERSION=3.12.2
pip install -r requirements.txt
```

## 2. Frontend Setup (Tailwind CSS with DaisyUI)

### Install Node.js 22 via NVM
```bash
source ~/.nvm/nvm.sh
nvm install 22
nvm use 22
```

### Create package.json
```bash
cat > package.json << 'EOL'
{
  "name": "limeclicks",
  "version": "1.0.0",
  "scripts": {
    "build-css": "npx tailwindcss -i ./static/src/input.css -o ./staticfiles/dist/tailwind.css --minify"
  },
  "devDependencies": {
    "tailwindcss": "^3.3.0",
    "daisyui": "^4.0.0"
  }
}
EOL
```

### Create Tailwind Configuration
```bash
cat > tailwind.config.js << 'EOL'
module.exports = {
  content: [
    "./templates/**/*.html",
    "./templates/**/*.js",
    "./static/src/**/*.js",
  ],
  theme: {
    extend: {},
  },
  plugins: [require("daisyui")],
  daisyui: {
    themes: ["light", "dark", "cupcake", "corporate"],
  },
}
EOL
```

### Create Tailwind Input CSS
```bash
mkdir -p static/src
cat > static/src/input.css << 'EOL'
@tailwind base;
@tailwind components;
@tailwind utilities;
EOL
```

### Install Dependencies and Build CSS
```bash
# Install npm packages
npm install

# Build Tailwind CSS with DaisyUI
npx tailwindcss -i ./static/src/input.css -o ./staticfiles/dist/tailwind.css --minify

# Fix permissions
chmod -R 755 staticfiles/
```

### Create Build Script for Future Use
```bash
cat > build-css.sh << 'EOL'
#!/bin/bash
source ~/.nvm/nvm.sh
nvm use 22
npx tailwindcss -i ./static/src/input.css -o ./staticfiles/dist/tailwind.css --minify
chmod 755 ./staticfiles/dist/tailwind.css
echo "Tailwind CSS built successfully!"
EOL
chmod +x build-css.sh
```

## 3. Django Static Files Setup

### Collect Static Files
```bash
export PATH="$HOME/.pyenv/shims:$PATH"
export PYENV_VERSION=3.12.2
python manage.py collectstatic --noinput

# Copy custom static files
cp -r static/* staticfiles/

# Fix permissions for nginx
chmod -R 755 /home/ubuntu
chmod -R 755 /home/ubuntu/new-limeclicks
chmod -R 755 /home/ubuntu/new-limeclicks/staticfiles
```

## 4. Environment Configuration

### Create .env file
```bash
# Copy from template
cp deploy/.env.template .env

# Edit with your configuration
nano .env
```

Required environment variables:
- `DEBUG=False`
- `SECRET_KEY=<your-secret-key>`
- `DATABASE_URL=postgresql://user:password@localhost:5432/dbname`
- `REDIS_URL=redis://localhost:6379/0`
- `GOOGLE_RECAPTCHA_SITE_KEY=<your-site-key>`
- `GOOGLE_RECAPTCHA_SECRET_KEY=<your-secret-key>`

## 5. Database Setup

```bash
# Run migrations
python manage.py migrate

# Create superuser (if needed)
python manage.py createsuperuser
```

## 6. Systemd Services Setup

### Create Gunicorn Service
```bash
sudo tee /etc/systemd/system/limeclicks-gunicorn.service > /dev/null << 'EOL'
[Unit]
Description=LimeClicks Gunicorn Application Server
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/new-limeclicks
Environment="PATH=/home/ubuntu/.pyenv/shims:/home/ubuntu/.pyenv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYENV_ROOT=/home/ubuntu/.pyenv"
Environment="PYENV_VERSION=3.12.2"
EnvironmentFile=/home/ubuntu/new-limeclicks/.env

ExecStart=/home/ubuntu/.pyenv/shims/gunicorn \
          --workers 4 \
          --worker-class sync \
          --bind 0.0.0.0:7650 \
          --timeout 300 \
          --access-logfile /home/ubuntu/new-limeclicks/logs/gunicorn-access.log \
          --error-logfile /home/ubuntu/new-limeclicks/logs/gunicorn-error.log \
          --log-level info \
          --capture-output \
          limeclicks.wsgi:application

Restart=always
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true
LimitNOFILE=65536
LimitNPROC=4096
KillMode=mixed
KillSignal=SIGQUIT

[Install]
WantedBy=multi-user.target
EOL
```

### Create Celery Worker Service
```bash
sudo tee /etc/systemd/system/limeclicks-celery.service > /dev/null << 'EOL'
[Unit]
Description=LimeClicks Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/new-limeclicks
Environment="PATH=/home/ubuntu/.pyenv/shims:/home/ubuntu/.pyenv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYENV_ROOT=/home/ubuntu/.pyenv"
Environment="PYENV_VERSION=3.12.2"
EnvironmentFile=/home/ubuntu/new-limeclicks/.env
Environment="CELERY_BROKER_URL=redis://localhost:6379/0"
Environment="CELERY_RESULT_BACKEND=redis://localhost:6379/0"

ExecStart=/home/ubuntu/.pyenv/shims/celery \
          -A limeclicks \
          worker \
          --loglevel=info \
          --concurrency=4 \
          --max-tasks-per-child=1000 \
          --time-limit=300 \
          --soft-time-limit=240 \
          --logfile=/home/ubuntu/new-limeclicks/logs/celery-worker.log

Restart=always
RestartSec=10
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
EOL
```

### Create Celery Beat Service
```bash
sudo tee /etc/systemd/system/limeclicks-celerybeat.service > /dev/null << 'EOL'
[Unit]
Description=LimeClicks Celery Beat Scheduler
After=network.target redis.service limeclicks-celery.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/new-limeclicks
Environment="PATH=/home/ubuntu/.pyenv/shims:/home/ubuntu/.pyenv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYENV_ROOT=/home/ubuntu/.pyenv"
Environment="PYENV_VERSION=3.12.2"
EnvironmentFile=/home/ubuntu/new-limeclicks/.env
Environment="CELERY_BROKER_URL=redis://localhost:6379/0"
Environment="CELERY_RESULT_BACKEND=redis://localhost:6379/0"

ExecStart=/home/ubuntu/.pyenv/shims/celery \
          -A limeclicks \
          beat \
          --loglevel=info \
          --logfile=/home/ubuntu/new-limeclicks/logs/celery-beat.log \
          --schedule=/home/ubuntu/new-limeclicks/celerybeat-schedule.db

Restart=always
RestartSec=10
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
EOL
```

### Enable and Start Services
```bash
# Create logs directory
mkdir -p /home/ubuntu/new-limeclicks/logs

# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable limeclicks-gunicorn limeclicks-celery limeclicks-celerybeat

# Start services
sudo systemctl start limeclicks-gunicorn limeclicks-celery limeclicks-celerybeat

# Check status
sudo systemctl status limeclicks-gunicorn limeclicks-celery limeclicks-celerybeat
```

## 7. Nginx Configuration

### Create Nginx Site Configuration
```bash
sudo tee /etc/nginx/sites-available/portal.limeclicks.com > /dev/null << 'EOL'
# HTTP to HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name portal.limeclicks.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS Server Block
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name portal.limeclicks.com;

    # SSL certificates
    ssl_certificate /etc/ssl/certs/origin.crt;
    ssl_certificate_key /etc/ssl/certs/origin.key;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Cloudflare real IP configuration
    set_real_ip_from 173.245.48.0/20;
    set_real_ip_from 103.21.244.0/22;
    set_real_ip_from 103.22.200.0/22;
    set_real_ip_from 103.31.4.0/22;
    set_real_ip_from 141.101.64.0/18;
    set_real_ip_from 108.162.192.0/18;
    set_real_ip_from 190.93.240.0/20;
    set_real_ip_from 188.114.96.0/20;
    set_real_ip_from 197.234.240.0/22;
    set_real_ip_from 198.41.128.0/17;
    set_real_ip_from 162.158.0.0/15;
    set_real_ip_from 104.16.0.0/13;
    set_real_ip_from 104.24.0.0/14;
    set_real_ip_from 172.64.0.0/13;
    set_real_ip_from 131.0.72.0/22;
    real_ip_header CF-Connecting-IP;

    # Logging
    access_log /var/log/nginx/portal.limeclicks.com_access.log;
    error_log /var/log/nginx/portal.limeclicks.com_error.log;

    client_max_body_size 100M;

    # Static files
    location /static/ {
        alias /home/ubuntu/new-limeclicks/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /home/ubuntu/new-limeclicks/media/;
        expires 7d;
        add_header Cache-Control "public";
    }

    # Main application
    location / {
        proxy_pass http://127.0.0.1:7650;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
    }

    # SSE endpoints
    location ~ ^/(api/sse|sse|events) {
        proxy_pass http://127.0.0.1:7650;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
        chunked_transfer_encoding on;
        tcp_nodelay on;
    }

    # WebSocket support
    location /ws/ {
        proxy_pass http://127.0.0.1:7650;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_buffering off;
    }
}
EOL

# Enable site
sudo ln -sf /etc/nginx/sites-available/portal.limeclicks.com /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

## 8. Post-Deployment Tasks

### Verify Services
```bash
# Check all services are running
sudo systemctl status limeclicks-gunicorn
sudo systemctl status limeclicks-celery
sudo systemctl status limeclicks-celerybeat
sudo systemctl status redis-server
sudo systemctl status nginx

# Check application logs
tail -f /home/ubuntu/new-limeclicks/logs/gunicorn-error.log
tail -f /home/ubuntu/new-limeclicks/logs/celery-worker.log
```

### Rebuilding CSS (when templates change)
```bash
cd /home/ubuntu/new-limeclicks
./build-css.sh
```

### Updating Static Files
```bash
cd /home/ubuntu/new-limeclicks
python manage.py collectstatic --noinput
cp -r static/* staticfiles/
chmod -R 755 staticfiles/
```

## 9. Troubleshooting

### Static Files Not Loading
1. Check permissions: `chmod -R 755 /home/ubuntu/new-limeclicks/staticfiles`
2. Rebuild CSS: `./build-css.sh`
3. Check nginx error logs: `sudo tail -f /var/log/nginx/portal.limeclicks.com_error.log`

### Services Not Starting
1. Check service logs: `sudo journalctl -xeu limeclicks-gunicorn`
2. Verify Python path: `which python` (should show pyenv shim)
3. Check .env file exists and has correct values

### Database Connection Issues
1. Verify PostgreSQL is running: `sudo systemctl status postgresql`
2. Check DATABASE_URL in .env file
3. Test connection: `python manage.py dbshell`

## 10. Security Notes

- Always use HTTPS in production
- Keep SECRET_KEY secure and never commit it
- Regularly update dependencies
- Use strong database passwords
- Configure firewall rules appropriately
- Keep SSL certificates up to date

## Service Ports
- Django/Gunicorn: 7650
- PostgreSQL: 5432
- Redis: 6379
- Nginx: 80, 443

## Important Paths
- Application: `/home/ubuntu/new-limeclicks`
- Static files: `/home/ubuntu/new-limeclicks/staticfiles`
- Logs: `/home/ubuntu/new-limeclicks/logs`
- Services: `/etc/systemd/system/limeclicks-*.service`
- Nginx config: `/etc/nginx/sites-available/portal.limeclicks.com`
