"""
Management command to populate TimelineConfiguration with default values.
Run with: python manage.py populate_timeline_config
"""
from django.core.management.base import BaseCommand
from apps.procurement.models import TimelineConfiguration


class Command(BaseCommand):
    help = 'Populate TimelineConfiguration with default procurement timelines'

    def handle(self, *args, **options):
        # Clear existing configurations
        TimelineConfiguration.objects.all().delete()
        
        configs = [
            # Publication of Tender Documents - varies by method
            TimelineConfiguration(
                stage_name='Publication of TD',
                procurement_method='International Competitive',
                min_days=30,
                max_days=None,
            ),
            TimelineConfiguration(
                stage_name='Publication of TD',
                procurement_method='International Restricted',
                min_days=14,
                max_days=None,
            ),
            TimelineConfiguration(
                stage_name='Publication of TD',
                procurement_method='National Competitive',
                min_days=21,
                max_days=None,
            ),
            TimelineConfiguration(
                stage_name='Publication of TD',
                procurement_method='National Restricted',
                min_days=7,
                max_days=None,
            ),
            TimelineConfiguration(
                stage_name='Publication of TD',
                procurement_method='Request for Quotations',
                min_days=3,
                max_days=None,
            ),
            TimelineConfiguration(
                stage_name='Publication of TD',
                procurement_method='National Open Simplified',
                min_days=8,
                max_days=None,
            ),
            TimelineConfiguration(
                stage_name='Publication of TD',
                procurement_method='National Restricted Simplified',
                min_days=5,
                max_days=None,
            ),
            # Methods without fixed timelines
            TimelineConfiguration(
                stage_name='Publication of TD',
                procurement_method='Prequalification',
                min_days=0,
                max_days=None,
            ),
            TimelineConfiguration(
                stage_name='Publication of TD',
                procurement_method='Single Source',
                min_days=0,
                max_days=None,
            ),
            TimelineConfiguration(
                stage_name='Publication of TD',
                procurement_method='Force Account',
                min_days=0,
                max_days=None,
            ),
            TimelineConfiguration(
                stage_name='Publication of TD',
                procurement_method='Two Stage Tendering',
                min_days=0,
                max_days=None,
            ),
            TimelineConfiguration(
                stage_name='Publication of TD',
                procurement_method='Turnkey',
                min_days=0,
                max_days=None,
            ),
            TimelineConfiguration(
                stage_name='Publication of TD',
                procurement_method='Community Participation',
                min_days=0,
                max_days=None,
            ),
            TimelineConfiguration(
                stage_name='Publication of TD',
                procurement_method='Competitive Dialogue',
                min_days=0,
                max_days=None,
            ),
            TimelineConfiguration(
                stage_name='Publication of TD',
                procurement_method='Design and Build',
                min_days=0,
                max_days=None,
            ),
            TimelineConfiguration(
                stage_name='Publication of TD',
                procurement_method='Pre-financing',
                min_days=0,
                max_days=None,
            ),
            TimelineConfiguration(
                stage_name='Publication of TD',
                procurement_method='Reverse Auctioning',
                min_days=0,
                max_days=None,
            ),
            
            # Evaluation of Bids/Proposals - all methods, max 21 days
            TimelineConfiguration(
                stage_name='Evaluation',
                procurement_method=None,
                min_days=0,
                max_days=21,
            ),
            
            # Notification - 7 days for all
            TimelineConfiguration(
                stage_name='Notification',
                procurement_method=None,
                min_days=7,
                max_days=7,
            ),
            
            # Bid Validity Period - 120 days base, extendable by 60
            TimelineConfiguration(
                stage_name='Bid Validity Period',
                procurement_method=None,
                min_days=120,
                max_days=120,
                is_extendable=True,
                extension_days=60,
            ),
            
            # Contract Signature - International (22 days total)
            TimelineConfiguration(
                stage_name='Contract Signature',
                procurement_method='International',
                min_days=22,
                max_days=22,
            ),
            
            # Contract Signature - National (28 days total)
            TimelineConfiguration(
                stage_name='Contract Signature',
                procurement_method='National',
                min_days=28,
                max_days=28,
            ),
        ]
        
        TimelineConfiguration.objects.bulk_create(configs)
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {len(configs)} timeline configurations'
            )
        )
