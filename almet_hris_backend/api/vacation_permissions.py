# api/vacation_permissions.py - ENHANCED VERSION

from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from .role_models import Permission, EmployeeRole, Role
from django.db.models import Q

def is_admin_user(user):
    """Check if user has Admin role"""
    try:
        from .models import Employee
        employee = Employee.objects.get(user=user, is_deleted=False)
        
        has_admin_role = EmployeeRole.objects.filter(
            employee=employee,
            role__name__icontains='Admin',
            role__is_active=True,
            is_active=True
        ).exists()
        
        return has_admin_role
    except Employee.DoesNotExist:
        return False


def get_vacation_access(user):
    """
    ✅ Get user's vacation access level and permissions
    Returns: dict with access info
    """
    from .models import Employee
    
    # Admin - Full Access
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
            'accessible_employee_ids': None,  # None means ALL
            'access_level': 'Admin - Full Access'
        }
    
    try:
        employee = Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return {
            'can_view_all': False,
            'is_manager': False,
            'is_admin': False,
            'employee': None,
            'accessible_employee_ids': [],
            'access_level': 'No Access'
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
        
        return {
            'can_view_all': False,
            'is_manager': True,
            'is_admin': False,
            'employee': employee,
            'accessible_employee_ids': accessible_ids,
            'access_level': 'Manager - Team Access'
        }
    else:
        # Regular employee - CAN VIEW their own data
        return {
            'can_view_all': False,
            'is_manager': False,
            'is_admin': False,
            'employee': employee,
            'accessible_employee_ids': [employee.id],
            'access_level': 'Employee - Own Access'
        }


def is_uk_additional_approver(user):
    """✅ NEW: Check if user is UK Additional Approver"""
    try:
        from .models import Employee
        from .vacation_models import VacationSetting
        
        settings = VacationSetting.get_active()
        if not settings or not settings.uk_additional_approver:
            return False
        
        employee = Employee.objects.get(user=user, is_deleted=False)
        return employee == settings.uk_additional_approver
        
    except Employee.DoesNotExist:
        return False


def filter_vacation_queryset(user, queryset, model_type='request'):
    """
    ✅ Filter vacation queryset based on user access
    model_type: 'request', 'schedule', or 'balance'
    """
    access = get_vacation_access(user)
    
    # Admin - see all
    if access['can_view_all']:
        return queryset
    
    # Manager or Employee - filter by accessible employee IDs
    if access['accessible_employee_ids']:
        return queryset.filter(
            employee_id__in=access['accessible_employee_ids']
        ).distinct()
    
    # No access
    return queryset.none()


def can_user_modify_vacation_request(user, vacation_request):
    """
    ✅ Check if user can edit/delete a vacation request
    Only ADMIN can modify after creation
    """
    if is_admin_user(user):
        return True, "Admin - Full Access"
    
    return False, "Only Admin can modify vacation requests"


def can_user_modify_schedule(user, vacation_schedule):
    """
    ✅ Check if user can delete a schedule
    Only ADMIN can delete SCHEDULED schedules
    """
    if is_admin_user(user):
        return True, "Admin - Full Access"
    
    if vacation_schedule.status == 'REGISTERED':
        return False, "Cannot delete registered schedules"
    
    return False, "Only Admin can delete schedules"


def can_user_register_schedule(user):
    """
    ✅ Check if user can register schedules
    Only ADMIN can register schedules
    """
    if is_admin_user(user):
        return True, "Admin - Full Access"
    
    return False, "Only Admin can register schedules"


def can_user_approve_request(user, vacation_request):
    """
    ✅ ENHANCED: Check if user can approve/reject a vacation request
    - Manager: Only requests from their DIRECT REPORTS (Line Manager stage)
    - UK Additional Approver: UK requests with 5+ days
    - HR: Requests in HR stage
    - Admin: All stages
    """
    access = get_vacation_access(user)
    
    # Admin can approve anything
    if access['is_admin']:
        return True, "Admin - Full Access"
    
    # Line Manager approval stage
    if vacation_request.status == 'PENDING_LINE_MANAGER':
        if access['employee'] and vacation_request.line_manager == access['employee']:
            # Check if requester is from manager's team
            if vacation_request.employee_id in access['accessible_employee_ids']:
                return True, "Line Manager - Team Request"
        return False, "Not your team member's request"
    
    # ✅ UK ADDITIONAL APPROVER STAGE
    if vacation_request.status == 'PENDING_UK_ADDITIONAL':
        if is_uk_additional_approver(user):
            return True, "UK Additional Approver"
        return False, "Not assigned as UK Additional Approver"
    
    # HR approval stage
    if vacation_request.status == 'PENDING_HR':
        # Check if user is HR representative
        if access['employee'] and vacation_request.hr_representative == access['employee']:
            return True, "HR Representative"
        return False, "Not assigned as HR representative"
    
    return False, "Request not in pending approval status"


# Decorator: Check vacation access
def check_vacation_access(required_level='own'):
    """
    Decorator to check vacation access level
    required_level: 'own', 'team', or 'all'
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            access = get_vacation_access(request.user)
            
            if required_level == 'all' and not access['can_view_all']:
                return Response({
                    'error': 'Access denied',
                    'detail': 'You need admin access to view all records',
                    'your_access': access['access_level']
                }, status=status.HTTP_403_FORBIDDEN)
            
            if required_level == 'team' and not (access['is_manager'] or access['can_view_all']):
                return Response({
                    'error': 'Access denied',
                    'detail': 'You need manager or admin access',
                    'your_access': access['access_level']
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Store access info in request for view to use
            request.vacation_access = access
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator