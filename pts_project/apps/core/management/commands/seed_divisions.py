"""
Management command to seed divisions into the database.
"""
from django.core.management.base import BaseCommand
from apps.divisions.models import Division


class Command(BaseCommand):
    help = 'Seed divisions into the database'

    def handle(self, *args, **options):
        divisions = [
            'MCCH',
            'Mental Health',
            'NCD',
            'EPR',
            'HIV',
            'Malaria',
            'TB',
            'BTD',
            'NRL',
            'MED',
            'RHCC',
            'RIDS',
            'SAMU',
            'SPIU',
            'CS',
        ]

        created_count = 0
        for division_name in divisions:
            division, created = Division.objects.get_or_create(name=division_name)
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created division: {division_name}')
                )
                created_count += 1
            else:
                self.stdout.write(
                    self.style.WARNING(f'⊘ Division already exists: {division_name}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\nSuccessfully created {created_count} new divisions!')
        )
