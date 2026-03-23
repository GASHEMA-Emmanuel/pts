"""
Notification models for PTS.
"""
import uuid
from django.db import models
from apps.core.models import TimestampMixin


class Notification(TimestampMixin):
    """
    Notification model for in-system notifications.
    """
    NOTIFICATION_TYPES = [
        ('procurement_call', 'New Procurement Call'),
        ('deadline_reminder', 'Deadline Reminder'),
        ('submission_status', 'Submission Status Update'),
        ('approval_required', 'Approval Required'),
        ('comment', 'New Comment'),
        ('escalation', 'Escalation'),
        ('system', 'System Notification'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='notification_id'
    )
    
    # Recipient
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='notifications',
        db_column='user_id'
    )
    
    # Content
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPES,
        default='system'
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium'
    )
    
    # Related object
    related_object_type = models.CharField(max_length=100, blank=True, null=True)
    related_object_id = models.CharField(max_length=100, blank=True, null=True)
    
    # URL to redirect to
    action_url = models.CharField(max_length=500, blank=True, null=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Email status
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'notifications'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['notification_type']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.full_name}"
    
    def mark_as_read(self):
        """Mark notification as read."""
        from django.utils import timezone
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])


class NotificationPreference(models.Model):
    """
    User notification preferences.
    """
    user = models.OneToOneField(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    # In-system notifications
    receive_procurement_calls = models.BooleanField(default=True)
    receive_deadline_reminders = models.BooleanField(default=True)
    receive_status_updates = models.BooleanField(default=True)
    receive_approval_requests = models.BooleanField(default=True)
    receive_comments = models.BooleanField(default=True)
    receive_escalations = models.BooleanField(default=True)
    
    # Email notifications
    email_procurement_calls = models.BooleanField(default=True)
    email_deadline_reminders = models.BooleanField(default=True)
    email_status_updates = models.BooleanField(default=False)
    email_approval_requests = models.BooleanField(default=True)
    email_escalations = models.BooleanField(default=True)
    
    # Timing
    deadline_reminder_days = models.PositiveIntegerField(default=3)
    
    class Meta:
        db_table = 'notification_preferences'
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
    
    def __str__(self):
        return f"Preferences for {self.user.full_name}"


class EmailLog(TimestampMixin):
    """
    Log of sent emails for audit purposes.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    recipient_email = models.EmailField()
    recipient_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_logs'
    )
    
    subject = models.CharField(max_length=255)
    body = models.TextField()
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('sent', 'Sent'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    error_message = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Related notification
    notification = models.ForeignKey(
        Notification,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_logs'
    )
    
    class Meta:
        db_table = 'email_logs'
        verbose_name = 'Email Log'
        verbose_name_plural = 'Email Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Email to {self.recipient_email}: {self.subject}"
