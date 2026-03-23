"""
Signals for automatic alert creation based on submission changes.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from apps.procurement.models import Submission
from apps.workflows.models import WorkflowStage
from .models import Alert, AlertConfiguration, AlertHistory


@receiver(post_save, sender=Submission)
def check_deadline_alerts(sender, instance, created, **kwargs):
    """
    Check if submission has approaching or missed deadlines.
    """
    config = AlertConfiguration.objects.filter(
        alert_type='deadline_approaching',
        is_enabled=True
    ).first()
    
    if not config:
        return
    
    today = timezone.now().date()
    days_before = config.days_before_deadline
    threshold_date = today + timedelta(days=days_before)
    
    # Check CBM review deadline
    if instance.cbm_review_deadline:
        if instance.cbm_review_deadline <= threshold_date:
            # Check if alert already exists
            existing_alert = Alert.objects.filter(
                submission=instance,
                alert_type='deadline_approaching',
                status__in=['active', 'acknowledged']
            ).first()
            
            if not existing_alert:
                Alert.objects.create(
                    submission=instance,
                    alert_type='deadline_approaching',
                    title=f"CBM Review Deadline Approaching - {instance.tracking_reference}",
                    description=f"CBM review for {instance.item_name} is due on {instance.cbm_review_deadline}",
                    severity='warning' if instance.cbm_review_deadline >= today else 'critical'
                )
                
                # Log to history
                AlertHistory.objects.create(
                    submission=instance,
                    alert_type='deadline_approaching',
                    title=f"CBM Review Deadline - {instance.tracking_reference}",
                    severity='warning' if instance.cbm_review_deadline >= today else 'critical',
                    triggered_reason=f"CBM review deadline is {instance.cbm_review_deadline}"
                )
    
    # Check procurement deadline
    if instance.procurement_deadline:
        if instance.procurement_deadline <= threshold_date:
            existing_alert = Alert.objects.filter(
                submission=instance,
                alert_type='deadline_approaching',
                status__in=['active', 'acknowledged']
            ).first()
            
            if not existing_alert:
                Alert.objects.create(
                    submission=instance,
                    alert_type='deadline_approaching',
                    title=f"Procurement Deadline Approaching - {instance.tracking_reference}",
                    description=f"Procurement for {instance.item_name} is due on {instance.procurement_deadline}",
                    severity='warning' if instance.procurement_deadline >= today else 'critical'
                )
                
                AlertHistory.objects.create(
                    submission=instance,
                    alert_type='deadline_approaching',
                    title=f"Procurement Deadline - {instance.tracking_reference}",
                    severity='warning' if instance.procurement_deadline >= today else 'critical',
                    triggered_reason=f"Procurement deadline is {instance.procurement_deadline}"
                )


@receiver(post_save, sender=Submission)
def check_stalled_submissions(sender, instance, **kwargs):
    """
    Check if submission is stalled in a stage for too long.
    """
    config = AlertConfiguration.objects.filter(
        alert_type='stalled_submission',
        is_enabled=True
    ).first()
    
    if not config:
        return
    
    # Get the most recent workflow history entry
    from apps.workflows.models import WorkflowHistory
    
    latest_history = WorkflowHistory.objects.filter(
        submission=instance
    ).order_by('-created_at').first()
    
    if not latest_history:
        return
    
    days_in_stage = (timezone.now() - latest_history.created_at).days
    
    if days_in_stage >= config.days_in_stage:
        # Check if alert already exists
        existing_alert = Alert.objects.filter(
            submission=instance,
            alert_type='stalled_submission',
            status__in=['active', 'acknowledged']
        ).first()
        
        if not existing_alert:
            stage_name = latest_history.new_stage.name if latest_history.new_stage else 'Unknown'
            Alert.objects.create(
                submission=instance,
                alert_type='stalled_submission',
                title=f"Submission Stalled - {instance.tracking_reference}",
                description=f"{instance.item_name} has been in '{stage_name}' stage for {days_in_stage} days",
                severity='warning' if days_in_stage < 30 else 'critical'
            )
            
            AlertHistory.objects.create(
                submission=instance,
                alert_type='stalled_submission',
                title=f"Submission Stalled - {instance.tracking_reference}",
                severity='warning' if days_in_stage < 30 else 'critical',
                triggered_reason=f"Submission in '{stage_name}' stage for {days_in_stage} days"
            )


@receiver(post_save, sender=Submission)
def check_priority_alerts(sender, instance, **kwargs):
    """
    Check if high/critical priority submissions are stuck.
    """
    if instance.priority not in ['HIGH', 'CRITICAL']:
        return
    
    config = AlertConfiguration.objects.filter(
        alert_type='high_priority_stuck',
        is_enabled=True
    ).first()
    
    if not config:
        return
    
    from apps.workflows.models import WorkflowHistory
    
    # Get submission age
    days_old = (timezone.now() - instance.created_at).days
    
    # Check if it's still not approved after certain days
    if instance.status not in ['Publish Plan', 'Prepare Tender Document', 'CBM Review TD', 'Publication of TD', 'Bidding', 'Evaluation', 'Notify Bidders', 'Contract Negotiation', 'Contract Drafting', 'Legal Review', 'MINIJUST Legal Review', 'Awarded', 'Completed'] and days_old >= 7:
        existing_alert = Alert.objects.filter(
            submission=instance,
            alert_type='high_priority_stuck',
            status__in=['active', 'acknowledged']
        ).first()
        
        if not existing_alert:
            Alert.objects.create(
                submission=instance,
                alert_type='high_priority_stuck',
                title=f"High Priority Submission Stuck - {instance.tracking_reference}",
                description=f"{instance.priority} priority submission '{instance.item_name}' is still in '{instance.status}' after {days_old} days",
                severity='critical'
            )
            
            AlertHistory.objects.create(
                submission=instance,
                alert_type='high_priority_stuck',
                title=f"High Priority Stuck - {instance.tracking_reference}",
                severity='critical',
                triggered_reason=f"{instance.priority} priority submission pending for {days_old} days"
            )
