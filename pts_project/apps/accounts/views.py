"""
Views for User and Role management.
"""
from rest_framework import viewsets, status, generics, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model, authenticate, login
from django.db.models import Count, Q
from django.utils import timezone
from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import timedelta
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from apps.core.permissions import IsAdmin, IsAdminOrCBM
from .models import Role, UserActivity
from .serializers import (
    RoleSerializer,
    UserSerializer,
    UserMinimalSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    AdminUserUpdateSerializer,
    PasswordChangeSerializer,
    UserActivitySerializer,
    UserStatsSerializer
)

User = get_user_model()


@extend_schema_view(
    list=extend_schema(summary="List all roles", tags=["Roles"]),
    retrieve=extend_schema(summary="Get role details", tags=["Roles"]),
    create=extend_schema(summary="Create a new role", tags=["Roles"]),
    update=extend_schema(summary="Update a role", tags=["Roles"]),
    partial_update=extend_schema(summary="Partial update a role", tags=["Roles"]),
    destroy=extend_schema(summary="Delete a role", tags=["Roles"]),
)
class RoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing roles.
    Only admins can create/update/delete roles.
    """
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return [permissions.IsAuthenticated()]


@extend_schema_view(
    list=extend_schema(
        summary="List all users",
        tags=["Users"],
        parameters=[
            OpenApiParameter(name='role', description='Filter by role name'),
            OpenApiParameter(name='division', description='Filter by division ID'),
            OpenApiParameter(name='is_active', description='Filter by active status'),
        ]
    ),
    retrieve=extend_schema(summary="Get user details", tags=["Users"]),
    create=extend_schema(summary="Create a new user", tags=["Users"]),
    update=extend_schema(summary="Update a user", tags=["Users"]),
    partial_update=extend_schema(summary="Partial update a user", tags=["Users"]),
    destroy=extend_schema(summary="Deactivate a user", tags=["Users"]),
)
class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing users.
    Admins have full access, others can only view and update their profile.
    """
    queryset = User.objects.select_related('role', 'division').all()
    filterset_fields = ['role', 'division', 'is_active']
    search_fields = ['full_name', 'email']
    ordering_fields = ['full_name', 'created_at', 'last_login']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        if self.action in ['update', 'partial_update']:
            if self.request.user.has_role('Admin'):
                return AdminUserUpdateSerializer
            return UserUpdateSerializer
        if self.action == 'list':
            return UserMinimalSerializer
        return UserSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            return [IsAdmin()]
        if self.action in ['update', 'partial_update']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Non-admin users can only see active users
        if not user.has_role('Admin'):
            queryset = queryset.filter(is_active=True)
        
        # Apply filters
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role__name=role)
        
        division = self.request.query_params.get('division')
        if division:
            queryset = queryset.filter(division_id=division)
        
        return queryset
    
    def perform_destroy(self, instance):
        """Soft delete - deactivate instead of deleting."""
        instance.is_active = False
        instance.save()
    
    @extend_schema(summary="Get current user profile", tags=["Users"])
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current authenticated user's profile."""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    
    @extend_schema(summary="Update current user profile", tags=["Users"])
    @action(detail=False, methods=['patch'])
    def update_profile(self, request):
        """Update current user's profile."""
        serializer = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)
    
    @extend_schema(summary="Change password", tags=["Users"])
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Change current user's password."""
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        
        # Log the activity
        UserActivity.objects.create(
            user=request.user,
            action='password_changed',
            description='User changed their password',
            ip_address=get_client_ip(request)
        )
        
        return Response({
            'success': True,
            'message': 'Password changed successfully'
        })
    
    @extend_schema(summary="Activate a user", tags=["Users"])
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def activate(self, request, pk=None):
        """Activate a deactivated user."""
        user = self.get_object()
        user.is_active = True
        user.save()
        return Response({
            'success': True,
            'message': f'User {user.full_name} has been activated'
        })
    
    @extend_schema(summary="Deactivate a user", tags=["Users"])
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def deactivate(self, request, pk=None):
        """Deactivate a user."""
        user = self.get_object()
        user.is_active = False
        user.save()
        return Response({
            'success': True,
            'message': f'User {user.full_name} has been deactivated'
        })
    
    @extend_schema(summary="Assign role to user", tags=["Users"])
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def assign_role(self, request, pk=None):
        """Assign a role to a user."""
        user = self.get_object()
        role_id = request.data.get('role_id')
        
        if not role_id:
            return Response(
                {'error': 'role_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            role = Role.objects.get(id=role_id)
            user.role = role
            user.save()
            
            return Response({
                'success': True,
                'message': f'Role {role.name} assigned to {user.full_name}'
            })
        except Role.DoesNotExist:
            return Response(
                {'error': 'Role not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class UserStatsView(APIView):
    """
    View for user statistics (admin dashboard).
    """
    permission_classes = [IsAdminOrCBM]
    
    @extend_schema(
        summary="Get user statistics",
        tags=["Users"],
        responses={200: UserStatsSerializer}
    )
    def get(self, request):
        """Get user statistics for dashboard."""
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        
        # Users by role
        users_by_role = dict(
            User.objects.filter(role__isnull=False)
            .values_list('role__name')
            .annotate(count=Count('id'))
        )
        
        # Users by division
        users_by_division = dict(
            User.objects.filter(division__isnull=False)
            .values_list('division__name')
            .annotate(count=Count('id'))
        )
        
        # Recent logins (last 7 days)
        recent_logins = User.objects.filter(
            last_login__gte=week_ago
        ).count()
        
        data = {
            'total_users': total_users,
            'active_users': active_users,
            'users_by_role': users_by_role,
            'users_by_division': users_by_division,
            'recent_logins': recent_logins
        }
        
        serializer = UserStatsSerializer(data)
        return Response(serializer.data)


class UserActivityListView(generics.ListAPIView):
    """
    View for listing user activities (audit log).
    """
    serializer_class = UserActivitySerializer
    permission_classes = [IsAdmin]
    filterset_fields = ['user', 'action']
    search_fields = ['description']
    ordering_fields = ['created_at']
    
    def get_queryset(self):
        queryset = UserActivity.objects.select_related('user').all()
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset


def get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class LoginView(View):
    """
    Template-based login view for the web dashboard.
    """
    template_name = 'account/login.html'
    
    def get(self, request):
        """Display login form."""
        # Redirect if already authenticated
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        
        return render(request, self.template_name)
    
    def post(self, request):
        """Handle login form submission."""
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        if not email or not password:
            return render(
                request,
                self.template_name,
                {'error': 'Please provide both email and password.'}
            )
        
        # Authenticate using email (custom user model uses email as username)
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            login(request, user)
            
            # Log the login activity
            UserActivity.objects.create(
                user=user,
                action='login',
                description='User logged in via web dashboard',
                ip_address=get_client_ip(request)
            )
            
            # Redirect to dashboard or next page
            next_url = request.GET.get('next', '/dashboard/')
            return redirect(next_url)
        else:
            # Check if the user exists but is inactive (pending admin activation)
            try:
                existing_user = User.objects.get(email=email)
                if not existing_user.is_active:
                    error_msg = 'Your account is pending admin activation. Please contact the administrator.'
                else:
                    error_msg = 'Invalid email or password.'
            except User.DoesNotExist:
                error_msg = 'Invalid email or password.'

            return render(
                request,
                self.template_name,
                {'error': error_msg}
            )


class LogoutView(LoginRequiredMixin, View):
    """
    Template-based logout view for the web dashboard.
    """
    def get(self, request):
        """Handle logout."""
        from django.contrib.auth import logout
        
        # Log the logout activity
        UserActivity.objects.create(
            user=request.user,
            action='logout',
            description='User logged out from web dashboard',
            ip_address=get_client_ip(request)
        )
        
        logout(request)
        return redirect('/accounts/login/')


class SignupView(View):
    """
    Template-based signup view for the web dashboard.
    """
    template_name = 'account/signup.html'
    
    def get(self, request):
        """Display signup form."""
        # Redirect if already authenticated
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        
        from apps.divisions.models import Division
        
        context = {
            'divisions': Division.objects.all(),
            'roles': Role.objects.all(),
        }
        return render(request, self.template_name, context)
    
    def post(self, request):
        """Handle signup form submission."""
        from apps.divisions.models import Division
        
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        division_id = request.POST.get('division')
        role_id = request.POST.get('role')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        # Validate inputs
        errors = {}
        
        if not full_name:
            errors['full_name'] = 'Full name is required.'
        if not email:
            errors['email'] = 'Email is required.'
        if not division_id:
            errors['division'] = 'Division is required.'
        if not role_id:
            errors['role'] = 'Role is required.'
        if not password1:
            errors['password1'] = 'Password is required.'
        if not password2:
            errors['password2'] = 'Password confirmation is required.'
        elif password1 != password2:
            errors['password2'] = 'Passwords do not match.'
        
        # Check if email already exists
        if email and User.objects.filter(email=email).exists():
            errors['email'] = 'This email is already registered.'
        
        if errors:
            context = {
                'errors': errors,
                'divisions': Division.objects.all(),
                'roles': Role.objects.all(),
                'form_data': {
                    'full_name': full_name,
                    'email': email,
                    'division': division_id,
                    'role': role_id,
                }
            }
            return render(request, self.template_name, context)
        
        # Create user
        try:
            division = Division.objects.get(id=division_id)
            role = Role.objects.get(id=role_id)
            
            user = User.objects.create_user(
                email=email,
                password=password1,
                full_name=full_name,
                division=division,
                role=role
            )
            
            # Log the signup activity
            UserActivity.objects.create(
                user=user,
                action='signup',
                description='User registered via web dashboard',
                ip_address=get_client_ip(request)
            )
            
            # Redirect to login page with pending-activation message
            from django.contrib import messages
            messages.success(request, 'Account created successfully! Your account is awaiting admin activation. You will be able to log in once an administrator activates your account.')
            return redirect('/accounts/login/')
        except Division.DoesNotExist:
            context = {
                'error': 'Selected division does not exist.',
                'divisions': Division.objects.all(),
                'roles': Role.objects.all(),
            }
            return render(request, self.template_name, context)
        except Role.DoesNotExist:
            context = {
                'error': 'Selected role does not exist.',
                'divisions': Division.objects.all(),
                'roles': Role.objects.all(),
            }
            return render(request, self.template_name, context)
        except Exception as e:

            context = {
                'error': f'An error occurred during registration: {str(e)}',
                'divisions': Division.objects.all(),
                'roles': Role.objects.all(),
            }
            return render(request, self.template_name, context)


class PasswordResetRequestView(View):
    """
    Request password reset by entering email address.
    """
    template_name = 'account/password_reset.html'
    
    def get(self, request):
        """Display password reset request form."""
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        
        return render(request, self.template_name)
    
    def post(self, request):
        """Handle password reset request."""
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        
        email = request.POST.get('email')
        
        if not email:
            return render(
                request,
                self.template_name,
                {'error': 'Please enter your email address.'}
            )
        
        try:
            user = User.objects.get(email=email)
            
            # Generate reset token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Create reset link
            reset_link = request.build_absolute_uri(
                f'/accounts/password/reset/confirm/{uid}/{token}/'
            )
            
            # Log the password reset request
            UserActivity.objects.create(
                user=user,
                action='password_reset_requested',
                description='User requested password reset',
                ip_address=get_client_ip(request)
            )
            
            # For development, display the reset link
            # In production, you would send this via email
            context = {
                'success': True,
                'message': 'Password reset link has been generated.',
                'reset_link': reset_link,
                'email': email,
            }
            return render(request, self.template_name, context)
            
        except User.DoesNotExist:
            # Don't reveal if email exists or not (security best practice)
            context = {
                'success': True,
                'message': 'If an account with this email exists, you will receive password reset instructions.',
                'email': email,
            }
            return render(request, self.template_name, context)


class PasswordResetConfirmView(View):
    """
    Confirm password reset with token and set new password.
    """
    template_name = 'account/password_reset_confirm.html'
    
    def get(self, request, uid, token):
        """Display password reset confirm form."""
        from django.utils.http import urlsafe_base64_decode
        from django.utils.encoding import force_str
        from django.contrib.auth.tokens import default_token_generator
        
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        
        try:
            # Decode the user ID from the URL-safe base64 encoded string
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
            
            # Check if the token is valid
            if not default_token_generator.check_token(user, token):
                return render(
                    request,
                    self.template_name,
                    {'error': 'This password reset link is invalid or has expired.'}
                )
            
            context = {
                'uid': uid,
                'token': token,
                'email': user.email,
            }
            return render(request, self.template_name, context)
            
        except (User.DoesNotExist, ValueError):
            return render(
                request,
                self.template_name,
                {'error': 'This password reset link is invalid or has expired.'}
            )
    
    def post(self, request, uid, token):
        """Handle password reset confirmation."""
        from django.utils.http import urlsafe_base64_decode
        from django.utils.encoding import force_str
        from django.contrib.auth.tokens import default_token_generator
        
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        errors = {}
        
        if not password1:
            errors['password1'] = 'Password is required.'
        if not password2:
            errors['password2'] = 'Password confirmation is required.'
        elif password1 != password2:
            errors['password2'] = 'Passwords do not match.'
        
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
            
            # Check if the token is valid
            if not default_token_generator.check_token(user, token):
                return render(
                    request,
                    self.template_name,
                    {'error': 'This password reset link is invalid or has expired.'}
                )
            
            if errors:
                context = {
                    'errors': errors,
                    'uid': uid,
                    'token': token,
                    'email': user.email,
                }
                return render(request, self.template_name, context)
            
            # Set the new password
            user.set_password(password1)
            user.save()
            
            # Log the password reset
            UserActivity.objects.create(
                user=user,
                action='password_reset',
                description='User successfully reset their password',
                ip_address=get_client_ip(request)
            )
            
            from django.contrib import messages
            messages.success(request, 'Password has been reset successfully! You can now log in with your new password.')
            return redirect('/accounts/login/')
            
        except (User.DoesNotExist, ValueError):
            return render(
                request,
                self.template_name,
                {'error': 'This password reset link is invalid or has expired.'}
            )
