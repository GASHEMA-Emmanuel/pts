"""
Custom permissions for PTS.
Implements Role-Based Access Control (RBAC) as per SRD requirements.
"""
from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """
    Permission check for System Administrator role.
    Full access to system configuration and user management.
    """
    message = 'Administrator access required.'
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role and
            request.user.role.name == 'Admin'
        )


class IsCBM(permissions.BasePermission):
    """
    Permission check for CBM (Chief Budget Manager) role.
    Can initiate procurement calls and approve submissions.
    """
    message = 'CBM access required.'
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role and
            request.user.role.name == 'CBM'
        )


class IsHODOrDM(permissions.BasePermission):
    """
    Permission check for HOD (Head of Department) or DM (Division Manager) role.
    Can submit procurement requests and approve within their division.
    """
    message = 'HOD or Division Manager access required.'
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role and
            request.user.role.name == 'HOD/DM'
        )


class IsProcurementTeam(permissions.BasePermission):
    """
    Permission check for Procurement Team role.
    Can update procurement statuses and manage timelines.
    """
    message = 'Procurement Team access required.'
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role and
            request.user.role.name == 'Procurement Team'
        )


class IsDivisionUser(permissions.BasePermission):
    """
    Permission check for Division User role.
    Can provide inputs and track procurement activities.
    """
    message = 'Division User access required.'
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role and
            request.user.role.name == 'Division User'
        )


class IsAdminOrCBM(permissions.BasePermission):
    """Combined permission for Admin or CBM roles."""
    message = 'Administrator or CBM access required.'
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role and
            request.user.role.name in ['Admin', 'CBM']
        )


class CanManageSubmissions(permissions.BasePermission):
    """
    Permission to create/edit submissions.
    Allowed for: HOD/DM, Division User (limited), Procurement Team
    """
    message = 'You do not have permission to manage submissions.'
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated or not request.user.role:
            return False
        
        allowed_roles = ['Admin', 'CBM', 'HOD/DM', 'Procurement Team', 'Division User']
        return request.user.role.name in allowed_roles
    
    def has_object_permission(self, request, view, obj):
        """Check if user can access specific submission."""
        if request.user.role.name in ['Admin', 'CBM', 'Procurement Team']:
            return True
        
        # HOD/DM and Division Users can only access their division's submissions
        if request.user.role.name in ['HOD/DM', 'Division User']:
            return obj.division == request.user.division
        
        return False


class CanApprove(permissions.BasePermission):
    """
    Permission to approve/reject submissions.
    Allowed for: CBM (all), HOD/DM (own division), Procurement Team (limited stages)
    """
    message = 'You do not have permission to approve submissions.'
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated or not request.user.role:
            return False
        
        allowed_roles = ['Admin', 'CBM', 'HOD/DM', 'Procurement Team']
        return request.user.role.name in allowed_roles


class CanUpdateWorkflow(permissions.BasePermission):
    """
    Permission to update workflow stages.
    Allowed for: Procurement Team, CBM, Admin
    """
    message = 'You do not have permission to update workflow status.'
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated or not request.user.role:
            return False
        
        allowed_roles = ['Admin', 'CBM', 'Procurement Team']
        return request.user.role.name in allowed_roles


class CanComment(permissions.BasePermission):
    """
    Permission to add comments.
    Allowed for: All authenticated users (on accessible submissions)
    """
    message = 'You do not have permission to comment.'
    
    def has_permission(self, request, view):
        return request.user.is_authenticated


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission to only allow owners or admins to edit.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions for any authenticated request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only for owner or admin
        if hasattr(obj, 'user'):
            return obj.user == request.user or request.user.role.name == 'Admin'
        if hasattr(obj, 'created_by'):
            return obj.created_by == request.user or request.user.role.name == 'Admin'
        
        return request.user.role.name == 'Admin'


class DivisionBasedPermission(permissions.BasePermission):
    """
    Permission that restricts access based on user's division.
    """
    def has_object_permission(self, request, view, obj):
        # Admins and CBM can access all
        if request.user.role.name in ['Admin', 'CBM', 'Procurement Team']:
            return True
        
        # Others can only access their division's data
        if hasattr(obj, 'division'):
            return obj.division == request.user.division
        if hasattr(obj, 'division_id'):
            return obj.division_id == request.user.division_id
        
        return False
