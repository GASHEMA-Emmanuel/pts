"""
Views for Procurement management.
"""
from rest_framework import viewsets, status, generics, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Sum, Q, Avg
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from django.shortcuts import redirect
from django.contrib import messages

from apps.core.permissions import (
    IsAdmin, IsCBM, IsAdminOrCBM, CanManageSubmissions,
    CanApprove, CanUpdateWorkflow, DivisionBasedPermission
)
from apps.core.exceptions import WorkflowException, DeadlineException
from .models import ProcurementCall, Submission, Bid, Comment, Attachment
from .serializers import (
    ProcurementCallSerializer, ProcurementCallCreateSerializer,
    ProcurementCallListSerializer, ProcurementCallExtendSerializer,
    SubmissionSerializer, SubmissionCreateSerializer,
    SubmissionUpdateSerializer, SubmissionListSerializer,
    SubmissionStatusUpdateSerializer, SubmissionApprovalSerializer,
    BidSerializer, BidCreateSerializer, BidEvaluationSerializer, BidListSerializer,
    CommentSerializer, CommentCreateSerializer,
    AttachmentSerializer, AttachmentUploadSerializer
)
from apps.workflows.models import WorkflowHistory


# ==================== PROCUREMENT CALL VIEWS ====================

@extend_schema_view(
    list=extend_schema(summary="List all procurement calls", tags=["Procurement Calls"]),
    retrieve=extend_schema(summary="Get procurement call details", tags=["Procurement Calls"]),
    create=extend_schema(summary="Create a new procurement call", tags=["Procurement Calls"]),
    update=extend_schema(summary="Update a procurement call", tags=["Procurement Calls"]),
    partial_update=extend_schema(summary="Partial update a procurement call", tags=["Procurement Calls"]),
    destroy=extend_schema(summary="Cancel a procurement call", tags=["Procurement Calls"]),
)
class ProcurementCallViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing procurement calls.
    CBM and Admin can create/update/delete calls.
    """
    queryset = ProcurementCall.objects.select_related('created_by').all()
    filterset_fields = ['status']
    search_fields = ['title', 'reference_number', 'description']
    ordering_fields = ['start_date', 'end_date', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ProcurementCallCreateSerializer
        if self.action == 'list':
            return ProcurementCallListSerializer
        if self.action == 'extend':
            return ProcurementCallExtendSerializer
        return ProcurementCallSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminOrCBM()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter active only
        active_only = self.request.query_params.get('active_only')
        if active_only and active_only.lower() == 'true':
            now = timezone.now()
            queryset = queryset.filter(
                status='Active',
                start_date__lte=now
            ).filter(
                Q(end_date__gte=now) | Q(extended_date__gte=now)
            )
        
        return queryset.annotate(
            submission_count=Count('submissions')
        )
    
    def perform_destroy(self, instance):
        """Cancel instead of delete."""
        instance.status = 'Cancelled'
        instance.save()
    
    @extend_schema(summary="Activate a procurement call", tags=["Procurement Calls"])
    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrCBM])
    def activate(self, request, pk=None):
        """Activate a draft procurement call."""
        call = self.get_object()
        
        if call.status != 'Draft':
            return Response(
                {'error': 'Only draft calls can be activated'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        call.status = 'Active'
        call.save()
        
        # Send notifications to all HODs and DMs
        from apps.notifications.tasks import notify_procurement_call
        notify_procurement_call.delay(str(call.id))
        
        return Response({
            'success': True,
            'message': f'Procurement call {call.reference_number} has been activated'
        })
    
    @extend_schema(summary="Close a procurement call", tags=["Procurement Calls"])
    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrCBM])
    def close(self, request, pk=None):
        """Close a procurement call."""
        call = self.get_object()
        
        if call.status not in ['Active', 'Extended']:
            return Response(
                {'error': 'Only active or extended calls can be closed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        call.status = 'Closed'
        call.save()
        
        return Response({
            'success': True,
            'message': f'Procurement call {call.reference_number} has been closed'
        })
    
    @extend_schema(summary="Extend procurement call deadline", tags=["Procurement Calls"])
    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrCBM])
    def extend(self, request, pk=None):
        """Extend the deadline for a procurement call."""
        call = self.get_object()
        serializer = ProcurementCallExtendSerializer(
            data=request.data,
            context={'call': call}
        )
        serializer.is_valid(raise_exception=True)
        
        call.extended_date = serializer.validated_data['extended_date']
        call.status = 'Extended'
        call.save()
        
        # Create workflow history
        # Notification logic here
        
        return Response({
            'success': True,
            'message': f'Deadline extended to {call.extended_date}'
        })
    
    @extend_schema(summary="Get submissions for a procurement call", tags=["Procurement Calls"])
    @action(detail=True, methods=['get'])
    def submissions(self, request, pk=None):
        """Get all submissions for a procurement call."""
        call = self.get_object()
        submissions = call.submissions.all()
        
        # Filter by user's division if not admin/CBM
        user = request.user
        if user.role and user.role.name not in ['Admin', 'CBM', 'Procurement Team']:
            submissions = submissions.filter(division=user.division)
        
        serializer = SubmissionListSerializer(submissions, many=True)
        return Response(serializer.data)
    
    @extend_schema(summary="Get statistics for a procurement call", tags=["Procurement Calls"])
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Get statistics for a procurement call."""
        call = self.get_object()
        
        stats = call.submissions.aggregate(
            total_submissions=Count('id'),
            total_budget=Sum('total_budget'),
            approved_count=Count('id', filter=Q(status='Approved')),
            pending_count=Count('id', filter=Q(status__in=['Submitted', 'Under Review'])),
            rejected_count=Count('id', filter=Q(status='Rejected'))
        )
        
        # Submissions by division
        by_division = list(
            call.submissions.values('division__name')
            .annotate(count=Count('id'), budget=Sum('total_budget'))
        )
        
        # Submissions by status
        by_status = list(
            call.submissions.values('status')
            .annotate(count=Count('id'))
        )
        
        return Response({
            'call': ProcurementCallListSerializer(call).data,
            'statistics': stats,
            'by_division': by_division,
            'by_status': by_status
        })


# ==================== SUBMISSION VIEWS ====================

@extend_schema_view(
    list=extend_schema(summary="List all submissions", tags=["Submissions"]),
    retrieve=extend_schema(summary="Get submission details", tags=["Submissions"]),
    create=extend_schema(summary="Create a new submission", tags=["Submissions"]),
    update=extend_schema(summary="Update a submission", tags=["Submissions"]),
    partial_update=extend_schema(summary="Partial update a submission", tags=["Submissions"]),
    destroy=extend_schema(summary="Cancel a submission", tags=["Submissions"]),
)
class SubmissionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing submissions.
    """
    queryset = Submission.objects.select_related(
        'call', 'division', 'created_by', 'submitted_by', 'current_stage'
    ).all()
    filterset_fields = ['status', 'division', 'call', 'priority']
    search_fields = ['tracking_reference', 'item_name', 'item_description']
    ordering_fields = ['created_at', 'total_budget', 'priority']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return SubmissionCreateSerializer
        if self.action in ['update', 'partial_update']:
            return SubmissionUpdateSerializer
        if self.action == 'list':
            return SubmissionListSerializer
        if self.action == 'update_status':
            return SubmissionStatusUpdateSerializer
        if self.action in ['approve', 'reject', 'return_for_clarification']:
            return SubmissionApprovalSerializer
        return SubmissionSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update']:
            return [CanManageSubmissions()]
        if self.action in ['approve', 'reject', 'return_for_clarification']:
            return [CanApprove()]
        if self.action == 'update_status':
            return [CanUpdateWorkflow()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Non-admin users only see their division's submissions
        if user.role and user.role.name not in ['Admin', 'CBM', 'Procurement Team']:
            queryset = queryset.filter(division=user.division)
        
        # Filter by call
        call_id = self.request.query_params.get('call_id')
        if call_id:
            queryset = queryset.filter(call_id=call_id)
        
        # Filter by stage
        stage_id = self.request.query_params.get('stage_id')
        if stage_id:
            queryset = queryset.filter(current_stage_id=stage_id)
        
        return queryset
    
    def perform_destroy(self, instance):
        """Cancel instead of delete."""
        if instance.status not in ['Draft', 'Returned']:
            raise WorkflowException('Cannot cancel a submission in this status')
        instance.status = 'Cancelled'
        instance.is_deleted = True
        instance.save()
    
    @extend_schema(summary="Submit a draft submission", tags=["Submissions"])
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit a draft submission for review."""
        submission = self.get_object()
        
        if submission.status != 'Draft':
            return Response(
                {'error': 'Only draft submissions can be submitted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if call is still active
        if not submission.call.is_active:
            if not submission.call.allow_late_submissions:
                return Response(
                    {'error': 'The procurement call deadline has passed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        submission.submit(request.user)
        
        # Create workflow history
        from apps.workflows.models import WorkflowStage, WorkflowHistory
        stage = WorkflowStage.objects.filter(order=2).first()
        
        WorkflowHistory.objects.create(
            submission=submission,
            from_stage=WorkflowStage.objects.filter(order=1).first(),
            to_stage=stage,
            action_by=request.user,
            action='submit',
            comments='Submission submitted for review'
        )
        
        # Send notification
        from apps.notifications.tasks import notify_submission_status
        notify_submission_status.delay(str(submission.id), 'submitted')
        
        return Response({
            'success': True,
            'message': 'Submission has been submitted for review',
            'tracking_reference': submission.tracking_reference
        })
    
    @extend_schema(summary="Approve a submission", tags=["Submissions"])
    @action(detail=True, methods=['post'], permission_classes=[CanApprove])
    def approve(self, request, pk=None):
        """Approve a submission."""
        submission = self.get_object()
        serializer = SubmissionApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        if submission.status not in ['Submitted', 'Under Review']:
            return Response(
                {'error': 'This submission cannot be approved in its current status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from apps.workflows.models import WorkflowStage, WorkflowHistory
        from datetime import datetime
        
        old_stage = submission.current_stage
        new_stage = WorkflowStage.objects.filter(order=4).first()  # Approved stage
        
        submission.status = 'Approved'
        submission.current_stage = new_stage
        submission.save()
        
        # Capture approval_date if provided (for stage 5+)
        approval_date = None
        if old_stage and old_stage.order >= 5 and 'approval_date' in request.data:
            approval_date_str = request.data.get('approval_date')
            if approval_date_str:
                try:
                    approval_date = datetime.strptime(approval_date_str, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    pass
        
        WorkflowHistory.objects.create(
            submission=submission,
            from_stage=old_stage,
            to_stage=new_stage,
            action_by=request.user,
            action='approve',
            comments=serializer.validated_data['comments'],
            approval_date=approval_date
        )
        
        # Create approval comment
        Comment.objects.create(
            submission=submission,
            author=request.user,
            content=serializer.validated_data['comments'],
            comment_type='approval'
        )
        
        # Send notification
        from apps.notifications.tasks import notify_submission_status
        notify_submission_status.delay(str(submission.id), 'approved')
        
        return Response({
            'success': True,
            'message': 'Submission has been approved'
        })
    
    @extend_schema(summary="Reject a submission", tags=["Submissions"])
    @action(detail=True, methods=['post'], permission_classes=[CanApprove])
    def reject(self, request, pk=None):
        """Reject a submission."""
        submission = self.get_object()
        serializer = SubmissionApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        if submission.status not in ['Submitted', 'Under Review']:
            return Response(
                {'error': 'This submission cannot be rejected in its current status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from apps.workflows.models import WorkflowHistory
        
        old_stage = submission.current_stage
        
        submission.status = 'Rejected'
        submission.save()
        
        WorkflowHistory.objects.create(
            submission=submission,
            from_stage=old_stage,
            to_stage=old_stage,
            action_by=request.user,
            action='reject',
            comments=serializer.validated_data['comments']
        )
        
        # Create rejection comment
        Comment.objects.create(
            submission=submission,
            author=request.user,
            content=serializer.validated_data['comments'],
            comment_type='rejection'
        )
        
        # Send notification
        from apps.notifications.tasks import notify_submission_status
        notify_submission_status.delay(str(submission.id), 'rejected')
        
        return Response({
            'success': True,
            'message': 'Submission has been rejected'
        })
    
    @extend_schema(summary="Return submission for clarification", tags=["Submissions"])
    @action(detail=True, methods=['post'], permission_classes=[CanApprove])
    def return_for_clarification(self, request, pk=None):
        """Return a submission for clarification."""
        submission = self.get_object()
        serializer = SubmissionApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        if submission.status not in ['Submitted', 'Under Review']:
            return Response(
                {'error': 'This submission cannot be returned in its current status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from apps.workflows.models import WorkflowHistory
        
        old_stage = submission.current_stage
        
        submission.status = 'Returned'
        submission.save()
        
        # Capture approval_date if provided (for stage 5+)
        from datetime import datetime
        approval_date = None
        if old_stage and old_stage.order >= 5 and 'approval_date' in request.data:
            approval_date_str = request.data.get('approval_date')
            if approval_date_str:
                try:
                    approval_date = datetime.strptime(approval_date_str, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    pass
        
        WorkflowHistory.objects.create(
            submission=submission,
            from_stage=old_stage,
            to_stage=old_stage,
            action_by=request.user,
            action='return',
            comments=serializer.validated_data['comments'],
            approval_date=approval_date
        )
        
        # Create clarification request comment
        Comment.objects.create(
            submission=submission,
            author=request.user,
            content=serializer.validated_data['comments'],
            comment_type='clarification'
        )
        
        # Send notification
        from apps.notifications.tasks import notify_submission_status
        notify_submission_status.delay(str(submission.id), 'returned')
        
        return Response({
            'success': True,
            'message': 'Submission has been returned for clarification'
        })
    
    @extend_schema(summary="Update submission workflow status", tags=["Submissions"])
    @action(detail=True, methods=['post'], permission_classes=[CanUpdateWorkflow])
    def update_status(self, request, pk=None):
        """Update submission workflow status (Procurement Team)."""
        submission = self.get_object()
        serializer = SubmissionStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        new_status = serializer.validated_data['status']
        comments = serializer.validated_data.get('comments', '')
        
        from apps.workflows.models import WorkflowStage, WorkflowHistory
        
        # Map status to stage
        status_stage_map = {
            'Published': 5,
            'Bidding': 6,
            'Evaluation': 7,
            'Awarded': 8,
            'Completed': 9
        }
        
        old_stage = submission.current_stage
        stage_order = status_stage_map.get(new_status)
        new_stage = WorkflowStage.objects.filter(order=stage_order).first() if stage_order else old_stage
        
        submission.status = new_status
        submission.current_stage = new_stage
        submission.save()
        
        # Capture approval_date if provided (for stage 5+)
        from datetime import datetime
        approval_date = None
        if new_stage and new_stage.order >= 5 and 'approval_date' in request.data:
            approval_date_str = request.data.get('approval_date')
            if approval_date_str:
                try:
                    approval_date = datetime.strptime(approval_date_str, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    pass
        
        WorkflowHistory.objects.create(
            submission=submission,
            from_stage=old_stage,
            to_stage=new_stage,
            action_by=request.user,
            action='status_update',
            comments=comments,
            approval_date=approval_date
        )
        
        # Send notification
        from apps.notifications.tasks import notify_submission_status
        notify_submission_status.delay(str(submission.id), new_status.lower())
        
        return Response({
            'success': True,
            'message': f'Submission status updated to {new_status}'
        })
    
    @extend_schema(summary="Get submission audit trail", tags=["Submissions"])
    @action(detail=True, methods=['get'])
    def audit_trail(self, request, pk=None):
        """Get the complete audit trail for a submission."""
        submission = self.get_object()
        
        from apps.workflows.serializers import WorkflowHistorySerializer
        history = submission.workflow_history.select_related(
            'from_stage', 'to_stage', 'action_by'
        ).all()
        
        serializer = WorkflowHistorySerializer(history, many=True)
        return Response(serializer.data)
    
    @extend_schema(summary="Get comments for a submission", tags=["Submissions"])
    @action(detail=True, methods=['get', 'post'])
    def comments(self, request, pk=None):
        """Get or add comments for a submission."""
        submission = self.get_object()
        
        if request.method == 'GET':
            comments = submission.comments.filter(parent__isnull=True)
            serializer = CommentSerializer(comments, many=True)
            return Response(serializer.data)
        
        # POST - add comment
        serializer = CommentCreateSerializer(
            data={**request.data, 'submission': submission.id},
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ==================== BID VIEWS ====================

@extend_schema_view(
    list=extend_schema(summary="List all bids", tags=["Bids"]),
    retrieve=extend_schema(summary="Get bid details", tags=["Bids"]),
    create=extend_schema(summary="Create a new bid", tags=["Bids"]),
    update=extend_schema(summary="Update a bid", tags=["Bids"]),
    partial_update=extend_schema(summary="Partial update a bid", tags=["Bids"]),
    destroy=extend_schema(summary="Delete a bid", tags=["Bids"]),
)
class BidViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing bids.
    """
    queryset = Bid.objects.select_related('submission', 'evaluated_by').all()
    filterset_fields = ['submission', 'is_winner', 'is_disqualified']
    search_fields = ['supplier_name', 'supplier_tin']
    ordering_fields = ['bid_amount', 'total_score', 'submission_date']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return BidCreateSerializer
        if self.action == 'evaluate':
            return BidEvaluationSerializer
        if self.action == 'list':
            return BidListSerializer
        return BidSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'evaluate']:
            return [CanUpdateWorkflow()]
        return [permissions.IsAuthenticated()]
    
    @extend_schema(summary="Evaluate a bid", tags=["Bids"])
    @action(detail=True, methods=['post'], permission_classes=[CanUpdateWorkflow])
    def evaluate(self, request, pk=None):
        """Evaluate a bid with scores."""
        bid = self.get_object()
        serializer = BidEvaluationSerializer(
            bid,
            data=request.data,
            context={'request': request},
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'success': True,
            'message': 'Bid has been evaluated',
            'data': BidSerializer(bid).data
        })
    
    @extend_schema(summary="Select winning bid", tags=["Bids"])
    @action(detail=True, methods=['post'], permission_classes=[CanUpdateWorkflow])
    def select_winner(self, request, pk=None):
        """Select this bid as the winner."""
        bid = self.get_object()
        
        # Ensure no other bid is already the winner
        Bid.objects.filter(
            submission=bid.submission,
            is_winner=True
        ).update(is_winner=False)
        
        bid.is_winner = True
        bid.save()
        
        # Update submission status
        bid.submission.status = 'Awarded'
        from apps.workflows.models import WorkflowStage
        stage = WorkflowStage.objects.filter(order=8).first()
        if stage:
            bid.submission.current_stage = stage
        bid.submission.save()
        
        return Response({
            'success': True,
            'message': f'{bid.supplier_name} has been selected as the winner'
        })


# ==================== COMMENT VIEWS ====================

class CommentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing comments.
    """
    queryset = Comment.objects.select_related('author', 'submission').all()
    serializer_class = CommentSerializer
    filterset_fields = ['submission', 'comment_type', 'is_resolved']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CommentCreateSerializer
        return CommentSerializer
    
    @extend_schema(summary="Resolve a comment", tags=["Comments"])
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Mark a comment as resolved."""
        comment = self.get_object()
        comment.resolve(request.user)
        return Response({
            'success': True,
            'message': 'Comment has been resolved'
        })


# ==================== ATTACHMENT VIEWS ====================

class AttachmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing attachments.
    """
    queryset = Attachment.objects.select_related('submission', 'uploaded_by').all()
    filterset_fields = ['submission']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return AttachmentUploadSerializer
        return AttachmentSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            return [CanManageSubmissions()]
        return [permissions.IsAuthenticated()]

def request_clarification(request, submission_id):
    """
    Handle the Request Clarification action for a submission.
    Updates the status to 'Returned' and moves to the previous stage.
    Also saves the clarification message as a comment and notifies the submitter.
    """
    if request.method == 'POST':
        try:
            from apps.workflows.models import WorkflowStage
            from apps.procurement.models import Comment
            from apps.notifications.models import Notification
            
            submission = Submission.objects.get(id=submission_id)
            clarification_message = request.POST.get('clarification_message', '').strip()

            if not clarification_message:
                messages.error(request, 'Clarification message is required.')
                return redirect('procurement_submission_detail', submission_id=submission_id)

            # Store the current stage before making changes
            current_stage = submission.current_stage
            
            # Determine the previous stage by order
            if current_stage and current_stage.order > 1:
                previous_stage = WorkflowStage.objects.filter(order=current_stage.order - 1).first()
                
                if previous_stage:
                    submission.current_stage = previous_stage
                    submission.status = 'Returned'  # Status: "Returned for Clarification"
                else:
                    messages.error(request, 'Unable to determine the previous stage.')
                    return redirect('procurement_submission_detail', submission_id=submission_id)
            else:
                messages.error(request, 'Cannot request clarification for the initial stage.')
                return redirect('procurement_submission_detail', submission_id=submission_id)

            # Save the updated submission
            submission.save()

            # Record the clarification in workflow history
            WorkflowHistory.objects.create(
                submission=submission,
                from_stage=current_stage,
                to_stage=submission.current_stage,
                action='request_clarification',
                comments=clarification_message,
                action_by=request.user,
            )
            
            # Save clarification message as a comment
            Comment.objects.create(
                submission=submission,
                author=request.user,
                content=clarification_message,
                comment_type='clarification'
            )
            
            # Notify the submitter (HOD/DM) that clarification is requested
            if submission.submitted_by:
                Notification.objects.create(
                    user=submission.submitted_by,
                    title='Clarification Requested',
                    message=f'Your submission {submission.tracking_reference} ({submission.item_name}) requires clarification. Please review the comments and resubmit.',
                    notification_type='approval_required',
                    priority='high',
                    action_url=f'/dashboard/procurement/submissions/{submission.id}/',
                    related_object_type='Submission',
                    related_object_id=str(submission.id),
                )

            messages.success(request, 'Clarification requested successfully. Submission has been returned to the previous stage.')
        except Submission.DoesNotExist:
            messages.error(request, 'Submission not found.')
    return redirect('procurement_submission_detail', submission_id=submission_id)

def approve_submission(request, submission_id):
    """
    Handle the Approve Submission action.
    Updates the submission status to the next stage and notifies responsible user.
    """
    if request.method == 'POST':
        try:
            from apps.notifications.models import Notification
            from apps.accounts.models import User
            
            submission = Submission.objects.get(id=submission_id)

            # Get the current stage and determine the next stage
            current_stage = submission.current_stage
            next_stage = WorkflowStage.objects.filter(order=current_stage.order + 1).first()

            if next_stage:
                submission.current_stage = next_stage
                submission.status = next_stage.name
                submission.save()

                # Record in workflow history
                WorkflowHistory.objects.create(
                    submission=submission,
                    from_stage=current_stage,
                    to_stage=next_stage,
                    action='approve',
                    comments='Submission approved.',
                    action_by=request.user,
                )
                
                # Send notifications to responsible user/role for the next stage
                # Map of stage order to responsible role
                stage_responsibility = {
                    2: 'Procurement Team',       # HOD/DM Submit - Procurement reviews
                    3: 'CBM',                    # Review of Procurement Draft - CBM approves
                    4: 'Procurement Team',       # CBM Review - Procurement acts
                    5: 'Procurement Team',       # Publish Plan
                    6: 'Procurement Team',       # Prepare Tender Document
                    7: 'CBM',                    # CBM Review TD
                    8: 'Procurement Team',       # Publication of TD
                    9: None,                     # Bidding - no action needed from staff
                    10: None,                    # Evaluation
                    11: None,                    # CBM Approval
                    12: None,                    # Notify Bidders
                    13: None,                    # Contract Negotiation
                    14: None,                    # Contract Drafting
                    15: None,                    # Legal Review
                    16: None,                    # Supplier Approval
                    17: None,                    # MINIJUST Legal Review
                    18: None,                    # Awarded
                    19: None,                    # Completed
                }
                
                responsible_role = stage_responsibility.get(next_stage.order)
                
                if responsible_role:
                    # Get users with the responsible role
                    recipients = User.objects.filter(role__name=responsible_role)
                    
                    for recipient in recipients:
                        Notification.objects.create(
                            user=recipient,
                            title=f'Action Required: {next_stage.name}',
                            message=f'Submission {submission.tracking_reference} ({submission.item_name}) is now waiting for {responsible_role} action at stage: {next_stage.name}',
                            notification_type='approval_required',
                            priority='high',
                            action_url=f'/dashboard/procurement/submissions/{submission.id}/',
                            related_object_type='Submission',
                            related_object_id=str(submission.id),
                        )

                messages.success(request, 'Submission approved successfully.')
            else:
                messages.error(request, 'Unable to determine the next stage.')
        except Submission.DoesNotExist:
            messages.error(request, 'Submission not found.')
    return redirect('procurement_submission_detail', submission_id=submission_id)
