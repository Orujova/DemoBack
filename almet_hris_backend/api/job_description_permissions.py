# api/job_description_permissions.py
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

def get_job_description_access(user):

    from .models import Employee
    employee = Employee.objects.get(user=user, is_deleted=False)
    # Admin - Full Access
    if is_admin_user(user):
        return {
            'can_view_all': True,
            'is_manager': True,
            'employee': employee,
            'accessible_employee_ids': None  # None means ALL
        }
    
    try:
        employee = Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return {
            'can_view_all': False,
            'is_manager': False,
            'employee': employee,
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
        # ✅ Regular employee - CAN VIEW their own job description
        return {
            'can_view_all': False,
            'is_manager': False,
            'employee': employee,
            'accessible_employee_ids': [employee.id]  # Only self
        }

def filter_job_description_queryset(user, queryset):
    """✅ Include DRAFT assignments"""
    access = get_job_description_access(user)
    
    # Admin - see all
    if access['can_view_all']:
        return queryset
    
    # Manager or Employee
    if access['accessible_employee_ids']:
        return queryset.filter(
            Q(assignments__employee_id__in=access['accessible_employee_ids']) &
            Q(assignments__is_active=True)  # is_active=True, status istənilən
        ).distinct()
    
    return queryset.none()

def can_user_view_job_description(user, job_description):
    """
    ✅ Check if user can view a specific job description
    """
    access = get_job_description_access(user)
    
    # Admin can view all
    if access['can_view_all']:
        return True, "Admin - Full Access"
    
    # Check if job description has assignments for accessible employees
    if access['accessible_employee_ids']:
        accessible_assignments = job_description.assignments.filter(
            employee_id__in=access['accessible_employee_ids'],
            is_active=True
        )
        
        if accessible_assignments.exists():
            assignment = accessible_assignments.first()
            
            # Check if it's the user's own job description
            if access['employee'] and assignment.employee_id == access['employee'].id:
                return True, "Your job description"
            else:
                return True, f"Direct report: {assignment.employee.full_name}"
        
    return False, "No access to this job description"

