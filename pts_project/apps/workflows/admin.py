"""
Admin configuration for workflows app.
"""
from django.contrib import admin
from .models import WorkflowStage, WorkflowHistory, WorkflowConfiguration, Deadline


@admin.register(WorkflowStage)
class WorkflowStageAdmin(admin.ModelAdmin):
    list_display = ['order', 'name', 'expected_duration_days', 'color', 'is_terminal']
    list_filter = ['is_terminal']
    ordering = ['order']


@admin.register(WorkflowHistory)
class WorkflowHistoryAdmin(admin.ModelAdmin):
    list_display = ['submission', 'from_stage', 'to_stage', 'action', 'action_by', 'created_at']
    list_filter = ['action', 'from_stage', 'to_stage']
    search_fields = ['submission__tracking_reference', 'comments']
    raw_id_fields = ['submission', 'action_by']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(WorkflowConfiguration)
class WorkflowConfigurationAdmin(admin.ModelAdmin):
    list_display = ['stage', 'minimum_approvals', 'escalation_after_days']
    raw_id_fields = ['stage', 'auto_transition_to']
    filter_horizontal = ['allowed_next_stages']


@admin.register(Deadline)
class DeadlineAdmin(admin.ModelAdmin):
    list_display = ['submission', 'stage', 'deadline', 'is_overdue', 'escalated']
    list_filter = ['is_overdue', 'escalated', 'stage']
    search_fields = ['submission__tracking_reference']
    raw_id_fields = ['submission', 'stage']
