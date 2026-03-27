"""
Admin configuration for accounts app.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from .models import Role, UserActivity

User = get_user_model()


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'can_create_calls', 'can_approve', 'can_submit', 'can_manage_users']
    list_filter = ['can_create_calls', 'can_approve', 'can_manage_users']
    search_fields = ['name']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'full_name', 'role', 'division', 'is_active', 'is_verified']
    list_filter = ['is_active', 'is_verified', 'role', 'division']
    search_fields = ['email', 'full_name']
    ordering = ['email']
    actions = ['activate_users', 'deactivate_users']

    @admin.action(description='Activate selected users')
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} user(s) successfully activated.')

    @admin.action(description='Deactivate selected users')
    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} user(s) successfully deactivated.')
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'phone_number', 'profile_picture')}),
        ('Role & Division', {'fields': ('role', 'division')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified')}),
        ('Preferences', {'fields': ('email_notifications',)}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'password1', 'password2', 'role', 'division'),
        }),
    )
    
    readonly_fields = ['last_login', 'created_at', 'updated_at', 'login_count']


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'ip_address', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['user__email', 'user__full_name', 'description']
    readonly_fields = ['user', 'action', 'description', 'ip_address', 'user_agent', 'created_at']
    ordering = ['-created_at']
