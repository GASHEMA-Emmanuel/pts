"""
Signals for accounts app.
"""
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import UserActivity

User = get_user_model()


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    """
    Signal handler for user login.
    Logs the activity and updates login count.
    """
    # Get IP address
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    
    # Update user's last login IP and count
    user.last_login_ip = ip
    user.increment_login_count()
    
    # Create activity log
    UserActivity.objects.create(
        user=user,
        action='login',
        description=f'User logged in from IP: {ip}',
        ip_address=ip,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
    )

    # Flag that the attention modal should appear on the next page render
    request.session['pts_attention_pending'] = True


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    """
    Signal handler for user logout.
    """
    if user:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        UserActivity.objects.create(
            user=user,
            action='logout',
            description='User logged out',
            ip_address=ip
        )
