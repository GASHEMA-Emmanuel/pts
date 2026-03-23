"""
Tender management views — for CBM and Procurement Team.

After a submission's plan is published, individual tenders are created and
tracked here independently. Each tender has its own 14-stage workflow
(Prepare Tender Document → Completed, stages 7-20).
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone


# Ordered list of tender stages (matches WorkflowStage orders 7-20)
TENDER_STAGES = [
    {'name': 'Prepare Tender Document', 'order': 7,  'actor': 'Procurement Team'},
    {'name': 'CBM Review TD',           'order': 8,  'actor': 'CBM'},
    {'name': 'Publication of TD',       'order': 9,  'actor': 'Procurement Team'},
    {'name': 'Opening',                 'order': 10, 'actor': 'Procurement Team'},
    {'name': 'Evaluation',              'order': 11, 'actor': 'Procurement Team'},
    {'name': 'CBM Approval',            'order': 12, 'actor': 'CBM'},
    {'name': 'Notify Bidders',          'order': 13, 'actor': 'Procurement Team'},
    {'name': 'Contract Negotiation',    'order': 14, 'actor': 'Procurement Team'},
    {'name': 'Contract Drafting',       'order': 15, 'actor': 'Procurement Team'},
    {'name': 'Legal Review',            'order': 16, 'actor': 'Procurement Team'},
    {'name': 'Supplier Approval',       'order': 17, 'actor': 'Procurement Team'},
    {'name': 'MINIJUST Legal Review',   'order': 18, 'actor': 'Procurement Team'},
    {'name': 'Awarded',                 'order': 19, 'actor': 'Procurement Team'},
    {'name': 'Completed',               'order': 20, 'actor': 'Procurement Team'},
]

# Which status each role can advance FROM
# Note: CBM stages now auto-advance, so Procurement Team goes directly through them
PROCUREMENT_CAN_ADVANCE = {
    'Prepare Tender Document': 'Publication of TD',        # Auto-advances through CBM Review TD
    'Publication of TD':       'Opening',
    'Opening':                 'Evaluation',
    'Evaluation':              'Notify Bidders',           # Auto-advances through CBM Approval
    'Notify Bidders':          'Contract Negotiation',
    'Contract Negotiation':    'Contract Drafting',
    'Contract Drafting':       'Legal Review',
    'Legal Review':            'Supplier Approval',
    'Supplier Approval':       'MINIJUST Legal Review',
    'MINIJUST Legal Review':   'Awarded',
    'Awarded':                 'Completed',
}

# CBM no longer manually approves - these stages are auto-completed with notification
CBM_CAN_APPROVE = {
    # 'CBM Review TD':  'Publication of TD',     # Now auto-advances
    # 'CBM Approval':   'Notify Bidders',        # Now auto-advances
}

CBM_RETURN_MAP = {
    'CBM Review TD': 'Prepare Tender Document',
    'CBM Approval':  'Evaluation',
}

STAGE_ORDER_MAP = {s['name']: s['order'] for s in TENDER_STAGES}


def _build_stages_context(tender):
    """Return stage list with state flags for the progress tracker."""
    current_idx = next(
        (i for i, s in enumerate(TENDER_STAGES) if s['name'] == tender.status),
        0
    )
    stages = []
    for i, s in enumerate(TENDER_STAGES):
        stages.append({
            **s,
            'is_completed': i < current_idx,
            'is_current':   i == current_idx,
            'is_future':    i > current_idx,
            'step':         i + 1,
        })
    total = len(TENDER_STAGES) - 1  # exclude 'Completed' from denominator
    progress_pct = int((current_idx / total) * 100) if current_idx > 0 else 0
    return stages, current_idx, progress_pct


def _get_stage_obj(status):
    from apps.workflows.models import WorkflowStage
    order = STAGE_ORDER_MAP.get(status)
    return WorkflowStage.objects.filter(order=order).first() if order else None


def _notify_users(role_names, title, message, tender, action_url=None, priority='high'):
    from apps.accounts.models import User
    from apps.notifications.models import Notification
    url = action_url or f'/dashboard/tenders/{tender.tender_number}/'
    for user in User.objects.filter(role__name__in=role_names, is_active=True):
        Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type='submission_status',
            priority=priority,
            related_object_type='Tender',
            related_object_id=str(tender.tender_number),
            action_url=url,
        )


# ─────────────────────────────────────────────────────────────────
# Tender list for a submission
# ─────────────────────────────────────────────────────────────────

@login_required
def submission_tender_list_view(request, submission_id):
    """
    Lists all tenders created under a published-plan submission.
    Accessible by CBM and Procurement Team.
    """
    user = request.user
    if not user.role or user.role.name not in ('CBM', 'Procurement Team', 'Admin'):
        return redirect('dashboard')

    from apps.procurement.models import Submission, Tender
    submission = get_object_or_404(Submission, id=submission_id)
    tenders = Tender.objects.filter(submission=submission).order_by('-created_at')

    # Stats
    stats = {
        'total':     tenders.count(),
        'active':    tenders.exclude(status__in=['Completed', 'Cancelled']).count(),
        'completed': tenders.filter(status='Completed').count(),
        'with_cbm':  tenders.filter(status__in=list(CBM_CAN_APPROVE.keys())).count(),
    }

    import json
    all_tender_numbers = list(Tender.objects.values_list('tender_number', flat=True))

    context = {
        'submission': submission,
        'tenders': tenders,
        'stats': stats,
        'can_create': user.role.name in ('Procurement Team', 'Admin')
                      and submission.status in ('Publish Plan', 'Plan Published'),
        'procurement_methods': [m[0] for m in Tender.PROCUREMENT_METHOD_CHOICES],
        'all_tender_numbers_json': json.dumps(all_tender_numbers),
    }
    return render(request, 'procurement/tender_list.html', context)


# ─────────────────────────────────────────────────────────────────
# Create tender (POST from tender_list page)
# ─────────────────────────────────────────────────────────────────

@login_required
def tender_create_view(request, submission_id):
    """
    Procurement Team creates a new tender for a published-plan submission.
    """
    user = request.user
    if not user.role or user.role.name not in ('Procurement Team', 'Admin'):
        messages.error(request, 'Only Procurement Team can create tenders.')
        return redirect('submission_tender_list', submission_id=submission_id)

    from apps.procurement.models import Submission, Tender, TenderHistory
    submission = get_object_or_404(Submission, id=submission_id)

    if submission.status not in ('Publish Plan', 'Plan Published'):
        messages.error(request, 'Tenders can only be created for published plans.')
        return redirect('submission_tender_list', submission_id=submission_id)

    if request.method != 'POST':
        return redirect('submission_tender_list', submission_id=submission_id)

    tender_number      = request.POST.get('tender_number', '').strip()
    tender_title       = request.POST.get('tender_title', '').strip()
    procurement_method = request.POST.get('procurement_method', '').strip()
    umucyo_link        = request.POST.get('umucyo_link', '').strip()
    notes              = request.POST.get('notes', '').strip()

    if not tender_number or not tender_title or not procurement_method:
        messages.error(request, 'Tender number, title and procurement method are required.')
        return redirect('submission_tender_list', submission_id=submission_id)

    if Tender.objects.filter(tender_number=tender_number).exists():
        messages.error(request, f'Tender {tender_number} already exists.')
        return redirect('submission_tender_list', submission_id=submission_id)

    initial_stage = _get_stage_obj('Prepare Tender Document')

    tender = Tender.objects.create(
        tender_number=tender_number,
        tender_title=tender_title,
        submission=submission,
        procurement_method=procurement_method,
        umucyo_link=umucyo_link or None,
        status='Prepare Tender Document',
        current_stage=initial_stage,
        created_by=user,
    )

    TenderHistory.objects.create(
        tender=tender,
        from_status='',
        to_status='Prepare Tender Document',
        action='create',
        comments=notes or f'Tender created from {submission.tracking_reference}',
        action_by=user,
    )

    # Mark submission as Plan Published if still at Publish Plan
    if submission.status == 'Publish Plan':
        submission.status = 'Plan Published'
        submission.save()

    messages.success(request, f'Tender {tender_number} created successfully.')
    return redirect('tender_detail', tender_number=tender_number)


# ─────────────────────────────────────────────────────────────────
# Individual tender detail page
# ─────────────────────────────────────────────────────────────────

@login_required
def tender_detail_view(request, tender_number):
    """
    Detail page for an individual tender.
    Shows stage progress, recent history, and role-specific action buttons.
    Accessible by CBM and Procurement Team.
    """
    user = request.user
    if not user.role or user.role.name not in ('CBM', 'Procurement Team', 'Admin'):
        return redirect('dashboard')

    from apps.procurement.models import Tender, TenderHistory
    tender = get_object_or_404(Tender, tender_number=tender_number)
    stages, current_idx, progress_pct = _build_stages_context(tender)
    history = TenderHistory.objects.filter(tender=tender).order_by('-created_at')[:20]

    # Build a lookup: to_status -> best date (approval_date preferred, else created_at)
    _hist_by_status = {}
    for h in TenderHistory.objects.filter(tender=tender).order_by('created_at'):
        if h.to_status and h.to_status not in _hist_by_status:
            _hist_by_status[h.to_status] = h.approval_date or h.created_at.date()
    # Attach date_label to each stage
    for stage in stages:
        stage['date_label'] = _hist_by_status.get(stage['name'])

    is_procurement = user.role.name in ('Procurement Team', 'Admin')
    is_cbm         = user.role.name in ('CBM', 'Admin')

    can_advance = is_procurement and tender.status in PROCUREMENT_CAN_ADVANCE
    can_cbm_act = is_cbm and tender.status in CBM_CAN_APPROVE
    next_status = PROCUREMENT_CAN_ADVANCE.get(tender.status) if can_advance else None
    cbm_next    = CBM_CAN_APPROVE.get(tender.status) if can_cbm_act else None

    procurement_methods = [m[0] for m in tender.PROCUREMENT_METHOD_CHOICES]

    # Build timeline info + live countdown for the procurement method
    from apps.procurement.timeline_utils import (
        PUBLICATION_TIMELINES, EVALUATION_TIMELINE,
        NOTIFICATION_TIMELINE, BID_VALIDITY_BASE, BID_VALIDITY_EXTENSION,
        CONTRACT_SIGNATURE_TIMELINES,
    )
    from django.utils import timezone as _tz
    pub_days = PUBLICATION_TIMELINES.get(tender.procurement_method)
    is_international = tender.procurement_method and 'International' in tender.procurement_method
    contract_sig_days = CONTRACT_SIGNATURE_TIMELINES.get(
        'International' if is_international else 'National', {}
    ).get('total_days')

    # Map status names to their allowed calendar days
    _TIMED = {
        'Publication of TD': pub_days,
        'Opening':           pub_days,
        'Evaluation':        EVALUATION_TIMELINE,
        'Notify Bidders':    NOTIFICATION_TIMELINE,
    }
    # Compute countdown for the current stage if it has a fixed duration
    countdown = None
    _allowed = _TIMED.get(tender.status)
    if _allowed:
        _entry = TenderHistory.objects.filter(
            tender=tender, to_status=tender.status
        ).order_by('-created_at').first()
        # Prefer the user-entered Umucyo approval_date (a past date) over the
        # system created_at timestamp, so the countdown counts from the real start.
        if _entry and _entry.approval_date:
            from datetime import datetime, time as _time
            _stage_start = _tz.make_aware(
                datetime.combine(_entry.approval_date, _time.min)
            )
        elif _entry:
            _stage_start = _entry.created_at
        else:
            _stage_start = tender.created_at
        _now = _tz.now()
        _elapsed = max(0, (_now - _stage_start).days)
        _remaining = max(0, _allowed - _elapsed)
        countdown = {
            'allowed_days':     _allowed,
            'elapsed':          _elapsed,
            'remaining':        _remaining,
            'overdue_days':     max(0, _elapsed - _allowed),
            'pct':              min(100, int(_elapsed / _allowed * 100)),
            'is_overdue':       _elapsed > _allowed,
            'is_warning':       (not _elapsed > _allowed) and _remaining <= 5,
            'stage_entry_date': _stage_start,
        }

    _ACTIVE = {
        'Publication of TD / Opening Period': ['Publication of TD', 'Opening'],
        'Evaluation':                         ['Evaluation'],
        'Notify Bidders':                     ['Notify Bidders'],
        'Bid Validity':                       [],
        'Contract Signature':                 [],
    }
    timeline_info = [
        {'stage': 'Publication of TD / Opening Period',
         'days': f'{pub_days} calendar days' if pub_days else 'Not fixed for this method',
         'note': tender.procurement_method or '',
         'is_active': tender.status in _ACTIVE['Publication of TD / Opening Period']},
        {'stage': 'Evaluation',
         'days': f'{EVALUATION_TIMELINE} calendar days (max)',
         'note': 'All methods',
         'is_active': tender.status in _ACTIVE['Evaluation']},
        {'stage': 'Notify Bidders',
         'days': f'{NOTIFICATION_TIMELINE} calendar days',
         'note': 'All methods',
         'is_active': tender.status in _ACTIVE['Notify Bidders']},
        {'stage': 'Bid Validity',
         'days': f'{BID_VALIDITY_BASE} calendar days',
         'note': f'Extendable once by +{BID_VALIDITY_EXTENSION} days',
         'is_active': False},
        {'stage': 'Contract Signature',
         'days': f'{contract_sig_days} calendar days' if contract_sig_days else 'Not fixed',
         'note': 'International' if is_international else 'National',
         'is_active': False},
    ]

    # Compute date constraints for the approval date inputs
    # prev_approval_date → minimum allowed date for the next stage action
    from apps.procurement.models import TenderHistory as _TH
    prev_approval_date = (
        _TH.objects.filter(tender=tender, approval_date__isnull=False)
        .order_by('-approval_date')
        .values_list('approval_date', flat=True)
        .first()
    )
    today_date = _tz.now().date()

    context = {
        'tender':        tender,
        'stages':        stages,
        'current_idx':   current_idx,
        'progress_pct':  progress_pct,
        'history':       history,
        'is_procurement': is_procurement,
        'is_cbm':         is_cbm,
        'can_advance':    can_advance,
        'can_cbm_act':    can_cbm_act,
        'next_status':    next_status,
        'cbm_next':       cbm_next,
        'cbm_return':     CBM_RETURN_MAP.get(tender.status),
        'procurement_methods': procurement_methods,
        'timeline_info': timeline_info,
        'countdown':     countdown,
        'prev_approval_date': prev_approval_date,
        'today_date':         today_date,
    }
    return render(request, 'procurement/tender_detail.html', context)


# ─────────────────────────────────────────────────────────────────
# Advance tender (Procurement Team)
# ─────────────────────────────────────────────────────────────────

@login_required
def tender_advance_view(request, tender_number):
    """
    Procurement Team advances a tender to the next stage.
    Auto-advances through CBM Review stages with notification to CBM.
    """
    user = request.user
    if not user.role or user.role.name not in ('Procurement Team', 'Admin'):
        messages.error(request, 'Only Procurement Team can advance tenders.')
        return redirect('tender_detail', tender_number=tender_number)

    if request.method != 'POST':
        return redirect('tender_detail', tender_number=tender_number)

    from apps.procurement.models import Tender, TenderHistory
    tender = get_object_or_404(Tender, tender_number=tender_number)

    if tender.status not in PROCUREMENT_CAN_ADVANCE:
        messages.error(request, f'Cannot advance from {tender.status}.')
        return redirect('tender_detail', tender_number=tender_number)

    notes           = request.POST.get('notes', '').strip()
    approval_date   = _parse_date(request.POST.get('approval_date', ''))
    from_status     = tender.status
    to_status       = PROCUREMENT_CAN_ADVANCE[from_status]
    
    # Validate approval_date
    from django.utils import timezone
    from datetime import date
    
    if approval_date:
        # Check if date is in the future
        today = timezone.now().date()
        if approval_date > today:
            messages.error(request, f'Approval date cannot be in the future. Please enter a date on or before {today}.')
            return redirect('tender_detail', tender_number=tender_number)
        
        # Check chronological order: approval_date must be >= previous stage dates
        previous_history = TenderHistory.objects.filter(
            tender=tender,
            approval_date__isnull=False
        ).order_by('-approval_date').first()
        
        if previous_history and previous_history.approval_date:
            if approval_date < previous_history.approval_date:
                messages.error(
                    request,
                    f'Approval date ({approval_date}) cannot be earlier than the previous stage date ({previous_history.approval_date}). '
                    f'Dates must follow chronological order.'
                )
                return redirect('tender_detail', tender_number=tender_number)
    
    # Determine if we're auto-advancing through a CBM stage
    cbm_intermediate_stage = None
    cbm_stage_name = None
    
    if from_status == 'Prepare Tender Document':
        # Auto-advance through CBM Review TD
        cbm_intermediate_stage = _get_stage_obj('CBM Review TD')
        cbm_stage_name = 'CBM Review TD'
    elif from_status == 'Evaluation':
        # Auto-advance through CBM Approval
        cbm_intermediate_stage = _get_stage_obj('CBM Approval')
        cbm_stage_name = 'CBM Approval'
    
    # Update tender to final status
    next_stage = _get_stage_obj(to_status)
    tender.status = to_status
    if next_stage:
        tender.current_stage = next_stage
    if approval_date:
        tender.approval_date = approval_date
    tender.save()
    
    # Create history records
    if cbm_intermediate_stage and cbm_stage_name:
        # Record the CBM stage (auto-completed)
        TenderHistory.objects.create(
            tender=tender,
            from_status=from_status,
            to_status=cbm_stage_name,
            action='advance',
            comments=notes or f'{cbm_stage_name} (auto-completed)',
            action_by=user,
            approval_date=approval_date,
        )
        
        # Record the auto-advance to final stage
        TenderHistory.objects.create(
            tender=tender,
            from_status=cbm_stage_name,
            to_status=to_status,
            action='auto_advance',
            comments=f'Auto-advanced to {to_status} after CBM notification',
            action_by=user,
        )
        
        # Notify CBM (informational only - no action required)
        if cbm_stage_name == 'CBM Review TD':
            _notify_users(
                ['CBM'],
                f'📄 Tender Document Prepared: {tender.tender_number}',
                f'Tender Document for "{tender.tender_title}" has been prepared. The workflow has automatically advanced to Publication of TD.',
                tender,
                priority='medium'
            )
        elif cbm_stage_name == 'CBM Approval':
            _notify_users(
                ['CBM'],
                f'✅ Tender Evaluation Complete: {tender.tender_number}',
                f'Evaluation for "{tender.tender_title}" is complete. The workflow has automatically advanced to Notify Bidders.',
                tender,
                priority='medium'
            )
        
        messages.success(request, f'Tender advanced to {to_status}. CBM has been notified.')
    else:
        # No CBM stage - standard advancement
        TenderHistory.objects.create(
            tender=tender,
            from_status=from_status,
            to_status=to_status,
            action='advance',
            comments=notes or f'Advanced to {to_status}',
            action_by=user,
            approval_date=approval_date,
        )
        
        messages.success(request, f'Tender advanced to {to_status}.')
    
    return redirect('tender_detail', tender_number=tender_number)


# ─────────────────────────────────────────────────────────────────
# CBM action on tender (approve or return)
# ─────────────────────────────────────────────────────────────────

@login_required
def tender_cbm_action_view(request, tender_number):
    """
    CBM action on tenders - No longer used as tenders auto-advance through CBM stages.
    This view is maintained for backward compatibility but shows an info message.
    """
    user = request.user
    if not user.role or user.role.name not in ('CBM', 'Admin'):
        messages.error(request, 'Only CBM can perform this action.')
        return redirect('tender_detail', tender_number=tender_number)

    # CBM stages now auto-advance with notification
    messages.info(request, 'Tender workflow now auto-advances through CBM review stages. You will receive notifications for information only.')
    return redirect('tender_detail', tender_number=tender_number)

    TenderHistory.objects.create(
        tender=tender,
        from_status=from_status,
        to_status=to_status,
        action=action_label,
        comments=notes or f'CBM {action_label}d — moved to {to_status}',
        action_by=user,
        approval_date=approval_date,
    )

    # Notify Procurement Team
    verb = 'approved' if action_label == 'approve' else 'returned'
    _notify_users(
        ['Procurement Team'],
        f'Tender {verb.capitalize()}: {tender.tender_number}',
        f'CBM has {verb} tender "{tender.tender_title}". Current status: {to_status}.',
        tender,
    )

    messages.success(request, f'Tender {verb}. Now at: {to_status}.')
    return redirect('tender_detail', tender_number=tender_number)


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _parse_date(date_str):
    if date_str:
        try:
            from datetime import datetime
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    return None


# ─────────────────────────────────────────────────────────────────
# Global Tenders List (menu entry point for CBM + Procurement Team)
# ─────────────────────────────────────────────────────────────────

@login_required
def tenders_list_view(request):
    """
    Global tenders page accessible from the sidebar menu.
    Procurement Team sees all tenders they manage plus a Create button.
    CBM sees all tenders awaiting or past their review.
    """
    user = request.user
    if not user.role or user.role.name not in ('CBM', 'Procurement Team', 'Admin'):
        return redirect('dashboard')

    from apps.procurement.models import Tender, Submission

    is_procurement = user.role.name in ('Procurement Team', 'Admin')
    is_cbm = user.role.name in ('CBM', 'Admin')

    # Filter & search
    status_filter = request.GET.get('status', '')
    search = request.GET.get('q', '').strip()

    tenders = Tender.objects.select_related('submission', 'submission__division', 'created_by').order_by('-created_at')

    if status_filter:
        tenders = tenders.filter(status=status_filter)
    if search:
        tenders = tenders.filter(
            tender_number__icontains=search
        ) | tenders.filter(
            tender_title__icontains=search
        )

    # Stats
    all_tenders = Tender.objects.all()
    stats = {
        'total':     all_tenders.count(),
        'active':    all_tenders.exclude(status__in=['Completed', 'Cancelled']).count(),
        'with_cbm':  all_tenders.filter(status__in=list(CBM_CAN_APPROVE.keys())).count(),
        'completed': all_tenders.filter(status='Completed').count(),
        'awarded':   all_tenders.filter(status='Awarded').count(),
    }

    import json
    all_tender_numbers = list(Tender.objects.values_list('tender_number', flat=True))

    context = {
        'tenders': tenders,
        'stats': stats,
        'status_filter': status_filter,
        'search': search,
        'is_procurement': is_procurement,
        'is_cbm': is_cbm,
        'procurement_methods': [m[0] for m in Tender.PROCUREMENT_METHOD_CHOICES],
        'tender_statuses': [s['name'] for s in TENDER_STAGES],
        'all_tender_numbers_json': json.dumps(all_tender_numbers),
    }
    return render(request, 'procurement/tenders_list.html', context)


# ─────────────────────────────────────────────────────────────────
# Standalone tender create (no submission required)
# ─────────────────────────────────────────────────────────────────

@login_required
def tender_create_standalone_view(request):
    """
    Procurement Team creates a new tender directly from the global Tenders page.
    No submission link required — tenders are independent procurement items.
    """
    user = request.user
    if not user.role or user.role.name != 'Procurement Team':
        messages.error(request, 'Only Procurement Team can create tenders.')
        return redirect('tenders_list')

    if request.method != 'POST':
        return redirect('tenders_list')

    from apps.procurement.models import Tender, TenderHistory

    tender_number      = request.POST.get('tender_number', '').strip()
    tender_title       = request.POST.get('tender_title', '').strip()
    procurement_method = request.POST.get('procurement_method', '').strip()
    notes              = request.POST.get('notes', '').strip()

    if not tender_number or not tender_title or not procurement_method:
        messages.error(request, 'Tender number, title and procurement method are required.')
        return redirect('tenders_list')

    if Tender.objects.filter(tender_number=tender_number).exists():
        messages.error(request, f'Tender {tender_number} already exists.')
        return redirect('tenders_list')

    initial_stage = _get_stage_obj('Prepare Tender Document')

    tender = Tender.objects.create(
        tender_number=tender_number,
        tender_title=tender_title,
        submission=None,
        procurement_method=procurement_method,
        status='Prepare Tender Document',
        current_stage=initial_stage,
        created_by=user,
    )

    TenderHistory.objects.create(
        tender=tender,
        from_status='',
        to_status='Prepare Tender Document',
        action='create',
        comments=notes or 'Tender created.',
        action_by=user,
    )

    messages.success(request, f'Tender {tender_number} created successfully.')
    return redirect('tender_detail', tender_number=tender_number)
