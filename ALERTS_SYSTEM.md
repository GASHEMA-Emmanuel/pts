# Alert System - Implementation Summary

## Overview

A complete automated alerting and deadline management system has been successfully implemented for the Procurement Tracking System (PTS). This system provides:

1. **Automatic Alert Generation**: Alerts are created based on configurable thresholds (deadlines, stalled submissions, priority escalations)
2. **Role-Based Visibility**: Different user roles see relevant alerts for their responsibilities
3. **Email Notifications**: Critical alerts trigger email notifications to appropriate stakeholders
4. **Admin Configuration**: Administrators can configure alert types, thresholds, and notification recipients
5. **Alert Dashboard**: Users can view, acknowledge, and resolve alerts
6. **Daily Summary Emails**: Optional daily email summaries of all active alerts

---

## Completed Components

### 1. **Alert Models** (`apps/alerts/models.py`)

#### AlertConfiguration
- Defines alert types and thresholds
- Controls which roles receive notifications
- Configurable settings for email/in-app notifications
- Fields:
  - `alert_type`: Choice of 6 alert types (deadline_approaching, deadline_missed, stalled_submission, long_in_review, high_priority_stuck, budget_threshold)
  - `days_before_deadline`: Days before deadline to trigger alert (default: 7)
  - `days_in_stage`: Days in a stage before marking as stalled (default: 14)
  - `is_enabled`: Toggle to enable/disable alert type
  - `notify_division_head`, `notify_cbm`, `notify_procurement_team`: Recipient configuration

#### Alert
- Tracks individual alerts for submissions
- Status: active, acknowledged, resolved
- Severity: info, warning, critical
- Fields:
  - `submission`: FK to Submission
  - `alert_type`: Type of alert
  - `title`, `description`: Alert details
  - `severity`: Alert severity level
  - `status`: Current status
  - `acknowledged_by`, `acknowledged_at`: Acknowledgement tracking
  - `resolved_at`, `resolution_notes`: Resolution tracking
- Methods:
  - `acknowledge(user, notes)`: Mark as acknowledged
  - `resolve(notes)`: Mark as resolved
  - `is_active`: Property to check if alert is active

#### AlertHistory
- Immutable historical record of all alerts
- Used for auditing and analytics
- Never deleted, only created

### 2. **Alert Views** (`apps/alerts/views.py`)

#### User Views
- **alert_dashboard_view**: Role-based alert dashboard showing active alerts grouped by severity
- **acknowledge_alert_view**: POST endpoint to acknowledge an alert
- **resolve_alert_view**: POST endpoint to resolve an alert
- **alert_history_view**: Admin-only view of all historical alerts

#### Admin Views
- **alert_configuration_view**: View all alert configurations
- **alert_configuration_edit_view**: Edit alert configuration thresholds and recipients
- **alert_statistics_view**: Dashboard showing alert trends, distribution by type/severity, and most alerted submissions

#### Access Control
- Function `can_manage_alert()` enforces role-based permissions
- Procurement Team sees critical/warning alerts
- HOD sees division-specific alerts
- CBM sees review-related alerts

### 3. **Alert Templates**

#### User Templates
- **`templates/alerts/dashboard.html`**: Main alert dashboard with:
  - Statistics cards (total, unresolved, critical, resolution rate)
  - Alerts grouped by severity (critical, warning, info)
  - Action buttons for acknowledge/resolve
  - Modal dialogs for adding notes
  - Color-coded severity badges

- **`templates/alerts/history.html`**: Historical alert records with:
  - Filter by alert type and severity
  - Paginated list (50 per page)
  - Detailed view modal for each record
  - Search and filter functionality

#### Admin Templates
- **`templates/alerts/admin_config.html`**: Configuration overview
  - Card layout for each alert type
  - Enable/disable toggles
  - Threshold display
  - Recipient configuration display

- **`templates/alerts/admin_config_edit.html`**: Edit alert configuration
  - Form for updating thresholds
  - Checkboxes for enabling/disabling features
  - Recipient role selection
  - Save/cancel buttons

- **`templates/alerts/admin_statistics.html`**: Alert analytics
  - Summary cards (total, active, resolved, resolution rate)
  - Alerts by type (pie/bar)
  - Alerts by severity (pie/bar)
  - Recent alerts list
  - Most alerted submissions list

### 4. **Email Templates**

#### Automated Email Notifications
- **`templates/emails/deadline_alert.html`**: Notification for approaching/missed deadlines
  - Submission details
  - Deadline information
  - Action required message
  - Link to submission in system

- **`templates/emails/stalled_submission.html`**: Notification for stalled submissions
  - Submission details
  - Stage name and days in stage
  - Escalation instruction
  - Link to take action

- **`templates/emails/escalation_notice.html`**: Critical priority escalation
  - Bold "ESCALATION NOTICE" header
  - High/critical priority indication
  - Days pending counter
  - Requires immediate action
  - Escalation link for team leads

- **`templates/emails/daily_summary.html`**: Daily alert summary
  - Alert count by severity
  - List of recent alerts
  - Quick action suggestions
  - Link to alert preferences

### 5. **Celery Background Tasks** (`apps/alerts/tasks.py`)

#### Deadline Alert Tasks
- **check_cbm_review_deadlines()**: Check for approaching CBM review deadlines
  - Runs daily at scheduled time
  - Creates alerts based on configured threshold
  - Marks as critical if deadline passed

- **check_procurement_deadlines()**: Check for approaching procurement deadlines
  - Monitors approved/published submissions
  - Alerts based on configured days_before_deadline

#### Submission Monitoring Tasks
- **check_stalled_submissions()**: Identify submissions stuck in stages
  - Checks days since last workflow history entry
  - Critical if 30+ days, warning if less
  - Identifies stage name and duration

- **check_high_priority_stuck()**: Monitor high/critical priority submissions
  - Critical: alert if pending 3+ days
  - High: alert if pending 7+ days
  - Automatic escalation to leadership

#### Summary Task
- **send_daily_alert_summary()**: Send daily digest emails
  - Groups alerts by role and division
  - Sends to Procurement Team, HOD/DM, etc.
  - Daily at scheduled time

#### Email Functions
- `send_deadline_alert_email()`: Email notification for deadline alerts
- `send_stalled_alert_email()`: Email notification for stalled submissions
- `send_priority_alert_email()`: Email notification for priority escalations
- `send_daily_summary_email()`: Email notification for daily summaries

### 6. **Signal-Based Auto-Detection** (`apps/alerts/signals.py`)

Automatic alert creation on submission changes:

- **check_deadline_alerts**: Triggered on submission save
  - Checks if deadline is approaching
  - Creates Alert objects automatically

- **check_stalled_submissions**: Triggered on submission save
  - Monitors workflow history
  - Flags submissions in stages too long

- **check_priority_alerts**: Triggered on submission save
  - Monitors high/critical priority submissions
  - Alerts if stuck in early stages

### 7. **Celery Beat Schedule** (Settings Configuration)

Added to `pts_project/settings.py`:

```python
CELERY_BEAT_SCHEDULE = {
    'check-cbm-review-deadlines': {
        'task': 'apps.alerts.tasks.check_cbm_review_deadlines',
        'schedule': 86400.0,  # Every 24 hours
    },
    'check-procurement-deadlines': {
        'task': 'apps.alerts.tasks.check_procurement_deadlines',
        'schedule': 86400.0,  # Every 24 hours
    },
    'check-stalled-submissions': {
        'task': 'apps.alerts.tasks.check_stalled_submissions',
        'schedule': 86400.0,  # Every 24 hours
    },
    'check-high-priority-stuck': {
        'task': 'apps.alerts.tasks.check_high_priority_stuck',
        'schedule': 86400.0,  # Every 24 hours
    },
    'send-daily-alert-summary': {
        'task': 'apps.alerts.tasks.send_daily_alert_summary',
        'schedule': 86400.0,  # Every 24 hours
    },
}
```

### 8. **Context Processor** (`pts_project/context_processors.py`)

- **alerts_context()**: Adds alert context to all templates
  - `unresolved_alerts_count`: Role-based alert count
  - `unread_notifications_count`: Unread notification count
  - Used in navigation to show badge counts

### 9. **URL Routes** (`apps/alerts/urls.py`)

```
/alerts/                              # Alert dashboard
/alerts/history/                       # Alert history
/alerts/<alert_id>/acknowledge/        # Acknowledge alert
/alerts/<alert_id>/resolve/           # Resolve alert
/alerts/admin/config/                  # Admin configuration
/alerts/admin/config/<config_id>/edit/ # Edit configuration
/alerts/admin/statistics/              # Alert statistics
```

### 10. **Database Models Registration** (`apps/alerts/admin.py`)

- **AlertConfigurationAdmin**: Manage alert type configurations
  - List view with status badges
  - Edit thresholds and recipients
  - Read-only (prevent deletion of core types)

- **AlertAdmin**: View and manage active alerts
  - List with severity/status badges
  - Search by submission reference
  - Filter by status, severity, type
  - Track acknowledgement and resolution

- **AlertHistoryAdmin**: Audit historical alerts
  - Read-only interface
  - Filter and search capabilities
  - No editing or deletion

### 11. **Navigation Integration**

Updated `templates/base.html`:
- Added "Alerts" link to sidebar navigation
- Badge showing unresolved alert count
- Alert dropdown in top navigation bar
- Shows quick access to alerts dashboard

### 12. **Deadline Fields in Submission Model**

Added to `apps/procurement/models.py`:
- `cbm_review_deadline`: DateField for CBM review deadline
- `procurement_deadline`: DateField for procurement completion deadline
- `expected_completion_date`: DateField for expected finish date
- `actual_completion_date`: DateField for actual completion tracking

---

## Alert Types

### 1. **Deadline Approaching** (deadline_approaching)
- Triggered when submission deadline is within configured days (default: 7 days)
- Severity: warning or critical based on deadline
- Recipients: Division Head, Procurement Team, or CBM based on deadline type

### 2. **Deadline Missed** (deadline_missed)
- Triggered when deadline has passed
- Severity: critical
- Immediate notification to stakeholders

### 3. **Stalled Submission** (stalled_submission)
- Triggered when submission is in a stage for configured days (default: 14 days)
- Severity: warning (14-29 days), critical (30+ days)
- Recipients: Division Head, Procurement Team

### 4. **Long in Review** (long_in_review)
- CBM submissions pending review for too long
- Severity: warning
- Recipients: CBM, Procurement Team

### 5. **High Priority Stuck** (high_priority_stuck)
- High or critical priority submissions stuck in early stages
- Critical: 3+ days, High: 7+ days
- Severity: critical
- Triggers escalation to leadership

### 6. **Budget Threshold** (budget_threshold)
- Submissions exceeding budget thresholds
- Severity: warning or critical based on overage
- Recipients: Finance, Division Head, Procurement Team

---

## Severity Levels

| Level | Color | Use Case |
|-------|-------|----------|
| **Info** | Blue | Informational updates, non-urgent |
| **Warning** | Yellow/Orange | Attention needed, upcoming deadline |
| **Critical** | Red | Urgent action required, missed deadline, escalation |

---

## User Roles and Alert Visibility

### Admin
- Sees all alerts
- Can view alert history
- Can configure alert types
- Can view statistics

### Procurement Team
- Sees critical and warning alerts
- Can acknowledge/resolve
- Receives deadline alerts
- Receives escalation notices

### HOD/DM
- Sees alerts for their division's submissions
- Can acknowledge/resolve
- Receives deadline alerts
- Receives stalled submission alerts

### CBM
- Sees review-related alerts
- Can acknowledge/resolve
- Receives deadline alerts for submissions under review

### Other Users
- Sees own submission alerts
- Can acknowledge/resolve
- Receives deadline alerts

---

## Email Notifications

Emails are sent automatically for:
- Approaching deadlines (7 days before by default)
- Missed deadlines (immediately)
- Stalled submissions (14 days in stage by default)
- High priority escalations (3+ days pending)
- Daily summary (once per day at configured time)

Email recipients are configured per alert type in `AlertConfiguration`.

---

## Admin Configuration

Administrators can configure:
- Alert thresholds (days before deadline, days in stage)
- Enable/disable alert types
- Email notification settings
- Notification recipients (which roles receive alerts)

Configuration is done through Django admin interface or dedicated alert configuration page.

---

## Remaining Tasks

### Task 7: User Alert Preferences
Not yet implemented. Will allow users to:
- Choose which alert types they receive
- Select notification method (email, in-app, both)
- Set frequency (immediate, daily digest, weekly)
- Manage subscription to different alert categories

---

## Setup and Configuration

### 1. Run Migrations

```bash
python manage.py makemigrations alerts
python manage.py migrate alerts
```

### 2. Create Initial Alert Configurations

Use Django admin to create AlertConfiguration objects for each alert type:
- deadline_approaching
- deadline_missed
- stalled_submission
- long_in_review
- high_priority_stuck
- budget_threshold

### 3. Start Celery Beat

```bash
celery -A pts_project beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### 4. Start Celery Worker

```bash
celery -A pts_project worker -l info
```

### 5. Configure Email Settings

Ensure `settings.py` has proper email configuration:
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'your_email_host'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your_email'
EMAIL_HOST_PASSWORD = 'your_password'
DEFAULT_FROM_EMAIL = 'noreply@pts.rbc.org'
```

---

## Features and Benefits

✅ **Automatic Detection**: No manual alert creation needed
✅ **Role-Based**: Users see only relevant alerts
✅ **Configurable**: Admins can adjust thresholds and recipients
✅ **Email Integration**: Critical alerts sent via email
✅ **Audit Trail**: Complete history of all alerts
✅ **Escalation**: High-priority submissions automatically escalated
✅ **Dashboard**: Visual alert management interface
✅ **Analytics**: Admin statistics and trends
✅ **Flexible**: Can be enabled/disabled per alert type

---

## Technical Details

- **Framework**: Django 4.2.27
- **Task Queue**: Celery with Redis broker
- **Database**: Alert and AlertConfiguration models
- **Signals**: Automatic alert generation on model changes
- **Email**: Django email backend with HTML templates
- **UI**: Bootstrap 5 with custom styling
- **Context Processor**: Automatic badge count in navigation

---

## Future Enhancements

1. **User Preferences**: Allow users to customize which alerts they receive
2. **SMS Alerts**: Send SMS for critical alerts
3. **Slack Integration**: Send alerts to Slack channels
4. **Custom Rules**: Allow users to create custom alert rules
5. **Alert Grouping**: Group similar alerts together
6. **AI-Powered Insights**: Suggest action items based on alert patterns
7. **Performance Optimization**: Cache frequently accessed alerts
8. **Bulk Actions**: Acknowledge/resolve multiple alerts at once

---

## Testing Checklist

- [ ] Alert creation on deadline approach
- [ ] Email notifications sent to correct recipients
- [ ] Role-based alert visibility
- [ ] Admin configuration updates
- [ ] Acknowledge/resolve functionality
- [ ] Alert history tracking
- [ ] Daily summary emails
- [ ] Celery beat task execution
- [ ] Database migrations complete
- [ ] No errors in Django logs

---

## Database Schema

### Alert Table
```sql
CREATE TABLE alerts (
    id UUID PRIMARY KEY,
    submission_id UUID NOT NULL (FK to procurement_submission),
    alert_type VARCHAR(50),
    title VARCHAR(255),
    description TEXT,
    severity VARCHAR(20),
    status VARCHAR(20),
    acknowledged_by_id INT (FK to accounts_user),
    acknowledged_at DATETIME,
    acknowledgement_notes TEXT,
    resolved_at DATETIME,
    resolution_notes TEXT,
    created_at DATETIME,
    updated_at DATETIME
);
```

### AlertConfiguration Table
```sql
CREATE TABLE alert_configurations (
    id UUID PRIMARY KEY,
    alert_type VARCHAR(50) UNIQUE,
    description TEXT,
    days_before_deadline INT,
    days_in_stage INT,
    is_enabled BOOLEAN,
    send_email BOOLEAN,
    send_notification BOOLEAN,
    notify_division_head BOOLEAN,
    notify_cbm BOOLEAN,
    notify_procurement_team BOOLEAN,
    created_at DATETIME,
    updated_at DATETIME
);
```

### AlertHistory Table
```sql
CREATE TABLE alert_history (
    id UUID PRIMARY KEY,
    submission_id UUID NOT NULL (FK to procurement_submission),
    alert_type VARCHAR(50),
    title VARCHAR(255),
    severity VARCHAR(20),
    triggered_reason TEXT,
    created_at DATETIME
);
```

---

## Support and Troubleshooting

### Alerts Not Creating?
- Check if AlertConfiguration for that type is enabled
- Verify Celery beat is running
- Check Django logs for errors

### Emails Not Sending?
- Verify email configuration in settings
- Check EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER credentials
- Ensure DEFAULT_FROM_EMAIL is configured

### Alerts Not Visible?
- Verify user role has appropriate access
- Check if Alert status is 'active'
- Verify filters aren't hiding alerts

---

*System implemented: 2026*
*Version: 1.0*
