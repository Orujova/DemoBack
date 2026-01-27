# api/timeoff_permissions.py
"""
Time Off System - ROLE-BASED Permissions (NO RBAC Decorators)
- Admin: Full access to everything
- Line Manager: Own + team requests
- Employee: Only own requests
"""

from django.db.models import Q
import logging

logger = logging.getLogger(__name__)


def is_admin_user(user):
    """Check if user has Admin role"""
    try:
        from .models import Employee
        from .role_models import EmployeeRole
        
        employee = Employee.objects.get(user=user, is_deleted=False)
        
        has_admin_role = EmployeeRole.objects.filter(
            employee=employee,
            role__name__icontains='Admin',
            role__is_active=True,
            is_active=True
        ).exists()
        
        return has_admin_role
    except:
        return False


def get_timeoff_request_access(user):
    """
    Get user's time off request access level BASED ON ROLE ONLY
    
    Returns:
        - can_view_all: Admin - see all requests
        - is_manager: Has direct reports
        - employee: Employee object
        - accessible_employee_ids: List of employee IDs user can view
        - access_level: Human-readable access level
    """
    from .models import Employee
    
    # 1. Check if Admin
    if is_admin_user(user):
        return {
            'can_view_all': True,
            'is_manager': True,
            'employee': None,
            'accessible_employee_ids': None,  # None means ALL
            'access_level': 'Admin - Full Access'
        }
    
    try:
        employee = Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return {
            'can_view_all': False,
            'is_manager': False,
            'employee': None,
            'accessible_employee_ids': [],
            'access_level': 'No Access'
        }
    
    # 2. Check if Line Manager (has direct reports)
    direct_reports = Employee.objects.filter(
        line_manager=employee,
        is_deleted=False
    )
    
    is_manager = direct_reports.exists()
    
    if is_manager:
        # Manager can see: self + direct reports
        accessible_ids = [employee.id]
        accessible_ids.extend(list(direct_reports.values_list('id', flat=True)))
        
        return {
            'can_view_all': False,
            'is_manager': True,
            'employee': employee,
            'accessible_employee_ids': accessible_ids,
            'access_level': 'Line Manager - Team Access'
        }
    else:
        # 3. Regular employee - only self
        return {
            'can_view_all': False,
            'is_manager': False,
            'employee': employee,
            'accessible_employee_ids': [employee.id],
            'access_level': 'Employee - Own Requests Only'
        }


def filter_timeoff_requests_by_access(user, queryset):
    """
    Filter time off requests based on ROLE-BASED access
    """
    access = get_timeoff_request_access(user)
    
    # Admin - see all
    if access['can_view_all']:
        return queryset
    
    # Manager or Employee - filter by accessible employee IDs
    if access['accessible_employee_ids']:
        return queryset.filter(
            employee_id__in=access['accessible_employee_ids']
        )
    
    # No access
    return queryset.none()


def can_approve_timeoff_role_based(user, request_obj):
    """
    Check if user can approve - ROLE-BASED ONLY
    Returns: (can_approve: bool, reason: str)
    """
    # 1. Admin həmişə approve edə bilər
    if is_admin_user(user):
        return True, "Admin role"
    
    # 2. Employee-i tap
    try:
        from .models import Employee
        employee = Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return False, "No employee profile"
    
    # 3. Line Manager yoxla
    if request_obj.line_manager == employee:
        return True, "Line Manager"
    
    return False, "Not authorized"


def can_view_timeoff_request_role_based(user, request_obj):
    """
    Check if user can view a specific request - ROLE-BASED ONLY
    Returns: (can_view: bool, reason: str)
    """
    # 1. Admin həmişə görə bilər
    if is_admin_user(user):
        return True, "Admin role"
    
    try:
        from .models import Employee
        employee = Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return False, "No employee profile"
    
    # 2. Öz request-i
    if request_obj.employee == employee:
        return True, "Own request"
    
    # 3. Line Manager - komanda üzvünün request-i
    if request_obj.line_manager == employee:
        return True, "Team request (Line Manager)"
    
    return False, "Not authorized"


def filter_timeoff_balances_by_access(user, queryset):
    """
    Filter time off balances based on ROLE-BASED access
    """
    access = get_timeoff_request_access(user)
    
    # Admin - see all
    if access['can_view_all']:
        return queryset
    
    # Manager or Employee - filter by accessible employee IDs
    if access['accessible_employee_ids']:
        return queryset.filter(
            employee_id__in=access['accessible_employee_ids']
        )
    
    # No access
    return queryset.none()