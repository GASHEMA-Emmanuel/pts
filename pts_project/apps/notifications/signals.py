"""
Signals for notifications app.
Handles automatic email sending when notifications are created.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging
from .models import Notification
from .tasks import send_notification_email

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Notification)
def send_email_on_notification_create(sender, instance, created, **kwargs):
    """
    Send email when a notification is created.
    Uses Celery task for async processing.
    """
    if created:
        try:
            # Queue the email sending task asynchronously
            send_notification_email.delay(str(instance.id))
            logger.info(f"Queued email sending for notification {instance.id} to {instance.user.email}")
        except Exception as e:
            logger.error(f"Error queuing email task for notification {instance.id}: {e}")


# Register signal handlers
default_app_config = 'notifications.apps.NotificationsConfig'
