"""
Signals for procurement app.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Submission, ProcurementCall, Bid


@receiver(pre_save, sender=Submission)
def submission_pre_save(sender, instance, **kwargs):
    """
    Pre-save signal for Submission.
    Ensures total_budget is calculated.
    """
    instance.total_budget = instance.quantity * instance.estimated_unit_price


@receiver(post_save, sender=Submission)
def submission_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal for Submission.
    Handles notifications and audit logging.
    """
    from apps.accounts.models import UserActivity, User
    from apps.notifications.models import Notification
    
    if created:
        # Log creation
        if instance.created_by:
            UserActivity.objects.create(
                user=instance.created_by,
                action='submission_created',
                description=f'Created submission: {instance.tracking_reference}',
                content_type='Submission',
                object_id=str(instance.id)
            )
    else:
        # Check if status has changed
        try:
            original = Submission.objects.get(pk=instance.pk)
            if original.status != instance.status:
                # Notify division head/HOD of status change
                division_heads = User.objects.filter(
                    division=instance.division,
                    role__name='HOD/DM'
                )
                
                status_messages = {
                    'Submitted': f'Your submission {instance.tracking_reference} has been received and is under review.',
                    'Under Review': f'Your submission {instance.tracking_reference} is currently under review by the procurement team.',
                    'Returned': f'Your submission {instance.tracking_reference} requires clarification. Please review the comments.',
                    'Approved': f'Your submission {instance.tracking_reference} has been approved!',
                    'Rejected': f'Unfortunately, your submission {instance.tracking_reference} has been rejected.',
                    'Published': f'Your submission {instance.tracking_reference} has been published to Umucyo.',
                    'Awarded': f'Your submission {instance.tracking_reference} has been awarded.',
                    'Completed': f'Your submission {instance.tracking_reference} has been completed.',
                }
                
                notification_title = f'Submission Status Changed to {instance.status}'
                message = status_messages.get(instance.status, f'Submission status changed to {instance.status}')
                
                notification_type = 'submission_status'
                priority = 'high' if instance.status in ['Returned', 'Rejected'] else 'medium'
                
                for hod in division_heads:
                    Notification.objects.create(
                        user=hod,
                        title=notification_title,
                        message=message,
                        notification_type=notification_type,
                        priority=priority,
                        related_object_type='Submission',
                        related_object_id=str(instance.id),
                        action_url=f'/dashboard/hod/submissions/{instance.id}/',
                    )
        except Submission.DoesNotExist:
            pass


@receiver(post_save, sender=ProcurementCall)
def procurement_call_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal for ProcurementCall.
    When a new call is issued, notify all HOD/DMs in the system.
    """
    from apps.accounts.models import UserActivity, User
    from apps.notifications.models import Notification
    
    if created:
        # Log creation
        if instance.created_by:
            UserActivity.objects.create(
                user=instance.created_by,
                action='call_created',
                description=f'Created procurement call: {instance.reference_number}',
                content_type='ProcurementCall',
                object_id=str(instance.id)
            )
        
        # Send notification to all HOD/DMs
        hod_dms = User.objects.filter(
            role__name='HOD/DM',
            is_active=True
        )
        
        notification_title = f'New Procurement Call: {instance.reference_number}'
        message = f'A new procurement call "{instance.title}" has been issued. Deadline: {instance.end_date.strftime("%B %d, %Y")}'
        
        for hod in hod_dms:
            Notification.objects.create(
                user=hod,
                title=notification_title,
                message=message,
                notification_type='procurement_call',
                priority='high',
                related_object_type='ProcurementCall',
                related_object_id=str(instance.id),
                action_url=f'/dashboard/hod/calls/{instance.id}/',
            )
    elif instance.status == 'Active':
        # If call was just activated, notify HOD/DMs again if not already notified
        from apps.accounts.models import User
        from apps.notifications.models import Notification
        
        # Check if notification already exists
        existing = Notification.objects.filter(
            related_object_id=str(instance.id),
            related_object_type='ProcurementCall',
            notification_type='procurement_call'
        ).first()
        
        if not existing:
            hod_dms = User.objects.filter(
                role__name='HOD/DM',
                is_active=True
            )
            
            for hod in hod_dms:
                Notification.objects.create(
                    user=hod,
                    title=f'Procurement Call Active: {instance.reference_number}',
                    message=f'The procurement call "{instance.title}" is now active and accepting submissions.',
                    notification_type='procurement_call',
                    priority='high',
                    related_object_type='ProcurementCall',
                    related_object_id=str(instance.id),
                    action_url=f'/dashboard/hod/calls/{instance.id}/',
                )


@receiver(post_save, sender=Bid)
def bid_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal for Bid.
    """
    if created:
        # Notify submission owner about new bid
        pass
