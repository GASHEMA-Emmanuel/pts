"""
Views for Reports and Analytics.
"""
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Sum, Avg, Q, F
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone
from datetime import timedelta
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.core.permissions import IsAdminOrCBM
from apps.procurement.models import ProcurementCall, Submission, Bid
from apps.workflows.models import WorkflowStage, WorkflowHistory
from apps.divisions.models import Division
from apps.accounts.models import User


class DashboardView(APIView):
    """
    Main dashboard view with key metrics.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Get dashboard data",
        tags=["Reports"],
        parameters=[
            OpenApiParameter(name='period', description='Time period (7d, 30d, 90d, all)', type=str),
        ]
    )
    def get(self, request):
        """Get dashboard metrics based on user role."""
        user = request.user
        period = request.query_params.get('period', '30d')
        
        # Calculate date range
        now = timezone.now()
        if period == '7d':
            start_date = now - timedelta(days=7)
        elif period == '30d':
            start_date = now - timedelta(days=30)
        elif period == '90d':
            start_date = now - timedelta(days=90)
        else:
            start_date = None
        
        # Base querysets
        calls = ProcurementCall.objects.all()
        submissions = Submission.objects.filter(is_deleted=False)
        
        if start_date:
            calls = calls.filter(created_at__gte=start_date)
            submissions = submissions.filter(created_at__gte=start_date)
        
        # Filter by division for non-admin users
        if user.role and user.role.name not in ['Admin', 'CBM', 'Procurement Team']:
            submissions = submissions.filter(division=user.division)
        
        # Build dashboard data
        data = {
            'summary': self._get_summary(calls, submissions),
            'recent_activity': self._get_recent_activity(submissions),
            'by_status': self._get_by_status(submissions),
            'by_division': self._get_by_division(submissions) if user.role and user.role.name in ['Admin', 'CBM'] else None,
            'upcoming_deadlines': self._get_upcoming_deadlines(user),
            'workflow_overview': self._get_workflow_overview(submissions),
        }
        
        return Response(data)
    
    def _get_summary(self, calls, submissions):
        """Get summary statistics."""
        return {
            'total_calls': calls.filter(status='Active').count(),
            'total_submissions': submissions.count(),
            'pending_submissions': submissions.filter(
                status__in=['Submitted', 'Under Review']
            ).count(),
            'approved_submissions': submissions.filter(status='Approved').count(),
            'total_budget': submissions.aggregate(total=Sum('total_budget'))['total'] or 0,
        }
    
    def _get_recent_activity(self, submissions):
        """Get recent submission activity."""
        return list(
            submissions.values('status')
            .annotate(
                date=TruncDate('created_at'),
                count=Count('id')
            )
            .order_by('-date')[:30]
        )
    
    def _get_by_status(self, submissions):
        """Get submissions by status."""
        return list(
            submissions.values('status')
            .annotate(
                count=Count('id'),
                budget=Sum('total_budget')
            )
        )
    
    def _get_by_division(self, submissions):
        """Get submissions by division."""
        return list(
            submissions.values('division__name')
            .annotate(
                count=Count('id'),
                budget=Sum('total_budget')
            )
        )
    
    def _get_upcoming_deadlines(self, user):
        """Get upcoming deadlines."""
        now = timezone.now()
        next_week = now + timedelta(days=7)
        
        calls = ProcurementCall.objects.filter(
            status='Active',
            end_date__gte=now,
            end_date__lte=next_week
        ).values('id', 'title', 'reference_number', 'end_date')[:5]
        
        return list(calls)
    
    def _get_workflow_overview(self, submissions):
        """Get workflow stage overview."""
        return list(
            submissions.values('current_stage__name', 'current_stage__order')
            .annotate(count=Count('id'))
            .order_by('current_stage__order')
        )


class ProcurementAnalyticsView(APIView):
    """
    Detailed procurement analytics.
    """
    permission_classes = [IsAdminOrCBM]
    
    @extend_schema(
        summary="Get procurement analytics",
        tags=["Reports"],
        parameters=[
            OpenApiParameter(name='year', description='Year filter', type=int),
            OpenApiParameter(name='division_id', description='Division filter', type=int),
        ]
    )
    def get(self, request):
        """Get detailed procurement analytics."""
        year = request.query_params.get('year', timezone.now().year)
        division_id = request.query_params.get('division_id')
        
        submissions = Submission.objects.filter(
            is_deleted=False,
            created_at__year=year
        )
        
        if division_id:
            submissions = submissions.filter(division_id=division_id)
        
        data = {
            'yearly_overview': self._get_yearly_overview(submissions),
            'monthly_trend': self._get_monthly_trend(submissions),
            'by_priority': self._get_by_priority(submissions),
            'cycle_time_analysis': self._get_cycle_time_analysis(submissions),
            'budget_analysis': self._get_budget_analysis(submissions),
            'division_comparison': self._get_division_comparison(year),
        }
        
        return Response(data)
    
    def _get_yearly_overview(self, submissions):
        """Get yearly overview statistics."""
        return submissions.aggregate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='Approved')),
            rejected=Count('id', filter=Q(status='Rejected')),
            completed=Count('id', filter=Q(status='Completed')),
            total_budget=Sum('total_budget'),
            avg_budget=Avg('total_budget'),
        )
    
    def _get_monthly_trend(self, submissions):
        """Get monthly submission trend."""
        return list(
            submissions.annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(
                count=Count('id'),
                budget=Sum('total_budget')
            )
            .order_by('month')
        )
    
    def _get_by_priority(self, submissions):
        """Get submissions by priority."""
        return list(
            submissions.values('priority')
            .annotate(
                count=Count('id'),
                budget=Sum('total_budget')
            )
        )
    
    def _get_cycle_time_analysis(self, submissions):
        """Analyze time spent at each workflow stage."""
        from apps.workflows.models import WorkflowHistory
        
        # Get average time at each stage
        stage_times = []
        for stage in WorkflowStage.objects.all():
            histories = WorkflowHistory.objects.filter(
                from_stage=stage,
                time_at_previous_stage__isnull=False
            )
            
            if histories.exists():
                avg_time = histories.aggregate(
                    avg=Avg('time_at_previous_stage')
                )['avg']
                
                stage_times.append({
                    'stage': stage.name,
                    'avg_days': avg_time.days if avg_time else 0
                })
        
        return stage_times
    
    def _get_budget_analysis(self, submissions):
        """Analyze budget distribution."""
        ranges = [
            (0, 1000000, 'Under 1M RWF'),
            (1000000, 10000000, '1M - 10M RWF'),
            (10000000, 50000000, '10M - 50M RWF'),
            (50000000, 100000000, '50M - 100M RWF'),
            (100000000, float('inf'), 'Over 100M RWF'),
        ]
        
        result = []
        for min_val, max_val, label in ranges:
            count = submissions.filter(
                total_budget__gte=min_val,
                total_budget__lt=max_val
            ).count()
            result.append({'range': label, 'count': count})
        
        return result
    
    def _get_division_comparison(self, year):
        """Compare divisions by performance."""
        return list(
            Division.objects.annotate(
                submission_count=Count(
                    'submissions',
                    filter=Q(submissions__created_at__year=year)
                ),
                total_budget=Sum(
                    'submissions__total_budget',
                    filter=Q(submissions__created_at__year=year)
                ),
                approved_count=Count(
                    'submissions',
                    filter=Q(
                        submissions__created_at__year=year,
                        submissions__status='Approved'
                    )
                )
            ).values(
                'name', 'submission_count', 'total_budget', 'approved_count'
            )
        )


class ComplianceReportView(APIView):
    """
    Compliance reports aligned with RPPA requirements.
    """
    permission_classes = [IsAdminOrCBM]
    
    @extend_schema(
        summary="Get compliance report",
        tags=["Reports"],
    )
    def get(self, request):
        """Get compliance metrics."""
        now = timezone.now()
        
        # Calculate compliance metrics
        submissions = Submission.objects.filter(is_deleted=False)
        
        # On-time submission rate
        total = submissions.count()
        on_time = submissions.filter(
            submitted_at__lte=F('call__end_date')
        ).count()
        
        # Deadline adherence by stage
        from apps.workflows.models import Deadline
        deadlines = Deadline.objects.all()
        total_deadlines = deadlines.count()
        met_deadlines = deadlines.filter(is_overdue=False).count()
        
        data = {
            'submission_compliance': {
                'total_submissions': total,
                'on_time_submissions': on_time,
                'late_submissions': total - on_time,
                'on_time_rate': round((on_time / total * 100) if total > 0 else 0, 2)
            },
            'deadline_adherence': {
                'total_deadlines': total_deadlines,
                'met': met_deadlines,
                'missed': total_deadlines - met_deadlines,
                'adherence_rate': round((met_deadlines / total_deadlines * 100) if total_deadlines > 0 else 0, 2)
            },
            'workflow_compliance': self._get_workflow_compliance(submissions),
            'audit_summary': self._get_audit_summary(),
        }
        
        return Response(data)
    
    def _get_workflow_compliance(self, submissions):
        """Check workflow compliance."""
        return {
            'proper_approvals': submissions.filter(
                status='Approved',
                workflow_history__action='approve'
            ).distinct().count(),
            'with_justification': submissions.exclude(
                justification__isnull=True
            ).exclude(justification='').count(),
            'documented_decisions': WorkflowHistory.objects.exclude(
                comments__isnull=True
            ).exclude(comments='').count()
        }
    
    def _get_audit_summary(self):
        """Get audit trail summary."""
        return {
            'total_actions_logged': WorkflowHistory.objects.count(),
            'unique_users_involved': WorkflowHistory.objects.values('action_by').distinct().count(),
            'actions_last_30_days': WorkflowHistory.objects.filter(
                created_at__gte=timezone.now() - timedelta(days=30)
            ).count()
        }


class ExportReportView(APIView):
    """
    Export reports in various formats.
    """
    permission_classes = [IsAdminOrCBM]
    
    @extend_schema(
        summary="Export report data",
        tags=["Reports"],
        parameters=[
            OpenApiParameter(name='report_type', description='Type of report'),
            OpenApiParameter(name='format', description='Export format (json, csv)'),
            OpenApiParameter(name='start_date', description='Start date'),
            OpenApiParameter(name='end_date', description='End date'),
        ]
    )
    def get(self, request):
        """Export report data."""
        report_type = request.query_params.get('report_type', 'submissions')
        export_format = request.query_params.get('format', 'json')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        # Get data based on report type
        if report_type == 'submissions':
            data = self._get_submissions_report(start_date, end_date)
        elif report_type == 'divisions':
            data = self._get_divisions_report(start_date, end_date)
        elif report_type == 'workflow':
            data = self._get_workflow_report(start_date, end_date)
        else:
            return Response(
                {'error': 'Invalid report type'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if export_format == 'csv':
            # For CSV, return instructions (actual CSV generation would need more setup)
            return Response({
                'message': 'CSV export coming soon',
                'data': data
            })
        
        return Response(data)
    
    def _get_submissions_report(self, start_date, end_date):
        """Get submissions report data."""
        queryset = Submission.objects.filter(is_deleted=False)
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return list(queryset.values(
            'tracking_reference', 'item_name', 'division__name',
            'status', 'total_budget', 'priority',
            'created_at', 'submitted_at'
        ))
    
    def _get_divisions_report(self, start_date, end_date):
        """Get divisions report data."""
        return list(Division.objects.annotate(
            submission_count=Count('submissions'),
            total_budget=Sum('submissions__total_budget'),
            user_count=Count('users')
        ).values(
            'name', 'submission_count', 'total_budget', 'user_count'
        ))
    
    def _get_workflow_report(self, start_date, end_date):
        """Get workflow report data."""
        queryset = WorkflowHistory.objects.all()
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return list(queryset.values(
            'submission__tracking_reference',
            'from_stage__name', 'to_stage__name',
            'action', 'action_by__full_name',
            'created_at'
        )[:1000])  # Limit to 1000 records
