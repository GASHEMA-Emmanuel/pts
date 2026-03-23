"""
Alert and AlertConfiguration models for tracking and alerting system.
"""
import uuid
from django.db import models
from django.utils import timezone
from apps.core.models import BaseModel, TimestampMixin


class AlertConfiguration(BaseModel):
    """
    System configuration for alert thresholds and escalation rules.
    Admin can configure when alerts should trigger.
    """
    ALERT_TYPE_CHOICES = [
        ('deadline_approaching', 'Deadline Approaching'),
        ('deadline_missed', 'Deadline Missed'),
        ('stalled_submission', 'Stalled Submission'),
        ('long_in_review', 'Long Time in Review'),
        ('high_priority_stuck', 'High Priority Stuck'),
        ('budget_threshold', 'Budget Threshold Exceeded'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPE_CHOICES, unique=True)
    description = models.TextField()
    
    # Threshold configuration
    days_before_deadline = models.IntegerField(default=7, help_text="Days before deadline to trigger alert")
    days_in_stage = models.IntegerField(default=14, help_text="Days in a stage before triggering stalled alert")
    
    # Alert settings
    is_enabled = models.BooleanField(default=True)
    send_email = models.BooleanField(default=True)
    send_notification = models.BooleanField(default=True)
    
    # Recipients
    notify_division_head = models.BooleanField(default=True)
    notify_cbm = models.BooleanField(default=False)
    notify_procurement_team = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'alert_configurations'
        verbose_name = 'Alert Configuration'
        verbose_name_plural = 'Alert Configurations'
    
    def __str__(self):
        return f"{self.get_alert_type_display()}"


class Alert(BaseModel):
    """
    Active alerts for submissions that need attention.
    Generated based on AlertConfiguration rules.
    """
    SEVERITY_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Related submission
    submission = models.ForeignKey(
        'procurement.Submission',
        on_delete=models.CASCADE,
        related_name='alerts'
    )
    
    # Alert details
    alert_type = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    description = models.TextField()
    
    # Severity and status
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='warning')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Acknowledgement
    acknowledged_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_alerts'
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledgement_notes = models.TextField(blank=True, null=True)
    
    # Resolution
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'alerts'
        verbose_name = 'Alert'
        verbose_name_plural = 'Alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['submission', 'status']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['severity']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.submission.tracking_reference}"
    
    @property
    def is_active(self):
        return self.status == 'active'
    
    @property
    def days_since_created(self):
        return (timezone.now() - self.created_at).days
    
    def acknowledge(self, user, notes=''):
        """Mark alert as acknowledged"""
        self.status = 'acknowledged'
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.acknowledgement_notes = notes
        self.save()
    
    def resolve(self, notes=''):
        """Mark alert as resolved"""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.save()


class AlertHistory(TimestampMixin):
    """
    Historical record of all alerts generated for auditing and analysis.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    submission = models.ForeignKey(
        'procurement.Submission',
        on_delete=models.CASCADE,
        related_name='alert_history'
    )
    
    alert_type = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    severity = models.CharField(max_length=20)
    triggered_reason = models.TextField()
    
    class Meta:
        db_table = 'alert_history'
        verbose_name = 'Alert History'
        verbose_name_plural = 'Alert Histories'
        ordering = ['-created_at']
