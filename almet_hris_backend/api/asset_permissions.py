# api/asset_permissions.py
"""
Asset Management Permissions
- Admin: Full access
- IT: Full asset management (like Admin for assets)
- Manager: View team assets
- Employee: View own assets only
"""

from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)


def get_employee_from_user(user):
    """Get employee object from user"""
    try:
        from .models import Employee
        return Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return None


def is_admin(user):
    """Check if user is Admin"""
    try:
        from .models import Employee
        from .role_models import EmployeeRole
        
        employee = get_employee_from_user(user)
        if not employee:
            return False
        
        return EmployeeRole.objects.filter(
            employee=employee,
            role__name__icontains='Admin',
            role__is_active=True,
            is_active=True
        ).exists()
    except:
        return False


def is_it_role(user):
    """Check if user has IT role"""
    try:
        from .models import Employee
        from .role_models import EmployeeRole
        
        employee = get_employee_from_user(user)
        if not employee:
            return False
        
        return EmployeeRole.objects.filter(
            employee=employee,
            role__name__icontains='IT',
            role__is_active=True,
            is_active=True
        ).exists()
    except:
        return False


def is_manager(user):
    """Check if user is a manager (has direct reports)"""
    try:
        from .models import Employee
        
        employee = get_employee_from_user(user)
        if not employee:
            return False
        
        # Check if has direct reports
        return Employee.objects.filter(
            line_manager=employee,
            is_deleted=False
        ).exists()
    except:
        return False


def get_asset_access_level(user):
    """
    Get user's asset access level
    """
    employee = get_employee_from_user(user)
    
    # Admin - Full access
    if is_admin(user):
        return {
            'access_level': 'ADMIN',
            'can_manage_all_assets': True,
            'can_approve_transfers': True,
            'can_view_all_assets': True,
            'can_create_batches': True,
            'can_bulk_upload': True,
            'can_create_transfers': True,  # 🆕
            'can_complete_handover': True,  # 🆕
            'employee': employee,
            'accessible_employee_ids': None
        }
    
    # IT - Full asset management
    if is_it_role(user):
        return {
            'access_level': 'IT',
            'can_manage_all_assets': True,
            'can_approve_transfers': True,
            'can_view_all_assets': True,
            'can_create_batches': True,
            'can_bulk_upload': True,
            'can_create_transfers': True,  # 🆕
            'can_complete_handover': True,  # 🆕
            'employee': employee,
            'accessible_employee_ids': None
        }
    
    # Manager - Team access
    if is_manager(user):
        from .models import Employee
        
        direct_reports = Employee.objects.filter(
            line_manager=employee,
            is_deleted=False
        )
        
        accessible_ids = [employee.id]
        accessible_ids.extend(list(direct_reports.values_list('id', flat=True)))
        
        return {
            'access_level': 'MANAGER',
            'can_manage_all_assets': False,
            'can_approve_transfers': False,  # Manager artıq approve edə bilməz
            'can_view_all_assets': False,
            'can_create_batches': False,
            'can_bulk_upload': False,
            'can_create_transfers': False,  # 🆕
            'can_complete_handover': False,  # 🆕
            'employee': employee,
            'accessible_employee_ids': accessible_ids
        }
    
    # Regular Employee
    return {
        'access_level': 'EMPLOYEE',
        'can_manage_all_assets': False,
        'can_approve_transfers': False,
        'can_view_all_assets': False,
        'can_create_batches': False,
        'can_bulk_upload': False,
        'can_create_transfers': False,  # 🆕
        'can_complete_handover': False,  # 🆕
        'employee': employee,
        'accessible_employee_ids': [employee.id] if employee else []
    }


def require_asset_permission(permission_type='view'):
    """
    Decorator to check asset permissions
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(view_instance, request, *args, **kwargs):
            access = get_asset_access_level(request.user)
            
            if permission_type == 'view':
                return view_func(view_instance, request, *args, **kwargs)
            
            elif permission_type == 'manage':
                if not access['can_manage_all_assets']:
                    return Response(
                        {'error': 'You do not have permission to manage assets'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            elif permission_type == 'create':
                if not access['can_create_batches']:
                    return Response(
                        {'error': 'You do not have permission to create asset batches'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            elif permission_type == 'approve':
                if not access['can_approve_transfers']:
                    return Response(
                        {'error': 'You do not have permission to approve transfers'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            # 🆕 Transfer creation - Admin/IT only
            elif permission_type == 'create_transfer':
                if not access['can_create_transfers']:
                    return Response(
                        {'error': 'Only Admin and IT can create transfer requests'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            # 🆕 Handover completion - Admin/IT only
            elif permission_type == 'complete_handover':
                if not access['can_complete_handover']:
                    return Response(
                        {'error': 'Only Admin and IT can complete handover'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            return view_func(view_instance, request, *args, **kwargs)
        
        return wrapped_view
    return decorator
def filter_assets_by_access(user, queryset):
    """
    Filter asset queryset based on user access
    
    Args:
        user: Django User
        queryset: Asset QuerySet
    
    Returns:
        Filtered QuerySet
    """
    access = get_asset_access_level(user)
    
    # Admin/IT - see all
    if access['can_view_all_assets']:
        return queryset
    
    # Manager/Employee - filter by accessible employees
    if access['accessible_employee_ids']:
        return queryset.filter(
            Q(assigned_to__id__in=access['accessible_employee_ids']) |
            Q(assigned_to__isnull=True)  # Also show unassigned
        ).distinct()
    
    return queryset.none()


def filter_batches_by_access(user, queryset):
    """Filter batch queryset based on user access"""
    access = get_asset_access_level(user)
    
    # Admin/IT - see all
    if access['can_view_all_assets']:
        return queryset
    
    # Others - only active batches
    return queryset.filter(status='ACTIVE')


def can_user_manage_asset(user, asset=None):
    """
    Check if user can manage specific asset or assets in general
    
    Args:
        user: Django User
        asset: Asset object (optional)
    
    Returns:
        tuple: (can_manage: bool, reason: str)
    """
    access = get_asset_access_level(user)
    
    # Admin/IT - full access
    if access['can_manage_all_assets']:
        return True, f"{access['access_level']} - Full access"
    
    # If specific asset provided
    if asset:
        # Manager - can manage team assets
        if access['access_level'] == 'MANAGER':
            if asset.assigned_to and asset.assigned_to.id in access['accessible_employee_ids']:
                return True, "Manager - Team asset"
            return False, "Not your team's asset"
        
        # Employee - can only view own
        if access['access_level'] == 'EMPLOYEE':
            if asset.assigned_to and asset.assigned_to.id == access['employee'].id:
                return True, "Your asset"
            return False, "Not your asset"
    
    return False, "Insufficient permissions"


def require_asset_permission(permission_type='view'):
    """
    Decorator to check asset permissions
    
    Args:
        permission_type: 'view' | 'manage' | 'create' | 'approve'
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(view_instance, request, *args, **kwargs):
            access = get_asset_access_level(request.user)
            
            if permission_type == 'view':
                # Everyone can view (filtered by access level)
                return view_func(view_instance, request, *args, **kwargs)
            
            elif permission_type == 'manage':
                if not access['can_manage_all_assets']:
                    return Response(
                        {'error': 'You do not have permission to manage assets'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            elif permission_type == 'create':
                if not access['can_create_batches']:
                    return Response(
                        {'error': 'You do not have permission to create asset batches'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            elif permission_type == 'approve':
                if not access['can_approve_transfers']:
                    return Response(
                        {'error': 'You do not have permission to approve transfers'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            return view_func(view_instance, request, *args, **kwargs)
        
        return wrapped_view
    return decorator


def get_access_summary(user):
    """Get human-readable access summary"""
    access = get_asset_access_level(user)
    
    return {
        'access_level': access['access_level'],
        'access_description': {
            'ADMIN': 'Full access to all assets',
            'IT': 'Full asset management access',
            'MANAGER': 'Access to team assets',
            'EMPLOYEE': 'Access to own assets only'
        }.get(access['access_level']),
        'permissions': {
            'can_view_all_assets': access['can_view_all_assets'],
            'can_manage_all_assets': access['can_manage_all_assets'],
            'can_create_batches': access['can_create_batches'],
            'can_bulk_upload': access['can_bulk_upload'],
            'can_approve_transfers': access['can_approve_transfers'],
        },
        'employee_id': access['employee'].id if access['employee'] else None,
        'employee_name': access['employee'].full_name if access['employee'] else None,
        'accessible_count': (
            'All' if access['accessible_employee_ids'] is None
            else len(access['accessible_employee_ids'])
        )
    }