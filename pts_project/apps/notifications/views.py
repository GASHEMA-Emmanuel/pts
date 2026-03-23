"""
Views for Notification management.
"""
from rest_framework import viewsets, status, permissions, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import Notification, NotificationPreference, EmailLog
from .serializers import (
    NotificationSerializer, NotificationListSerializer,
    NotificationPreferenceSerializer, EmailLogSerializer,
    NotificationCountSerializer
)


@extend_schema_view(
    list=extend_schema(summary="List user notifications", tags=["Notifications"]),
    retrieve=extend_schema(summary="Get notification details", tags=["Notifications"]),
)
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing and managing notifications.
    Users can only see their own notifications.
    """
    serializer_class = NotificationSerializer
    filterset_fields = ['notification_type', 'is_read', 'priority']
    ordering_fields = ['created_at', 'priority']
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        if self.action == 'list':
            return NotificationListSerializer
        return NotificationSerializer
    
    @extend_schema(summary="Mark notification as read", tags=["Notifications"])
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a single notification as read."""
        notification = self.get_object()
        notification.mark_as_read()
        return Response({'success': True, 'message': 'Notification marked as read'})
    
    @extend_schema(summary="Mark all notifications as read", tags=["Notifications"])
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read."""
        count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        
        return Response({
            'success': True,
            'message': f'{count} notifications marked as read'
        })
    
    @extend_schema(summary="Get unread notifications", tags=["Notifications"])
    @action(detail=False, methods=['get'])
    def unread(self, request):
        """Get unread notifications."""
        notifications = self.get_queryset().filter(is_read=False)
        serializer = NotificationListSerializer(notifications, many=True)
        return Response(serializer.data)
    
    @extend_schema(summary="Get notification counts", tags=["Notifications"])
    @action(detail=False, methods=['get'])
    def counts(self, request):
        """Get notification counts."""
        queryset = self.get_queryset()
        
        total = queryset.count()
        unread = queryset.filter(is_read=False).count()
        
        by_type = dict(
            queryset.values_list('notification_type')
            .annotate(count=Count('id'))
        )
        
        data = {
            'total': total,
            'unread': unread,
            'by_type': by_type
        }
        
        serializer = NotificationCountSerializer(data)
        return Response(serializer.data)
    
    @extend_schema(summary="Delete old notifications", tags=["Notifications"])
    @action(detail=False, methods=['delete'])
    def clear_old(self, request):
        """Delete notifications older than 30 days."""
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=30)
        
        count = Notification.objects.filter(
            user=request.user,
            is_read=True,
            created_at__lt=cutoff
        ).delete()[0]
        
        return Response({
            'success': True,
            'message': f'{count} old notifications deleted'
        })


class NotificationPreferenceView(generics.RetrieveUpdateAPIView):
    """
    View for managing notification preferences.
    """
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        obj, created = NotificationPreference.objects.get_or_create(
            user=self.request.user
        )
        return obj
    
    @extend_schema(summary="Get notification preferences", tags=["Notifications"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(summary="Update notification preferences", tags=["Notifications"])
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)
    
    @extend_schema(summary="Partial update notification preferences", tags=["Notifications"])
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class EmailLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing email logs (admin only).
    """
    queryset = EmailLog.objects.select_related('recipient_user', 'notification').all()
    serializer_class = EmailLogSerializer
    filterset_fields = ['status', 'recipient_email']
    ordering_fields = ['created_at', 'sent_at']
    
    def get_queryset(self):
        # Only show user's own emails unless admin
        if self.request.user.has_role('Admin'):
            return super().get_queryset()
        return EmailLog.objects.filter(recipient_user=self.request.user)
