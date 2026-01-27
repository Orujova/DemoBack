# api/serializers.py - ENHANCED: Complete Employee Management with Contract Status Management

from rest_framework import serializers
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from datetime import date, timedelta
from .models import (
    Employee, BusinessFunction, Department, Unit, JobFunction,
    PositionGroup, EmployeeTag, EmployeeStatus, EmployeeDocument,
    VacantPosition, EmployeeActivity,  ContractTypeConfig,JobTitle
)
import logging
import os
from django.db import models 
logger = logging.getLogger(__name__)
from .job_description_models import JobDescription

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name']
        read_only_fields = ['id', 'username']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

class BusinessFunctionSerializer(serializers.ModelSerializer):
    employee_count = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessFunction
        fields = ['id', 'name', 'code',  'is_active', 'employee_count', 'created_at']

    
    def get_employee_count(self, obj):
        return obj.employees.filter(status__affects_headcount=True).count()


class DepartmentSerializer(serializers.ModelSerializer):
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    business_function_code = serializers.CharField(source='business_function.code', read_only=True)
    employee_count = serializers.SerializerMethodField()
    unit_count = serializers.SerializerMethodField()
    
    # ✅ GET üçün - read_only (integer)
    business_function_id = serializers.IntegerField(
        source='business_function.id',
        read_only=True
    )
    
    # ✅ POST/PUT üçün - write_only (list)
    business_function_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="Business function ID(s) - array for create, single for update"
    )
    
    class Meta:
        model = Department
        fields = [
            'id', 'name',
            'business_function_id',      # GET-də görsənir (integer)
            'business_function_ids',     # POST/PUT-da işləyir (list)
            'business_function_name', 
            'business_function_code',
            'is_active', 
            'employee_count', 
            'unit_count', 
            'created_at'
        ]
    
    def to_representation(self, instance):
        """Format text fields to title case"""
        data = super().to_representation(instance)
        
        # ✅ Title case tətbiq et
        text_fields = ['name']
        
        for field in text_fields:
            if field in data and data[field]:
                data[field] = str(data[field]).strip().title()
        
        return data
    
    def get_employee_count(self, obj):
        return obj.employees.filter(status__affects_headcount=True).count()
    
    def get_unit_count(self, obj):
        return obj.units.filter(is_active=True).count()
    
    def validate_business_function_ids(self, value):
        """Validate business_function_ids"""
        if not value:
            raise serializers.ValidationError("business_function_ids is required")
        
        # Ensure it's a list
        if not isinstance(value, list):
            value = [value]
        
        # Validate all IDs exist
        existing_count = BusinessFunction.objects.filter(
            id__in=value, 
            is_active=True
        ).count()
        
        if existing_count != len(value):
            raise serializers.ValidationError(
                "Some business function IDs do not exist or are inactive"
            )
        
        return value
    
    def create(self, validated_data):
        """Handle both single and bulk creation"""
        business_function_ids = validated_data.pop('business_function_ids', None)
        
        if not business_function_ids:
            raise serializers.ValidationError("business_function_ids is required")
        
        # Ensure it's a list
        if not isinstance(business_function_ids, list):
            business_function_ids = [business_function_ids]
        
        # Single creation (1 ID)
        if len(business_function_ids) == 1:
            try:
                business_function = BusinessFunction.objects.get(id=business_function_ids[0])
                validated_data['business_function'] = business_function
                return super().create(validated_data)
            except BusinessFunction.DoesNotExist:
                raise serializers.ValidationError("Business function not found")
        
        # Bulk creation (2+ IDs)
        name = validated_data['name']
        is_active = validated_data.get('is_active', True)
        
        created_departments = []
        errors = []
        
        for bf_id in business_function_ids:
            try:
                business_function = BusinessFunction.objects.get(id=bf_id)
                
                if Department.objects.filter(
                    business_function=business_function,
                    name=name
                ).exists():
                    errors.append(f"Department '{name}' already exists for {business_function.name}")
                    continue
                
                department = Department.objects.create(
                    name=name,
                    business_function=business_function,
                    is_active=is_active
                )
                created_departments.append(department)
                
            except Exception as e:
                errors.append(f"Error for BF {bf_id}: {str(e)}")
        
        self.context['bulk_result'] = {
            'created_departments': created_departments,
            'errors': errors,
            'success_count': len(created_departments),
            'error_count': len(errors)
        }
        
        if created_departments:
            return created_departments[0]
        else:
            raise serializers.ValidationError({"errors": errors})
    
    def update(self, instance, validated_data):
        """Handle update with single business_function_id"""
        business_function_ids = validated_data.pop('business_function_ids', None)
        
        if business_function_ids:
            # For update, expect single ID
            bf_id = business_function_ids[0] if isinstance(business_function_ids, list) else business_function_ids
            
            try:
                business_function = BusinessFunction.objects.get(id=bf_id, is_active=True)
                instance.business_function = business_function
            except BusinessFunction.DoesNotExist:
                raise serializers.ValidationError("Business function not found")
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance
class UnitSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    business_function_name = serializers.CharField(source='department.business_function.name', read_only=True)
    employee_count = serializers.SerializerMethodField()
    
    # ✅ GET üçün - read_only (integer)
    department_id = serializers.IntegerField(
        source='department.id',
        read_only=True
    )
    
    # ✅ POST/PUT üçün - write_only (list)
    department_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="Department ID(s) - can be single integer or array"
    )
    
    class Meta:
        model = Unit
        fields = [
            'id',
            'name',
            'department_id',      # GET-də görsənir (integer)
            'department_ids',     # POST/PUT-da işləyir (list)
            'department_name',
            'business_function_name',
            'is_active',
            'employee_count',
            'created_at'
        ]
    
    def to_representation(self, instance):
        """Format text fields to title case"""
        data = super().to_representation(instance)
        
        # ✅ Title case tətbiq et
        text_fields = ['name']
        for field in text_fields:
            if field in data and data[field]:
                data[field] = str(data[field]).strip().title()
        
        return data
    
    def get_employee_count(self, obj):
        """Get active employee count"""
        return obj.employees.filter(status__affects_headcount=True).count()
    
    def validate_department_ids(self, value):
        """Validate and normalize department_ids"""
        if not value:
            raise serializers.ValidationError("department_ids is required")
        
        # Ensure it's a list
        if not isinstance(value, list):
            value = [value]
        
        # Validate all IDs exist
        existing_count = Department.objects.filter(
            id__in=value,
            is_active=True
        ).count()
        
        if existing_count != len(value):
            raise serializers.ValidationError(
                "Some department IDs do not exist or are inactive"
            )
        
        return value
    
    def create(self, validated_data):
        """Handle both single and bulk creation"""
        department_ids = validated_data.pop('department_ids', None)
        
        if not department_ids:
            raise serializers.ValidationError("department_ids is required")
        
        # Ensure it's a list
        if not isinstance(department_ids, list):
            department_ids = [department_ids]
        
        # Single creation (1 ID)
        if len(department_ids) == 1:
            try:
                department = Department.objects.get(id=department_ids[0])
                validated_data['department'] = department
                return super().create(validated_data)
            except Department.DoesNotExist:
                raise serializers.ValidationError("Department not found")
        
        # Bulk creation (2+ IDs)
        name = validated_data['name']
        is_active = validated_data.get('is_active', True)
        created_units = []
        errors = []
        
        for dept_id in department_ids:
            try:
                department = Department.objects.get(id=dept_id)
                
                # Check if already exists
                if Unit.objects.filter(department=department, name=name).exists():
                    errors.append(f"Unit '{name}' already exists for {department.name}")
                    continue
                
                unit = Unit.objects.create(
                    name=name,
                    department=department,
                    is_active=is_active
                )
                created_units.append(unit)
                
            except Exception as e:
                errors.append(f"Error for Department {dept_id}: {str(e)}")
        
        # Store results for response
        self.context['bulk_result'] = {
            'created_units': created_units,
            'errors': errors,
            'success_count': len(created_units),
            'error_count': len(errors)
        }
        
        if created_units:
            return created_units[0]
        else:
            raise serializers.ValidationError({"errors": errors})
    
    def update(self, instance, validated_data):
        """Handle single ID for update"""
        department_ids = validated_data.pop('department_ids', None)
        
        if department_ids:
            # For update, take first ID from array or use single value
            dept_id = department_ids[0] if isinstance(department_ids, list) else department_ids
            
            try:
                department = Department.objects.get(id=dept_id, is_active=True)
                instance.department = department
            except Department.DoesNotExist:
                raise serializers.ValidationError("Department not found")
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance   


class JobTitleSerializer(serializers.ModelSerializer):

    employee_count = serializers.SerializerMethodField()
    
    class Meta:
        model = JobTitle
        fields = [
            'id', 'name', 'description',
            'is_active', 'employee_count', 'created_at', 'updated_at'
        ]
    def to_representation(self, instance):
        """Format text fields to title case"""
        data = super().to_representation(instance)
        
        # ✅ Title case tətbiq et - ad və soyad
        text_fields = [
            'name',  
            
        ]
        
        for field in text_fields:
            if field in data and data[field]:
                # Strip whitespace və title case
                data[field] = str(data[field]).strip().title()
        
        return data
    
    def get_employee_count(self, obj):
        return Employee.objects.filter(
            job_title=obj.name,
            status__affects_headcount=True,
            is_deleted=False
        ).count()

class JobFunctionSerializer(serializers.ModelSerializer):
    employee_count = serializers.SerializerMethodField()
    
    class Meta:
        model = JobFunction
        fields = ['id', 'name',  'is_active', 'employee_count', 'created_at']
    def to_representation(self, instance):
        """Format text fields to title case"""
        data = super().to_representation(instance)
        
        # ✅ Title case tətbiq et - ad və soyad
        text_fields = [
            'name',  
            
        ]
        
        for field in text_fields:
            if field in data and data[field]:
                # Strip whitespace və title case
                data[field] = str(data[field]).strip().title()
        
        return data
    
    def get_employee_count(self, obj):
        return obj.employees.filter(status__affects_headcount=True).count()

class PositionGroupSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source='get_name_display', read_only=True)
    grading_levels = serializers.SerializerMethodField()
    employee_count = serializers.SerializerMethodField()
    grading_shorthand = serializers.CharField(read_only=True)
    
    class Meta:
        model = PositionGroup
        fields = [
            'id', 'name', 'display_name', 'hierarchy_level', 'grading_shorthand',
            'grading_levels', 'is_active', 'employee_count', 'created_at'
        ]
    
    def get_grading_levels(self, obj):
        """Get grading level options for this position"""
        return obj.get_grading_levels()
    
    def get_employee_count(self, obj):
        return obj.employees.filter(status__affects_headcount=True).count()

class EmployeeTagSerializer(serializers.ModelSerializer):
    employee_count = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeTag
        fields = ['id', 'name',  'color', 'is_active', 'employee_count', 'created_at']
    
    def get_employee_count(self, obj):
        return obj.employees.filter(status__affects_headcount=True).count()

class EmployeeStatusSerializer(serializers.ModelSerializer):
    employee_count = serializers.SerializerMethodField()
    auto_transition_to_name = serializers.CharField(source='auto_transition_to.name', read_only=True)
    
    class Meta:
        model = EmployeeStatus
        fields = [
            'id', 'name', 'status_type', 'color', 'description', 'order', 
            'affects_headcount', 'allows_org_chart', 
            'auto_transition_enabled', 'auto_transition_days', 'auto_transition_to', 'auto_transition_to_name',
            'is_transitional', 'transition_priority',
            'send_notifications', 'notification_template',
            'is_system_status', 'is_default_for_new_employees',
            'is_active', 'employee_count', 'created_at'
        ]
    
    def get_employee_count(self, obj):
        return obj.employees.count()

class ContractTypeConfigSerializer(serializers.ModelSerializer):
    total_days_until_active = serializers.SerializerMethodField()
    employee_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ContractTypeConfig
        fields = [
            'id', 'contract_type', 'display_name', 
           'probation_days', 'total_days_until_active',
            'enable_auto_transitions', 'transition_to_inactive_on_end',
            'notify_days_before_end', 'employee_count', 'is_active', 'created_at'
        ]
    
    def get_total_days_until_active(self, obj):
        return obj.get_total_days_until_active()
    
    def get_employee_count(self, obj):
        return Employee.objects.filter(contract_duration=obj.contract_type).count()

class VacantPositionCreateSerializer(serializers.ModelSerializer):
    """Enhanced serializer for creating vacant positions with business function based position_id"""
    
    # Auto-generate position_id preview like employee_id
    position_id_preview = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = VacantPosition
        fields = [
            # Required organizational fields
            'business_function', 'department', 'unit', 'job_function', 
            'position_group', 'job_title', 'grading_level',
            
            # Management
            'reporting_to',
            
            # Configuration
            'is_visible_in_org_chart', 'include_in_headcount',
            
            # Additional info
            'notes',
            
            # Read-only fields
            'position_id_preview', 'id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['position_id', 'created_at', 'updated_at']
    
    def get_position_id_preview(self, obj):
        """Preview what position ID will be generated"""
        if hasattr(obj, 'business_function') and obj.business_function:
            return VacantPosition.get_next_position_id_preview(obj.business_function.id)
        return None
    
    def create(self, validated_data):
        # position_id will be auto-generated in model save() method
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

class VacantPositionListSerializer(serializers.ModelSerializer):
    """ENHANCED: List serializer with employee-like fields and business function based ID"""
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    business_function_code = serializers.CharField(source='business_function.code', read_only=True)
    business_function_id = serializers.CharField(source='business_function.id', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    department_id = serializers.CharField(source='department.id', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    unit_id = serializers.CharField(source='unit.id', read_only=True)
    job_function_name = serializers.CharField(source='job_function.name', read_only=True)
    job_function_id = serializers.CharField(source='job_function.id', read_only=True)
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    position_group_id = serializers.IntegerField(source='position_group.id', read_only=True)
    position_group_level = serializers.IntegerField(source='position_group.hierarchy_level', read_only=True)
    reporting_to_name = serializers.CharField(source='reporting_to.full_name', read_only=True)
    reporting_to_id = serializers.CharField(source='reporting_to.id', read_only=True)
    reporting_to_hc_number = serializers.CharField(source='reporting_to.employee_id', read_only=True)
    filled_by_name = serializers.CharField(source='filled_by_employee.full_name', read_only=True)
    
    # ENHANCED: Employee-like fields for unified display (using position_id as employee_id)
    
    employee_id = serializers.CharField(source='position_id', read_only=True)  # position_id acts as employee_id
    job_title = serializers.CharField()
    status_name = serializers.CharField(source='vacancy_status.name', read_only=True)
    status_color = serializers.CharField(source='vacancy_status.color', read_only=True)
 
    
    # ENHANCED: Mark as vacancy for frontend identification
    is_vacancy = serializers.SerializerMethodField()

    
    class Meta:
        model = VacantPosition
        fields = [
            # Employee-like fields for unified display
            'id', 'employee_id',  'job_title', 'business_function_name', 'business_function_code','business_function_id',
            'department_name', 'department_id','unit_name','unit_id', 'job_function_name','job_function_id', 'position_group_name', 'position_group_level','position_group_id',
            'grading_level',  'status_name', 'status_color','reporting_to_id',
            'reporting_to_name', 'reporting_to_hc_number', 'is_visible_in_org_chart',
            'is_filled', 'filled_by_name', 'filled_date', 'include_in_headcount',
            'is_vacancy',  'created_at', 'updated_at',
            
            # Original vacancy fields
            'position_id',  'notes'
        ]
    def to_representation(self, instance):
        """Format text fields to title case"""
        data = super().to_representation(instance)
        
        # ✅ Title case tətbiq et - ad və soyad
        text_fields = [
             'department_name','unit_name',  'reporting_to_name','job_function_name',
            'job_title', 'business_function_name',
        ]
        
        for field in text_fields:
            if field in data and data[field]:
                # Strip whitespace və title case
                data[field] = str(data[field]).strip().title()
        
        return data
    def get_grading_display(self, obj):
        if obj.grading_level:
            parts = obj.grading_level.split('_')
            if len(parts) == 2:
                position_short, level = parts
                return f"{position_short}-{level}"
        return "No Grade"
    
    def get_is_vacancy(self, obj):
        return True

class VacantPositionDetailSerializer(serializers.ModelSerializer):
    """FIXED: Detail serializer with proper JSON serialization"""
    
    # Use proper serialization instead of including objects directly
    business_function_detail = BusinessFunctionSerializer(source='business_function', read_only=True)
    department_detail = DepartmentSerializer(source='department', read_only=True)
    unit_detail = UnitSerializer(source='unit', read_only=True)
    job_function_detail = JobFunctionSerializer(source='job_function', read_only=True)
    position_group_detail = PositionGroupSerializer(source='position_group', read_only=True)
    status_detail = EmployeeStatusSerializer(source='vacancy_status', read_only=True)
    
    # Management details
    reporting_to_detail = serializers.SerializerMethodField()
    filled_by_detail = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    # Simple field references instead of complex objects
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    business_function_code = serializers.CharField(source='business_function.code', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    job_function_name = serializers.CharField(source='job_function.name', read_only=True)
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    status_name = serializers.CharField(source='vacancy_status.name', read_only=True)
    status_color = serializers.CharField(source='vacancy_status.color', read_only=True)
    
    # Employee-like conversion - FIXED to avoid BusinessFunction object serialization
    as_employee_data = serializers.SerializerMethodField()
    

    next_position_id_would_be = serializers.SerializerMethodField()
    
    class Meta:
        model = VacantPosition
        fields = [
            # Basic info
            'id', 'position_id', 'job_title', 'grading_level', 'display_name',
            'is_filled', 'filled_date', 'include_in_headcount', 'is_visible_in_org_chart',
            'notes', 'created_at', 'updated_at',
            
            # Simple name fields (JSON serializable)
            'business_function_name', 'business_function_code', 'department_name', 
            'unit_name', 'job_function_name', 'position_group_name',
            'status_name', 'status_color',
            
            # Detailed objects (properly serialized)
            'business_function_detail', 'department_detail', 'unit_detail',
            'job_function_detail', 'position_group_detail', 'status_detail',
            
            # Management
            'reporting_to_detail', 'filled_by_detail', 'created_by_name',
            
            # Complex fields
            'as_employee_data',  'next_position_id_would_be'
        ]
    
    def get_reporting_to_detail(self, obj):
        if obj.reporting_to:
            return {
                'id': obj.reporting_to.id,
                'employee_id': obj.reporting_to.employee_id,
                'name': obj.reporting_to.full_name,
                'job_title': obj.reporting_to.job_title,
                'email': obj.reporting_to.user.email if obj.reporting_to.user else None
            }
        return None
    
    def get_filled_by_detail(self, obj):
        if obj.filled_by_employee:
            return {
                'id': obj.filled_by_employee.id,
                'employee_id': obj.filled_by_employee.employee_id,
                'name': obj.filled_by_employee.full_name,
                'job_title': obj.filled_by_employee.job_title,
                'email': obj.filled_by_employee.user.email if obj.filled_by_employee.user else None
            }
        return None
    
    def get_as_employee_data(self, obj):
        """Get vacancy data in employee-like format - FIXED"""
        return {
            'id': f"vacancy_{obj.id}",
            'employee_id': obj.position_id,
            'name': obj.display_name,
            'full_name': None,
            'email': None,
            'job_title': obj.job_title,
            
            # Use simple string references instead of objects
            'business_function_name': obj.business_function.name if obj.business_function else 'N/A',
            'business_function_code': obj.business_function.code if obj.business_function else 'N/A',
            'department_name': obj.department.name if obj.department else 'N/A',
            'unit_name': obj.unit.name if obj.unit else None,
            'job_function_name': obj.job_function.name if obj.job_function else 'N/A',
            'position_group_name': obj.position_group.get_name_display() if obj.position_group else 'N/A',
            'grading_level': obj.grading_level,
            
            'status_name': obj.vacancy_status.name if obj.vacancy_status else 'VACANT',
            'status_color': obj.vacancy_status.color if obj.vacancy_status else '#F97316',
            'line_manager_name': obj.reporting_to.full_name if obj.reporting_to else None,
            'line_manager_hc_number': obj.reporting_to.employee_id if obj.reporting_to else None,
            'is_visible_in_org_chart': obj.is_visible_in_org_chart,
            'is_vacancy': True,
            'created_at': obj.created_at,
            'notes': obj.notes,
            'filled_by': obj.filled_by_employee.full_name if obj.filled_by_employee else None,
            'vacancy_details': {
                'internal_id': obj.id,
                'position_id': obj.position_id,
                'include_in_headcount': obj.include_in_headcount,
                'is_filled': obj.is_filled,
                'filled_date': obj.filled_date,
                'business_function_based_id': True
            }
        }
    
    
    def get_next_position_id_would_be(self, obj):
        """Show what the next position ID would be for this business function"""
        if obj.business_function:
            return VacantPosition.get_next_position_id_preview(obj.business_function.id)
        return None

class VacancyToEmployeeConversionSerializer(serializers.Serializer):
    """Serializer for converting vacancy to employee"""
    
    # Required employee data
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)  
    email = serializers.EmailField()
    start_date = serializers.DateField()
    contract_duration = serializers.CharField(max_length=50, default='PERMANENT')
    
    # Personal data - ALL OPTIONAL
    father_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=Employee.GENDER_CHOICES, required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    emergency_contact = serializers.CharField(required=False, allow_blank=True)
    
    # Employment details - OPTIONAL
    end_date = serializers.DateField(required=False, allow_null=True)
    contract_start_date = serializers.DateField(required=False, allow_null=True)
    
    # File uploads - OPTIONAL
    document = serializers.FileField(required=False)
    profile_photo = serializers.ImageField(required=False)
    document_type = serializers.ChoiceField(
        choices=EmployeeDocument.DOCUMENT_TYPES, 
        required=False, 
        default='OTHER'
    )
    document_name = serializers.CharField(max_length=255, required=False)
    
    # Additional - OPTIONAL
    tag_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value
    
    def validate_contract_duration(self, value):
        """Validate that contract duration exists in configurations"""
        try:
            ContractTypeConfig.objects.get(contract_type=value, is_active=True)
        except ContractTypeConfig.DoesNotExist:
            available_choices = list(ContractTypeConfig.objects.filter(is_active=True).values_list('contract_type', flat=True))
           
            
            raise serializers.ValidationError(
                f"Invalid contract duration '{value}'. Available choices: {', '.join(available_choices)}"
            )
        return value
    
    def create(self, validated_data):
        """Convert vacancy to employee"""
        vacancy = self.context['vacancy']
        
        tag_ids = validated_data.pop('tag_ids', [])
        document = validated_data.pop('document', None)
        profile_photo = validated_data.pop('profile_photo', None)
        document_type = validated_data.pop('document_type', 'OTHER')
        document_name = validated_data.pop('document_name', '')
        
        # ✅ CRITICAL FIX: Extract first_name and last_name
        first_name = validated_data.get('first_name')
        last_name = validated_data.get('last_name')
        email = validated_data.get('email')
        
        with transaction.atomic():
            # ✅ FIXED: Create user WITHOUT set_unusable_password
            # This way, user can login with Microsoft later
            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=first_name,  # ✅ CRITICAL
                last_name=last_name     # ✅ CRITICAL
            )
            user.set_unusable_password()  # Still no password auth
            user.save()
            
            # ✅ CRITICAL: Pass first_name, last_name directly to Employee
            employee = Employee.objects.create(
                user=user,
                
                # ✅ CRITICAL: Set employee's own first_name/last_name fields
                first_name=first_name,
                last_name=last_name,
                email=email,
                
                # Personal information
                date_of_birth=validated_data.get('date_of_birth'),
                gender=validated_data.get('gender'),
                father_name=validated_data.get('father_name', ''),
                address=validated_data.get('address', ''),
                phone=validated_data.get('phone', ''),
                emergency_contact=validated_data.get('emergency_contact', ''),
                
                # Copy organizational structure from vacancy
                business_function=vacancy.business_function,
                department=vacancy.department,
                unit=vacancy.unit,
                job_function=vacancy.job_function,
                job_title=vacancy.job_title,
                position_group=vacancy.position_group,
                grading_level=vacancy.grading_level,
                
                # Employment details
                start_date=validated_data['start_date'],
                end_date=validated_data.get('end_date'),
                contract_duration=validated_data['contract_duration'],
                contract_start_date=validated_data.get('contract_start_date') or validated_data['start_date'],
                
                # Management
                line_manager=vacancy.reporting_to,
                
                # Configuration
                is_visible_in_org_chart=vacancy.is_visible_in_org_chart,
                original_vacancy=vacancy,
                created_by=self.context['request'].user
            )
            
            # Handle profile photo
            if profile_photo:
                employee.profile_image = profile_photo
                employee.save()
            
            # Add tags
            if tag_ids:
                valid_tags = EmployeeTag.objects.filter(id__in=tag_ids, is_active=True)
                employee.tags.set(valid_tags)
            
            # Handle document upload
            if document:
                doc_name = document_name or document.name
                EmployeeDocument.objects.create(
                    employee=employee,
                    name=doc_name,
                    document_type=document_type,
                    document_file=document,
                    uploaded_by=self.context['request'].user,
                    document_status='ACTIVE',
                    version=1,
                    is_current_version=True
                )
            
            # Mark vacancy as filled
            vacancy.mark_as_filled(employee)
            
            # Log activity
            EmployeeActivity.objects.create(
                employee=employee,
                activity_type='CREATED',
                description=f"Employee {employee.full_name} created from vacancy {vacancy.position_id}",
                performed_by=self.context['request'].user,
                metadata={
                    'converted_from_vacancy': True,
                    'vacancy_id': vacancy.id,
                    'vacancy_position_id': vacancy.position_id,
                    'has_user_account': True,
                    'first_name': first_name,  # ✅ Log for debugging
                    'last_name': last_name
                }
            )
            
            return employee
class EmployeeDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)
    file_size_display = serializers.CharField(source='get_file_size_display', read_only=True)
    is_image = serializers.BooleanField(read_only=True)
    is_pdf = serializers.BooleanField(read_only=True)
    file_url = serializers.SerializerMethodField()
    version_info = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeDocument
        fields = [
            'id', 'name', 'document_type', 'document_status', 'document_file', 'file_url',
            'version', 'is_current_version', 'version_info',
            'file_size', 'file_size_display', 'mime_type', 'original_filename',
            'description', 'expiry_date', 'is_confidential', 'is_required',
            'uploaded_at', 'uploaded_by_name', 'download_count', 'last_accessed',
            'is_image', 'is_pdf', 'is_deleted'
        ]
        read_only_fields = [
            'id', 'version', 'file_size', 'mime_type', 'original_filename', 
            'uploaded_at', 'download_count', 'last_accessed', 'is_current_version'
        ]
    
    def get_file_url(self, obj):
        if obj.document_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.document_file.url)
        return None
    
    def get_version_info(self, obj):
        """Get version history information"""
        version_history = obj.get_version_history()
        return {
            'current_version': obj.version,
            'is_current': obj.is_current_version,
            'total_versions': version_history.count(),
            'has_previous': obj.get_previous_version() is not None,
            'has_next': obj.get_next_version() is not None
        }

class ProfileImageUploadSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    profile_image = serializers.ImageField()
    
    def validate_employee_id(self, value):
        try:
            Employee.objects.get(id=value)
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Employee not found.")
        return value
    
    def validate_profile_image(self, value):
        # Image size validation (10MB max)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Image size cannot exceed 10MB.")
        
        # Image format validation
        allowed_formats = ['JPEG', 'PNG', 'GIF', 'BMP']
        
        try:
            from PIL import Image
            img = Image.open(value)
            if img.format not in allowed_formats:
                raise serializers.ValidationError(f"Image format {img.format} is not allowed.")
        except Exception as e:
            raise serializers.ValidationError("Invalid image file.")
        
        return value
    
    def save(self):
        employee_id = self.validated_data['employee_id']
        profile_image = self.validated_data['profile_image']
        
        employee = Employee.objects.get(id=employee_id)
        
        # Delete old profile image if exists
        if employee.profile_image:
            try:
                # Check if it's a FieldFile with a path
                if hasattr(employee.profile_image, 'path'):
                    old_image_path = employee.profile_image.path
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
            except Exception as e:
                # Log error but don't fail
                logger.warning(f"Could not delete old profile image: {e}")
        
        # Save the new profile image
        employee.profile_image = profile_image
        employee.save()
        
        # Log activity
        EmployeeActivity.objects.create(
            employee=employee,
            activity_type='PROFILE_UPDATED',
            description="Profile image updated",
            performed_by=self.context['request'].user,
            metadata={'action': 'profile_image_upload'}
        )
        
        return employee

class ProfileImageDeleteSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    
    def validate_employee_id(self, value):
        try:
            employee = Employee.objects.get(id=value)
            if not employee.profile_image:
                raise serializers.ValidationError("Employee has no profile image to delete.")
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Employee not found.")
        return value
    
    def save(self):
        employee_id = self.validated_data['employee_id']
        employee = Employee.objects.get(id=employee_id)
        
        # Delete image file safely
        if employee.profile_image:
            try:
                if hasattr(employee.profile_image, 'path'):
                    old_image_path = employee.profile_image.path
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
            except Exception as e:
                logger.warning(f"Could not delete profile image file: {e}")
        
        # Clear the field
        employee.profile_image = None
        employee.save()
        
        # Log activity
        EmployeeActivity.objects.create(
            employee=employee,
            activity_type='PROFILE_UPDATED',
            description="Profile image deleted",
            performed_by=self.context['request'].user,
            metadata={'action': 'profile_image_delete'}
        )
        
        return employee

class EmployeeActivitySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source='performed_by.username', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    
    class Meta:
        model = EmployeeActivity
        fields = [
            'id', 'employee', 'employee_name', 'activity_type', 'description',
            'performed_by', 'performed_by_name', 'metadata', 'created_at'
        ]

class EmployeeListSerializer(serializers.ModelSerializer):
    
    name = serializers.CharField(source='get_display_name', read_only=True)
    email = serializers.CharField(source='get_contact_email', read_only=True)
    
    # System access information
    has_system_access = serializers.BooleanField(read_only=True)
    can_login_with_microsoft = serializers.BooleanField(read_only=True)
  

    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    business_function_code = serializers.CharField(source='business_function.code', read_only=True)
    business_function_id = serializers.CharField(source='business_function.id', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    department_id = serializers.CharField(source='department.id', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    unit_id = serializers.CharField(source='unit.id', read_only=True)
    job_function_name = serializers.CharField(source='job_function.name', read_only=True)
    job_function_id = serializers.CharField(source='job_function.id', read_only=True)
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    position_group_level = serializers.IntegerField(source='position_group.hierarchy_level', read_only=True)
    position_group_id = serializers.IntegerField(source='position_group.id', read_only=True)
    line_manager_name = serializers.CharField(source='line_manager.full_name', read_only=True)
    line_manager_hc_number = serializers.CharField(source='line_manager.employee_id', read_only=True)
    line_manager_email = serializers.CharField(source='line_manager.user.email', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    tag_names = serializers.SerializerMethodField()
    years_of_service = serializers.ReadOnlyField()
    current_status_display = serializers.ReadOnlyField()
    contract_duration_display = serializers.CharField(source='get_contract_duration_display', read_only=True)
   
    
    direct_reports_count = serializers.SerializerMethodField()
    status_needs_update = serializers.SerializerMethodField()
    profile_image_url = serializers.SerializerMethodField()
    is_vacancy = serializers.SerializerMethodField()
    
    def get_is_vacancy(self, obj):
        return False  # This is for actual employees
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'name', 'email', 'first_name', 'last_name', 'father_name', 
            'date_of_birth', 'gender', 'phone',
            'has_system_access', 'can_login_with_microsoft',  # NEW fields
            'business_function_name', 'business_function_code', 'business_function_id', 
            'department_name', 'unit_name', 'job_function_name', 'job_title', 
            'position_group_name', 'position_group_level', 'department_id',
            'grading_level', 'start_date', 'end_date', 'unit_id', 'position_group_id',
            'contract_duration', 'contract_duration_display', 'contract_start_date', 
            'contract_end_date', 'contract_extensions', 'last_extension_date', 
            'job_function_id', 'line_manager_name', 'line_manager_hc_number', 
            'status_name', 'status_color', 'tag_names', 'years_of_service', 
            'current_status_display', 'is_visible_in_org_chart',
            'direct_reports_count', 'status_needs_update', 'created_at', 
            'updated_at', 'profile_image_url', 'is_deleted', 'is_vacancy','line_manager_email'
        ]
    
    def to_representation(self, instance):
        """Format text fields to title case"""
        data = super().to_representation(instance)
        
        # ✅ Title case tətbiq et - ad və soyad
        text_fields = [
            'name',  # Full name
            'first_name',
            'last_name',
            'father_name',
            'business_function_name',
            'department_name',
            'unit_name',
            'job_function_name',
            'job_title',
            'position_group_name',
            'line_manager_name'
        ]
        
        for field in text_fields:
            if field in data and data[field]:
                # Strip whitespace və title case
                data[field] = str(data[field]).strip().title()
        
        return data
    
    def get_profile_image_url(self, obj):
        """Get profile image URL safely"""
        if obj.profile_image:
            try:
                if hasattr(obj.profile_image, 'url'):
                    request = self.context.get('request')
                    if request:
                        return request.build_absolute_uri(obj.profile_image.url)
                    return obj.profile_image.url
            except Exception as e:
                # Log error but don't fail serialization
                logger.warning(f"Could not get profile image URL for employee {obj.employee_id}: {e}")
        return None
    
    def get_tag_names(self, obj):
        return [
            {
                'id': tag.id,
                'name': tag.name,
                'color': tag.color,
                
            }
            for tag in obj.tags.filter(is_active=True)
        ]
    
    def get_direct_reports_count(self, obj):
        return obj.get_direct_reports_count()
    
    def get_status_needs_update(self, obj):
        """Check if employee status needs updating based on contract"""
        try:
            preview = obj.get_status_preview()
            return preview['needs_update']
        except:
            return False

class EmployeeDetailSerializer(serializers.ModelSerializer):
    """UPDATED: Job Description integration əlavə olundu"""
     
    name = serializers.CharField(source='full_name', read_only=True)
    email = serializers.CharField(source='get_contact_email', read_only=True)
    first_name = serializers.CharField(source='get_display_first_name', read_only=True)
    last_name = serializers.CharField(source='get_display_last_name', read_only=True)
    
    # Related objects
    business_function_detail = BusinessFunctionSerializer(source='business_function', read_only=True)
    department_detail = DepartmentSerializer(source='department', read_only=True)
    unit_detail = UnitSerializer(source='unit', read_only=True)
    job_function_detail = JobFunctionSerializer(source='job_function', read_only=True)
    position_group_detail = PositionGroupSerializer(source='position_group', read_only=True)
    status_detail = EmployeeStatusSerializer(source='status', read_only=True)
    line_manager_detail = serializers.SerializerMethodField()
    
    # Enhanced fields
    documents = EmployeeDocumentSerializer(many=True, read_only=True)
    activities = EmployeeActivitySerializer(many=True, read_only=True)
    tag_details = EmployeeTagSerializer(source='tags', many=True, read_only=True)
    direct_reports = serializers.SerializerMethodField()
    
    # Calculated fields
    years_of_service = serializers.ReadOnlyField()
    contract_duration_display = serializers.CharField(source='get_contract_duration_display', read_only=True)
    
    # Contract status analysis
    status_preview = serializers.SerializerMethodField()
    
    # Vacancy information
    original_vacancy_detail = VacantPositionListSerializer(source='original_vacancy', read_only=True)
    
    profile_image_url = serializers.SerializerMethodField()
    documents_count = serializers.SerializerMethodField()
    
    # JOB DESCRIPTION INTEGRATION - YENİ SAHƏLƏR
    job_description_assignments = serializers.SerializerMethodField()
    team_job_description_assignments = serializers.SerializerMethodField()
    job_descriptions_count = serializers.SerializerMethodField()
    pending_job_description_approvals = serializers.SerializerMethodField()
    job_description_summary = serializers.SerializerMethodField()
    
   
    team_pending_approvals = serializers.SerializerMethodField()
    team_jd_summary = serializers.SerializerMethodField()
    
    assigned_assets = serializers.SerializerMethodField()
    pending_asset_approvals = serializers.SerializerMethodField()
    assets_summary = serializers.SerializerMethodField()
     # Performance Management Integration
    performance_records = serializers.SerializerMethodField()
    performance_summary = serializers.SerializerMethodField()
    current_performance = serializers.SerializerMethodField()
    performance_history = serializers.SerializerMethodField()
    pending_performance_actions = serializers.SerializerMethodField()
    team_performance_overview = serializers.SerializerMethodField()
    
    
    pending_transfer_approvals = serializers.SerializerMethodField()
    transfers_summary = serializers.SerializerMethodField()
    class Meta:
        model = Employee
        fields = '__all__'
    def to_representation(self, instance):
        """Format text fields to title case"""
        data = super().to_representation(instance)
        
        # ✅ Title case tətbiq et
        text_fields = [
            'name',
            'first_name', 
            'last_name',
            'father_name',
            'job_title'
        ]
        
        for field in text_fields:
            if field in data and data[field]:
                data[field] = str(data[field]).strip().title()
        
        return data
    def _get_period_display(self, period):
        """Get human-readable period name"""
        periods = {
            'GOAL_SETTING': 'Goal Setting',
            'MID_YEAR_REVIEW': 'Mid-Year Review',
            'END_YEAR_REVIEW': 'End-Year Review',
            'COMPLETED': 'Completed',
            'CLOSED': 'Closed'
        }
        return periods.get(period, period)
    
    def _calculate_available_actions(self, performance, current_user, employee_obj):
        """
        ✅ FIXED: Calculate which actions are available for THIS USER viewing THIS PERFORMANCE
        
        CRITICAL RULES:
        - If viewing OWN performance → show ONLY employee actions
        - If viewing TEAM MEMBER's performance → show ONLY manager actions
        - Admin can see both, but context-aware
        """
        if not current_user:
            return []
        
        try:
            actions = []
            
            from .performance_permissions import is_admin_user
            from .models import Employee
            
            is_admin = is_admin_user(current_user)
            is_own = False
            is_manager = False
            current_emp = None
            
            try:
                current_emp = Employee.objects.get(user=current_user, is_deleted=False)
                is_own = (performance.employee == current_emp)
                is_manager = (performance.employee.line_manager == current_emp)
            except Employee.DoesNotExist:
                pass
            
            current_period = performance.performance_year.get_current_period()
            
            # ==================== EMPLOYEE ACTIONS (viewing OWN performance) ====================
            if is_own or is_admin:
                # GOAL SETTING - Employee Approval
                if current_period == 'GOAL_SETTING':
                    # ✅ FIX: Only show if manager submitted AND employee NOT approved yet
                    if performance.objectives_employee_submitted and not performance.objectives_employee_approved:
                        actions.append({
                            'type': 'approve_objectives_employee',
                            'label': 'Approve Objectives',
                            'description': 'Review and approve your objectives',
                            'icon': 'CheckSquare',
                            'color': 'green',
                            'priority': 'high',
                            'requires_comment': False,
                        })
                    
                    # Request Clarification (only if submitted)
                    if performance.objectives_employee_submitted and performance.approval_status != 'NEED_CLARIFICATION':
                        actions.append({
                            'type': 'request_clarification',
                            'label': 'Request Clarification',
                            'description': 'Request changes to objectives',
                            'icon': 'MessageSquare',
                            'color': 'orange',
                            'priority': 'medium',
                            'requires_comment': True,
                        })
                
                # MID-YEAR - Employee Self-Review
                if current_period == 'MID_YEAR_REVIEW':
                    if not performance.mid_year_employee_submitted:
                        actions.append({
                            'type': 'submit_mid_year_employee',
                            'label': 'Submit Mid-Year Review',
                            'description': 'Submit your mid-year self-assessment',
                            'icon': 'Send',
                            'color': 'blue',
                            'priority': 'high',
                            'requires_comment': True,
                        })
                
                # END-YEAR - Employee Self-Review
                if current_period == 'END_YEAR_REVIEW':
                    if not performance.end_year_employee_submitted:
                        actions.append({
                            'type': 'submit_end_year_employee',
                            'label': 'Submit End-Year Review',
                            'description': 'Submit your end-year self-assessment',
                            'icon': 'Send',
                            'color': 'purple',
                            'priority': 'critical',
                            'requires_comment': True,
                        })
                
                # FINAL APPROVAL - Employee
                if performance.end_year_completed and not performance.final_employee_approved:
                    actions.append({
                        'type': 'approve_final_employee',
                        'label': 'Approve Final Results',
                        'description': 'Approve your final performance rating',
                        'icon': 'CheckSquare',
                        'color': 'green',
                        'priority': 'critical',
                        'requires_comment': False,
                    })
            
            # ==================== MANAGER ACTIONS (viewing TEAM MEMBER's performance) ====================
            elif is_manager or (is_admin and not is_own):
                # ✅ CRITICAL: Only show manager actions when viewing SOMEONE ELSE's performance
                
                # GOAL SETTING - Manager Final Approval
                if current_period == 'GOAL_SETTING':
                    pass 
                
                # MID-YEAR - Manager Complete Review
                if current_period == 'MID_YEAR_REVIEW':
                    if performance.mid_year_employee_submitted and not performance.mid_year_completed:
                        actions.append({
                            'type': 'submit_mid_year_manager',
                            'label': 'Complete Mid-Year',
                            'description': 'Complete mid-year assessment',
                            'icon': 'Send',
                            'color': 'blue',
                            'priority': 'high',
                            'requires_comment': True,
                        })
                
                # END-YEAR - Manager Complete
                if current_period == 'END_YEAR_REVIEW':
                    if not performance.end_year_completed:
                        actions.append({
                            'type': 'complete_end_year',
                            'label': 'Complete End-Year',
                            'description': 'Finalize all ratings and scores',
                            'icon': 'CheckCircle',
                            'color': 'purple',
                            'priority': 'critical',
                            'requires_comment': True,
                        })
                
                # FINAL APPROVAL - Manager Publish
                if performance.end_year_completed:
                    if performance.final_employee_approved and not performance.final_manager_approved:
                        actions.append({
                            'type': 'approve_final_manager',
                            'label': 'Publish Performance',
                            'description': 'Final approval and publish results',
                            'icon': 'CheckSquare',
                            'color': 'green',
                            'priority': 'critical',
                            'requires_comment': False,
                        })
            
            # ==================== ADMIN OVERRIDE (if needed) ====================
            # Admin can perform both employee and manager actions
            # But when viewing OWN performance, show ONLY employee actions
            # When viewing TEAM performance, show ONLY manager actions
            
            return actions
            
        except Exception as e:
            logger.error(f"Error calculating actions: {e}")
            return []
    
    def get_pending_transfer_approvals(self, obj):
        """✅ Get pending transfers that need employee approval"""
        try:
            from .asset_models import AssetTransferRequest
            
            pending_transfers = AssetTransferRequest.objects.filter(
                to_employee=obj,
                status='PENDING'
            ).select_related(
                'asset',
                'from_employee',
                'requested_by',
                'offboarding'
            ).order_by('-requested_at')
            
            transfers_data = []
            for transfer in pending_transfers:
                transfers_data.append({
                    'id': transfer.id,
                    'asset': {
                        'id': str(transfer.asset.id),
                        'asset_number': transfer.asset.asset_number,
                        'asset_name': transfer.asset.asset_name,
                        'serial_number': transfer.asset.serial_number,
                        'category': transfer.asset.category.name if transfer.asset.category else None,
                        'status': transfer.asset.status,
                        'status_display': transfer.asset.get_status_display()
                    },
                    'from_employee': {
                        'id': transfer.from_employee.id,
                        'employee_id': transfer.from_employee.employee_id,
                        'name': transfer.from_employee.full_name,
                        'job_title': transfer.from_employee.job_title
                    },
                    'requested_by': {
                        'id': transfer.requested_by.id if transfer.requested_by else None,
                        'name': transfer.requested_by.get_full_name() if transfer.requested_by else None
                    },
                    'transfer_notes': transfer.transfer_notes,
                    'requested_at': transfer.requested_at,
                    'status': transfer.status,
                    'status_display': transfer.get_status_display(),
                    'urgency': 'high' if (timezone.now() - transfer.requested_at).days > 3 else 'normal',
                    'days_pending': (timezone.now() - transfer.requested_at).days
                })
            
            return transfers_data
            
        except Exception as e:
            logger.error(f"Error getting pending transfers for employee {obj.employee_id}: {e}")
            return []
    
    def get_transfers_summary(self, obj):
        """✅ Get transfer summary for employee"""
        try:
            from .asset_models import AssetTransferRequest
            
            # Transfers TO this employee
            incoming_transfers = AssetTransferRequest.objects.filter(to_employee=obj)
            
            # Transfers FROM this employee (offboarding scenario)
            outgoing_transfers = AssetTransferRequest.objects.filter(from_employee=obj)
            
            return {
                'incoming': {
                    'total': incoming_transfers.count(),
                    'pending': incoming_transfers.filter(status='PENDING').count(),
                    'approved': incoming_transfers.filter(status='APPROVED').count(),
                    'completed': incoming_transfers.filter(status='COMPLETED').count(),
                    'rejected': incoming_transfers.filter(status='REJECTED').count()
                },
                'outgoing': {
                    'total': outgoing_transfers.count(),
                    'pending': outgoing_transfers.filter(status='PENDING').count(),
                    'completed': outgoing_transfers.filter(status='COMPLETED').count()
                },
                'has_pending_approvals': incoming_transfers.filter(status='PENDING').exists(),
                'pending_count': incoming_transfers.filter(status='PENDING').count()
            }
            
        except Exception as e:
            logger.error(f"Error getting transfers summary for employee {obj.employee_id}: {e}")
            return {
                'incoming': {'total': 0, 'pending': 0, 'approved': 0, 'completed': 0, 'rejected': 0},
                'outgoing': {'total': 0, 'pending': 0, 'completed': 0},
                'has_pending_approvals': False,
                'pending_count': 0
            }
    
    def get_performance_records(self, obj):
        """Get all performance records with real-time data"""
        try:
            from .performance_models import EmployeePerformance
            
            performances = EmployeePerformance.objects.filter(
                employee=obj
            ).select_related(
                'performance_year',
                'created_by'
            ).prefetch_related(
                'objectives',
                'competency_ratings',
                'development_needs'
            ).order_by('-performance_year__year')
            
            if not performances.exists():
                return []
            
            request = self.context.get('request')
            current_user = request.user if request else None
            
            performance_list = []
            
            for perf in performances:
                actions = self._calculate_available_actions(perf, current_user, obj)
                
                perf_data = {
                    'id': str(perf.id),
                    'year': perf.performance_year.year,
                    'current_period': perf.performance_year.get_current_period(),
                    'current_period_display': self._get_period_display(perf.performance_year.get_current_period()),
                    
                    'approval_status': perf.approval_status,
                    'approval_status_display': perf.get_approval_status_display(),
                    
                    'workflow': {
                        'objectives': {
                            'employee_submitted': perf.objectives_employee_submitted,
                            'employee_submitted_date': perf.objectives_employee_submitted_date,
                            'employee_approved': perf.objectives_employee_approved,
                            'employee_approved_date': perf.objectives_employee_approved_date,
                            'manager_approved': perf.objectives_manager_approved,  # ✅ Auto-set when employee approves
                            'manager_approved_date': perf.objectives_manager_approved_date,
                            'is_complete': perf.objectives_employee_approved,  # ✅ Complete when employee approves
                            'description': 'Employee approval is final - no manager approval needed'  # ✅ NEW
                        },
                        'mid_year': {
                            'employee_submitted': perf.mid_year_employee_submitted,
                            'manager_submitted': perf.mid_year_manager_submitted,
                            'completed': perf.mid_year_completed,
                            'is_complete': perf.mid_year_completed,
                        },
                        'end_year': {
                            'employee_submitted': perf.end_year_employee_submitted,
                            'manager_submitted': perf.end_year_manager_submitted,
                            'completed': perf.end_year_completed,
                            'is_complete': perf.end_year_completed,
                        },
                        'final': {
                            'employee_approved': perf.final_employee_approved,
                            'employee_approval_date': perf.final_employee_approval_date,
                            'manager_approved': perf.final_manager_approved,
                            'manager_approval_date': perf.final_manager_approval_date,
                            'is_complete': perf.final_manager_approved,
                        }
                    },
                    
                    'objectives_count': perf.objectives.filter(is_cancelled=False).count(),
                    'competencies_count': perf.competency_ratings.count(),
                    'development_needs_count': perf.development_needs.count(),
                    
                    'scores': {
                        'objectives_score': float(perf.total_objectives_score) if perf.total_objectives_score else 0,
                        'objectives_percentage': float(perf.objectives_percentage) if perf.objectives_percentage else 0,
                        'competencies_required': perf.total_competencies_required_score,
                        'competencies_actual': perf.total_competencies_actual_score,
                        'competencies_percentage': float(perf.competencies_percentage) if perf.competencies_percentage else 0,
                        'competencies_letter_grade': perf.competencies_letter_grade or 'N/A',
                        'overall_percentage': float(perf.overall_weighted_percentage) if perf.overall_weighted_percentage else 0,
                        'final_rating': perf.final_rating or 'N/A',
                    },
                    
                    'group_competency_scores': perf.group_competency_scores or {},
                    
                    'available_actions': actions,
                    'has_actions': len(actions) > 0,
                    
                    'drafts': {
                        'objectives': perf.objectives_draft_saved_date is not None,
                        'competencies': perf.competencies_draft_saved_date is not None,
                        'mid_year_employee': perf.mid_year_employee_draft_saved is not None,
                        'mid_year_manager': perf.mid_year_manager_draft_saved is not None,
                        'end_year_employee': perf.end_year_employee_draft_saved is not None,
                        'end_year_manager': perf.end_year_manager_draft_saved is not None,
                        'development_needs': perf.development_needs_draft_saved is not None,
                    },
                    
                    'created_at': perf.created_at,
                    'updated_at': perf.updated_at,
                }
                
                performance_list.append(perf_data)
            
            return performance_list
            
        except Exception as e:
            logger.error(f"Error getting performance records: {e}")
            return []
    
    def get_performance_summary(self, obj):
        """Get performance summary statistics"""
        try:
            from .performance_models import EmployeePerformance
            from django.db.models import Avg
            
            performances = EmployeePerformance.objects.filter(employee=obj)
            
            if not performances.exists():
                return {
                    'total_records': 0,
                    'has_performance_data': False,
                    'message': 'No performance records found'
                }
            
            completed = performances.filter(
                final_employee_approved=True,
                final_manager_approved=True
            )
            
            avg_overall = completed.aggregate(Avg('overall_weighted_percentage'))['overall_weighted_percentage__avg']
            avg_objectives = completed.aggregate(Avg('objectives_percentage'))['objectives_percentage__avg']
            avg_competencies = completed.aggregate(Avg('competencies_percentage'))['competencies_percentage__avg']
            
            ratings = completed.values('final_rating').annotate(count=models.Count('id'))
            
            return {
                'total_records': performances.count(),
                'completed_records': completed.count(),
                'pending_records': performances.count() - completed.count(),
                'has_performance_data': True,
                
                'averages': {
                    'overall_percentage': round(avg_overall, 2) if avg_overall else 0,
                    'objectives_percentage': round(avg_objectives, 2) if avg_objectives else 0,
                    'competencies_percentage': round(avg_competencies, 2) if avg_competencies else 0,
                },
                
                'rating_distribution': {
                    rating['final_rating']: rating['count'] 
                    for rating in ratings if rating['final_rating']
                },
                
                'latest_rating': completed.first().final_rating if completed.exists() else None,
                'latest_score': float(completed.first().overall_weighted_percentage) if completed.exists() else None,
            }
            
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {
                'total_records': 0,
                'has_performance_data': False,
                'error': str(e)
            }
    
    def get_current_performance(self, obj):
        """Get current active performance with full details"""
        try:
            from .performance_models import EmployeePerformance, PerformanceYear
            
            active_year = PerformanceYear.objects.filter(is_active=True).first()
            
            if not active_year:
                return {
                    'has_current_performance': False,
                    'message': 'No active performance year',
                    'active_year': None,
                    'current_period': None,
                    'can_initialize': False,
                }
            
            current_perf = EmployeePerformance.objects.filter(
                employee=obj,
                performance_year=active_year
            ).select_related('performance_year').first()
            
            if not current_perf:
                return {
                    'has_current_performance': False,
                    'active_year': active_year.year,
                    'current_period': active_year.get_current_period(),
                    'current_period_display': self._get_period_display(active_year.get_current_period()),
                    'message': f'No performance record for {active_year.year}',
                    'can_initialize': True,
                }
            
            request = self.context.get('request')
            current_user = request.user if request else None
            
            actions = self._calculate_available_actions(current_perf, current_user, obj)
            
            return {
                'has_current_performance': True,
                'active_year': active_year.year,
                'current_period': active_year.get_current_period(),
                'current_period_display': self._get_period_display(active_year.get_current_period()),
                'can_initialize': False,
                
                'performance': {
                    'id': str(current_perf.id),
                    'approval_status': current_perf.approval_status,
                    'approval_status_display': current_perf.get_approval_status_display(),
                    
                    'workflow': {
                        'objectives_complete': current_perf.objectives_manager_approved,
                        'mid_year_complete': current_perf.mid_year_completed,
                        'end_year_complete': current_perf.end_year_completed,
                        'final_complete': current_perf.final_manager_approved,
                    },
                    
                    'counts': {
                        'objectives': current_perf.objectives.filter(is_cancelled=False).count(),
                        'competencies': current_perf.competency_ratings.count(),
                        'development_needs': current_perf.development_needs.count(),
                    },
                    
                    'scores': {
                        'objectives_percentage': float(current_perf.objectives_percentage) if current_perf.objectives_percentage else 0,
                        'competencies_percentage': float(current_perf.competencies_percentage) if current_perf.competencies_percentage else 0,
                        'overall_percentage': float(current_perf.overall_weighted_percentage) if current_perf.overall_weighted_percentage else 0,
                        'final_rating': current_perf.final_rating or 'N/A',
                    },
                    
                    'updated_at': current_perf.updated_at,
                },
                
                'available_actions': actions,
                'has_actions': len(actions) > 0,
            }
            
        except Exception as e:
            logger.error(f"Error getting current performance: {e}")
            return {
                'has_current_performance': False,
                'error': str(e)
            }
    
    def get_performance_history(self, obj):
        """Get performance history with trends"""
        try:
            from .performance_models import EmployeePerformance
            
            performances = EmployeePerformance.objects.filter(
                employee=obj,
                final_employee_approved=True,
                final_manager_approved=True
            ).select_related('performance_year').order_by('-performance_year__year')[:5]
            
            if not performances.exists():
                return {
                    'has_history': False,
                    'message': 'No completed performance records'
                }
            
            history = []
            for perf in performances:
                history.append({
                    'year': perf.performance_year.year,
                    'overall_percentage': float(perf.overall_weighted_percentage),
                    'objectives_percentage': float(perf.objectives_percentage),
                    'competencies_percentage': float(perf.competencies_percentage),
                    'competencies_letter_grade': perf.competencies_letter_grade,
                    'final_rating': perf.final_rating,
                    'objectives_count': perf.objectives.filter(is_cancelled=False).count(),
                    'competencies_count': perf.competency_ratings.count(),
                })
            
            if len(history) >= 2:
                latest = history[0]['overall_percentage']
                previous = history[1]['overall_percentage']
                trend = 'improving' if latest > previous else ('declining' if latest < previous else 'stable')
                trend_value = round(latest - previous, 2)
            else:
                trend = 'insufficient_data'
                trend_value = 0
            
            return {
                'has_history': True,
                'records_count': len(history),
                'history': history,
                'trend': trend,
                'trend_value': trend_value,
                'years_covered': [h['year'] for h in history]
            }
            
        except Exception as e:
            logger.error(f"Error getting performance history: {e}")
            return {
                'has_history': False,
                'error': str(e)
            }
    
    def get_pending_performance_actions(self, obj):
        """Get pending performance actions for employee"""
        try:
            from .performance_models import EmployeePerformance, PerformanceYear
            
            active_year = PerformanceYear.objects.filter(is_active=True).first()
            
            if not active_year:
                return {
                    'has_pending_actions': False,
                    'message': 'No active performance year'
                }
            
            current_perf = EmployeePerformance.objects.filter(
                employee=obj,
                performance_year=active_year
            ).first()
            
            if not current_perf:
                return {
                    'has_pending_actions': True,
                    'actions': [{
                        'type': 'INITIALIZE_PERFORMANCE',
                        'title': 'Initialize Performance Record',
                        'description': f'Create performance record for {active_year.year}',
                        'priority': 'high',
                        'deadline': active_year.goal_setting_employee_end
                    }]
                }
            
            actions = []
            current_period = active_year.get_current_period()
            
            if current_period == 'GOAL_SETTING' and not current_perf.objectives_employee_submitted:
                actions.append({
                    'type': 'SUBMIT_OBJECTIVES',
                    'title': 'Submit Objectives',
                    'description': 'Submit your objectives for approval',
                    'priority': 'high',
                    'deadline': active_year.goal_setting_employee_end,
                    'performance_id': str(current_perf.id)
                })
            
            if current_perf.objectives_employee_approved and not current_perf.objectives_manager_approved:
                if current_period == 'GOAL_SETTING':
                    actions.append({
                        'type': 'PENDING_MANAGER_APPROVAL',
                        'title': 'Waiting for Manager Approval',
                        'description': 'Your objectives are pending manager approval',
                        'priority': 'medium',
                        'deadline': active_year.goal_setting_manager_end,
                        'performance_id': str(current_perf.id)
                    })
            
            if current_period == 'MID_YEAR_REVIEW' and not current_perf.mid_year_employee_submitted:
                actions.append({
                    'type': 'SUBMIT_MID_YEAR',
                    'title': 'Submit Mid-Year Review',
                    'description': 'Complete your mid-year self-assessment',
                    'priority': 'high',
                    'deadline': active_year.mid_year_review_end,
                    'performance_id': str(current_perf.id)
                })
            
            if current_period == 'END_YEAR_REVIEW' and not current_perf.end_year_employee_submitted:
                actions.append({
                    'type': 'SUBMIT_END_YEAR',
                    'title': 'Submit End-Year Review',
                    'description': 'Complete your end-year self-assessment',
                    'priority': 'critical',
                    'deadline': active_year.end_year_review_end,
                    'performance_id': str(current_perf.id)
                })
            
            if current_perf.end_year_manager_submitted and not current_perf.final_employee_approved:
                actions.append({
                    'type': 'APPROVE_FINAL',
                    'title': 'Approve Final Performance',
                    'description': 'Review and approve your final performance rating',
                    'priority': 'critical',
                    'deadline': None,
                    'performance_id': str(current_perf.id)
                })
            
            if current_perf.approval_status == 'NEED_CLARIFICATION':
                actions.append({
                    'type': 'PROVIDE_CLARIFICATION',
                    'title': 'Clarification Needed',
                    'description': 'Your manager has requested clarification',
                    'priority': 'critical',
                    'deadline': None,
                    'performance_id': str(current_perf.id)
                })
            
            return {
                'has_pending_actions': len(actions) > 0,
                'actions_count': len(actions),
                'actions': actions,
                'current_period': current_period,
                'active_year': active_year.year
            }
            
        except Exception as e:
            logger.error(f"Error getting pending actions: {e}")
            return {
                'has_pending_actions': False,
                'error': str(e)
            }
    
    def get_team_performance_overview(self, obj):
        """Get team performance overview for managers"""
        try:
            from .performance_models import EmployeePerformance, PerformanceYear
            from .models import Employee
            
            direct_reports = Employee.objects.filter(
                line_manager=obj,
                is_deleted=False,
                status__affects_headcount=True
            )
            
            if not direct_reports.exists():
                return {
                    'is_manager': False,
                    'message': 'No direct reports'
                }
            
            active_year = PerformanceYear.objects.filter(is_active=True).first()
            
            if not active_year:
                return {
                    'is_manager': True,
                    'team_size': direct_reports.count(),
                    'message': 'No active performance year'
                }
            
            team_performances = EmployeePerformance.objects.filter(
                employee__in=direct_reports,
                performance_year=active_year
            ).select_related('employee', 'performance_year')
            
            initiated = team_performances.count()
            not_initiated = direct_reports.count() - initiated
            
            objectives_submitted = team_performances.filter(
                objectives_employee_submitted=True
            ).count()
            
            objectives_pending_manager = team_performances.filter(
                objectives_employee_approved=True,
                objectives_manager_approved=False
            ).count()
            
            mid_year_complete = team_performances.filter(
                mid_year_completed=True
            ).count()
            
            end_year_complete = team_performances.filter(
                end_year_completed=True
            ).count()
            
            need_clarification = team_performances.filter(
                approval_status='NEED_CLARIFICATION'
            ).count()
            
            fully_approved = team_performances.filter(
                final_manager_approved=True
            ).count()
            
            # Team members needing attention
            needs_attention = []
            current_period = active_year.get_current_period()
            
            for perf in team_performances:
                issues = []
                
                if current_period == 'GOAL_SETTING':
                    if not perf.objectives_employee_submitted:
                        issues.append('objectives_not_submitted')
                    elif perf.objectives_employee_approved and not perf.objectives_manager_approved:
                        issues.append('pending_manager_approval')
                
                if current_period == 'MID_YEAR_REVIEW':
                    if not perf.mid_year_employee_submitted:
                        issues.append('mid_year_pending')
                
                if current_period == 'END_YEAR_REVIEW':
                    if not perf.end_year_employee_submitted:
                        issues.append('end_year_pending')
                
                if perf.approval_status == 'NEED_CLARIFICATION':
                    issues.append('clarification_needed')
                
                if issues:
                    needs_attention.append({
                        'employee_id': perf.employee.employee_id,
                        'employee_name': perf.employee.full_name,
                        'performance_id': str(perf.id),
                        'issues': issues,
                        'issue_count': len(issues),
                    })
            
            return {
                'is_manager': True,
                'team_size': direct_reports.count(),
                'active_year': active_year.year,
                'current_period': current_period,
                'current_period_display': self._get_period_display(current_period),
                
                'stats': {
                    'performance_initiated': initiated,
                    'not_initiated': not_initiated,
                    'objectives_submitted': objectives_submitted,
                    'objectives_pending_manager': objectives_pending_manager,
                    'mid_year_complete': mid_year_complete,
                    'end_year_complete': end_year_complete,
                    'need_clarification': need_clarification,
                    'fully_approved': fully_approved,
                },
                
                'needs_attention': needs_attention,
                'needs_attention_count': len(needs_attention),
            }
            
        except Exception as e:
            logger.error(f"Error getting team performance overview: {e}")
            return {
                'is_manager': False,
                'error': str(e)
            }
    
    # serializers.py - EmployeeDetailSerializer UPDATE

    def get_assigned_assets(self, obj):
        """✅ UPDATED: Get all assets assigned to this employee with clarification info"""
        try:
            from .asset_models import Asset
            assets = Asset.objects.filter(
                assigned_to=obj
            ).select_related('category', 'batch').order_by('-created_at')
            
            assets_data = []
            for asset in assets:
                asset_info = {
                    'id': str(asset.id),
                    'asset_number': asset.asset_number,
                    'asset_name': asset.asset_name,
                    'category': asset.category.name if asset.category else None,
                    'serial_number': asset.serial_number,
                    'status': asset.status,
                    'status_display': asset.get_status_display(),
                    'batch_number': asset.batch.batch_number if asset.batch else None,
                    'purchase_date': asset.batch.purchase_date if asset.batch else None,
                    'created_at': asset.created_at,
                    
                    # ✅ Action permissions based on status
                    'can_accept': asset.can_be_approved(),  # Uses model method
                    'can_request_clarification': asset.can_request_clarification(),  # Uses model method
                    'can_be_cancelled': asset.status in ['ASSIGNED', 'NEED_CLARIFICATION'],
                    
                    # Assignment details
                    'assignment_date': None,
                    'days_assigned': 0,
                    'assigned_by': None,
                    
                    # ✅ Clarification information
                    'clarification_info': self._get_asset_clarification_info(asset)
                }
                
                # Get assignment details
                current_assignment = asset.assignments.filter(check_in_date__isnull=True).first()
                if current_assignment:
                    asset_info['assignment_date'] = current_assignment.check_out_date
                    asset_info['days_assigned'] = current_assignment.get_duration_days()
                    asset_info['assigned_by'] = (
                        current_assignment.assigned_by.get_full_name() 
                        if current_assignment.assigned_by else None
                    )
                    asset_info['condition_on_checkout'] = current_assignment.condition_on_checkout
                
                assets_data.append(asset_info)
            
            return assets_data
        except Exception as e:
            logger.error(f"Error getting assigned assets for employee {obj.employee_id}: {e}")
            return []
    
    def _get_asset_clarification_info(self, asset):
        """✅ UPDATED: Get clarification information for asset"""
        try:
            # Check if asset has clarification fields
            if hasattr(asset, 'clarification_requested_reason'):
                if asset.status == 'NEED_CLARIFICATION' or asset.clarification_requested_reason:
                    return {
                        'has_clarification': True,
                        'requested_reason': asset.clarification_requested_reason,
                        'requested_at': asset.clarification_requested_at.isoformat() if asset.clarification_requested_at else None,
                        'requested_by': (
                            asset.clarification_requested_by.get_full_name() 
                            if asset.clarification_requested_by else None
                        ),
                        'response': asset.clarification_response,
                        'provided_at': asset.clarification_provided_at.isoformat() if asset.clarification_provided_at else None,
                        'provided_by': (
                            asset.clarification_provided_by.get_full_name() 
                            if asset.clarification_provided_by else None
                        ),
                        'has_response': bool(asset.clarification_response),
                        'is_pending': asset.status == 'NEED_CLARIFICATION' and not asset.clarification_response,
                        'status': 'pending' if (asset.status == 'NEED_CLARIFICATION' and not asset.clarification_response) else 'resolved'
                    }
            
            return {'has_clarification': False}
            
        except Exception as e:
            logger.error(f"Error getting clarification info for asset {asset.id}: {e}")
            return {'has_clarification': False}
    
    def get_pending_asset_approvals(self, obj):
        """✅ UPDATED: Get assets pending employee approval"""
        try:
            from .asset_models import Asset
            pending_assets = Asset.objects.filter(
                assigned_to=obj,
                status='ASSIGNED'
            ).select_related('category', 'batch')
            
            return [
                {
                    'id': str(asset.id),
                    'asset_number': asset.asset_number,
                    'asset_name': asset.asset_name,
                    'category': asset.category.name if asset.category else None,
                    'serial_number': asset.serial_number,
                    'status': asset.status,
                    'status_display': asset.get_status_display(),
                    'batch_number': asset.batch.batch_number if asset.batch else None,
                    'assignment_date': (
                        asset.assignments.filter(check_in_date__isnull=True).first().check_out_date 
                        if asset.assignments.filter(check_in_date__isnull=True).exists() else None
                    ),
                    'assigned_by': (
                        asset.assignments.filter(check_in_date__isnull=True).first().assigned_by.get_full_name()
                        if asset.assignments.filter(check_in_date__isnull=True).exists() and 
                           asset.assignments.filter(check_in_date__isnull=True).first().assigned_by else None
                    ),
                    'urgency': 'high' if (timezone.now().date() - (
                        asset.assignments.filter(check_in_date__isnull=True).first().check_out_date 
                        if asset.assignments.filter(check_in_date__isnull=True).exists() else timezone.now().date()
                    )).days > 3 else 'normal'
                }
                for asset in pending_assets
            ]
        except Exception as e:
            logger.error(f"Error getting pending asset approvals for employee {obj.employee_id}: {e}")
            return []
    
    def get_assets_summary(self, obj):
        """✅ UPDATED: Get asset assignment summary for employee"""
        try:
            from .asset_models import Asset
            all_assets = Asset.objects.filter(assigned_to=obj)
            
            return {
                'total_assigned': all_assets.count(),
                'pending_approval': all_assets.filter(status='ASSIGNED').count(),
                'in_use': all_assets.filter(status='IN_USE').count(),
                'need_clarification': all_assets.filter(status='NEED_CLARIFICATION').count(),
                'in_repair': all_assets.filter(status='IN_REPAIR').count(),
                'has_pending_approvals': all_assets.filter(status='ASSIGNED').exists(),
                'has_clarification_requests': all_assets.filter(status='NEED_CLARIFICATION').exists(),
                'by_category': self._get_assets_by_category(all_assets)
            }
        except Exception as e:
            logger.error(f"Error getting assets summary for employee {obj.employee_id}: {e}")
            return {
                'total_assigned': 0,
                'pending_approval': 0,
                'in_use': 0,
                'need_clarification': 0,
                'in_repair': 0,
                'has_pending_approvals': False,
                'has_clarification_requests': False,
                'by_category': {}
            }
    
    def _get_assets_by_category(self, assets_queryset):
        """Get asset count by category"""
        try:
            from django.db.models import Count
            category_counts = assets_queryset.values(
                'category__name'
            ).annotate(
                count=Count('id')
            )
            
            return {
                item['category__name']: item['count'] 
                for item in category_counts 
                if item['category__name']
            }
        except:
            return {}
    def get_profile_image_url(self, obj):
        """Get profile image URL safely"""
        if obj.profile_image:
            try:
                if hasattr(obj.profile_image, 'url'):
                    request = self.context.get('request')
                    if request:
                        return request.build_absolute_uri(obj.profile_image.url)
                    return obj.profile_image.url
            except Exception as e:
                logger.warning(f"Could not get profile image URL for employee {obj.employee_id}: {e}")
        return None
    
    def get_documents_count(self, obj):
        return obj.documents.filter(is_deleted=False).count()
    
    def get_line_manager_detail(self, obj):
        if obj.line_manager:
            return {
                'id': obj.line_manager.id,
                'employee_id': obj.line_manager.employee_id,
    
                'name': obj.line_manager.full_name,
                'job_title': obj.line_manager.job_title,
                'email': obj.line_manager.user.email if obj.line_manager.user else None
            }
        return None
    
    def get_direct_reports(self, obj):
        reports = obj.direct_reports.filter(status__affects_headcount=True)[:5]  # Limit to 5
        return [
            {
                'id': emp.id,
                'employee_id': emp.employee_id,
                'name': emp.full_name,
                'job_title': emp.job_title
            }
            for emp in reports
        ]
    
    def get_status_preview(self, obj):
        """Get status preview for this employee"""
        try:
            return obj.get_status_preview()
        except:
            return None
    
    def get_job_description_assignments(self, obj):
        """Get all job description assignments for this employee"""
        try:
            from .job_description_models import JobDescriptionAssignment
            
            assignments = JobDescriptionAssignment.objects.filter(
                employee=obj,
                is_active=True
            ).select_related(
                'job_description__business_function',
                'job_description__department',
                'job_description__job_function',
                'reports_to'
            ).order_by('-created_at')[:10]
            
            # ✅ CRITICAL: Pass context to serializer
            serializer = EmployeeJobDescriptionSerializer(
                assignments,
                many=True,
                context={'request': self.context.get('request')}  # ✅ Context əlavə et
            )
            
            return serializer.data
        except Exception as e:
            logger.error(f"Error getting job description assignments for employee {obj.employee_id}: {e}")
            return []
    
    def get_team_job_description_assignments(self, obj):
        """Get job description assignments for direct reports (for managers)"""
        try:
            from .job_description_models import JobDescriptionAssignment
            
            if not self.context.get('request') or not self.context.get('request').user:
                return []
            
            # Get assignments where this employee is the reports_to manager
            team_assignments = JobDescriptionAssignment.objects.filter(
                reports_to=obj,
                is_active=True
            ).select_related(
                'job_description__business_function',
                'job_description__department',
                'job_description__job_function',
                'employee',
                'vacancy_position'
            ).order_by('-created_at')[:10]
            
            # ✅ CRITICAL: Pass context to serializer
            serializer = ManagerJobDescriptionSerializer(
                team_assignments,
                many=True,
                context={'request': self.context.get('request')}  # ✅ Context əlavə et
            )
            
            return serializer.data
        except Exception as e:
            logger.error(f"Error getting team JD assignments for manager {obj.employee_id}: {e}")
            return []
    def get_job_descriptions_count(self, obj):
        """Get total count of job description assignments"""
        try:
            from .job_description_models import JobDescriptionAssignment
            return JobDescriptionAssignment.objects.filter(
                employee=obj,
                is_active=True
            ).count()
        except:
            return 0
    
    def get_pending_job_description_approvals(self, obj):
        """Get assignments pending employee approval"""
        try:
            from .job_description_models import JobDescriptionAssignment
            
            request_user = self.context.get('request').user if self.context.get('request') else None
            if not request_user:
                return []
            
            pending_assignments = JobDescriptionAssignment.objects.filter(
                employee=obj,
                is_active=True,
                status='PENDING_EMPLOYEE'
            ).select_related(
                'job_description__business_function',
                'job_description__department',
                'reports_to'
            )
            
            serializer = EmployeeJobDescriptionSerializer(
                pending_assignments,
                many=True,
                context=self.context
            )
            
            return serializer.data
        except Exception as e:
            logger.error(f"Error getting pending JD approvals for employee {obj.employee_id}: {e}")
            return []
    
    def get_job_description_summary(self, obj):
        """Get summary of job description assignments"""
        try:
            from .job_description_models import JobDescriptionAssignment
            
            assignments = JobDescriptionAssignment.objects.filter(
                employee=obj,
                is_active=True
            )
            
            return {
                'total': assignments.count(),
                'approved': assignments.filter(status='APPROVED').count(),
                'pending_employee': assignments.filter(status='PENDING_EMPLOYEE').count(),
                'pending_line_manager': assignments.filter(status='PENDING_LINE_MANAGER').count(),
                'draft': assignments.filter(status='DRAFT').count(),
                'rejected': assignments.filter(status='REJECTED').count(),
                'has_pending': assignments.filter(
                    status__in=['PENDING_EMPLOYEE', 'PENDING_LINE_MANAGER']
                ).exists()
            }
        except Exception as e:
            logger.error(f"Error getting JD summary for employee {obj.employee_id}: {e}")
            return {
                'total': 0,
                'approved': 0,
                'pending_employee': 0,
                'pending_line_manager': 0,
                'draft': 0,
                'rejected': 0,
                'has_pending': False
            }
    
 
    def get_team_pending_approvals(self, obj):
        """Get assignments pending line manager approval"""
        try:
            from .job_description_models import JobDescriptionAssignment
            
            if not self.context.get('request') or not self.context.get('request').user:
                return []
            
            pending_assignments = JobDescriptionAssignment.objects.filter(
                reports_to=obj,
                is_active=True,
                status='PENDING_LINE_MANAGER'
            ).select_related(
                'job_description__business_function',
                'job_description__department',
                'employee',
                'vacancy_position'
            )
            
            serializer = ManagerJobDescriptionSerializer(
                pending_assignments,
                many=True,
                context=self.context
            )
            
            return serializer.data
        except Exception as e:
            logger.error(f"Error getting team pending JD approvals for manager {obj.employee_id}: {e}")
            return []
    
    def get_team_jd_summary(self, obj):
        """Get summary of team member job description assignments"""
        try:
            from .job_description_models import JobDescriptionAssignment
            
            team_assignments = JobDescriptionAssignment.objects.filter(
                reports_to=obj,
                is_active=True
            )
            
            return {
                'total': team_assignments.count(),
                'pending_line_manager': team_assignments.filter(status='PENDING_LINE_MANAGER').count(),
                'pending_employee': team_assignments.filter(status='PENDING_EMPLOYEE').count(),
                'approved': team_assignments.filter(status='APPROVED').count(),
                'draft': team_assignments.filter(status='DRAFT').count(),
                'team_members': team_assignments.values('employee').distinct().count(),
                'has_pending': team_assignments.filter(status='PENDING_LINE_MANAGER').exists()
            }
        except Exception as e:
            logger.error(f"Error getting team JD summary for manager {obj.employee_id}: {e}")
            return {
                'total': 0,
                'pending_line_manager': 0,
                'pending_employee': 0,
                'approved': 0,
                'draft': 0,
                'team_members': 0,
                'has_pending': False
            }


class EmployeeJobDescriptionSerializer(serializers.Serializer):
    """NEW: Serializer for job description assignments"""
    
    id = serializers.UUIDField(read_only=True)
    job_description_id = serializers.UUIDField(source='job_description.id', read_only=True)
    job_title = serializers.CharField(source='job_description.job_title', read_only=True)
    
    # Assignment status
    status = serializers.CharField(read_only=True)
    status_display = serializers.SerializerMethodField()
    
    # Assignment details
    is_vacancy = serializers.BooleanField(read_only=True)
    employee_name = serializers.SerializerMethodField()  # ✅ ƏLAVƏ ET
    reports_to_name = serializers.CharField(source='reports_to.full_name', read_only=True)
    
    # Approval workflow
    line_manager_approved_at = serializers.DateTimeField(read_only=True)
    employee_approved_at = serializers.DateTimeField(read_only=True)
    
    # Organizational info
    business_function = serializers.CharField(source='job_description.business_function.name', read_only=True)
    department = serializers.CharField(source='job_description.department.name', read_only=True)
    job_function = serializers.CharField(source='job_description.job_function.name', read_only=True)
    
    # Metadata
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    # ✅ ƏSAS DƏYİŞİKLİK: Unified can_approve field
    can_approve = serializers.SerializerMethodField()
    can_approve_as_manager = serializers.SerializerMethodField()  # Manager view üçün
    can_approve_as_employee = serializers.SerializerMethodField()  # Employee view üçün
    urgency = serializers.SerializerMethodField()
    days_pending = serializers.SerializerMethodField()
    
    def get_employee_name(self, obj):
        """Get employee or vacancy name"""
        if obj.employee:
            return obj.employee.full_name
        elif obj.is_vacancy and obj.vacancy_position:
            return f"VACANT - {obj.vacancy_position.position_id}"
        return "Unassigned"
    
    def get_status_display(self, obj):
        return obj.get_status_display_with_color()
    
    
    def get_can_approve(self, obj):
        """✅ Everyone can approve"""
        # Pending status-da olanlar approve edilə bilər
        return obj.status in ['PENDING_LINE_MANAGER', 'PENDING_EMPLOYEE']
    
    def get_can_approve_as_manager(self, obj):
        """✅ Everyone can approve as manager"""
        return obj.status == 'PENDING_LINE_MANAGER'
    
    def get_can_approve_as_employee(self, obj):
        """✅ Everyone can approve as employee"""
        return obj.status == 'PENDING_EMPLOYEE'
    
    def get_urgency(self, obj):
        from django.utils import timezone
        days = (timezone.now() - obj.created_at).days
        if days > 14:
            return 'critical'
        elif days > 7:
            return 'high'
        else:
            return 'normal'
    
    def get_days_pending(self, obj):
        from django.utils import timezone
        return (timezone.now() - obj.created_at).days


class ManagerJobDescriptionSerializer(serializers.Serializer):
    """NEW: Serializer for manager viewing team member assignments"""
    
    id = serializers.UUIDField(read_only=True)
    job_description_id = serializers.UUIDField(source='job_description.id', read_only=True)
    job_title = serializers.CharField(source='job_description.job_title', read_only=True)
    
    # Employee/Vacancy info
    employee_name = serializers.SerializerMethodField()
    employee_id = serializers.SerializerMethodField()
    is_vacancy = serializers.BooleanField(read_only=True)
    
    # Assignment status
    status = serializers.CharField(read_only=True)
    status_display = serializers.SerializerMethodField()
    
    # Organizational info
    business_function = serializers.CharField(source='job_description.business_function.name', read_only=True)
    department = serializers.CharField(source='job_description.department.name', read_only=True)
    job_function = serializers.CharField(source='job_description.job_function.name', read_only=True)
    
    # Metadata
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    # ✅ ƏSAS: Manager action permissions
    can_approve = serializers.SerializerMethodField()
    can_approve_as_manager = serializers.SerializerMethodField()
    urgency_level = serializers.SerializerMethodField()
    days_since_created = serializers.SerializerMethodField()
    
    def get_employee_name(self, obj):
        return obj.get_display_name()
    
    def get_employee_id(self, obj):
        if obj.employee:
            return obj.employee.employee_id
        elif obj.vacancy_position:
            return obj.vacancy_position.position_id
        return None
    
    def get_status_display(self, obj):
        return obj.get_status_display_with_color()
    
    def get_can_approve(self, obj):
        """✅ Everyone can approve"""
        return obj.status in ['PENDING_LINE_MANAGER', 'PENDING_EMPLOYEE']
    
    def get_can_approve_as_manager(self, obj):
        """✅ Everyone can approve as manager"""
        return obj.status == 'PENDING_LINE_MANAGER'
    
    def get_urgency_level(self, obj):
        from django.utils import timezone
        days = (timezone.now() - obj.created_at).days
        if days > 14:
            return 'critical'
        elif days > 7:
            return 'high'
        else:
            return 'normal'
    
    def get_days_since_created(self, obj):
        from django.utils import timezone
        return (timezone.now() - obj.created_at).days
class BulkSoftDeleteSerializer(serializers.Serializer):
    """Simple serializer for bulk soft delete operations"""
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of employee IDs to soft delete"
    )
    reason = serializers.CharField(
        max_length=500,
        required=False,
        default="Bulk restructuring",
        help_text="Reason for bulk deletion"
    )
    
    def validate_employee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one employee ID is required.")
        
        employees = Employee.objects.filter(id__in=value, is_deleted=False)
        if employees.count() != len(value):
            raise serializers.ValidationError("Some employee IDs were not found or already deleted.")
        
        return value

class BulkHardDeleteSerializer(serializers.Serializer):
    """Simple serializer for bulk hard delete operations"""
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of employee IDs to hard delete"
    )
    confirm_hard_delete = serializers.BooleanField(
        help_text="Confirmation flag (must be true)"
    )
    notes = serializers.CharField(
        max_length=1000,
        required=False,
        help_text="Additional notes about deletion"
    )
    
    def validate_employee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one employee ID is required.")
        
        employees = Employee.objects.filter(id__in=value)
        if employees.count() != len(value):
            raise serializers.ValidationError("Some employee IDs were not found.")
        
        return value
    
    def validate_confirm_hard_delete(self, value):
        if not value:
            raise serializers.ValidationError("confirm_hard_delete must be true for hard deletion.")
        return value

class HardDeleteSerializer(serializers.Serializer):
    """Simple serializer for single employee hard delete"""
    employee_id = serializers.IntegerField(help_text="Employee ID to hard delete")
    confirm_hard_delete = serializers.BooleanField(help_text="Confirmation flag (must be true)")
    notes = serializers.CharField(
        max_length=1000,
        required=False,
        help_text="Additional notes about deletion"
    )
    
    def validate_employee_id(self, value):
        try:
            Employee.objects.get(id=value)
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Employee not found.")
        return value
    
    def validate_confirm_hard_delete(self, value):
        if not value:
            raise serializers.ValidationError("confirm_hard_delete must be true for hard deletion.")
        return value


class EmployeeCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating employees with auto-generated employee_id"""
    
    # User fields (CHANGED: Required for both create and update)
    first_name = serializers.CharField(max_length=150, required=True)
    last_name = serializers.CharField(max_length=150, required=True)
    email = serializers.EmailField(required=True)
    
    # Optional personal fields
    father_name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    tag_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)
    vacancy_id = serializers.IntegerField(write_only=True, required=False, help_text="Link to vacant position")
    
    # File upload fields
    document = serializers.FileField(write_only=True, required=False, help_text="Employee document file")
    profile_photo = serializers.ImageField(write_only=True, required=False, help_text="Employee profile photo")
    document_type = serializers.ChoiceField(
        choices=EmployeeDocument.DOCUMENT_TYPES,
        write_only=True, 
        required=False, 
        default='OTHER'
    )
    document_name = serializers.CharField(write_only=True, required=False, max_length=255)
    
    # System access fields (optional)
    create_user_account = serializers.BooleanField(
        write_only=True, 
        required=False, 
        default=False,
        help_text="Create system user account for this employee (for system access)"
    )
    
    # Preview field (read-only)
    employee_id_preview = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Employee
        exclude = [
            'employee_id',  # Auto-generated
            'user',        # Managed separately
            'full_name',   # Auto-generated from first_name + last_name
            'tags',        # Handled via tag_ids
            'original_vacancy', 
            'status', 
            'created_by', 
            'updated_by', 
            'profile_image'
        ]
        read_only_fields = [
            'contract_extensions', 
            'last_extension_date', 
            'deleted_by', 
            'deleted_at', 
            'is_deleted',
            'contract_end_date', 
            'created_at', 
            'updated_at'
        ]
    
    def get_employee_id_preview(self, obj):
        """Preview what employee ID will be generated"""
        if hasattr(obj, 'business_function') and obj.business_function:
            return Employee.get_next_employee_id_preview(obj.business_function.id)
        return None
    
    def validate_email(self, value):
        """Validate email uniqueness"""
        if self.instance:
            # Updating existing employee
            if Employee.objects.filter(email=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("Email already exists.")
        else:
            # Creating new employee
            if Employee.objects.filter(email=value).exists():
                raise serializers.ValidationError("Email already exists.")
        return value
    
    @transaction.atomic
    def create(self, validated_data):
        # Extract additional fields
        tag_ids = validated_data.pop('tag_ids', [])
        vacancy_id = validated_data.pop('vacancy_id', None)
        create_user_account = validated_data.pop('create_user_account', False)
        
        # ✅ CRITICAL: Extract first_name, last_name, email
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        email = validated_data.pop('email')
        
        # Extract file data
        document = validated_data.pop('document', None)
        profile_photo = validated_data.pop('profile_photo', None)
        document_type = validated_data.pop('document_type', 'OTHER')
        document_name = validated_data.pop('document_name', '')
        
        # ✅ Set employee fields directly
        validated_data['first_name'] = first_name
        validated_data['last_name'] = last_name
        validated_data['email'] = email
        validated_data['created_by'] = self.context['request'].user
        
        # Set profile photo if provided
        if profile_photo:
            validated_data['profile_image'] = profile_photo
        
        # Set vacancy link if provided
        if vacancy_id:
            validated_data['_vacancy_id'] = vacancy_id
        
        # Set contract_start_date to start_date if not provided
        if not validated_data.get('contract_start_date'):
            validated_data['contract_start_date'] = validated_data.get('start_date')
        
        # Set default values for required fields
        if 'contract_extensions' not in validated_data:
            validated_data['contract_extensions'] = 0
        if 'notes' not in validated_data:
            validated_data['notes'] = ''
        if 'grading_level' not in validated_data:
            validated_data['grading_level'] = ''
        
        # ✅ Create the employee (first_name, last_name, email now in validated_data)
        employee = super().create(validated_data)
        
        # OPTIONAL: Create user account if requested
        if create_user_account:
            try:
                employee.create_user_account()
            except ValueError as e:
                logger.warning(f"Could not create user account for employee {employee.employee_id}: {e}")
        
        # Add tags
        if tag_ids:
            employee.tags.set(tag_ids)
        
        # Handle document upload
        if document:
            doc_name = document_name or document.name
            EmployeeDocument.objects.create(
                employee=employee,
                name=doc_name,
                document_type=document_type,
                document_file=document,
                uploaded_by=self.context['request'].user,
                document_status='ACTIVE',
                version=1,
                is_current_version=True
            )
        
        # Log activity
        activity_description = f"Employee {employee.get_display_name()} created with ID {employee.employee_id}"
        if create_user_account:
            activity_description += " with system access"
        if document:
            activity_description += f" with document '{doc_name}'"
        if profile_photo:
            activity_description += " with profile photo"
        
        EmployeeActivity.objects.create(
            employee=employee,
            activity_type='CREATED',
            description=activity_description,
            performed_by=self.context['request'].user,
            metadata={
                'auto_generated_employee_id': employee.employee_id,
                'has_user_account': bool(employee.user),
                'has_document': bool(document),
                'has_profile_photo': bool(profile_photo),
                'document_type': document_type if document else None
            }
        )
        
        return employee
    
    @transaction.atomic
    def update(self, instance, validated_data):
        # Extract additional fields
        tag_ids = validated_data.pop('tag_ids', None)
        vacancy_id = validated_data.pop('vacancy_id', None)
        create_user_account = validated_data.pop('create_user_account', False)
        
        # ✅ CRITICAL: Extract first_name, last_name, email if provided
        first_name = validated_data.pop('first_name', None)
        last_name = validated_data.pop('last_name', None)
        email = validated_data.pop('email', None)
        
        # Extract file data
        document = validated_data.pop('document', None)
        profile_photo = validated_data.pop('profile_photo', None)
        document_type = validated_data.pop('document_type', 'OTHER')
        document_name = validated_data.pop('document_name', '')
        
        # Track changes for activity log
        changes = []
        
        # ✅ Update employee fields directly
        if first_name is not None:
            old_value = instance.first_name
            if old_value != first_name:
                instance.first_name = first_name
                validated_data['first_name'] = first_name
                changes.append(f"First Name: {old_value} → {first_name}")
        
        if last_name is not None:
            old_value = instance.last_name
            if old_value != last_name:
                instance.last_name = last_name
                validated_data['last_name'] = last_name
                changes.append(f"Last Name: {old_value} → {last_name}")
        
        if email is not None:
            old_value = instance.email
            if old_value != email:
                instance.email = email
                validated_data['email'] = email
                changes.append(f"Email: {old_value} → {email}")
        
        # Update profile photo if provided
        if profile_photo:
            if instance.profile_image:
                try:
                    if hasattr(instance.profile_image, 'path'):
                        import os
                        old_image_path = instance.profile_image.path
                        if os.path.exists(old_image_path):
                            os.remove(old_image_path)
                except Exception as e:
                    logger.warning(f"Could not delete old profile image: {e}")
            
            instance.profile_image = profile_photo
            changes.append("Profile photo updated")
        
        # Set updated_by
        validated_data['updated_by'] = self.context['request'].user
        
        # Update employee
        employee = super().update(instance, validated_data)
        
        # OPTIONAL: Create user account if requested and doesn't exist
        if create_user_account and not employee.user:
            try:
                user = User.objects.create_user(
                    username=employee.email,
                    email=employee.email,
                    first_name=employee.first_name,
                    last_name=employee.last_name
                )
                user.set_unusable_password()
                user.save()
                
                employee.user = user
                employee.save()
                
                changes.append("System user account created")
            except Exception as e:
                logger.warning(f"Could not create user account for employee {employee.employee_id}: {e}")
        
        # ✅ FIX: Sync user account if it exists - NULL CHECK
        if employee.user:
            user_updated = False
            
            # ✅ Only update if values are provided and different
            if first_name and employee.user.first_name != employee.first_name:
                employee.user.first_name = employee.first_name
                user_updated = True
            
            if last_name and employee.user.last_name != employee.last_name:
                employee.user.last_name = employee.last_name
                user_updated = True
            
            if email and employee.user.email != employee.email:
                employee.user.email = employee.email
                employee.user.username = employee.email
                user_updated = True
            
            if user_updated:
                try:
                    employee.user.save()
                    changes.append("User account synced")
                except Exception as e:
                    logger.warning(f"Could not sync user account: {e}")
        
        # Update tags
        if tag_ids is not None:
            employee.tags.set(tag_ids)
            changes.append("Tags updated")
        
        # Handle document upload
        if document:
            doc_name = document_name or document.name
            EmployeeDocument.objects.create(
                employee=employee,
                name=doc_name,
                document_type=document_type,
                document_file=document,
                uploaded_by=self.context['request'].user,
                document_status='ACTIVE',
                version=1,
                is_current_version=True
            )
            changes.append(f"Document '{doc_name}' uploaded")
        
        # Link to vacancy if provided
        if vacancy_id:
            try:
                vacancy = VacantPosition.objects.get(id=vacancy_id, is_filled=False)
                vacancy.mark_as_filled(employee)
                changes.append(f"Linked to vacant position {vacancy.position_id}")
            except VacantPosition.DoesNotExist:
                pass
        
        # Log activity
        if changes:
            EmployeeActivity.objects.create(
                employee=employee,
                activity_type='UPDATED',
                description=f"Employee {employee.get_display_name()} updated: {'; '.join(changes)}",
                performed_by=self.context['request'].user,
                metadata={
                    'changes': changes,
                    'has_user_account': bool(employee.user),
                    'has_new_document': bool(document),
                    'has_new_profile_photo': bool(profile_photo),
                    'employee_id_unchanged': employee.employee_id
                }
            )
        
        return employee
class BulkEmployeeCreateItemSerializer(serializers.Serializer):
    """Serializer for a single employee in bulk creation"""
    employee_id = serializers.CharField(max_length=50, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=Employee.GENDER_CHOICES, required=False, allow_null=True)
    father_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    emergency_contact = serializers.CharField(required=False, allow_blank=True)
    
    # Job Information
    business_function_id = serializers.IntegerField()
    department_id = serializers.IntegerField()
    unit_id = serializers.IntegerField(required=False, allow_null=True)
    job_function_id = serializers.IntegerField()
    job_title = serializers.CharField(max_length=200)
    position_group_id = serializers.IntegerField()
    grading_level = serializers.CharField(max_length=15, required=False, allow_blank=True)
    
    # Employment Details
    start_date = serializers.DateField()
    # FIXED: Use CharField instead of ChoiceField for dynamic contract types
    contract_duration = serializers.CharField(max_length=50, default='PERMANENT')
    contract_start_date = serializers.DateField(required=False, allow_null=True)
    line_manager_id = serializers.IntegerField(required=False, allow_null=True)
    
    # Additional
    is_visible_in_org_chart = serializers.BooleanField(default=True)
    tag_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    notes = serializers.CharField(required=False, allow_blank=True)
    vacancy_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate_contract_duration(self, value):
        """Validate that contract duration exists in configurations"""
        try:
            ContractTypeConfig.objects.get(contract_type=value, is_active=True)
        except ContractTypeConfig.DoesNotExist:
            # Get available choices for error message
            available_choices = list(ContractTypeConfig.objects.filter(is_active=True).values_list('contract_type', flat=True))
            raise serializers.ValidationError(
                f"Invalid contract duration '{value}'. Available choices: {', '.join(available_choices)}"
            )
        return value

class BulkEmployeeUpdateSerializer(serializers.Serializer):
    employee_ids = serializers.ListField(child=serializers.IntegerField())
    updates = serializers.DictField()
    
    def validate_employee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one employee ID is required.")
        
        # Validate all employee IDs exist
        existing_count = Employee.objects.filter(id__in=value).count()
        if existing_count != len(value):
            raise serializers.ValidationError("Some employee IDs do not exist.")
        
        return value

class BulkLineManagerAssignmentSerializer(serializers.Serializer):
    """Bulk line manager assignment using employee IDs"""
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of employee IDs to update"
    )
    line_manager_id = serializers.IntegerField(
        allow_null=True,
        help_text="Line manager employee ID (null to remove line manager)"
    )
    
    def validate_employee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one employee ID is required.")
        
        existing_count = Employee.objects.filter(id__in=value).count()
        if existing_count != len(value):
            raise serializers.ValidationError("Some employee IDs do not exist.")
        
        return value
    
    def validate_line_manager_id(self, value):
        if value is not None:
            try:
                Employee.objects.get(id=value)
            except Employee.DoesNotExist:
                raise serializers.ValidationError("Line manager not found.")
        return value

class SingleLineManagerAssignmentSerializer(serializers.Serializer):
    """Single employee line manager assignment"""
    employee_id = serializers.IntegerField(help_text="Employee ID")
    line_manager_id = serializers.IntegerField(
        allow_null=True,
        help_text="Line manager employee ID (null to remove line manager)"
    )
    
    def validate_employee_id(self, value):
        try:
            Employee.objects.get(id=value)
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Employee not found.")
        return value
    
    def validate_line_manager_id(self, value):
        if value is not None:
            try:
                Employee.objects.get(id=value)
            except Employee.DoesNotExist:
                raise serializers.ValidationError("Line manager not found.")
        return value

class BulkEmployeeTagUpdateSerializer(serializers.Serializer):
    """
    ✅ UPDATED: Bulk tag operations with automatic INACTIVE status change
    """
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of employee IDs to update"
    )
    tag_id = serializers.IntegerField(
        help_text="Tag ID to add or remove"
    )
    
    # ✅ YENİ: Optional field to override auto-INACTIVE behavior
    skip_status_change = serializers.BooleanField(
        default=False,
        required=False,
        help_text="Set to true to skip automatic status change to INACTIVE (advanced use only)"
    )
    
    def validate_employee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one employee ID is required.")
        
        existing_count = Employee.objects.filter(id__in=value).count()
        if existing_count != len(value):
            raise serializers.ValidationError("Some employee IDs do not exist.")
        
        return value
    
    def validate_tag_id(self, value):
        try:
            EmployeeTag.objects.get(id=value)
        except EmployeeTag.DoesNotExist:
            raise serializers.ValidationError("Tag not found.")
        return value
class SingleEmployeeTagUpdateSerializer(serializers.Serializer):
    """Single employee tag operations"""
    employee_id = serializers.IntegerField(help_text="Employee ID")
    tag_id = serializers.IntegerField(help_text="Tag ID to add or remove")
    
    def validate_employee_id(self, value):
        try:
            Employee.objects.get(id=value)
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Employee not found.")
        return value
    
    def validate_tag_id(self, value):
        try:
            EmployeeTag.objects.get(id=value)
        except EmployeeTag.DoesNotExist:
            raise serializers.ValidationError("Tag not found.")
        return value

class EmployeeGradingUpdateSerializer(serializers.Serializer):
    """Serializer for updating employee grading information"""
    employee_id = serializers.IntegerField()
    grading_level = serializers.CharField()
    
    def validate_grading_level(self, value):
        """Validate grading level format"""
        if value and '_' not in value:
            raise serializers.ValidationError("Grading level must be in format POSITION_LEVEL (e.g., MGR_UQ)")
        return value
    
    def validate_employee_id(self, value):
        try:
            Employee.objects.get(id=value)
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Employee not found.")
        return value

class EmployeeGradingListSerializer(serializers.ModelSerializer):
    """Serializer for employee grading information display"""
    name = serializers.CharField(source='full_name', read_only=True)
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    grading_display = serializers.CharField(source='get_grading_display', read_only=True)
    available_levels = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'name', 'job_title', 'position_group_name',
            'grading_level', 'grading_display', 'available_levels'
        ]
    
    def get_available_levels(self, obj):
        """Get available grading levels for this employee's position"""
        if obj.position_group:
            return obj.position_group.get_grading_levels()
        return []

class BulkEmployeeGradingUpdateSerializer(serializers.Serializer):
    """Serializer for bulk updating employee grades"""
    updates = serializers.ListField(
        child=EmployeeGradingUpdateSerializer(),
        help_text="List of employee grading updates",
        allow_empty=False
    )
    
    def validate_updates(self, value):
        if not value:
            raise serializers.ValidationError("At least one update is required")
        return value

class OrgChartNodeSerializer(serializers.ModelSerializer):
    """FINAL FIXED: Enhanced serializer for organizational chart nodes"""
    
    # ✅ Internal database ID (primary key)
    id = serializers.IntegerField(read_only=True)
    
    # Basic employee info for org chart
    employee_id = serializers.CharField(read_only=True)  # HC001 kimi
    name = serializers.CharField(source='full_name', read_only=True)
    title = serializers.CharField(source='job_title', read_only=True)
    avatar = serializers.SerializerMethodField()
    
    # Organizational info
    department = serializers.CharField(source='department.name', read_only=True)
    unit = serializers.SerializerMethodField()
    business_function = serializers.CharField(source='business_function.name', read_only=True)
    position_group = serializers.CharField(source='position_group.get_name_display', read_only=True)
    
    # Contact info
    email = serializers.CharField(source='user.email', read_only=True)
    phone = serializers.SerializerMethodField()
    
    # Hierarchy info
    line_manager_id = serializers.CharField(source='line_manager.employee_id', read_only=True)
    direct_reports = serializers.SerializerMethodField()
    direct_reports_details = serializers.SerializerMethodField()
    
    # Visual info
    status_color = serializers.CharField(source='status.color', read_only=True)
    profile_image_url = serializers.SerializerMethodField()
    
    # Additional calculated fields
    level_to_ceo = serializers.SerializerMethodField()
    total_subordinates = serializers.SerializerMethodField()
    colleagues_in_unit = serializers.SerializerMethodField()
    colleagues_in_business_function = serializers.SerializerMethodField()
    manager_info = serializers.SerializerMethodField()
    
    # Employee details
    employee_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            # ✅ ƏSAS: ID və Employee ID hər ikisi
            'id',  # Internal database ID (73)
            'employee_id',  # Business ID (GEO1, HC001)
            
            # Org chart essentials
            'name', 'title', 'avatar',
            'department', 'unit', 'business_function', 'position_group',
            'email', 'phone',
            'line_manager_id', 'direct_reports', 'direct_reports_details', 'status_color',
            'profile_image_url',
            
            # Calculated metrics
            'level_to_ceo', 'total_subordinates', 
            'colleagues_in_unit', 'colleagues_in_business_function',
            'manager_info', 'employee_details'
        ]
    def to_representation(self, instance):
        """Format text fields to title case"""
        data = super().to_representation(instance)
        
        # ✅ Title case tətbiq et - ad və soyad
        text_fields = [
            'name',  
            'title', 'department', 'unit', 'business_function',
        ]
        
        for field in text_fields:
            if field in data and data[field]:
                # Strip whitespace və title case
                data[field] = str(data[field]).strip().title()
        
        return data
    
    def get_employee_details(self, obj):
        """Get additional employee details safely"""
        try:
            # FIXED: Safe grading display
            grading_display = 'No Grade'
            if obj.grading_level:
                parts = obj.grading_level.split('_')
                if len(parts) == 2:
                    position_short, level = parts
                    grading_display = f"{position_short}-{level}"
                else:
                    grading_display = obj.grading_level
            elif obj.position_group:
                grading_display = f"{obj.position_group.grading_shorthand}-M"
            
            # FIXED: Safe contract duration
            contract_duration = obj.contract_duration
            try:
                if hasattr(obj, 'get_contract_duration_display'):
                    contract_duration = obj.get_contract_duration_display()
            except:
                pass
            
            return {
                'internal_id': obj.id,  # ✅ ID burada da var
                'employee_id': obj.employee_id,  # ✅ Employee ID burada da var
                'start_date': obj.start_date,
                'contract_duration': contract_duration,
                'years_of_service': obj.years_of_service,
                'grading_display': grading_display,
                'tags': [
                    {'name': tag.name, 'color': tag.color} 
                    for tag in obj.tags.filter(is_active=True)
                ],
                'is_visible_in_org_chart': obj.is_visible_in_org_chart,
                'created_at': obj.created_at,
                'updated_at': obj.updated_at
            }
        except Exception as e:
            return {
                'internal_id': obj.id,
                'employee_id': getattr(obj, 'employee_id', 'UNKNOWN'),
                'start_date': obj.start_date,
                'contract_duration': getattr(obj, 'contract_duration', 'N/A'),
                'years_of_service': getattr(obj, 'years_of_service', 0),
                'grading_display': 'No Grade',
                'tags': [],
                'is_visible_in_org_chart': getattr(obj, 'is_visible_in_org_chart', True),
                'created_at': getattr(obj, 'created_at', None),
                'updated_at': getattr(obj, 'updated_at', None)
            }
    
    def get_direct_reports_details(self, obj):
        """NEW: Get detailed information about direct reports"""
        try:
            direct_reports = Employee.objects.filter(
                line_manager=obj,
                status__allows_org_chart=True,
                is_deleted=False
            ).select_related('user', 'department', 'position_group', 'status')
            
            reports_data = []
            for report in direct_reports:
                report_data = {
                    'id': report.id,  # ✅ Internal ID
                    'employee_id': report.employee_id,  # ✅ Business ID
                    'name': report.full_name,
                    'title': report.job_title,
                    'department': report.department.name if report.department else 'N/A',
                    'unit': report.unit.name if report.unit else None,
                    'position_group': report.position_group.get_name_display() if report.position_group else 'N/A',
                    'email': report.user.email if report.user else 'N/A',
                    'avatar': self.get_avatar(report),
                    'status_color': report.status.color if report.status else '#6B7280',
                    'profile_image_url': self._get_safe_profile_image_url(report)
                }
                reports_data.append(report_data)
            
            return reports_data
        except Exception:
            return []
    
    def get_manager_info(self, obj):
        """Get manager information safely"""
        try:
            if not obj.line_manager:
                return None
            
            manager = obj.line_manager
            return {
                'id': manager.id,  # ✅ Internal ID
                'employee_id': manager.employee_id,  # ✅ Business ID
                'name': manager.full_name,
                'title': manager.job_title,
                'department': manager.department.name if manager.department else 'N/A',
                'avatar': self.get_avatar(manager),
                'email': manager.user.email if manager.user else None,
                'profile_image_url': self._get_safe_profile_image_url(manager)
            }
        except Exception:
            return None
    
    def get_avatar(self, obj):
        """Generate avatar initials safely"""
        try:
            if not obj.full_name:
                return 'NA'
            
            words = obj.full_name.strip().split()
            if len(words) >= 2:
                return f"{words[0][0]}{words[1][0]}".upper()
            elif len(words) == 1:
                return words[0][:2].upper()
            return 'NA'
        except Exception:
            return 'NA'
    
    
    def get_unit(self, obj):
        """FIXED: Get unit name properly or department name as fallback"""
        try:
            if obj.unit and obj.unit.name:
                return obj.unit.name
            
            return 'N/A'
        except Exception:
            return 'N/A'
    
    def get_phone(self, obj):
        """Get phone or default"""
        return obj.phone or '+994 50 xxx xxxx'
    
    def get_direct_reports(self, obj):
        """Get number of direct reports safely"""
        try:
            return Employee.objects.filter(
                line_manager=obj,
                status__allows_org_chart=True,
                is_deleted=False
            ).count()
        except Exception:
            return 0
    
    
    def _get_safe_profile_image_url(self, employee):
        """Get profile image URL safely for any employee"""
        try:
            if employee.profile_image and hasattr(employee.profile_image, 'url'):
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(employee.profile_image.url)
                return employee.profile_image.url
        except Exception:
            pass
        return None
    
    def get_profile_image_url(self, obj):
        """Get profile image URL safely"""
        return self._get_safe_profile_image_url(obj)
    
    def get_level_to_ceo(self, obj):
        """FIXED: Calculate level to CEO with recursion protection"""
        try:
            level = 0
            current = obj
            visited = set()
            
            while current and current.line_manager and current.id not in visited:
                visited.add(current.id)
                current = current.line_manager
                level += 1
                
                if level > 10:  # Prevent infinite loops
                    break
            
            return level
        except Exception:
            return 0
    
    def get_total_subordinates(self, obj):
        """FIXED: Calculate total subordinates with recursion protection"""
        try:
            def count_subordinates_safe(employee, visited=None):
                if visited is None:
                    visited = set()
                
                if employee.id in visited:
                    return 0
                
                visited.add(employee.id)
                
                direct_reports = Employee.objects.filter(
                    line_manager=employee,
                    status__allows_org_chart=True,
                    is_deleted=False
                )
                
                total = direct_reports.count()
                for report in direct_reports:
                    if report.id not in visited:
                        total += count_subordinates_safe(report, visited.copy())
                
                return total
            
            return count_subordinates_safe(obj)
        except Exception:
            return 0
    
    def get_colleagues_in_unit(self, obj):
        """Get colleagues in same unit safely"""
        try:
            if not obj.unit:
                return 0
            
            return Employee.objects.filter(
                unit=obj.unit,
                status__allows_org_chart=True,
                is_deleted=False
            ).exclude(id=obj.id).count()
        except Exception:
            return 0
    
    def get_colleagues_in_business_function(self, obj):
        """Get colleagues in same business function safely"""
        try:
            if not obj.business_function:
                return 0
            
            return Employee.objects.filter(
                business_function=obj.business_function,
                status__allows_org_chart=True,
                is_deleted=False
            ).exclude(id=obj.id).count()
        except Exception:
            return 0
    
class ContractExpirySerializer(serializers.ModelSerializer):
    """Serializer for contract expiry tracking"""
    name = serializers.CharField(source='full_name', read_only=True)
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    days_until_expiry = serializers.SerializerMethodField()
    status_needs_update = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'name', 'job_title', 'business_function_name',
            'department_name', 'position_group_name', 'contract_duration',
            'contract_end_date', 'days_until_expiry', 'status_needs_update'
        ]
    
    def get_days_until_expiry(self, obj):
        if obj.contract_end_date:
            delta = obj.contract_end_date - date.today()
            return delta.days
        return None
    
    def get_status_needs_update(self, obj):
        try:
            preview = obj.get_status_preview()
            return preview['needs_update']
        except:
            return False

class EmployeeExportSerializer(serializers.Serializer):
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(), 
        required=False,
        help_text="List of employee IDs to export. If empty, exports filtered results."
    )
    export_format = serializers.ChoiceField(
        choices=[('csv', 'CSV'), ('excel', 'Excel')],
        default='excel'
    )
    include_fields = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="List of fields to include in export"
    )

class ContractExtensionSerializer(serializers.Serializer):
    """Contract extension for single employee - WITHOUT extension_months"""
    employee_id = serializers.IntegerField(help_text="Employee ID")
    new_contract_type = serializers.CharField(
        max_length=50,
        help_text="New contract type (required)"
    )
    new_start_date = serializers.DateField(
        help_text="New contract start date (required)"
    )
    reason = serializers.CharField(
        max_length=500,
        required=False,
        help_text="Reason for contract change"
    )
    
    def validate_employee_id(self, value):
        try:
            Employee.objects.get(id=value)
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Employee not found.")
        return value
    
    def validate_new_contract_type(self, value):
        try:
            ContractTypeConfig.objects.get(contract_type=value, is_active=True)
        except ContractTypeConfig.DoesNotExist:
            available_choices = list(ContractTypeConfig.objects.filter(is_active=True).values_list('contract_type', flat=True))
            raise serializers.ValidationError(
                f"Invalid contract type '{value}'. Available choices: {', '.join(available_choices)}"
            )
        return value

class BulkContractExtensionSerializer(serializers.Serializer):
    """Bulk contract extension - WITHOUT extension_months"""
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of employee IDs to update contracts"
    )
    new_contract_type = serializers.CharField(
        max_length=50,
        help_text="New contract type for all employees (required)"
    )
    new_start_date = serializers.DateField(
        help_text="New contract start date for all employees (required)"
    )
    reason = serializers.CharField(
        max_length=500,
        required=False,
        help_text="Reason for contract change"
    )
    
    def validate_employee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one employee ID is required.")
        
        employees = Employee.objects.filter(id__in=value)
        if employees.count() != len(value):
            raise serializers.ValidationError("Some employee IDs do not exist.")
        
        return value
    
    def validate_new_contract_type(self, value):
        try:
            ContractTypeConfig.objects.get(contract_type=value, is_active=True)
        except ContractTypeConfig.DoesNotExist:
            available_choices = list(ContractTypeConfig.objects.filter(is_active=True).values_list('contract_type', flat=True))
            raise serializers.ValidationError(
                f"Invalid contract type '{value}'. Available choices: {', '.join(available_choices)}"
            )
        return value

                    
                    