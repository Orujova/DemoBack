# api/handover_permissions.py - WITH ROLE SYSTEM
from rest_framework import permissions
from django.db.models import Q
from .models import Employee


def is_admin_user(user):
    """Check if user has Admin role or is superuser/staff"""
    # Django built-in admin check
    if user.is_staff or user.is_superuser:
        return True
    
    # Role-based admin check
    try:
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


def get_handover_access(user):
    """Get user's handover access permissions"""
    
    # Admin - Full Access
    if is_admin_user(user):
        return {
            'is_admin': True,
            'is_manager': True,
            'employee': None,
            'subordinate_ids': None  # None means ALL
        }
    
    try:
        employee = Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return {
            'is_admin': False,
            'is_manager': False,
            'employee': None,
            'subordinate_ids': []
        }
    
    # Get all subordinates recursively
    def get_all_subordinates(emp):
        subordinates = []
        direct_reports = Employee.objects.filter(
            line_manager=emp,
            is_deleted=False
        )
        
        for report in direct_reports:
            subordinates.append(report.id)
            subordinates.extend(get_all_subordinates(report))
        
        return subordinates
    
    subordinate_ids = get_all_subordinates(employee)
    is_manager = len(subordinate_ids) > 0
    
    return {
        'is_admin': False,
        'is_manager': is_manager,
        'employee': employee,
        'subordinate_ids': subordinate_ids
    }


class HandoverPermission(permissions.BasePermission):
    """
    Custom permission for Handover system with role-based access
    
    Access Rules:
    - Admin (Role or Django Staff): FULL access to everything
    - Manager: Can see own + subordinates' handovers, can approve them
    - Employee: Can see own handovers only, can perform own actions
    """
    
    def has_permission(self, request, view):
        """Check if user has permission to access the view"""
        if not request.user.is_authenticated:
            return False
        
        # Admins have FULL access
        if is_admin_user(request.user):
            return True
        
        # All authenticated users can access basic views
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check if user has permission for specific handover"""
        user = request.user
        
        # Get access permissions
        access = get_handover_access(user)
        
        # ⭐ CRITICAL: Admins have FULL access to ALL actions
        if access['is_admin']:
            return True
        
        employee = access['employee']
        if not employee:
            return False
        
        # Check if user is involved in this handover
        is_handing_over = obj.handing_over_employee == employee
        is_taking_over = obj.taking_over_employee == employee
        is_line_manager = obj.line_manager == employee
        
        # Check if user is manager of involved employees
        subordinate_ids = access.get('subordinate_ids', [])
        is_ho_manager = obj.handing_over_employee_id in subordinate_ids
        is_to_manager = obj.taking_over_employee_id in subordinate_ids
        
        # View permissions
        if view.action in ['retrieve', 'activity_log']:
            return (
                is_handing_over or 
                is_taking_over or 
                is_line_manager or
                is_ho_manager or
                is_to_manager
            )
        
        # Update permissions - only before signing
        if view.action in ['update', 'partial_update']:
            return is_handing_over and not obj.ho_signed
        
        # Delete permissions - only creator before signing
        if view.action == 'destroy':
            return is_handing_over and not obj.ho_signed
        
        # Action permissions
        if view.action == 'sign_ho':
            return is_handing_over
        
        if view.action == 'sign_to':
            return is_taking_over
        
        if view.action in ['approve_lm', 'reject_lm', 'request_clarification']:
            return (
                is_line_manager or 
                is_ho_manager or 
                is_to_manager
            )
        
        if view.action == 'resubmit':
            return is_handing_over
        
        if view.action == 'takeover':
            return is_taking_over
        
        if view.action == 'takeback':
            return is_handing_over
        
        return False


class HandoverTaskPermission(permissions.BasePermission):
    """Permission for Handover Tasks"""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # ⭐ Admins have FULL access
        if is_admin_user(request.user):
            return True
        
        return True
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # ⭐ Admins have FULL access
        if is_admin_user(user):
            return True
        
        try:
            employee = Employee.objects.get(user=user, is_deleted=False)
        except Employee.DoesNotExist:
            return False
        
        handover = obj.handover
        
        # Can view if involved in handover
        if view.action in ['retrieve', 'list']:
            return (
                handover.handing_over_employee == employee or
                handover.taking_over_employee == employee or
                handover.line_manager == employee
            )
        
        # Only taking over employee can update task status
        if view.action == 'update_status':
            return handover.taking_over_employee == employee
        
        return False


class HandoverAttachmentPermission(permissions.BasePermission):
    """Permission for Handover Attachments"""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # ⭐ Admins have FULL access
        if is_admin_user(request.user):
            return True
        
        return True
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # ⭐ Admins have FULL access
        if is_admin_user(user):
            return True
        
        try:
            employee = Employee.objects.get(user=user, is_deleted=False)
        except Employee.DoesNotExist:
            return False
        
        handover = obj.handover
        
        # Can view if involved in handover
        if view.action in ['retrieve', 'list']:
            return (
                handover.handing_over_employee == employee or
                handover.taking_over_employee == employee or
                handover.line_manager == employee
            )
        
        # Can delete own uploads before handover is approved
        if view.action == 'destroy':
            return (
                obj.uploaded_by == user and 
                not handover.lm_approved
            )
        
        return False


def filter_handover_queryset(user, queryset):
    """Filter handover queryset based on user access"""
    
    access = get_handover_access(user)
    
    # Admin - see all
    if access['is_admin']:
        return queryset
    
    employee = access['employee']
    if not employee:
        return queryset.none()
    
    subordinate_ids = access.get('subordinate_ids', [])
    
    # Filter: handovers where user is HO, TO, LM, or manager of HO/TO
    return queryset.filter(
        Q(handing_over_employee=employee) |
        Q(taking_over_employee=employee) |
        Q(line_manager=employee) |
        Q(handing_over_employee_id__in=subordinate_ids) |
        Q(taking_over_employee_id__in=subordinate_ids)
    ).distinct()


def can_user_view_handover(user, handover):
    """Check if user can view a specific handover"""
    
    access = get_handover_access(user)
    
    # Admin can view all
    if access['is_admin']:
        return True, "Admin - Full Access"
    
    employee = access['employee']
    if not employee:
        return False, "No employee profile"
    
    # Check direct involvement
    if handover.handing_over_employee == employee:
        return True, "You are handing over"
    
    if handover.taking_over_employee == employee:
        return True, "You are taking over"
    
    if handover.line_manager == employee:
        return True, "You are the line manager"
    
    # Check if manager of involved employees
    subordinate_ids = access.get('subordinate_ids', [])
    if handover.handing_over_employee_id in subordinate_ids:
        return True, f"Manager of {handover.handing_over_employee_name}"
    
    if handover.taking_over_employee_id in subordinate_ids:
        return True, f"Manager of {handover.taking_over_employee_name}"
    
    return False, "No access to this handover"