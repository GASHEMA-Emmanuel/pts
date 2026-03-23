"""
Context processors for adding global context to all templates.
"""
from django.db.models import Count


# ── Role-specific display metadata ──────────────────────────────────────────
_ROLE_META = {
    'CBM': {
        'label':    'CBM Dashboard',
        'icon':     'bi-shield-check',
        'color':    '#ef4444',
        'gradient': 'linear-gradient(135deg,#b91c1c 0%,#7f1d1d 100%)',
        'message':  (
            'Tenders and submissions are awaiting your review and approval. '
            'Please action these items immediately to keep procurement workflows moving forward.'
        ),
    },
    'HOD/DM': {
        'label':    'HOD / DM Dashboard',
        'icon':     'bi-building',
        'color':    '#ef4444',
        'gradient': 'linear-gradient(135deg,#b91c1c 0%,#7f1d1d 100%)',
        'message':  (
            'Your division has active procurement calls and returned submissions '
            'that need your attention. Respond immediately to keep your division on track.'
        ),
    },
    'Procurement Team': {
        'label':    'Procurement Dashboard',
        'icon':     'bi-clipboard2-data',
        'color':    '#ef4444',
        'gradient': 'linear-gradient(135deg,#b91c1c 0%,#7f1d1d 100%)',
        'message':  (
            'Awarded tenders need contracts, stalled submissions require action, and '
            'deadlines are approaching. Review each item and take appropriate steps.'
        ),
    },
    'Admin': {
        'label':    'Admin Dashboard',
        'icon':     'bi-gear-wide-connected',
        'color':    '#ef4444',
        'gradient': 'linear-gradient(135deg,#b91c1c 0%,#7f1d1d 100%)',
        'message':  (
            'System-wide items requiring immediate administrative oversight are listed below. '
            'These include critical contract issues, stalled workflows, and pending approvals.'
        ),
    },
}
_DEFAULT_META = {
    'label':    'My Dashboard',
    'icon':     'bi-person-circle',
    'color':    '#ef4444',
    'gradient': 'linear-gradient(135deg,#b91c1c 0%,#7f1d1d 100%)',
    'message':  'The following items from your activities require your immediate attention before you continue.',
}


def attention_modal_context(request):
    """
    Inject login-attention-modal data once per login session.
    The flag 'pts_attention_pending' is set by the user_logged_in signal.
    It is cleared when the user dismisses the modal via POST /alerts/attention/dismiss/.
    """
    empty = {
        'show_attention_modal':    False,
        'attention_items':         [],
        'attention_contracts':     [],
        'attention_pos':           [],
        'attention_procurement':   [],
        'attention_tenders':       [],
        'attention_submissions':   [],
        'attention_alerts_list':   [],
        'attention_critical':      0,
        'attention_warning':       0,
        'attention_info':          0,
        'attention_role_label':    '',
        'attention_role_icon':     '',
        'attention_role_color':    '',
        'attention_role_gradient': '',
        'attention_role_message':  '',
    }
    if not request.user.is_authenticated:
        return empty
    if not request.session.get('pts_attention_pending'):
        return empty

    try:
        from apps.alerts.attention import get_attention_items
        items = get_attention_items(request.user)
        if not items:
            request.session.pop('pts_attention_pending', None)
            return empty

        role      = getattr(getattr(request.user, 'role', None), 'name', '')
        meta      = _ROLE_META.get(role, _DEFAULT_META)

        context = dict(empty)
        context.update({
            'show_attention_modal':    True,
            'attention_items':         items,
            'attention_contracts':     [i for i in items if i['category'] == 'contract'],
            'attention_pos':           [i for i in items if i['category'] == 'po'],
            'attention_procurement':   [i for i in items if i['category'] == 'procurement'],
            'attention_tenders':       [i for i in items if i['category'] == 'tender'],
            'attention_submissions':   [i for i in items if i['category'] == 'submission'],
            'attention_alerts_list':   [i for i in items if i['category'] == 'alert'],
            'attention_critical':      sum(1 for i in items if i['severity'] == 'critical'),
            'attention_warning':       sum(1 for i in items if i['severity'] == 'warning'),
            'attention_info':          sum(1 for i in items if i['severity'] == 'info'),
            'attention_role_label':    meta['label'],
            'attention_role_icon':     meta['icon'],
            'attention_role_color':    meta['color'],
            'attention_role_gradient': meta['gradient'],
            'attention_role_message':  meta['message'],
        })
        return context
    except Exception:
        return empty


def alerts_context(request):
    """
    Add alert-related context to all templates.
    Includes unresolved alert count and unread notification count.
    """
    context = {
        'unresolved_alerts_count': 0,
        'unread_notifications_count': 0,
    }
    
    if request.user.is_authenticated:
        try:
            from apps.alerts.models import Alert
            
            # Get unresolved alerts based on user role
            if request.user.role.name == 'Procurement Team':
                # Procurement team sees critical/warning alerts
                context['unresolved_alerts_count'] = Alert.objects.filter(
                    status='active',
                    severity__in=['critical', 'warning']
                ).count()
            elif request.user.role.name == 'HOD':
                # HOD sees alerts for their division
                context['unresolved_alerts_count'] = Alert.objects.filter(
                    submission__division=request.user.division,
                    status='active'
                ).count()
            elif request.user.role.name == 'CBM':
                # CBM sees review alerts
                context['unresolved_alerts_count'] = Alert.objects.filter(
                    submission__status__in=['Under Review'],
                    status='active'
                ).count()
            else:
                # Others see their own alerts
                context['unresolved_alerts_count'] = Alert.objects.filter(
                    submission__submitted_by=request.user,
                    status='active'
                ).count()
            
            # Get unread notifications
            from apps.notifications.models import Notification
            context['unread_notifications_count'] = Notification.objects.filter(
                user=request.user,
                is_read=False
            ).count()
        except Exception as e:
            # If there's an error (e.g., missing tables), silently fail
            pass
    
    return context
