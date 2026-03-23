"""
URL patterns for reports app.
"""
from django.urls import path
from .views import (
    DashboardView,
    ProcurementAnalyticsView,
    ComplianceReportView,
    ExportReportView
)

urlpatterns = [
    path('dashboard/', DashboardView.as_view(), name='reports_dashboard'),
    path('analytics/', ProcurementAnalyticsView.as_view(), name='analytics'),
    path('compliance/', ComplianceReportView.as_view(), name='compliance'),
    path('export/', ExportReportView.as_view(), name='export'),
]
