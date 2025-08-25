"""
Celery configuration for LimeClicks
"""

import os
from celery import Celery
from kombu import Queue, Exchange

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')

# Create Celery app
app = Celery('limeclicks')

# Load config from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Define priority queues
app.conf.task_routes = {
    'keywords.tasks.fetch_keyword_serp_html': {'queue': 'serp_default'},
    'performance_audit.tasks.run_lighthouse_audit': {'queue': 'performance_audit'},
    'performance_audit.tasks.check_scheduled_audits': {'queue': 'performance_audit'},
    'performance_audit.tasks.create_audit_for_project': {'queue': 'performance_audit'},
    'performance_audit.tasks.run_manual_audit': {'queue': 'performance_audit'},
    'site_audit.tasks.run_site_audit': {'queue': 'onpage'},
    'site_audit.tasks.check_scheduled_site_audits': {'queue': 'onpage'},
    'site_audit.tasks.create_site_audit_for_project': {'queue': 'onpage'},
    'site_audit.tasks.run_manual_site_audit': {'queue': 'onpage'},
    'site_audit.tasks.validate_screaming_frog_license': {'queue': 'onpage'},
}

# Queue configuration with priorities
app.conf.task_queues = (
    Queue('serp_high', Exchange('serp'), routing_key='serp.high', priority=10),
    Queue('serp_default', Exchange('serp'), routing_key='serp.default', priority=5),
    Queue('performance_audit', Exchange('performance_audit'), routing_key='performance_audit', priority=3),
    Queue('onpage', Exchange('onpage'), routing_key='onpage', priority=3),
    Queue('celery', Exchange('celery'), routing_key='celery'),  # Default queue
)

# Enable task priorities
app.conf.task_acks_late = True
app.conf.worker_prefetch_multiplier = 1
app.conf.task_default_priority = 5
app.conf.task_inherit_parent_priority = True

# Auto-discover tasks from Django apps
app.autodiscover_tasks()

# Celery Beat schedule for periodic tasks
from celery.schedules import crontab

app.conf.beat_schedule = {
    'check-scheduled-audits': {
        'task': 'performance_audit.tasks.check_scheduled_audits',
        'schedule': crontab(minute=0),  # Run every hour
    },
    'cleanup-old-audits': {
        'task': 'performance_audit.tasks.cleanup_old_audits',
        'schedule': crontab(hour=2, minute=0),  # Run daily at 2 AM
        'kwargs': {'days_to_keep': 90}
    },
    'check-scheduled-onpage-audits': {
        'task': 'site_audit.tasks.check_scheduled_site_audits',
        'schedule': crontab(hour='*/6'),  # Run every 6 hours
    },
    'cleanup-old-onpage-audits': {
        'task': 'site_audit.tasks.cleanup_old_site_audits',
        'schedule': crontab(hour=3, minute=0),  # Run daily at 3 AM
        'kwargs': {'days_to_keep': 90}
    },
    'validate-screaming-frog-license': {
        'task': 'site_audit.tasks.validate_screaming_frog_license',
        'schedule': crontab(day_of_week=1, hour=0, minute=0),  # Run weekly on Monday
    },
    'check-license-expiry': {
        'task': 'site_audit.tasks.check_license_expiry_reminder',
        'schedule': crontab(hour=9, minute=0),  # Run daily at 9 AM
    },
}

@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery"""
    print(f'Request: {self.request!r}')