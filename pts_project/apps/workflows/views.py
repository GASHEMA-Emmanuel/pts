"""
Views for Workflow management.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Sum, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.core.permissions import IsAdmin, IsAdminOrCBM, CanUpdateWorkflow
from .models import WorkflowStage, WorkflowHistory, WorkflowConfiguration, Deadline
from .serializers import (
    WorkflowStageSerializer, WorkflowStageMinimalSerializer,
    WorkflowHistorySerializer, WorkflowHistoryCreateSerializer,
    WorkflowConfigurationSerializer,
    DeadlineSerializer,
    WorkflowTransitionSerializer, WorkflowSummarySerializer
)


@extend_schema_view(
    list=extend_schema(summary="List all workflow stages", tags=["Workflows"]),
    retrieve=extend_schema(summary="Get workflow stage details", tags=["Workflows"]),
)
class WorkflowStageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing workflow stages.
    Stages are predefined and cannot be modified via API.
    """
    queryset = WorkflowStage.objects.all()
    serializer_class = WorkflowStageSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return WorkflowStageMinimalSerializer
        return WorkflowStageSerializer
    
    @extend_schema(summary="Get submissions at a stage", tags=["Workflows"])
    @action(detail=True, methods=['get'])
    def submissions(self, request, pk=None):
        """Get all submissions currently at this stage."""
        stage = self.get_object()
        submissions = stage.current_submissions.all()
        
        # Filter by user's division if not admin/CBM
        user = request.user
        if user.role and user.role.name not in ['Admin', 'CBM', 'Procurement Team']:
            submissions = submissions.filter(division=user.division)
        
        from apps.procurement.serializers import SubmissionListSerializer
        serializer = SubmissionListSerializer(submissions, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(summary="List workflow history", tags=["Workflows"]),
    retrieve=extend_schema(summary="Get workflow history details", tags=["Workflows"]),
)
class WorkflowHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing workflow history (audit trail).
    """
    queryset = WorkflowHistory.objects.select_related(
        'from_stage', 'to_stage', 'action_by', 'submission'
    ).all()
    serializer_class = WorkflowHistorySerializer
    filterset_fields = ['submission', 'action', 'action_by']
    ordering_fields = ['created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by submission
        submission_id = self.request.query_params.get('submission_id')
        if submission_id:
            queryset = queryset.filter(submission_id=submission_id)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset


class WorkflowSummaryView(APIView):
    """
    View for workflow summary dashboard.
    Shows count of submissions at each stage.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Get workflow summary",
        tags=["Workflows"],
        responses={200: WorkflowSummarySerializer(many=True)}
    )
    def get(self, request):
        """Get summary of submissions at each workflow stage."""
        user = request.user
        
        # Base queryset
        from apps.procurement.models import Submission
        submissions = Submission.objects.filter(is_deleted=False)
        
        # Filter by division if needed
        if user.role and user.role.name not in ['Admin', 'CBM', 'Procurement Team']:
            submissions = submissions.filter(division=user.division)
        
        # Get summary by stage
        summary = []
        for stage in WorkflowStage.objects.all():
            stage_submissions = submissions.filter(current_stage=stage)
            
            # Count overdue
            overdue_count = 0
            for sub in stage_submissions:
                deadline = sub.deadlines.filter(stage=stage).first()
                if deadline and deadline.is_overdue:
                    overdue_count += 1
            
            agg = stage_submissions.aggregate(
                count=Count('id'),
                total_budget=Sum('total_budget')
            )
            
            summary.append({
                'stage_id': stage.id,
                'stage_name': stage.name,
                'stage_order': stage.order,
                'color': stage.color,
                'count': agg['count'] or 0,
                'total_budget': agg['total_budget'] or 0,
                'overdue_count': overdue_count
            })
        
        serializer = WorkflowSummarySerializer(summary, many=True)
        return Response(serializer.data)


class WorkflowTransitionView(APIView):
    """
    View for transitioning submissions between workflow stages.
    """
    permission_classes = [CanUpdateWorkflow]
    
    @extend_schema(
        summary="Transition submission to new stage",
        tags=["Workflows"],
        request=WorkflowTransitionSerializer,
    )
    def post(self, request):
        """Transition a submission to a new workflow stage."""
        serializer = WorkflowTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        from apps.procurement.models import Submission
        
        try:
            submission = Submission.objects.get(
                id=serializer.validated_data['submission_id']
            )
        except Submission.DoesNotExist:
            return Response(
                {'error': 'Submission not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        to_stage = WorkflowStage.objects.get(
            id=serializer.validated_data['to_stage_id']
        )
        
        from_stage = submission.current_stage
        comments = serializer.validated_data.get('comments', '')
        approval_date = serializer.validated_data.get('approval_date')
        
        # Validate approval_date is only set for stages from Publish Plan (order 6) onwards
        publish_plan_stage = WorkflowStage.objects.filter(name='Publish Plan').first()
        if approval_date and publish_plan_stage:
            if to_stage.order < publish_plan_stage.order:
                return Response(
                    {'error': f'Approval date can only be set from {publish_plan_stage.name} stage onwards'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Create history record with approval_date
        WorkflowHistory.objects.create(
            submission=submission,
            from_stage=from_stage,
            to_stage=to_stage,
            action_by=request.user,
            action='status_update',
            comments=comments,
            approval_date=approval_date
        )
        
        # Update submission
        submission.current_stage = to_stage
        submission.status = to_stage.name
        submission.save()
        
        return Response({
            'success': True,
            'message': f'Submission moved to {to_stage.name}',
            'from_stage': from_stage.name if from_stage else None,
            'to_stage': to_stage.name,
            'approval_date': approval_date
        })


@extend_schema_view(
    list=extend_schema(summary="List deadlines", tags=["Workflows"]),
    retrieve=extend_schema(summary="Get deadline details", tags=["Workflows"]),
)
class DeadlineViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing and managing deadlines.
    """
    queryset = Deadline.objects.select_related('submission', 'stage').all()
    serializer_class = DeadlineSerializer
    filterset_fields = ['submission', 'stage', 'is_overdue', 'escalated']
    ordering_fields = ['deadline', 'created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Update overdue status
        now = timezone.now()
        queryset.filter(deadline__lt=now, is_overdue=False).update(is_overdue=True)
        
        # Filter upcoming only
        upcoming = self.request.query_params.get('upcoming')
        if upcoming and upcoming.lower() == 'true':
            queryset = queryset.filter(deadline__gte=now, is_overdue=False)
        
        # Filter overdue only
        overdue = self.request.query_params.get('overdue')
        if overdue and overdue.lower() == 'true':
            queryset = queryset.filter(is_overdue=True)
        
        return queryset
    
    @extend_schema(summary="Get overdue deadlines", tags=["Workflows"])
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get all overdue deadlines."""
        now = timezone.now()
        deadlines = self.get_queryset().filter(
            deadline__lt=now
        ).order_by('deadline')
        
        serializer = self.get_serializer(deadlines, many=True)
        return Response(serializer.data)
    
    @extend_schema(summary="Get upcoming deadlines", tags=["Workflows"])
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming deadlines (next 7 days)."""
        now = timezone.now()
        from datetime import timedelta
        next_week = now + timedelta(days=7)
        
        deadlines = self.get_queryset().filter(
            deadline__gte=now,
            deadline__lte=next_week
        ).order_by('deadline')
        
        serializer = self.get_serializer(deadlines, many=True)
        return Response(serializer.data)


class WorkflowConfigurationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing workflow configurations.
    Admin only.
    """
    queryset = WorkflowConfiguration.objects.select_related('stage').all()
    serializer_class = WorkflowConfigurationSerializer
    permission_classes = [IsAdmin]
