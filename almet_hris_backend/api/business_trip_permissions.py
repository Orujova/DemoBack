# api/business_trip_permissions.py - Role-Based Permissions

from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from .role_models import Permission, EmployeeRole, Role

def is_admin_user(user):
    """Check if user has Admin role"""
    try:
        from .models import Employee
        employee = Employee.objects.get(user=user, is_deleted=False)
        
        # Admin role-u yoxla (case-insensitive)
        has_admin_role = EmployeeRole.objects.filter(
            employee=employee,
            role__name__icontains='Admin',
            role__is_active=True,
            is_active=True
        ).exists()
        
        return has_admin_role
    except Employee.DoesNotExist:
        return False


def has_business_trip_permission(permission_codename):
    """
    Decorator to check business trip permissions
    Admin role bütün permission-lara sahib
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user
            
            # Admin role yoxla
            if is_admin_user(user):
                return view_func(request, *args, **kwargs)
            
            # Employee tap
            try:
                from .models import Employee
                employee = Employee.objects.get(user=user, is_deleted=False)
            except Employee.DoesNotExist:
                return Response({
                    'error': 'Employee profili tapılmadı',
                    'detail': 'Business Trip sisteminə daxil olmaq üçün employee profili lazımdır'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Employee-in rollarını tap
            employee_roles = EmployeeRole.objects.filter(
                employee=employee,
                is_active=True
            ).select_related('role')
            
            if not employee_roles.exists():
                return Response({
                    'error': 'Aktiv rol tapılmadı',
                    'detail': 'Bu əməliyyat üçün sizə rol təyin edilməlidir'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Permission yoxla
            has_permission = False
            for emp_role in employee_roles:
                role = emp_role.role
                if role.role_permissions.filter(
                    permission__codename=permission_codename,
                    permission__is_active=True
                ).exists():
                    has_permission = True
                    break
            
            if not has_permission:
                return Response({
                    'error': 'İcazə yoxdur',
                    'detail': f'Bu əməliyyat üçün "{permission_codename}" icazəsi lazımdır',
                    'your_roles': [er.role.name for er in employee_roles]
                }, status=status.HTTP_403_FORBIDDEN)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def has_any_business_trip_permission(permission_codenames):
    """
    Check if user has ANY of the specified permissions
    Admin role automatically passes
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user
            
            # Admin role yoxla
            if is_admin_user(user):
                return view_func(request, *args, **kwargs)
            
            try:
                from .models import Employee
                employee = Employee.objects.get(user=user, is_deleted=False)
            except Employee.DoesNotExist:
                return Response({
                    'error': 'Employee profili tapılmadı'
                }, status=status.HTTP_403_FORBIDDEN)
            
            employee_roles = EmployeeRole.objects.filter(
                employee=employee,
                is_active=True
            ).select_related('role')
            
            if not employee_roles.exists():
                return Response({
                    'error': 'Aktiv rol tapılmadı'
                }, status=status.HTTP_403_FORBIDDEN)
            
            has_permission = False
            for emp_role in employee_roles:
                role = emp_role.role
                if role.role_permissions.filter(
                    permission__codename__in=permission_codenames,
                    permission__is_active=True
                ).exists():
                    has_permission = True
                    break
            
            if not has_permission:
                return Response({
                    'error': 'İcazə yoxdur',
                    'detail': f'Bu əməliyyat üçün aşağıdakı icazələrdən biri lazımdır',
                    'required_permissions': permission_codenames,
                    'your_roles': [er.role.name for er in employee_roles]
                }, status=status.HTTP_403_FORBIDDEN)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def check_business_trip_permission(user, permission_codename):
    """
    Utility function to check permission without decorator
    Returns: (has_permission: bool, employee: Employee or None)
    """
    # Admin role yoxla
    if is_admin_user(user):
        return True, None
    
    try:
        from .models import Employee
        employee = Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return False, None
    
    employee_roles = EmployeeRole.objects.filter(
        employee=employee,
        is_active=True
    ).select_related('role')
    
    for emp_role in employee_roles:
        role = emp_role.role
        if role.role_permissions.filter(
            permission__codename=permission_codename,
            permission__is_active=True
        ).exists():
            return True, employee
    
    return False, employee


def get_user_business_trip_permissions(user):
    """
    Get all business trip permissions for user
    Returns: list of permission codenames
    """
    if is_admin_user(user):
        # Admin has all business trip permissions
        return list(Permission.objects.filter(
            category='Business Trips',
            is_active=True
        ).values_list('codename', flat=True))
    
    try:
        from .models import Employee
        employee = Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return []
    
    employee_roles = EmployeeRole.objects.filter(
        employee=employee,
        is_active=True
    ).select_related('role')
    
    permission_codenames = set()
    for emp_role in employee_roles:
        role_perms = emp_role.role.role_permissions.filter(
            permission__is_active=True,
            permission__category='Business Trips'
        ).values_list('permission__codename', flat=True)
        permission_codenames.update(role_perms)
    
    return list(permission_codenames)