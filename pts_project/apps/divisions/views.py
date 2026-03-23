"""
Views for Division management.
"""
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Sum, Q
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.core.permissions import IsAdmin, IsAdminOrCBM
from .models import Division
from .serializers import (
    DivisionSerializer,
    DivisionMinimalSerializer,
    DivisionStatsSerializer
)


@extend_schema_view(
    list=extend_schema(summary="List all divisions", tags=["Divisions"]),
    retrieve=extend_schema(summary="Get division details", tags=["Divisions"]),
    create=extend_schema(summary="Create a new division", tags=["Divisions"]),
    update=extend_schema(summary="Update a division", tags=["Divisions"]),
    partial_update=extend_schema(summary="Partial update a division", tags=["Divisions"]),
    destroy=extend_schema(summary="Delete a division", tags=["Divisions"]),
)
class DivisionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing divisions.
    Only admins can create/update/delete divisions.
    """
    queryset = Division.objects.all()
    serializer_class = DivisionSerializer
    filterset_fields = ['is_active']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'created_at']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return [permissions.IsAuthenticated()]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return DivisionMinimalSerializer
        return DivisionSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Non-admin users only see active divisions
        if not self.request.user.has_role('Admin'):
            queryset = queryset.filter(is_active=True)
        
        return queryset
    
    @extend_schema(summary="Get division statistics", tags=["Divisions"])
    @action(detail=False, methods=['get'], permission_classes=[IsAdminOrCBM])
    def stats(self, request):
        """Get statistics for all divisions."""
        divisions = Division.objects.filter(is_active=True).annotate(
            user_count=Count('users', filter=Q(users__is_active=True)),
            submission_count=Count('submissions'),
            pending_submissions=Count(
                'submissions',
                filter=Q(submissions__status__in=['Draft', 'Submitted', 'Under Review'])
            ),
            approved_submissions=Count(
                'submissions',
                filter=Q(submissions__status='Approved')
            ),
            total_budget=Sum('submissions__total_budget')
        )
        
        serializer = DivisionStatsSerializer(divisions, many=True)
        return Response(serializer.data)
    
    @extend_schema(summary="Get users in a division", tags=["Divisions"])
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """Get all users in a specific division."""
        division = self.get_object()
        users = division.users.filter(is_active=True)
        
        from apps.accounts.serializers import UserMinimalSerializer
        serializer = UserMinimalSerializer(users, many=True)
        return Response(serializer.data)
    
    @extend_schema(summary="Get submissions from a division", tags=["Divisions"])
    @action(detail=True, methods=['get'])
    def submissions(self, request, pk=None):
        """Get all submissions from a specific division."""
        division = self.get_object()
        
        # Check if user has access to this division
        if not request.user.can_access_division(division.id):
            return Response(
                {'error': 'You do not have access to this division'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        submissions = division.submissions.all()
        
        from apps.procurement.serializers import SubmissionListSerializer
        serializer = SubmissionListSerializer(submissions, many=True)
        return Response(serializer.data)
