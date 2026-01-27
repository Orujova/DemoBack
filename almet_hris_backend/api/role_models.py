# api/role_models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

class Role(models.Model):
    """Custom roles for RBAC system"""
    
    # BigAutoField istifadə edirik (Django tərəfindən tövsiyə olunur)
    # AutoField yazsanız da Django avtomatik yaradır, lakin explicit yazmaq daha yaxşıdır
    name = models.CharField(max_length=100, unique=True)
   
    # Permissions
    is_active = models.BooleanField(default=True)
    is_system_role = models.BooleanField(default=False, help_text="System roles cannot be deleted")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='created_roles'
    )
    
    class Meta:
        ordering = ['name']
        verbose_name = "Role"
        verbose_name_plural = "Roles"
    
    def __str__(self):
        return self.name


class Permission(models.Model):
    """Granular permissions for actions"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codename = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100, blank=True, help_text="Custom category name")
    description = models.TextField(blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['category', 'name']
        verbose_name = "Permission"
        verbose_name_plural = "Permissions"
    
    def __str__(self):
        return f"{self.name} ({self.codename})"


class RolePermission(models.Model):
    """Many-to-many relationship between roles and permissions"""
    
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='role_permissions')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='permission_roles')
    
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='granted_permissions'
    )
    
    class Meta:
        unique_together = ['role', 'permission']
        verbose_name = "Role Permission"
        verbose_name_plural = "Role Permissions"
    
    def __str__(self):
        return f"{self.role.name} - {self.permission.name}"


class EmployeeRole(models.Model):
    """Assign roles to employees"""
    
    employee = models.ForeignKey(
        'Employee', 
        on_delete=models.CASCADE, 
        related_name='employee_roles'
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='assigned_to_employees')
    
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='assigned_roles'
    )
    
    is_active = models.BooleanField(default=True)
   
    
    class Meta:
        unique_together = ['employee', 'role']
        ordering = ['-assigned_at']
        verbose_name = "Employee Role"
        verbose_name_plural = "Employee Roles"
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.role.name}"
    
    