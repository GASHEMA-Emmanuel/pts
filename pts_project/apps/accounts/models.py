"""
User and Role models for PTS.
Implements RBAC as specified in the SRD.
"""
import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
from apps.core.models import TimestampMixin


class Role(models.Model):
    """
    Role model for RBAC.
    Predefined roles: Admin, CBM, HOD/DM, Procurement Team, Division User
    """
    ROLE_CHOICES = [
        ('Admin', 'System Administrator'),
        ('CBM', 'Chief Budget Manager'),
        ('HOD/DM', 'Head of Department / Division Manager'),
        ('Procurement Team', 'Procurement Team'),
        ('Division User', 'Division User'),
    ]
    
    id = models.AutoField(primary_key=True, db_column='role_id')
    name = models.CharField(
        max_length=50,
        choices=ROLE_CHOICES,
        unique=True,
        db_column='role_name'
    )
    description = models.TextField(blank=True, null=True)
    
    # Permission flags for quick checks
    can_create_calls = models.BooleanField(default=False)
    can_approve = models.BooleanField(default=False)
    can_submit = models.BooleanField(default=False)
    can_update_status = models.BooleanField(default=False)
    can_manage_users = models.BooleanField(default=False)
    can_view_all_divisions = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'roles'
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
    
    def __str__(self):
        return self.name
    
    @classmethod
    def get_default_permissions(cls, role_name):
        """Get default permissions for a role."""
        permissions = {
            'Admin': {
                'can_create_calls': True,
                'can_approve': True,
                'can_submit': True,
                'can_update_status': True,
                'can_manage_users': True,
                'can_view_all_divisions': True,
                'can_view_reports': True,
            },
            'CBM': {
                'can_create_calls': True,
                'can_approve': True,
                'can_submit': False,
                'can_update_status': True,
                'can_manage_users': False,
                'can_view_all_divisions': True,
                'can_view_reports': True,
            },
            'HOD/DM': {
                'can_create_calls': False,
                'can_approve': True,
                'can_submit': True,
                'can_update_status': False,
                'can_manage_users': False,
                'can_view_all_divisions': False,
                'can_view_reports': True,
            },
            'Procurement Team': {
                'can_create_calls': False,
                'can_approve': True,
                'can_submit': False,
                'can_update_status': True,
                'can_manage_users': False,
                'can_view_all_divisions': True,
                'can_view_reports': True,
            },
            'Division User': {
                'can_create_calls': False,
                'can_approve': False,
                'can_submit': True,
                'can_update_status': False,
                'can_manage_users': False,
                'can_view_all_divisions': False,
                'can_view_reports': False,
            },
        }
        return permissions.get(role_name, {})


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user."""
        if not email:
            raise ValueError('Email address is required')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, TimestampMixin):
    """
    Custom User model with email-based authentication.
    Aligned with the PTS database schema.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='user_id'
    )
    email = models.EmailField(unique=True, max_length=255)
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    
    # Role-based access
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        db_column='role_id'
    )
    
    # Division association
    division = models.ForeignKey(
        'divisions.Division',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        db_column='division_id'
    )
    
    # User status
    is_active = models.BooleanField(default=False)  # Requires admin activation
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    
    # Profile
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        blank=True,
        null=True
    )
    
    # Tracking
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    login_count = models.PositiveIntegerField(default=0)
    
    # Notification preferences
    email_notifications = models.BooleanField(default=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['full_name']
    
    def __str__(self):
        return f"{self.full_name} ({self.email})"
    
    @property
    def role_name(self):
        """Get the role name or 'No Role' if not assigned."""
        return self.role.name if self.role else 'No Role'
    
    @property
    def division_name(self):
        """Get the division name or 'No Division' if not assigned."""
        return self.division.name if self.division else 'No Division'
    
    def has_role(self, role_name):
        """Check if user has a specific role."""
        return self.role and self.role.name == role_name
    
    def can_access_division(self, division_id):
        """Check if user can access a specific division."""
        if not self.role:
            return False
        if self.role.can_view_all_divisions:
            return True
        return str(self.division_id) == str(division_id)
    
    def increment_login_count(self):
        """Increment login count."""
        self.login_count += 1
        self.save(update_fields=['login_count'])


class UserActivity(TimestampMixin):
    """
    Model to track user activities for audit purposes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    action = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    
    # Related object tracking
    content_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    
    class Meta:
        db_table = 'user_activities'
        verbose_name = 'User Activity'
        verbose_name_plural = 'User Activities'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.action} at {self.created_at}"
