# api/role_views.py - COMPLETE CLEAN VERSION

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .role_models import Role, Permission, RolePermission, EmployeeRole
from .role_serializers import (
    RoleSerializer, PermissionSerializer, 
    EmployeeRoleSerializer, AssignRoleSerializer, BulkAssignRoleSerializer,
    BulkAssignPermissionsToRoleSerializer, BulkAssignRolesToEmployeeSerializer
)
from .models import Employee
import logging

logger = logging.getLogger(__name__)


class RoleViewSet(viewsets.ModelViewSet):
    """Complete ViewSet for Role CRUD and Permission Management"""
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Role.objects.annotate(
            permissions_count=Count('role_permissions', distinct=True),
            employees_count=Count('assigned_to_employees', filter=Q(assigned_to_employees__is_active=True), distinct=True)
        )
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        is_system = self.request.query_params.get('is_system_role')
        if is_system is not None:
            queryset = queryset.filter(is_system_role=is_system.lower() == 'true')
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_system_role:
            return Response(
                {'error': 'System roles cannot be deleted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if instance.assigned_to_employees.filter(is_active=True).exists():
            return Response(
                {'error': 'Cannot delete role that is assigned to employees'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().destroy(request, *args, **kwargs)
    
    
    @swagger_auto_schema(
        method='post',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['role_ids', 'permission_ids'],
            properties={
                'role_ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY, 
                    items=openapi.Schema(type=openapi.TYPE_INTEGER)  # UUID-dən Integer-ə
                ),
                'permission_ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY, 
                    items=openapi.Schema(type=openapi.TYPE_STRING, format='uuid')
                )
            }
        )
    )
    @action(detail=False, methods=['post'])
    def bulk_assign_permissions(self, request):
        """Assign permissions to multiple roles"""
        serializer = BulkAssignPermissionsToRoleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        role_ids = serializer.validated_data['role_ids']
        permission_ids = serializer.validated_data['permission_ids']
        
        try:
            roles = Role.objects.filter(id__in=role_ids, is_active=True)
            permissions = Permission.objects.filter(id__in=permission_ids, is_active=True)
            
            results = {'success': 0, 'failed': 0, 'details': []}
            
            with transaction.atomic():
                for role in roles:
                    try:
                        role.role_permissions.all().delete()
                        for permission in permissions:
                            RolePermission.objects.create(role=role, permission=permission, granted_by=request.user)
                        
                        results['success'] += 1
                        results['details'].append({
                            'role_id': role.id,  # Artıq str() lazım deyil
                            'role_name': role.name,
                            'status': 'success',
                            'permissions_assigned': permissions.count()
                        })
                    except Exception as e:
                        results['failed'] += 1
                        results['details'].append({
                            'role_id': role.id,
                            'role_name': role.name,
                            'status': 'failed',
                            'error': str(e)
                        })
            
            return Response({
                'success': True,
                'message': f'{permissions.count()} permissions assigned to {results["success"]} roles',
                'results': results
            })
        except Exception as e:
            logger.error(f'Error in bulk assign permissions: {e}')
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
   
    @swagger_auto_schema(
        method='delete',
        manual_parameters=[
            openapi.Parameter(
                'permission_id',
                openapi.IN_QUERY,
                description='Permission UUID to remove',
                type=openapi.TYPE_STRING,
                format='uuid',
                required=True
            )
        ]
    )
    @action(detail=True, methods=['delete'])
    def remove_permission(self, request, pk=None):
        """Remove single permission from role"""
        role = self.get_object()
        permission_id = request.query_params.get('permission_id')
        
        if not permission_id:
            return Response({'error': 'permission_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            role_permission = role.role_permissions.get(permission_id=permission_id)
            permission_name = role_permission.permission.name
            role_permission.delete()
            
            return Response({
                'success': True,
                'message': f'Permission "{permission_name}" removed from {role.name}'
            })
        except RolePermission.DoesNotExist:
            return Response({'error': 'Permission not assigned to this role'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['get'])
    def permissions(self, request, pk=None):
        """Get all permissions for role"""
        role = self.get_object()
        role_permissions = role.role_permissions.select_related('permission').all()
        
        return Response({
            'role_id': role.id,  # Artıq str() lazım deyil
            'role_name': role.name,
            'permissions_count': role_permissions.count(),
            'permissions': [
                {
                    'id': str(rp.permission.id),
                    'codename': rp.permission.codename,
                    'name': rp.permission.name,
                    'category': rp.permission.category,
                    'granted_at': rp.granted_at
                }
                for rp in role_permissions
            ]
        })
    
    @action(detail=True, methods=['get'])
    def employees(self, request, pk=None):
        """Get all employees with this role"""
        role = self.get_object()
        employee_roles = role.assigned_to_employees.filter(is_active=True).select_related('employee')
        
        return Response({
            'role_id': role.id,  # Artıq str() lazım deyil
            'role_name': role.name,
            'employees_count': employee_roles.count(),
            'employees': [
                {
                    'id': er.employee.id,
                    'employee_id': er.employee.employee_id,
                    'full_name': er.employee.full_name,
                    'email': er.employee.email,
                    'assigned_at': er.assigned_at
                }
                for er in employee_roles
            ]
        })

class PermissionViewSet(viewsets.ModelViewSet):
    """Complete CRUD ViewSet for Permission management"""
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Permission.objects.all()
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(codename__icontains=search))
        
        return queryset
    
    def destroy(self, request, *args, **kwargs):
        """Soft delete permission"""
        instance = self.get_object()
        
        if instance.permission_roles.exists():
            return Response({
                'error': 'Cannot delete permission that is assigned to roles',
                'assigned_to_roles_count': instance.permission_roles.count()
            }, status=status.HTTP_400_BAD_REQUEST)
        
        instance.is_active = False
        instance.save()
        
        return Response({'success': True, 'message': f'Permission "{instance.name}" deactivated'})
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Get permissions grouped by category"""
        permissions = self.get_queryset()
        categories = {}
        
        for perm in permissions:
            category = perm.category or 'Uncategorized'
            if category not in categories:
                categories[category] = []
            categories[category].append(PermissionSerializer(perm).data)
        
        return Response({
            'categories': categories,
            'total_categories': len(categories),
            'total_permissions': permissions.count()
        })
    
    

class EmployeeRoleViewSet(viewsets.ModelViewSet):
    """Complete ViewSet for Employee Role assignments"""
    queryset = EmployeeRole.objects.all()
    serializer_class = EmployeeRoleSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = EmployeeRole.objects.select_related('employee', 'role', 'assigned_by')
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        employee_id = self.request.query_params.get('employee_id')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        
        role_id = self.request.query_params.get('role_id')
        if role_id:
            queryset = queryset.filter(role_id=role_id)
        
        return queryset
    
    
    @swagger_auto_schema(method='post', request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['employee_ids', 'role_ids'],
        properties={
            'employee_ids': openapi.Schema(
                type=openapi.TYPE_ARRAY, 
                items=openapi.Schema(type=openapi.TYPE_INTEGER)
            ),
            'role_ids': openapi.Schema(
                type=openapi.TYPE_ARRAY, 
                items=openapi.Schema(type=openapi.TYPE_INTEGER)  # UUID-dən Integer-ə
            )
        }
    ))
    @action(detail=False, methods=['post'])
    def bulk_assign_roles(self, request):
        """Assign multiple roles to multiple employees"""
        serializer = BulkAssignRolesToEmployeeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_ids = serializer.validated_data['employee_ids']
        role_ids = serializer.validated_data['role_ids']
        
        
        try:
            employees = Employee.objects.filter(id__in=employee_ids, is_deleted=False)
            roles = Role.objects.filter(id__in=role_ids, is_active=True)
            
            if employees.count() != len(employee_ids):
                return Response({'error': 'Some employees not found'}, status=status.HTTP_400_BAD_REQUEST)
            if roles.count() != len(role_ids):
                return Response({'error': 'Some roles not found'}, status=status.HTTP_400_BAD_REQUEST)
            
            results = {'total_assignments': 0, 'success': 0, 'updated': 0, 'failed': 0, 'details': []}
            
            with transaction.atomic():
                for employee in employees:
                    employee_result = {
                        'employee_id': employee.employee_id,
                        'employee_name': employee.full_name,
                        'roles_assigned': []
                    }
                    
                    for role in roles:
                        try:
                            employee_role, created = EmployeeRole.objects.update_or_create(
                                employee=employee,
                                role=role,
                                defaults={'assigned_by': request.user,  'is_active': True}
                            )
                            
                            results['total_assignments'] += 1
                            if created:
                                results['success'] += 1
                            else:
                                results['updated'] += 1
                            
                            employee_result['roles_assigned'].append({
                                'role_id': role.id,  # Artıq str() lazım deyil
                                'role_name': role.name,
                                'status': 'created' if created else 'updated'
                            })
                        except Exception as e:
                            results['failed'] += 1
                            employee_result['roles_assigned'].append({
                                'role_id': role.id,
                                'status': 'failed',
                                'error': str(e)
                            })
                    
                    results['details'].append(employee_result)
            
            return Response({
                'success': True,
                'message': f'{len(roles)} roles assigned to {len(employees)} employees',
                'summary': {
                    'employees_count': len(employees),
                    'roles_count': len(roles),
                    'total_assignments': results['total_assignments'],
                    'created': results['success'],
                    'updated': results['updated'],
                    'failed': results['failed']
                },
                'details': results['details']
            })
        except Exception as e:
            logger.error(f'Error in bulk assign roles: {e}')
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
   
    @swagger_auto_schema(method='delete', manual_parameters=[
        openapi.Parameter('employee_id', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=True),
        openapi.Parameter('role_id', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=True)  # UUID-dən Integer-ə
    ])
    @action(detail=False, methods=['delete'])
    def revoke_role(self, request):
        """Revoke role from employee"""
        employee_id = request.query_params.get('employee_id')
        role_id = request.query_params.get('role_id')
        
        if not employee_id or not role_id:
            return Response({'error': 'Both employee_id and role_id are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            employee_id = int(employee_id)
            role_id = int(role_id)  # role_id də integer olmalıdır
            employee_role = EmployeeRole.objects.get(employee_id=employee_id, role_id=role_id)
            
            employee_name = employee_role.employee.full_name
            role_name = employee_role.role.name
            employee_role.delete()
            
            return Response({
                'success': True,
                'message': f'Role "{role_name}" revoked from {employee_name}'
            })
        except (ValueError, TypeError):
            return Response({'error': 'employee_id and role_id must be valid integers'}, status=status.HTTP_400_BAD_REQUEST)
        except EmployeeRole.DoesNotExist:
            return Response({'error': 'Employee role assignment not found'}, status=status.HTTP_404_NOT_FOUND)
    
    