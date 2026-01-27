# api/headcount_permissions.py - YENİ FİL
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

def get_headcount_access(user):
    """
    ✅ Get headcount access level for user
    Returns: {
        'can_view_all': bool,
        'is_manager': bool,
        'employee': Employee or None,
        'accessible_employee_ids': list or None,
        'accessible_business_functions': list or None
    }
    """
    from .models import Employee
    
    # Admin - Full Access
    if is_admin_user(user):
        return {
            'can_view_all': True,
            'is_manager': True,
            'employee': None,
            'accessible_employee_ids': None,  # None means ALL
            'accessible_business_functions': None  # None means ALL
        }
    
    try:
        employee = Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return {
            'can_view_all': False,
            'is_manager': False,
            'employee': None,
            'accessible_employee_ids': [],
            'accessible_business_functions': []
        }
    
    # Check if manager (has direct reports)
    direct_reports = Employee.objects.filter(
        line_manager=employee,
        is_deleted=False
    )
    
    is_manager = direct_reports.exists()
    
    if is_manager:
        # Manager can see: self + direct reports
        accessible_ids = [employee.id]
        accessible_ids.extend(list(direct_reports.values_list('id', flat=True)))
        
        # Get business functions of accessible employees
        accessible_bfs = set()
        accessible_bfs.add(employee.business_function_id)
        accessible_bfs.update(
            direct_reports.values_list('business_function_id', flat=True)
        )
        
        return {
            'can_view_all': False,
            'is_manager': True,
            'employee': employee,
            'accessible_employee_ids': accessible_ids,
            'accessible_business_functions': list(accessible_bfs)
        }
    else:
        # Regular employee - NO ACCESS to headcount table
        return {
            'can_view_all': False,
            'is_manager': False,
            'employee': employee,
            'accessible_employee_ids': [employee.id],  # Only self
            'accessible_business_functions': [employee.business_function_id] if employee.business_function else []
        }

def filter_headcount_queryset(user, queryset):
    """
    ✅ Filter employee queryset based on user access
    """
    access = get_headcount_access(user)
    
    if access['can_view_all']:
        return queryset
    
    if not access['is_manager']:
        # Regular employee - return empty queryset (no access)
        return queryset.none()
    
    # Manager - filter by accessible IDs
    return queryset.filter(id__in=access['accessible_employee_ids'])