# api/assessment_permissions.py
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

def get_assessment_access(user):
    """
    ✅ Get assessment access level for user
    Returns: {
        'can_view_all': bool,
        'is_manager': bool,
        'employee': Employee or None,
        'accessible_employee_ids': list or None
    }
    """
    from .models import Employee
    
    # Admin - Full Access
    if is_admin_user(user):
        return {
            'can_view_all': True,
            'is_manager': True,
            'employee': None,
            'accessible_employee_ids': None  # None means ALL
        }
    
    try:
        employee = Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return {
            'can_view_all': False,
            'is_manager': False,
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
            'employee': employee,
            'accessible_employee_ids': accessible_ids
        }
    else:
        # ✅ Regular employee - CAN VIEW their own assessments
        return {
            'can_view_all': False,
            'is_manager': False,
            'employee': employee,
            'accessible_employee_ids': [employee.id]  # Only self
        }

def filter_assessment_queryset(user, queryset):
    """
    ✅ Filter assessment queryset based on user access
    - Admin: sees all
    - Manager: sees own + direct reports
    - Employee: sees only their own
    """
    access = get_assessment_access(user)
    
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

def can_user_view_assessment(user, assessment):
    """
    ✅ Check if user can view a specific assessment
    Returns: (bool, str) - (can_view, reason)
    """
    access = get_assessment_access(user)
    
    # Admin can view all
    if access['can_view_all']:
        return True, "Admin - Full Access"
    
    # Check if assessment belongs to accessible employees
    if access['accessible_employee_ids']:
        if assessment.employee_id in access['accessible_employee_ids']:
            # Check if it's the user's own assessment
            if access['employee'] and assessment.employee_id == access['employee'].id:
                return True, "Your assessment"
            else:
                return True, f"Direct report: {assessment.employee.full_name}"
    
    return False, "No access to this assessment"

def can_user_create_assessment(user, employee_id):
    """
    ✅ Check if user can create assessment for employee
    - Admin: can create for anyone
    - Manager: can create for self + direct reports
    - Employee: can create only for self (if allowed)
    """
    access = get_assessment_access(user)
    
    # Admin can create for anyone
    if access['can_view_all']:
        return True, "Admin - Full Access"
    
    # Manager or Employee
    if access['accessible_employee_ids']:
        if employee_id in access['accessible_employee_ids']:
            if access['employee'] and employee_id == access['employee'].id:
                return True, "Creating your own assessment"
            else:
                return True, "Creating assessment for direct report"
    
    return False, "Cannot create assessment for this employee"

def can_user_edit_assessment(user, assessment):
    """
    ✅ Check if user can edit assessment
    Rules:
    - Admin: can edit all
    - Manager: can edit own + direct reports' assessments
    - Employee: can edit only their own DRAFT assessments
    """
    access = get_assessment_access(user)
    
    # Admin can edit all
    if access['can_view_all']:
        return True, "Admin - Full Access"
    
    # Check accessibility
    if access['accessible_employee_ids']:
        if assessment.employee_id not in access['accessible_employee_ids']:
            return False, "Assessment belongs to inaccessible employee"
        
        # If it's user's own assessment
        if access['employee'] and assessment.employee_id == access['employee'].id:
            # Employee can only edit their own DRAFT assessments
            if not access['is_manager'] and assessment.status != 'DRAFT':
                return False, "Cannot edit completed assessment (only managers can)"
            return True, "Your assessment"
        
        # If it's a direct report's assessment (manager only)
        if access['is_manager']:
            return True, f"Direct report: {assessment.employee.full_name}"
    
    return False, "No edit access to this assessment"

def can_user_delete_assessment(user, assessment):
    """
    ✅ Check if user can delete assessment
    Rules:
    - Admin: can delete all
    - Manager: can delete own + direct reports' assessments
    - Employee: cannot delete (or only DRAFT)
    """
    access = get_assessment_access(user)
    
    # Admin can delete all
    if access['can_view_all']:
        return True, "Admin - Full Access"
    
    # Regular employee cannot delete assessments
    if not access['is_manager']:
        return False, "Only managers and admins can delete assessments"
    
    # Manager can delete accessible assessments
    if access['accessible_employee_ids']:
        if assessment.employee_id in access['accessible_employee_ids']:
            return True, "Manager access"
    
    return False, "No delete access to this assessment"