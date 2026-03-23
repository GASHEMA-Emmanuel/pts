"""
Celery tasks for notification processing.
"""
from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_notification_email(self, notification_id):
    """
    Send email for a notification with HTML template.
    """
    from .models import Notification, EmailLog
    from .email_templates import generate_generic_notification_email
    
    try:
        notification = Notification.objects.select_related('user').get(id=notification_id)
        user = notification.user
        
        if not user.email_notifications or not user.email:
            return {'status': 'skipped', 'reason': 'Email notifications disabled'}
        
        # Check user preferences
        preferences = getattr(user, 'notification_preferences', None)
        if preferences:
            type_pref_map = {
                'procurement_call': preferences.email_procurement_calls,
                'deadline_reminder': preferences.email_deadline_reminders,
                'submission_status': preferences.email_status_updates,
                'approval_required': preferences.email_approval_requests,
                'escalation': preferences.email_escalations,
            }
            if not type_pref_map.get(notification.notification_type, True):
                return {'status': 'skipped', 'reason': 'User disabled this notification type'}
        
        # Create email log
        email_log = EmailLog.objects.create(
            recipient_email=user.email,
            recipient_user=user,
            subject=notification.title,
            body=notification.message,
            notification=notification
        )
        
        # Generate HTML email
        html_message = generate_generic_notification_email(
            title=notification.title,
            message=notification.message,
            action_url=notification.action_url if notification.action_url else '/dashboard/',
            user=user,
            notification_type=notification.notification_type
        )
        
        # Send email
        try:
            send_mail(
                subject=f"[PTS] {notification.title}",
                message=notification.message,  # Plain text fallback
                html_message=html_message,      # HTML version
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False
            )
            
            email_log.status = 'sent'
            email_log.sent_at = timezone.now()
            email_log.save()
            
            notification.email_sent = True
            notification.email_sent_at = timezone.now()
            notification.save()
            
            return {'status': 'sent', 'email': user.email}
            
        except Exception as e:
            email_log.status = 'failed'
            email_log.error_message = str(e)
            email_log.save()
            raise
            
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found")
        return {'status': 'error', 'reason': 'Notification not found'}
    except Exception as e:
        logger.error(f"Error sending notification email: {e}")
        self.retry(countdown=60 * (2 ** self.request.retries))


@shared_task
def notify_procurement_call(call_id):
    """
    Send notifications to all HODs and DMs about a new procurement call.
    """
    from apps.procurement.models import ProcurementCall
    from apps.accounts.models import User
    from .models import Notification
    
    try:
        call = ProcurementCall.objects.get(id=call_id)
        
        # Get all HODs and DMs
        recipients = User.objects.filter(
            role__name__in=['HOD/DM'],
            is_active=True
        )
        
        notifications = []
        for user in recipients:
            notification = Notification.objects.create(
                user=user,
                title=f"New Procurement Call: {call.title}",
                message=f"A new procurement call has been issued. Reference: {call.reference_number}. Please submit your division's requirements by {call.end_date.strftime('%B %d, %Y')}.",
                notification_type='procurement_call',
                priority='high',
                related_object_type='ProcurementCall',
                related_object_id=str(call.id),
                action_url=f"/procurement/calls/{call.id}"
            )
            notifications.append(notification)
            
            # Queue email
            send_notification_email.delay(str(notification.id))
        
        return {'status': 'success', 'notifications_sent': len(notifications)}
        
    except ProcurementCall.DoesNotExist:
        logger.error(f"Procurement call {call_id} not found")
        return {'status': 'error', 'reason': 'Call not found'}


@shared_task
def notify_submission_status(submission_id, new_status):
    """
    Notify relevant users about a submission status change.
    """
    from apps.procurement.models import Submission
    from .models import Notification
    
    try:
        submission = Submission.objects.select_related(
            'division', 'created_by', 'submitted_by'
        ).get(id=submission_id)
        
        status_messages = {
            'submitted': f"Your submission {submission.tracking_reference} has been submitted for review.",
            'approved': f"Your submission {submission.tracking_reference} has been approved!",
            'rejected': f"Your submission {submission.tracking_reference} has been rejected. Please check comments for details.",
            'returned': f"Your submission {submission.tracking_reference} has been returned for clarification.",
            'published': f"Your submission {submission.tracking_reference} has been published to Umucyo.",
            'awarded': f"Contract for {submission.tracking_reference} has been awarded.",
            'completed': f"Procurement for {submission.tracking_reference} has been completed.",
        }
        
        message = status_messages.get(
            new_status,
            f"Status of {submission.tracking_reference} has been updated to {new_status}."
        )
        
        # Notify the submitter and creator
        recipients = set()
        if submission.submitted_by:
            recipients.add(submission.submitted_by)
        if submission.created_by:
            recipients.add(submission.created_by)
        
        for user in recipients:
            notification = Notification.objects.create(
                user=user,
                title=f"Submission Status Update",
                message=message,
                notification_type='submission_status',
                priority='medium',
                related_object_type='Submission',
                related_object_id=str(submission.id),
                action_url=f"/procurement/submissions/{submission.id}"
            )
            send_notification_email.delay(str(notification.id))
        
        return {'status': 'success', 'recipients': len(recipients)}
        
    except Submission.DoesNotExist:
        logger.error(f"Submission {submission_id} not found")
        return {'status': 'error', 'reason': 'Submission not found'}


@shared_task
def check_upcoming_deadlines():
    """
    Check for upcoming deadlines and send reminders.
    Runs daily at 8:00 AM.
    """
    from apps.procurement.models import ProcurementCall
    from apps.accounts.models import User
    from .models import Notification, NotificationPreference
    
    now = timezone.now()
    reminder_days = 3
    deadline = now + timedelta(days=reminder_days)
    
    # Check procurement call deadlines
    upcoming_calls = ProcurementCall.objects.filter(
        status='Active',
        end_date__lte=deadline,
        end_date__gt=now
    )
    
    notifications_sent = 0
    
    for call in upcoming_calls:
        days_left = (call.end_date - now).days
        
        # Notify HODs/DMs who haven't submitted yet
        from apps.divisions.models import Division
        divisions_submitted = call.submissions.values_list('division_id', flat=True)
        divisions_pending = Division.objects.exclude(id__in=divisions_submitted)
        
        for division in divisions_pending:
            users = User.objects.filter(
                division=division,
                role__name='HOD/DM',
                is_active=True
            )
            
            for user in users:
                notification = Notification.objects.create(
                    user=user,
                    title=f"Deadline Reminder: {call.reference_number}",
                    message=f"Only {days_left} days remaining to submit your division's procurement needs for {call.title}. Deadline: {call.end_date.strftime('%B %d, %Y')}.",
                    notification_type='deadline_reminder',
                    priority='high',
                    related_object_type='ProcurementCall',
                    related_object_id=str(call.id),
                    action_url=f"/procurement/calls/{call.id}"
                )
                send_notification_email.delay(str(notification.id))
                notifications_sent += 1
    
    return {'status': 'success', 'notifications_sent': notifications_sent}


@shared_task
def check_overdue_submissions():
    """
    Check for overdue submissions and send escalation notifications.
    Runs daily at 9:00 AM.
    """
    from apps.workflows.models import Deadline
    from apps.accounts.models import User
    from .models import Notification
    
    now = timezone.now()
    escalation_days = 7
    
    # Find overdue deadlines that haven't been escalated
    overdue = Deadline.objects.filter(
        deadline__lt=now,
        is_overdue=True,
        escalated=False
    ).select_related('submission', 'stage')
    
    notifications_sent = 0
    
    for deadline in overdue:
        days_overdue = (now - deadline.deadline).days
        
        if days_overdue >= escalation_days:
            # Escalate to CBM
            cbm_users = User.objects.filter(
                role__name='CBM',
                is_active=True
            )
            
            for user in cbm_users:
                notification = Notification.objects.create(
                    user=user,
                    title=f"Escalation: Overdue Submission",
                    message=f"Submission {deadline.submission.tracking_reference} is {days_overdue} days overdue at stage '{deadline.stage.name}'. Immediate attention required.",
                    notification_type='escalation',
                    priority='urgent',
                    related_object_type='Submission',
                    related_object_id=str(deadline.submission.id),
                    action_url=f"/procurement/submissions/{deadline.submission.id}"
                )
                send_notification_email.delay(str(notification.id))
                notifications_sent += 1
            
            deadline.escalated = True
            deadline.escalated_at = now
            deadline.save()
    
    return {'status': 'success', 'escalations': notifications_sent}


@shared_task
def send_daily_summary():
    """
    Send daily summary to CBM.
    Runs daily at 6:00 PM.
    """
    from apps.procurement.models import Submission, ProcurementCall
    from apps.accounts.models import User
    from .models import Notification
    
    now = timezone.now()
    today = now.date()
    
    # Get today's statistics
    new_submissions = Submission.objects.filter(
        created_at__date=today
    ).count()
    
    approved_today = Submission.objects.filter(
        status='Approved',
        updated_at__date=today
    ).count()
    
    active_calls = ProcurementCall.objects.filter(
        status='Active'
    ).count()
    
    pending_approvals = Submission.objects.filter(
        status__in=['Submitted', 'Under Review']
    ).count()
    
    # Build summary message
    message = f"""
Daily Procurement Summary - {today.strftime('%B %d, %Y')}

Today's Activity:
- New Submissions: {new_submissions}
- Approved: {approved_today}

Current Status:
- Active Procurement Calls: {active_calls}
- Pending Approvals: {pending_approvals}

Please log in to the PTS dashboard for detailed information.
    """
    
    # Send to all CBM users
    cbm_users = User.objects.filter(
        role__name='CBM',
        is_active=True
    )
    
    for user in cbm_users:
        notification = Notification.objects.create(
            user=user,
            title="Daily Procurement Summary",
            message=message.strip(),
            notification_type='system',
            priority='low',
            action_url="/dashboard"
        )
        send_notification_email.delay(str(notification.id))
    
    return {'status': 'success', 'recipients': cbm_users.count()}


@shared_task
def cleanup_old_notifications():
    """
    Delete notifications older than 90 days.
    Runs weekly on Sunday at 2:00 AM.
    """
    from .models import Notification
    
    cutoff = timezone.now() - timedelta(days=90)
    count = Notification.objects.filter(
        created_at__lt=cutoff,
        is_read=True
    ).delete()[0]
    
    return {'status': 'success', 'deleted': count}


@shared_task
def monitor_submission_timelines():
    """
    Check all active submissions and update their timeline status.
    Creates notifications for submissions approaching or past deadline.
    Runs every 6 hours.
    """
    from apps.procurement.models import Submission
    from .models import Notification
    
    try:
        # Get all submissions with active timelines (not completed, not rejected, not cancelled)
        active_statuses = [
            'HOD/DM Submit', 'Review of Procurement Draft', 'CBM Review',
            'Publish Plan', 'Prepare Tender Document', 'CBM Review TD',
            'Publication of TD', 'Bidding', 'Evaluation', 'CBM Approval',
            'Notify Bidders', 'Contract Negotiation', 'Contract Drafting',
            'Legal Review', 'Supplier Approval', 'MINIJUST Legal Review', 'Awarded'
        ]
        
        submissions = Submission.objects.filter(
            status__in=active_statuses,
            current_stage_deadline__isnull=False,
            is_deleted=False
        ).select_related('division', 'current_stage', 'submitted_by', 'call')
        
        flagged_count = 0
        approached_count = 0
        expired_count = 0
        
        for submission in submissions:
            old_status = submission.timeline_status
            submission.update_timeline_status()
            new_status = submission.timeline_status
            
            # Create notifications if status changed
            if old_status != new_status:
                if new_status == 'approaching':
                    approached_count += 1
                    # Notify CBM or relevant role
                    notification = Notification.objects.create(
                        user=submission.submitted_by or submission.division.head_of_department,
                        title=f"⏰ Approaching Deadline: {submission.tracking_reference}",
                        message=f"Submission '{submission.item_name}' is approaching deadline ({submission.timeline_days_remaining} days remaining). Current stage: {submission.current_stage.name if submission.current_stage else submission.status}",
                        notification_type='deadline_reminder',
                        priority='high',
                        action_url=f'/dashboard/submissions/{submission.id}/'
                    )
                    send_notification_email.delay(str(notification.id))
                    
                elif new_status == 'expired':
                    expired_count += 1
                    # Notify CBM urgently
                    notification = Notification.objects.create(
                        user=submission.submitted_by or submission.division.head_of_department,
                        title=f"🚨 Deadline Expired: {submission.tracking_reference}",
                        message=f"Submission '{submission.item_name}' deadline has passed! Stage: {submission.current_stage.name if submission.current_stage else submission.status}. Immediate action required!",
                        notification_type='escalation',
                        priority='critical',
                        action_url=f'/dashboard/submissions/{submission.id}/'
                    )
                    send_notification_email.delay(str(notification.id))
            
            flagged_count += 1
        
        logger.info(
            f"Timeline monitoring complete: {flagged_count} submissions checked, "
            f"{approached_count} approaching deadline, {expired_count} expired"
        )
        
        return {
            'status': 'success',
            'checked': flagged_count,
            'approaching': approached_count,
            'expired': expired_count,
        }
        
    except Exception as e:
        logger.error(f"Error monitoring submission timelines: {e}")
        return {'status': 'error', 'message': str(e)}

