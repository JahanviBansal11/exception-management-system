from rest_framework.permissions import BasePermission


class IsRequestor(BasePermission):
    """Allow only the requestor to edit their own exception."""
    
    def has_object_permission(self, request, view, obj):
        # Allow GET for all authorized users
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        # Only requestor can modify
        return obj.requested_by == request.user


class IsAssignedRequestor(BasePermission):
    """Legacy alias for IsRequestor."""
    def has_object_permission(self, request, view, obj):
        return obj.requested_by == request.user


class IsAssignedRiskOwner(BasePermission):
    """Allow only assigned risk owner to view/edit risk assessment."""
    
    def has_object_permission(self, request, view, obj):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        return obj.risk_owner == request.user


class IsAssignedApprover(BasePermission):
    """Allow only assigned approver to approve/reject."""
    
    def has_object_permission(self, request, view, obj):
        # Approvers can view all exceptions
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        # Only assigned approver can act
        return obj.assigned_approver == request.user


class IsSecurity(BasePermission):
    """Allow Security group members to override actions."""
    
    def has_permission(self, request, view):
        return request.user.groups.filter(name="Security").exists()

    def has_object_permission(self, request, view, obj):
        # Security can do anything
        return request.user.groups.filter(name="Security").exists()


class CanApproveOrReject(BasePermission):
    """Combined permission for approve/reject actions."""
    
    def has_object_permission(self, request, view, obj):
        is_assigned = obj.assigned_approver == request.user
        is_security = request.user.groups.filter(name="Security").exists()
        return is_assigned or is_security
