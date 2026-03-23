"""
Serializers for Notification models.
"""
from rest_framework import serializers
from .models import Notification, NotificationPreference, EmailLog


class NotificationSerializer(serializers.ModelSerializer):
    """Full Notification serializer."""
    
    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'title', 'message',
            'notification_type', 'priority',
            'related_object_type', 'related_object_id', 'action_url',
            'is_read', 'read_at',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class NotificationListSerializer(serializers.ModelSerializer):
    """Minimal Notification serializer for listings."""
    
    class Meta:
        model = Notification
        fields = [
            'id', 'title', 'message', 'notification_type',
            'priority', 'is_read', 'action_url', 'created_at'
        ]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Notification preferences serializer."""
    
    class Meta:
        model = NotificationPreference
        fields = [
            'receive_procurement_calls', 'receive_deadline_reminders',
            'receive_status_updates', 'receive_approval_requests',
            'receive_comments', 'receive_escalations',
            'email_procurement_calls', 'email_deadline_reminders',
            'email_status_updates', 'email_approval_requests',
            'email_escalations', 'deadline_reminder_days'
        ]


class EmailLogSerializer(serializers.ModelSerializer):
    """Email log serializer."""
    
    class Meta:
        model = EmailLog
        fields = [
            'id', 'recipient_email', 'subject',
            'status', 'error_message', 'sent_at', 'created_at'
        ]


class NotificationCountSerializer(serializers.Serializer):
    """Serializer for notification counts."""
    total = serializers.IntegerField()
    unread = serializers.IntegerField()
    by_type = serializers.DictField()
