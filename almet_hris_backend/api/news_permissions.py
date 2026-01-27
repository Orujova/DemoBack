# api/news_permissions.py - UPDATED WITHOUT view_all
"""
Company News System Permissions
✅ Simplified: Admin sees all, others see only their target group news
"""

from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import BasePermission
from .role_models import Permission, EmployeeRole, Role


def is_admin_user(user):
    """Check if user has Admin role"""
    try:
        from .models import Employee
        employee = Employee.objects.get(user=user, is_deleted=False)
        
        # Admin role check (case-insensitive)
        has_admin_role = EmployeeRole.objects.filter(
            employee=employee,
            role__name__icontains='Admin',
            role__is_active=True,
            is_active=True
        ).exists()
        
        return has_admin_role
    except Employee.DoesNotExist:
        return False




# ==================== DRF PERMISSION CLASSES ====================

class IsAdminOnly(BasePermission):
    """
    ✅ STRICT: Only Admin can access
    Used for: Categories, Target Groups, Create News
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return is_admin_user(request.user)


class CanViewNews(BasePermission):
    """
    ✅ SIMPLIFIED: Everyone can view published news in their target groups
    Admin can view all news
    """
    
    def has_permission(self, request, view):
        """Everyone authenticated can attempt to view news"""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if user can view this specific news"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin can view all
        if is_admin_user(request.user):
            return True
        
        # Regular users can only view published news in their target groups
        if not obj.is_published or obj.is_deleted:
            return False
        
        # Check if user is in any of the news target groups
        try:
            from .models import Employee
            employee = Employee.objects.get(user=request.user, is_deleted=False)
            
            news_target_groups = obj.target_groups.filter(is_active=True, is_deleted=False)
            
            # If news has no target groups, it's visible to all
            if not news_target_groups.exists():
                return True
            
            # Check if user is in any target group
            user_in_target_group = news_target_groups.filter(members=employee).exists()
            return user_in_target_group
            
        except Employee.DoesNotExist:
            return False