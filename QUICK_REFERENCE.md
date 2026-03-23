# Alert System - Quick Reference Guide

## 🚀 Quick Start

### 1. Enable Alerts (One-Time Setup)
```bash
# Apply database migrations
python manage.py makemigrations alerts
python manage.py migrate alerts

# Create alert configurations in admin
# Go to http://localhost:8000/admin/alerts/alertconfiguration/
# Create 6 configurations for these alert types:
# - deadline_approaching (days_before_deadline: 7, days_in_stage: 14)
# - deadline_missed (days_before_deadline: 0, days_in_stage: 0)
# - stalled_submission (days_before_deadline: 0, days_in_stage: 14)
# - long_in_review (days_before_deadline: 0, days_in_stage: 30)
# - high_priority_stuck (days_before_deadline: 0, days_in_stage: 3)
# - budget_threshold (days_before_deadline: 0, days_in_stage: 0)
```

### 2. Start Background Services
```bash
# Terminal 1: Celery Beat (Scheduler)
celery -A pts_project beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Terminal 2: Celery Worker (Task Executor)
celery -A pts_project worker -l info
```

### 3. Configure Email (Optional but Recommended)
```python
# In settings.py
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
DEFAULT_FROM_EMAIL = 'noreply@pts.rbc.org'
```

---

## 📍 Key URLs

| URL | Purpose | Access |
|-----|---------|--------|
| `/alerts/` | View alerts | All users |
| `/alerts/history/` | Alert history | Admins |
| `/alerts/admin/config/` | Configure alerts | Admins |
| `/alerts/admin/statistics/` | View statistics | Admins |

---

## 🔔 Alert Types

| Type | Trigger | Severity | Recipients |
|------|---------|----------|------------|
| **Deadline Approaching** | 7 days before deadline | ⚠️ Warning | Division Head, Procurement |
| **Deadline Missed** | After deadline | 🔴 Critical | CBM, Procurement |
| **Stalled Submission** | 14+ days in stage | ⚠️ Warning | Division Head, Procurement |
| **Long in Review** | 30+ days under review | 🔴 Critical | CBM, Procurement |
| **High Priority Stuck** | Critical: 3+ days, High: 7+ days | 🔴 Critical | Division Head |
| **Budget Threshold** | Exceeds budget limit | ⚠️ Warning | Finance, Division Head |

---

## 💻 For Developers

### Create Alert Manually
```python
from apps.alerts.models import Alert
from apps.procurement.models import Submission

submission = Submission.objects.get(id='...')
alert = Alert.objects.create(
    submission=submission,
    alert_type='deadline_approaching',
    title='Deadline Approaching',
    description='This submission deadline is approaching',
    severity='warning'
)
```

### Run Task Manually
```bash
# In Django shell
python manage.py shell
from apps.alerts.tasks import check_cbm_review_deadlines
check_cbm_review_deadlines()
```

### Get User Alerts
```python
from apps.alerts.models import Alert

# Get unresolved alerts for user (role-based)
if request.user.role.name == 'Procurement Team':
    alerts = Alert.objects.filter(status='active', severity__in=['critical', 'warning'])
elif request.user.role.name == 'HOD':
    alerts = Alert.objects.filter(submission__division=request.user.division, status='active')
```

---

## 🎯 Admin Tasks

### Configure Alert Threshold
1. Go to `/admin/alerts/alertconfiguration/`
2. Click alert type to edit
3. Change `days_before_deadline` or `days_in_stage`
4. Check notification recipient boxes
5. Save changes

### View Alert Statistics
1. Go to `/alerts/admin/statistics/`
2. See alert trends and distribution
3. Identify most alerted submissions

### View Alert History
1. Go to `/alerts/history/`
2. Filter by type or severity
3. Click "View" to see details

---

## 👥 User Workflows

### Procurement Team
1. Navigate to `/alerts/`
2. See all critical/warning alerts
3. Click submission to view details
4. Click "Acknowledge" when reviewing
5. Click "Resolve" when completed

### HOD/DM
1. Navigate to `/alerts/`
2. See division-specific alerts
3. Follow up with submitter if needed
4. Mark as resolved when addressed

### CBM User
1. Navigate to `/alerts/`
2. See review-related alerts
3. Review submission immediately
4. Update status in system
5. Mark alert as resolved

### Admin
1. Navigate to `/alerts/admin/config/`
2. Review all alert configurations
3. Adjust thresholds as needed
4. View statistics at `/alerts/admin/statistics/`

---

## 🧪 Testing

### Test Deadline Alert
```python
from datetime import datetime, timedelta
from apps.procurement.models import Submission

submission = Submission.objects.first()
submission.cbm_review_deadline = datetime.now().date() + timedelta(days=5)
submission.save()
# Alert should be created (check database)
```

### Test Stalled Submission
```python
from datetime import datetime, timedelta
from apps.workflows.models import WorkflowHistory

# Create old workflow history entry
history = WorkflowHistory.objects.filter(submission__status='Under Review').first()
history.created_at = datetime.now() - timedelta(days=20)
history.save()
# Alert should be created on next check
```

### Test Email Sending
```python
from apps.alerts.tasks import send_deadline_alert_email
from apps.alerts.models import Alert

alert = Alert.objects.first()
send_deadline_alert_email(alert.submission, alert, config='test')
# Check email inbox or Django console
```

---

## 🔧 Troubleshooting

### Alerts Not Creating?
1. ✅ Check AlertConfiguration is enabled in admin
2. ✅ Verify Celery worker and beat are running
3. ✅ Check Django logs for errors
4. ✅ Run task manually to see error: `python manage.py shell` then `from apps.alerts.tasks import check_cbm_review_deadlines; check_cbm_review_deadlines()`

### Emails Not Sending?
1. ✅ Check email settings in settings.py
2. ✅ Test SMTP connection: `python manage.py shell` then `from django.core.mail import send_mail; send_mail(...)`
3. ✅ Check DEFAULT_FROM_EMAIL is set
4. ✅ Verify email credentials are correct

### Alerts Not Visible?
1. ✅ Check user role has appropriate permission
2. ✅ Verify Alert status is 'active'
3. ✅ Check division matches for HOD users
4. ✅ Clear browser cache

### Celery Tasks Not Running?
1. ✅ Verify Redis is running: `redis-cli ping` (should return PONG)
2. ✅ Check Celery worker output for errors
3. ✅ Check Celery beat output for schedule entries
4. ✅ Verify CELERY_BROKER_URL is correct in settings.py

---

## 📝 Database Queries

### Count Active Alerts
```sql
SELECT COUNT(*) FROM alerts WHERE status = 'active';
```

### Get Alerts by Severity
```sql
SELECT severity, COUNT(*) FROM alerts GROUP BY severity;
```

### Get Most Alerted Submissions
```sql
SELECT submission_id, COUNT(*) as alert_count FROM alerts 
GROUP BY submission_id ORDER BY alert_count DESC LIMIT 10;
```

### Get Pending Alerts by User Role
```sql
SELECT a.*, u.role_id FROM alerts a 
JOIN procurement_submission ps ON a.submission_id = ps.id 
JOIN accounts_user u ON ps.division_id = u.division_id 
WHERE a.status = 'active' AND u.role_id IN (SELECT id FROM core_role WHERE name = 'HOD');
```

---

## 📚 Key Files Reference

| File | Purpose |
|------|---------|
| `apps/alerts/models.py` | Alert, AlertConfiguration, AlertHistory models |
| `apps/alerts/views.py` | Dashboard, configuration, history views |
| `apps/alerts/tasks.py` | Celery tasks and email functions |
| `apps/alerts/signals.py` | Automatic alert creation on save |
| `templates/alerts/` | User and admin templates |
| `pts_project/settings.py` | Celery configuration and context processor |

---

## 🚨 Critical Settings

```python
# Celery
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
DEFAULT_FROM_EMAIL = 'noreply@pts.rbc.org'

# Alerts
INSTALLED_APPS = [..., 'apps.alerts', ...]
context_processors = [..., 'pts_project.context_processors.alerts_context', ...]
```

---

## 📞 Support

For issues or questions:
1. Check ALERTS_SYSTEM.md for detailed documentation
2. Review Django admin interface for configurations
3. Check logs: `tail -f logs/django.log`
4. Test components manually in Django shell
5. Review email template examples

---

## ✅ Production Checklist

- [ ] Database migrations applied
- [ ] AlertConfiguration objects created for all 6 types
- [ ] Celery beat and worker started
- [ ] Email settings configured
- [ ] Redis running and accessible
- [ ] Submission model deadline fields populated
- [ ] Test alert creation works
- [ ] Test email sending works
- [ ] Navigation shows alert badge
- [ ] Dashboard alerts visible
- [ ] Logs monitored for errors

---

**Ready to deploy!** All systems are go. 🚀
