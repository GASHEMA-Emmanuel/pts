"""
Serializers for Procurement models.
"""
from rest_framework import serializers
from django.utils import timezone
from .models import ProcurementCall, Submission, Bid, Comment, Attachment
from apps.accounts.serializers import UserMinimalSerializer
from apps.divisions.serializers import DivisionMinimalSerializer


# ==================== PROCUREMENT CALL SERIALIZERS ====================

class ProcurementCallSerializer(serializers.ModelSerializer):
    """Full Procurement Call serializer."""
    created_by = UserMinimalSerializer(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)
    submission_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = ProcurementCall
        fields = [
            'id', 'title', 'description', 'reference_number',
            'start_date', 'end_date', 'extended_date',
            'instructions', 'scope', 'status',
            'created_by', 'budget_ceiling', 'allow_late_submissions',
            'call_document',
            'is_active', 'is_overdue', 'days_remaining', 'submission_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'reference_number', 'created_at', 'updated_at']


class ProcurementCallCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating procurement calls."""
    
    class Meta:
        model = ProcurementCall
        fields = [
            'title', 'description', 'start_date', 'end_date',
            'instructions', 'scope', 'budget_ceiling', 'allow_late_submissions',
            'call_document'
        ]
    
    def validate(self, data):
        if data['start_date'] >= data['end_date']:
            raise serializers.ValidationError({
                'end_date': 'End date must be after start date.'
            })
        if data['start_date'] < timezone.now():
            raise serializers.ValidationError({
                'start_date': 'Start date cannot be in the past.'
            })
        return data
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class ProcurementCallListSerializer(serializers.ModelSerializer):
    """Minimal Procurement Call serializer for listings."""
    submission_count = serializers.IntegerField(read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = ProcurementCall
        fields = [
            'id', 'title', 'reference_number', 'status',
            'start_date', 'end_date', 'days_remaining', 'submission_count',
            'call_document'
        ]


class ProcurementCallExtendSerializer(serializers.Serializer):
    """Serializer for extending call deadline."""
    extended_date = serializers.DateTimeField()
    reason = serializers.CharField(max_length=500)
    
    def validate_extended_date(self, value):
        call = self.context.get('call')
        if call and value <= call.end_date:
            raise serializers.ValidationError(
                'Extended date must be after the original end date.'
            )
        return value


# ==================== SUBMISSION SERIALIZERS ====================

class SubmissionSerializer(serializers.ModelSerializer):
    """Full Submission serializer."""
    call = ProcurementCallListSerializer(read_only=True)
    call_id = serializers.UUIDField(write_only=True)
    division = DivisionMinimalSerializer(read_only=True)
    division_id = serializers.IntegerField(write_only=True, required=False)
    created_by = UserMinimalSerializer(read_only=True)
    submitted_by = UserMinimalSerializer(read_only=True)
    current_stage_name = serializers.CharField(source='current_stage.name', read_only=True)
    is_editable = serializers.BooleanField(read_only=True)
    is_late = serializers.BooleanField(read_only=True)
    days_at_current_stage = serializers.IntegerField(read_only=True)
    comment_count = serializers.SerializerMethodField()
    bid_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Submission
        fields = [
            'id', 'tracking_reference',
            'call', 'call_id', 'division', 'division_id',
            'item_name', 'item_description', 'category',
            'quantity', 'unit_of_measure', 'estimated_unit_price', 'total_budget',
            'justification', 'priority', 'expected_delivery_date',
            'current_stage', 'current_stage_name', 'status',
            'created_by', 'submitted_by', 'submitted_at',
            'umucyo_reference', 'attachments',
            'is_editable', 'is_late', 'days_at_current_stage',
            'comment_count', 'bid_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tracking_reference', 'total_budget',
            'submitted_at', 'created_at', 'updated_at'
        ]
    
    def get_comment_count(self, obj):
        return obj.comments.count()
    
    def get_bid_count(self, obj):
        return obj.bids.count()


class SubmissionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating submissions."""
    
    class Meta:
        model = Submission
        fields = [
            'call', 'item_name', 'item_description', 'category',
            'quantity', 'unit_of_measure', 'estimated_unit_price',
            'justification', 'priority', 'expected_delivery_date'
        ]
    
    def validate_call(self, value):
        if not value.is_active:
            raise serializers.ValidationError(
                'Cannot submit to an inactive procurement call.'
            )
        return value
    
    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['created_by'] = user
        validated_data['division'] = user.division
        
        # Set initial stage
        from apps.workflows.models import WorkflowStage
        initial_stage = WorkflowStage.objects.filter(order=1).first()
        if initial_stage:
            validated_data['current_stage'] = initial_stage
        
        return super().create(validated_data)


class SubmissionUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating submissions."""
    
    class Meta:
        model = Submission
        fields = [
            'item_name', 'item_description', 'category',
            'quantity', 'unit_of_measure', 'estimated_unit_price',
            'justification', 'priority', 'expected_delivery_date'
        ]
    
    def validate(self, data):
        if not self.instance.is_editable:
            raise serializers.ValidationError(
                'This submission cannot be edited in its current status.'
            )
        return data


class SubmissionListSerializer(serializers.ModelSerializer):
    """Minimal Submission serializer for listings."""
    division_name = serializers.CharField(source='division.name', read_only=True)
    current_stage_name = serializers.CharField(source='current_stage.name', read_only=True)
    
    class Meta:
        model = Submission
        fields = [
            'id', 'tracking_reference', 'item_name',
            'division_name', 'total_budget', 'status',
            'current_stage_name', 'priority', 'created_at'
        ]


class SubmissionStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating submission status."""
    status = serializers.ChoiceField(choices=Submission.STATUS_CHOICES)
    comments = serializers.CharField(required=False, allow_blank=True)


class SubmissionApprovalSerializer(serializers.Serializer):
    """Serializer for approving/rejecting submissions."""
    action = serializers.ChoiceField(choices=['approve', 'reject', 'return'])
    comments = serializers.CharField(required=True)


# ==================== BID SERIALIZERS ====================

class BidSerializer(serializers.ModelSerializer):
    """Full Bid serializer."""
    submission = SubmissionListSerializer(read_only=True)
    submission_id = serializers.UUIDField(write_only=True)
    evaluated_by = UserMinimalSerializer(read_only=True)
    
    class Meta:
        model = Bid
        fields = [
            'id', 'submission', 'submission_id',
            'supplier_name', 'supplier_tin', 'supplier_contact', 'supplier_email',
            'bid_amount', 'currency',
            'technical_score', 'financial_score', 'total_score',
            'is_winner', 'is_disqualified', 'disqualification_reason',
            'documents', 'evaluation_notes',
            'evaluated_by', 'evaluated_at', 'submission_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'total_score', 'submission_date',
            'created_at', 'updated_at'
        ]


class BidCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating bids."""
    
    class Meta:
        model = Bid
        fields = [
            'submission', 'supplier_name', 'supplier_tin',
            'supplier_contact', 'supplier_email',
            'bid_amount', 'currency', 'documents'
        ]
    
    def validate_submission(self, value):
        if value.status not in ['Bidding', 'Publication of TD']:
            raise serializers.ValidationError(
                'Cannot add bids to this submission in its current status.'
            )
        return value


class BidEvaluationSerializer(serializers.ModelSerializer):
    """Serializer for evaluating bids."""
    
    class Meta:
        model = Bid
        fields = [
            'technical_score', 'financial_score',
            'evaluation_notes', 'is_disqualified', 'disqualification_reason'
        ]
    
    def validate(self, data):
        if data.get('is_disqualified') and not data.get('disqualification_reason'):
            raise serializers.ValidationError({
                'disqualification_reason': 'Reason required when disqualifying a bid.'
            })
        return data
    
    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        instance.evaluated_by = self.context['request'].user
        instance.evaluated_at = timezone.now()
        instance.calculate_total_score()
        return instance


class BidListSerializer(serializers.ModelSerializer):
    """Minimal Bid serializer for listings."""
    
    class Meta:
        model = Bid
        fields = [
            'id', 'supplier_name', 'bid_amount', 'currency',
            'total_score', 'is_winner', 'is_disqualified', 'submission_date'
        ]


# ==================== COMMENT SERIALIZERS ====================

class CommentSerializer(serializers.ModelSerializer):
    """Full Comment serializer."""
    author = UserMinimalSerializer(read_only=True)
    resolved_by = UserMinimalSerializer(read_only=True)
    replies = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            'id', 'submission', 'author', 'content',
            'parent', 'comment_type',
            'is_resolved', 'resolved_by', 'resolved_at',
            'replies', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_replies(self, obj):
        if obj.replies.exists():
            return CommentSerializer(obj.replies.all(), many=True).data
        return []


class CommentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating comments."""
    
    class Meta:
        model = Comment
        fields = ['submission', 'content', 'parent', 'comment_type']
    
    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)


# ==================== ATTACHMENT SERIALIZERS ====================

class AttachmentSerializer(serializers.ModelSerializer):
    """Attachment serializer."""
    uploaded_by = UserMinimalSerializer(read_only=True)
    
    class Meta:
        model = Attachment
        fields = [
            'id', 'submission', 'file', 'original_filename',
            'file_type', 'file_size', 'description',
            'uploaded_by', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class AttachmentUploadSerializer(serializers.ModelSerializer):
    """Serializer for uploading attachments."""
    
    class Meta:
        model = Attachment
        fields = ['submission', 'file', 'description']
    
    def create(self, validated_data):
        file = validated_data['file']
        validated_data['original_filename'] = file.name
        validated_data['file_type'] = file.content_type
        validated_data['file_size'] = file.size
        validated_data['uploaded_by'] = self.context['request'].user
        return super().create(validated_data)
