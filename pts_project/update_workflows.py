#!/usr/bin/env python
"""Script to update workflow stages in the database."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pts_project.settings')
django.setup()

from apps.workflows.models import WorkflowStage

# Delete old stages
print("Deleting old workflow stages...")
WorkflowStage.objects.all().delete()
print("Old stages deleted.")

# Create new stages
stages_data = [
    {'name': 'Call Issued', 'order': 1, 'stage_type': 'internal', 'description': 'Procurement call has been issued by CBM', 'expected_duration_days': 14, 'color': '#6366F1', 'icon': 'megaphone', 'allowed_roles': ['CBM', 'Admin']},
    {'name': 'HOD/DM Submit', 'order': 2, 'stage_type': 'internal', 'description': 'Head of Department/Division Manager submits procurement request', 'expected_duration_days': 7, 'color': '#8B5CF6', 'icon': 'document-text', 'allowed_roles': ['HOD/DM', 'Division User']},
    {'name': 'Review of Procurement Draft', 'order': 3, 'stage_type': 'internal', 'description': 'Procurement draft is reviewed for completeness', 'expected_duration_days': 5, 'color': '#EC4899', 'icon': 'eye', 'allowed_roles': ['Procurement Team', 'CBM']},
    {'name': 'Submit Compiled Document', 'order': 4, 'stage_type': 'transition', 'description': 'Procurement Team compiles all division submissions into one document and submits to CBM for review', 'expected_duration_days': 5, 'color': '#F97316', 'icon': 'archive', 'allowed_roles': ['Procurement Team']},
    {'name': 'CBM Review', 'order': 5, 'stage_type': 'transition', 'description': 'CBM reviews the compiled procurement document', 'expected_duration_days': 7, 'color': '#F59E0B', 'icon': 'user-check', 'allowed_roles': ['CBM']},
    {'name': 'Publish Plan', 'order': 6, 'stage_type': 'transition', 'description': 'Procurement plan is published', 'expected_duration_days': 3, 'color': '#10B981', 'icon': 'check-circle', 'allowed_roles': ['Procurement Team', 'CBM']},
    {'name': 'Prepare Tender Document', 'order': 7, 'stage_type': 'external', 'description': 'Individual tender document prepared; Umucyo tender number, title and procurement method are recorded', 'expected_duration_days': 7, 'color': '#3B82F6', 'icon': 'document-add', 'allowed_roles': ['Procurement Team']},
    {'name': 'CBM Review TD', 'order': 8, 'stage_type': 'external', 'description': 'CBM reviews the Tender Document', 'expected_duration_days': 5, 'color': '#F59E0B', 'icon': 'user-check', 'allowed_roles': ['CBM']},
    {'name': 'Publication of TD', 'order': 9, 'stage_type': 'external', 'description': 'Tender Document is published to Umucyo e-procurement', 'expected_duration_days': 2, 'color': '#06B6D4', 'icon': 'globe', 'allowed_roles': ['Procurement Team']},
    {'name': 'Bidding', 'order': 10, 'stage_type': 'external', 'description': 'Bidding period is open for suppliers', 'expected_duration_days': 30, 'color': '#EC4899', 'icon': 'currency-dollar', 'allowed_roles': ['Procurement Team']},
    {'name': 'Evaluation', 'order': 11, 'stage_type': 'external', 'description': 'Submitted bids are evaluated', 'expected_duration_days': 14, 'color': '#EF4444', 'icon': 'clipboard-check', 'allowed_roles': ['Procurement Team']},
    {'name': 'CBM Approval', 'order': 12, 'stage_type': 'external', 'description': 'CBM approves evaluation results', 'expected_duration_days': 7, 'color': '#F59E0B', 'icon': 'user-check', 'allowed_roles': ['CBM']},
    {'name': 'Notify Bidders', 'order': 13, 'stage_type': 'external', 'description': 'Bidders are notified of evaluation results', 'expected_duration_days': 3, 'color': '#8B5CF6', 'icon': 'mail', 'allowed_roles': ['Procurement Team']},
    {'name': 'Contract Negotiation', 'order': 14, 'stage_type': 'external', 'description': 'Contract negotiation with awarded bidder', 'expected_duration_days': 7, 'color': '#F59E0B', 'icon': 'handshake', 'allowed_roles': ['Procurement Team']},
    {'name': 'Contract Drafting', 'order': 15, 'stage_type': 'external', 'description': 'Contract is drafted based on negotiations', 'expected_duration_days': 5, 'color': '#3B82F6', 'icon': 'document-text', 'allowed_roles': ['Procurement Team']},
    {'name': 'Legal Review', 'order': 16, 'stage_type': 'external', 'description': 'Legal review of contract (RBC internal)', 'expected_duration_days': 7, 'color': '#06B6D4', 'icon': 'shield-check', 'allowed_roles': ['Admin', 'CBM']},
    {'name': 'Supplier Approval', 'order': 17, 'stage_type': 'external', 'description': 'Supplier approval of contract terms', 'expected_duration_days': 7, 'color': '#F59E0B', 'icon': 'user-check', 'allowed_roles': ['Procurement Team']},
    {'name': 'MINIJUST Legal Review', 'order': 18, 'stage_type': 'external', 'description': 'MINIJUST legal review (for contracts > 500M RWF)', 'expected_duration_days': 14, 'color': '#EC4899', 'icon': 'building-2', 'allowed_roles': ['Admin', 'CBM']},
    {'name': 'Awarded', 'order': 19, 'stage_type': 'external', 'description': 'Contract has been awarded and signed', 'expected_duration_days': 3, 'color': '#14B8A6', 'icon': 'badge-check', 'allowed_roles': ['Procurement Team', 'CBM']},
    {'name': 'Completed', 'order': 20, 'stage_type': 'external', 'description': 'Procurement process completed successfully', 'expected_duration_days': 0, 'color': '#22C55E', 'icon': 'flag', 'allowed_roles': ['Procurement Team'], 'is_terminal': True},
]

print("\nCreating new workflow stages...")
for stage_data in stages_data:
    is_terminal = stage_data.pop('is_terminal', False)
    stage = WorkflowStage.objects.create(**stage_data, is_terminal=is_terminal)
    print(f"  Created: {stage.order}. {stage.name}")

print("\n✅ All 20 workflow stages created successfully!")
