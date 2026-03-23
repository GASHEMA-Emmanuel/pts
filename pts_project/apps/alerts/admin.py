from django.contrib import admin
from django.utils.html import format_html
from .models import Alert, AlertConfiguration, AlertHistory


@admin.register(AlertConfiguration)
class AlertConfigurationAdmin(admin.ModelAdmin):
    list_display = (
        'alert_type',
        'description',
        'is_enabled_badge',
        'days_before_deadline',
        'days_in_stage',
        'notify_division_head',
        'notify_procurement_team'
    )
    list_filter = ('is_enabled', 'alert_type')
    fieldsets = (
        ('Alert Configuration', {
            'fields': ('alert_type', 'description')
        }),
        ('Thresholds', {
            'fields': ('days_before_deadline', 'days_in_stage'),
            'description': 'Configure thresholds for triggering alerts'
        }),
        ('Alert Settings', {
            'fields': ('is_enabled', 'send_email', 'send_notification')
        }),
        ('Notification Recipients', {
            'fields': ('notify_division_head', 'notify_cbm', 'notify_procurement_team'),
            'description': 'Select which roles should receive notifications for this alert type'
        }),
    )
    
    def is_enabled_badge(self, obj):
        if obj.is_enabled:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Enabled</span>'
            )
        return format_html(
            '<span style="color: red; font-weight: bold;">✗ Disabled</span>'
        )
    is_enabled_badge.short_description = 'Status'
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of core alert types
        return False


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'submission_ref',
        'severity_badge',
        'status_badge',
        'days_ago',
        'actions_link'
    )
    list_filter = ('status', 'severity', 'alert_type', 'created_at')
    search_fields = ('title', 'submission__tracking_reference', 'description')
    readonly_fields = (
        'id',
        'created_at',
        'updated_at',
        'acknowledged_at',
        'resolved_at'
    )
    fieldsets = (
        ('Alert Information', {
            'fields': ('id', 'submission', 'alert_type', 'title', 'description', 'severity')
        }),
        ('Status', {
            'fields': ('status', 'created_at', 'updated_at')
        }),
        ('Acknowledgement', {
            'fields': ('acknowledged_by', 'acknowledged_at', 'acknowledgement_notes'),
            'classes': ('collapse',)
        }),
        ('Resolution', {
            'fields': ('resolved_at', 'resolution_notes'),
            'classes': ('collapse',)
        }),
    )
    
    def submission_ref(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        url = reverse('admin:procurement_submission_change', args=[obj.submission.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.submission.tracking_reference
        )
    submission_ref.short_description = 'Submission'
    
    def severity_badge(self, obj):
        colors = {
            'info': '#17a2b8',
            'warning': '#ffc107',
            'critical': '#dc3545'
        }
        color = colors.get(obj.severity, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_severity_display()
        )
    severity_badge.short_description = 'Severity'
    
    def status_badge(self, obj):
        colors = {
            'active': '#28a745',
            'acknowledged': '#ffc107',
            'resolved': '#6c757d'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def days_ago(self, obj):
        return f"{obj.days_since_created} days"
    days_ago.short_description = 'Created'
    
    def actions_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        url = reverse('admin:alerts_alert_change', args=[obj.id])
        return format_html(
            '<a class="button" href="{}">View</a>',
            url
        )
    actions_link.short_description = 'Actions'
    
    def has_delete_permission(self, request, obj=None):
        # Keep historical record - don't delete alerts
        return False


@admin.register(AlertHistory)
class AlertHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'submission_ref',
        'alert_type',
        'severity',
        'created_at'
    )
    list_filter = ('alert_type', 'severity', 'created_at')
    search_fields = ('title', 'submission__tracking_reference')
    readonly_fields = (
        'id',
        'submission',
        'alert_type',
        'title',
        'severity',
        'triggered_reason',
        'created_at'
    )
    
    def submission_ref(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        url = reverse('admin:procurement_submission_change', args=[obj.submission.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.submission.tracking_reference
        )
    submission_ref.short_description = 'Submission'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
