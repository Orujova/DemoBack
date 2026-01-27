# api/job_description_serializers.py - UPDATED: Multiple employee assignment support
# PART 1: Basic and Resource serializers

from rest_framework import serializers
from .job_description_models import (
    JobDescription, JobDescriptionAssignment, JobDescriptionSection,
    JobDescriptionSkill, JobDescriptionBehavioralCompetency,
    JobBusinessResource, AccessMatrix, CompanyBenefit,
    JobDescriptionBusinessResource, JobDescriptionAccessMatrix,
    JobDescriptionCompanyBenefit, JobBusinessResourceItem,
    AccessMatrixItem, CompanyBenefitItem, normalize_grading_level
)
from .models import BusinessFunction, Department, Unit, PositionGroup, Employee, JobFunction, VacantPosition
from .competency_models import Skill, BehavioralCompetency
from django.contrib.auth.models import User
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


# ==================== BASIC SERIALIZERS ====================

class BusinessFunctionBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessFunction
        fields = ['id', 'name', 'code']


class DepartmentBasicSerializer(serializers.ModelSerializer):
    business_function = BusinessFunctionBasicSerializer(read_only=True)
    
    class Meta:
        model = Department
        fields = ['id', 'name', 'business_function']


class UnitBasicSerializer(serializers.ModelSerializer):
    department = DepartmentBasicSerializer(read_only=True)
    
    class Meta:
        model = Unit
        fields = ['id', 'name', 'department']


class PositionGroupBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = PositionGroup
        fields = ['id', 'name', 'hierarchy_level', 'grading_shorthand']


class JobFunctionBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobFunction
        fields = ['id', 'name']


class UserBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']


class EmployeeBasicSerializer(serializers.ModelSerializer):
    """Enhanced employee serializer with organizational details"""
    
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    job_function_name = serializers.CharField(source='job_function.name', read_only=True)
    position_group_name = serializers.CharField(source='position_group.name', read_only=True)
    line_manager_name = serializers.CharField(source='line_manager.full_name', read_only=True)
    line_manager_id = serializers.IntegerField(source='line_manager.id', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    has_line_manager = serializers.SerializerMethodField()
    organizational_path = serializers.SerializerMethodField()
    matching_score = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'full_name', 'job_title', 'phone', 'email',
            'business_function', 'business_function_name',
            'department', 'department_name',
            'unit', 'unit_name',
            'job_function', 'job_function_name',
            'position_group', 'position_group_name',
            'grading_level', 'line_manager', 'line_manager_name', 'line_manager_id',
            'has_line_manager', 'organizational_path', 'matching_score'
        ]
    
    def get_has_line_manager(self, obj):
        return obj.line_manager is not None
    
    def get_organizational_path(self, obj):
        path_parts = []
        if obj.business_function:
            path_parts.append(obj.business_function.name)
        if obj.department:
            path_parts.append(obj.department.name)
        if obj.unit:
            path_parts.append(obj.unit.name)
        if obj.job_function:
            path_parts.append(f"Function: {obj.job_function.name}")
        if obj.position_group:
            path_parts.append(f"Grade: {obj.grading_level}")
        return " > ".join(path_parts)
    
    def get_matching_score(self, obj):
        return 100


# ==================== SKILL & COMPETENCY SERIALIZERS ====================

class SkillBasicSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)
    
    class Meta:
        model = Skill
        fields = ['id', 'name', 'group_name']


class BehavioralCompetencyBasicSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)
    
    class Meta:
        model = BehavioralCompetency
        fields = ['id', 'name', 'group_name']


# ==================== RESOURCE ITEM SERIALIZERS ====================

class JobBusinessResourceItemDetailSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    resource_name = serializers.CharField(source='resource.name', read_only=True)
    full_path = serializers.SerializerMethodField()
    formatted_created_at = serializers.SerializerMethodField()
    
    class Meta:
        model = JobBusinessResourceItem
        fields = [
            'id', 'resource', 'resource_name', 'name', 'description',
            'full_path', 'is_active', 'created_at', 'formatted_created_at',
            'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'created_by']
    
    def get_full_path(self, obj):
        return f"{obj.resource.name} > {obj.name}"
    
    def get_formatted_created_at(self, obj):
        if obj.created_at:
            return obj.created_at.strftime('%d %B %Y, %H:%M')
        return None


class JobBusinessResourceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobBusinessResourceItem
        fields = ['id', 'resource', 'name', 'description', 'is_active']


class AccessMatrixItemDetailSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    access_matrix_name = serializers.CharField(source='access_matrix.name', read_only=True)
    full_path = serializers.SerializerMethodField()
    formatted_created_at = serializers.SerializerMethodField()
    
    class Meta:
        model = AccessMatrixItem
        fields = [
            'id', 'access_matrix', 'access_matrix_name', 'name', 'description',
            'full_path', 'is_active', 'created_at', 'formatted_created_at',
            'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'created_by']
    
    def get_full_path(self, obj):
        return f"{obj.access_matrix.name} > {obj.name}"
    
    def get_formatted_created_at(self, obj):
        if obj.created_at:
            return obj.created_at.strftime('%d %B %Y, %H:%M')
        return None


class AccessMatrixItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessMatrixItem
        fields = ['id', 'access_matrix', 'name', 'description', 'is_active']


class CompanyBenefitItemDetailSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    benefit_name = serializers.CharField(source='benefit.name', read_only=True)
    full_path = serializers.SerializerMethodField()
    formatted_created_at = serializers.SerializerMethodField()
    
    class Meta:
        model = CompanyBenefitItem
        fields = [
            'id', 'benefit', 'benefit_name', 'name', 'description', 'value',
            'full_path', 'is_active', 'created_at', 'formatted_created_at',
            'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'created_by']
    
    def get_full_path(self, obj):
        return f"{obj.benefit.name} > {obj.name}"
    
    def get_formatted_created_at(self, obj):
        if obj.created_at:
            return obj.created_at.strftime('%d %B %Y, %H:%M')
        return None


class CompanyBenefitItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyBenefitItem
        fields = ['id', 'benefit', 'name', 'description', 'value', 'is_active']


# ==================== RESOURCE PARENT SERIALIZERS ====================

class JobBusinessResourceSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    items = JobBusinessResourceItemDetailSerializer(many=True, read_only=True)
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = JobBusinessResource
        fields = [
            'id', 'name', 'description', 'is_active',
            'created_at', 'created_by', 'created_by_name',
            'items', 'items_count'
        ]
        read_only_fields = ['created_at', 'created_by']
    
    def get_items_count(self, obj):
        return obj.items.filter(is_active=True).count()


class AccessMatrixSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    items = AccessMatrixItemDetailSerializer(many=True, read_only=True)
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AccessMatrix
        fields = [
            'id', 'name', 'description', 'is_active',
            'created_at', 'created_by', 'created_by_name',
            'items', 'items_count'
        ]
        read_only_fields = ['created_at', 'created_by']
    
    def get_items_count(self, obj):
        return obj.items.filter(is_active=True).count()


class CompanyBenefitSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    items = CompanyBenefitItemDetailSerializer(many=True, read_only=True)
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CompanyBenefit
        fields = [
            'id', 'name', 'description', 'is_active',
            'created_at', 'created_by', 'created_by_name',
            'items', 'items_count'
        ]
        read_only_fields = ['created_at', 'created_by']
    
    def get_items_count(self, obj):
        return obj.items.filter(is_active=True).count()


# ==================== JOB DESCRIPTION COMPONENT SERIALIZERS ====================

class JobDescriptionSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobDescriptionSection
        fields = ['id', 'section_type', 'title', 'content', 'order']


class JobDescriptionSkillSerializer(serializers.ModelSerializer):
    skill_detail = SkillBasicSerializer(source='skill', read_only=True)
    
    class Meta:
        model = JobDescriptionSkill
        fields = ['id', 'skill', 'skill_detail']


class JobDescriptionBehavioralCompetencySerializer(serializers.ModelSerializer):
    competency_detail = BehavioralCompetencyBasicSerializer(source='competency', read_only=True)
    
    class Meta:
        model = JobDescriptionBehavioralCompetency
        fields = ['id', 'competency', 'competency_detail']


class JobDescriptionBusinessResourceSerializer(serializers.ModelSerializer):
    resource_detail = JobBusinessResourceSerializer(source='resource', read_only=True)
    
    class Meta:
        model = JobDescriptionBusinessResource
        fields = ['id', 'resource', 'resource_detail']


class JobDescriptionAccessMatrixSerializer(serializers.ModelSerializer):
    access_detail = AccessMatrixSerializer(source='access_matrix', read_only=True)
    
    class Meta:
        model = JobDescriptionAccessMatrix
        fields = ['id', 'access_matrix', 'access_detail']


class JobDescriptionCompanyBenefitSerializer(serializers.ModelSerializer):
    benefit_detail = CompanyBenefitSerializer(source='benefit', read_only=True)
    
    class Meta:
        model = JobDescriptionCompanyBenefit
        fields = ['id', 'benefit', 'benefit_detail']


class JobDescriptionBusinessResourceDetailSerializer(serializers.ModelSerializer):
    resource_detail = JobBusinessResourceSerializer(source='resource', read_only=True)
    specific_items_detail = JobBusinessResourceItemDetailSerializer(
        source='specific_items', many=True, read_only=True
    )
    has_specific_items = serializers.SerializerMethodField()
    items_display = serializers.SerializerMethodField()
    
    class Meta:
        model = JobDescriptionBusinessResource
        fields = [
            'id', 'resource', 'resource_detail', 'specific_items_detail',
            'has_specific_items', 'items_display'
        ]
    
    def get_has_specific_items(self, obj):
        return obj.specific_items.exists()
    
    def get_items_display(self, obj):
        if obj.specific_items.exists():
            items = obj.specific_items.all()
            return f"{obj.resource.name}: {', '.join([item.name for item in items])}"
        return f"{obj.resource.name}: All items"


class JobDescriptionAccessMatrixDetailSerializer(serializers.ModelSerializer):
    access_detail = AccessMatrixSerializer(source='access_matrix', read_only=True)
    specific_items_detail = AccessMatrixItemDetailSerializer(
        source='specific_items', many=True, read_only=True
    )
    has_specific_items = serializers.SerializerMethodField()
    items_display = serializers.SerializerMethodField()
    
    class Meta:
        model = JobDescriptionAccessMatrix
        fields = [
            'id', 'access_matrix', 'access_detail', 'specific_items_detail',
            'has_specific_items', 'items_display'
        ]
    
    def get_has_specific_items(self, obj):
        return obj.specific_items.exists()
    
    def get_items_display(self, obj):
        if obj.specific_items.exists():
            items = obj.specific_items.all()
            return f"{obj.access_matrix.name}: {', '.join([item.name for item in items])}"
        return f"{obj.access_matrix.name}: All items"


class JobDescriptionCompanyBenefitDetailSerializer(serializers.ModelSerializer):
    benefit_detail = CompanyBenefitSerializer(source='benefit', read_only=True)
    specific_items_detail = CompanyBenefitItemDetailSerializer(
        source='specific_items', many=True, read_only=True
    )
    has_specific_items = serializers.SerializerMethodField()
    items_display = serializers.SerializerMethodField()
    
    class Meta:
        model = JobDescriptionCompanyBenefit
        fields = [
            'id', 'benefit', 'benefit_detail', 'specific_items_detail',
            'has_specific_items', 'items_display'
        ]
    
    def get_has_specific_items(self, obj):
        return obj.specific_items.exists()
    
    def get_items_display(self, obj):
        if obj.specific_items.exists():
            items = obj.specific_items.all()
            return f"{obj.benefit.name}: {', '.join([item.name for item in items])}"
        return f"{obj.benefit.name}: All items"
    
# api/job_description_serializers.py - PART 2: Assignment and Main serializers
# Bu hissəni Part 1-in ardınca əlavə edin

# ==================== ASSIGNMENT SERIALIZERS ====================

class JobDescriptionAssignmentListSerializer(serializers.ModelSerializer):
    """Serializer for listing assignments"""
    
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id_number = serializers.CharField(source='employee.employee_id', read_only=True)
    reports_to_name = serializers.CharField(source='reports_to.full_name', read_only=True)
    status_display = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    job_description_title = serializers.CharField(source='job_description.job_title', read_only=True)
    
    class Meta:
        model = JobDescriptionAssignment
        fields = [
            'id', 'job_description', 'job_description_title',
            'employee', 'employee_name', 'employee_id_number',
            'is_vacancy', 'vacancy_position', 'reports_to', 'reports_to_name',
            'status', 'status_display', 'display_name',
            'line_manager_approved_at', 'employee_approved_at',
            'created_at', 'is_active'
        ]
    
    def get_status_display(self, obj):
        return obj.get_status_display_with_color()
    
    def get_display_name(self, obj):
        return obj.get_display_name()


class JobDescriptionAssignmentDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single assignment"""
    
    employee = EmployeeBasicSerializer(read_only=True)
    reports_to = EmployeeBasicSerializer(read_only=True)
    line_manager_approved_by_detail = UserBasicSerializer(
        source='line_manager_approved_by', read_only=True
    )
    employee_approved_by_detail = UserBasicSerializer(
        source='employee_approved_by', read_only=True
    )
    status_display = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    can_approve_as_line_manager = serializers.SerializerMethodField()
    can_approve_as_employee = serializers.SerializerMethodField()
    employee_info = serializers.SerializerMethodField()
    manager_info = serializers.SerializerMethodField()
    validation_result = serializers.SerializerMethodField()
    matching_details = serializers.SerializerMethodField()
    
    class Meta:
        model = JobDescriptionAssignment
        fields = [
            'id', 'job_description', 'employee', 'is_vacancy', 'vacancy_position',
            'reports_to', 'status', 'status_display', 'display_name',
            'line_manager_approved_by_detail', 'line_manager_approved_at',
            'line_manager_comments', 'employee_approved_by_detail',
            'employee_approved_at', 'employee_comments',
            'line_manager_signature', 'employee_signature',
            'created_at', 'updated_at', 'is_active',
            'employee_removed_at', 'employee_removed_reason',
            'can_approve_as_line_manager', 'can_approve_as_employee',
            'employee_info', 'manager_info', 'validation_result', 'matching_details'
        ]
    
    def get_status_display(self, obj):
        return obj.get_status_display_with_color()
    
    def get_display_name(self, obj):
        return obj.get_display_name()
    
    def get_can_approve_as_line_manager(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.can_be_approved_by_line_manager(request.user)
    
    def get_can_approve_as_employee(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.can_be_approved_by_employee(request.user)
    
    def get_employee_info(self, obj):
        return obj.get_employee_info()
    
    def get_manager_info(self, obj):
        return obj.get_manager_info()
    
    def get_validation_result(self, obj):
        is_valid, message = obj.validate_employee_assignment()
        return {'is_valid': is_valid, 'message': message}
    
    def get_matching_details(self, obj):
        return obj.get_employee_matching_details()


# ==================== MAIN CREATE/UPDATE SERIALIZER ====================

class JobDescriptionCreateUpdateSerializer(serializers.ModelSerializer):
    """Create job description with multiple employee assignments"""
    
    # Nested data inputs
    sections = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="List of sections: {section_type, title, content, order}"
    )
    required_skills_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="List of {skill_id}"
    )
    behavioral_competencies_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="List of {competency_id}"
    )
    business_resources_with_items = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="List of {resource_id: int, item_ids: [int]}"
    )
    access_rights_with_items = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="List of {access_matrix_id: int, item_ids: [int]}"
    )
    company_benefits_with_items = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="List of {benefit_id: int, item_ids: [int]}"
    )
    
    # Employee selection
    selected_employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of employee IDs to assign"
    )
    
    grading_levels = serializers.ListField(
        child=serializers.CharField(max_length=10),
        required=True,
        help_text="List of grading levels (e.g., ['M', 'N', 'O'])"
    )
    
    # Response fields
    assignments_created = serializers.SerializerMethodField()
    total_assignments = serializers.SerializerMethodField()
    requires_selection = serializers.SerializerMethodField()
    
    class Meta:
        model = JobDescription
        fields = [
            'id', 'job_title', 'job_purpose', 'business_function', 'department',
            'unit', 'job_function', 'position_group', 'grading_levels',
            'sections', 'required_skills_data', 'behavioral_competencies_data',
            'business_resources_with_items', 'access_rights_with_items',
            'company_benefits_with_items', 'selected_employee_ids',
            'assignments_created', 'total_assignments', 'requires_selection'
        ]
        read_only_fields = ['id']
    
    def get_assignments_created(self, obj):
        if hasattr(obj, '_assignments_created'):
            return [
                {
                    'id': str(a.id),
                    'employee_name': a.employee.full_name if a.employee else 'VACANT',
                    'employee_id': a.employee.employee_id if a.employee else None,
                    'is_vacancy': a.is_vacancy,
                    'status': a.status,
                    'reports_to': a.reports_to.full_name if a.reports_to else None
                }
                for a in obj._assignments_created
            ]
        return []
    
    def get_total_assignments(self, obj):
        if hasattr(obj, '_assignments_created'):
            return len(obj._assignments_created)
        return obj.assignments.count()
    
    def get_requires_selection(self, obj):
        return getattr(obj, '_requires_selection', False)
    
    def validate_grading_levels(self, value):
        if not value:
            raise serializers.ValidationError("At least one grading level required")
        normalized = list(set([gl.strip().upper() for gl in value if gl.strip()]))
        if not normalized:
            raise serializers.ValidationError("No valid grading levels")
        return normalized
    
    def validate_selected_employee_ids(self, value):
        if not value:
            return value
        
        valid_employee_ids = list(Employee.objects.filter(
            id__in=value, is_deleted=False
        ).values_list('id', flat=True))
        
        valid_vacancy_ids = list(VacantPosition.objects.filter(
            original_employee_pk__in=value, is_filled=False
        ).values_list('original_employee_pk', flat=True))
        
        valid_ids = valid_employee_ids + valid_vacancy_ids
        invalid_ids = [id for id in value if id not in valid_ids]
        
        if invalid_ids:
            raise serializers.ValidationError(
                f"Invalid position IDs: {invalid_ids}"
            )
        
        return value
    
    def create(self, validated_data):
        """Create job description and assign to employees"""
        
        # Extract nested data
        sections_data = validated_data.pop('sections', [])
        skills_data = validated_data.pop('required_skills_data', [])
        competencies_data = validated_data.pop('behavioral_competencies_data', [])
        grading_levels = validated_data.pop('grading_levels', [])
        selected_employee_ids = validated_data.pop('selected_employee_ids', [])
        business_resources_data = validated_data.pop('business_resources_with_items', [])
        access_rights_data = validated_data.pop('access_rights_with_items', [])
        company_benefits_data = validated_data.pop('company_benefits_with_items', [])
        
        with transaction.atomic():
            # Get eligible employees
            eligible_employees = JobDescription.get_eligible_employees_with_priority(
                job_title=validated_data['job_title'],
                business_function_id=validated_data['business_function'].id,
                department_id=validated_data['department'].id,
                unit_id=validated_data['unit'].id if validated_data.get('unit') else None,
                job_function_id=validated_data['job_function'].id,
                position_group_id=validated_data['position_group'].id,
                grading_levels=grading_levels
            )
            
            # Get eligible vacancies
            eligible_vacancies = self._get_eligible_vacancies(
                job_title=validated_data['job_title'],
                business_function_id=validated_data['business_function'].id,
                department_id=validated_data['department'].id,
                unit_id=validated_data['unit'].id if validated_data.get('unit') else None,
                job_function_id=validated_data['job_function'].id,
                position_group_id=validated_data['position_group'].id,
                grading_levels=grading_levels
            )
            
            total_eligible = eligible_employees.count() + eligible_vacancies.count()
            
            if total_eligible == 0:
                raise serializers.ValidationError({
                    'position_assignment': "No employees or vacant positions found matching criteria",
                    'criteria': {
                        'job_title': validated_data['job_title'],
                        'business_function': validated_data['business_function'].name,
                        'department': validated_data['department'].name,
                        'grading_levels': grading_levels
                    }
                })
            
            # Determine assignments
            employees_to_assign = []
            vacancies_to_assign = []
            
            if selected_employee_ids:
                # User selected specific positions
                employees_to_assign = list(eligible_employees.filter(id__in=selected_employee_ids))
                vacancies_to_assign = list(eligible_vacancies.filter(
                    original_employee_pk__in=selected_employee_ids
                ))
                
                if not employees_to_assign and not vacancies_to_assign:
                    raise serializers.ValidationError({
                        'selected_employee_ids': 'None of selected IDs match criteria'
                    })
            else:
                # Auto-assign all matching
                employees_to_assign = list(eligible_employees)
                vacancies_to_assign = list(eligible_vacancies)
            
            # Create job description
            validated_data['grading_levels'] = grading_levels
            if grading_levels:
                validated_data['grading_level'] = grading_levels[0]
            
            job_description = JobDescription.objects.create(**validated_data)
            
            # Create nested components
            self._create_nested_data(
                job_description, sections_data, skills_data, competencies_data,
                business_resources_data, access_rights_data, company_benefits_data
            )
            
            # Create assignments
            assignments_created = []
            
            for employee in employees_to_assign:
                assignment = JobDescriptionAssignment.objects.create(
                    job_description=job_description,
                    employee=employee,
                    is_vacancy=False,
                    reports_to=employee.line_manager
                )
                assignments_created.append(assignment)
              
            
            for vacancy in vacancies_to_assign:
                assignment = JobDescriptionAssignment.objects.create(
                    job_description=job_description,
                    employee=None,
                    is_vacancy=True,
                    vacancy_position=vacancy,
                    reports_to=vacancy.reporting_to
                )
                assignments_created.append(assignment)
          
            
            job_description._assignments_created = assignments_created
            
         
            
            return job_description
    
    def _get_eligible_vacancies(self, **kwargs):
        """Get eligible vacant positions"""
        queryset = VacantPosition.objects.filter(
            is_filled=False,
            is_deleted=False,
            include_in_headcount=True
        )
        
        if kwargs.get('job_title'):
            queryset = queryset.filter(job_title__iexact=kwargs['job_title'].strip())
        
        if kwargs.get('business_function_id'):
            queryset = queryset.filter(business_function_id=kwargs['business_function_id'])
        
        if kwargs.get('department_id'):
            queryset = queryset.filter(department_id=kwargs['department_id'])
        
        if kwargs.get('unit_id'):
            queryset = queryset.filter(unit_id=kwargs['unit_id'])
        
        if kwargs.get('job_function_id'):
            queryset = queryset.filter(job_function_id=kwargs['job_function_id'])
        
        if kwargs.get('position_group_id'):
            queryset = queryset.filter(position_group_id=kwargs['position_group_id'])
        
        grading_levels = kwargs.get('grading_levels', [])
        if grading_levels:
            if isinstance(grading_levels, str):
                grading_levels = [grading_levels]
            
            normalized = [normalize_grading_level(gl) for gl in grading_levels]
            matching_ids = []
            
            for v in queryset:
                v_norm = normalize_grading_level(v.grading_level or '')
                if v_norm in normalized:
                    matching_ids.append(v.id)
            
            queryset = queryset.filter(id__in=matching_ids)
        
        return queryset
    
    def _create_nested_data(self, job_description, sections_data, skills_data,
                           competencies_data, business_resources_data,
                           access_rights_data, company_benefits_data):
        """Create all nested data"""
        
        # Sections
        for section in sections_data:
            JobDescriptionSection.objects.create(
                job_description=job_description, **section
            )
        
        # Skills
        for skill in skills_data:
            JobDescriptionSkill.objects.create(
                job_description=job_description,
                skill_id=skill['skill_id']
            )
        
        # Competencies
        for comp in competencies_data:
            JobDescriptionBehavioralCompetency.objects.create(
                job_description=job_description,
                competency_id=comp['competency_id']
            )
        
        # Business resources
        for res_data in business_resources_data:
            jd_res = JobDescriptionBusinessResource.objects.create(
                job_description=job_description,
                resource_id=res_data.get('resource_id')
            )
            item_ids = res_data.get('item_ids', [])
            if item_ids:
                items = JobBusinessResourceItem.objects.filter(
                    id__in=item_ids, is_active=True
                )
                jd_res.specific_items.set(items)
        
        # Access rights
        for acc_data in access_rights_data:
            jd_acc = JobDescriptionAccessMatrix.objects.create(
                job_description=job_description,
                access_matrix_id=acc_data.get('access_matrix_id')
            )
            item_ids = acc_data.get('item_ids', [])
            if item_ids:
                items = AccessMatrixItem.objects.filter(
                    id__in=item_ids, is_active=True
                )
                jd_acc.specific_items.set(items)
        
        # Benefits
        for ben_data in company_benefits_data:
            jd_ben = JobDescriptionCompanyBenefit.objects.create(
                job_description=job_description,
                benefit_id=ben_data.get('benefit_id')
            )
            item_ids = ben_data.get('item_ids', [])
            if item_ids:
                items = CompanyBenefitItem.objects.filter(
                    id__in=item_ids, is_active=True
                )
                jd_ben.specific_items.set(items)
    
    def update(self, instance, validated_data):
        """Update job description (not assignments)"""
        
        sections_data = validated_data.pop('sections', None)
        skills_data = validated_data.pop('required_skills_data', None)
        competencies_data = validated_data.pop('behavioral_competencies_data', None)
        grading_levels = validated_data.pop('grading_levels', None)
        validated_data.pop('selected_employee_ids', None)
        business_resources_data = validated_data.pop('business_resources_with_items', None)
        access_rights_data = validated_data.pop('access_rights_with_items', None)
        company_benefits_data = validated_data.pop('company_benefits_with_items', None)
        
        with transaction.atomic():
            if grading_levels:
                validated_data['grading_levels'] = grading_levels
                validated_data['grading_level'] = grading_levels[0]
            
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            instance.updated_by = self.context['request'].user
            instance.save()
            
            # Update nested data if provided
            if sections_data is not None:
                instance.sections.all().delete()
                for section in sections_data:
                    JobDescriptionSection.objects.create(
                        job_description=instance, **section
                    )
            
            if skills_data is not None:
                instance.required_skills.all().delete()
                for skill in skills_data:
                    JobDescriptionSkill.objects.create(
                        job_description=instance,
                        skill_id=skill['skill_id']
                    )
            
            if competencies_data is not None:
                instance.behavioral_competencies.all().delete()
                for comp in competencies_data:
                    JobDescriptionBehavioralCompetency.objects.create(
                        job_description=instance,
                        competency_id=comp['competency_id']
                    )
            
            if business_resources_data is not None:
                instance.business_resources.all().delete()
                for res_data in business_resources_data:
                    jd_res = JobDescriptionBusinessResource.objects.create(
                        job_description=instance,
                        resource_id=res_data.get('resource_id')
                    )
                    item_ids = res_data.get('item_ids', [])
                    if item_ids:
                        items = JobBusinessResourceItem.objects.filter(
                            id__in=item_ids, is_active=True
                        )
                        jd_res.specific_items.set(items)
            
            if access_rights_data is not None:
                instance.access_rights.all().delete()
                for acc_data in access_rights_data:
                    jd_acc = JobDescriptionAccessMatrix.objects.create(
                        job_description=instance,
                        access_matrix_id=acc_data.get('access_matrix_id')
                    )
                    item_ids = acc_data.get('item_ids', [])
                    if item_ids:
                        items = AccessMatrixItem.objects.filter(
                            id__in=item_ids, is_active=True
                        )
                        jd_acc.specific_items.set(items)
            
            if company_benefits_data is not None:
                instance.company_benefits.all().delete()
                for ben_data in company_benefits_data:
                    jd_ben = JobDescriptionCompanyBenefit.objects.create(
                        job_description=instance,
                        benefit_id=ben_data.get('benefit_id')
                    )
                    item_ids = ben_data.get('item_ids', [])
                    if item_ids:
                        items = CompanyBenefitItem.objects.filter(
                            id__in=item_ids, is_active=True
                        )
                        jd_ben.specific_items.set(items)
            
            return instance
# api/job_description_serializers.py - PART 3: List and Detail serializers
# Bu hissəni Part 2-nin ardınca əlavə edin

# ==================== LIST SERIALIZER ====================

class JobDescriptionListSerializer(serializers.ModelSerializer):
    """List view serializer with assignment summary"""
    
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    job_function_name = serializers.CharField(source='job_function.name', read_only=True)
    position_group_name = serializers.CharField(source='position_group.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    # Assignment summary
    overall_status = serializers.ReadOnlyField()
    total_assignments = serializers.ReadOnlyField()
    employee_assignments_count = serializers.ReadOnlyField()
    vacancy_assignments_count = serializers.ReadOnlyField()
    approved_count = serializers.ReadOnlyField()
    pending_count = serializers.ReadOnlyField()
    
    # Quick assignment list
    assignments_preview = serializers.SerializerMethodField()
    assignments_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = JobDescription
        fields = [
            'id', 'job_title', 'job_purpose',
            'business_function_name', 'department_name', 'unit_name',
            'job_function_name', 'position_group_name', 'grading_levels',
            'overall_status', 'total_assignments', 'employee_assignments_count',
            'vacancy_assignments_count', 'approved_count', 'pending_count',
            'assignments_preview', 'assignments_summary',
            'version', 'is_active', 'created_at', 'created_by_name'
        ]
    
    def get_assignments_preview(self, obj):
        """Get first few assignments for preview"""
        assignments = obj.assignments.filter(is_active=True).select_related(
            'employee', 'reports_to', 'vacancy_position'
        )[:5]
        return [
            {
                'id': str(a.id),
                'name': a.get_display_name(),
                'status': a.status,
                'status_display': a.get_status_display_with_color(),
                'is_vacancy': a.is_vacancy,
                'reports_to': a.reports_to.full_name if a.reports_to else None
            }
            for a in assignments
        ]
    
    def get_assignments_summary(self, obj):
        return obj.get_assignments_summary()


# ==================== DETAIL SERIALIZER ====================

class JobDescriptionDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer with all nested data"""
    
    # Related object details
    business_function = BusinessFunctionBasicSerializer(read_only=True)
    department = DepartmentBasicSerializer(read_only=True)
    unit = UnitBasicSerializer(read_only=True)
    job_function = JobFunctionBasicSerializer(read_only=True)
    position_group = PositionGroupBasicSerializer(read_only=True)
    
    # All assignments
    assignments = JobDescriptionAssignmentDetailSerializer(many=True, read_only=True)
    assignments_summary = serializers.SerializerMethodField()
    
    # Nested data
    sections = JobDescriptionSectionSerializer(many=True, read_only=True)
    required_skills = JobDescriptionSkillSerializer(many=True, read_only=True)
    behavioral_competencies = JobDescriptionBehavioralCompetencySerializer(many=True, read_only=True)
    business_resources = JobDescriptionBusinessResourceDetailSerializer(many=True, read_only=True)
    access_rights = JobDescriptionAccessMatrixDetailSerializer(many=True, read_only=True)
    company_benefits = JobDescriptionCompanyBenefitDetailSerializer(many=True, read_only=True)
    
    # User details
    created_by_detail = UserBasicSerializer(source='created_by', read_only=True)
    updated_by_detail = UserBasicSerializer(source='updated_by', read_only=True)
    
    # Status and counts
    overall_status = serializers.ReadOnlyField()
    total_assignments = serializers.ReadOnlyField()
    employee_assignments_count = serializers.ReadOnlyField()
    vacancy_assignments_count = serializers.ReadOnlyField()
    approved_count = serializers.ReadOnlyField()
    pending_count = serializers.ReadOnlyField()
    
    # Permission checks
    can_edit = serializers.SerializerMethodField()
    can_add_assignments = serializers.SerializerMethodField()
    
    # Summary counts
    sections_count = serializers.SerializerMethodField()
    skills_count = serializers.SerializerMethodField()
    competencies_count = serializers.SerializerMethodField()
    resources_count = serializers.SerializerMethodField()
    
    class Meta:
        model = JobDescription
        fields = [
            # Basic info
            'id', 'job_title', 'job_purpose', 'grading_levels', 'grading_level',
            'version', 'is_active',
            
            # Organizational structure
            'business_function', 'department', 'unit', 'job_function', 'position_group',
            
            # All assignments with details
            'assignments', 'assignments_summary',
            
            # Status counts
            'overall_status', 'total_assignments', 'employee_assignments_count',
            'vacancy_assignments_count', 'approved_count', 'pending_count',
            
            # Nested data
            'sections', 'required_skills', 'behavioral_competencies',
            'business_resources', 'access_rights', 'company_benefits',
            
            # Summary counts
            'sections_count', 'skills_count', 'competencies_count', 'resources_count',
            
            # Permissions
            'can_edit', 'can_add_assignments',
            
            # User details
            'created_by_detail', 'updated_by_detail',
            
            # Metadata
            'created_at', 'updated_at'
        ]
    
    def get_assignments_summary(self, obj):
        return obj.get_assignments_summary()
    
    def get_can_edit(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.created_by == request.user or request.user.is_staff
    
    def get_can_add_assignments(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.created_by == request.user or request.user.is_staff
    
    def get_sections_count(self, obj):
        return obj.sections.count()
    
    def get_skills_count(self, obj):
        return obj.required_skills.count()
    
    def get_competencies_count(self, obj):
        return obj.behavioral_competencies.count()
    
    def get_resources_count(self, obj):
        return (
            obj.business_resources.count() +
            obj.access_rights.count() +
            obj.company_benefits.count()
        )


# ==================== APPROVAL SERIALIZERS ====================

class JobDescriptionApprovalSerializer(serializers.Serializer):
    """Serializer for approval actions"""
    
    comments = serializers.CharField(required=False, allow_blank=True)
    signature = serializers.FileField(required=False, allow_null=True)
    
    def validate_signature(self, value):
        if value:
            if value.size > 2 * 1024 * 1024:
                raise serializers.ValidationError("Signature file must be less than 2MB")
            
            allowed_types = ['image/png', 'image/jpeg', 'image/jpg', 'application/pdf']
            if value.content_type not in allowed_types:
                raise serializers.ValidationError(
                    "Invalid file type. Allowed: PNG, JPEG, PDF"
                )
        return value


class JobDescriptionRejectionSerializer(serializers.Serializer):
    """Serializer for rejection actions"""
    
    reason = serializers.CharField(required=True, min_length=10)


class JobDescriptionSubmissionSerializer(serializers.Serializer):
    """Serializer for submitting for approval"""
    
    submit_to_line_manager = serializers.BooleanField(default=True)
    comments = serializers.CharField(required=False, allow_blank=True)


# ==================== ADD ASSIGNMENT SERIALIZER ====================

class AddAssignmentSerializer(serializers.Serializer):
    """Serializer for adding new assignments to existing job description"""
    
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of employee IDs to add"
    )
    vacancy_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of vacancy IDs to add"
    )
    
    def validate(self, attrs):
        employee_ids = attrs.get('employee_ids', [])
        vacancy_ids = attrs.get('vacancy_ids', [])
        
        if not employee_ids and not vacancy_ids:
            raise serializers.ValidationError(
                "At least one employee_id or vacancy_id is required"
            )
        
        return attrs


# ==================== ASSIGNMENT MANAGEMENT SERIALIZERS ====================

class AssignmentStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating assignment status"""
    
    status = serializers.ChoiceField(
        choices=JobDescriptionAssignment.STATUS_CHOICES
    )
    comments = serializers.CharField(required=False, allow_blank=True)


class BulkAssignmentActionSerializer(serializers.Serializer):
    """Serializer for bulk actions on assignments"""
    
    assignment_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True,
        help_text="List of assignment UUIDs"
    )
    action = serializers.ChoiceField(
        choices=[
            ('submit', 'Submit for Approval'),
            ('approve_lm', 'Approve as Line Manager'),
            ('approve_emp', 'Approve as Employee'),
            ('reject', 'Reject'),
            ('revision', 'Request Revision')
        ]
    )
    comments = serializers.CharField(required=False, allow_blank=True)


class ReassignEmployeeSerializer(serializers.Serializer):
    """Serializer for reassigning an employee to a vacant assignment"""
    
    assignment_id = serializers.UUIDField(required=True)
    employee_id = serializers.IntegerField(required=True)
    
    def validate_employee_id(self, value):
        try:
            Employee.objects.get(id=value, is_deleted=False)
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Employee not found or inactive")
        return value            