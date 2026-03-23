"""
Utility functions for procurement timeline management.
Handles calendar day calculations, timeline configurations, and deadline calculations.
"""
from datetime import datetime, timedelta
from django.utils import timezone


def add_calendar_days(start_date, num_days):
    """
    Add calendar days to a given date (including weekends).
    
    Args:
        start_date: datetime or date object
        num_days: number of calendar days to add
    
    Returns:
        datetime object with days added
    """
    if isinstance(start_date, datetime):
        return start_date + timedelta(days=num_days)
    else:
        current_date = datetime.combine(start_date, datetime.min.time())
        current_date = timezone.make_aware(current_date)
        return current_date + timedelta(days=num_days)


def get_calendar_days_until(start_date, end_date):
    """
    Calculate number of calendar days between two dates (including weekends).
    
    Args:
        start_date: datetime or date object
        end_date: datetime or date object
    
    Returns:
        Number of calendar days
    """
    if isinstance(start_date, datetime):
        current = start_date
    else:
        current = datetime.combine(start_date, datetime.min.time())
        current = timezone.make_aware(current)
    
    if isinstance(end_date, datetime):
        end = end_date
    else:
        end = datetime.combine(end_date, datetime.max.time())
        end = timezone.make_aware(end)
    
    delta = end - current
    return max(0, delta.days)


def is_calendar_day(date_obj):
    """
    Validate if a given date is valid.
    
    Args:
        date_obj: datetime or date object
    
    Returns:
        True if valid date
    """
    return isinstance(date_obj, (datetime, type(None))) or hasattr(date_obj, 'day')


# TIMELINE CONFIGURATION
# Maps procurement methods and workflow stages to their timelines (in calendar days including weekends)

PUBLICATION_TIMELINES = {
    'International Competitive': 30,
    'International Restricted': 14,
    'National Competitive': 21,
    'National Restricted': 7,
    'Request for Quotations': 3,
    'National Open Simplified': 8,
    'National Restricted Simplified': 5,
    'Prequalification': None,  # Not fixed
    'Single Source': None,
    'Force Account': None,
    'Two Stage Tendering': None,
    'Turnkey': None,
    'Community Participation': None,
    'Competitive Dialogue': None,
    'Design and Build': None,
    'Pre-financing': None,
    'Reverse Auctioning': None,
}

EVALUATION_TIMELINE = 21  # Max 21 days for all methods

NOTIFICATION_TIMELINE = 7  # 7 days for all methods

BID_VALIDITY_BASE = 120  # 120 days base (can extend +60 once)
BID_VALIDITY_EXTENSION = 60  # 60-day extension

# Contract signature timelines based on tender type
CONTRACT_SIGNATURE_TIMELINES = {
    'International': {
        'notification_days': 7,
        'security_days': 15,
        'total_days': 22,
    },
    'National': {
        'notification_days': 7,
        'security_days': 21,
        'total_days': 28,
    }
}

# Stage to timeline mapping
STAGE_TIMELINES = {
    'Publication of TD': {
        'key': 'publication',
        'uses_method': True,
        'default_timeline': PUBLICATION_TIMELINES,
    },
    'Evaluation': {
        'key': 'evaluation',
        'uses_method': False,
        'timeline': EVALUATION_TIMELINE,
    },
    'Notification': {
        'key': 'notification',
        'uses_method': False,
        'timeline': NOTIFICATION_TIMELINE,
    },
    'Bid Validity Period': {
        'key': 'bid_validity',
        'uses_method': False,
        'timeline': BID_VALIDITY_BASE,
        'extendable': True,
    },
    'Contract Signature': {
        'key': 'contract_signature',
        'uses_method': True,
        'default_timeline': CONTRACT_SIGNATURE_TIMELINES,
    }
}


def get_timeline_for_stage(stage_name, procurement_method=None, tender_type=None):
    """
    Get the timeline (in business days) for a specific stage.
    
    Args:
        stage_name: Name of the workflow stage
        procurement_method: Selected procurement method (if applicable)
        tender_type: 'International' or 'National' (for contract signature stage)
    
    Returns:
        Number of business days for the stage, or None if not fixed
    """
    if stage_name not in STAGE_TIMELINES:
        return None
    
    stage_config = STAGE_TIMELINES[stage_name]
    
    if stage_config.get('uses_method'):
        if stage_name == 'Publication of TD':
            if procurement_method and procurement_method in PUBLICATION_TIMELINES:
                return PUBLICATION_TIMELINES[procurement_method]
            return None
        elif stage_name == 'Contract Signature':
            if tender_type and tender_type in CONTRACT_SIGNATURE_TIMELINES:
                return CONTRACT_SIGNATURE_TIMELINES[tender_type]['total_days']
            return None
    else:
        return stage_config.get('timeline')
    
    return None


def calculate_deadline(start_date, stage_name, procurement_method=None, tender_type=None):
    """
    Calculate deadline for a stage.
    
    Args:
        start_date: When the stage starts
        stage_name: Name of the workflow stage
        procurement_method: Selected procurement method
        tender_type: 'International' or 'National'
    
    Returns:
        Datetime of the deadline, or None if timeline is not fixed
    """
    timeline_days = get_timeline_for_stage(stage_name, procurement_method, tender_type)
    
    if timeline_days is None:
        return None
    
    return add_calendar_days(start_date, timeline_days)
