"""
Email template generators for professional HTML emails.
"""
from django.conf import settings
from django.urls import reverse


def get_login_url(user):
    """Get the login URL for the user."""
    return f"{settings.SITE_URL or 'http://127.0.0.1:8000'}/login/"


def generate_email_html(title, message, action_url=None, user=None, notification_type=None):
    """
    Generate a professional HTML email template.
    """
    login_url = get_login_url(user) if user else f"{settings.SITE_URL or 'http://127.0.0.1:8000'}/login/"
    
    # Customize button text based on notification type
    button_text = "View Details"
    if notification_type == 'procurement_call':
        button_text = "View Procurement Call"
    elif notification_type == 'submission_status':
        button_text = "View Submission"
    elif notification_type == 'approval_required':
        button_text = "Review & Approve"
    
    action_button = ""
    if action_url:
        full_action_url = f"{settings.SITE_URL or 'http://127.0.0.1:8000'}{action_url}"
        action_button = f'''
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 20px;">
            <tr>
                <td>
                    <a href="{full_action_url}" style="background-color: #2563eb; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        {button_text}
                    </a>
                </td>
            </tr>
        </table>
        '''
    
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>[PTS] {title}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                background-color: #f9fafb;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
                color: white;
                padding: 30px 20px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
                font-weight: bold;
            }}
            .logo {{
                font-size: 14px;
                opacity: 0.9;
                margin-top: 5px;
            }}
            .content {{
                padding: 30px 20px;
            }}
            .greeting {{
                font-size: 16px;
                margin-bottom: 20px;
                color: #1f2937;
            }}
            .message {{
                font-size: 15px;
                line-height: 1.8;
                color: #374151;
                margin-bottom: 20px;
            }}
            .footer {{
                padding: 20px;
                background-color: #f3f4f6;
                border-top: 1px solid #e5e7eb;
                text-align: center;
                font-size: 12px;
                color: #6b7280;
            }}
            .footer-link {{
                color: #2563eb;
                text-decoration: none;
            }}
            .divider {{
                height: 1px;
                background-color: #e5e7eb;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <!-- Header -->
            <div class="header">
                <h1>📋 Procurement Tracking System</h1>
                <div class="logo">PTS - RBC</div>
            </div>
            
            <!-- Content -->
            <div class="content">
                <div class="greeting">
                    Hello,
                </div>
                
                <div class="message">
                    {message}
                </div>
                
                {action_button}
                
                <div class="divider"></div>
                
                <div style="background-color: #f0f9ff; border-left: 4px solid #2563eb; padding: 15px; border-radius: 4px; margin-bottom: 20px;">
                    <strong style="color: #1e40af;">💡 Quick Action</strong>
                    <p style="margin: 10px 0 0 0; font-size: 14px; color: #1f2937;">
                        Log in to your PTS account to see all details and take action:
                    </p>
                    <a href="{login_url}" style="color: #2563eb; text-decoration: none; font-weight: bold;">
                        Login to PTS →
                    </a>
                </div>
            </div>
            
            <!-- Footer -->
            <div class="footer">
                <p style="margin: 0 0 10px 0;">
                    This is an automated notification from the Procurement Tracking System.
                </p>
                <p style="margin: 0;">
                    © 2026 Rwanda Biomedical Centre (RBC). All rights reserved.<br>
                    <a href="{login_url}" class="footer-link">Login to PTS</a> | 
                    <a href="mailto:support@rbc.gov.rw" class="footer-link">Contact Support</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    '''
    
    return html


# Template generators for specific notification types

def generate_procurement_call_email(call_reference, call_title, deadline, user=None):
    """Generate email for new procurement call."""
    message = f'''
    <strong>A new procurement call has been issued:</strong>
    <br><br>
    <strong>Reference:</strong> {call_reference}<br>
    <strong>Title:</strong> {call_title}<br>
    <strong>Deadline:</strong> {deadline}
    <br><br>
    Please review the details and take necessary action if required.
    '''
    return generate_email_html(
        title=f"New Procurement Call: {call_reference}",
        message=message,
        action_url=f"/dashboard/hod/calls/",
        user=user,
        notification_type='procurement_call'
    )


def generate_submission_submitted_email(submission_ref, item_name, division, user=None):
    """Generate email for submission submitted to review."""
    message = f'''
    A new procurement submission has been submitted for review:
    <br><br>
    <strong>Submission Reference:</strong> {submission_ref}<br>
    <strong>Item:</strong> {item_name}<br>
    <strong>Submitted by:</strong> {division}
    <br><br>
    Please review the submission and provide feedback or approve it to proceed to the next stage.
    '''
    return generate_email_html(
        title=f"New Submission for Review: {submission_ref}",
        message=message,
        action_url=f"/dashboard/procurement/submissions/",
        user=user,
        notification_type='submission_status'
    )


def generate_submission_approved_email(submission_ref, item_name, next_stage, user=None):
    """Generate email for submission approval."""
    message = f'''
    Your procurement submission has been approved!
    <br><br>
    <strong>Submission Reference:</strong> {submission_ref}<br>
    <strong>Item:</strong> {item_name}<br>
    <strong>Next Stage:</strong> {next_stage}
    <br><br>
    Your submission is progressing smoothly through the approval workflow.
    '''
    return generate_email_html(
        title=f"Submission Approved: {submission_ref}",
        message=message,
        action_url=f"/dashboard/hod/submissions/",
        user=user,
        notification_type='submission_status'
    )


def generate_clarification_required_email(submission_ref, item_name, user=None):
    """Generate email for clarification request."""
    message = f'''
    Clarification is required for your submission:
    <br><br>
    <strong>Submission Reference:</strong> {submission_ref}<br>
    <strong>Item:</strong> {item_name}
    <br><br>
    <strong style="color: #dc2626;">⚠️ Action Required</strong>
    <br>
    Please review the feedback and provide the requested clarifications to move this submission forward.
    '''
    return generate_email_html(
        title=f"Clarification Required: {submission_ref}",
        message=message,
        action_url=f"/dashboard/hod/submissions/",
        user=user,
        notification_type='approval_required'
    )


def generate_tender_document_ready_email(submission_ref, item_name, user=None):
    """Generate email for tender document ready."""
    message = f'''
    The tender document is ready for review:
    <br><br>
    <strong>Submission Reference:</strong> {submission_ref}<br>
    <strong>Item:</strong> {item_name}
    <br><br>
    Please review the tender document and provide your feedback or approval.
    '''
    return generate_email_html(
        title=f"Tender Document Ready for Review: {submission_ref}",
        message=message,
        action_url=f"/dashboard/cbm/submissions/",
        user=user,
        notification_type='approval_required'
    )


def generate_generic_notification_email(title, message, action_url=None, user=None, notification_type=None):
    """Generate generic notification email."""
    return generate_email_html(
        title=title,
        message=message,
        action_url=action_url,
        user=user,
        notification_type=notification_type
    )
