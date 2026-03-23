"""
Procurement Team views for external activity tracking and status updates.
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from apps.dashboard.views import convert_word_to_html, convert_excel_to_html


@login_required
def procurement_dashboard_view(request):
    """
    Procurement Team dashboard – action queue, tender pipeline, contracts, activity.
    """
    user = request.user

    if user.role and user.role.name != 'Procurement Team':
        return redirect('dashboard')

    from apps.procurement.models import Submission, Tender
    from apps.contracts.models import Contract
    from apps.workflows.models import WorkflowHistory
    from apps.notifications.models import Notification
    from apps.divisions.models import Division
    from django.db.models import Sum, Count, Q
    from apps.dashboard.views import time_ago

    # ── Stages where PT must act (submission-level) ──────────────
    _SUBMISSION_PENDING = [
        'HOD/DM Submit', 'Review of Procurement Draft',
        'Submit Compiled Document', 'Publish Plan',
    ]

    # ── Stages where PT must act (tender-level) ──────────────────
    _PT_TENDER_PENDING = [
        'Prepare Tender Document', 'Publication of TD', 'Opening',
        'Evaluation', 'Notify Bidders', 'Contract Negotiation',
        'Contract Drafting', 'Legal Review', 'Supplier Approval',
        'MINIJUST Legal Review',
    ]

    # ── Action queues ─────────────────────────────────────────────
    pending_submissions = Submission.objects.filter(
        status__in=_SUBMISSION_PENDING, is_deleted=False
    ).select_related('division', 'call').order_by('-created_at')

    action_queue = []
    for sub in pending_submissions:
        call_doc_url = None
        call_doc_type = None
        call_doc_name = None
        if sub.call and sub.call.call_document:
            call_doc_url = sub.call.call_document.url
            fname = sub.call.call_document.name.lower()
            if fname.endswith('.pdf'):
                call_doc_type = 'pdf'
            elif fname.endswith(('.doc', '.docx')):
                call_doc_type = 'word'
            elif fname.endswith(('.xls', '.xlsx')):
                call_doc_type = 'excel'
            elif fname.endswith('.txt'):
                call_doc_type = 'txt'
            elif fname.endswith('.zip'):
                call_doc_type = 'zip'
            else:
                call_doc_type = 'other'
            call_doc_name = sub.call.call_document.name.split('/')[-1]
        action_queue.append({
            'id': sub.id,
            'tracking_reference': sub.tracking_reference,
            'item_name': sub.item_name,
            'division': sub.division.name if sub.division else '—',
            'status': sub.status,
            'total_budget': sub.total_budget,
            'days_waiting': sub.days_at_current_stage,
            'call_doc_url': call_doc_url,
            'call_doc_type': call_doc_type,
            'call_doc_name': call_doc_name,
        })

    # Tender-level action queue
    pending_tenders = Tender.objects.filter(
        status__in=_PT_TENDER_PENDING
    ).select_related('submission__division').order_by('-created_at')[:20]

    tender_action_queue = []
    for t in pending_tenders:
        tender_action_queue.append({
            'tender_number': t.tender_number,
            'tender_title': t.tender_title,
            'division': t.submission.division.name if t.submission and t.submission.division else '—',
            'status': t.status,
        })

    # ── Tender pipeline board (group by status) ──────────────────
    all_tender_statuses = [
        'Prepare Tender Document', 'CBM Review TD', 'Publication of TD',
        'Opening', 'Evaluation', 'CBM Approval', 'Notify Bidders',
        'Contract Negotiation', 'Contract Drafting', 'Legal Review',
        'Supplier Approval', 'MINIJUST Legal Review', 'Awarded', 'Completed',
    ]
    tender_pipeline = []
    for status in all_tender_statuses:
        count = Tender.objects.filter(status=status).count()
        if count > 0:
            tender_pipeline.append({'status': status, 'count': count})

    # ── Active contracts with health ──────────────────────────────
    active_contracts_qs = Contract.objects.filter(
        status__in=['Active', 'Renewed']
    ).select_related('division')

    contract_rows = []
    overdue_count = 0
    for c in active_contracts_qs:
        prog = c.lumpsum_progress_data
        days = c.days_until_delivery
        is_overdue = (prog and prog.get('is_overdue')) or (days is not None and days < 0)
        is_warning = (prog and prog.get('is_quarter_alert')) or (days is not None and 0 <= days <= 30)
        if is_overdue:
            overdue_count += 1
            health = 'overdue'
        elif is_warning:
            health = 'warning'
        else:
            health = 'healthy'

        contract_rows.append({
            'id': c.id,
            'contract_number': c.contract_number,
            'contract_name': c.contract_name,
            'contract_type': c.contract_type,
            'status': c.status,
            'health': health,
            'days_until_delivery': days,
            'division': c.division.name if c.division else '—',
            'pct': prog['pct'] if prog else None,
        })
    # sort overdue first
    _order = {'overdue': 0, 'warning': 1, 'healthy': 2}
    contract_rows.sort(key=lambda x: _order[x['health']])

    # ── Tenders awarded with no contract yet ─────────────────────
    tenders_need_contract = Tender.objects.filter(
        status='Awarded'
    ).annotate(
        contract_count=Count('contracts')
    ).filter(contract_count=0).select_related('submission__division')[:20]

    tenders_need_contract_list = []
    for t in tenders_need_contract:
        tenders_need_contract_list.append({
            'tender_number': t.tender_number,
            'tender_title': t.tender_title,
            'division': t.submission.division.name if t.submission and t.submission.division else '—',
        })

    # ── Total pipeline value ──────────────────────────────────────
    live_statuses = [s for s in _SUBMISSION_PENDING + _PT_TENDER_PENDING]
    total_pipeline_value = Submission.objects.filter(
        status__in=['HOD/DM Submit', 'Review of Procurement Draft', 'Submit Compiled Document',
                    'CBM Review', 'Publish Plan', 'Prepare Tender Document', 'CBM Review TD',
                    'Publication of TD', 'Opening', 'Evaluation', 'CBM Approval',
                    'Notify Bidders', 'Contract Negotiation', 'Contract Drafting',
                    'Legal Review', 'Supplier Approval', 'MINIJUST Legal Review'],
        is_deleted=False
    ).aggregate(total=Sum('total_budget'))['total'] or 0

    # ── Division activity snapshot ────────────────────────────────
    division_activity = []
    for div in Division.objects.all():
        subs = Submission.objects.filter(division=div, is_deleted=False)
        pending = subs.filter(status__in=_SUBMISSION_PENDING).count()
        in_tender = subs.filter(status__in=_PT_TENDER_PENDING).count()
        awarded = subs.filter(status__in=['Awarded', 'Completed']).count()
        if subs.count() > 0:
            division_activity.append({
                'name': div.name,
                'total': subs.count(),
                'pending': pending,
                'in_tender': in_tender,
                'awarded': awarded,
            })
    division_activity.sort(key=lambda x: x['total'], reverse=True)

    # ── Recent workflow activity ──────────────────────────────────
    recent_activity = []
    for h in WorkflowHistory.objects.select_related(
        'submission', 'action_by', 'from_stage', 'to_stage'
    ).order_by('-created_at')[:10]:
        recent_activity.append({
            'actor': h.action_by.full_name if h.action_by else 'System',
            'action': h.get_action_display(),
            'submission_ref': h.submission.tracking_reference if h.submission else '—',
            'from_stage': h.from_stage.name if h.from_stage else '—',
            'to_stage': h.to_stage.name if h.to_stage else '—',
            'time': time_ago(h.created_at),
        })

    # ── Unread notifications ──────────────────────────────────────
    unread_notifications = Notification.objects.filter(
        user=user, is_read=False
    ).order_by('-created_at')[:5]
    unread_count = Notification.objects.filter(user=user, is_read=False).count()

    # ── KPI stats ─────────────────────────────────────────────────
    stats = {
        'submissions_pending': len(action_queue),
        'tenders_active': Tender.objects.exclude(
            status__in=['Completed', 'Cancelled']
        ).count(),
        'active_contracts': active_contracts_qs.count(),
        'overdue_contracts': overdue_count,
        'total_pipeline_value': total_pipeline_value,
        'awarded_need_contract': len(tenders_need_contract_list),
    }

    context = {
        'stats': stats,
        'action_queue': action_queue,
        'tender_action_queue': tender_action_queue,
        'tender_pipeline': tender_pipeline,
        'contract_rows': contract_rows,
        'tenders_need_contract': tenders_need_contract_list,
        'division_activity': division_activity,
        'recent_activity': recent_activity,
        'unread_notifications': unread_notifications,
        'unread_count': unread_count,
    }

    return render(request, 'procurement/dashboard.html', context)


@login_required
def procurement_submission_detail_view(request, submission_id):
    """
    View for procurement team to record Umucyo information and update milestones.
    """
    user = request.user
    
    if user.role and user.role.name != 'Procurement Team':
        return redirect('dashboard')
    
    from apps.procurement.models import Submission, Comment
    from apps.workflows.models import WorkflowHistory, WorkflowStage
    from apps.notifications.models import Notification
    
    try:
        submission = Submission.objects.select_related(
            'division', 'call', 'current_stage', 'submitted_by'
        ).get(id=submission_id)
    except Submission.DoesNotExist:
        return render(request, 'dashboard/error.html', {'error': 'Submission not found'})
    
    # Get workflow history
    workflow_history = WorkflowHistory.objects.filter(
        submission=submission
    ).select_related('action_by', 'from_stage', 'to_stage').order_by('created_at')
    
    # Build workflow visualization with role information
    # Only show submission stages (internal + transition, orders 1-6).
    # External tender stages are tracked separately on the Tender pages.
    all_stages = WorkflowStage.objects.filter(
        stage_type__in=['internal', 'transition']
    ).order_by('order')
    role_mapping = {
        'Call Issued': ('CBM', 'Chief Budget Manager'),
        'HOD/DM Submit': ('HOD/DM', 'Head of Department'),
        'Review of Procurement Draft': ('Procurement Team', 'Procurement Officer'),
        'Submit Compiled Document': ('Procurement Team', 'Procurement Officer'),
        'CBM Review': ('CBM', 'Chief Budget Manager'),
        'Publish Plan': ('Procurement Team', 'Procurement Officer'),
        'Prepare Tender Document': ('Procurement Team', 'Procurement Officer'),
        'CBM Review TD': ('CBM', 'Chief Budget Manager'),
        'Publication of TD': ('Procurement Team', 'Procurement Officer'),
        'Opening': ('Procurement Team', 'Procurement Officer'),
        'Evaluation': ('Procurement Team', 'Procurement Officer'),
        'CBM Approval': ('CBM', 'Chief Budget Manager'),
        'Notify Bidders': ('Procurement Team', 'Procurement Officer'),
        'Contract Negotiation': ('Procurement Team', 'Procurement Officer'),
        'Contract Drafting': ('Procurement Team', 'Procurement Officer'),
        'Legal Review': ('Procurement Team', 'Procurement Officer'),
        'Supplier Approval': ('Procurement Team', 'Procurement Officer'),
        'MINIJUST Legal Review': ('Procurement Team', 'Procurement Officer'),
        'Awarded': ('Procurement Team', 'Procurement Officer'),
        'Completed': ('Procurement Team', 'Procurement Officer'),
    }
    
    # Map submission status to workflow stage order (same as CBM and HOD)
    status_to_stage_order = {
        'Draft': 0,  # Pre-workflow
        'Call Issued': 1,
        'HOD/DM Submit': 2,
        'Review of Procurement Draft': 3,
        'Returned': -1,  # Special handling
        'Submit Compiled Document': 4,
        'CBM Review': 5,
        'Publish Plan': 6,
        'Prepare Tender Document': 7,
        'CBM Review TD': 8,
        'Publication of TD': 9,
        'Opening': 10,
        'Evaluation': 11,
        'CBM Approval': 12,
        'Notify Bidders': 13,
        'Contract Negotiation': 14,
        'Contract Drafting': 15,
        'Legal Review': 16,
        'Supplier Approval': 17,
        'MINIJUST Legal Review': 18,
        'Awarded': 19,
        'Completed': 20,
        'Rejected': 5,
        'Cancelled': 5,
    }
    
    # Get the current stage order from the submission's current_stage
    # This is the single source of truth and will be updated when clarification is requested
    if submission.current_stage:
        current_stage_order = submission.current_stage.order
        is_returned = submission.status == 'Returned'
        returned_from_stage = submission.current_stage.name if is_returned else None
    else:
        # Fallback to status mapping if current_stage is not set
        current_stage_order = status_to_stage_order.get(submission.status, 0)
        is_returned = submission.status == 'Returned'
        last_history = WorkflowHistory.objects.filter(
            submission=submission
        ).order_by('-created_at').first()
        returned_from_stage = last_history.from_stage.name if last_history and last_history.from_stage and is_returned else None
    
    # Build workflow visualization with correct stage states
    workflow_visualization = []
    completed_count = 0
    
    for stage in all_stages:
        # A stage is:
        # - Completed: if its order is less than current_stage_order
        # - Current: if its order equals current_stage_order
        # - Pending: if its order is greater than current_stage_order
        is_completed = stage.order < current_stage_order
        is_current = stage.order == current_stage_order
        
        if is_completed:
            completed_count += 1
        
        role_info = role_mapping.get(stage.name, ('Unknown', 'Unknown'))
        
        # Get approval date from workflow history if available
        # Look for records where FROM_STAGE is this stage (when this stage was approved and moved forward)
        approval_date = None
        if stage.order >= 5:  # Only from CBM Review onwards (order 5)
            history_record = workflow_history.filter(from_stage=stage).first()
            if history_record and history_record.approval_date:
                approval_date = history_record.approval_date
        
        workflow_visualization.append({
            'id': stage.id,
            'order': stage.order,
            'name': stage.name,
            'description': stage.description,
            'is_completed': is_completed,
            'is_current': is_current,
            'role': role_info[0],
            'responsible': role_info[1],
            'approval_date': approval_date,
        })
    
    # Calculate progress based on submission stages only (1-6)
    total_stages = all_stages.count()  # 6 stages
    progress_percent = int((completed_count / total_stages * 100)) if total_stages > 0 else 0
    
    # Calculate SVG line x2 position
    progress_x2 = 50 + (completed_count / total_stages * 900) if total_stages > 0 else 50
    
    # Calculate days elapsed and remaining
    from datetime import datetime
    now = timezone.now()
    days_elapsed = (now - submission.created_at).days
    days_remaining = 0
    if submission.expected_delivery_date:
        days_remaining = max(0, (submission.expected_delivery_date - now.date()).days)
    
    # Get comments
    comments = Comment.objects.filter(
        submission=submission
    ).select_related('author').order_by('-created_at')
    
    # Get supporting documents grouped by type and prepare preview data
    from apps.procurement.models import SubmissionDocument
    supporting_documents_list = submission.supporting_documents.all().order_by('document_type', '-uploaded_at')
    
    # Group documents by type and prepare preview data
    procurement_plan_docs = []
    technical_spec_docs = []
    market_survey_docs = []
    
    doc_type_groups = {
        'procurement_plan': procurement_plan_docs,
        'technical_specification': technical_spec_docs,
        'market_survey': market_survey_docs,
    }
    
    for doc in supporting_documents_list:
        # Detect document file type and prepare preview
        filename = doc.original_filename.lower()
        doc_file_type = None
        doc_preview_html = None
        absolute_document_url = request.build_absolute_uri(doc.file.url)
        
        if filename.endswith('.pdf'):
            doc_file_type = 'pdf'
        elif filename.endswith('.txt'):
            doc_file_type = 'txt'
        elif filename.endswith(('.doc', '.docx')):
            doc_file_type = 'word'
            # Convert Word to HTML
            try:
                doc_preview_html = convert_word_to_html(doc.file.path)
            except Exception as e:
                doc_preview_html = f'<div class="alert alert-danger">Error loading Word document preview: {str(e)}</div>'
        elif filename.endswith(('.xls', '.xlsx')):
            doc_file_type = 'excel'
            # Convert Excel to HTML
            try:
                doc_preview_html = convert_excel_to_html(doc.file.path)
            except Exception as e:
                doc_preview_html = f'<div class="alert alert-danger">Error loading Excel file preview: {str(e)}</div>'
        elif filename.endswith('.zip'):
            doc_file_type = 'zip'
        
        # Add document with preview data to the appropriate category
        doc_data = {
            'id': str(doc.id),
            'original_filename': doc.original_filename,
            'file_size': doc.file_size,
            'file_url': doc.file.url,
            'absolute_url': absolute_document_url,
            'doc_file_type': doc_file_type,
            'doc_preview_html': doc_preview_html,
            'uploaded_at': doc.uploaded_at,
            'uploaded_by': doc.uploaded_by.full_name if doc.uploaded_by else 'System',
        }
        
        if doc.document_type in doc_type_groups:
            doc_type_groups[doc.document_type].append(doc_data)
    
    # Detect document file type for procurement call preview
    doc_file_type = None
    absolute_document_url = None
    doc_preview_html = None
    if submission.call and submission.call.call_document:
        filename = submission.call.call_document.name.lower()
        if filename.endswith('.pdf'):
            doc_file_type = 'pdf'
        elif filename.endswith('.txt'):
            doc_file_type = 'txt'
        elif filename.endswith(('.doc', '.docx')):
            doc_file_type = 'word'
            # Convert Word to HTML
            try:
                doc_preview_html = convert_word_to_html(submission.call.call_document.path)
            except Exception as e:
                doc_preview_html = f'<div class="alert alert-danger">Error loading Word document preview: {str(e)}</div>'
        elif filename.endswith(('.xls', '.xlsx')):
            doc_file_type = 'excel'
            # Convert Excel to HTML
            try:
                doc_preview_html = convert_excel_to_html(submission.call.call_document.path)
            except Exception as e:
                doc_preview_html = f'<div class="alert alert-danger">Error loading Excel file preview: {str(e)}</div>'
        elif filename.endswith('.zip'):
            doc_file_type = 'zip'
        # Convert relative URL to absolute URL for Google Docs Viewer
        absolute_document_url = request.build_absolute_uri(submission.call.call_document.url)
    
    # Split workflow visualization into two separate tracker groups
    submission_workflow_viz = [s for s in workflow_visualization if s['order'] <= 3]
    compiled_workflow_viz = [s for s in workflow_visualization if 4 <= s['order'] <= 6]

    context = {
        'submission': submission,
        'current_stage': submission.current_stage,
        'workflow_visualization': workflow_visualization,
        'submission_workflow_viz': submission_workflow_viz,
        'compiled_workflow_viz': compiled_workflow_viz,
        'workflow_timeline': workflow_history,
        'workflow_history': workflow_history,
        'comments': comments,
        'current_stage_order': current_stage_order,
        'completed_count': completed_count,
        'total_stages': total_stages,
        'progress_percent': progress_percent,
        'progress_x2': progress_x2,
        'elapsed_days': days_elapsed,
        'remaining_days': days_remaining,
        'is_returned': is_returned,
        'returned_from_stage': returned_from_stage,
        'returned_status': 'Returned for Clarification' if is_returned else None,
        'supporting_documents': supporting_documents_list,
        'procurement_plan_docs': procurement_plan_docs,
        'technical_spec_docs': technical_spec_docs,
        'market_survey_docs': market_survey_docs,
        'doc_file_type': doc_file_type,
        'absolute_document_url': absolute_document_url,
        'doc_preview_html': doc_preview_html,
    }
    
    return render(request, 'procurement/submission_detail.html', context)


@login_required
def procurement_record_umucyo_view(request, submission_id):
    """
    Record Umucyo Tender ID and link.
    """
    user = request.user
    
    if user.role and user.role.name != 'Procurement Team':
        return redirect('dashboard')
    
    from apps.procurement.models import Submission
    
    if request.method == 'POST':
        try:
            submission = Submission.objects.get(id=submission_id)
            umucyo_reference = request.POST.get('umucyo_reference', '').strip()
            umucyo_link = request.POST.get('umucyo_link', '').strip()
            
            if not umucyo_reference:
                messages.error(request, 'Umucyo Reference is required')
                return redirect('procurement_submission_detail', submission_id=submission_id)
            
            submission.umucyo_reference = umucyo_reference
            submission.umucyo_link = umucyo_link
            submission.save()
            
            messages.success(request, 'Umucyo information recorded successfully!')
            
        except Submission.DoesNotExist:
            messages.error(request, 'Submission not found')
    
    return redirect('procurement_submission_detail', submission_id=submission_id)


@login_required
def procurement_update_status_view(request, submission_id):
    """
    Update submission status to reflect Umucyo milestones.
    """
    user = request.user
    
    if user.role and user.role.name != 'Procurement Team':
        return redirect('dashboard')
    
    from apps.procurement.models import Submission
    from apps.workflows.models import WorkflowHistory, WorkflowStage
    from apps.notifications.models import Notification
    
    if request.method == 'POST':
        try:
            submission = Submission.objects.get(id=submission_id)
            new_status = request.POST.get('status', '').strip()
            notes = request.POST.get('notes', '').strip()
            
            # Map status to stage
            status_stage_map = {
                'Publication of TD': 8,
                'Opening': 9,
                'Evaluation': 10,
                'CBM Approval': 11,
                'Notify Bidders': 12,
                'Contract Negotiation': 13,
                'Contract Drafting': 14,
                'Legal Review': 15,
                'Supplier Approval': 16,
                'MINIJUST Legal Review': 17,
                'Awarded': 18,
                'Completed': 19
            }
            
            if new_status not in status_stage_map:
                messages.error(request, 'Invalid status')
                return redirect('procurement_submission_detail', submission_id=submission_id)
            
            current_stage = submission.current_stage
            stage_order = status_stage_map[new_status]
            next_stage = WorkflowStage.objects.filter(order=stage_order).first()
            
            if not next_stage:
                messages.error(request, 'Workflow stage not found')
                return redirect('procurement_submission_detail', submission_id=submission_id)
            
            # Update submission
            submission.status = new_status
            submission.current_stage = next_stage
            submission.save()
            
            # Record in workflow history
            WorkflowHistory.objects.create(
                submission=submission,
                from_stage=current_stage,
                to_stage=next_stage,
                action='status_update',
                comments=notes or f'{new_status} on Umucyo',
                action_by=user,
            )
            
            # Notify division of update
            if submission.submitted_by:
                Notification.objects.create(
                    user=submission.submitted_by,
                    title=f'Status Update: {submission.tracking_reference}',
                    message=f'Your procurement request has been updated to "{new_status}" on Umucyo.',
                    notification_type='submission_status',
                    priority='medium',
                    related_object_type='Submission',
                    related_object_id=str(submission.id),
                    action_url=f'/dashboard/hod/submissions/{submission.id}/',
                )
            
            messages.success(request, f'Status updated to {new_status} successfully!')
            
        except Submission.DoesNotExist:
            messages.error(request, 'Submission not found')
        except Exception as e:
            messages.error(request, str(e))
    
    return redirect('procurement_submission_detail', submission_id=submission_id)


@login_required
def procurement_record_award_view(request, submission_id):
    """
    Record awarded supplier details (name, amount, date).
    Automatically advances to Completed status and sends notifications to all users.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f'=== procurement_record_award_view called ===')
    logger.warning(f'Method: {request.method}, Submission ID: {submission_id}')
    
    user = request.user
    
    if user.role and user.role.name != 'Procurement Team':
        return redirect('dashboard')
    
    from apps.procurement.models import Submission
    from apps.workflows.models import WorkflowHistory, WorkflowStage
    from apps.notifications.models import Notification
    from apps.accounts.models import User
    from django.utils import timezone
    
    if request.method == 'POST':
        import logging
        logger = logging.getLogger(__name__)
        try:
            logger.warning(f'=== AWARD RECORDING STARTED ===')
            logger.warning(f'POST keys: {list(request.POST.keys())}')
            
            submission = Submission.objects.get(id=submission_id)
            logger.warning(f'Found submission: {submission.id}')
            supplier_name = request.POST.get('supplier_name', '').strip()
            award_amount = request.POST.get('award_amount', '').strip()
            award_date = request.POST.get('award_date', '').strip()
            
            logger.warning(f'Supplier: {supplier_name}'  )
            logger.warning(f'Amount: {award_amount}')
            logger.warning(f'Date: {award_date}')
            
            # Validate all required fields with specific messages
            if not supplier_name:
                messages.error(request, 'Supplier name is required')
                return redirect('procurement_submission_detail', submission_id=submission_id)
            
            if not award_amount:
                messages.error(request, 'Award amount is required')
                return redirect('procurement_submission_detail', submission_id=submission_id)
            
            if not award_date:
                messages.error(request, 'Award date is required')
                return redirect('procurement_submission_detail', submission_id=submission_id)
            
            # Validate award_amount is a valid number
            try:
                award_amount_float = float(award_amount)
                if award_amount_float <= 0:
                    messages.error(request, 'Award amount must be greater than 0')
                    return redirect('procurement_submission_detail', submission_id=submission_id)
            except ValueError:
                messages.error(request, 'Award amount must be a valid number')
                return redirect('procurement_submission_detail', submission_id=submission_id)
            
            # Store award details
            submission.award_details = {
                'supplier_name': supplier_name,
                'award_amount': award_amount_float,
                'award_date': award_date,
                'recorded_by': user.full_name,  # Fixed
                'recorded_at': timezone.now().isoformat(),
            }
            
            # Get current stage (Awarded - stage 18)
            current_stage = submission.current_stage
            completed_stage = None
            
            # Advance to Completed (stage 19)
            try:
                completed_stage = WorkflowStage.objects.filter(order=19).first()
                if completed_stage:
                    submission.status = 'Completed'
                    submission.current_stage = completed_stage
                else:
                    # Fallback to 'Completed' status if stage not found
                    submission.status = 'Completed'
            except Exception as stage_error:
                # If stage retrieval fails, still set status to Completed
                submission.status = 'Completed'
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Error retrieving Completed stage: {str(stage_error)}')
            
            submission.save()
            
            # Verify the save was successful by refreshing from database
            submission.refresh_from_db()
            
            # DEBUG: Log the saved data
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f'Award recorded - ID: {submission.id}, Status: {submission.status}, Award Details: {submission.award_details}')
            
            # Record in workflow history (only if completed_stage exists)
            if completed_stage:
                WorkflowHistory.objects.create(
                    submission=submission,
                    from_stage=current_stage,
                    to_stage=completed_stage,
                    action='award',
                    comments=f'Award recorded: {supplier_name} - RWF {award_amount}',
                    action_by=user,
                )
            else:
                # Create without to_stage if not found
                WorkflowHistory.objects.create(
                    submission=submission,
                    from_stage=current_stage,
                    action='award',
                    comments=f'Award recorded: {supplier_name} - RWF {award_amount}',
                    action_by=user,
                )
            
            # Notify CBM, Procurement Team, and HOD/DM of the specific division
            cbm_users = User.objects.filter(role__name='CBM')
            procurement_team_users = User.objects.filter(role__name='Procurement Team')
            hod_dm_user = submission.division.users.filter(role__name__in=['HOD', 'DM']).first()

            # Combine all recipients
            recipients = list(cbm_users) + list(procurement_team_users)
            if hod_dm_user:
                recipients.append(hod_dm_user)

            # Send notifications
            for recipient in recipients:
                Notification.objects.create(
                    user=recipient,
                    title='Contract Awarded',
                    message=f"The contract for submission {submission.tracking_reference} has been awarded to {supplier_name}.",
                    notification_type='submission_status',
                    priority='high',
                    action_url=f"/dashboard/procurement/submissions/{submission.id}/",
                    related_object_type='Submission',
                    related_object_id=str(submission.id),
                )
            
            messages.success(request, f'Award recorded and procurement marked as complete! Notifications sent to all users.')
            
        except Submission.DoesNotExist:
            messages.error(request, 'Submission not found')
        except ValueError as ve:
            messages.error(request, 'Invalid amount format')
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'ValueError in award recording: {str(ve)}')
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error in award recording: {str(e)}, Type: {type(e).__name__}')
            import traceback
            logger.error(f'Traceback: {traceback.format_exc()}')
            messages.error(request, f'Error recording award: {str(e)}')
    
    return redirect('procurement_submission_detail', submission_id=submission_id)


@login_required
def procurement_add_comment_view(request, submission_id):
    """
    Add internal comments or notes to submission.
    """
    user = request.user
    
    if user.role and user.role.name != 'Procurement Team':
        return redirect('dashboard')
    
    from apps.procurement.models import Submission, Comment
    
    if request.method == 'POST':
        try:
            submission = Submission.objects.get(id=submission_id)
            content = request.POST.get('comment', '').strip()
            
            if not content:
                messages.error(request, 'Comment cannot be empty')
                return redirect('procurement_submission_detail', submission_id=submission_id)
            
            Comment.objects.create(
                submission=submission,
                author=user,
                content=content,
                comment_type='internal',
            )
            
            messages.success(request, 'Comment added successfully!')
            
        except Submission.DoesNotExist:
            messages.error(request, 'Submission not found')
        except Exception as e:
            messages.error(request, str(e))
    
    return redirect('procurement_submission_detail', submission_id=submission_id)


@login_required
def procurement_approve_draft_view(request, submission_id):
    """
    Procurement Team approves the procurement draft.
    Moves submission from "Review of Procurement Draft" (stage 3) to "Submit Compiled Document" (stage 4).
    """
    user = request.user

    if user.role and user.role.name != 'Procurement Team':
        return redirect('dashboard')

    from apps.procurement.models import Submission
    from apps.workflows.models import WorkflowHistory, WorkflowStage
    from apps.notifications.models import Notification

    if request.method == 'POST':
        try:
            submission = Submission.objects.get(id=submission_id)
            notes = request.POST.get('notes', '')

            # Verify submission is in the correct status for review
            if submission.status not in ['HOD/DM Submit', 'Review of Procurement Draft']:
                messages.error(request, 'This submission cannot be approved at this stage')
                return redirect('procurement_submission_detail', submission_id=submission_id)

            # Get workflow stages
            current_stage = submission.current_stage
            compiled_doc_stage = WorkflowStage.objects.filter(order=4).first()  # Submit Compiled Document

            # Update submission to move to Submit Compiled Document stage
            submission.status = 'Submit Compiled Document'
            if compiled_doc_stage:
                submission.current_stage = compiled_doc_stage
            submission.save()

            # Record in workflow history
            WorkflowHistory.objects.create(
                submission=submission,
                from_stage=current_stage,
                to_stage=compiled_doc_stage,
                action='approve',
                comments=notes or 'Draft reviewed — ready for compiled document submission to CBM',
                action_by=user,
            )

            messages.success(request, f'Draft approved! Submission moved to Submit Compiled Document.')

        except Submission.DoesNotExist:
            messages.error(request, 'Submission not found')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

    return redirect('procurement_submission_detail', submission_id=submission_id)


@login_required
def procurement_submit_compiled_document_view(request, submission_id):
    """
    Procurement Team submits the compiled document.
    Auto-advances from "Submit Compiled Document" (stage 4) through "CBM Review" (stage 5) 
    directly to "Publish Plan" (stage 6), sending notification to CBM for information only.
    """
    user = request.user

    if user.role and user.role.name != 'Procurement Team':
        return redirect('dashboard')

    from apps.procurement.models import Submission
    from apps.workflows.models import WorkflowHistory, WorkflowStage
    from apps.notifications.models import Notification
    from apps.accounts.models import User as PtsUser

    if request.method == 'POST':
        try:
            submission = Submission.objects.get(id=submission_id)
            notes = request.POST.get('notes', '')

            if submission.status != 'Submit Compiled Document':
                messages.error(request, 'This submission is not in Submit Compiled Document stage')
                return redirect('procurement_submission_detail', submission_id=submission_id)

            current_stage = submission.current_stage
            cbm_review_stage = WorkflowStage.objects.filter(order=5).first()  # CBM Review
            publish_plan_stage = WorkflowStage.objects.filter(order=6).first()  # Publish Plan

            # Auto-advance through CBM Review to Publish Plan
            submission.status = 'Publish Plan'
            if publish_plan_stage:
                submission.current_stage = publish_plan_stage
            submission.save()

            # Record CBM Review step in workflow history (auto-completed)
            WorkflowHistory.objects.create(
                submission=submission,
                from_stage=current_stage,
                to_stage=cbm_review_stage,
                action='approve',
                comments=notes or 'Compiled document submitted - CBM Review (auto-completed)',
                action_by=user,
            )

            # Record Publish Plan advancement in workflow history
            WorkflowHistory.objects.create(
                submission=submission,
                from_stage=cbm_review_stage,
                to_stage=publish_plan_stage,
                action='auto_advance',
                comments='Auto-advanced to Publish Plan after CBM notification',
                action_by=user,
            )

            # Notify CBM (informational only - no action required)
            cbm_users = PtsUser.objects.filter(role__name='CBM', is_active=True)
            for cbm_user in cbm_users:
                Notification.objects.create(
                    user=cbm_user,
                    title=f'📋 Compiled Document Submitted: {submission.tracking_reference}',
                    message=f'Procurement Team has submitted the compiled document for {submission.item_name}. The workflow has automatically advanced to Publish Plan.',
                    notification_type='submission_status',
                    priority='medium',
                    related_object_type='Submission',
                    related_object_id=str(submission.id),
                    action_url=f'/dashboard/cbm/submissions/{submission.id}/',
                )

            # Notify Procurement Team that it's ready for next stage
            procurement_users = PtsUser.objects.filter(role__name='Procurement Team', is_active=True)
            for proc_user in procurement_users:
                if proc_user.id != user.id:  # Don't notify the user who just submitted
                    Notification.objects.create(
                        user=proc_user,
                        title=f'Ready for Publish Plan: {submission.tracking_reference}',
                        message=f'Submission {submission.tracking_reference} is ready for publishing the procurement plan.',
                        notification_type='submission_status',
                        priority='high',
                        related_object_type='Submission',
                        related_object_id=str(submission.id),
                        action_url=f'/dashboard/procurement/submissions/{submission.id}/',
                    )

            messages.success(request, 'Compiled document submitted! CBM has been notified and submission advanced to Publish Plan.')

        except Submission.DoesNotExist:
            messages.error(request, 'Submission not found')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

    return redirect('procurement_submission_detail', submission_id=submission_id)


@login_required
def procurement_return_draft_view(request, submission_id):
    """
    Procurement Team returns submission for clarification.
    Moves submission back one stage and sets status to Returned.
    """
    user = request.user
    
    if user.role and user.role.name != 'Procurement Team':
        return redirect('dashboard')
    
    from apps.procurement.models import Submission
    from apps.workflows.models import WorkflowHistory, WorkflowStage
    from apps.notifications.models import Notification
    from django.contrib import messages
    
    if request.method == 'POST':
        try:
            submission = Submission.objects.get(id=submission_id)
            clarification_request = request.POST.get('clarification_request', '')
            
            current_stage = submission.current_stage
            
            if not current_stage:
                messages.error(request, 'Current stage not set')
                return redirect('procurement_submission_detail', submission_id=submission_id)
            
            # Get the previous stage (order - 1)
            previous_stage = WorkflowStage.objects.filter(order=current_stage.order - 1).first()
            
            if not previous_stage:
                messages.error(request, 'Cannot return from the first stage')
                return redirect('procurement_submission_detail', submission_id=submission_id)
            
            # Update submission to previous stage with Returned status
            submission.current_stage = previous_stage
            submission.status = 'Returned'
            submission.save()
            
            # Record in workflow history
            WorkflowHistory.objects.create(
                submission=submission,
                from_stage=current_stage,
                to_stage=previous_stage,
                action='return',
                comments=clarification_request or 'Returned for clarification by Procurement Team',
                action_by=user,
            )
            
            # Notify HOD/DM to provide clarification
            if submission.submitted_by:
                Notification.objects.create(
                    user=submission.submitted_by,
                    title=f'Clarification Required: {submission.tracking_reference}',
                    message=f'Procurement Team has requested clarifications for {submission.item_name}. Please review the feedback and resubmit.',
                    notification_type='approval_required',
                    priority='high',
                    related_object_type='Submission',
                    related_object_id=str(submission.id),
                    action_url=f'/dashboard/hod/submissions/{submission.id}/',
                )
            
            messages.success(request, 'Submission returned for clarification!')
            
        except Submission.DoesNotExist:
            messages.error(request, 'Submission not found')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return redirect('procurement_submission_detail', submission_id=submission_id)


@login_required
def procurement_publish_plan_view(request, submission_id):
    """
    Procurement Team publishes the plan.
    Moves submission from Publish Plan (stage 6) to Plan Published,
    then redirects to the tender management page where individual
    tenders are created and tracked from stage 7 onward.
    """
    user = request.user
    
    if user.role and user.role.name != 'Procurement Team':
        return redirect('dashboard')
    
    from apps.procurement.models import Submission
    from apps.workflows.models import WorkflowHistory, WorkflowStage
    from apps.notifications.models import Notification
    
    if request.method == 'POST':
        try:
            submission = Submission.objects.get(id=submission_id)
            notes = request.POST.get('notes', '')
            approval_date_str = request.POST.get('approval_date', '')
            approval_date = None
            
            # Parse approval_date if provided
            if approval_date_str:
                try:
                    from datetime import datetime
                    approval_date = datetime.strptime(approval_date_str, '%Y-%m-%d').date()
                    
                    # Validate approval_date
                    from django.utils import timezone
                    today = timezone.now().date()
                    
                    # Check if date is in the future
                    if approval_date > today:
                        messages.error(request, f'Approval date cannot be in the future. Please enter a date on or before {today}.')
                        return redirect('procurement_submission_detail', submission_id=submission_id)
                    
                    # Check chronological order with previous submission stages
                    from apps.workflows.models import WorkflowHistory as WH
                    previous_history = WH.objects.filter(
                        submission=submission,
                        approval_date__isnull=False
                    ).order_by('-approval_date').first()
                    
                    if previous_history and previous_history.approval_date:
                        if approval_date < previous_history.approval_date:
                            messages.error(
                                request,
                                f'Approval date ({approval_date}) cannot be earlier than the previous stage date ({previous_history.approval_date}). '
                                f'Dates must follow chronological order.'
                            )
                            return redirect('procurement_submission_detail', submission_id=submission_id)
                except ValueError:
                    messages.warning(request, 'Invalid approval date format')
            
            # Verify at correct stage
            if submission.status != 'Publish Plan':
                messages.error(request, 'This submission is not in Publish Plan stage')
                return redirect('procurement_submission_detail', submission_id=submission_id)
            
            # Mark submission as Plan Published — individual tenders are tracked separately
            current_stage = submission.current_stage
            plan_published_stage = WorkflowStage.objects.filter(order=6).first()

            submission.status = 'Plan Published'
            submission.save()

            # Record in workflow history with approval_date
            WorkflowHistory.objects.create(
                submission=submission,
                from_stage=current_stage,
                to_stage=plan_published_stage,
                action='advance',
                comments=notes or 'Plan published — individual tenders will be tracked separately',
                action_by=user,
                approval_date=approval_date,
            )
            
            # Notify HOD/DM about plan publication
            from apps.accounts.models import User
            if submission.division:
                hod_users = User.objects.filter(
                    division=submission.division,
                    role__name='HOD/DM',
                    is_active=True
                )
                for hod_user in hod_users:
                    Notification.objects.create(
                        user=hod_user,
                        title=f'Plan Published: {submission.tracking_reference}',
                        message=f'The procurement plan for {submission.item_name} has been published. Individual tenders are now being tracked.',
                        notification_type='submission_status',
                        priority='high',
                        related_object_type='Submission',
                        related_object_id=str(submission.id),
                        action_url=f'/dashboard/hod/submissions/{submission.id}/',
                    )

            messages.success(request, 'Plan published! You can now create individual tenders.')

        except Submission.DoesNotExist:
            messages.error(request, 'Submission not found')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

    return redirect('submission_tender_list', submission_id=submission_id)
@login_required
def procurement_prepare_td_view(request, submission_id):
    """
    Procurement Team prepares/approves the tender document.
    At this step, the Umucyo tender_number, tender_title and procurement_method are captured
    and a Tender record is created. Auto-advances from Prepare Tender Document (stage 7)
    through CBM Review TD (stage 8) directly to Publication of TD (stage 9), sending 
    notification to CBM for information only.
    """
    user = request.user

    if user.role and user.role.name != 'Procurement Team':
        return redirect('dashboard')

    from apps.procurement.models import Submission, Tender
    from apps.workflows.models import WorkflowHistory, WorkflowStage
    from apps.notifications.models import Notification
    from apps.accounts.models import User

    if request.method == 'POST':
        try:
            submission = Submission.objects.get(id=submission_id)
            notes = request.POST.get('notes', '')
            approval_date_str = request.POST.get('approval_date', '')
            tender_number = request.POST.get('tender_number', '').strip()
            tender_title = request.POST.get('tender_title', '').strip()
            procurement_method = request.POST.get('procurement_method', '').strip()
            umucyo_link = request.POST.get('umucyo_link', '').strip()
            approval_date = None

            # Parse approval_date if provided
            if approval_date_str:
                try:
                    from datetime import datetime
                    approval_date = datetime.strptime(approval_date_str, '%Y-%m-%d').date()
                    
                    # Validate approval_date
                    from django.utils import timezone
                    today = timezone.now().date()
                    
                    # Check if date is in the future
                    if approval_date > today:
                        messages.error(request, f'Approval date cannot be in the future. Please enter a date on or before {today}.')
                        return redirect('procurement_submission_detail', submission_id=submission_id)
                    
                    # Check chronological order with previous submission stages
                    from apps.workflows.models import WorkflowHistory as WH
                    previous_history = WH.objects.filter(
                        submission=submission,
                        approval_date__isnull=False
                    ).order_by('-approval_date').first()
                    
                    if previous_history and previous_history.approval_date:
                        if approval_date < previous_history.approval_date:
                            messages.error(
                                request,
                                f'Approval date ({approval_date}) cannot be earlier than the previous stage date ({previous_history.approval_date}). '
                                f'Dates must follow chronological order.'
                            )
                            return redirect('procurement_submission_detail', submission_id=submission_id)
                except ValueError:
                    messages.warning(request, 'Invalid approval date format')

            # Verify at correct stage
            if submission.status != 'Prepare Tender Document':
                messages.error(request, 'This submission is not in Tender Document preparation stage')
                return redirect('procurement_submission_detail', submission_id=submission_id)

            # Validate required tender fields
            if not tender_number:
                messages.error(request, 'Tender number from Umucyo is required')
                return redirect('procurement_submission_detail', submission_id=submission_id)
            if not tender_title:
                messages.error(request, 'Tender title is required')
                return redirect('procurement_submission_detail', submission_id=submission_id)
            if not procurement_method:
                messages.error(request, 'Procurement method is required')
                return redirect('procurement_submission_detail', submission_id=submission_id)

            # Check if tender already exists - prevent duplicates
            existing_tender = Tender.objects.filter(tender_number=tender_number).first()
            if existing_tender:
                # Tender already exists - show error and prevent creation
                if existing_tender.submission and existing_tender.submission.id != submission.id:
                    messages.error(
                        request,
                        f'Tender {tender_number} already exists and is linked to another submission '
                        f'({existing_tender.submission.tracking_reference}). Please use a different tender number.'
                    )
                else:
                    messages.error(
                        request,
                        f'Tender {tender_number} already exists for this submission. Please use a different tender number or update the existing tender.'
                    )
                return redirect('procurement_submission_detail', submission_id=submission_id)

            # Create the Tender record (only if it doesn't exist)
            tender = Tender.objects.create(
                tender_number=tender_number,
                tender_title=tender_title,
                submission=submission,
                procurement_method=procurement_method,
                umucyo_link=umucyo_link or None,
                created_by=user,
            )

            # Also store procurement method on the submission for timeline calculations
            submission.procurement_method = procurement_method
            if umucyo_link:
                submission.umucyo_link = umucyo_link

            # Auto-advance through CBM Review TD to Publication of TD
            current_stage = submission.current_stage
            cbm_review_td_stage = WorkflowStage.objects.filter(order=8).first()  # CBM Review TD
            publication_td_stage = WorkflowStage.objects.filter(order=9).first()  # Publication of TD

            # Update both submission and tender status
            submission.status = 'Publication of TD'
            if publication_td_stage:
                submission.current_stage = publication_td_stage
            submission.save()

            # Update tender status to match (auto-advance through CBM Review TD)
            tender.status = 'Publication of TD'
            if publication_td_stage:
                tender.current_stage = publication_td_stage
            tender.save()

            # Set timeline deadline for publication stage
            submission.set_timeline_deadline(
                stage_name='Publication of TD',
                procurement_method=procurement_method
            )

            # Record submission workflow history - CBM Review TD step (auto-completed)
            WorkflowHistory.objects.create(
                submission=submission,
                from_stage=current_stage,
                to_stage=cbm_review_td_stage,
                action='advance',
                comments=notes or f'Tender Document prepared (Ref: {tender_number}) - CBM Review TD (auto-completed)',
                action_by=user,
                approval_date=approval_date,
            )

            # Record submission workflow history - Publication of TD advancement
            WorkflowHistory.objects.create(
                submission=submission,
                from_stage=cbm_review_td_stage,
                to_stage=publication_td_stage,
                action='auto_advance',
                comments='Auto-advanced to Publication of TD after CBM notification',
                action_by=user,
            )

            # Record tender history as well
            from apps.procurement.models import TenderHistory
            
            # Record Prepare TD → CBM Review TD (auto-completed)
            TenderHistory.objects.create(
                tender=tender,
                from_status='Prepare Tender Document',
                to_status='CBM Review TD',
                action='advance',
                comments=notes or f'Tender Document prepared - CBM Review TD (auto-completed)',
                action_by=user,
                approval_date=approval_date,
            )
            
            # Record CBM Review TD → Publication of TD (auto-advanced)
            TenderHistory.objects.create(
                tender=tender,
                from_status='CBM Review TD',
                to_status='Publication of TD',
                action='auto_advance',
                comments='Auto-advanced to Publication of TD after CBM notification',
                action_by=user,
            )

            # Notify CBM (informational only - no action required)
            cbm_users = User.objects.filter(role__name='CBM', is_active=True)
            for cbm_user in cbm_users:
                Notification.objects.create(
                    user=cbm_user,
                    title=f'📄 Tender Document Prepared: {submission.tracking_reference}',
                    message=f'Tender Document for {submission.item_name} (Tender: {tender_number}) has been prepared. The workflow has automatically advanced to Publication of TD.',
                    notification_type='submission_status',
                    priority='medium',
                    related_object_type='Submission',
                    related_object_id=str(submission.id),
                    action_url=f'/dashboard/cbm/submissions/{submission.id}/',
                )

            # Notify HOD/DM about TD preparation and readiness for publication
            if submission.division:
                hod_users = User.objects.filter(
                    division=submission.division,
                    role__name='HOD/DM',
                    is_active=True
                )
                for hod_user in hod_users:
                    Notification.objects.create(
                        user=hod_user,
                        title=f'Tender Document Ready for Publication: {submission.tracking_reference}',
                        message=f'Tender Document for {submission.item_name} has been prepared and is ready for publication.',
                        notification_type='submission_status',
                        priority='high',
                        related_object_type='Submission',
                        related_object_id=str(submission.id),
                        action_url=f'/dashboard/hod/submissions/{submission.id}/',
                    )

            # Notify other Procurement Team members
            procurement_users = User.objects.filter(role__name='Procurement Team', is_active=True)
            for proc_user in procurement_users:
                if proc_user.id != user.id:  # Don't notify the user who just submitted
                    Notification.objects.create(
                        user=proc_user,
                        title=f'Ready for TD Publication: {submission.tracking_reference}',
                        message=f'Tender {tender_number} is ready for publication in Umucyo.',
                        notification_type='submission_status',
                        priority='high',
                        related_object_type='Submission',
                        related_object_id=str(submission.id),
                        action_url=f'/dashboard/procurement/submissions/{submission.id}/',
                    )

            messages.success(request, f'Tender {tender_number} created! CBM has been notified and tender is ready for publication.')

        except Submission.DoesNotExist:
            messages.error(request, 'Submission not found')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

    return redirect('procurement_submission_detail', submission_id=submission_id)


@login_required
def procurement_publish_td_view(request, submission_id):
    """
    Procurement Team publishes the tender document.
    Moves submission from Publication of TD (stage 9) to Opening (stage 10).
    """
    user = request.user
    
    if user.role and user.role.name != 'Procurement Team':
        return redirect('dashboard')
    
    from apps.procurement.models import Submission
    from apps.workflows.models import WorkflowHistory, WorkflowStage
    from apps.notifications.models import Notification
    
    if request.method == 'POST':
        try:
            submission = Submission.objects.get(id=submission_id)
            notes = request.POST.get('notes', '')
            approval_date_str = request.POST.get('approval_date', '')
            approval_date = None
            
            # Parse approval_date if provided
            if approval_date_str:
                try:
                    from datetime import datetime
                    approval_date = datetime.strptime(approval_date_str, '%Y-%m-%d').date()
                    
                    # Validate approval_date
                    from django.utils import timezone
                    today = timezone.now().date()
                    
                    # Check if date is in the future
                    if approval_date > today:
                        messages.error(request, f'Approval date cannot be in the future. Please enter a date on or before {today}.')
                        return redirect('procurement_submission_detail', submission_id=submission_id)
                    
                    # Check chronological order with previous submission stages
                    from apps.workflows.models import WorkflowHistory as WH
                    previous_history = WH.objects.filter(
                        submission=submission,
                        approval_date__isnull=False
                    ).order_by('-approval_date').first()
                    
                    if previous_history and previous_history.approval_date:
                        if approval_date < previous_history.approval_date:
                            messages.error(
                                request,
                                f'Approval date ({approval_date}) cannot be earlier than the previous stage date ({previous_history.approval_date}). '
                                f'Dates must follow chronological order.'
                            )
                            return redirect('procurement_submission_detail', submission_id=submission_id)
                except ValueError:
                    messages.warning(request, 'Invalid approval date format')
            
            # Verify at correct stage
            if submission.status != 'Publication of TD':
                messages.error(request, 'This submission is not in Publication of TD stage')
                return redirect('procurement_submission_detail', submission_id=submission_id)
            
            # Move to Opening (stage 10)
            current_stage = submission.current_stage
            next_stage = WorkflowStage.objects.filter(order=10).first()
            
            submission.status = 'Opening'
            if next_stage:
                submission.current_stage = next_stage
            submission.save()
            
            # Set Bid Validity timeline (120 days from bid opening)
            submission.set_timeline_deadline(
                stage_name='Bid Validity Period',
                procurement_method=None
            )
            
            # Record in workflow history with approval_date
            WorkflowHistory.objects.create(
                submission=submission,
                from_stage=current_stage,
                to_stage=next_stage,
                action='advance',
                comments=notes or 'Tender Document published - Opening phase started',
                action_by=user,
                approval_date=approval_date,
            )
            
            # Notify HOD/DM about TD publication and opening start
            from apps.accounts.models import User
            if submission.division:
                hod_users = User.objects.filter(
                    division=submission.division,
                    role__name='HOD/DM',
                    is_active=True
                )
                for hod_user in hod_users:
                    Notification.objects.create(
                        user=hod_user,
                        title=f'📢 Opening Phase Started: {submission.tracking_reference}',
                        message=f'Tender Document for {submission.item_name} has been published. Opening phase is now active.',
                        notification_type='submission_status',
                        priority='high',
                        related_object_type='Submission',
                        related_object_id=str(submission.id),
                        action_url=f'/dashboard/hod/submissions/{submission.id}/',
                    )
            
            messages.success(request, 'Tender Document published! Opening phase started.')
            
        except Submission.DoesNotExist:
            messages.error(request, 'Submission not found')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return redirect('procurement_submission_detail', submission_id=submission_id)


@login_required
def procurement_notify_bidders_view(request, submission_id):
    """
    Procurement Team completes evaluation.
    Auto-advances from Evaluation (stage 11) through CBM Approval (stage 12) 
    directly to Notify Bidders (stage 13), sending notification to CBM for information only.
    """
    user = request.user
    
    if user.role and user.role.name != 'Procurement Team':
        return redirect('dashboard')
    
    from apps.procurement.models import Submission
    from apps.workflows.models import WorkflowHistory, WorkflowStage
    from apps.notifications.models import Notification
    from apps.accounts.models import User
    
    if request.method == 'POST':
        try:
            submission = Submission.objects.get(id=submission_id)
            notes = request.POST.get('notes', '')
            approval_date_str = request.POST.get('approval_date', '')
            approval_date = None
            
            # Parse approval_date if provided
            if approval_date_str:
                try:
                    from datetime import datetime
                    approval_date = datetime.strptime(approval_date_str, '%Y-%m-%d').date()
                    
                    # Validate approval_date
                    from django.utils import timezone
                    today = timezone.now().date()
                    
                    # Check if date is in the future
                    if approval_date > today:
                        messages.error(request, f'Approval date cannot be in the future. Please enter a date on or before {today}.')
                        return redirect('procurement_submission_detail', submission_id=submission_id)
                    
                    # Check chronological order with previous submission stages
                    from apps.workflows.models import WorkflowHistory as WH
                    previous_history = WH.objects.filter(
                        submission=submission,
                        approval_date__isnull=False
                    ).order_by('-approval_date').first()
                    
                    if previous_history and previous_history.approval_date:
                        if approval_date < previous_history.approval_date:
                            messages.error(
                                request,
                                f'Approval date ({approval_date}) cannot be earlier than the previous stage date ({previous_history.approval_date}). '
                                f'Dates must follow chronological order.'
                            )
                            return redirect('procurement_submission_detail', submission_id=submission_id)
                except ValueError:
                    messages.warning(request, 'Invalid approval date format')
            
            # Verify at correct stage
            if submission.status != 'Evaluation':
                messages.error(request, 'This submission is not in Evaluation stage')
                return redirect('procurement_submission_detail', submission_id=submission_id)
            
            # Auto-advance through CBM Approval to Notify Bidders
            current_stage = submission.current_stage
            cbm_approval_stage = WorkflowStage.objects.filter(order=12).first()  # CBM Approval
            notify_bidders_stage = WorkflowStage.objects.filter(order=13).first()  # Notify Bidders
            
            submission.status = 'Notify Bidders'
            if notify_bidders_stage:
                submission.current_stage = notify_bidders_stage
            
            # Set Evaluation timeline (21 days) if not already set
            if not submission.current_stage_deadline:
                submission.set_timeline_deadline(
                    stage_name='Evaluation',
                    procurement_method=None
                )
            
            submission.save()
            
            # Record CBM Approval step in workflow history (auto-completed)
            WorkflowHistory.objects.create(
                submission=submission,
                from_stage=current_stage,
                to_stage=cbm_approval_stage,
                action='advance',
                comments=notes or 'Evaluation results complete - CBM Approval (auto-completed)',
                action_by=user,
                approval_date=approval_date,
            )
            
            # Record Notify Bidders advancement in workflow history
            WorkflowHistory.objects.create(
                submission=submission,
                from_stage=cbm_approval_stage,
                to_stage=notify_bidders_stage,
                action='auto_advance',
                comments='Auto-advanced to Notify Bidders after CBM notification',
                action_by=user,
            )
            
            # Notify CBM (informational only - no action required)
            cbm_users = User.objects.filter(
                role__name='CBM',
                is_active=True
            )
            for cbm_user in cbm_users:
                Notification.objects.create(
                    user=cbm_user,
                    title=f'✅ Evaluation Complete: {submission.tracking_reference}',
                    message=f'Evaluation results for {submission.item_name} have been completed. The workflow has automatically advanced to Notify Bidders.',
                    notification_type='submission_status',
                    priority='medium',
                    related_object_type='Submission',
                    related_object_id=str(submission.id),
                    action_url=f'/dashboard/cbm/submissions/{submission.id}/',
                )
            
            # Notify HOD/DM about evaluation completion
            if submission.division:
                hod_users = User.objects.filter(
                    division=submission.division,
                    role__name='HOD/DM',
                    is_active=True
                )
                for hod_user in hod_users:
                    Notification.objects.create(
                        user=hod_user,
                        title=f'Evaluation Complete: {submission.tracking_reference}',
                        message=f'Evaluation for {submission.item_name} has been completed. Bidders will be notified of results.',
                        notification_type='submission_status',
                        priority='high',
                        related_object_type='Submission',
                        related_object_id=str(submission.id),
                        action_url=f'/dashboard/hod/submissions/{submission.id}/',
                    )
            
            # Notify other Procurement Team members
            procurement_users = User.objects.filter(role__name='Procurement Team', is_active=True)
            for proc_user in procurement_users:
                if proc_user.id != user.id:  # Don't notify the user who just submitted
                    Notification.objects.create(
                        user=proc_user,
                        title=f'Ready to Notify Bidders: {submission.tracking_reference}',
                        message=f'Evaluation is complete. Proceed with notifying bidders for {submission.item_name}.',
                        notification_type='submission_status',
                        priority='high',
                        related_object_type='Submission',
                        related_object_id=str(submission.id),
                        action_url=f'/dashboard/procurement/submissions/{submission.id}/',
                    )
            
            messages.success(request, 'Evaluation complete! CBM has been notified and submission advanced to Notify Bidders.')
            
        except Submission.DoesNotExist:
            messages.error(request, 'Submission not found')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return redirect('procurement_submission_detail', submission_id=submission_id)


@login_required
def procurement_advance_stage_view(request, submission_id):
    """
    Generic view for Procurement Team to advance submission through remaining stages.
    Handles: Opening → Evaluation → Notify Bidders → Contract Negotiation → Contract Drafting → Legal Review → Award → Completed
    """
    user = request.user
    
    if user.role and user.role.name != 'Procurement Team':
        return redirect('dashboard')
    
    from apps.procurement.models import Submission
    from apps.workflows.models import WorkflowHistory, WorkflowStage
    from apps.notifications.models import Notification
    from apps.accounts.models import User
    
    if request.method == 'POST':
        try:
            submission = Submission.objects.get(id=submission_id)
            notes = request.POST.get('notes', '')
            approval_date_str = request.POST.get('approval_date', '')
            approval_date = None
            
            # Parse approval_date if provided
            if approval_date_str:
                try:
                    from datetime import datetime
                    approval_date = datetime.strptime(approval_date_str, '%Y-%m-%d').date()
                    
                    # Validate approval_date
                    from django.utils import timezone
                    today = timezone.now().date()
                    
                    # Check if date is in the future
                    if approval_date > today:
                        messages.error(request, f'Approval date cannot be in the future. Please enter a date on or before {today}.')
                        return redirect('procurement_submission_detail', submission_id=submission_id)
                    
                    # Check chronological order with previous submission stages
                    from apps.workflows.models import WorkflowHistory as WH
                    previous_history = WH.objects.filter(
                        submission=submission,
                        approval_date__isnull=False
                    ).order_by('-approval_date').first()
                    
                    if previous_history and previous_history.approval_date:
                        if approval_date < previous_history.approval_date:
                            messages.error(
                                request,
                                f'Approval date ({approval_date}) cannot be earlier than the previous stage date ({previous_history.approval_date}). '
                                f'Dates must follow chronological order.'
                            )
                            return redirect('procurement_submission_detail', submission_id=submission_id)
                except ValueError:
                    messages.warning(request, 'Invalid approval date format')
            
            current_stage = submission.current_stage
            if not current_stage:
                messages.error(request, 'Current stage not set')
                return redirect('procurement_submission_detail', submission_id=submission_id)
            
            # Define stage progression (stage 11→ 12 is CBM Approval, handled by procurement_notify_bidders_view)
            stage_progression = {
                10: (11, 'Evaluation'),                  # Opening(10) → Evaluation(11)
                12: (13, 'Notify Bidders'),             # CBM Approval(12) → Notify Bidders(13)
                13: (14, 'Contract Negotiation'),       # Notify Bidders(13) → Contract Negotiation(14)
                14: (15, 'Contract Drafting'),          # Contract Negotiation(14) → Contract Drafting(15)
                15: (16, 'Legal Review'),               # Contract Drafting(15) → Legal Review(16)
                16: (17, 'Supplier Approval'),          # Legal Review(16) → Supplier Approval(17)
                17: (18, 'MINIJUST Legal Review'),      # Supplier Approval(17) → MINIJUST Legal Review(18)
                18: (19, 'Awarded'),                    # MINIJUST Legal Review(18) → Awarded(19)
                19: (20, 'Completed'),                  # Awarded(19) → Completed(20)
            }
            
            current_order = current_stage.order
            
            if current_order not in stage_progression:
                messages.error(request, f'Cannot advance from {submission.status}')
                return redirect('procurement_submission_detail', submission_id=submission_id)
            
            next_order, next_status = stage_progression[current_order]
            next_stage = WorkflowStage.objects.filter(order=next_order).first()
            
            submission.status = next_status
            if next_stage:
                submission.current_stage = next_stage
            
            # Set timeline based on stage transition
            if next_status == 'Notify Bidders':
                # Set Notification timeline (7 days)
                submission.set_timeline_deadline(
                    stage_name='Notification',
                    procurement_method=None
                )
            elif next_status in ['Contract Drafting', 'Awarded']:
                # These stages require tender type for contract signature timeline
                # For now, we'll check if procurement method is set
                # If the submission has procurement_method set, we can infer tender type
                tender_type = None
                if submission.procurement_method:
                    # Transactions with international methods get International timeline
                    international_methods = ['International Competitive', 'International Restricted']
                    if submission.procurement_method in international_methods:
                        tender_type = 'International'
                    else:
                        tender_type = 'National'
                
                if tender_type:
                    submission.set_timeline_deadline(
                        stage_name='Contract Signature',
                        procurement_method=None,
                        tender_type=tender_type
                    )
            
            submission.save()
            
            # Record in workflow history with approval_date
            WorkflowHistory.objects.create(
                submission=submission,
                from_stage=current_stage,
                to_stage=next_stage,
                action='advance',
                comments=notes or f'Advanced to {next_status}',
                action_by=user,
                approval_date=approval_date,
            )
            
            # Notify CBM/Legal if moving to Legal Review
            if next_status == 'Legal Review':
                admin_users = User.objects.filter(role__name__in=['CBM', 'Admin'], is_active=True)
                for admin_user in admin_users:
                    Notification.objects.create(
                        user=admin_user,
                        title=f'Legal Review Required: {submission.tracking_reference}',
                        message=f'Contract for {submission.item_name} is ready for legal review.',
                        notification_type='submission_status',
                        priority='high',
                        related_object_type='Submission',
                        related_object_id=str(submission.id),
                        action_url=f'/dashboard/cbm/submissions/{submission.id}/',
                    )
            
            # Notify HOD/DM about key milestone updates
            if submission.division:
                hod_users = User.objects.filter(
                    division=submission.division,
                    role__name='HOD/DM',
                    is_active=True
                )
                
                notification_messages = {
                    'Evaluation': {
                        'title': f'🔍 Evaluation Phase Started: {submission.tracking_reference}',
                        'message': f'Bid evaluation for {submission.item_name} has started.',
                        'priority': 'high'
                    },
                    'Notify Bidders': {
                        'title': f'📢 Bidders Notification: {submission.tracking_reference}',
                        'message': f'Bidders are being notified about the results for {submission.item_name}.',
                        'priority': 'high'
                    },
                    'Contract Negotiation': {
                        'title': f'🤝 Contract Negotiation: {submission.tracking_reference}',
                        'message': f'Contract negotiation is underway for {submission.item_name}.',
                        'priority': 'medium'
                    },
                    'Contract Drafting': {
                        'title': f'📝 Contract Being Drafted: {submission.tracking_reference}',
                        'message': f'Contract for {submission.item_name} is being drafted.',
                        'priority': 'medium'
                    },
                    'MINIJUST Legal Review': {
                        'title': f'⚖️ MINIJUST Legal Review: {submission.tracking_reference}',
                        'message': f'Contract for {submission.item_name} is under MINIJUST legal review.',
                        'priority': 'high'
                    },
                    'Awarded': {
                        'title': f'🏆 Contract Awarded: {submission.tracking_reference}',
                        'message': f'Contract for {submission.item_name} has been awarded!',
                        'priority': 'urgent'
                    },
                }
                
                if next_status in notification_messages:
                    msg_config = notification_messages[next_status]
                    for hod_user in hod_users:
                        Notification.objects.create(
                            user=hod_user,
                            title=msg_config['title'],
                            message=msg_config['message'],
                            notification_type='submission_status',
                            priority=msg_config['priority'],
                            related_object_type='Submission',
                            related_object_id=str(submission.id),
                            action_url=f'/dashboard/hod/submissions/{submission.id}/',
                        )
            
            messages.success(request, f'Submission advanced to {next_status}!')
            
        except Submission.DoesNotExist:
            messages.error(request, 'Submission not found')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return redirect('procurement_submission_detail', submission_id=submission_id)
