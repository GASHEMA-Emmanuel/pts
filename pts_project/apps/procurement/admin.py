"""
Admin configuration for procurement app.
"""
from django.contrib import admin
from .models import ProcurementCall, Submission, Bid, Comment, Attachment, TimelineConfiguration, Tender, TenderHistory


@admin.register(ProcurementCall)
class ProcurementCallAdmin(admin.ModelAdmin):
    list_display = ['reference_number', 'title', 'status', 'start_date', 'end_date', 'created_by']
    list_filter = ['status', 'created_at']
    search_fields = ['reference_number', 'title', 'description']
    readonly_fields = ['reference_number', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = [
        'tracking_reference', 'item_name', 'division',
        'status', 'total_budget', 'priority', 'timeline_status', 'created_at'
    ]
    list_filter = ['status', 'priority', 'division', 'call', 'timeline_status', 'procurement_method']
    search_fields = ['tracking_reference', 'item_name', 'item_description']
    readonly_fields = ['tracking_reference', 'total_budget', 'created_at', 'updated_at', 'timeline_last_checked']
    raw_id_fields = ['call', 'division', 'created_by', 'submitted_by', 'current_stage']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tracking_reference', 'item_name', 'item_description', 'division', 'call')
        }),
        ('Procurement Details', {
            'fields': ('quantity', 'unit_of_measure', 'estimated_unit_price', 'total_budget', 'priority')
        }),
        ('Workflow & Status', {
            'fields': ('status', 'current_stage', 'submitted_by', 'submitted_at')
        }),
        ('Timeline & Deadlines', {
            'fields': (
                'procurement_method', 'current_stage_deadline', 'timeline_status',
                'timeline_days_remaining', 'bid_validity_extension_used', 'timeline_last_checked'
            ),
            'classes': ('collapse',)
        }),
        ('Dates & Tracking', {
            'fields': ('created_at', 'updated_at', 'created_by')
        }),
    )


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = [
        'supplier_name', 'submission', 'bid_amount',
        'total_score', 'is_winner', 'submission_date'
    ]
    list_filter = ['is_winner', 'is_disqualified', 'currency']
    search_fields = ['supplier_name', 'supplier_tin']
    raw_id_fields = ['submission', 'evaluated_by']


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['submission', 'author', 'comment_type', 'is_resolved', 'created_at']
    list_filter = ['comment_type', 'is_resolved']
    search_fields = ['content']
    raw_id_fields = ['submission', 'author', 'parent', 'resolved_by']


@admin.register(TimelineConfiguration)
class TimelineConfigurationAdmin(admin.ModelAdmin):
    list_display = [
        'stage_name', 'procurement_method', 'min_days', 'max_days',
        'is_extendable', 'extension_days'
    ]
    list_filter = ['stage_name', 'is_extendable']
    search_fields = ['stage_name', 'procurement_method']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Stage Configuration', {
            'fields': ('stage_name', 'procurement_method')
        }),
        ('Timeline Settings', {
            'fields': ('min_days', 'max_days')
        }),
        ('Extension Settings', {
            'fields': ('is_extendable', 'extension_days')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ['original_filename', 'submission', 'file_type', 'file_size', 'created_at']
    list_filter = ['file_type']
    search_fields = ['original_filename', 'description']
    raw_id_fields = ['submission', 'uploaded_by']


@admin.register(Tender)
class TenderAdmin(admin.ModelAdmin):
    list_display = ['tender_number', 'tender_title', 'procurement_method', 'status', 'submission', 'created_by', 'created_at']
    list_filter = ['procurement_method', 'status']
    search_fields = ['tender_number', 'tender_title']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['submission', 'created_by', 'current_stage']


@admin.register(TenderHistory)
class TenderHistoryAdmin(admin.ModelAdmin):
    list_display = ['tender', 'from_status', 'to_status', 'action', 'action_by', 'approval_date', 'created_at']
    list_filter = ['action']
    search_fields = ['tender__tender_number', 'tender__tender_title']
    readonly_fields = ['created_at']
    raw_id_fields = ['tender', 'action_by']
