"""
Views for alert management and dashboard.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.db.models import Q, Count
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from .models import Alert, AlertConfiguration, AlertHistory
from apps.procurement.models import Submission


@login_required
def alert_dashboard_view(request):
    """
    User alert dashboard showing all their active alerts.
    """
    user = request.user
    
    # Get user's active alerts based on their role
    if user.role.name == 'Procurement Team':
        # Procurement team sees all critical alerts
        alerts = Alert.objects.filter(
            status='active',
            severity__in=['critical', 'warning']
        ).select_related('submission').order_by('-created_at')
    elif user.role.name == 'HOD':
        # HOD sees alerts for their division's submissions
        alerts = Alert.objects.filter(
            submission__division=user.division,
            status='active'
        ).select_related('submission').order_by('-created_at')
    elif user.role.name == 'CBM':
        # CBM sees alerts for submissions they're reviewing
        alerts = Alert.objects.filter(
            submission__status__in=['Under Review'],
            status='active'
        ).select_related('submission').order_by('-created_at')
    else:
        # Others see their own alerts
        alerts = Alert.objects.filter(
            submission__submitted_by=user,
            status='active'
        ).select_related('submission').order_by('-created_at')
    
    # Filter by status if provided
    status_filter = request.GET.get('status', '')
    if status_filter:
        alerts = alerts.filter(status=status_filter)
    
    # Filter by severity if provided
    severity_filter = request.GET.get('severity', '')
    if severity_filter:
        alerts = alerts.filter(severity=severity_filter)
    
    # Group by severity
    alert_groups = {
        'critical': alerts.filter(severity='critical'),
        'warning': alerts.filter(severity='warning'),
        'info': alerts.filter(severity='info'),
    }
    
    # Statistics
    total_alerts = alerts.count()
    unresolved_count = alerts.filter(status='active').count()
    
    context = {
        'alerts': alerts,
        'alert_groups': alert_groups,
        'total_alerts': total_alerts,
        'unresolved_count': unresolved_count,
        'status_filter': status_filter,
        'severity_filter': severity_filter,
    }
    
    return render(request, 'alerts/dashboard.html', context)


@login_required
@require_http_methods(['POST'])
def acknowledge_alert_view(request, alert_id):
    """
    Mark alert as acknowledged.
    """
    alert = get_object_or_404(Alert, id=alert_id)
    
    # Check permissions
    if not can_manage_alert(request.user, alert):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    notes = request.POST.get('notes', '')
    alert.acknowledge(request.user, notes)
    
    messages.success(request, f"Alert acknowledged")
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'alert_id': str(alert.id)})
    
    return redirect('alert_dashboard')


@login_required
@require_http_methods(['POST'])
def resolve_alert_view(request, alert_id):
    """
    Mark alert as resolved.
    """
    alert = get_object_or_404(Alert, id=alert_id)
    
    # Check permissions
    if not can_manage_alert(request.user, alert):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    notes = request.POST.get('notes', '')
    alert.resolve(notes)
    
    messages.success(request, f"Alert resolved")
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'alert_id': str(alert.id)})
    
    return redirect('alert_dashboard')


@user_passes_test(lambda u: u.is_staff)
def alert_history_view(request):
    """
    View historical alerts for auditing and analysis.
    """
    # Only admins can view alert history
    if request.user.role.name != 'Admin':
        messages.error(request, 'You do not have permission to view alert history')
        return redirect('dashboard')
    
    history = AlertHistory.objects.select_related('submission').order_by('-created_at')
    
    # Filter by alert type
    alert_type = request.GET.get('alert_type', '')
    if alert_type:
        history = history.filter(alert_type=alert_type)
    
    # Filter by severity
    severity = request.GET.get('severity', '')
    if severity:
        history = history.filter(severity=severity)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(history, 50)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)
    
    context = {
        'page_obj': page_obj,
        'alert_type': alert_type,
        'severity': severity,
    }
    
    return render(request, 'alerts/history.html', context)


@user_passes_test(lambda u: u.is_staff)
def alert_configuration_view(request):
    """
    Admin view for configuring alert rules.
    """
    configs = AlertConfiguration.objects.all().order_by('alert_type')
    
    context = {
        'configurations': configs,
    }
    
    return render(request, 'alerts/admin_config.html', context)


@user_passes_test(lambda u: u.is_staff)
def alert_configuration_edit_view(request, config_id):
    """
    Edit alert configuration.
    """
    config = get_object_or_404(AlertConfiguration, id=config_id)
    
    if request.method == 'POST':
        # Update configuration
        config.description = request.POST.get('description', config.description)
        config.days_before_deadline = int(request.POST.get('days_before_deadline', config.days_before_deadline))
        config.days_in_stage = int(request.POST.get('days_in_stage', config.days_in_stage))
        config.is_enabled = request.POST.get('is_enabled') == 'on'
        config.send_email = request.POST.get('send_email') == 'on'
        config.send_notification = request.POST.get('send_notification') == 'on'
        config.notify_division_head = request.POST.get('notify_division_head') == 'on'
        config.notify_cbm = request.POST.get('notify_cbm') == 'on'
        config.notify_procurement_team = request.POST.get('notify_procurement_team') == 'on'
        config.save()
        
        messages.success(request, f"Alert configuration updated")
        return redirect('alert_configuration')
    
    context = {
        'config': config,
    }
    
    return render(request, 'alerts/admin_config_edit.html', context)


@user_passes_test(lambda u: u.is_staff)
def alert_statistics_view(request):
    """
    Admin dashboard showing alert statistics and trends.
    """
    # Total alerts statistics
    total_alerts = Alert.objects.count()
    active_alerts = Alert.objects.filter(status='active').count()
    resolved_alerts = Alert.objects.filter(status='resolved').count()
    
    # Calculate resolution rate
    if total_alerts > 0:
        resolution_rate = (resolved_alerts / total_alerts) * 100
    else:
        resolution_rate = 0
    
    # Alerts by type
    alerts_by_type = Alert.objects.values('alert_type').annotate(count=Count('id')).order_by('-count')
    
    # Alerts by severity
    alerts_by_severity = Alert.objects.values('severity').annotate(count=Count('id')).order_by('-count')
    
    # Recent alerts
    recent_alerts = Alert.objects.select_related('submission').order_by('-created_at')[:10]
    
    # Most alerted submissions
    most_alerted = Submission.objects.annotate(
        alert_count=Count('alerts')
    ).filter(alert_count__gt=0).order_by('-alert_count')[:10]
    
    context = {
        'total_alerts': total_alerts,
        'active_alerts': active_alerts,
        'resolved_alerts': resolved_alerts,
        'resolution_rate': resolution_rate,
        'alerts_by_type': alerts_by_type,
        'alerts_by_severity': alerts_by_severity,
        'recent_alerts': recent_alerts,
        'most_alerted': most_alerted,
    }
    
    return render(request, 'alerts/admin_statistics.html', context)


def can_manage_alert(user, alert):
    """
    Check if user can manage (acknowledge/resolve) an alert.
    """
    if user.role.name == 'Admin':
        return True
    
    if user.role.name == 'Procurement Team':
        return alert.severity in ['critical', 'warning']
    
    if user.role.name == 'HOD':
        return alert.submission.division == user.division
    
    if user.role.name == 'CBM':
        return alert.submission.status == 'Under Review'
    
    return alert.submission.submitted_by == user


@login_required
@require_http_methods(['POST'])
def attention_dismiss_view(request):
    """
    Called via AJAX when the user closes the attention modal.
    Clears the session flag so the modal doesn't appear again until next login.
    """
    request.session.pop('pts_attention_pending', None)
    return JsonResponse({'status': 'ok'})
