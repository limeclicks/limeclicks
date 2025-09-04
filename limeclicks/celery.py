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

# Define priority queues with routing for new domains vs scheduled audits
app.conf.task_routes = {
    # Keywords tasks
    'keywords.tasks.fetch_keyword_serp_html': {'queue': 'serp_default'},
    
    
    # Site audit tasks - High priority for new domains
    'site_audit.tasks.run_site_audit_high_priority': {'queue': 'audit_high_priority'},
    'site_audit.tasks.create_site_audit_for_new_project': {'queue': 'audit_high_priority'},
    
    # Site audit tasks - Regular priority for scheduled
    'site_audit.tasks.run_site_audit': {'queue': 'audit_scheduled'},
    'site_audit.tasks.check_scheduled_site_audits': {'queue': 'audit_scheduled'},
    'site_audit.tasks.create_site_audit_for_project': {'queue': 'audit_scheduled'},
    'site_audit.tasks.run_manual_site_audit': {'queue': 'audit_scheduled'},
    'site_audit.tasks.validate_screaming_frog_license': {'queue': 'audit_scheduled'},
}

# Queue configuration with priorities
# High priority queue for new domain audits (priority 10)
# Scheduled queue for repeating 30-day audits (priority 5)
app.conf.task_queues = (
    # High priority queue for new domain audits
    Queue('audit_high_priority', Exchange('audits'), routing_key='audits.high', priority=10),
    
    # Regular priority queue for scheduled/repeating audits
    Queue('audit_scheduled', Exchange('audits'), routing_key='audits.scheduled', priority=5),
    
    # SERP queues
    Queue('serp_high', Exchange('serp'), routing_key='serp.high', priority=8),
    Queue('serp_default', Exchange('serp'), routing_key='serp.default', priority=4),
    
    # Default queue
    Queue('celery', Exchange('celery'), routing_key='celery', priority=1),
)

# Enable task priorities
app.conf.task_acks_late = True
app.conf.worker_prefetch_multiplier = 1
app.conf.task_default_priority = 5
app.conf.task_inherit_parent_priority = True

# General worker configuration
app.conf.worker_concurrency = 4  # Total worker concurrency

# Auto-discover tasks from Django apps
app.autodiscover_tasks()

# Celery Beat schedule for periodic tasks
from celery.schedules import crontab

app.conf.beat_schedule = {
    # Keyword crawl scheduling
    'schedule-keyword-crawls': {
        'task': 'keywords.schedule_keyword_crawls',
        'schedule': crontab(minute='*/5'),  # Run every 5 minutes
        'kwargs': {'batch_size': 50}
    },
    'update-keyword-priorities': {
        'task': 'keywords.update_keyword_priorities',
        'schedule': crontab(hour=1, minute=0),  # Run daily at 1 AM
    },
    'reset-stuck-keywords': {
        'task': 'keywords.reset_stuck_keywords',
        'schedule': crontab(minute='*/30'),  # Run every 30 minutes
        'kwargs': {'stuck_hours': 2}
    },
    # Site audit tasks - Check for 30-day scheduled audits
    'check-scheduled-site-audits': {
        'task': 'site_audit.tasks.check_and_run_scheduled_audits',
        'schedule': crontab(hour=0, minute=30),  # Run daily at 12:30 AM to check for due audits
    },
    'cleanup-old-onpage-audits': {
        'task': 'site_audit.tasks.cleanup_old_site_audits',
        'schedule': crontab(hour=3, minute=0),  # Run daily at 3 AM
        'kwargs': {'days_to_keep': 90}
    },
    'cleanup-screaming-frog-data': {
        'task': 'site_audit.tasks.cleanup_screaming_frog_data',
        'schedule': crontab(hour='*/6'),  # Run every 6 hours
        'kwargs': {'hours_old': 24}  # Clean up data older than 24 hours
    },
    'validate-screaming-frog-license': {
        'task': 'site_audit.tasks.validate_screaming_frog_license',
        'schedule': crontab(day_of_week=1, hour=0, minute=0),  # Run weekly on Monday
    },
    'check-license-expiry': {
        'task': 'site_audit.tasks.check_license_expiry_reminder',
        'schedule': crontab(hour=9, minute=0),  # Run daily at 9 AM
    },
    # Keyword report scheduling
    'process-scheduled-keyword-reports': {
        'task': 'keywords.tasks_reports.process_scheduled_reports',
        'schedule': crontab(minute='*/15'),  # Run every 15 minutes to check for due reports
    },
    'cleanup-old-keyword-reports': {
        'task': 'keywords.tasks_reports.cleanup_old_reports',
        'schedule': crontab(hour=2, minute=0),  # Run daily at 2 AM
        'kwargs': {'days_to_keep': 90}
    },
}

@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery"""
    print(f'Request: {self.request!r}')