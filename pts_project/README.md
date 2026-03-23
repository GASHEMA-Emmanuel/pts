# Procurement Tracking System (PTS)

A comprehensive procurement tracking system for Rwanda Biomedical Center (RBC), built with Django REST Framework. The system aligns with Rwanda's e-procurement platform (Umucyo) and RPPA guidelines.

## 🎯 Overview

The PTS tracks procurement activities through a structured 9-stage lifecycle:

1. **Call Issued** - CBM initiates procurement call
2. **Division Submitted** - Divisions submit their needs
3. **Under Review** - Submissions are being reviewed
4. **Approved** - Submission approved for procurement
5. **Published** - Published to Umucyo e-procurement
6. **Bidding** - Bidding period in progress
7. **Evaluation** - Bids under evaluation
8. **Awarded** - Contract awarded to winner
9. **Completed** - Procurement process completed

## 🏗️ Architecture

```
pts_project/
├── config/                 # Project configuration
│   ├── settings.py        # Django settings
│   ├── urls.py            # URL routing
│   ├── celery.py          # Celery configuration
│   └── wsgi.py            # WSGI entry point
├── apps/
│   ├── accounts/          # User management & authentication
│   ├── divisions/         # Organizational units
│   ├── procurement/       # Core procurement (calls, submissions, bids)
│   ├── workflows/         # 9-stage workflow tracking
│   ├── notifications/     # In-app and email notifications
│   ├── reports/           # Analytics and reporting
│   └── dashboard/         # Web interface views
├── templates/             # HTML templates
├── static/                # CSS, JS, images
└── requirements.txt       # Python dependencies
```

## 👥 User Roles (RBAC)

| Role | Permissions |
|------|-------------|
| **Admin** | Full system access, user management |
| **CBM** | Create calls, approve submissions, view all divisions |
| **HOD/DM** | Submit and approve within division |
| **Procurement Team** | Update status, manage workflow |
| **Division User** | Create submissions, support activities |

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- Redis (for Celery)
- Node.js (optional, for frontend development)

### Installation

1. **Clone and setup environment**
```bash
cd pts_project
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your database and email settings
```

3. **Setup database**
```bash
# Create PostgreSQL database
psql -U postgres
CREATE DATABASE pts_db;
CREATE USER pts_user WITH PASSWORD 'pts_password';
GRANT ALL PRIVILEGES ON DATABASE pts_db TO pts_user;
\q

# Run migrations
python manage.py migrate
```

4. **Seed initial data**
```bash
# Create roles, divisions, workflow stages
python manage.py seed_data

# With sample users for testing
python manage.py seed_data --with-sample-data
```

5. **Run development server**
```bash
python manage.py runserver
```

6. **Access the system**
- Web Interface: http://localhost:8000/dashboard/
- Admin Panel: http://localhost:8000/admin/
- API Documentation: http://localhost:8000/api/docs/

### Default Users (with --with-sample-data)

| Email | Password | Role |
|-------|----------|------|
| admin@rbc.gov.rw | admin123! | Admin |
| cbm@rbc.gov.rw | cbm123! | CBM |
| hod.rids@rbc.gov.rw | hod123! | HOD/DM |
| procurement@rbc.gov.rw | proc123! | Procurement Team |

## 📡 API Endpoints

### Authentication
```
POST /api/v1/auth/token/           # Get JWT token
POST /api/v1/auth/token/refresh/   # Refresh token
POST /api/v1/auth/registration/    # Register new user
```

### Procurement
```
GET/POST   /api/v1/procurement/calls/                 # List/Create calls
GET/PUT    /api/v1/procurement/calls/{id}/            # Get/Update call
POST       /api/v1/procurement/calls/{id}/activate/   # Activate call
POST       /api/v1/procurement/calls/{id}/extend/     # Extend deadline

GET/POST   /api/v1/procurement/submissions/           # List/Create submissions
POST       /api/v1/procurement/submissions/{id}/submit/   # Submit for review
POST       /api/v1/procurement/submissions/{id}/approve/  # Approve submission
POST       /api/v1/procurement/submissions/{id}/reject/   # Reject submission

GET/POST   /api/v1/procurement/bids/                  # List/Create bids
POST       /api/v1/procurement/bids/{id}/evaluate/    # Evaluate bid
POST       /api/v1/procurement/bids/{id}/select_winner/  # Select winner
```

### Workflows
```
GET        /api/v1/workflows/stages/          # List workflow stages
GET        /api/v1/workflows/summary/         # Get workflow summary
POST       /api/v1/workflows/transition/      # Transition submission
GET        /api/v1/workflows/deadlines/       # List deadlines
```

### Reports
```
GET        /api/v1/reports/dashboard/         # Dashboard metrics
GET        /api/v1/reports/analytics/         # Detailed analytics
GET        /api/v1/reports/compliance/        # Compliance report
GET        /api/v1/reports/export/            # Export data
```

## 🔔 Background Tasks (Celery)

Start Celery worker and beat scheduler:

```bash
# In separate terminals
celery -A config worker -l info
celery -A config beat -l info
```

Scheduled tasks:
- **08:00** - Check upcoming deadlines
- **09:00** - Check overdue submissions
- **18:00** - Send daily summary to CBM
- **Sunday 02:00** - Cleanup old notifications

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific app tests
pytest apps/procurement/tests/

# With coverage
pytest --cov=apps
```

## 📦 Project Structure Details

### Models Overview

**accounts/**
- `Role` - RBAC roles with permissions
- `User` - Custom user with role and division
- `UserActivity` - Activity audit log

**divisions/**
- `Division` - Organizational units (RIDS, HIV, MCCH, etc.)

**procurement/**
- `ProcurementCall` - Procurement announcements
- `Submission` - Division procurement requests
- `Bid` - Supplier bids
- `Comment` - Threaded comments
- `Attachment` - File attachments

**workflows/**
- `WorkflowStage` - 9 procurement stages
- `WorkflowHistory` - Audit trail
- `Deadline` - Stage deadlines

**notifications/**
- `Notification` - In-app notifications
- `NotificationPreference` - User preferences
- `EmailLog` - Email audit trail

## 🔒 Security Features

- JWT Authentication with token rotation
- Role-Based Access Control (RBAC)
- Division-based data isolation
- Audit trails for all actions
- CSRF protection
- XSS prevention
- SQL injection protection (Django ORM)

## 📝 License

Copyright © 2026 Rwanda Biomedical Center (RBC). All rights reserved.

## 📞 Support

For support, contact the RIDS division at RBC.
