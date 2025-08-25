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
}

# Queue configuration with priorities
app.conf.task_queues = (
    Queue('serp_high', Exchange('serp'), routing_key='serp.high', priority=10),
    Queue('serp_default', Exchange('serp'), routing_key='serp.default', priority=5),
    Queue('celery', Exchange('celery'), routing_key='celery'),  # Default queue
)

# Enable task priorities
app.conf.task_acks_late = True
app.conf.worker_prefetch_multiplier = 1
app.conf.task_default_priority = 5
app.conf.task_inherit_parent_priority = True

# Auto-discover tasks from Django apps
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery"""
    print(f'Request: {self.request!r}')