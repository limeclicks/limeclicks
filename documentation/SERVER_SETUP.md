# LimeClicks Server Setup Documentation

## Server Information
- **Server IP**: 91.230.110.86
- **OS**: Ubuntu 22.04 LTS
- **Project Path**: `/home/ubuntu/new-limeclicks`
- **Python Version**: 3.12.2 (via pyenv)
- **Node.js Version**: 22.18.0 (via nvm)

## Prerequisites

### 1. System Updates
```bash
sudo apt-get update
sudo apt-get upgrade -y
```

### 2. Essential Packages
```bash
sudo apt-get install -y \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    wget \
    curl \
    llvm \
    libncurses5-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libffi-dev \
    liblzma-dev \
    python3-openssl \
    git \
    nginx \
    redis-server \
    postgresql \
    postgresql-contrib
```

## Python Environment Setup

### 1. Install pyenv
```bash
curl https://pyenv.run | bash

# Add to ~/.bashrc
echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init --path)"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
source ~/.bashrc
```

### 2. Install Python 3.12.2
```bash
pyenv install 3.12.2
pyenv global 3.12.2
```

### 3. Clone Repository
```bash
cd /home/ubuntu
git clone https://github.com/limeclicks/limeclicks.git new-limeclicks
cd new-limeclicks
```

### 4. Install Python Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Node.js and Frontend Setup

### 1. Install NVM (Node Version Manager)
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc
```

### 2. Install Node.js 22.18.0
```bash
nvm install 22.18.0
nvm use 22.18.0
nvm alias default 22.18.0
```

### 3. Install Frontend Dependencies
```bash
cd /home/ubuntu/new-limeclicks
npm install
```

### 4. Build Frontend Assets
```bash
npx tailwindcss -i ./static/src/input.css -o ./staticfiles/dist/tailwind.css --minify
```

### ⚠️ Important: DaisyUI Version Compatibility Issue
**Issue**: DaisyUI v5 is incompatible with Tailwind CSS v3  
**Solution**: Use DaisyUI v4.12.24

```bash
npm uninstall daisyui
npm install daisyui@4.12.24
```

Verify versions in `package.json`:
```json
{
  "devDependencies": {
    "autoprefixer": "^10.4.21",
    "daisyui": "^4.12.24",
    "postcss": "^8.5.6",
    "tailwindcss": "^3.4.17"
  }
}
```

## Database Setup

### 1. Create PostgreSQL Database
```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE limeclicks;
CREATE USER limeclicks_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE limeclicks TO limeclicks_user;
\q
```

### 2. Configure Environment
Create `.env` file:
```bash
cat > /home/ubuntu/new-limeclicks/.env << 'EOF'
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_DOMAINS=['portal.limeclicks.com', '91.230.110.86']
DATABASE_URL=postgresql://limeclicks_user:your_password@localhost/limeclicks
REDIS_URL=redis://localhost:6379/0
SCRAPPER_API_KEY=your-api-key
SCREAMING_FROG_LICENSE=your-license-key
GOOGLE_PSI_KEY=your-google-key
EOF
```

### 3. Run Migrations
```bash
cd /home/ubuntu/new-limeclicks
python manage.py migrate
python manage.py collectstatic --noinput
```

## Screaming Frog SEO Spider Setup

### 1. Install Screaming Frog (Version 22.2)
```bash
# Download and install the DEB package
wget https://download.screamingfrog.co.uk/products/seo-spider/screamingfrogseospider_22.2_all.deb
sudo dpkg -i screamingfrogseospider_22.2_all.deb
sudo apt-get install -f  # Fix any dependency issues
```

### 2. Set Up License
```bash
mkdir -p ~/.ScreamingFrogSEOSpider
echo "your-license-key" > ~/.ScreamingFrogSEOSpider/licence.txt
```

### 3. Accept EULA (Critical Step!)
**Issue**: Screaming Frog requires EULA acceptance which blocks headless operation  
**Solution**: Create spider.config with EULA acceptance

```bash
printf "eula.accepted=15\n" > ~/.ScreamingFrogSEOSpider/spider.config
```

Verify:
```bash
cat ~/.ScreamingFrogSEOSpider/spider.config
# Should output: eula.accepted=15
```

### 4. Install Dependencies for Headless Operation
```bash
sudo apt-get install -y xvfb
```

## Systemd Services Setup

### 1. Gunicorn Service
```bash
sudo nano /etc/systemd/system/limeclicks-gunicorn.service
```

```ini
[Unit]
Description=LimeClicks Gunicorn
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/new-limeclicks
Environment="PATH=/home/ubuntu/.pyenv/shims:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/ubuntu/.pyenv/shims/gunicorn limeclicks.wsgi:application --bind 127.0.0.1:7650 --workers 3 --timeout 120
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### 2. Celery Service
```bash
sudo nano /etc/systemd/system/limeclicks-celery.service
```

```ini
[Unit]
Description=LimeClicks Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/new-limeclicks
Environment="PATH=/home/ubuntu/.pyenv/shims:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/ubuntu/.pyenv/shims/celery -A limeclicks worker -l info
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### 3. Celery Beat Service
```bash
sudo nano /etc/systemd/system/limeclicks-celery-beat.service
```

```ini
[Unit]
Description=LimeClicks Celery Beat
After=network.target redis.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/new-limeclicks
Environment="PATH=/home/ubuntu/.pyenv/shims:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/ubuntu/.pyenv/shims/celery -A limeclicks beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### 4. Enable and Start Services
```bash
sudo systemctl daemon-reload
sudo systemctl enable limeclicks-gunicorn limeclicks-celery limeclicks-celery-beat
sudo systemctl start limeclicks-gunicorn limeclicks-celery limeclicks-celery-beat
```

## Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/portal.limeclicks.com
```

```nginx
server {
    listen 80;
    server_name portal.limeclicks.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name portal.limeclicks.com;

    ssl_certificate /etc/nginx/ssl/portal.limeclicks.com.pem;
    ssl_certificate_key /etc/nginx/ssl/portal.limeclicks.com.key;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:7650;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 300s;
        proxy_read_timeout 300s;
    }

    location /static/ {
        alias /home/ubuntu/new-limeclicks/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /home/ubuntu/new-limeclicks/media/;
        expires 30d;
    }

    # SSE endpoints for real-time features
    location ~ ^/(api/keywords/serp-updates/|api/site-audit/updates/) {
        proxy_pass http://127.0.0.1:7650;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;
        proxy_read_timeout 86400s;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/portal.limeclicks.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Common Issues and Solutions

### Issue 1: Python Virtual Environment Path
**Problem**: Initially tried creating venv, but Python 3.12.2 was installed via pyenv  
**Solution**: Use pyenv Python directly without virtual environment
```bash
/home/ubuntu/.pyenv/shims/python
```

### Issue 2: DaisyUI Classes Not Appearing
**Problem**: DaisyUI v5 incompatible with Tailwind CSS v3  
**Solution**: Downgrade to DaisyUI v4.12.24
```bash
npm install daisyui@4.12.24
```

### Issue 3: Static Files 404 Error
**Problem**: Nginx couldn't serve static files  
**Solution**: 
1. Fix permissions: `chmod -R 755 /home/ubuntu/new-limeclicks/staticfiles`
2. Ensure correct nginx alias path
3. Run `python manage.py collectstatic`

### Issue 4: Screaming Frog EULA Blocking Headless Operation
**Problem**: EULA acceptance dialog prevents automated crawling  
**Solution**: Create spider.config with EULA acceptance
```bash
printf "eula.accepted=15\n" > ~/.ScreamingFrogSEOSpider/spider.config
```

### Issue 5: Celery Service Not Starting
**Problem**: Service type was set to 'forking' but Celery runs as simple process  
**Solution**: Change Type=forking to Type=simple in systemd service file

### Issue 6: Tailwind CSS Not Building Properly
**Problem**: CSS file missing or not including all styles  
**Solution**: 
1. Ensure tailwind.config.js scans all template directories
2. Build with: `npx tailwindcss -i ./static/src/input.css -o ./staticfiles/dist/tailwind.css --minify`

## Deployment Workflow

### Initial Deployment
1. Clone repository
2. Set up Python environment with pyenv
3. Install dependencies
4. Set up Node.js with nvm
5. Build frontend assets
6. Configure database
7. Run migrations
8. Set up systemd services
9. Configure nginx
10. Start all services

### Updates Deployment
```bash
cd /home/ubuntu/new-limeclicks
git pull origin main
pip install -r requirements.txt
npm install
npx tailwindcss -i ./static/src/input.css -o ./staticfiles/dist/tailwind.css --minify
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart limeclicks-gunicorn limeclicks-celery limeclicks-celery-beat
```

## Creating Admin User
```bash
cd /home/ubuntu/new-limeclicks
python manage.py createsuperuser
# Or programmatically:
python manage.py shell << EOF
from accounts.models import User
user = User.objects.create_superuser(
    username='admin',
    email='admin@example.com',
    password='secure_password'
)
user.email_verified = True
user.save()
EOF
```

## Monitoring Services

### Check Service Status
```bash
sudo systemctl status limeclicks-gunicorn
sudo systemctl status limeclicks-celery
sudo systemctl status limeclicks-celery-beat
```

### View Logs
```bash
sudo journalctl -u limeclicks-gunicorn -f
sudo journalctl -u limeclicks-celery -f
sudo journalctl -u limeclicks-celery-beat -f
```

### Nginx Logs
```bash
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

## Security Considerations

1. **Firewall Setup**
```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

2. **SSL Certificates**
- Use Cloudflare SSL certificates or Let's Encrypt
- Store in `/etc/nginx/ssl/`
- Set proper permissions: `chmod 600 /etc/nginx/ssl/*.key`

3. **Environment Variables**
- Never commit `.env` file to git
- Use strong SECRET_KEY
- Rotate API keys regularly

4. **Database Security**
- Use strong passwords
- Restrict database access to localhost
- Regular backups

## Troubleshooting

### Redis Connection Issues
```bash
sudo systemctl restart redis-server
redis-cli ping  # Should return PONG
```

### Database Connection Issues
```bash
sudo -u postgres psql -c "SELECT 1"  # Test PostgreSQL
python manage.py dbshell  # Test Django connection
```

### Static Files Not Loading
1. Check nginx error logs
2. Verify file permissions
3. Run collectstatic again
4. Check STATIC_ROOT and STATIC_URL settings

### Screaming Frog Not Working
1. Verify EULA acceptance: `cat ~/.ScreamingFrogSEOSpider/spider.config`
2. Check license: `cat ~/.ScreamingFrogSEOSpider/licence.txt`
3. Test with: `screamingfrogseospider --headless --crawl https://example.com --output-folder /tmp/test`

## Important Notes

- Always use git for deployments (no SCP/manual file copying)
- Test locally before deploying to server
- Keep Python and Node.js versions consistent between local and server
- Monitor disk space for Screaming Frog output files
- Regular database backups are essential
- Use systemd for process management (not screen/tmux)

## Contact & Support

For issues or questions, please refer to the project repository or contact the development team.

---
*Last Updated: September 2025*
*Server Setup Version: 1.0*