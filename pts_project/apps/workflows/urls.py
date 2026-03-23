"""
URL patterns for workflows app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WorkflowStageViewSet,
    WorkflowHistoryViewSet,
    WorkflowSummaryView,
    WorkflowTransitionView,
    DeadlineViewSet,
    WorkflowConfigurationViewSet
)

router = DefaultRouter()
router.register(r'stages', WorkflowStageViewSet, basename='workflow-stage')
router.register(r'history', WorkflowHistoryViewSet, basename='workflow-history')
router.register(r'deadlines', DeadlineViewSet, basename='deadline')
router.register(r'configurations', WorkflowConfigurationViewSet, basename='workflow-config')

urlpatterns = [
    path('summary/', WorkflowSummaryView.as_view(), name='workflow-summary'),
    path('transition/', WorkflowTransitionView.as_view(), name='workflow-transition'),
    path('', include(router.urls)),
]
