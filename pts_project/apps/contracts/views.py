"""
Contract Management views.

Procurement Team:  create, set milestones, issue POs/completion certificates.
HOD/DM:           view own division's contracts (project manager role).
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta


def _is_pt(user):
    return user.role and user.role.name in ('Procurement Team', 'Admin')


def _is_hod(user):
    return user.role and user.role.name == 'HOD/DM'


def _can_view(user):
    return user.role and user.role.name in ('Procurement Team', 'HOD/DM', 'CBM', 'Admin')


# ─────────────────────────────────────────────────────────────────
# List + Create
# ─────────────────────────────────────────────────────────────────

@login_required
def contract_check_number_view(request):
    """AJAX: check whether a contract number is already taken."""
    from .models import Contract
    number = request.GET.get('number', '').strip()
    if not number:
        return JsonResponse({'exists': False, 'number': ''})
    exists = Contract.objects.filter(contract_number__iexact=number).exists()
    return JsonResponse({'exists': exists, 'number': number})


@login_required
def contracts_list_view(request):
    if not _can_view(request.user):
        return redirect('dashboard')

    from .models import Contract
    from apps.divisions.models import Division
    from apps.accounts.models import User

    contracts = Contract.objects.select_related('division', 'created_by', 'tender').prefetch_related('project_managers')

    # HOD/DM: only their division's contracts
    if _is_hod(request.user):
        contracts = contracts.filter(division=request.user.division)

    # Filters
    type_filter   = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')
    q             = request.GET.get('q', '')
    if type_filter:
        contracts = contracts.filter(contract_type=type_filter)
    if status_filter:
        contracts = contracts.filter(status=status_filter)
    if q:
        contracts = contracts.filter(
            contract_number__icontains=q,
        ) | contracts.filter(contract_name__icontains=q)

    contracts = contracts.order_by('-created_at')

    stats = {
        'total':      Contract.objects.count(),
        'active':     Contract.objects.filter(status='Active').count(),
        'completed':  Contract.objects.filter(status='Completed').count(),
        'lumpsum':    Contract.objects.filter(contract_type='Goods').count(),
        'framework':  Contract.objects.filter(contract_type='Non-consultancy services').count(),
        'consultancy': Contract.objects.filter(contract_type='Consultancy Service').count(),
        'works':      Contract.objects.filter(contract_type='Works').count(),
    }

    divisions    = Division.objects.filter(is_active=True).order_by('name')
    hod_users    = User.objects.filter(role__name='HOD/DM', is_active=True).select_related('role', 'division')

    # Build a JSON map {division_id: [{id, name}, ...]} for JS PM filtering
    import json
    division_users_map = {}
    for u in hod_users:
        div_key = str(u.division_id) if u.division_id else '0'
        division_users_map.setdefault(div_key, []).append({
            'id': str(u.id),
            'name': u.full_name or u.email,
        })
    division_users_json = json.dumps(division_users_map)

    context = {
        'contracts':            contracts,
        'stats':                stats,
        'divisions':            divisions,
        'hod_users':            hod_users,
        'division_users_json':  division_users_json,
        'type_filter':          type_filter,
        'status_filter':        status_filter,
        'q':                    q,
        'is_procurement':       _is_pt(request.user),
        'is_hod':               _is_hod(request.user),
        'contract_types':       [c[0] for c in Contract.CONTRACT_TYPE_CHOICES],
    }
    return render(request, 'contracts/contracts_list.html', context)


@login_required
def contract_create_view(request):
    if not _is_pt(request.user):
        messages.error(request, 'Only Procurement Team can create contracts.')
        return redirect('contracts_list')

    if request.method != 'POST':
        return redirect('contracts_list')

    from .models import Contract, ContractHistory
    from apps.divisions.models import Division
    from apps.accounts.models import User

    contract_number    = request.POST.get('contract_number', '').strip()
    contract_name      = request.POST.get('contract_name', '').strip()
    contract_structure = request.POST.get('contract_structure', '').strip()
    contract_type      = request.POST.get('contract_type', '').strip()
    division_id        = request.POST.get('division', '').strip()
    pm_ids             = request.POST.getlist('project_managers')  # multi-select
    notes              = request.POST.get('notes', '').strip()
    contract_budget    = request.POST.get('contract_budget', '').strip() or None
    supplier_name      = request.POST.get('supplier_name', '').strip()

    if not contract_number or not contract_name or not contract_type:
        messages.error(request, 'Contract number, name and type are required.')
        return redirect(reverse('contracts_list') + '?reopen=1')

    if Contract.objects.filter(contract_number=contract_number).exists():
        messages.error(request, f'Contract number "{contract_number}" is already in use. Please choose a different number.')
        from urllib.parse import urlencode
        return redirect(reverse('contracts_list') + '?' + urlencode({'reopen': '1', 'cn': contract_number}))

    division = Division.objects.filter(id=division_id).first() if division_id else None
    pm_qs    = User.objects.filter(id__in=[i for i in pm_ids if i], is_active=True)

    contract = Contract.objects.create(
        contract_number=contract_number,
        contract_name=contract_name,
        contract_type=contract_type,
        contract_structure=contract_structure,
        contract_budget=contract_budget,
        supplier_name=supplier_name,
        division=division,
        created_by=request.user,
        notes=notes,
    )
    if pm_qs.exists():
        contract.project_managers.set(pm_qs)

    # Handle contract document upload
    contract_doc = request.FILES.get('contract_document')
    if contract_doc:
        contract.document = contract_doc
        contract.save(update_fields=['document'])

    pm_names = ', '.join(u.full_name or u.email for u in pm_qs)
    ContractHistory.objects.create(
        contract=contract,
        action='Contract created',
        notes=f'Type: {contract_type}' + (f' | PM(s): {pm_names}' if pm_names else ''),
        action_by=request.user,
    )

    messages.success(request, f'Contract {contract_number} created successfully.')
    return redirect('contract_detail', pk=contract.pk)


# ─────────────────────────────────────────────────────────────────
# Detail view
# ─────────────────────────────────────────────────────────────────

@login_required
def contract_detail_view(request, pk):
    if not _can_view(request.user):
        return redirect('dashboard')

    from .models import Contract, PurchaseOrder, ContractHistory, ContractComment, ContractMilestoneAlert
    from .models import PerformanceGuarantee, ContractCommunication
    from apps.accounts.models import User

    contract = get_object_or_404(Contract, pk=pk)

    # HOD/DM: only their division
    if _is_hod(request.user) and contract.division != getattr(request.user, 'division', None):
        messages.error(request, 'You do not have access to this contract.')
        return redirect('contracts_list')

    history  = ContractHistory.objects.filter(contract=contract).order_by('-created_at')[:30]
    # Contract-level comments (Lumpsum) — those not tied to a specific PO
    comments = ContractComment.objects.filter(contract=contract, purchase_order__isnull=True).select_related('created_by').order_by('-created_at')
    pos      = contract.purchase_orders.all().prefetch_related('comments__created_by', 'performance_guarantees') if contract.contract_type == 'Non-consultancy services' else None
    # Per-PO comment map for Framework: {po.pk: [comments]}
    po_comments_map = {}
    if pos is not None:
        for po in pos:
            po_comments_map[po.pk] = list(po.comments.select_related('created_by').order_by('-created_at'))

    # Performance guarantees for the contract
    pgs = PerformanceGuarantee.objects.filter(contract=contract).select_related('uploaded_by').order_by('-uploaded_at')

    # Communications log
    can_communicate = (
        _is_pt(request.user) or
        _is_hod(request.user) or
        contract.project_managers.filter(pk=request.user.pk).exists()
    )
    communications = ContractCommunication.objects.filter(contract=contract).select_related('sent_by').order_by('-created_at')

    # Build alerts map  {milestone_key: alert_obj}
    alerts_qs  = ContractMilestoneAlert.objects.filter(contract=contract, is_active=True)
    alerts_map = {a.milestone_key: a for a in alerts_qs}

    # ── Consultancy steps ──────────────────────────────────────────────
    consultancy_steps = []
    if contract.contract_type == 'Consultancy Service':
        today     = timezone.now().date()
        start_ref = contract.created_at.date()

        def _c_step(key, label, target_date, approved, prev_done, prev_date_or_created):
            cd = contract.consultancy_step_countdown(target_date, prev_date_or_created)
            alert = alerts_map.get(key)
            ms_ext_counts = contract.milestone_extension_counts or {}
            return {
                'key':        key,
                'label':      label,
                'target':     target_date,
                'approved':   approved,
                'prev_done':  prev_done,
                'countdown':  cd,
                'alert':      alert,
                'ext_count':  ms_ext_counts.get(key, 0),
            }

        s1 = _c_step('inception',    'Inception',    contract.inception_date,    contract.inception_approved,    True,                            start_ref)
        s2 = _c_step('draft_report', 'Draft Report', contract.draft_report_date, contract.draft_report_approved, contract.inception_approved,     contract.inception_date or start_ref)
        s3 = _c_step('final_report', 'Final Report', contract.final_report_date, contract.final_report_approved, contract.draft_report_approved,  contract.draft_report_date or contract.inception_date or start_ref)
        s4_ref = contract.final_report_date or contract.draft_report_date or contract.inception_date or start_ref
        s4 = {
            'key': 'payment', 'label': 'Payment',
            'target': contract.payment_date, 'approved': bool(contract.payment_date),
            'prev_done': contract.final_report_approved, 'countdown': None, 'alert': alerts_map.get('payment'),
        }
        consultancy_steps = [s1, s2, s3, s4]

    # ── Works milestones (7 steps) ──────────────────────────────────────
    works_milestones = []
    if contract.contract_type == 'Works':
        _all_steps = [
            ('kickoff_meeting',     'Kickoff Meeting',      contract.kickoff_meeting_date,      contract.kickoff_meeting_approved),
            ('study_review',        'Study Review',         contract.study_review_date,         contract.study_review_approved),
            ('works_approval',      'Approval',             contract.works_approval_date,       contract.works_approval_approved),
            ('works_start',         'Work Start',           contract.works_start_date,          contract.works_start_approved),
            ('technical_handover',  'Technical Handover',   contract.technical_handover_date,   contract.technical_handover_approved),
            ('provisional_handover','Provisional Handover', contract.provisional_handover_date, contract.provisional_handover_approved),
            ('final_handover',      'Final Handover',       contract.final_handover_date,       contract.final_handover_approved),
        ]
        today = timezone.now().date()
        prev_approved_all = True
        ms_ext_counts = contract.milestone_extension_counts or {}
        for i, (key, name, dt, approved) in enumerate(_all_steps):
            if approved:
                status = 'completed'              # date set + marked done
            elif dt:
                status = 'started'                # date set, not yet done
            else:
                status = 'pending'
            # is_next = no date yet AND all previous steps are fully approved
            is_next = not dt and prev_approved_all
            if not approved:
                prev_approved_all = False          # block later steps from being 'is_next'
            alert   = alerts_map.get(key)
            prev_dt = _all_steps[i-1][2] if i > 0 else None
            prog    = None
            if dt and not approved:
                # In-progress: show elapsed since start date
                start = dt
                if alert and alert.target_date:
                    total_days = max(1, (alert.target_date - start).days)
                    elapsed    = max(0, (today - start).days)
                    remaining  = (alert.target_date - today).days
                    prog = {
                        'done': False, 'start': start, 'target': alert.target_date,
                        'elapsed': elapsed, 'total_days': total_days,
                        'remaining': remaining,
                        'pct': min(100, max(0, round(elapsed / total_days * 100))),
                        'is_overdue': remaining < 0,
                        'overdue_days': abs(remaining) if remaining < 0 else 0,
                    }
            elif not dt and is_next and alert and alert.target_date:
                start      = prev_dt or contract.created_at.date()
                total_days = max(1, (alert.target_date - start).days)
                elapsed    = max(0, (today - start).days)
                remaining  = (alert.target_date - today).days
                prog = {
                    'done': False, 'start': start, 'target': alert.target_date,
                    'elapsed': elapsed, 'total_days': total_days,
                    'remaining': remaining,
                    'pct': min(100, max(0, round(elapsed / total_days * 100))),
                    'is_overdue': remaining < 0,
                    'overdue_days': abs(remaining) if remaining < 0 else 0,
                }
            works_milestones.append({
                'step':     i + 1,
                'key':      key,
                'name':     name,
                'date':     dt,
                'approved': approved,
                'status':   status,
                'is_next':  is_next,
                'is_started': status == 'started',
                'alert':    alert,
                'prog':     prog,
                'ext_count': ms_ext_counts.get(key, 0),
            })

    # Lumpsum countdown
    countdown = contract.lumpsum_progress_data if contract.contract_type == 'Goods' else None

    # Fire any pending milestone alerts (passive check on page load)
    if _is_pt(request.user):
        for alert in alerts_qs:
            if alert.should_fire_today:
                _notify(
                    _recipients_for_contract(contract),
                    f'Milestone Alert — {alert.get_milestone_key_display()} ({contract.contract_number})',
                    f'Target date for {alert.get_milestone_key_display()} is {alert.target_date} '
                    f'({alert.alert_days_before} days notice).',
                    _contract_url(contract),
                )
                from django.utils import timezone as _tz
                alert.notified_at = _tz.now()
                alert.save(update_fields=['notified_at'])

    context = {
        'contract':            contract,
        'history':             history,
        'comments':            comments,
        'po_comments_map':     po_comments_map,
        'pos':                 pos,
        'works_milestones':    works_milestones,
        'consultancy_steps':   consultancy_steps,
        'countdown':           countdown,
        'alerts_map':          alerts_map,
        'is_procurement':      _is_pt(request.user),
        'is_hod':              _is_hod(request.user),
        'today':               timezone.now().date(),
        'pgs':                 pgs,
        'communications':      communications,
        'can_communicate':     can_communicate,
    }
    return render(request, 'contracts/contract_detail.html', context)


# ─────────────────────────────────────────────────────────────────
# Update milestones / dates (Procurement Team only)
# ─────────────────────────────────────────────────────────────────

@login_required
def contract_update_view(request, pk):
    if not _is_pt(request.user):
        messages.error(request, 'Only Procurement Team can update contracts.')
        return redirect('contract_detail', pk=pk)

    if request.method != 'POST':
        return redirect('contract_detail', pk=pk)

    from .models import Contract, ContractHistory
    contract = get_object_or_404(Contract, pk=pk)

    action = request.POST.get('action', '')
    notes  = request.POST.get('notes', '').strip()

    def _parse_date(field):
        val = request.POST.get(field, '').strip()
        return date.fromisoformat(val) if val else None

    if action == 'set_delivery':
        # Lumpsum: set delivery date + record countdown start
        delivery = _parse_date('delivery_date')
        contract.delivery_date = delivery
        if not contract.lumpsum_start_date:
            contract.lumpsum_start_date = timezone.now().date()
        contract.save()
        _log(contract, 'Delivery date set', f'{contract.delivery_date}', request.user)
        _trigger_delivery_alert(contract)
        _trigger_quarter_alert_if_needed(contract)

    elif action in ('extend_lumpsum', 'extend_contract'):
        new_date  = _parse_date('new_end_date') or _parse_date('new_delivery_date')
        ext_notes = request.POST.get('extension_notes', '').strip()
        milestone = request.POST.get('milestone', '').strip()

        if milestone:
            # Extend a specific milestone / step date
            _milestone_fields = {
                # Consultancy
                'inception':          'inception_date',
                'draft_report':       'draft_report_date',
                'final_report':       'final_report_date',
                # Works
                'kickoff_meeting':     'kickoff_meeting_date',
                'study_review':        'study_review_date',
                'works_approval':      'works_approval_date',
                'works_start':         'works_start_date',
                'technical_handover':  'technical_handover_date',
                'provisional_handover':'provisional_handover_date',
                'final_handover':      'final_handover_date',
            }
            _field = _milestone_fields.get(milestone)
            if not _field:
                messages.error(request, 'Invalid milestone.')
                return redirect('contract_detail', pk=pk)
            current_date = getattr(contract, _field, None)
            if not new_date or (current_date and new_date <= current_date):
                messages.error(request, 'New date must be after the current date.')
                return redirect('contract_detail', pk=pk)
            # Shift the milestone's alert target_date by the same delta
            if current_date and new_date:
                from .models import ContractMilestoneAlert
                shift_days = (new_date - current_date).days
                alert_to_shift = ContractMilestoneAlert.objects.filter(
                    contract=contract, milestone_key=milestone, is_active=True
                ).first()
                if alert_to_shift and shift_days > 0:
                    alert_to_shift.target_date = alert_to_shift.target_date + timedelta(days=shift_days)
                    alert_to_shift.notified_at = None   # re-arm the notification
                    alert_to_shift.save(update_fields=['target_date', 'notified_at'])
            setattr(contract, _field, new_date)
            # Reset approved flag so the step goes back to "started"
            approved_field = milestone + '_approved'
            if hasattr(contract, approved_field):
                setattr(contract, approved_field, False)
            counts = contract.milestone_extension_counts or {}
            counts[milestone] = counts.get(milestone, 0) + 1
            contract.milestone_extension_counts = counts
            contract.extension_count = (contract.extension_count or 0) + 1
            contract.extension_notes = ext_notes
            contract.save()
            _log(contract, f'{milestone.replace("_", " ").title()} Extended (#{counts[milestone]})',
                 f'New date: {new_date} | Reason: {ext_notes}', request.user)
            _trigger_contract_change(contract,
                f'Step Extended \u2014 {contract.contract_number}',
                f'{milestone.replace("_", " ").title()} extended to {new_date}. Reason: {ext_notes}.')
        else:
            # Contract-level extend (Lumpsum / Framework)
            _type_field = {
                'Goods':     'delivery_date',
                'Non-consultancy services': 'renewal_end_date' if contract.is_renewed else 'framework_end_date',
            }
            _field = _type_field.get(contract.contract_type, 'delivery_date')
            current_date = getattr(contract, _field, None)
            if not new_date or (current_date and new_date <= current_date):
                messages.error(request, 'New date must be after the current deadline.')
                return redirect('contract_detail', pk=pk)
            if contract.contract_type == 'Goods' and not contract.original_delivery_date:
                contract.original_delivery_date = current_date
            setattr(contract, _field, new_date)
            contract.extension_count = (contract.extension_count or 0) + 1
            contract.extension_notes = ext_notes
            contract.save()
            _log(contract, f'Deadline Extended (#{contract.extension_count})',
                 f'New date: {new_date} | Reason: {ext_notes}', request.user)
            _trigger_contract_change(contract,
                f'Deadline Extended \u2014 {contract.contract_number}',
                f'New deadline: {new_date} (extension #{contract.extension_count}). Reason: {ext_notes}.')
            if contract.contract_type == 'Goods':
                _trigger_quarter_alert_if_needed(contract)

    elif action == 'set_performance_guarantee':
        pg_file = request.FILES.get('performance_guarantee')
        if pg_file:
            contract.performance_guarantee = pg_file
            contract.save(update_fields=['performance_guarantee'])
            _log(contract, 'Performance Guarantee uploaded',
                 pg_file.name, request.user)
        else:
            messages.error(request, 'Please select a file to upload.')
            return redirect('contract_detail', pk=pk)

    elif action == 'issue_completion':
        # Lumpsum: issue Good Completion Certificate
        contract.completion_certificate_date = _parse_date('completion_certificate_date') or timezone.now().date()
        contract.completion_comment = request.POST.get('completion_comment', '').strip()
        pg_file = request.FILES.get('performance_guarantee')
        if pg_file:
            contract.performance_guarantee = pg_file
        contract.status = 'Completed'
        contract.save()
        _log(contract, 'Good Completion Certificate issued', notes, request.user)
        _trigger_contract_change(contract, 'Contract Completed',
            f'Good Completion Certificate issued on {contract.completion_certificate_date}.')

    elif action == 'set_framework_dates':
        contract.framework_start_date = _parse_date('framework_start_date')
        if contract.framework_start_date:
            contract.framework_end_date = contract.framework_start_date + timedelta(days=365)
        contract.save()
        _log(contract, 'Framework period set', f'{contract.framework_start_date} → {contract.framework_end_date}', request.user)
        _trigger_framework_expiry_alert(contract)

    elif action == 'renew_framework':
        if contract.is_renewed:
            messages.error(request, 'Framework contract can only be renewed once.')
            return redirect('contract_detail', pk=pk)
        contract.is_renewed = True
        contract.renewal_start_date = contract.framework_end_date
        contract.renewal_end_date   = contract.framework_end_date + timedelta(days=365)
        contract.status = 'Renewed'
        contract.save()
        _log(contract, 'Framework renewed', f'Renewal period: {contract.renewal_start_date} → {contract.renewal_end_date}', request.user)
        _trigger_framework_expiry_alert(contract)

    elif action == 'set_inception':
        contract.inception_date = _parse_date('step_date') or _parse_date('inception_date')
        contract.inception_approved = False   # reset approval when target is re-set
        contract.save()
        _log(contract, 'Inception target date set', f'{contract.inception_date}', request.user)
        _trigger_contract_change(contract, 'Inception Date Set',
            f'Consultancy inception target set to {contract.inception_date}.')

    elif action == 'approve_inception':
        contract.inception_approved = True
        contract.save()
        _log(contract, 'Inception approved', notes, request.user)
        _trigger_contract_change(contract, 'Inception Approved',
            f'Inception step approved for {contract.contract_number}.')

    elif action == 'set_draft_report':
        contract.draft_report_date = _parse_date('step_date') or _parse_date('draft_report_date')
        contract.draft_report_approved = False
        contract.save()
        _log(contract, 'Draft Report target date set', f'{contract.draft_report_date}', request.user)

    elif action == 'approve_draft_report':
        contract.draft_report_approved = True
        contract.save()
        _log(contract, 'Draft Report approved', notes, request.user)
        _trigger_contract_change(contract, 'Draft Report Approved',
            f'Draft Report step approved for {contract.contract_number}.')

    elif action == 'set_final_report':
        contract.final_report_date = _parse_date('step_date') or _parse_date('final_report_date')
        contract.final_report_approved = False
        contract.save()
        _log(contract, 'Final Report target date set', f'{contract.final_report_date}', request.user)

    elif action == 'approve_final_report':
        contract.final_report_approved = True
        contract.save()
        _log(contract, 'Final Report approved', notes, request.user)
        _trigger_contract_change(contract, 'Final Report Approved',
            f'Final Report step approved for {contract.contract_number}.')

    elif action == 'set_payment':
        contract.payment_date = _parse_date('payment_date')
        contract.status = 'Completed'
        contract.save()
        _log(contract, 'Payment recorded — contract completed', notes, request.user)
        _trigger_contract_change(contract, 'Contract Completed',
            f'Payment recorded on {contract.payment_date}. Contract marked Completed.')

    elif action == 'approve_works_milestone':
        milestone = request.POST.get('milestone', '')
        approved_field_map = {
            'kickoff_meeting':     'kickoff_meeting_approved',
            'study_review':        'study_review_approved',
            'works_approval':      'works_approval_approved',
            'works_start':         'works_start_approved',
            'technical_handover':  'technical_handover_approved',
            'provisional_handover':'provisional_handover_approved',
            'final_handover':      'final_handover_approved',
        }
        label_map = {
            'kickoff_meeting':     'Kickoff Meeting',
            'study_review':        'Study Review',
            'works_approval':      'Approval',
            'works_start':         'Work Start',
            'technical_handover':  'Technical Handover',
            'provisional_handover':'Provisional Handover',
            'final_handover':      'Final Handover',
        }
        if milestone in approved_field_map:
            setattr(contract, approved_field_map[milestone], True)
            if milestone == 'final_handover':
                contract.status = 'Completed'
            contract.save()
            _log(contract, f'{label_map[milestone]} marked Done', notes or '', request.user)
            _trigger_contract_change(contract,
                f'{label_map[milestone]} Completed — {contract.contract_number}',
                f'{label_map[milestone]} has been marked as done.')
        else:
            messages.error(request, 'Invalid milestone.')

    elif action == 'set_works_milestone':
        milestone = request.POST.get('milestone', '')
        milestone_date = _parse_date('milestone_date')
        field_map = {
            'kickoff_meeting':     'kickoff_meeting_date',
            'study_review':        'study_review_date',
            'works_approval':      'works_approval_date',
            'works_start':         'works_start_date',
            'technical_handover':  'technical_handover_date',
            'provisional_handover':'provisional_handover_date',
            'final_handover':      'final_handover_date',
        }
        label_map = {
            'kickoff_meeting':     'Kickoff Meeting',
            'study_review':        'Study Review',
            'works_approval':      'Approval',
            'works_start':         'Work Start',
            'technical_handover':  'Technical Handover',
            'provisional_handover':'Provisional Handover',
            'final_handover':      'Final Handover',
        }
        if milestone in field_map and milestone_date:
            setattr(contract, field_map[milestone], milestone_date)
            # Reset approved flag when re-setting a date
            approved_field = milestone + '_approved'
            if hasattr(contract, approved_field):
                setattr(contract, approved_field, False)
            if milestone == 'final_handover':
                contract.status = 'Completed'
            contract.save()
            _log(contract, f'{label_map[milestone]} set', str(milestone_date), request.user)
            _trigger_works_alert(contract, label_map[milestone], milestone_date)
            # Optional inline alert
            alert_target_str = request.POST.get('alert_target_date', '').strip()
            if alert_target_str:
                try:
                    alert_target = date.fromisoformat(alert_target_str)
                    alert_days   = max(1, int(request.POST.get('alert_days_before', '7') or '7'))
                    from .models import ContractMilestoneAlert
                    ContractMilestoneAlert.objects.update_or_create(
                        contract=contract,
                        milestone_key=milestone,
                        defaults={
                            'target_date':       alert_target,
                            'alert_days_before': alert_days,
                            'created_by':        request.user,
                            'notified_at':       None,
                            'is_active':         True,
                        },
                    )
                    _log(contract, f'Alert set for {label_map[milestone]}',
                         f'Target: {alert_target} | {alert_days}d before', request.user)
                except (ValueError, TypeError):
                    pass
        else:
            messages.error(request, 'Invalid milestone or missing date.')

    elif action == 'cancel':
        contract.status = 'Cancelled'
        contract.save()
        _log(contract, 'Contract cancelled', notes, request.user)
        _trigger_contract_change(contract, 'Contract Cancelled',
            f'Contract {contract.contract_number} was cancelled. Reason: {notes}')

    messages.success(request, 'Contract updated successfully.')
    return redirect('contract_detail', pk=pk)


# ─────────────────────────────────────────────────────────────────
# Purchase Orders (Framework only)
# ─────────────────────────────────────────────────────────────────

@login_required
def contract_issue_po_view(request, pk):
    if not _is_pt(request.user):
        messages.error(request, 'Only Procurement Team can issue purchase orders.')
        return redirect('contract_detail', pk=pk)

    if request.method != 'POST':
        return redirect('contract_detail', pk=pk)

    from .models import Contract, PurchaseOrder, ContractHistory

    contract = get_object_or_404(Contract, pk=pk)
    if contract.contract_type != 'Non-consultancy services':
        messages.error(request, 'Purchase orders are only for Non-consultancy services contracts.')
        return redirect('contract_detail', pk=pk)

    po_number   = request.POST.get('po_number', '').strip()
    description = request.POST.get('description', '').strip()
    issued_date_str   = request.POST.get('issued_date', '').strip()
    delivery_date_str = request.POST.get('delivery_date', '').strip()

    if not po_number or not issued_date_str or not delivery_date_str:
        messages.error(request, 'PO number, issued date and delivery date are required.')
        return redirect('contract_detail', pk=pk)

    if PurchaseOrder.objects.filter(po_number=po_number).exists():
        messages.error(request, f'PO {po_number} already exists.')
        return redirect('contract_detail', pk=pk)

    po = PurchaseOrder.objects.create(
        contract=contract,
        po_number=po_number,
        description=description,
        issued_date=date.fromisoformat(issued_date_str),
        delivery_date=date.fromisoformat(delivery_date_str),
        created_by=request.user,
    )

    # Handle PO document upload
    po_doc = request.FILES.get('po_document')
    if po_doc:
        po.document = po_doc
        po.save(update_fields=['document'])

    ContractHistory.objects.create(
        contract=contract,
        action=f'Purchase Order {po_number} issued',
        notes=f'Delivery: {po.delivery_date}',
        action_by=request.user,
    )
    _trigger_po_delivery_alert(contract, po)

    messages.success(request, f'Purchase Order {po_number} issued.')
    return redirect('contract_detail', pk=pk)


@login_required
def po_complete_view(request, pk, po_pk):
    """Issue Good Completion Certificate for a PO."""
    if not _is_pt(request.user):
        messages.error(request, 'Only Procurement Team can complete purchase orders.')
        return redirect('contract_detail', pk=pk)

    if request.method != 'POST':
        return redirect('contract_detail', pk=pk)

    from .models import Contract, PurchaseOrder, ContractHistory

    contract = get_object_or_404(Contract, pk=pk)
    po       = get_object_or_404(PurchaseOrder, pk=po_pk, contract=contract)

    cert_date_str = request.POST.get('completion_certificate_date', '').strip()
    cert_date = date.fromisoformat(cert_date_str) if cert_date_str else timezone.now().date()

    po.completion_certificate_date = cert_date
    po.completion_comment = request.POST.get('completion_comment', '').strip()
    pg_file = request.FILES.get('performance_guarantee')
    if pg_file:
        po.performance_guarantee = pg_file
    po.status = 'Completed'
    po.save()

    ContractHistory.objects.create(
        contract=contract,
        action=f'Good Completion Certificate issued for PO {po.po_number}',
        notes=f'Date: {cert_date}',
        action_by=request.user,
    )
    _trigger_contract_change(contract,
        f'PO Completed — {po.po_number}',
        f'Good Completion Certificate issued for PO {po.po_number} on {cert_date}.')

    messages.success(request, f'Completion certificate issued for {po.po_number}.')
    return redirect('contract_detail', pk=pk)


@login_required
def po_extend_view(request, pk, po_pk):
    """Extend the delivery deadline for a PO."""
    if not _is_pt(request.user):
        messages.error(request, 'Only Procurement Team can extend purchase order deadlines.')
        return redirect('contract_detail', pk=pk)

    if request.method != 'POST':
        return redirect('contract_detail', pk=pk)

    from .models import Contract, PurchaseOrder, ContractHistory

    contract = get_object_or_404(Contract, pk=pk)
    po       = get_object_or_404(PurchaseOrder, pk=po_pk, contract=contract)

    new_date_str  = request.POST.get('new_delivery_date', '').strip()
    ext_notes     = request.POST.get('extension_notes', '').strip()

    if not new_date_str:
        messages.error(request, 'New delivery date is required.')
        return redirect('contract_detail', pk=pk)

    new_date = date.fromisoformat(new_date_str)
    if new_date <= po.delivery_date:
        messages.error(request, 'New delivery date must be after the current deadline.')
        return redirect('contract_detail', pk=pk)

    if not po.original_delivery_date:
        po.original_delivery_date = po.delivery_date
    po.delivery_date     = new_date
    po.extension_count  += 1
    po.extension_notes   = ext_notes
    po.save()

    ContractHistory.objects.create(
        contract=contract,
        action=f'PO {po.po_number} Deadline Extended (#{po.extension_count})',
        notes=f'New date: {new_date} | Reason: {ext_notes}',
        action_by=request.user,
    )

    _trigger_po_delivery_alert(contract, po, extended=True)
    messages.success(request, f'Deadline for {po.po_number} extended to {new_date}.')
    return redirect('contract_detail', pk=pk)


@login_required
def po_set_pg_view(request, pk, po_pk):
    """Record Performance Guarantee for a specific PO (Framework)."""
    if not _is_pt(request.user):
        messages.error(request, 'Only Procurement Team can update purchase orders.')
        return redirect('contract_detail', pk=pk)
    if request.method != 'POST':
        return redirect('contract_detail', pk=pk)

    from .models import Contract, PurchaseOrder, ContractHistory
    contract = get_object_or_404(Contract, pk=pk)
    po       = get_object_or_404(PurchaseOrder, pk=po_pk, contract=contract)

    pg_file = request.FILES.get('performance_guarantee')
    if not pg_file:
        messages.error(request, 'Please select a file to upload.')
        return redirect('contract_detail', pk=pk)
    po.performance_guarantee = pg_file
    po.save(update_fields=['performance_guarantee'])

    ContractHistory.objects.create(
        contract=contract,
        action=f'Performance Guarantee uploaded for PO {po.po_number}',
        notes=pg_file.name,
        action_by=request.user,
    )
    messages.success(request, f'Performance Guarantee uploaded for {po.po_number}.')
    return redirect('contract_detail', pk=pk)

@login_required
def contract_add_comment_view(request, pk):
    if not _can_view(request.user):
        return redirect('dashboard')
    if request.method != 'POST':
        return redirect('contract_detail', pk=pk)

    from .models import Contract, PurchaseOrder, ContractComment
    contract = get_object_or_404(Contract, pk=pk)
    text   = request.POST.get('comment_text', '').strip()
    po_id  = request.POST.get('po_id', '').strip()
    po_obj = None
    if po_id:
        try:
            po_obj = PurchaseOrder.objects.get(pk=int(po_id), contract=contract)
        except (PurchaseOrder.DoesNotExist, ValueError):
            pass
    if text:
        ContractComment.objects.create(
            contract=contract,
            purchase_order=po_obj,
            text=text,
            created_by=request.user,
        )
        messages.success(request, 'Comment added.')
    else:
        messages.error(request, 'Comment cannot be empty.')
    return redirect('contract_detail', pk=pk)


# ─────────────────────────────────────────────────────────────────
# Milestone Alert Setting
# ─────────────────────────────────────────────────────────────────

@login_required
def contract_set_milestone_alert_view(request, pk):
    if not _is_pt(request.user):
        messages.error(request, 'Only Procurement Team can set alerts.')
        return redirect('contract_detail', pk=pk)
    if request.method != 'POST':
        return redirect('contract_detail', pk=pk)

    from .models import Contract, ContractMilestoneAlert
    from datetime import date as _date

    contract      = get_object_or_404(Contract, pk=pk)
    milestone_key = request.POST.get('milestone_key', '').strip()
    target_str    = request.POST.get('target_date', '').strip()
    days_before   = request.POST.get('alert_days_before', '7').strip()

    if not milestone_key or not target_str:
        messages.error(request, 'Milestone and target date are required.')
        return redirect('contract_detail', pk=pk)

    try:
        target_date  = _date.fromisoformat(target_str)
        days_before  = max(1, int(days_before))
    except (ValueError, TypeError):
        messages.error(request, 'Invalid date or days value.')
        return redirect('contract_detail', pk=pk)

    ContractMilestoneAlert.objects.update_or_create(
        contract=contract,
        milestone_key=milestone_key,
        defaults={
            'target_date':       target_date,
            'alert_days_before': days_before,
            'created_by':        request.user,
            'notified_at':       None,
            'is_active':         True,
        },
    )
    _log(contract, f'Milestone alert set: {milestone_key}',
         f'Target: {target_date} | Alert: {days_before} days before', request.user)
    messages.success(request, f'Alert set: {days_before} days before {milestone_key.replace("_", " ").title()} ({target_date}).')
    return redirect('contract_detail', pk=pk)


# ─────────────────────────────────────────────────────────────────
# Performance Guarantees (multiple per contract / PO)
# ─────────────────────────────────────────────────────────────────

@login_required
def contract_add_pg_view(request, pk):
    """Add a Performance Guarantee document to a contract."""
    if not _is_pt(request.user):
        messages.error(request, 'Only Procurement Team can upload performance guarantees.')
        return redirect('contract_detail', pk=pk)
    if request.method != 'POST':
        return redirect('contract_detail', pk=pk)

    from .models import Contract, PerformanceGuarantee
    contract = get_object_or_404(Contract, pk=pk)
    pg_file  = request.FILES.get('pg_file')
    if not pg_file:
        messages.error(request, 'Please select a file to upload.')
        return redirect('contract_detail', pk=pk)

    expiry_str  = request.POST.get('pg_expiry_date', '').strip()
    description = request.POST.get('pg_description', '').strip()
    expiry_date = None
    if expiry_str:
        try:
            expiry_date = date.fromisoformat(expiry_str)
        except ValueError:
            pass

    PerformanceGuarantee.objects.create(
        contract=contract,
        file=pg_file,
        expiry_date=expiry_date,
        description=description,
        uploaded_by=request.user,
    )
    _log(contract, 'Performance Guarantee uploaded', f'{pg_file.name}' + (f' | Expiry: {expiry_date}' if expiry_date else ''), request.user)
    messages.success(request, 'Performance Guarantee uploaded successfully.')
    return redirect('contract_detail', pk=pk)


@login_required
def po_add_pg_view(request, pk, po_pk):
    """Add a Performance Guarantee document to a PO."""
    if not _is_pt(request.user):
        messages.error(request, 'Only Procurement Team can upload performance guarantees.')
        return redirect('contract_detail', pk=pk)
    if request.method != 'POST':
        return redirect('contract_detail', pk=pk)

    from .models import Contract, PurchaseOrder, POPerformanceGuarantee
    contract = get_object_or_404(Contract, pk=pk)
    po       = get_object_or_404(PurchaseOrder, pk=po_pk, contract=contract)
    pg_file  = request.FILES.get('pg_file')
    if not pg_file:
        messages.error(request, 'Please select a file to upload.')
        return redirect('contract_detail', pk=pk)

    expiry_str  = request.POST.get('pg_expiry_date', '').strip()
    description = request.POST.get('pg_description', '').strip()
    expiry_date = None
    if expiry_str:
        try:
            expiry_date = date.fromisoformat(expiry_str)
        except ValueError:
            pass

    POPerformanceGuarantee.objects.create(
        purchase_order=po,
        file=pg_file,
        expiry_date=expiry_date,
        description=description,
        uploaded_by=request.user,
    )
    _log(contract, f'PO {po.po_number} — Performance Guarantee uploaded', pg_file.name, request.user)
    messages.success(request, f'Performance Guarantee uploaded for {po.po_number}.')
    return redirect('contract_detail', pk=pk)


# ─────────────────────────────────────────────────────────────────
# Delivery Receipt & Evaluation  (Contract-level)
# ─────────────────────────────────────────────────────────────────

@login_required
def contract_receive_view(request, pk):
    """Confirm that goods/services have been received on a contract."""
    if not _is_pt(request.user):
        messages.error(request, 'Only Procurement Team can record receipt confirmation.')
        return redirect('contract_detail', pk=pk)
    if request.method != 'POST':
        return redirect('contract_detail', pk=pk)

    from .models import Contract
    contract = get_object_or_404(Contract, pk=pk)

    received_date_str = request.POST.get('received_date', '').strip()
    received_notes    = request.POST.get('received_notes', '').strip()

    try:
        received_date = date.fromisoformat(received_date_str) if received_date_str else timezone.now().date()
    except ValueError:
        received_date = timezone.now().date()

    contract.received_date  = received_date
    contract.received_by    = request.user
    contract.received_notes = received_notes
    contract.save(update_fields=['received_date', 'received_by', 'received_notes'])

    _log(contract, 'Delivery Received', f'Received on {received_date}. {received_notes}', request.user)
    _trigger_contract_change(contract, f'Delivery Received — {contract.contract_number}',
        f'Goods/services confirmed received on {received_date}.')
    messages.success(request, 'Delivery receipt recorded.')
    return redirect('contract_detail', pk=pk)


@login_required
def contract_evaluate_view(request, pk):
    """Record evaluation of received goods/services."""
    if not _is_pt(request.user):
        messages.error(request, 'Only Procurement Team can record evaluations.')
        return redirect('contract_detail', pk=pk)
    if request.method != 'POST':
        return redirect('contract_detail', pk=pk)

    from .models import Contract
    contract = get_object_or_404(Contract, pk=pk)

    if not contract.received_date:
        messages.error(request, 'You must confirm receipt before recording evaluation.')
        return redirect('contract_detail', pk=pk)

    evaluation_date_str = request.POST.get('evaluation_date', '').strip()
    evaluation_notes    = request.POST.get('evaluation_notes', '').strip()

    try:
        evaluation_date = date.fromisoformat(evaluation_date_str) if evaluation_date_str else timezone.now().date()
    except ValueError:
        evaluation_date = timezone.now().date()

    contract.evaluation_date  = evaluation_date
    contract.evaluation_notes = evaluation_notes
    contract.save(update_fields=['evaluation_date', 'evaluation_notes'])

    _log(contract, 'Evaluation Completed', f'Evaluated on {evaluation_date}. {evaluation_notes}', request.user)
    messages.success(request, 'Evaluation recorded.')
    return redirect('contract_detail', pk=pk)


# ─────────────────────────────────────────────────────────────────
# Delivery Receipt & Evaluation  (PO-level)
# ─────────────────────────────────────────────────────────────────

@login_required
def po_receive_view(request, pk, po_pk):
    """Confirm receipt for a PO."""
    if not _is_pt(request.user):
        messages.error(request, 'Only Procurement Team can record PO receipt.')
        return redirect('contract_detail', pk=pk)
    if request.method != 'POST':
        return redirect('contract_detail', pk=pk)

    from .models import Contract, PurchaseOrder
    contract = get_object_or_404(Contract, pk=pk)
    po       = get_object_or_404(PurchaseOrder, pk=po_pk, contract=contract)

    received_date_str = request.POST.get('received_date', '').strip()
    received_notes    = request.POST.get('received_notes', '').strip()

    try:
        received_date = date.fromisoformat(received_date_str) if received_date_str else timezone.now().date()
    except ValueError:
        received_date = timezone.now().date()

    po.received_date  = received_date
    po.received_by    = request.user
    po.received_notes = received_notes
    po.save(update_fields=['received_date', 'received_by', 'received_notes'])

    _log(contract, f'PO {po.po_number} — Delivery Received',
         f'Received on {received_date}. {received_notes}', request.user)
    messages.success(request, f'Receipt confirmed for {po.po_number}.')
    return redirect('contract_detail', pk=pk)


@login_required
def po_evaluate_view(request, pk, po_pk):
    """Record evaluation for a PO."""
    if not _is_pt(request.user):
        messages.error(request, 'Only Procurement Team can record PO evaluations.')
        return redirect('contract_detail', pk=pk)
    if request.method != 'POST':
        return redirect('contract_detail', pk=pk)

    from .models import Contract, PurchaseOrder
    contract = get_object_or_404(Contract, pk=pk)
    po       = get_object_or_404(PurchaseOrder, pk=po_pk, contract=contract)

    if not po.received_date:
        messages.error(request, 'You must confirm PO receipt before recording evaluation.')
        return redirect('contract_detail', pk=pk)

    evaluation_date_str = request.POST.get('evaluation_date', '').strip()
    evaluation_notes    = request.POST.get('evaluation_notes', '').strip()

    try:
        evaluation_date = date.fromisoformat(evaluation_date_str) if evaluation_date_str else timezone.now().date()
    except ValueError:
        evaluation_date = timezone.now().date()

    po.evaluation_date  = evaluation_date
    po.evaluation_notes = evaluation_notes
    po.save(update_fields=['evaluation_date', 'evaluation_notes'])

    _log(contract, f'PO {po.po_number} — Evaluation Completed',
         f'Evaluated on {evaluation_date}. {evaluation_notes}', request.user)
    messages.success(request, f'Evaluation recorded for {po.po_number}.')
    return redirect('contract_detail', pk=pk)


# ─────────────────────────────────────────────────────────────────
# Contract Communication Log
# ─────────────────────────────────────────────────────────────────

@login_required
def contract_add_communication_view(request, pk):
    """Add a communication entry to a contract's communication log."""
    from .models import Contract, ContractCommunication
    contract = get_object_or_404(Contract, pk=pk)

    # Allow Procurement Team, HOD/DM, and contract Project Managers to communicate
    can_comm = (
        _is_pt(request.user) or
        _is_hod(request.user) or
        contract.project_managers.filter(pk=request.user.pk).exists()
    )
    if not can_comm:
        messages.error(request, 'You do not have permission to post to this contract communication log.')
        return redirect('contract_detail', pk=pk)

    if request.method != 'POST':
        return redirect('contract_detail', pk=pk)

    subject    = request.POST.get('comm_subject', '').strip()
    message    = request.POST.get('comm_message', '').strip()
    attachment = request.FILES.get('comm_attachment')

    if not message:
        messages.error(request, 'Communication message cannot be empty.')
        return redirect('contract_detail', pk=pk)

    ContractCommunication.objects.create(
        contract=contract,
        subject=subject,
        message=message,
        attachment=attachment if attachment else None,
        sent_by=request.user,
    )
    _log(contract, 'Communication added',
         f'Subject: {subject or "(no subject)"}', request.user)
    messages.success(request, 'Communication added to contract log.')
    return redirect('contract_detail', pk=pk)


# ─────────────────────────────────────────────────────────────────
# Alert helpers
# ─────────────────────────────────────────────────────────────────

def _log(contract, action, notes, user):
    from .models import ContractHistory
    ContractHistory.objects.create(
        contract=contract, action=action, notes=notes or '', action_by=user,
    )


def _notify(users_qs, title, message, url):
    """Create in-app notifications for a queryset of users."""
    try:
        from apps.notifications.models import Notification
        for user in users_qs:
            Notification.objects.create(
                user=user, title=title, message=message,
                notification_type='submission_status', priority='high',
                related_object_type='Contract', action_url=url,
            )
    except Exception:
        pass


def _contract_url(contract):
    return f'/dashboard/contracts/{contract.pk}/'


def _recipients_for_contract(contract):
    """Return a queryset of Users who should be notified about this contract.
    Includes all Procurement Team + all HOD/DM users + the contract's project manager.
    """
    from apps.accounts.models import User
    from django.db.models import Q
    pm_ids = list(contract.project_managers.values_list('id', flat=True))
    qs = User.objects.filter(
        Q(role__name__in=['Procurement Team', 'HOD/DM']) | Q(id__in=pm_ids),
        is_active=True,
    ).distinct()
    return qs


def _trigger_delivery_alert(contract):
    days = contract.days_until_delivery
    _notify(
        _recipients_for_contract(contract),
        f'Delivery Date Set — {contract.contract_number}',
        f'Delivery date set to {contract.delivery_date} ({days} days remaining).',
        _contract_url(contract),
    )


def _trigger_framework_expiry_alert(contract):
    end = contract.framework_active_end
    label = 'renewed' if contract.is_renewed else 'set'
    _notify(
        _recipients_for_contract(contract),
        f'Framework Contract Period {label.title()} — {contract.contract_number}',
        f'Framework period {label}: ends {end}.',
        _contract_url(contract),
    )


def _trigger_po_delivery_alert(contract, po, extended=False):
    action_label = 'Deadline Extended' if extended else 'Issued'
    _notify(
        _recipients_for_contract(contract),
        f'PO {action_label} — {po.po_number}',
        f'PO {po.po_number} ({action_label.lower()}) under {contract.contract_number}. Delivery: {po.delivery_date}.',
        _contract_url(contract),
    )


def _trigger_quarter_alert_if_needed(contract):
    """Fire a notification when <= 1/4 of the contract period remains."""
    data = contract.lumpsum_progress_data
    if not data or not data['is_quarter_alert']:
        return
    _notify(
        _recipients_for_contract(contract),
        f'Contract Deadline Alert — {contract.contract_number}',
        f'Only {data["remaining"]} day(s) remaining out of {data["total_days"]} '
        f'(less than 1/4 of contract time). Deadline: {contract.delivery_date}.',
        _contract_url(contract),
    )


def _trigger_works_alert(contract, step_name, step_date):
    _notify(
        _recipients_for_contract(contract),
        f'{step_name} — {contract.contract_number}',
        f'{step_name} milestone recorded on {step_date}.',
        _contract_url(contract),
    )


def _trigger_contract_change(contract, action_label, detail=''):
    """Generic notification for any contract-level change."""
    _notify(
        _recipients_for_contract(contract),
        f'{action_label} — {contract.contract_number}',
        detail or action_label,
        _contract_url(contract),
    )
