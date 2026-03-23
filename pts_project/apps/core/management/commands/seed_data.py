"""
Management command to seed initial data for PTS.
Creates roles, divisions, workflow stages, and optionally sample data.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.accounts.models import Role
from apps.divisions.models import Division
from apps.workflows.models import WorkflowStage

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed initial data for PTS (roles, divisions, workflow stages)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--with-sample-data',
            action='store_true',
            help='Also create sample users and procurement data',
        )
        parser.add_argument(
            '--admin-email',
            type=str,
            help='Email for the admin user',
            default='admin@rbc.gov.rw'
        )
        parser.add_argument(
            '--admin-password',
            type=str,
            help='Password for the admin user',
            default='admin123!'
        )
    
    def handle(self, *args, **options):
        self.stdout.write('Starting PTS data seeding...\n')
        
        # Seed roles
        self._seed_roles()
        
        # Seed divisions
        self._seed_divisions()
        
        # Seed workflow stages
        self._seed_workflow_stages()
        
        # Create admin user
        self._create_admin(options['admin_email'], options['admin_password'])
        
        # Create sample data if requested
        if options['with_sample_data']:
            self._create_sample_data()
        
        self.stdout.write(self.style.SUCCESS('\nData seeding completed successfully!'))
    
    def _seed_roles(self):
        """Seed the predefined roles."""
        self.stdout.write('Seeding roles...')
        
        roles_data = [
            {
                'name': 'Admin',
                'description': 'System Administrator with full access',
                'can_create_calls': True,
                'can_approve': True,
                'can_submit': True,
                'can_update_status': True,
                'can_manage_users': True,
                'can_view_all_divisions': True,
                'can_view_reports': True,
            },
            {
                'name': 'CBM',
                'description': 'Chief Budget Manager - initiates calls, approves submissions',
                'can_create_calls': True,
                'can_approve': True,
                'can_submit': False,
                'can_update_status': True,
                'can_manage_users': False,
                'can_view_all_divisions': True,
                'can_view_reports': True,
            },
            {
                'name': 'HOD/DM',
                'description': 'Head of Department / Division Manager - submits and approves within division',
                'can_create_calls': False,
                'can_approve': True,
                'can_submit': True,
                'can_update_status': False,
                'can_manage_users': False,
                'can_view_all_divisions': False,
                'can_view_reports': True,
            },
            {
                'name': 'Procurement Team',
                'description': 'Manages procurement workflow and status updates',
                'can_create_calls': False,
                'can_approve': False,
                'can_submit': False,
                'can_update_status': True,
                'can_manage_users': False,
                'can_view_all_divisions': True,
                'can_view_reports': True,
            },
            {
                'name': 'Division User',
                'description': 'Division staff - supports submissions and tracks activities',
                'can_create_calls': False,
                'can_approve': False,
                'can_submit': True,
                'can_update_status': False,
                'can_manage_users': False,
                'can_view_all_divisions': False,
                'can_view_reports': False,
            },
        ]
        
        for role_data in roles_data:
            role, created = Role.objects.update_or_create(
                name=role_data['name'],
                defaults=role_data
            )
            status = 'Created' if created else 'Updated'
            self.stdout.write(f'  {status} role: {role.name}')
    
    def _seed_divisions(self):
        """Seed the predefined divisions."""
        self.stdout.write('Seeding divisions...')
        
        divisions_data = [
            {
                'name': 'Research, Innovation and Data Science',
                'code': 'RIDS',
                'description': 'Division responsible for research, innovation, and data science activities',
            },
            {
                'name': 'HIV/AIDS and STIs',
                'code': 'HIV',
                'description': 'Division managing HIV/AIDS and STI programs',
            },
            {
                'name': 'Maternal, Child and Community Health',
                'code': 'MCCH',
                'description': 'Division for maternal, child, and community health services',
            },
            {
                'name': 'Mental Health',
                'code': 'MH',
                'description': 'Division for mental health services and programs',
            },
            {
                'name': 'Malaria and Other Parasitic Diseases',
                'code': 'MALARIA',
                'description': 'Division managing malaria and parasitic disease programs',
            },
            {
                'name': 'Non-Communicable Diseases',
                'code': 'NCDs',
                'description': 'Division for non-communicable disease programs',
            },
            {
                'name': 'Administration',
                'code': 'ADMIN',
                'description': 'Administrative division',
            },
            {
                'name': 'Finance',
                'code': 'FIN',
                'description': 'Finance division',
            },
            {
                'name': 'Procurement',
                'code': 'PROC',
                'description': 'Procurement division',
            },
        ]
        
        for div_data in divisions_data:
            division, created = Division.objects.update_or_create(
                code=div_data['code'],
                defaults=div_data
            )
            status = 'Created' if created else 'Updated'
            self.stdout.write(f'  {status} division: {division.name}')
    
    def _seed_workflow_stages(self):
        """Seed the complete procurement workflow stages."""
        self.stdout.write('Seeding workflow stages...')
        
        stages_data = [
            {
                'name': 'Call Issued',
                'order': 1,
                'stage_type': 'internal',
                'description': 'Procurement call has been issued by CBM',
                'expected_duration_days': 14,
                'color': '#6366F1',
                'icon': 'megaphone',
                'allowed_roles': ['CBM', 'Admin'],
            },
            {
                'name': 'HOD/DM Submit',
                'order': 2,
                'stage_type': 'internal',
                'description': 'Head of Department/Division Manager submits procurement request',
                'expected_duration_days': 7,
                'color': '#8B5CF6',
                'icon': 'document-text',
                'allowed_roles': ['HOD/DM', 'Division User'],
            },
            {
                'name': 'Review of Procurement Draft',
                'order': 3,
                'stage_type': 'internal',
                'description': 'Procurement draft is reviewed for completeness',
                'expected_duration_days': 5,
                'color': '#EC4899',
                'icon': 'eye',
                'allowed_roles': ['Procurement Team', 'CBM'],
            },
            {
                'name': 'Submit Compiled Document',
                'order': 4,
                'stage_type': 'transition',
                'description': 'Procurement Team compiles all division submissions into one document and submits to CBM for review',
                'expected_duration_days': 5,
                'color': '#F97316',
                'icon': 'archive',
                'allowed_roles': ['Procurement Team'],
            },
            {
                'name': 'CBM Review',
                'order': 5,
                'stage_type': 'transition',
                'description': 'CBM reviews the compiled procurement document',
                'expected_duration_days': 7,
                'color': '#F59E0B',
                'icon': 'user-check',
                'allowed_roles': ['CBM'],
            },
            {
                'name': 'Publish Plan',
                'order': 6,
                'stage_type': 'transition',
                'description': 'Procurement plan is published',
                'expected_duration_days': 3,
                'color': '#10B981',
                'icon': 'check-circle',
                'allowed_roles': ['Procurement Team', 'CBM'],
            },
            {
                'name': 'Prepare Tender Document',
                'order': 7,
                'stage_type': 'external',
                'description': 'Individual tender document prepared; Umucyo tender number, title and procurement method are recorded',
                'expected_duration_days': 7,
                'color': '#3B82F6',
                'icon': 'document-add',
                'allowed_roles': ['Procurement Team'],
            },
            {
                'name': 'CBM Review TD',
                'order': 8,
                'stage_type': 'external',
                'description': 'CBM reviews the Tender Document',
                'expected_duration_days': 5,
                'color': '#F59E0B',
                'icon': 'user-check',
                'allowed_roles': ['CBM'],
            },
            {
                'name': 'Publication of TD',
                'order': 9,
                'stage_type': 'external',
                'description': 'Tender Document is published to Umucyo e-procurement',
                'expected_duration_days': 2,
                'color': '#06B6D4',
                'icon': 'globe',
                'allowed_roles': ['Procurement Team'],
            },
            {
                'name': 'Bidding',
                'order': 10,
                'stage_type': 'external',
                'description': 'Bidding period is open for suppliers',
                'expected_duration_days': 30,
                'color': '#EC4899',
                'icon': 'currency-dollar',
                'allowed_roles': ['Procurement Team'],
            },
            {
                'name': 'Evaluation',
                'order': 11,
                'stage_type': 'external',
                'description': 'Submitted bids are evaluated',
                'expected_duration_days': 14,
                'color': '#EF4444',
                'icon': 'clipboard-check',
                'allowed_roles': ['Procurement Team'],
            },
            {
                'name': 'CBM Approval',
                'order': 12,
                'stage_type': 'external',
                'description': 'CBM approves evaluation results',
                'expected_duration_days': 7,
                'color': '#F59E0B',
                'icon': 'user-check',
                'allowed_roles': ['CBM'],
            },
            {
                'name': 'Notify Bidders',
                'order': 13,
                'stage_type': 'external',
                'description': 'Bidders are notified of evaluation results',
                'expected_duration_days': 3,
                'color': '#8B5CF6',
                'icon': 'mail',
                'allowed_roles': ['Procurement Team'],
            },
            {
                'name': 'Contract Negotiation',
                'order': 14,
                'stage_type': 'external',
                'description': 'Contract negotiation with awarded bidder',
                'expected_duration_days': 7,
                'color': '#F59E0B',
                'icon': 'handshake',
                'allowed_roles': ['Procurement Team'],
            },
            {
                'name': 'Contract Drafting',
                'order': 15,
                'stage_type': 'external',
                'description': 'Contract is drafted based on negotiations',
                'expected_duration_days': 5,
                'color': '#3B82F6',
                'icon': 'document-text',
                'allowed_roles': ['Procurement Team'],
            },
            {
                'name': 'Legal Review',
                'order': 16,
                'stage_type': 'external',
                'description': 'Legal review of contract (RBC internal)',
                'expected_duration_days': 7,
                'color': '#06B6D4',
                'icon': 'shield-check',
                'allowed_roles': ['Admin', 'CBM'],
            },
            {
                'name': 'Supplier Approval',
                'order': 17,
                'stage_type': 'external',
                'description': 'Supplier approval of contract terms',
                'expected_duration_days': 7,
                'color': '#F59E0B',
                'icon': 'user-check',
                'allowed_roles': ['Procurement Team'],
            },
            {
                'name': 'MINIJUST Legal Review',
                'order': 18,
                'stage_type': 'external',
                'description': 'MINIJUST legal review (for contracts > 500M RWF)',
                'expected_duration_days': 14,
                'color': '#EC4899',
                'icon': 'building-2',
                'allowed_roles': ['Admin', 'CBM'],
            },
            {
                'name': 'Awarded',
                'order': 19,
                'stage_type': 'external',
                'description': 'Contract has been awarded and signed',
                'expected_duration_days': 3,
                'color': '#14B8A6',
                'icon': 'badge-check',
                'allowed_roles': ['Procurement Team', 'CBM'],
            },
            {
                'name': 'Completed',
                'order': 20,
                'stage_type': 'external',
                'description': 'Procurement process completed successfully',
                'expected_duration_days': 0,
                'color': '#22C55E',
                'icon': 'flag',
                'allowed_roles': ['Procurement Team'],
                'is_terminal': True,
            },
        ]

        for stage_data in stages_data:
            is_terminal = stage_data.pop('is_terminal', False)
            stage, created = WorkflowStage.objects.update_or_create(
                order=stage_data['order'],
                defaults={**stage_data, 'is_terminal': is_terminal}
            )
            status = 'Created' if created else 'Updated'
            self.stdout.write(f'  {status} stage: {stage.order}. {stage.name}')
    
    def _create_admin(self, email, password):
        """Create the admin user."""
        self.stdout.write('Creating admin user...')
        
        admin_role = Role.objects.get(name='Admin')
        
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'full_name': 'System Administrator',
                'role': admin_role,
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
                'is_verified': True,
            }
        )
        
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(f'  Created admin user: {email}')
        else:
            self.stdout.write(f'  Admin user already exists: {email}')
    
    def _create_sample_data(self):
        """Create sample users and procurement data."""
        self.stdout.write('Creating sample data...')
        
        # Create sample users for each division and role
        divisions = Division.objects.all()
        roles = Role.objects.all()
        
        # Create CBM user
        cbm_role = Role.objects.get(name='CBM')
        cbm_user, _ = User.objects.get_or_create(
            email='cbm@rbc.gov.rw',
            defaults={
                'full_name': 'Chief Budget Manager',
                'role': cbm_role,
                'is_active': True,
                'is_verified': True,
            }
        )
        cbm_user.set_password('cbm123!')
        cbm_user.save()
        self.stdout.write(f'  Created CBM user: cbm@rbc.gov.rw')
        
        # Create HOD/DM for each division
        hod_role = Role.objects.get(name='HOD/DM')
        for division in divisions[:5]:  # First 5 divisions
            email = f"hod.{division.code.lower()}@rbc.gov.rw"
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'full_name': f'HOD {division.name}',
                    'role': hod_role,
                    'division': division,
                    'is_active': True,
                    'is_verified': True,
                }
            )
            if created:
                user.set_password('hod123!')
                user.save()
                self.stdout.write(f'  Created HOD user: {email}')
        
        # Create Procurement Team user
        proc_role = Role.objects.get(name='Procurement Team')
        proc_div = Division.objects.get(code='PROC')
        proc_user, created = User.objects.get_or_create(
            email='procurement@rbc.gov.rw',
            defaults={
                'full_name': 'Procurement Officer',
                'role': proc_role,
                'division': proc_div,
                'is_active': True,
                'is_verified': True,
            }
        )
        if created:
            proc_user.set_password('proc123!')
            proc_user.save()
            self.stdout.write(f'  Created Procurement user: procurement@rbc.gov.rw')
        
        self.stdout.write('  Sample data creation completed')
