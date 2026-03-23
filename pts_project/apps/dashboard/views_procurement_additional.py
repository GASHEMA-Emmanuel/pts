"""
Additional Procurement Team views for submissions list and reports.
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import timedelta, datetime


@login_required
def procurement_submissions_list_view(request):
    """
    Procurement Team submissions list - shows ALL submissions from all divisions.
    Submissions remain visible after approval/clarification to provide a complete overview.
    Similar to Submissions Snapshot.
    """
    user = request.user
    
    if user.role and user.role.name != 'Procurement Team':
        return redirect('dashboard')
    
    from apps.procurement.models import Submission
    from apps.divisions.models import Division
    
    # Get ALL submissions from ALL divisions (not just draft/review) - provides complete visibility
    # Submissions stay visible after approval/clarification for reference and tracking
    submissions = Submission.objects.filter(
        is_deleted=False
    ).select_related('division', 'call', 'current_stage', 'submitted_by').order_by('-created_at')
    
    # Search
    search_query = request.GET.get('search', '').strip()
    if search_query:
        submissions = submissions.filter(
            Q(item_name__icontains=search_query) |
            Q(tracking_reference__icontains=search_query) |
            Q(division__name__icontains=search_query) |
            Q(justification__icontains=search_query)
        )
    
    # Filter by status (optional)
    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        submissions = submissions.filter(status=status_filter)
    
    # Filter by division (optional - for user convenience, but default is all divisions)
    division_filter = request.GET.get('division', '').strip()
    if division_filter:
        submissions = submissions.filter(division_id=division_filter)
    
    # Filter by priority
    priority_filter = request.GET.get('priority', '').strip()
    if priority_filter:
        submissions = submissions.filter(priority=priority_filter)
    
    # Get divisions for filter dropdown
    divisions = Division.objects.all()
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(submissions, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'submissions': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'divisions': divisions,
        'search_query': search_query,
        'active_status': status_filter,
        'active_division': division_filter,
        'active_priority': priority_filter,
        'total_count': paginator.count,
        'user_role': user.role.name if user.role else None,
        'actionable_stages': [2, 3],  # Procurement Team handles HOD/DM Submit (2) and Review of Procurement Draft (3)
    }
    
    return render(request, 'procurement/submissions_list.html', context)


@login_required
def procurement_compile_document_list_view(request):
    """
    Procurement Team compiled document pipeline.
    Independent of submission statuses — procurement compiles one document
    covering all divisions, sends to CBM, then publishes.
    """
    user = request.user

    if user.role and user.role.name != 'Procurement Team':
        return redirect('dashboard')

    from apps.procurement.models import CompiledDocument

    compiled_docs = CompiledDocument.objects.select_related('submitted_by').all()
    total_count = compiled_docs.count()
    pending_count = compiled_docs.filter(status='Sent to CBM').count()
    published_count = compiled_docs.filter(status='Published').count()

    if total_count == 0:
        current_step = 1
    elif pending_count > 0:
        current_step = 2
    else:
        current_step = 3

    context = {
        'compiled_docs': compiled_docs,
        'total_count': total_count,
        'pending_count': pending_count,
        'published_count': published_count,
        'current_step': current_step,
    }

    return render(request, 'procurement/compile_document_list.html', context)


@login_required
def procurement_compile_all_view(request):
    """
    Procurement Team submits ONE compiled document covering ALL divisions.
    No prerequisite — this is the starting point. Creates a CompiledDocument
    record, saves the file, and notifies CBM.
    """
    if request.user.role and request.user.role.name != 'Procurement Team':
        return redirect('dashboard')

    if request.method != 'POST':
        return redirect('procurement_compile_document')

    from apps.procurement.models import CompiledDocument
    from apps.notifications.models import Notification
    from apps.accounts.models import User as PtsUser

    document_name = request.POST.get('document_name', '').strip()
    description = request.POST.get('description', '').strip()
    uploaded_file = request.FILES.get('compiled_document')

    if not document_name or not uploaded_file:
        messages.error(request, 'Document name and file are required.')
        return redirect('procurement_compile_document')

    # Create the CompiledDocument record (FileField handles storage)
    doc = CompiledDocument.objects.create(
        document_name=document_name,
        description=description,
        file=uploaded_file,
        submitted_by=request.user,
        status='Sent to CBM',
    )

    # Notify all CBM users once
    cbm_users = PtsUser.objects.filter(role__name='CBM', is_active=True)
    for cbm_user in cbm_users:
        Notification.objects.create(
            user=cbm_user,
            title=f'📋 Compiled Document Submitted: {document_name}',
            message=(
                f'Procurement Team has submitted the compiled procurement document '
                f'"{document_name}".'
                + (f' {description}' if description else '')
            ),
            notification_type='submission_status',
            priority='high',
            related_object_type='CompiledDocument',
            related_object_id=str(doc.id),
            action_url='/dashboard/cbm/submissions/',
        )

    messages.success(request, f'Compiled document "{document_name}" submitted. CBM has been notified.')
    return redirect('procurement_compile_document')


@login_required
def procurement_publish_compiled_document_view(request, doc_id):
    """
    Marks a CompiledDocument as Published. CBM performs this action.
    """
    if request.user.role and request.user.role.name not in ['CBM', 'Procurement Team']:
        return redirect('dashboard')

    if request.method != 'POST':
        return redirect('procurement_compile_document')

    from apps.procurement.models import CompiledDocument
    from django.shortcuts import get_object_or_404

    doc = get_object_or_404(CompiledDocument, id=doc_id)
    doc.status = 'Published'
    doc.save()

    messages.success(request, f'"{doc.document_name}" has been published successfully.')
    if request.user.role and request.user.role.name == 'CBM':
        return redirect('cbm_compiled_documents')
    return redirect('procurement_compile_document')


@login_required
def procurement_compiled_document_detail_view(request, doc_id):
    """
    Detail page for a single CompiledDocument — shows full tracker + doc info.
    Accessible by Procurement Team and CBM.
    """
    if request.user.role and request.user.role.name not in ['Procurement Team', 'CBM']:
        return redirect('dashboard')

    from apps.procurement.models import CompiledDocument
    from django.shortcuts import get_object_or_404
    from apps.dashboard.views import convert_word_to_html, convert_excel_to_html

    doc = get_object_or_404(CompiledDocument, id=doc_id)

    doc_file_type = None
    doc_preview_html = None
    absolute_document_url = None

    if doc.file:
        absolute_document_url = request.build_absolute_uri(doc.file.url)
        filename = doc.file.name.lower()
        if filename.endswith('.pdf'):
            doc_file_type = 'pdf'
        elif filename.endswith('.txt'):
            doc_file_type = 'txt'
        elif filename.endswith(('.doc', '.docx')):
            doc_file_type = 'word'
            try:
                doc_preview_html = convert_word_to_html(doc.file.path)
            except Exception as e:
                doc_preview_html = f'<div class="alert alert-danger">Error loading Word document preview: {str(e)}</div>'
        elif filename.endswith(('.xls', '.xlsx')):
            doc_file_type = 'excel'
            try:
                doc_preview_html = convert_excel_to_html(doc.file.path)
            except Exception as e:
                doc_preview_html = f'<div class="alert alert-danger">Error loading Excel file preview: {str(e)}</div>'
        elif filename.endswith('.zip'):
            doc_file_type = 'zip'

    return render(request, 'procurement/compiled_document_detail.html', {
        'doc': doc,
        'doc_file_type': doc_file_type,
        'doc_preview_html': doc_preview_html,
        'absolute_document_url': absolute_document_url,
    })


@login_required
def cbm_compiled_documents_view(request):
    """
    CBM view: list all compiled documents submitted by Procurement Team.
    """
    if request.user.role and request.user.role.name != 'CBM':
        return redirect('dashboard')

    from apps.procurement.models import CompiledDocument

    compiled_docs = CompiledDocument.objects.select_related('submitted_by').all()
    total_count = compiled_docs.count()
    pending_count = compiled_docs.filter(status='Sent to CBM').count()
    published_count = compiled_docs.filter(status='Published').count()

    return render(request, 'cbm/compiled_documents.html', {
        'compiled_docs': compiled_docs,
        'total_count': total_count,
        'pending_count': pending_count,
        'published_count': published_count,
    })


@login_required
def procurement_reports_view(request):
    """
    Procurement Team and CBM reports and analytics.
    Three sections: Internal Submissions, Tenders, Contracts.
    """
    user = request.user

    if user.role and user.role.name not in ['Procurement Team', 'CBM']:
        return redirect('dashboard')

    from apps.procurement.models import Submission, Tender
    from apps.contracts.models import Contract
    from apps.divisions.models import Division
    from django.db.models import Avg, Min, Max, Count

    # ── Date range filter ──────────────────────────────────────
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    date_from = parse_date(date_from_str) if date_from_str else None
    date_to = parse_date(date_to_str) if date_to_str else None

    def apply_date(qs):
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs

    # ── SECTION 1: Internal Submissions ───────────────────────
    all_submissions = apply_date(Submission.objects.filter(is_deleted=False))

    internal_statuses_before_tender = [
        'Draft', 'HOD/DM Submit', 'Review of Procurement Draft',
        'Submit Compiled Document', 'CBM Review', 'Publish Plan',
        'Returned', 'Rejected',
    ]

    sub_stats = {
        'total': all_submissions.count(),
        'draft': all_submissions.filter(status='Draft').count(),
        'with_procurement': all_submissions.filter(
            status__in=['HOD/DM Submit', 'Review of Procurement Draft', 'Submit Compiled Document']
        ).count(),
        'with_cbm': all_submissions.filter(status__in=['CBM Review']).count(),
        'plan_published': all_submissions.filter(status='Publish Plan').count(),
        'returned': all_submissions.filter(status='Returned').count(),
        'rejected': all_submissions.filter(status='Rejected').count(),
        'in_tender': all_submissions.filter(
            status__in=['Prepare Tender Document', 'CBM Review TD', 'Publication of TD',
                        'Bidding', 'Evaluation', 'CBM Approval', 'Notify Bidders',
                        'Contract Negotiation', 'Contract Drafting', 'Legal Review',
                        'Supplier Approval', 'MINIJUST Legal Review', 'Awarded']
        ).count(),
        'completed': all_submissions.filter(status='Completed').count(),
    }
    total = sub_stats['total'] or 1
    sub_stats['completed_pct'] = int(sub_stats['completed'] / total * 100)
    sub_stats['plan_published_pct'] = int(sub_stats['plan_published'] / total * 100)

    sub_budget_total = all_submissions.aggregate(Sum('total_budget'))['total_budget__sum'] or 0
    sub_budget_plan = all_submissions.exclude(
        status__in=['Draft', 'HOD/DM Submit', 'Returned', 'Rejected']
    ).aggregate(Sum('total_budget'))['total_budget__sum'] or 0
    sub_budget_completed = all_submissions.filter(status='Completed').aggregate(
        Sum('total_budget'))['total_budget__sum'] or 0

    budget_stats = {
        'total': sub_budget_total,
        'in_pipeline': sub_budget_plan,
        'completed': sub_budget_completed,
    }

    submissions_by_division = all_submissions.values('division__name').annotate(
        total=Count('id'),
        published=Count('id', filter=Q(status='Publish Plan')),
        completed=Count('id', filter=Q(status='Completed')),
    ).order_by('-total')

    submissions_by_priority = all_submissions.values('priority').annotate(
        total=Count('id'),
        completed=Count('id', filter=Q(status='Completed')),
    ).order_by('priority')

    recent_submissions = all_submissions.order_by('-created_at')[:8]

    stalled_subs = all_submissions.filter(
        status__in=['HOD/DM Submit', 'Review of Procurement Draft', 'CBM Review'],
        created_at__lt=timezone.now() - timedelta(days=30)
    ).count()

    # ── SECTION 2: Tenders ────────────────────────────────────
    all_tenders = apply_date(Tender.objects.all())

    tender_stats = {
        'total': all_tenders.count(),
        'preparing': all_tenders.filter(status='Prepare Tender Document').count(),
        'cbm_review': all_tenders.filter(status__in=['CBM Review TD', 'CBM Approval']).count(),
        'published': all_tenders.filter(status='Publication of TD').count(),
        'bidding': all_tenders.filter(status='Bidding').count(),
        'evaluation': all_tenders.filter(status='Evaluation').count(),
        'awarded': all_tenders.filter(status='Awarded').count(),
        'completed': all_tenders.filter(status='Completed').count(),
        'cancelled': all_tenders.filter(status='Cancelled').count(),
        'returned': all_tenders.filter(status='Returned').count(),
    }

    tenders_by_method = all_tenders.values('procurement_method').annotate(
        total=Count('tender_number'),
        completed=Count('tender_number', filter=Q(status='Completed')),
        awarded=Count('tender_number', filter=Q(status='Awarded')),
    ).order_by('-total')[:12]

    recent_tenders = all_tenders.select_related('submission__division').order_by('-created_at')[:8]

    avg_tender_days = 0
    completed_tenders = all_tenders.filter(status='Completed')
    if completed_tenders.exists():
        d, c = 0, 0
        for t in completed_tenders:
            days = (t.updated_at - t.created_at).days
            if days >= 0:
                d += days; c += 1
        avg_tender_days = int(d / c) if c else 0

    # ── SECTION 3: Contracts ──────────────────────────────────
    all_contracts = apply_date(Contract.objects.all())

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

    contracts_by_type = all_contracts.values('contract_type').annotate(
        total=Count('id'),
        active=Count('id', filter=Q(status='Active')),
        completed=Count('id', filter=Q(status='Completed')),
    ).order_by('-total')

    contracts_by_division = all_contracts.values('division__name').annotate(
        total=Count('id'),
        active=Count('id', filter=Q(status='Active')),
    ).order_by('-total')[:8]

    contract_budget_total = all_contracts.aggregate(Sum('contract_budget'))['contract_budget__sum'] or 0
    contract_budget_active = all_contracts.filter(status='Active').aggregate(
        Sum('contract_budget'))['contract_budget__sum'] or 0
    contract_budget_completed = all_contracts.filter(status='Completed').aggregate(
        Sum('contract_budget'))['contract_budget__sum'] or 0

    contract_budget_stats = {
        'total': contract_budget_total,
        'active': contract_budget_active,
        'completed': contract_budget_completed,
    }

    recent_contracts = all_contracts.select_related('division').order_by('-created_at')[:8]

    context = {
        # submissions
        'sub_stats': sub_stats,
        'budget_stats': budget_stats,
        'submissions_by_division': submissions_by_division,
        'submissions_by_priority': submissions_by_priority,
        'recent_submissions': recent_submissions,
        'stalled_subs': stalled_subs,
        # tenders
        'tender_stats': tender_stats,
        'tenders_by_method': tenders_by_method,
        'recent_tenders': recent_tenders,
        'avg_tender_days': avg_tender_days,
        # contracts
        'contract_stats': contract_stats,
        'contracts_by_type': contracts_by_type,
        'contracts_by_division': contracts_by_division,
        'contract_budget_stats': contract_budget_stats,
        'recent_contracts': recent_contracts,
        # filter state
        'date_from': date_from_str,
        'date_to': date_to_str,
        'date_filtered': bool(date_from or date_to),
    }
    
    # Use different template based on user role
    template = 'cbm/reports.html' if user.role and user.role.name == 'CBM' else 'procurement/reports.html'
    return render(request, template, context)
