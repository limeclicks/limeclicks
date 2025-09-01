# LimeClicks Production Deployment Guide

This guide provides comprehensive instructions for deploying LimeClicks to a production Ubuntu server.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Initial Server Setup](#initial-server-setup)
- [Automated Installation](#automated-installation)
- [Manual Installation Steps](#manual-installation-steps)
- [Post-Installation Configuration](#post-installation-configuration)
- [Service Management](#service-management)
- [Monitoring and Maintenance](#monitoring-and-maintenance)
- [Troubleshooting](#troubleshooting)
- [CI/CD Setup](#cicd-setup)

## Prerequisites

### Server Requirements
- Ubuntu 20.04 LTS or 22.04 LTS
- Minimum 2 CPU cores
- Minimum 4GB RAM (8GB recommended)
- 20GB+ available disk space
- Root or sudo access
- Domain name pointed to server IP

### Required Accounts/Services
- GitHub repository with the project code
- PostgreSQL database (installed during setup)
- Redis server (installed during setup)
- Domain name
- SSL certificate (via Let's Encrypt)
- Optional: Cloudflare account for CDN/DDoS protection

## Initial Server Setup

### 1. Connect to Your Server
```bash
ssh root@your-server-ip
```

### 2. Create Initial User (if using root)
```bash
adduser deploy
usermod -aG sudo deploy
su - deploy
```

### 3. Clone the Repository
```bash
sudo mkdir -p /home/limeclicks
sudo chown deploy:deploy /home/limeclicks
cd /home/limeclicks
git clone https://github.com/your-username/limeclicks.git
cd limeclicks
```

## Automated Installation

### Quick Setup (Recommended)
```bash
# Make the script executable
chmod +x deploy/setup_production.sh

# Run the complete setup
sudo ./deploy/setup_production.sh --domain=yourdomain.com

# Or run without system packages if already installed
sudo ./deploy/setup_production.sh --skip-system --domain=yourdomain.com
```

The script will automatically:
- Install system dependencies
- Create project user
- Install pyenv and Python 3.12.0
- Install nvm and Node.js 20.10.0
- Setup PostgreSQL database
- Install project dependencies
- Configure systemd services
- Setup Nginx (optional)
- Configure SSL with Let's Encrypt
- Setup firewall rules
- Create monitoring scripts

## Manual Installation Steps

If you prefer manual installation or need to customize the setup:

### 1. System Dependencies
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
    libncurses5-dev libncursesw5-dev xz-utils tk-dev libffi-dev \
    liblzma-dev python3-openssl git nginx redis-server \
    postgresql postgresql-contrib certbot python3-certbot-nginx
```

### 2. Create Project User
```bash
sudo useradd -m -s /bin/bash limeclicks
sudo usermod -aG sudo limeclicks
```

### 3. Install pyenv
```bash
sudo -u limeclicks bash
curl https://pyenv.run | bash

# Add to ~/.bashrc
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
source ~/.bashrc

# Install Python
pyenv install 3.12.0
pyenv global 3.12.0
```

### 4. Install nvm and Node.js
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc
nvm install 20.10.0
nvm use 20.10.0
nvm alias default 20.10.0
```

### 5. Setup PostgreSQL
```bash
sudo -u postgres psql
CREATE USER limeclicks WITH PASSWORD 'secure-password';
CREATE DATABASE limeclicks_db OWNER limeclicks;
GRANT ALL PRIVILEGES ON DATABASE limeclicks_db TO limeclicks;
\q
```

### 6. Setup Python Virtual Environment
```bash
cd /home/limeclicks/limeclicks
python -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

### 7. Configure Environment Variables
```bash
cp deploy/.env.template /home/limeclicks/.env
nano /home/limeclicks/.env
# Update with your actual values
```

### 8. Setup Systemd Services
```bash
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable limeclicks-gunicorn limeclicks-celery limeclicks-celerybeat
```

### 9. Configure Nginx
```bash
# Replace ${DOMAIN_NAME} with your actual domain
sudo envsubst '${DOMAIN_NAME}' < deploy/nginx/limeclicks.conf > /etc/nginx/sites-available/limeclicks
sudo ln -s /etc/nginx/sites-available/limeclicks /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 10. Setup SSL Certificate
```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

## Post-Installation Configuration

### 1. Update Environment Variables
Edit `/home/limeclicks/.env` and update:
- `SECRET_KEY` - Generate a new secret key
- `ALLOWED_HOSTS` - Add your domain
- Database credentials
- Email settings
- API keys

### 2. Initialize Database
```bash
sudo -u limeclicks bash -c "cd /home/limeclicks/limeclicks && source venv/bin/activate && python manage.py migrate"
sudo -u limeclicks bash -c "cd /home/limeclicks/limeclicks && source venv/bin/activate && python manage.py collectstatic --noinput"
```

### 3. Create Superuser
```bash
sudo -u limeclicks bash -c "cd /home/limeclicks/limeclicks && source venv/bin/activate && python manage.py createsuperuser"
```

### 4. Create Required Directories
```bash
sudo mkdir -p /var/log/limeclicks
sudo mkdir -p /var/run/limeclicks
sudo chown -R limeclicks:limeclicks /var/log/limeclicks
sudo chown -R limeclicks:limeclicks /var/run/limeclicks
```

## Service Management

### Start Services
```bash
sudo systemctl start limeclicks-gunicorn
sudo systemctl start limeclicks-celery
sudo systemctl start limeclicks-celerybeat
sudo systemctl start redis
sudo systemctl start nginx
```

### Check Service Status
```bash
sudo systemctl status limeclicks-gunicorn
sudo systemctl status limeclicks-celery
sudo systemctl status limeclicks-celerybeat
```

### View Logs
```bash
# Gunicorn logs
sudo journalctl -u limeclicks-gunicorn -f
sudo tail -f /var/log/limeclicks/gunicorn-*.log

# Celery logs
sudo journalctl -u limeclicks-celery -f
sudo tail -f /var/log/limeclicks/celery*.log

# Nginx logs
sudo tail -f /var/log/nginx/limeclicks_*.log
```

### Restart Services
```bash
sudo systemctl restart limeclicks-gunicorn
sudo systemctl restart limeclicks-celery
sudo systemctl restart limeclicks-celerybeat
```

## Monitoring and Maintenance

### Health Check Script
A health check script is automatically installed at `/usr/local/bin/limeclicks-health-check.sh` and runs every 5 minutes via cron.

### Manual Health Check
```bash
sudo /usr/local/bin/limeclicks-health-check.sh
```

### Update Deployment
Use the update script for deployments:
```bash
sudo /usr/local/bin/limeclicks-update.sh
```

Or manually:
```bash
cd /home/limeclicks/limeclicks
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart limeclicks-gunicorn limeclicks-celery limeclicks-celerybeat
```

### Database Backup
```bash
# Create backup
sudo -u postgres pg_dump limeclicks_db > backup_$(date +%Y%m%d).sql

# Restore backup
sudo -u postgres psql limeclicks_db < backup_20240101.sql
```

## Troubleshooting

### Common Issues

#### 1. Gunicorn Not Starting
```bash
# Check logs
sudo journalctl -u limeclicks-gunicorn -n 50

# Check socket file
ls -la /home/limeclicks/limeclicks/gunicorn.sock

# Test manually
cd /home/limeclicks/limeclicks
source venv/bin/activate
gunicorn limeclicks.wsgi:application --bind 0.0.0.0:8000
```

#### 2. Celery Issues
```bash
# Check Redis connection
redis-cli ping

# Test Celery manually
cd /home/limeclicks/limeclicks
source venv/bin/activate
celery -A limeclicks worker --loglevel=info
```

#### 3. Static Files Not Loading
```bash
# Re-collect static files
cd /home/limeclicks/limeclicks
source venv/bin/activate
python manage.py collectstatic --clear --noinput
```

#### 4. Database Connection Issues
```bash
# Test PostgreSQL connection
sudo -u postgres psql -c "SELECT 1"

# Check database exists
sudo -u postgres psql -l | grep limeclicks
```

#### 5. Permission Issues
```bash
# Fix ownership
sudo chown -R limeclicks:limeclicks /home/limeclicks/limeclicks
sudo chown -R limeclicks:limeclicks /var/log/limeclicks
```

### Emergency Rollback
```bash
cd /home/limeclicks/limeclicks
git log --oneline -10  # Find the commit to rollback to
git reset --hard <commit-hash>
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart limeclicks-gunicorn limeclicks-celery
```

## CI/CD Setup

### GitHub Actions Workflow
Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to server
        uses: appleboy/ssh-action@v0.1.5
        with:
          host: ${{ secrets.HOST }}
          username: ${{ secrets.USERNAME }}
          key: ${{ secrets.SSH_KEY }}
          script: |
            sudo /usr/local/bin/limeclicks-update.sh
```

### Setup GitHub Secrets
Add to your repository secrets:
- `HOST`: Your server IP or domain
- `USERNAME`: Deploy user (limeclicks)
- `SSH_KEY`: Private SSH key for deployment

### Setup SSH Key for Deployment
```bash
# On your local machine
ssh-keygen -t ed25519 -C "deploy@limeclicks"

# Copy public key to server
ssh-copy-id -i ~/.ssh/id_ed25519.pub limeclicks@your-server

# Add private key to GitHub secrets
cat ~/.ssh/id_ed25519
```

## Security Checklist

- [ ] Change default Django admin URL
- [ ] Set strong SECRET_KEY
- [ ] Enable firewall (ufw)
- [ ] Configure fail2ban
- [ ] Setup SSL certificate
- [ ] Disable root SSH login
- [ ] Use SSH keys instead of passwords
- [ ] Regular security updates
- [ ] Setup monitoring (e.g., Sentry)
- [ ] Configure backup strategy
- [ ] Set up log rotation
- [ ] Review and restrict file permissions

## Performance Optimization

### 1. Enable Caching
Configure Redis caching in Django settings.

### 2. Optimize Database
```bash
# Analyze database
sudo -u postgres psql limeclicks_db -c "ANALYZE;"

# Create indexes as needed
```

### 3. Configure Gunicorn Workers
Adjust in systemd service file:
```
Workers = (2 × CPU cores) + 1
```

### 4. Enable Gzip Compression
Already configured in Nginx.

### 5. Use CDN for Static Files
Configure Cloudflare or another CDN service.

## Support

For issues or questions:
1. Check the logs first
2. Review this documentation
3. Check Django debug toolbar (development only)
4. Contact system administrator

## License

[Your License Here]