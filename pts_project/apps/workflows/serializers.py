"""
Serializers for Workflow models.
"""
from rest_framework import serializers
from .models import WorkflowStage, WorkflowHistory, WorkflowConfiguration, Deadline
from apps.accounts.serializers import UserMinimalSerializer


class WorkflowStageSerializer(serializers.ModelSerializer):
    """Full WorkflowStage serializer."""
    submission_count = serializers.SerializerMethodField()
    
    class Meta:
        model = WorkflowStage
        fields = [
            'id', 'name', 'description', 'order',
            'expected_duration_days', 'allowed_roles',
            'color', 'icon', 'is_terminal', 'submission_count'
        ]
    
    def get_submission_count(self, obj):
        return obj.current_submissions.count()


class WorkflowStageMinimalSerializer(serializers.ModelSerializer):
    """Minimal WorkflowStage serializer."""
    
    class Meta:
        model = WorkflowStage
        fields = ['id', 'name', 'order', 'color']


class WorkflowHistorySerializer(serializers.ModelSerializer):
    """Full WorkflowHistory serializer."""
    from_stage = WorkflowStageMinimalSerializer(read_only=True)
    to_stage = WorkflowStageMinimalSerializer(read_only=True)
    action_by = UserMinimalSerializer(read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = WorkflowHistory
        fields = [
            'id', 'submission',
            'from_stage', 'to_stage',
            'action', 'action_display', 'action_by',
            'comments', 'approval_date', 'metadata', 'time_at_previous_stage',
            'created_at'
        ]


class WorkflowHistoryCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating workflow history."""
    
    class Meta:
        model = WorkflowHistory
        fields = ['submission', 'from_stage', 'to_stage', 'action', 'comments', 'approval_date', 'metadata']
    
    def create(self, validated_data):
        validated_data['action_by'] = self.context['request'].user
        return super().create(validated_data)


class WorkflowConfigurationSerializer(serializers.ModelSerializer):
    """WorkflowConfiguration serializer."""
    stage = WorkflowStageMinimalSerializer(read_only=True)
    allowed_next_stages = WorkflowStageMinimalSerializer(many=True, read_only=True)
    auto_transition_to = WorkflowStageMinimalSerializer(read_only=True)
    
    class Meta:
        model = WorkflowConfiguration
        fields = [
            'id', 'stage', 'allowed_next_stages',
            'required_approval_roles', 'minimum_approvals',
            'auto_transition_after_days', 'auto_transition_to',
            'escalation_after_days', 'escalation_roles'
        ]


class DeadlineSerializer(serializers.ModelSerializer):
    """Deadline serializer."""
    stage = WorkflowStageMinimalSerializer(read_only=True)
    submission_reference = serializers.CharField(
        source='submission.tracking_reference',
        read_only=True
    )
    days_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = Deadline
        fields = [
            'id', 'submission', 'submission_reference', 'stage',
            'deadline', 'is_overdue', 'days_remaining',
            'reminder_sent', 'escalated', 'created_at'
        ]
    
    def get_days_remaining(self, obj):
        from django.utils import timezone
        delta = obj.deadline - timezone.now()
        return max(0, delta.days)


class WorkflowTransitionSerializer(serializers.Serializer):
    """Serializer for workflow transitions."""
    submission_id = serializers.UUIDField()
    to_stage_id = serializers.IntegerField()
    comments = serializers.CharField(required=False, allow_blank=True)
    approval_date = serializers.DateField(required=False, allow_null=True)
    
    def validate_to_stage_id(self, value):
        try:
            WorkflowStage.objects.get(id=value)
        except WorkflowStage.DoesNotExist:
            raise serializers.ValidationError('Invalid stage ID')
        return value


class WorkflowSummarySerializer(serializers.Serializer):
    """Summary of submissions at each workflow stage."""
    stage_id = serializers.IntegerField()
    stage_name = serializers.CharField()
    stage_order = serializers.IntegerField()
    color = serializers.CharField()
    count = serializers.IntegerField()
    total_budget = serializers.DecimalField(max_digits=15, decimal_places=2)
    overdue_count = serializers.IntegerField()
