"""
Celery configuration for PTS project.
Used for background tasks like notifications and deadline reminders.
"""

import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pts_project.settings')

app = Celery('pts_project')

# Load config from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Celery Beat Schedule for periodic tasks
app.conf.beat_schedule = {
    # Monitor submission timelines every 6 hours
    'monitor-submission-timelines': {
        'task': 'apps.notifications.tasks.monitor_submission_timelines',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
    # Check for upcoming deadlines every day at 8:00 AM
    'check-upcoming-deadlines': {
        'task': 'apps.notifications.tasks.check_upcoming_deadlines',
        'schedule': crontab(hour=8, minute=0),
    },
    # Check for overdue submissions every day at 9:00 AM
    'check-overdue-submissions': {
        'task': 'apps.notifications.tasks.check_overdue_submissions',
        'schedule': crontab(hour=9, minute=0),
    },
    # Send daily summary to CBM every day at 6:00 PM
    'send-daily-summary': {
        'task': 'apps.notifications.tasks.send_daily_summary',
        'schedule': crontab(hour=18, minute=0),
    },
    # Clean up old notifications (older than 90 days) weekly
    'cleanup-old-notifications': {
        'task': 'apps.notifications.tasks.cleanup_old_notifications',
        'schedule': crontab(hour=2, minute=0, day_of_week='sunday'),
    },
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
