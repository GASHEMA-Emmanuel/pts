"""
Serializers for User and Role models.
"""
from rest_framework import serializers
from dj_rest_auth.registration.serializers import RegisterSerializer
from django.contrib.auth import get_user_model
from .models import Role, UserActivity

User = get_user_model()


class RoleSerializer(serializers.ModelSerializer):
    """Serializer for Role model."""
    
    class Meta:
        model = Role
        fields = [
            'id', 'name', 'description',
            'can_create_calls', 'can_approve', 'can_submit',
            'can_update_status', 'can_manage_users',
            'can_view_all_divisions', 'can_view_reports'
        ]
        read_only_fields = ['id']


class RoleMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for Role (used in nested representations)."""
    
    class Meta:
        model = Role
        fields = ['id', 'name']


class UserSerializer(serializers.ModelSerializer):
    """Full User serializer with nested role and division."""
    role = RoleMinimalSerializer(read_only=True)
    role_id = serializers.IntegerField(write_only=True, required=False)
    division_name = serializers.CharField(source='division.name', read_only=True)
    division_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'full_name', 'phone_number',
            'role', 'role_id', 'role_name',
            'division', 'division_id', 'division_name',
            'is_active', 'is_verified',
            'email_notifications',
            'profile_picture',
            'last_login', 'login_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'last_login', 'login_count',
            'created_at', 'updated_at', 'is_verified'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'full_name': {'required': True},
        }


class UserMinimalSerializer(serializers.ModelSerializer):
    """Minimal User serializer for nested representations."""
    role_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'role_name']


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new users (admin only)."""
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = [
            'email', 'full_name', 'phone_number',
            'password', 'confirm_password',
            'role_id', 'division_id',
            'is_active', 'email_notifications'
        ]
    
    def validate(self, data):
        if data['password'] != data.pop('confirm_password'):
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match.'
            })
        return data
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profiles."""
    
    class Meta:
        model = User
        fields = [
            'full_name', 'phone_number',
            'profile_picture', 'email_notifications'
        ]


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for admin to update any user."""
    
    class Meta:
        model = User
        fields = [
            'full_name', 'phone_number',
            'role_id', 'division_id',
            'is_active', 'is_verified',
            'email_notifications'
        ]


class CustomRegisterSerializer(RegisterSerializer):
    """Custom registration serializer with additional fields."""
    full_name = serializers.CharField(required=True, max_length=255)
    phone_number = serializers.CharField(required=False, max_length=20, allow_blank=True)
    division_id = serializers.IntegerField(required=False, allow_null=True)
    
    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data.update({
            'full_name': self.validated_data.get('full_name', ''),
            'phone_number': self.validated_data.get('phone_number', ''),
            'division_id': self.validated_data.get('division_id'),
        })
        return data
    
    def save(self, request):
        user = super().save(request)
        user.full_name = self.cleaned_data.get('full_name')
        user.phone_number = self.cleaned_data.get('phone_number')
        user.division_id = self.cleaned_data.get('division_id')
        
        # Assign default role (Division User)
        default_role = Role.objects.filter(name='Division User').first()
        if default_role:
            user.role = default_role
        
        user.save()
        return user


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change."""
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    confirm_new_password = serializers.CharField(required=True)
    
    def validate(self, data):
        if data['new_password'] != data['confirm_new_password']:
            raise serializers.ValidationError({
                'confirm_new_password': 'New passwords do not match.'
            })
        return data
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value


class UserActivitySerializer(serializers.ModelSerializer):
    """Serializer for UserActivity model."""
    user = UserMinimalSerializer(read_only=True)
    
    class Meta:
        model = UserActivity
        fields = [
            'id', 'user', 'action', 'description',
            'ip_address', 'content_type', 'object_id',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class UserStatsSerializer(serializers.Serializer):
    """Serializer for user statistics (dashboard)."""
    total_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    users_by_role = serializers.DictField()
    users_by_division = serializers.DictField()
    recent_logins = serializers.IntegerField()
