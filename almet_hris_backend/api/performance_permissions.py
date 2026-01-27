# api/performance_permissions.py - SIMPLIFIED (Job Description kimi)

from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q

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


def get_performance_access(user):
    """
    ✅ Get user's performance access info
    Returns: {
        'can_view_all': bool,
        'is_manager': bool,
        'is_admin': bool,
        'employee': Employee instance,
        'accessible_employee_ids': list or None
    }
    """
    from .models import Employee
    
    # ✅ Admin - Full Access
    if is_admin_user(user):
        try:
            employee = Employee.objects.get(user=user, is_deleted=False)
        except Employee.DoesNotExist:
            employee = None
        
        return {
            'can_view_all': True,
            'is_manager': True,
            'is_admin': True,
            'employee': employee,
            'accessible_employee_ids': None  # None means ALL
        }
    
    try:
        employee = Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return {
            'can_view_all': False,
            'is_manager': False,
            'is_admin': False,
            'employee': None,
            'accessible_employee_ids': []
        }
    
    # ✅ Check if manager (has direct reports)
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
            'is_admin': False,
            'employee': employee,
            'accessible_employee_ids': accessible_ids
        }
    else:
        # ✅ Regular employee - CAN VIEW their own performance
        return {
            'can_view_all': False,
            'is_manager': False,
            'is_admin': False,
            'employee': employee,
            'accessible_employee_ids': [employee.id]  # Only self
        }


def filter_performance_queryset(user, queryset):
    """
    ✅ Filter performance queryset based on user access
    """
    access = get_performance_access(user)
    
    # Admin - see all
    if access['can_view_all']:
        return queryset
    
    # Manager or Employee - filter by accessible employee IDs
    if access['accessible_employee_ids']:
        return queryset.filter(
            employee_id__in=access['accessible_employee_ids']
        )
    
    # No access (shouldn't happen, but safety check)
    return queryset.none()


def can_user_view_performance(user, performance):
    """
    ✅ Check if user can view a specific performance
    Returns: (can_view: bool, reason: str)
    """
    access = get_performance_access(user)
    
    # Admin can view all
    if access['can_view_all']:
        return True, "Admin - Full Access"
    
    # Check if performance employee is in accessible list
    if access['accessible_employee_ids']:
        if performance.employee_id in access['accessible_employee_ids']:
            # Check if it's the user's own performance
            if access['employee'] and performance.employee_id == access['employee'].id:
                return True, "Your performance"
            else:
                return True, f"Direct report: {performance.employee.full_name}"
    
    return False, "No access to this performance"


def can_user_edit_performance(user, performance):
    """
    ✅ Check if user can edit a specific performance
    Returns: (can_edit: bool, reason: str)
    """
    access = get_performance_access(user)
    
    # Admin can edit all
    if access['can_view_all']:
        return True, "Admin - Full Access"
    
    # Manager can edit direct reports' performances
    if access['is_manager']:
        if performance.employee.line_manager == access['employee']:
            return True, "Manager - Direct Report"
    
    # Employee can edit their own performance (in specific periods)
    if access['employee'] and performance.employee == access['employee']:
        return True, "Your performance"
    
    return False, "No edit access"


# ============ DECORATOR FOR ADMIN-ONLY ACTIONS ============

def admin_only(view_func):
    """
    ✅ Decorator for admin-only endpoints
    Usage: @admin_only
    """
    @wraps(view_func)
    def wrapper(self_or_request, *args, **kwargs):
        # Determine if this is a ViewSet method or a function view
        if hasattr(self_or_request, 'request'):
            request = self_or_request.request
        else:
            request = self_or_request
        
        user = request.user
        
        # Admin check
        if is_admin_user(user):
            return view_func(self_or_request, *args, **kwargs)
        
        return Response({
            'error': 'Admin access required',
            'detail': 'You must be an admin to access this resource'
        }, status=status.HTTP_403_FORBIDDEN)
    
    return wrapper


# ============ BACKWARD COMPATIBILITY (if needed) ============

def has_performance_permission(permission_codename):
    """
    ⚠️ DEPRECATED - kept for backward compatibility
    Now all permissions determined by role (Admin/Manager/Employee)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self_or_request, *args, **kwargs):
            if hasattr(self_or_request, 'request'):
                request = self_or_request.request
            else:
                request = self_or_request
            
            # Just check if admin
            if is_admin_user(request.user):
                return view_func(self_or_request, *args, **kwargs)
            
            return Response({
                'error': 'Permission denied',
                'detail': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return wrapper
    return decorator


def check_performance_permission(user, permission_codename):
    """
    ⚠️ DEPRECATED - kept for backward compatibility
    Returns: (has_permission: bool, employee: Employee or None)
    """
    access = get_performance_access(user)
    return access['is_admin'], access['employee']


def get_user_performance_permissions(user):
    """
    ⚠️ DEPRECATED - kept for backward compatibility
    Returns: list of permission codenames (now just ['admin'] or [])
    """
    if is_admin_user(user):
        return ['admin']
    return []


def can_view_performance(user, performance):
    """
    ⚠️ DEPRECATED - use can_user_view_performance instead
    """
    can_view, _ = can_user_view_performance(user, performance)
    return can_view


def can_edit_performance(user, performance):
    """
    ⚠️ DEPRECATED - use can_user_edit_performance instead
    """
    can_edit, _ = can_user_edit_performance(user, performance)
    return can_edit


def get_accessible_employees_for_performance(user):
    """
    ⚠️ DEPRECATED - use get_performance_access instead
    Returns: (employee_ids, can_view_all, is_manager)
    """
    access = get_performance_access(user)
    return (
        access['accessible_employee_ids'],
        access['can_view_all'],
        access['is_manager']
    )


def filter_viewable_performances(user, queryset):
    """
    ⚠️ DEPRECATED - use filter_performance_queryset instead
    """
    return filter_performance_queryset(user, queryset)


def get_accessible_employees_for_analytics(user):
    """
    ✅ Get employees accessible for analytics/statistics
    Returns: (employee_queryset, can_view_all, is_manager)
    """
    from .models import Employee
    
    access = get_performance_access(user)
    
    # Admin sees all
    if access['can_view_all']:
        return Employee.objects.filter(is_deleted=False), True, True
    
    # Manager or Employee - filter by accessible IDs
    if access['accessible_employee_ids']:
        return (
            Employee.objects.filter(
                id__in=access['accessible_employee_ids'],
                is_deleted=False
            ),
            False,
            access['is_manager']
        )
    
    return Employee.objects.none(), False, False


def format_access_info_for_api(user):
    """
    ✅ Format access info for API response (like Job Description)
    """
    access = get_performance_access(user)
    
    if access['can_view_all']:
        accessible_count_text = "All"
    elif access['accessible_employee_ids']:
        accessible_count_text = len(access['accessible_employee_ids'])
    else:
        accessible_count_text = 0
    
    # Determine access level text
    if access['is_admin']:
        access_level_text = "Admin - Full Access"
    elif access['is_manager']:
        access_level_text = f"Manager - You + {accessible_count_text - 1} direct reports"
    else:
        access_level_text = "Employee - Your performance only"
    
    return {
        'can_view_all': access['can_view_all'],
        'is_manager': access['is_manager'],
        'is_admin': access['is_admin'],
        'access_level': access_level_text,
        'accessible_count': accessible_count_text,
        'employee_id': access['employee'].id if access['employee'] else None,
        'employee_name': access['employee'].full_name if access['employee'] else None
    }