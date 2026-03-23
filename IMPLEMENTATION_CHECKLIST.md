# Alert System Implementation Checklist

## Completed Implementation

### ✅ Models Created (Task 1)
- [x] Alert model with fields: submission, alert_type, title, description, severity, status, acknowledged_by, acknowledged_at, resolved_at, resolution_notes
- [x] AlertConfiguration model with fields: alert_type, days_before_deadline, days_in_stage, is_enabled, send_email, notify_roles
- [x] AlertHistory model for audit trail
- [x] Model methods: acknowledge(), resolve(), is_active property
- [x] Database indexes on status, severity, created_at
- [x] Admin registration for all three models

### ✅ Views Created (Task 2)
- [x] alert_dashboard_view: Role-based alert dashboard with severity grouping
- [x] acknowledge_alert_view: POST endpoint to mark alert acknowledged
- [x] resolve_alert_view: POST endpoint to mark alert resolved
- [x] alert_history_view: Admin-only historical records view
- [x] alert_configuration_view: View all alert configurations
- [x] alert_configuration_edit_view: Edit configuration thresholds
- [x] alert_statistics_view: Admin dashboard with trends and analytics
- [x] can_manage_alert(): Permission function for role-based access

### ✅ Templates Created (Task 3)
- [x] alerts/dashboard.html: User alert dashboard with filters and modals
- [x] alerts/history.html: Paginated alert history with filters
- [x] alerts/admin_config.html: Configuration overview for admins
- [x] alerts/admin_config_edit.html: Edit configuration form
- [x] alerts/admin_statistics.html: Analytics and trends dashboard

### ✅ Celery Tasks Implemented (Task 4)
- [x] check_cbm_review_deadlines(): Check approaching CBM review deadlines
- [x] check_procurement_deadlines(): Check procurement completion deadlines
- [x] check_stalled_submissions(): Identify submissions stuck in stages
- [x] check_high_priority_stuck(): Monitor critical/high priority submissions
- [x] send_daily_alert_summary(): Daily digest emails
- [x] Support functions: send_deadline_alert_email(), send_stalled_alert_email(), send_priority_alert_email(), send_daily_summary_email()
- [x] Celery beat schedule configured in settings.py

### ✅ Email Templates Created (Task 5)
- [x] templates/emails/deadline_alert.html: Deadline approaching notification
- [x] templates/emails/stalled_submission.html: Stalled submission notification
- [x] templates/emails/escalation_notice.html: Critical priority escalation
- [x] templates/emails/daily_summary.html: Daily alert summary digest

### ✅ Integration and Navigation (Task 6)
- [x] Context processor (pts_project/context_processors.py) for alert badge counts
- [x] Updated settings.py to include context processor
- [x] Updated base.html navigation with Alerts link and badge
- [x] Updated top navbar with alert dropdown
- [x] Added signal handlers for automatic alert creation
- [x] URL routes configured in apps/alerts/urls.py
- [x] Main project URLs include alerts app
- [x] Alerts app added to INSTALLED_APPS in settings.py

### ✅ Database and Configuration
- [x] Migration folder created for alerts app
- [x] Admin.py configured with custom admin classes
- [x] Apps.py configured with signals import
- [x] Settings.py updated with CELERY_BEAT_SCHEDULE
- [x] Deadline fields added to Submission model (cbm_review_deadline, procurement_deadline, expected_completion_date, actual_completion_date)

---

## File Summary

### New Files Created
```
apps/alerts/
  ├── __init__.py
  ├── admin.py              (AlertConfigurationAdmin, AlertAdmin, AlertHistoryAdmin)
  ├── apps.py               (AlertsConfig)
  ├── models.py             (Alert, AlertConfiguration, AlertHistory)
  ├── signals.py            (Alert auto-creation handlers)
  ├── tasks.py              (Celery tasks and email functions)
  ├── urls.py               (URL routes)
  ├── views.py              (Dashboard, configuration, history views)
  └── migrations/
      └── __init__.py

templates/alerts/
  ├── dashboard.html        (User alert dashboard)
  ├── history.html          (Alert history records)
  ├── admin_config.html     (Configuration overview)
  ├── admin_config_edit.html (Edit configuration)
  └── admin_statistics.html (Alert analytics)

templates/emails/
  ├── deadline_alert.html        (Deadline notification)
  ├── stalled_submission.html    (Stalled notification)
  ├── escalation_notice.html     (Priority escalation)
  └── daily_summary.html         (Daily digest)

pts_project/
  └── context_processors.py (Alert context for all templates)

ALERTS_SYSTEM.md (Documentation)
```

### Modified Files
```
pts_project/settings.py
  - Added 'apps.alerts' to INSTALLED_APPS
  - Added alerts_context to context_processors
  - Added CELERY_BEAT_SCHEDULE configuration

pts_project/urls.py
  - Added alerts URL include

apps/procurement/models.py
  - Added deadline fields to Submission model

templates/base.html
  - Added Alerts navigation link with badge
  - Updated notification dropdown to show alerts
```

---

## Configuration Required

### 1. Initial Setup
```bash
# Create migrations
python manage.py makemigrations alerts

# Apply migrations
python manage.py migrate alerts
```

### 2. Create Alert Configurations
- Use Django admin (/admin/alerts/alertconfiguration/)
- Create entries for each alert type:
  - deadline_approaching
  - deadline_missed
  - stalled_submission
  - long_in_review
  - high_priority_stuck
  - budget_threshold

### 3. Start Background Services
```bash
# Terminal 1: Celery Beat (scheduler)
celery -A pts_project beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Terminal 2: Celery Worker (task executor)
celery -A pts_project worker -l info
```

### 4. Email Configuration
Ensure these settings in settings.py:
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'  # or your email provider
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@example.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
DEFAULT_FROM_EMAIL = 'noreply@pts.rbc.org'
```

---

## Testing

### Unit Tests to Add
- [ ] Test alert creation on deadline approach
- [ ] Test alert creation for stalled submissions
- [ ] Test alert visibility by role
- [ ] Test acknowledge/resolve functionality
- [ ] Test email notification sending
- [ ] Test Celery beat task execution
- [ ] Test context processor adds badge count
- [ ] Test admin configuration updates

### Manual Testing Steps
1. Create a submission with cbm_review_deadline set to tomorrow
2. Run `check_cbm_review_deadlines` task manually
3. Check if Alert object was created
4. Log in as different roles and verify alert visibility
5. Click acknowledge button and verify status changes
6. Verify email was sent (check SMTP logs or email service)
7. Check alert count badge in navigation

---

## Usage Examples

### For End Users
1. Navigate to /alerts/ to see active alerts
2. Click "Acknowledge" to mark as seen
3. Click "Resolve" to mark as completed
4. Click on submission reference to view details
5. View history at /alerts/history/

### For Administrators
1. Visit /alerts/admin/config/ to view all alert configurations
2. Click "Edit Configuration" to adjust thresholds
3. Toggle notification recipients as needed
4. View statistics at /alerts/admin/statistics/
5. Monitor alert trends and most-alerted submissions

---

## Performance Considerations

- Alert queries use select_related() for FK optimization
- Context processor queries are cached during request
- Database indexes on frequently filtered fields (status, severity, created_at)
- Celery tasks run asynchronously to avoid blocking requests
- Email sending is non-blocking (fail_silently=True)

---

## Security

- Role-based access control prevents unauthorized alert access
- Admin-only views protected with staff_required decorator
- CSRF protection on all POST endpoints
- Email headers sanitized to prevent injection
- Permission checks in can_manage_alert() function

---

## Next Steps (Task 7)

### User Alert Preferences
Remaining task to implement:
- Add UserAlertPreference model to accounts app
- Create user preference settings page
- Filter alerts based on user preferences
- Allow users to choose notification methods and frequency

---

## Support Resources

- See ALERTS_SYSTEM.md for detailed documentation
- Check Django admin for alert configuration
- Review logs for Celery task execution
- Verify email settings if notifications not sending
- Test signal handlers by saving submission with deadline

---

**Status**: ✅ Complete (6 of 7 tasks done)
**Remaining**: User alert preferences configuration
**Ready for**: Migration, testing, and production deployment
