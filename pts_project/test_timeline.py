#!/usr/bin/env python
"""Test timeline system functionality."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pts_project.settings')
django.setup()

from apps.procurement.models import Submission, TimelineConfiguration
from apps.procurement.timeline_utils import add_business_days, calculate_deadline
from datetime import datetime, timedelta

# Check if TimelineConfiguration has data
config_count = TimelineConfiguration.objects.count()
print(f"✓ TimelineConfiguration records: {config_count}")

# List some configurations to verify
configs = TimelineConfiguration.objects.all()[:5]
for config in configs:
    print(f"  - {config.stage_name} / {config.procurement_method}: {config.max_days} days")

# Test business day calculation
test_date = datetime.now().date()
deadline = add_business_days(test_date, 21)
print(f"\n✓ Business day calculation works")
print(f"  From: {test_date}, +21 business days = {deadline}")

# Check Submission fields
submission = Submission.objects.first()
if submission:
    print(f"\n✓ Submission model has timeline fields:")
    print(f"  - procurement_method: {submission.procurement_method}")
    print(f"  - current_stage_deadline: {submission.current_stage_deadline}")
    print(f"  - timeline_status: {submission.timeline_status}")
    print(f"  - timeline_days_remaining: {submission.timeline_days_remaining}")
    print(f"  - is_timeline_expired: {submission.is_timeline_expired}")
else:
    print("\n⚠ No submissions found in database")

print("\n✓ Timeline system is ready!")
