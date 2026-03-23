"""
Management command to fix notification action URLs for procurement calls.
"""
from django.core.management.base import BaseCommand
from apps.notifications.models import Notification
import re


class Command(BaseCommand):
    help = 'Fix action URLs for procurement call notifications'

    def handle(self, *args, **options):
        # Find all notifications for procurement calls with old URLs
        notifications = Notification.objects.filter(
            notification_type='procurement_call',
            action_url__icontains='/dashboard/hod/'
        )

        fixed_count = 0
        for notification in notifications:
            # Check if it's using the old format
            if notification.action_url == '/dashboard/hod/' or \
               notification.action_url.startswith('/dashboard/hod/submissions/'):
                
                # Update to new format
                call_id = notification.related_object_id
                notification.action_url = f'/dashboard/hod/calls/{call_id}/'
                notification.save()
                fixed_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Updated notification: {notification.id} -> {notification.action_url}'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(f'\nSuccessfully fixed {fixed_count} notification(s)')
        )
