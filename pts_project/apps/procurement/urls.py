"""
URL patterns for procurement app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProcurementCallViewSet,
    SubmissionViewSet,
    BidViewSet,
    CommentViewSet,
    AttachmentViewSet
)
from . import views

router = DefaultRouter()
router.register(r'calls', ProcurementCallViewSet, basename='procurement-call')
router.register(r'submissions', SubmissionViewSet, basename='submission')
router.register(r'bids', BidViewSet, basename='bid')
router.register(r'comments', CommentViewSet, basename='comment')
router.register(r'attachments', AttachmentViewSet, basename='attachment')

urlpatterns = [
    path('', include(router.urls)),
    path('submissions/<uuid:submission_id>/request-clarification/', views.request_clarification, name='procurement_request_clarification'),
    path('submissions/<uuid:submission_id>/approve/', views.approve_submission, name='procurement_approve_submission'),
]
