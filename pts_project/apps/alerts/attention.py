"""
Attention items builder.

Called once per login session (via context processor + session flag).
Returns a list of categorised dicts that the full-screen attention modal displays.

Each item::

    {
        'category': str,        # 'contract' | 'po' | 'procurement' | 'submission' | 'alert'
        'severity': str,        # 'critical' | 'warning' | 'info'
        'icon':     str,        # Bootstrap-Icons class name
        'title':    str,
        'detail':   str,
        'url':      str | None,
    }
"""
from django.utils import timezone


# ─── severity ordering helper ────────────────────────────────────────────────
_SEVERITY_ORDER = {'critical': 0, 'warning': 1, 'info': 2}


def get_attention_items(user):
    """
    Return a list of attention items relevant to *user*, sorted critical-first.
    Returns an empty list (no blocking modal) when nothing needs attention.
    """
    if not user.is_authenticated or not user.role:
        return []

    role = user.role.name
    items = []

    items += _contract_items(user, role)
    items += _po_items(user, role)
    items += _procurement_call_items(user, role)
    items += _tender_items(user, role)
    items += _submission_items(user, role)
    items += _alert_items(user, role)

    items.sort(key=lambda x: _SEVERITY_ORDER.get(x['severity'], 9))
    return items


# ─── Contract deadline items ──────────────────────────────────────────────────

def _contract_items(user, role):
    items = []
    try:
        from apps.contracts.models import Contract
        from django.db.models import Q
        today = timezone.now().date()

        qs = Contract.objects.filter(
            status__in=['Active', 'Renewed'],
        ).exclude(delivery_date=None).select_related('division').prefetch_related('project_managers')

        # HOD/DM: only their division
        if role == 'HOD/DM':
            qs = qs.filter(
                Q(division=getattr(user, 'division', None)) |
                Q(project_managers=user)
            ).distinct()

        for c in qs:
            pd = c.lumpsum_progress_data
            if pd is None:
                continue
            url = f'/dashboard/contracts/{c.pk}/'
            if pd['is_overdue']:
                items.append({
                    'category': 'contract',
                    'severity': 'critical',
                    'icon': 'bi-exclamation-triangle-fill',
                    'title': f'Contract Overdue — {c.contract_number}',
                    'detail': (
                        f'{c.contract_name} | Delivery was {c.delivery_date.strftime("%d %b %Y")} '
                        f'({pd["overdue_days"]} day(s) ago)'
                    ),
                    'url': url,
                })
            elif pd['is_quarter_alert']:
                items.append({
                    'category': 'contract',
                    'severity': 'warning',
                    'icon': 'bi-alarm-fill',
                    'title': f'Contract Deadline Approaching — {c.contract_number}',
                    'detail': (
                        f'{c.contract_name} | {pd["remaining"]} day(s) remaining '
                        f'(less than ¼ of contract period)'
                    ),
                    'url': url,
                })

        # Framework contracts nearing expiry
        fw_qs = Contract.objects.filter(
            contract_type='Framework',
            status__in=['Active', 'Renewed'],
        ).select_related('division').prefetch_related('project_managers')
        if role == 'HOD/DM':
            fw_qs = fw_qs.filter(
                Q(division=getattr(user, 'division', None)) |
                Q(project_managers=user)
            ).distinct()
        for c in fw_qs:
            dr = c.framework_days_remaining
            if dr is None:
                continue
            url = f'/dashboard/contracts/{c.pk}/'
            if dr < 0:
                items.append({
                    'category': 'contract',
                    'severity': 'critical',
                    'icon': 'bi-calendar-x-fill',
                    'title': f'Framework Contract Expired — {c.contract_number}',
                    'detail': f'{c.contract_name} | Framework period expired {abs(dr)} day(s) ago.',
                    'url': url,
                })
            elif dr <= 90:
                items.append({
                    'category': 'contract',
                    'severity': 'warning',
                    'icon': 'bi-calendar-event-fill',
                    'title': f'Framework Expiring Soon — {c.contract_number}',
                    'detail': f'{c.contract_name} | {dr} day(s) until framework period ends.',
                    'url': url,
                })
    except Exception:
        pass
    return items


# ─── Purchase Order deadline items ───────────────────────────────────────────

def _po_items(user, role):
    items = []
    try:
        from apps.contracts.models import PurchaseOrder
        from django.db.models import Q

        qs = PurchaseOrder.objects.filter(
            status='Active',
        ).select_related('contract', 'contract__division').prefetch_related('contract__project_managers')

        if role == 'HOD/DM':
            qs = qs.filter(
                Q(contract__division=getattr(user, 'division', None)) |
                Q(contract__project_managers=user)
            ).distinct()

        for po in qs:
            pd = po.progress_data
            url = f'/dashboard/contracts/{po.contract_id}/'
            if pd['is_overdue']:
                items.append({
                    'category': 'po',
                    'severity': 'critical',
                    'icon': 'bi-receipt-cutoff',
                    'title': f'PO Overdue — {po.po_number}',
                    'detail': (
                        f'Under {po.contract.contract_number} | Delivery was '
                        f'{po.delivery_date.strftime("%d %b %Y")} '
                        f'({pd["overdue_days"]} day(s) ago)'
                    ),
                    'url': url,
                })
            elif pd['is_quarter_alert']:
                items.append({
                    'category': 'po',
                    'severity': 'warning',
                    'icon': 'bi-receipt',
                    'title': f'PO Deadline Approaching — {po.po_number}',
                    'detail': (
                        f'Under {po.contract.contract_number} | '
                        f'{pd["remaining"]} day(s) remaining (≤ ¼ of PO period)'
                    ),
                    'url': url,
                })
    except Exception:
        pass
    return items


# ─── Procurement call items ───────────────────────────────────────────────────

def _procurement_call_items(user, role):
    items = []
    try:
        from apps.procurement.models import ProcurementCall, Submission
        from django.utils import timezone as tz

        now = tz.now()

        if role == 'HOD/DM':
            # Active calls where this division has NOT yet submitted
            div = getattr(user, 'division', None)
            if div:
                active_calls = ProcurementCall.objects.filter(
                    status__in=['Active', 'Extended'],
                ).filter(end_date__gte=now)
                submitted_call_ids = set(
                    Submission.objects.filter(
                        division=div,
                        call__in=active_calls,
                    ).exclude(
                        status__in=['Draft']
                    ).values_list('call_id', flat=True)
                )
                for call in active_calls:
                    if call.pk not in submitted_call_ids:
                        effective_end = call.extended_date or call.end_date
                        days_left = (effective_end - now).days
                        sev = 'critical' if days_left <= 3 else 'warning' if days_left <= 7 else 'info'
                        items.append({
                            'category': 'procurement',
                            'severity': sev,
                            'icon': 'bi-megaphone-fill',
                            'title': f'Procurement Call Awaiting Submission — {call.reference_number}',
                            'detail': (
                                f'{call.title} | Deadline: '
                                f'{effective_end.strftime("%d %b %Y %H:%M")} '
                                f'({max(0, days_left)} day(s) remaining)'
                            ),
                            'url': f'/procurement/calls/{call.pk}/',
                        })

        elif role in ('Procurement Team', 'CBM', 'Admin'):
            # Calls expiring within 5 days with very few / no submissions
            expiring = ProcurementCall.objects.filter(
                status__in=['Active', 'Extended'],
                end_date__gte=now,
                end_date__lte=now + timezone.timedelta(days=5),
            )
            for call in expiring:
                items.append({
                    'category': 'procurement',
                    'severity': 'warning',
                    'icon': 'bi-megaphone',
                    'title': f'Procurement Call Closing Soon — {call.reference_number}',
                    'detail': (
                        f'{call.title} | Closes '
                        f'{(call.extended_date or call.end_date).strftime("%d %b %Y")} '
                        f'| {call.submission_count} submission(s) so far'
                    ),
                    'url': f'/procurement/calls/{call.pk}/',
                })
    except Exception:
        pass
    return items


# ─── Submission / workflow items ──────────────────────────────────────────────

def _submission_items(user, role):
    items = []
    try:
        from apps.procurement.models import Submission
        from django.utils import timezone as tz

        now = tz.now()
        STALE_DAYS = 7  # how many days before a submission is considered "stuck"

        if role == 'CBM':
            # Submissions waiting for CBM action
            waiting = Submission.objects.filter(
                status__in=['CBM Review', 'CBM Approval'],
            ).select_related('call', 'division').order_by('updated_at')
            for s in waiting:
                days_waiting = (now - s.updated_at).days
                sev = 'critical' if days_waiting >= STALE_DAYS * 2 else 'warning'
                items.append({
                    'category': 'submission',
                    'severity': sev,
                    'icon': 'bi-clipboard2-check-fill',
                    'title': f'Awaiting CBM Action — {s.tracking_reference}',
                    'detail': (
                        f'{s.item_name} ({s.division.name}) | '
                        f'Status: {s.status} | Waiting {days_waiting} day(s)'
                    ),
                    'url': f'/procurement/submissions/{s.pk}/',
                })

        elif role == 'HOD/DM':
            div = getattr(user, 'division', None)
            if div:
                # Returned items needing HOD/DM action
                returned = Submission.objects.filter(
                    division=div,
                    status='Returned',
                ).select_related('call')
                for s in returned:
                    days_waiting = (now - s.updated_at).days
                    items.append({
                        'category': 'submission',
                        'severity': 'warning',
                        'icon': 'bi-arrow-return-left',
                        'title': f'Submission Returned — {s.tracking_reference}',
                        'detail': (
                            f'{s.item_name} | Returned for clarification '
                            f'{days_waiting} day(s) ago'
                        ),
                        'url': f'/procurement/submissions/{s.pk}/',
                    })

        elif role in ('Procurement Team', 'Admin'):
            # ── Stages where Procurement Team IS the active actor ──────────
            # Map each status to a plain-language action label + icon
            PROC_ACTION_STAGES = {
                'HOD/DM Submit':              ('Review Division Submission',    'bi-inbox-fill'),
                'Review of Procurement Draft':('Complete Procurement Draft Review','bi-pencil-square'),
                'Submit Compiled Document':   ('Process Compiled Document',     'bi-file-earmark-arrow-up-fill'),
                'Prepare Tender Document':    ('Prepare Tender Document',        'bi-file-earmark-text-fill'),
                'Evaluation':                 ('Complete Bid Evaluation',        'bi-bar-chart-steps'),
                'Notify Bidders':             ('Notify Bidders of Outcome',      'bi-send-fill'),
                'Contract Negotiation':       ('Complete Contract Negotiation',  'bi-handshake-fill'),
                'Contract Drafting':          ('Draft the Contract',             'bi-journal-text'),
            }
            action_qs = Submission.objects.filter(
                status__in=list(PROC_ACTION_STAGES.keys()),
            ).select_related('call', 'division').order_by('updated_at')[:30]

            for s in action_qs:
                days_elapsed = (now - s.updated_at).days
                action_label, icon = PROC_ACTION_STAGES[s.status]
                sev = 'critical' if days_elapsed >= STALE_DAYS * 2 else (
                      'warning'  if days_elapsed >= STALE_DAYS else 'info')
                items.append({
                    'category': 'submission',
                    'severity': sev,
                    'icon':     icon,
                    'title':    f'{action_label} — {s.tracking_reference}',
                    'detail':   (
                        f'{s.item_name}'
                        + (f' ({s.division.name})' if s.division_id else '')
                        + f' | Stage: {s.status}'
                        + f' | {days_elapsed} day(s) at this stage'
                    ),
                    'url':      f'/procurement/submissions/{s.pk}/',
                })

            # ── Submissions externally blocked and going stale ──────────────
            stale_qs = Submission.objects.filter(
                status__in=[
                    'CBM Review', 'CBM Review TD', 'CBM Approval',
                    'Legal Review', 'MINIJUST Legal Review',
                    'Supplier Approval',
                ],
                updated_at__lt=now - timezone.timedelta(days=STALE_DAYS),
            ).select_related('call', 'division').order_by('updated_at')[:20]

            for s in stale_qs:
                days_stuck = (now - s.updated_at).days
                items.append({
                    'category': 'submission',
                    'severity': 'warning' if days_stuck < STALE_DAYS * 3 else 'critical',
                    'icon': 'bi-hourglass-split',
                    'title': f'Submission Stalled Externally — {s.tracking_reference}',
                    'detail': (
                        f'{s.item_name} ({s.division.name if s.division else "—"}) | '
                        f'Stage: {s.status} | {days_stuck} day(s) without progress'
                    ),
                    'url': f'/procurement/submissions/{s.pk}/',
                })

            # Overdue CBM review deadlines
            overdue_cbm = Submission.objects.filter(
                status__in=['CBM Review', 'CBM Approval'],
                cbm_review_deadline__lt=now.date(),
                cbm_review_deadline__isnull=False,
            ).select_related('division')[:10]
            for s in overdue_cbm:
                overdue_by = (now.date() - s.cbm_review_deadline).days
                items.append({
                    'category': 'submission',
                    'severity': 'critical',
                    'icon': 'bi-calendar-x-fill',
                    'title': f'CBM Review Deadline Missed — {s.tracking_reference}',
                    'detail': (
                        f'{s.item_name} | CBM deadline was '
                        f'{s.cbm_review_deadline.strftime("%d %b %Y")} '
                        f'({overdue_by} day(s) ago)'
                    ),
                    'url': f'/procurement/submissions/{s.pk}/',
                })
    except Exception:
        pass
    return items


# ─── Tender items ────────────────────────────────────────────────────────────

def _tender_items(user, role):
    items = []
    try:
        from apps.procurement.models import Tender
        from apps.contracts.models import Contract

        if role == 'CBM':
            # Tenders sitting in CBM's court
            tenders = Tender.objects.filter(
                status__in=['CBM Review TD', 'CBM Approval'],
            ).select_related('submission', 'submission__division').order_by('updated_at')
            for t in tenders:
                days_waiting = (timezone.now() - t.updated_at).days
                action = 'Review Tender Document' if t.status == 'CBM Review TD' else 'Approve Award'
                sev = 'critical' if days_waiting >= 7 else 'warning'
                items.append({
                    'category': 'tender',
                    'severity': sev,
                    'icon': 'bi-file-earmark-ruled-fill',
                    'title': f'Tender Awaiting CBM {action} — {t.tender_number}',
                    'detail': (
                        f'{t.tender_title}'
                        + (f' | Division: {t.submission.division.name}' if t.submission and t.submission.division_id else '')
                        + f' | Method: {t.procurement_method}'
                        + f' | Waiting {days_waiting} day(s)'
                    ),
                    'url': f'/dashboard/tenders/{t.tender_number}/',
                })

        elif role in ('Procurement Team', 'Admin'):
            # Tenders blocked at CBM — Procurement Team needs to follow up
            pending_cbm = Tender.objects.filter(
                status__in=['CBM Review TD', 'CBM Approval'],
            ).select_related('submission', 'submission__division').order_by('updated_at')[:20]
            for t in pending_cbm:
                days_waiting = (timezone.now() - t.updated_at).days
                sev = 'critical' if days_waiting >= 7 else 'warning'
                items.append({
                    'category': 'tender',
                    'severity': sev,
                    'icon': 'bi-hourglass-top',
                    'title': f'Tender Pending CBM Action — {t.tender_number}',
                    'detail': (
                        f'{t.tender_title} | Stage: {t.status}'
                        + (f' | {t.submission.division.name}' if t.submission and t.submission.division_id else '')
                        + f' | Waiting {days_waiting} day(s)'
                    ),
                    'url': f'/dashboard/tenders/{t.tender_number}/',
                })

            # Awarded tenders with no contract created yet
            contracted_numbers = set(
                Contract.objects.exclude(tender_id=None)
                .values_list('tender_id', flat=True)
            )
            no_contract = Tender.objects.filter(
                status='Awarded',
            ).exclude(
                tender_number__in=contracted_numbers,
            ).select_related('submission', 'submission__division')[:20]
            for t in no_contract:
                items.append({
                    'category': 'tender',
                    'severity': 'critical',
                    'icon': 'bi-file-earmark-plus-fill',
                    'title': f'Contract Must Be Created — {t.tender_number}',
                    'detail': (
                        f'{t.tender_title} has been Awarded but no contract exists yet.'
                        + (f' Division: {t.submission.division.name}' if t.submission and t.submission.division_id else '')
                    ),
                    'url': f'/dashboard/contracts/new/',
                })
    except Exception:
        pass
    return items


# ─── Alert model items ────────────────────────────────────────────────────────

def _alert_items(user, role):
    items = []
    try:
        from apps.alerts.models import Alert
        from django.db.models import Q

        if role == 'Procurement Team':
            qs = Alert.objects.filter(
                status='active', severity__in=['critical', 'warning']
            ).select_related('submission', 'submission__division').order_by('-created_at')[:15]
        elif role == 'HOD/DM':
            div = getattr(user, 'division', None)
            qs = Alert.objects.filter(
                Q(submission__division=div),
                status='active',
            ).select_related('submission').order_by('-created_at')[:10]
        elif role == 'CBM':
            qs = Alert.objects.filter(
                status='active',
                severity='critical',
            ).select_related('submission', 'submission__division').order_by('-created_at')[:10]
        elif role == 'Admin':
            qs = Alert.objects.filter(
                status='active',
            ).select_related('submission', 'submission__division').order_by('-created_at')[:20]
        else:
            qs = Alert.objects.filter(
                submission__submitted_by=user,
                status='active',
            ).select_related('submission').order_by('-created_at')[:10]

        sev_map = {'critical': 'critical', 'warning': 'warning', 'info': 'info'}
        icon_map = {'critical': 'bi-exclamation-octagon-fill', 'warning': 'bi-exclamation-triangle-fill', 'info': 'bi-info-circle-fill'}
        for a in qs:
            items.append({
                'category': 'alert',
                'severity': sev_map.get(a.severity, 'info'),
                'icon': icon_map.get(a.severity, 'bi-bell-fill'),
                'title': a.title,
                'detail': (
                    f'{a.submission.tracking_reference}'
                    + (f' ({a.submission.division.name})' if a.submission.division_id else '')
                    + f' — {a.description[:120]}'
                ),
                'url': f'/procurement/submissions/{a.submission_id}/',
            })
    except Exception:
        pass
    return items
