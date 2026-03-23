"""
Celery tasks for alert generation and notification.
Runs scheduled jobs to check for deadline alerts, stalled submissions, and escalations.
"""
from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from datetime import timedelta
from apps.procurement.models import Submission
from apps.workflows.models import WorkflowHistory
from apps.alerts.models import Alert, AlertConfiguration, AlertHistory
from apps.accounts.models import User


@shared_task
def check_cbm_review_deadlines():
    """
    Check for submissions with approaching or missed CBM review deadlines.
    Runs daily to create deadline alerts.
    """
    config = AlertConfiguration.objects.filter(
        alert_type='deadline_approaching',
        is_enabled=True
    ).first()
    
    if not config:
        return {'status': 'skipped', 'reason': 'Configuration disabled'}
    
    today = timezone.now().date()
    threshold_date = today + timedelta(days=config.days_before_deadline)
    
    # Find submissions with approaching CBM review deadlines
    submissions = Submission.objects.filter(
        cbm_review_deadline__lte=threshold_date,
        cbm_review_deadline__gt=None,
        status__in=['HOD/DM Submit', 'Review of Procurement Draft', 'CBM Review', 'Prepare Tender Document', 'CBM Review TD']
    )
    
    created_count = 0
    
    for submission in submissions:
        # Check if alert already exists for this submission
        existing_alert = Alert.objects.filter(
            submission=submission,
            alert_type='deadline_approaching',
            status__in=['active', 'acknowledged']
        ).exists()
        
        if not existing_alert:
            # Determine severity
            if submission.cbm_review_deadline < today:
                severity = 'critical'
                title = f"URGENT: CBM Review Deadline Missed - {submission.tracking_reference}"
            elif submission.cbm_review_deadline == today:
                severity = 'critical'
                title = f"CBM Review Deadline Today - {submission.tracking_reference}"
            else:
                severity = 'warning'
                title = f"CBM Review Deadline Approaching - {submission.tracking_reference}"
            
            alert = Alert.objects.create(
                submission=submission,
                alert_type='deadline_approaching',
                title=title,
                description=f"CBM review for '{submission.item_name}' (Budget: {submission.estimated_budget}) is due on {submission.cbm_review_deadline}",
                severity=severity
            )
            
            # Log to history
            AlertHistory.objects.create(
                submission=submission,
                alert_type='deadline_approaching',
                title=title,
                severity=severity,
                triggered_reason=f"CBM review deadline: {submission.cbm_review_deadline}"
            )
            
            # Send notifications if configured
            if config.send_email:
                send_deadline_alert_email(submission, alert, config, 'cbm_review')
            
            created_count += 1
    
    return {
        'status': 'success',
        'alerts_created': created_count,
        'checked_count': submissions.count()
    }


@shared_task
def check_procurement_deadlines():
    """
    Check for submissions with approaching or missed procurement deadlines.
    Runs daily to create deadline alerts.
    """
    config = AlertConfiguration.objects.filter(
        alert_type='deadline_approaching',
        is_enabled=True
    ).first()
    
    if not config:
        return {'status': 'skipped', 'reason': 'Configuration disabled'}
    
    today = timezone.now().date()
    threshold_date = today + timedelta(days=config.days_before_deadline)
    
    # Find submissions with approaching procurement deadlines
    submissions = Submission.objects.filter(
        procurement_deadline__lte=threshold_date,
        procurement_deadline__gt=None,
        status__in=['Publish Plan', 'Prepare Tender Document', 'CBM Review TD', 'Publication of TD', 'Bidding', 'Evaluation', 'Notify Bidders']
    )
    
    created_count = 0
    
    for submission in submissions:
        # Check if alert already exists
        existing_alert = Alert.objects.filter(
            submission=submission,
            alert_type='deadline_approaching',
            status__in=['active', 'acknowledged']
        ).exists()
        
        if not existing_alert:
            # Determine severity
            if submission.procurement_deadline < today:
                severity = 'critical'
                title = f"URGENT: Procurement Deadline Missed - {submission.tracking_reference}"
            elif submission.procurement_deadline == today:
                severity = 'critical'
                title = f"Procurement Deadline Today - {submission.tracking_reference}"
            else:
                severity = 'warning'
                title = f"Procurement Deadline Approaching - {submission.tracking_reference}"
            
            alert = Alert.objects.create(
                submission=submission,
                alert_type='deadline_approaching',
                title=title,
                description=f"Procurement for '{submission.item_name}' is due on {submission.procurement_deadline}",
                severity=severity
            )
            
            # Log to history
            AlertHistory.objects.create(
                submission=submission,
                alert_type='deadline_approaching',
                title=title,
                severity=severity,
                triggered_reason=f"Procurement deadline: {submission.procurement_deadline}"
            )
            
            # Send notifications if configured
            if config.send_email:
                send_deadline_alert_email(submission, alert, config, 'procurement')
            
            created_count += 1
    
    return {
        'status': 'success',
        'alerts_created': created_count,
        'checked_count': submissions.count()
    }


@shared_task
def check_stalled_submissions():
    """
    Check for submissions stalled in a stage for too long.
    Runs daily to create stalled submission alerts.
    """
    config = AlertConfiguration.objects.filter(
        alert_type='stalled_submission',
        is_enabled=True
    ).first()
    
    if not config:
        return {'status': 'skipped', 'reason': 'Configuration disabled'}
    
    # Get all submissions with workflow history
    submissions = Submission.objects.filter(
        status__in=['HOD/DM Submit', 'Review of Procurement Draft', 'CBM Review', 'Prepare Tender Document', 'CBM Review TD', 'Publication of TD', 'Bidding', 'Evaluation', 'Notify Bidders', 'Contract Negotiation', 'Contract Drafting', 'Legal Review', 'MINIJUST Legal Review']
    )
    
    created_count = 0
    
    for submission in submissions:
        # Get the most recent workflow history entry
        latest_history = WorkflowHistory.objects.filter(
            submission=submission
        ).order_by('-created_at').first()
        
        if not latest_history:
            continue
        
        days_in_stage = (timezone.now() - latest_history.created_at).days
        
        if days_in_stage >= config.days_in_stage:
            # Check if alert already exists
            existing_alert = Alert.objects.filter(
                submission=submission,
                alert_type='stalled_submission',
                status__in=['active', 'acknowledged']
            ).exists()
            
            if not existing_alert:
                stage_name = latest_history.new_stage.name if latest_history.new_stage else 'Unknown'
                severity = 'critical' if days_in_stage >= 30 else 'warning'
                
                alert = Alert.objects.create(
                    submission=submission,
                    alert_type='stalled_submission',
                    title=f"Submission Stalled - {submission.tracking_reference}",
                    description=f"'{submission.item_name}' has been in '{stage_name}' stage for {days_in_stage} days",
                    severity=severity
                )
                
                # Log to history
                AlertHistory.objects.create(
                    submission=submission,
                    alert_type='stalled_submission',
                    title=f"Submission Stalled - {submission.tracking_reference}",
                    severity=severity,
                    triggered_reason=f"In '{stage_name}' stage for {days_in_stage} days"
                )
                
                # Send notifications if configured
                if config.send_email:
                    send_stalled_alert_email(submission, alert, config, stage_name, days_in_stage)
                
                created_count += 1
    
    return {
        'status': 'success',
        'alerts_created': created_count,
        'checked_count': submissions.count()
    }


@shared_task
def check_high_priority_stuck():
    """
    Check for high/critical priority submissions that are stuck in early stages.
    Runs daily for escalation tracking.
    """
    config = AlertConfiguration.objects.filter(
        alert_type='high_priority_stuck',
        is_enabled=True
    ).first()
    
    if not config:
        return {'status': 'skipped', 'reason': 'Configuration disabled'}
    
    # Find high priority submissions still in early stages
    submissions = Submission.objects.filter(
        priority__in=['High', 'Critical'],
        status__in=['Draft', 'HOD/DM Submit', 'Review of Procurement Draft']
    )
    
    created_count = 0
    
    for submission in submissions:
        days_old = (timezone.now() - submission.created_at).days
        
        # Alert if critical priority is pending 3+ days or high priority is pending 7+ days
        alert_threshold = 3 if submission.priority == 'CRITICAL' else 7
        
        if days_old >= alert_threshold:
            # Check if alert already exists
            existing_alert = Alert.objects.filter(
                submission=submission,
                alert_type='high_priority_stuck',
                status__in=['active', 'acknowledged']
            ).exists()
            
            if not existing_alert:
                alert = Alert.objects.create(
                    submission=submission,
                    alert_type='high_priority_stuck',
                    title=f"{submission.priority} Priority Stuck - {submission.tracking_reference}",
                    description=f"'{submission.item_name}' ({submission.priority} priority) is pending for {days_old} days in '{submission.status}' status",
                    severity='critical'
                )
                
                # Log to history
                AlertHistory.objects.create(
                    submission=submission,
                    alert_type='high_priority_stuck',
                    title=f"{submission.priority} Priority Stuck - {submission.tracking_reference}",
                    severity='critical',
                    triggered_reason=f"{submission.priority} priority pending {days_old} days in {submission.status}"
                )
                
                # Send notifications if configured
                if config.send_email:
                    send_priority_alert_email(submission, alert, config, days_old)
                
                created_count += 1
    
    return {
        'status': 'success',
        'alerts_created': created_count,
        'checked_count': submissions.count()
    }


@shared_task
def send_daily_alert_summary():
    """
    Send daily summary of all active alerts to relevant users.
    Runs once daily (typically in the morning).
    """
    # Get all active alerts
    active_alerts = Alert.objects.filter(
        status='active'
    ).select_related('submission').order_by('-severity')
    
    if not active_alerts.exists():
        return {'status': 'success', 'message': 'No active alerts to summarize'}
    
    # Group alerts by recipient role
    sent_count = 0
    
    # Send to Procurement Team
    procurement_team_users = User.objects.filter(role__name='Procurement Team')
    critical_alerts = active_alerts.filter(severity='critical')
    
    if critical_alerts.exists() and procurement_team_users.exists():
        for user in procurement_team_users:
            send_daily_summary_email(user, active_alerts, 'daily')
            sent_count += 1
    
    # Send to HOD/DM
    hod_users = User.objects.filter(role__name='HOD')
    for user in hod_users:
        user_alerts = active_alerts.filter(submission__division=user.division)
        if user_alerts.exists():
            send_daily_summary_email(user, user_alerts, 'daily')
            sent_count += 1
    
    return {
        'status': 'success',
        'emails_sent': sent_count,
        'alerts_summarized': active_alerts.count()
    }


def send_deadline_alert_email(submission, alert, config, deadline_type):
    """
    Send email notification for deadline alerts.
    """
    try:
        # Get recipients based on configuration
        recipients = []
        
        if config.notify_division_head and submission.division and submission.division.head:
            recipients.append(submission.division.head.email)
        
        if config.notify_cbm:
            cbm_users = User.objects.filter(role__name='CBM')
            recipients.extend(cbm_users.values_list('email', flat=True))
        
        if config.notify_procurement_team:
            procurement_users = User.objects.filter(role__name='Procurement Team')
            recipients.extend(procurement_users.values_list('email', flat=True))
        
        if not recipients:
            return
        
        # Render email template
        context = {
            'submission': submission,
            'alert': alert,
            'deadline_type': deadline_type,
            'deadline': submission.cbm_review_deadline if deadline_type == 'cbm_review' else submission.procurement_deadline,
        }
        
        subject = f"Alert: {alert.title}"
        html_message = render_to_string('emails/deadline_alert.html', context)
        
        send_mail(
            subject,
            f"Alert: {alert.title}",
            'noreply@pts.rbc.org',
            list(set(recipients)),  # Remove duplicates
            html_message=html_message,
            fail_silently=True
        )
        
        return True
    except Exception as e:
        print(f"Error sending deadline alert email: {e}")
        return False


def send_stalled_alert_email(submission, alert, config, stage_name, days_in_stage):
    """
    Send email notification for stalled submission alerts.
    """
    try:
        # Get recipients
        recipients = []
        
        if config.notify_division_head and submission.division and submission.division.head:
            recipients.append(submission.division.head.email)
        
        if config.notify_procurement_team:
            procurement_users = User.objects.filter(role__name='Procurement Team')
            recipients.extend(procurement_users.values_list('email', flat=True))
        
        if config.notify_cbm:
            cbm_users = User.objects.filter(role__name='CBM')
            recipients.extend(cbm_users.values_list('email', flat=True))
        
        if not recipients:
            return
        
        # Render email template
        context = {
            'submission': submission,
            'alert': alert,
            'stage_name': stage_name,
            'days_in_stage': days_in_stage,
        }
        
        subject = f"Alert: {alert.title}"
        html_message = render_to_string('emails/stalled_submission.html', context)
        
        send_mail(
            subject,
            f"Alert: {alert.title}",
            'noreply@pts.rbc.org',
            list(set(recipients)),
            html_message=html_message,
            fail_silently=True
        )
        
        return True
    except Exception as e:
        print(f"Error sending stalled alert email: {e}")
        return False


def send_priority_alert_email(submission, alert, config, days_pending):
    """
    Send email notification for high priority stuck submissions.
    """
    try:
        # Get recipients - prioritize team leads
        recipients = []
        
        if config.notify_division_head and submission.division and submission.division.head:
            recipients.append(submission.division.head.email)
        
        if config.notify_procurement_team:
            procurement_users = User.objects.filter(role__name='Procurement Team')
            recipients.extend(procurement_users.values_list('email', flat=True))
        
        if not recipients:
            return
        
        # Render email template
        context = {
            'submission': submission,
            'alert': alert,
            'days_pending': days_pending,
        }
        
        subject = f"ESCALATION: {alert.title}"
        html_message = render_to_string('emails/escalation_notice.html', context)
        
        send_mail(
            subject,
            f"ESCALATION: {alert.title}",
            'noreply@pts.rbc.org',
            list(set(recipients)),
            html_message=html_message,
            fail_silently=True
        )
        
        return True
    except Exception as e:
        print(f"Error sending priority alert email: {e}")
        return False


def send_daily_summary_email(user, alerts, frequency='daily'):
    """
    Send daily summary email of all active alerts to a user.
    """
    try:
        if not user.email:
            return False
        
        # Count alerts by severity
        critical_count = alerts.filter(severity='critical').count()
        warning_count = alerts.filter(severity='warning').count()
        info_count = alerts.filter(severity='info').count()
        
        context = {
            'user': user,
            'alerts': alerts[:20],  # Limit to 20 most recent
            'total_alerts': alerts.count(),
            'critical_count': critical_count,
            'warning_count': warning_count,
            'info_count': info_count,
            'frequency': frequency,
        }
        
        subject = f"Daily Alert Summary - {timezone.now().strftime('%B %d, %Y')}"
        html_message = render_to_string('emails/daily_summary.html', context)
        
        send_mail(
            subject,
            f"Daily Alert Summary",
            'noreply@pts.rbc.org',
            [user.email],
            html_message=html_message,
            fail_silently=True
        )
        
        return True
    except Exception as e:
        print(f"Error sending daily summary email: {e}")
        return False
