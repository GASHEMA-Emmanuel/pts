"""
Admin configuration for notifications app.
"""
from django.contrib import admin
from .models import Notification, NotificationPreference, EmailLog


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'notification_type', 'priority', 'is_read', 'created_at']
    list_filter = ['notification_type', 'priority', 'is_read']
    search_fields = ['title', 'message', 'user__email']
    raw_id_fields = ['user']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'receive_deadline_reminders', 'email_deadline_reminders']
    raw_id_fields = ['user']


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ['recipient_email', 'subject', 'status', 'sent_at', 'created_at']
    list_filter = ['status']
    search_fields = ['recipient_email', 'subject']
    raw_id_fields = ['recipient_user', 'notification']
    readonly_fields = ['created_at']
