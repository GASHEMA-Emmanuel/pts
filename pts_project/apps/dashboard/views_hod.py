"""
HOD/DM Reports view for submission analytics.
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import timedelta


@login_required
def hod_reports_view(request):
    """
    HOD/DM reports showing submission analytics and progress.
    Supports date range filtering via ?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
    """
    user = request.user
    
    # Check if user has HOD/DM role and belongs to a division
    if not user.role or user.role.name != 'HOD/DM':
        return redirect('dashboard')
    
    if not user.division:
        return render(request, 'dashboard/error.html', {'error': 'You are not assigned to a division'})
    
    from apps.procurement.models import Submission
    from apps.workflows.models import WorkflowHistory
    from apps.contracts.models import Contract
    
    # Date range filter
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    date_from = parse_date(date_from_str) if date_from_str else None
    date_to = parse_date(date_to_str) if date_to_str else None

    # Get all submissions for this division
    division = user.division
    all_submissions = Submission.objects.filter(
        division=division,
        is_deleted=False
    )

    # Apply date range filters
    if date_from:
        all_submissions = all_submissions.filter(created_at__date__gte=date_from)
    if date_to:
        all_submissions = all_submissions.filter(created_at__date__lte=date_to)
    
    # Overall Statistics — organised by internal workflow stage
    TENDER_STAGES = [
        'Prepare Tender Document', 'CBM Review TD', 'Publication of TD',
        'Bidding', 'Evaluation', 'CBM Approval', 'Notify Bidders',
        'Contract Negotiation', 'Contract Drafting', 'Legal Review',
        'Supplier Approval', 'MINIJUST Legal Review', 'Awarded',
    ]
    stats = {
        'total_submissions': all_submissions.count(),
        'draft': all_submissions.filter(status='Draft').count(),
        'with_procurement': all_submissions.filter(
            status__in=['HOD/DM Submit', 'Review of Procurement Draft', 'Submit Compiled Document']
        ).count(),
        'with_cbm': all_submissions.filter(status='CBM Review').count(),
        'plan_published': all_submissions.filter(status='Publish Plan').count(),
        'in_tender': all_submissions.filter(status__in=TENDER_STAGES).count(),
        'returned': all_submissions.filter(status='Returned').count(),
        'rejected': all_submissions.filter(status='Rejected').count(),
        'completed': all_submissions.filter(status='Completed').count(),
    }
    
    # Calculate percentages
    total = stats['total_submissions'] or 1
    stats['plan_published_pct'] = int(stats['plan_published'] / total * 100)
    stats['completed_pct'] = int(stats['completed'] / total * 100)
    stats['in_tender_pct'] = int(stats['in_tender'] / total * 100)
    
    # Budget Analysis
    total_budget = all_submissions.aggregate(Sum('total_budget'))['total_budget__sum'] or 0
    submitted_budget = all_submissions.filter(status__in=['HOD/DM Submit', 'Review of Procurement Draft', 'Returned', 'Submit Compiled Document', 'CBM Review', 'Publish Plan', 'Prepare Tender Document', 'CBM Review TD', 'Publication of TD', 'Bidding', 'Evaluation', 'CBM Approval', 'Notify Bidders', 'Contract Negotiation', 'Contract Drafting', 'Legal Review', 'Supplier Approval', 'MINIJUST Legal Review', 'Awarded', 'Completed']).aggregate(Sum('total_budget'))['total_budget__sum'] or 0
    approved_budget = all_submissions.filter(status__in=['Publish Plan', 'Prepare Tender Document', 'CBM Review TD', 'Publication of TD', 'Bidding', 'Evaluation', 'CBM Approval', 'Notify Bidders', 'Contract Negotiation', 'Contract Drafting', 'Legal Review', 'Supplier Approval', 'MINIJUST Legal Review', 'Awarded', 'Completed']).aggregate(Sum('total_budget'))['total_budget__sum'] or 0
    completed_budget = all_submissions.filter(status='Completed').aggregate(Sum('total_budget'))['total_budget__sum'] or 0
    
    budget_stats = {
        'total_budget': total_budget,
        'submitted_budget': submitted_budget,
        'approved_budget': approved_budget,
        'completed_budget': completed_budget,
        'pending_approval': submitted_budget - approved_budget,
    }
    
    # Submissions by Priority
    submissions_by_priority = all_submissions.values('priority').annotate(
        total=Count('id'),
        approved=Count('id', filter=Q(status='Approved')),
        completed=Count('id', filter=Q(status='Completed'))
    ).order_by('priority')
    
    # Submissions by Status
    submissions_by_status = all_submissions.values('status').annotate(
        count=Count('id'),
        total_budget=Sum('total_budget')
    ).order_by('-count')
    
    # Timeline Analysis - Average days to approve
    approved_submissions = all_submissions.filter(
        status__in=['Approved', 'Published', 'Bidding', 'Evaluation', 'Awarded', 'Completed'],
        created_at__isnull=False
    )
    
    if approved_submissions.exists():
        avg_days_to_approve = 0
        count = 0
        for sub in approved_submissions:
            # Get the approval history
            approval_history = WorkflowHistory.objects.filter(
                submission=sub,
                to_stage__order=5  # Stage 5 is "CBM Review" (first stage after HOD/DM internal flow)
            ).first()
            
            if approval_history:
                days = (approval_history.created_at - sub.created_at).days
                if days >= 0:
                    avg_days_to_approve += days
                    count += 1
        
        avg_days_to_approve = int(avg_days_to_approve / count) if count > 0 else 0
    else:
        avg_days_to_approve = 0
    
    # Recent Submissions
    recent_submissions = all_submissions.order_by('-created_at')[:10]
    
    # Overdue Submissions (submitted more than 14 days ago, not yet approved)
    fourteen_days_ago = timezone.now() - timedelta(days=14)
    overdue_submissions = all_submissions.filter(
        status__in=['Draft', 'HOD/DM Submit', 'Review of Procurement Draft', 'CBM Review'],
        created_at__lt=fourteen_days_ago
    ).count()

    # ── CONTRACTS for this division ────────────────────────────
    all_contracts = Contract.objects.filter(division=division)
    if date_from:
        all_contracts = all_contracts.filter(created_at__date__gte=date_from)
    if date_to:
        all_contracts = all_contracts.filter(created_at__date__lte=date_to)

    contract_stats = {
        'total': all_contracts.count(),
        'active': all_contracts.filter(status='Active').count(),
        'renewed': all_contracts.filter(status='Renewed').count(),
        'completed': all_contracts.filter(status='Completed').count(),
        'cancelled': all_contracts.filter(status='Cancelled').count(),
    }
    total_c = contract_stats['total'] or 1
    contract_stats['active_pct'] = int(contract_stats['active'] / total_c * 100)
    contract_stats['completed_pct'] = int(contract_stats['completed'] / total_c * 100)

    contract_budget_total = all_contracts.aggregate(Sum('contract_budget'))['contract_budget__sum'] or 0
    contract_budget_active = all_contracts.filter(status='Active').aggregate(Sum('contract_budget'))['contract_budget__sum'] or 0
    contract_budget_completed = all_contracts.filter(status='Completed').aggregate(Sum('contract_budget'))['contract_budget__sum'] or 0
    contract_budget_stats = {
        'total': contract_budget_total,
        'active': contract_budget_active,
        'completed': contract_budget_completed,
    }

    contracts_by_type = all_contracts.values('contract_type').annotate(
        total=Count('id'),
        active=Count('id', filter=Q(status='Active')),
        completed=Count('id', filter=Q(status='Completed')),
    ).order_by('-total')

    recent_contracts = all_contracts.order_by('-created_at')[:8]

    context = {
        'division': division,
        'stats': stats,
        'budget_stats': budget_stats,
        'submissions_by_priority': submissions_by_priority,
        'submissions_by_status': submissions_by_status,
        'avg_days_to_approve': avg_days_to_approve,
        'recent_submissions': recent_submissions,
        'overdue_submissions': overdue_submissions,
        # contracts
        'contract_stats': contract_stats,
        'contract_budget_stats': contract_budget_stats,
        'contracts_by_type': contracts_by_type,
        'recent_contracts': recent_contracts,
        'date_from': date_from_str,
        'date_to': date_to_str,
        'date_filtered': bool(date_from or date_to),
    }
    
    return render(request, 'dashboard/hod_reports.html', context)
