#!/usr/bin/env python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pts_project.settings')
django.setup()

from apps.procurement.models import Submission

# Get recent submissions with status Awarded or Completed
print("\n" + "="*60)
print("CHECKING RECENT SUBMISSIONS")
print("="*60 + "\n")

# Check Awarded status
awarded_subs = Submission.objects.filter(status='Awarded').order_by('-updated_at')[:5]
print(f"Submissions with 'Awarded' status: {awarded_subs.count()}\n")
for sub in awarded_subs:
    print(f"  ID: {sub.id}")
    print(f"  Ref: {sub.tracking_reference}")
    print(f"  Status: {sub.status}")
    print(f"  Award Details: {sub.award_details}")
    print()

# Check Completed status
completed_subs = Submission.objects.filter(status='Completed').order_by('-updated_at')[:5]
print(f"\nSubmissions with 'Completed' status: {completed_subs.count()}\n")
for sub in completed_subs:
    print(f"  ID: {sub.id}")
    print(f"  Ref: {sub.tracking_reference}")
    print(f"  Status: {sub.status}")
    print(f"  Award Details: {sub.award_details}")
    print()

# Check if any submission has award_details set but empty
with_award_details = Submission.objects.filter(award_details__isnull=False).exclude(award_details={}).order_by('-updated_at')[:10]
print(f"\nSubmissions WITH award_details populated: {with_award_details.count()}\n")
for sub in with_award_details:
    print(f"  ID: {sub.id}")
    print(f"  Ref: {sub.tracking_reference}")
    print(f"  Status: {sub.status}")
    print(f"  Award Details: {sub.award_details}")
    print()
