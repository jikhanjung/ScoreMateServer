"""
Celery configuration for ScoreMateServer
"""
import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scoremateserver.settings')

app = Celery('scoremateserver')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Development/testing configuration
if settings.DEBUG:
    # Run tasks synchronously in development
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup"""
    print(f'Request: {self.request!r}')


# Task routing (optional - for advanced setups)
app.conf.task_routes = {
    'tasks.pdf_tasks.*': {'queue': 'pdf_processing'},
    'tasks.file_tasks.*': {'queue': 'file_operations'},
}

# Task result expires after 1 hour
app.conf.result_expires = 3600

# Task retry configuration
app.conf.task_acks_late = True
app.conf.task_reject_on_worker_lost = True

# Monitoring and logging
app.conf.worker_send_task_events = True
app.conf.task_send_sent_event = True