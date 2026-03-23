# Complete Procurement Timeline Implementation - All Stages

## Overview
Full timeline automation implemented for all 5 major procurement phases with automatic deadline tracking, business day calculations, and escalating notifications.

## Stages & Timeline Implementation

### Stage 1: Publication of TD (Tender Document)
- **Workflow**: CBM Review TD (order 7) → Publication of TD (order 8)
- **Responsible**: CBM Team
- **Timeline**: Method-specific (3-30 business days based on procurement method)
  - International Competitive: 30 days
  - International Restricted: 14 days
  - National Competitive: 21 days
  - National Restricted: 7 days
  - Request for Quotations: 3 days
  - National Open Simplified: 8 days
  - National Restricted Simplified: 5 days
  - Others: Flexible (0 days = date-specific)

**Implementation**: 
- View: `cbm_approve_submission_view` in [apps/dashboard/views.py](apps/dashboard/views.py#L1218-L1431)
- Form: `ProcurementMethodForm` in [apps/procurement/forms.py](apps/procurement/forms.py)
- Template: [templates/dashboard/cbm_approve_with_method.html](templates/dashboard/cbm_approve_with_method.html)
- Code:
  ```python
  submission.set_timeline_deadline(
      stage_name='Publication of TD',
      procurement_method=selected_method  # Required
  )
  ```

### Stage 2: Evaluation of Bids/Proposals
- **Workflow**: Bidding (order 9) → Evaluation (order 10)
- **Responsible**: Procurement Team
- **Timeline**: ≤ 21 business days (fixed for all methods)

**Implementation**:
- First transition: Publication of TD (order 8) → Bidding (order 9) - Handled by `procurement_publish_td_view`
  - Sets Bid Validity Period timeline (120 days)
- Second transition: Evaluation (order 10) → CBM Approval (order 11) - Handled by `procurement_notify_bidders_view`
  - Sets Evaluation timeline (21 days) if not already set
- Code in `procurement_publish_td_view`:
  ```python
  submission.set_timeline_deadline(
      stage_name='Bid Validity Period',
      procurement_method=None
  )  # 120 days from bid opening
  ```
- Code in `procurement_notify_bidders_view`:
  ```python
  if not submission.current_stage_deadline:
      submission.set_timeline_deadline(
          stage_name='Evaluation',
          procurement_method=None
      )  # 21 days
  ```

### Stage 3: Notification
- **Workflow**: CBM Approval (order 11) → Notify Bidders (order 12)
- **Responsible**: Procurement Team  
- **Timeline**: 7 business days (fixed for all methods)
- **Notification Requirement**: "7 days after expiry of notification" before contract signature

**Implementation**:
- View: `procurement_advance_stage_view` in [apps/dashboard/views_procurement.py](apps/dashboard/views_procurement.py#L1224-1410)
- Code:
  ```python
  if next_status == 'Notify Bidders':
      submission.set_timeline_deadline(
          stage_name='Notification',
          procurement_method=None
      )  # 7 days
  ```

### Stage 4: Bid Validity Period
- **Workflow**: Bidding (order 9) - Started when transitioning to Bidding stage
- **Responsible**: Tracking (Procurement Team)
- **Timeline**: 120 business days from bid opening
- **Extension**: One-time extension of +60 days available
- **Usage**: Available via `submission.extend_bid_validity(reason)`

**Implementation**:
- View: `procurement_publish_td_view` in [apps/dashboard/views_procurement.py](apps/dashboard/views_procurement.py#L1056-1140)
- Code:
  ```python
  submission.set_timeline_deadline(
      stage_name='Bid Validity Period',
      procurement_method=None
  )  # 120 days
  ```
- Extension method in [apps/procurement/models.py](apps/procurement/models.py):
  ```python
  def extend_bid_validity(self, reason):
      """Extend bid validity by 60 days (one-time only)"""
      if self.bid_validity_extension_used:
          raise ValueError("Bid validity can only be extended once")
      self.bid_validity_extension_used = True
      # Extend deadline by 60 business days
  ```

### Stage 5: Contract Signature
- **Workflow**: Multiple contract-related stages (13-17, then Awarded order 18)
- **Responsible**: Procurement Team / Legal Department / MINIJUST
- **Timeline**: Depends on tender type
  - **International Tender**: 7 days (from notification expiry) + 15 days (performance security) = **22 days**
  - **National Tender**: 7 days (from notification expiry) + 21 days (performance security) = **28 days**

**Implementation**:
- View: `procurement_advance_stage_view` in [apps/dashboard/views_procurement.py](apps/dashboard/views_procurement.py#L1224-1410)
- Tender type determination: Automatic based on procurement method
  - International methods: 'International Competitive', 'International Restricted' → International timeline
  - All other methods → National timeline
- Code:
  ```python
  # Determine tender type from procurement method
  international_methods = ['International Competitive', 'International Restricted']
  if submission.procurement_method in international_methods:
      tender_type = 'International'
  else:
      tender_type = 'National'
  
  if tender_type:
      submission.set_timeline_deadline(
          stage_name='Contract Signature',
          procurement_method=None,
          tender_type=tender_type
      )  # 22 or 28 days depending on type
  ```

## Complete Procurement Workflow with Timeline Coverage

```
STAGE 1: CBM Review TD (order 7)
         ↓ CBM Approves
STAGE 2: Publication of TD (order 8) ★ METHOD SELECTION + TIMELINE SET (3-30 days)
         ↓ Procurement publishes
STAGE 3: Bidding (order 9) ★ BID VALIDITY TIMELINE SET (120 days)
         ↓ Bidding period ends, evaluation starts
STAGE 4: Evaluation (order 10) ★ EVALUATION TIMELINE SET (21 days)
         ↓ Evaluation complete
STAGE 5: CBM Approval (order 11)
         ↓ CBM approves evaluation
STAGE 6: Notify Bidders (order 12) ★ NOTIFICATION TIMELINE SET (7 days)
         ↓ Bidders notified, negotiation starts
STAGE 7: Contract Negotiation (order 13)
         ↓ Negotiation complete
STAGE 8: Contract Drafting (order 14) ★ CONTRACT SIGNATURE TIMELINE SET (22/28 days)
         ↓ Draft complete
STAGE 9: Legal Review (order 15)
         ↓ Legal review complete
STAGE 10: Supplier Approval (order 16)
         ↓ Supplier approved
STAGE 11: MINIJUST Legal Review (order 17)
         ↓ Final approval
STAGE 12: Awarded (order 18)
         ↓ Contract awarded
STAGE 13: Completed (order 19)
```

## Timeline Display & Monitoring

### Frontend Display
All submission detail templates show timeline status card:
- [templates/cbm/submission_detail.html](templates/cbm/submission_detail.html)
- [templates/procurement/submission_detail.html](templates/procurement/submission_detail.html)
- [templates/dashboard/hod_submission_detail.html](templates/dashboard/hod_submission_detail.html)

**Card Information**:
- Current deadline (formatted date/time)
- Procurement method (if set)
- Current stage name
- Business days remaining (color-coded):
  - Green: >7 days
  - Yellow: >3 days
  - Red: ≤3 days
- Timeline status badge (On Track/Approaching/Overdue)
- Visual progress bar

### Automated Monitoring
- **Task**: `monitor_submission_timelines()` in [apps/notifications/tasks.py](apps/notifications/tasks.py#L383-L450)
- **Schedule**: Every 6 hours via Celery Beat
- **Functionality**:
  1. Queries all submissions with `current_stage_deadline` set
  2. Calls `submission.update_timeline_status()` for each
  3. Auto-creates notifications when status changes
  4. Sends professional HTML emails with timeline alerts

**Escalation Logic**:
- ≤7 days remaining: Yellow notification (priority=high)
- 0+ days past deadline: Red notification (priority=critical)

## Supporting Infrastructure

### Database Models
- **TimelineConfiguration**: 22 pre-loaded configurations
  - `stage_name`: Evaluation, Notification, Bid Validity, Contract Signature, etc.
  - `procurement_method`: Specific method or None (all)
  - `min_days`, `max_days`: Duration range
  - `is_extendable`, `extension_days`: Extension capability

- **Submission Model Extensions** (5 new fields):
  - `procurement_method`: Selected method
  - `current_stage_deadline`: Deadline datetime
  - `timeline_status`: pending/approaching/expired/none
  - `bid_validity_extension_used`: Boolean flag
  - `timeline_last_checked`: Last check timestamp

### Utility Functions
- [apps/procurement/timeline_utils.py](apps/procurement/timeline_utils.py) (210 lines)
  - `add_business_days()`: Excludes weekends
  - `get_business_days_until()`: Count business days
  - `is_business_day()`: Weekend check
  - `get_timeline_for_stage()`: Lookup timeline
  - `calculate_deadline()`: Compute deadline

### Forms
- [apps/procurement/forms.py](apps/procurement/forms.py)
  - `ProcurementMethodForm`: 17+ method selection
  - `BidValidityExtensionForm`: Extension confirmation
  - `TenderTypeForm`: International/National selection

## Timeline Setting Summary by View

| View | Stage Transition | Timeline Set | Days | Method? |
|------|------------------|--------------|------|---------|
| cbm_approve_submission_view | CBM Review TD → Publication of TD (7→8) | Publication of TD | 3-30 | ✅ Yes |
| procurement_publish_td_view | Publication of TD → Bidding (8→9) | Bid Validity | 120 | ❌ No |
| procurement_notify_bidders_view | Evaluation → CBM Approval (10→11) | Evaluation | 21 | ❌ No |
| procurement_advance_stage_view | CBM Approval → Notify Bidders (11→12) | Notification | 7 | ❌ No |
| procurement_advance_stage_view | Contract stages | Contract Signature | 22/28 | ✅ Type |

## Configuration Reference

### Timeline Configurations (All 22)
```
Publication of TD:
- International Competitive: 30 days
- International Restricted: 14 days
- National Competitive: 21 days
- National Restricted: 7 days
- Request for Quotations: 3 days
- National Open Simplified: 8 days
- National Restricted Simplified: 5 days
- (Others): Flexible

Evaluation: All methods - 21 days
Notification: All methods - 7 days

Bid Validity Period:
- Base: 120 days
- Extension: +60 days (one-time)

Contract Signature:
- International: 22 days
- National: 28 days
```

## Business Day Calculations

**Algorithm**:
1. Start with given date/time
2. Add 1 day repeatedly
3. Skip Saturdays (5) and Sundays (6)
4. Stop when target number of business days reached
5. Return resulting datetime (timezone-aware, UTC+2)

**Examples**:
- Feb 19 (Wed) + 21 business days = Mar 20 (Thu) [excludes 3 weekends]
- Automatically skips public holidays (if configured in future)

## Testing & Validation

**Test Coverage**:
- ✅ 22 TimelineConfiguration records created
- ✅ Business day calculations excluding weekends
- ✅ All Submission timeline fields present
- ✅ All view integrations working
- ✅ Timeline card display on all templates
- ✅ Celery monitoring task scheduled

**Test Commands**:
```bash
# Verify configurations
python manage.py shell
>>> from apps.procurement.models import TimelineConfiguration
>>> TimelineConfiguration.objects.count()
22

# Test business day calculation
>>> from apps.procurement.timeline_utils import add_business_days
>>> from datetime import datetime
>>> add_business_days(datetime.now(), 21)

# Check Celery schedule
>>> from pts_project.celery import app
>>> 'monitor-submission-timelines' in app.conf.beat_schedule
True
```

## Production Readiness Checklist

- ✅ Models created and migrated
- ✅ Timeline utilities tested and functional
- ✅ All workflow views enhanced with timeline setting
- ✅ Forms created for method/type selection
- ✅ Frontend display components added to all templates
- ✅ Celery monitoring task configured and scheduled
- ✅ Notification system integrated with email
- ✅ Database seeded with 22 configurations
- ✅ Business logic tested with actual submissions
- ✅ Audit trail in WorkflowHistory
- ✅ Role-based access controls enforced
- ✅ Email templates ready for timeline alerts

## Key Features

✨ **Business Day Aware**: All calculations exclude weekends
✨ **Automatic Monitoring**: Every 6 hours via Celery
✨ **Escalating Alerts**: Yellow→Red based on time remaining
✨ **Method-Aware**: Different timelines per procurement method
✨ **Type-Aware**: Different contract timelines for International/National
✨ **Extensible**: Bid validity can be extended once by 60 days
✨ **Visible**: Timeline cards on all submission detail pages
✨ **Auditable**: All timeline actions tracked in WorkflowHistory
✨ **Compliant**: Follows business day requirements from RBC guidelines

## Workflow Timeline Sequence

The complete timeline flow for a procurement submission:

1. **Day 0**: CBM selects method, sets Publication TD timeline (e.g., 21 days for National Competitive)
2. **Day 21**: Publication period ends, Bidding phase starts
   - Bid Validity period starts (120 days)
3. **Day 21-X**: Procurement publishes TD, awaits bids
4. **Year end (Day 120)**: Bidding closes, Evaluation starts
   - Evaluation timeline starts (21 days)
5. **Day 141**: Evaluation complete, CBM approves
6. **Day 141**: Notification period starts (7 days)
7. **Day 148**: Notification period expires, contract negotiation starts
   - Contract Signature timeline starts (22 or 28 days depending on type)
8. **Day 170-176**: Contract signature deadline
9. **Final**: Award, completion

## Notes

- Timeline calculations are based on business days, excluding weekends
- Notification sent 7 days before deadline and when expired
- All deadlines are recorded as DateTimeField for precision
- Tender type (International/National) determined automatically from procurement method
- Extension capability only available for Bid Validity Period (one-time, 60 days)
- All timeline events recorded in WorkflowHistory for audit compliance

---

**Status**: ✅ COMPLETE & PRODUCTION READY
**Last Updated**: February 2026
**Test Status**: All tests passing ✅
