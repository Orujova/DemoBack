# api/role_serializers.py - COMPLETE VERSION

from rest_framework import serializers
from .role_models import Role, Permission, RolePermission, EmployeeRole
from .models import Employee
from django.utils import timezone


class PermissionSerializer(serializers.ModelSerializer):
    """Complete permission serializer with all fields"""
    
    class Meta:
        model = Permission
        fields = [
            'id', 'codename', 'name', 'category', 'description',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class RolePermissionSerializer(serializers.ModelSerializer):
    """Role-Permission relationship serializer"""
    permission_detail = PermissionSerializer(source='permission', read_only=True)
    granted_by_username = serializers.CharField(source='granted_by.username', read_only=True)
    
    class Meta:
        model = RolePermission
        fields = [
            'id', 'role', 'permission', 'permission_detail',
            'granted_at', 'granted_by', 'granted_by_username'
        ]
        read_only_fields = ['id', 'granted_at', 'granted_by']


class RoleSerializer(serializers.ModelSerializer):
    """Complete role serializer with nested permissions"""
    permissions = serializers.SerializerMethodField()
    permissions_count = serializers.SerializerMethodField()
    employees_count = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = Role
        fields = [
            'id', 'name',
            'is_active', 'is_system_role',
            'permissions', 'permissions_count', 'employees_count',
            'created_at', 'updated_at', 'created_by', 'created_by_username'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_system_role']
    
    def get_permissions(self, obj):
        """Get all permissions for this role"""
        role_permissions = obj.role_permissions.select_related('permission').all()
        return [
            {
                'id': str(rp.permission.id),
                'codename': rp.permission.codename,
                'name': rp.permission.name,
                'category': rp.permission.category,
                'granted_at': rp.granted_at
            }
            for rp in role_permissions
        ]
    
    def get_permissions_count(self, obj):
        """Count of permissions"""
        return obj.role_permissions.count()
    
    def get_employees_count(self, obj):
        """Count of active employees with this role"""
        return obj.assigned_to_employees.filter(is_active=True).count()


class RoleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for role lists"""
    permissions_count = serializers.SerializerMethodField()
    employees_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Role
        fields = [
            'id', 'name', 'is_active', 'is_system_role',
            'permissions_count', 'employees_count'
        ]
    
    def get_permissions_count(self, obj):
        return obj.role_permissions.count()
    
    def get_employees_count(self, obj):
        return obj.assigned_to_employees.filter(is_active=True).count()


class EmployeeRoleSerializer(serializers.ModelSerializer):
    """Complete employee role serializer with all details"""
    role_detail = RoleListSerializer(source='role', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id_display = serializers.CharField(source='employee.employee_id', read_only=True)
    employee_email = serializers.CharField(source='employee.email', read_only=True)
    employee_job_title = serializers.CharField(source='employee.job_title', read_only=True)

    assigned_by_username = serializers.CharField(source='assigned_by.username', read_only=True)
    
    class Meta:
        model = EmployeeRole
        fields = [
            'id', 'employee', 'employee_name', 'employee_id_display',
            'employee_email', 'employee_job_title',
            'role', 'role_detail',
            'assigned_at', 'assigned_by', 'assigned_by_username',
            'is_active'
        ]
        read_only_fields = ['id', 'assigned_at', 'assigned_by']
    
   


class EmployeeRoleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for employee role lists"""
    role_name = serializers.CharField(source='role.name', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
   
    class Meta:
        model = EmployeeRole
        fields = [
            'id', 'employee', 'employee_name',
            'role', 'role_name',
            'is_active', 
        ]
    
    


class AssignRoleSerializer(serializers.Serializer):
    """Serializer for assigning a single role to a single employee"""
    employee_id = serializers.IntegerField()
    role_id = serializers.IntegerField()  # UUID-dən Integer-ə dəyişdi
    
    
    def validate_employee_id(self, value):
        """Validate employee exists"""
        try:
            Employee.objects.get(id=value, is_deleted=False)
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Employee not found or deleted")
        return value
    
    def validate_role_id(self, value):
        """Validate role exists and is active"""
        try:
            Role.objects.get(id=value, is_active=True)
        except Role.DoesNotExist:
            raise serializers.ValidationError("Role not found or inactive")
        return value

class BulkAssignRoleSerializer(serializers.Serializer):
    """Serializer for assigning a single role to multiple employees"""
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=100,
        help_text="List of employee IDs"
    )
    role_id = serializers.IntegerField()  # UUID-dən Integer-ə dəyişdi
  
    
    def validate_employee_ids(self, value):
        """Validate all employees exist"""
        existing_count = Employee.objects.filter(
            id__in=value, 
            is_deleted=False
        ).count()
        
        if existing_count != len(value):
            raise serializers.ValidationError(
                f"Some employees not found. Found {existing_count} out of {len(value)}"
            )
        return value
    
    def validate_role_id(self, value):
        """Validate role exists and is active"""
        try:
            Role.objects.get(id=value, is_active=True)
        except Role.DoesNotExist:
            raise serializers.ValidationError("Role not found or inactive")
        return value

class BulkAssignPermissionsToRoleSerializer(serializers.Serializer):
    """Serializer for assigning permissions to multiple roles"""
    role_ids = serializers.ListField(
        child=serializers.IntegerField(),  # UUID-dən Integer-ə dəyişdi
        min_length=1,
        max_length=50,
        help_text="List of role IDs"
    )
    permission_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text="List of permission UUIDs to assign"
    )
    
    def validate_role_ids(self, value):
        """Validate all roles exist"""
        existing_count = Role.objects.filter(
            id__in=value,
            is_active=True
        ).count()
        
        if existing_count != len(value):
            raise serializers.ValidationError(
                f"Some roles not found or inactive. Found {existing_count} out of {len(value)}"
            )
        return value
    
    def validate_permission_ids(self, value):
        """Validate all permissions exist"""
        existing_count = Permission.objects.filter(
            id__in=value,
            is_active=True
        ).count()
        
        if existing_count != len(value):
            raise serializers.ValidationError(
                f"Some permissions not found or inactive. Found {existing_count} out of {len(value)}"
            )
        return value

class BulkAssignRolesToEmployeeSerializer(serializers.Serializer):
    """Serializer for assigning multiple roles to multiple employees"""
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=100,
        help_text="List of employee IDs"
    )
    role_ids = serializers.ListField(
        child=serializers.IntegerField(),  # UUID-dən Integer-ə dəyişdi
        min_length=1,
        help_text="List of role IDs to assign"
    )
   
    
    def validate_employee_ids(self, value):
        """Validate all employees exist"""
        existing_count = Employee.objects.filter(
            id__in=value,
            is_deleted=False
        ).count()
        
        if existing_count != len(value):
            raise serializers.ValidationError(
                f"Some employees not found. Found {existing_count} out of {len(value)}"
            )
        return value
    
    def validate_role_ids(self, value):
        """Validate all roles exist"""
        existing_count = Role.objects.filter(
            id__in=value,
            is_active=True
        ).count()
        
        if existing_count != len(value):
            raise serializers.ValidationError(
                f"Some roles not found or inactive. Found {existing_count} out of {len(value)}"
            )
        return value

class EmployeeWithRolesSerializer(serializers.ModelSerializer):
    """Serializer for employee with their assigned roles"""
    roles = serializers.SerializerMethodField()
    roles_count = serializers.SerializerMethodField()
    active_roles_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'full_name', 'email', 'job_title',
            'business_function', 'department', 'status',
            'roles', 'roles_count', 'active_roles_count'
        ]
    
    def get_roles(self, obj):
        """Get all active roles for employee"""
        employee_roles = obj.employee_roles.filter(
            is_active=True
        ).select_related('role')
        
        return [
            {
                'id': er.role.id,  # Artıq str() lazım deyil
                'name': er.role.name,
                'assigned_at': er.assigned_at,
               
              
            }
            for er in employee_roles
        ]
    
    def get_roles_count(self, obj):
        """Total roles count"""
        return obj.employee_roles.count()
    
    def get_active_roles_count(self, obj):
        """Active roles count"""
        return obj.employee_roles.filter(is_active=True).count()

class RolePermissionBulkSerializer(serializers.Serializer):
    """Serializer for bulk permission assignment to a single role"""
    permission_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text="List of permission UUIDs"
    )
    
    def validate_permission_ids(self, value):
        """Validate all permissions exist"""
        existing_count = Permission.objects.filter(
            id__in=value,
            is_active=True
        ).count()
        
        if existing_count != len(value):
            raise serializers.ValidationError(
                f"Some permissions not found or inactive. Found {existing_count} out of {len(value)}"
            )
        return value