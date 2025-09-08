# LimeClicks Server Setup Guide

## Server Details
- **Server**: ubuntu@91.230.110.86
- **Application Path**: `/home/ubuntu/new-limeclicks`
- **Python Version**: pyenv 3.12.2

## System Services

### 1. limeclicks-gunicorn
- **Service File**: `/etc/systemd/system/limeclicks-gunicorn.service`
- **Type**: Gunicorn with Gevent workers
- **Config File**: `/home/ubuntu/new-limeclicks/gunicorn_config_production.py`
- **Resource Limits**: 
  - File descriptors: 65536
  - Processes: 4096

### 2. limeclicks-celery
- **Service File**: `/etc/systemd/system/limeclicks-celery.service`
- **Type**: Celery Worker
- **Configuration**:
  - Concurrency: 2
  - Max tasks per child: 50
  - Time limit: 300s
  - Pool: prefork
  - Broker: redis://localhost:6379/0

### 3. limeclicks-celerybeat
- **Service File**: `/etc/systemd/system/limeclicks-celerybeat.service`
- **Type**: Celery Beat Scheduler
- **Schedule DB**: `/home/ubuntu/new-limeclicks/celerybeat-schedule.db`

## Log Files
- **Celery Worker**: `/home/ubuntu/new-limeclicks/logs/celery-worker.log`
- **Celery Beat**: `/home/ubuntu/new-limeclicks/logs/celery-beat.log`
- **Gunicorn Access**: `/home/ubuntu/new-limeclicks/logs/gunicorn-access.log`
- **Gunicorn Error**: `/home/ubuntu/new-limeclicks/logs/gunicorn-error.log`

## Service Management Commands

### Check Service Status
```bash
sudo systemctl status limeclicks-gunicorn
sudo systemctl status limeclicks-celery
sudo systemctl status limeclicks-celerybeat
```

### Restart Services
```bash
sudo systemctl restart limeclicks-gunicorn
sudo systemctl restart limeclicks-celery
sudo systemctl restart limeclicks-celerybeat
```

### View Logs
```bash
# Real-time logs
sudo journalctl -f -u limeclicks-gunicorn
sudo journalctl -f -u limeclicks-celery
sudo journalctl -f -u limeclicks-celerybeat

# Application logs
tail -f /home/ubuntu/new-limeclicks/logs/celery-worker.log
tail -f /home/ubuntu/new-limeclicks/logs/celery-beat.log
tail -f /home/ubuntu/new-limeclicks/logs/gunicorn-error.log
```

## Environment Configuration
- Environment file: `/home/ubuntu/new-limeclicks/.env`
- Django settings: `limeclicks.settings`
- Redis: localhost:6379

## Deployment Steps
1. SSH to server: `ssh ubuntu@91.230.110.86`
2. Navigate to app: `cd /home/ubuntu/new-limeclicks`
3. Activate pyenv: `pyenv local 3.12.2`
4. Pull latest code: `git pull origin main`
5. Install dependencies: `pip install -r requirements.txt`
6. Run migrations: `python manage.py migrate`
7. Collect static: `python manage.py collectstatic --noinput`
8. Restart services:
   ```bash
   sudo systemctl restart limeclicks-gunicorn
   sudo systemctl restart limeclicks-celery
   sudo systemctl restart limeclicks-celerybeat
   ```