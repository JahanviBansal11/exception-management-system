"""
Celery configuration for GRC Automation System.
Event-driven async task processing for reminders, escalations, and notifications.
"""

import os
from celery import Celery
from celery.schedules import crontab

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grc_backend.settings')

app = Celery('grc_backend')

# Load configuration from Django settings (with CELERY prefix)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# ============================================
# CELERY BEAT SCHEDULE (Periodic Tasks)
# ============================================
app.conf.beat_schedule = {
    # Evaluate pending approvals every 5 minutes
    'evaluate-pending-reminders': {
        'task': 'exceptions.tasks.evaluate_pending_approvals',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    # Evaluate active exceptions every 10 minutes
    'evaluate-active-exceptions': {
        'task': 'exceptions.tasks.evaluate_active_exceptions',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
    # Check for expired approvals every 1 hour
    'escalate-expired-approvals': {
        'task': 'exceptions.tasks.escalate_expired_approvals',
        'schedule': crontab(minute=0),  # Every hour
    },
    # Close approved exceptions once validity window ends
    'close-expired-exceptions': {
        'task': 'exceptions.tasks.close_expired_exceptions',
        'schedule': crontab(minute=0),  # Every hour
    },
}

# ============================================
# CELERY CONFIGURATION
# ============================================
app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task execution settings
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes hard limit
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
    
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    
    # Retry settings
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f'Request: {self.request!r}')
