# api/self_assessment_permissions.py
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
        
        return has_admin_role or user.is_staff or user.is_superuser
    except:
        return user.is_staff or user.is_superuser


def get_self_assessment_access(user):
    """
    Get user's access level for self assessments
    Returns: {
        'can_view_all': bool,
        'is_manager': bool,
        'is_admin': bool,
        'employee': Employee instance,
        'accessible_employee_ids': list or None (None = all)
    }
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
            'accessible_employee_ids': accessible_ids
        }
    else:
        # Regular employee - can only see their own
        return {
            'can_view_all': False,
            'is_manager': False,
            'is_admin': False,
            'employee': employee,
            'accessible_employee_ids': [employee.id]
        }


def filter_assessment_queryset(user, queryset):
    """Filter queryset based on user permissions"""
    access = get_self_assessment_access(user)
    
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


def can_user_view_assessment(user, assessment):
    """Check if user can view a specific assessment"""
    access = get_self_assessment_access(user)
    
    # Admin can view all
    if access['can_view_all']:
        return True, "Admin - Full Access"
    
    # Check if assessment belongs to accessible employees
    if access['accessible_employee_ids']:
        if assessment.employee_id in access['accessible_employee_ids']:
            if access['employee'] and assessment.employee_id == access['employee'].id:
                return True, "Your assessment"
            else:
                return True, f"Direct report: {assessment.employee.full_name}"
    
    return False, "No access to this assessment"


def can_user_edit_assessment(user, assessment):
    """Check if user can edit a specific assessment"""
    access = get_self_assessment_access(user)
    
    # Admin can edit all
    if access['can_view_all']:
        return True
    
    # Only owner can edit if DRAFT
    if access['employee'] and assessment.employee_id == access['employee'].id:
        return assessment.status == 'DRAFT'
    
    return False


def can_user_submit_assessment(user, assessment):
    """Check if user can submit a specific assessment"""
    access = get_self_assessment_access(user)
    
    # Only owner can submit if DRAFT and has ratings
    if access['employee'] and assessment.employee_id == access['employee'].id:
        return assessment.status == 'DRAFT' and assessment.skill_ratings.exists()
    
    return False


def can_user_review_assessment(user, assessment):
    """Check if user can review a specific assessment"""
    access = get_self_assessment_access(user)
    
    # Admin can review all
    if access['can_view_all']:
        return True
    
    # Manager can review if SUBMITTED and is line manager
    if assessment.status == 'SUBMITTED':
        if access['employee'] and assessment.employee.line_manager_id == access['employee'].id:
            return True
    
    return False


def can_user_manage_periods(user):
    """Check if user can manage assessment periods"""
    return is_admin_user(user)