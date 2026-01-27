# api/job_description_models.py - UPDATED: Multiple employee assignment per job description
# PART 1: Core models and JobDescriptionAssignment

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinLengthValidator
import uuid
import logging

logger = logging.getLogger(__name__)

def normalize_grading_level(grading_level):
    """
    Normalize grading level for comparison
    Removes underscores and spaces, converts to uppercase
    Examples: '_M' -> 'M', 'm' -> 'M', ' M ' -> 'M'
    """
    if not grading_level:
        return ""
    
    normalized = grading_level.strip().replace('_', '').replace(' ', '').upper()
    return normalized


class JobDescriptionAssignment(models.Model):
    """
    NEW: Individual assignment of a job description to an employee/vacancy
    Each assignment has its own approval workflow
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    job_description = models.ForeignKey(
        'JobDescription',
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    
    # Employee assignment (nullable for vacancies)
    employee = models.ForeignKey(
        'Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='job_description_assignments'
    )
    
    # Vacancy tracking
    is_vacancy = models.BooleanField(default=False)
    vacancy_position = models.ForeignKey(
        'VacantPosition',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='job_description_assignments'
    )
    
    # Reports to (auto-assigned from employee's line manager)
    reports_to = models.ForeignKey(
        'Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subordinate_assignments'
    )
    
    # Individual approval status for this assignment
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_LINE_MANAGER', 'Pending Line Manager Approval'),
        ('PENDING_EMPLOYEE', 'Pending Employee Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('REVISION_REQUIRED', 'Revision Required'),
    ]
    
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default='DRAFT'
    )
    
    # Approval workflow fields
    line_manager_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lm_approved_assignments'
    )
    line_manager_approved_at = models.DateTimeField(null=True, blank=True)
    line_manager_comments = models.TextField(blank=True)
    
    employee_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='emp_approved_assignments'
    )
    employee_approved_at = models.DateTimeField(null=True, blank=True)
    employee_comments = models.TextField(blank=True)
    
    # Digital signatures
    line_manager_signature = models.FileField(
        upload_to='job_descriptions/signatures/line_managers/',
        null=True,
        blank=True
    )
    employee_signature = models.FileField(
        upload_to='job_descriptions/signatures/employees/',
        null=True,
        blank=True
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    # Track when employee was removed
    employee_removed_at = models.DateTimeField(null=True, blank=True)
    employee_removed_reason = models.CharField(max_length=200, blank=True)
    
    class Meta:
        db_table = 'job_description_assignments'
        verbose_name = 'Job Description Assignment'
        verbose_name_plural = 'Job Description Assignments'
        ordering = ['-created_at']
    
    def __str__(self):
        if self.employee:
            return f"{self.job_description.job_title} - {self.employee.full_name} ({self.status})"
        elif self.is_vacancy:
            return f"{self.job_description.job_title} - VACANT ({self.status})"
        return f"{self.job_description.job_title} - Unassigned"
    
    def save(self, *args, **kwargs):
        """Auto-assign reports_to from employee's line_manager"""
        if self.employee and self.employee.line_manager:
            self.reports_to = self.employee.line_manager
        elif self.vacancy_position and self.vacancy_position.reporting_to:
            self.reports_to = self.vacancy_position.reporting_to
        
        if not self.employee and not self.is_vacancy:
            self.is_vacancy = True
        
        super().save(*args, **kwargs)
    
    def mark_as_vacant(self, reason="Employee removed"):
        """Mark assignment as vacant when employee is removed"""
        self.employee_removed_at = timezone.now()
        self.employee_removed_reason = reason
        self.is_vacancy = True
        self.employee = None
        self.save()
    
    def assign_new_employee(self, employee):
        """Assign a new employee to this vacant position"""
        self.employee = employee
        self.is_vacancy = False
        self.employee_removed_at = None
        self.employee_removed_reason = ''
        self.reports_to = employee.line_manager
        # Reset approval status for new employee
        self.status = 'DRAFT'
        self.line_manager_approved_by = None
        self.line_manager_approved_at = None
        self.employee_approved_by = None
        self.employee_approved_at = None
        self.save()
    
    def get_display_name(self):
        """Get display name for this assignment"""
        if self.employee:
            return self.employee.full_name
        elif self.is_vacancy:
            if self.vacancy_position:
                return f"VACANT - {self.vacancy_position.position_id}"
            return "VACANT POSITION"
        return "Unassigned"
    
    def can_be_approved_by_line_manager(self, user):
        """✅ SIMPLIFIED: Anyone can approve if status matches"""
        # Sadəcə status yoxla
        return self.status == 'PENDING_LINE_MANAGER'
    
    def can_be_approved_by_employee(self, user):
        """✅ SIMPLIFIED: Anyone can approve if status matches"""
        # Sadəcə status yoxla
        return self.status == 'PENDING_EMPLOYEE'
    def get_status_display_with_color(self):
        """Get status with color coding"""
        status_colors = {
            'DRAFT': '#6B7280',
            'PENDING_LINE_MANAGER': '#F59E0B',
            'PENDING_EMPLOYEE': '#3B82F6',
            'APPROVED': '#10B981',
            'REJECTED': '#EF4444',
            'REVISION_REQUIRED': '#8B5CF6',
        }
        return {
            'status': self.get_status_display(),
            'color': status_colors.get(self.status, '#6B7280')
        }
    
    def get_employee_info(self):
        """Get employee information"""
        if self.employee:
            return {
                'type': 'assigned',
                'id': self.employee.id,
                'name': self.employee.full_name,
                'phone': self.employee.phone,
                'employee_id': self.employee.employee_id,
                'email': getattr(self.employee, 'email', None)
            }
        elif self.is_vacancy and self.vacancy_position:
            return {
                'type': 'vacancy',
                'id': self.vacancy_position.id,
                'name': f"VACANT - {self.vacancy_position.position_id}",
                'phone': None,
                'employee_id': self.vacancy_position.position_id,
                'email': None
            }
        return None
    
    def get_manager_info(self):
        """Get manager information"""
        if self.reports_to:
            return {
                'id': self.reports_to.id,
                'name': self.reports_to.full_name,
                'job_title': self.reports_to.job_title,
                'employee_id': self.reports_to.employee_id
            }
        return None
    
    def validate_employee_assignment(self):
        """Validate employee against job description criteria"""
        if not self.employee:
            if self.is_vacancy:
                return True, "Vacancy position - no employee validation needed"
            return False, "No employee assigned"
        
        emp = self.employee
        jd = self.job_description
        errors = []
        
        # 1. JOB TITLE CHECK
        if jd.job_title:
            emp_title = emp.job_title.strip() if emp.job_title else ""
            jd_title = jd.job_title.strip()
            if emp_title.upper() != jd_title.upper():
                errors.append(f"Job Title: Required '{jd_title}', Employee has '{emp_title}'")
        
        # 2. BUSINESS FUNCTION CHECK
        if jd.business_function:
            if not emp.business_function or emp.business_function.id != jd.business_function.id:
                req_bf = jd.business_function.name
                emp_bf = emp.business_function.name if emp.business_function else "None"
                errors.append(f"Business Function: Required '{req_bf}', Employee has '{emp_bf}'")
        
        # 3. DEPARTMENT CHECK
        if jd.department:
            if not emp.department or emp.department.id != jd.department.id:
                req_dept = jd.department.name
                emp_dept = emp.department.name if emp.department else "None"
                errors.append(f"Department: Required '{req_dept}', Employee has '{emp_dept}'")
        
        # 4. UNIT CHECK (optional)
        if jd.unit:
            if not emp.unit or emp.unit.id != jd.unit.id:
                req_unit = jd.unit.name
                emp_unit = emp.unit.name if emp.unit else "None"
                errors.append(f"Unit: Required '{req_unit}', Employee has '{emp_unit}'")
        
        # 5. JOB FUNCTION CHECK
        if jd.job_function:
            if not emp.job_function or emp.job_function.id != jd.job_function.id:
                req_jf = jd.job_function.name
                emp_jf = emp.job_function.name if emp.job_function else "None"
                errors.append(f"Job Function: Required '{req_jf}', Employee has '{emp_jf}'")
        
        # 6. POSITION GROUP CHECK
        if jd.position_group:
            if not emp.position_group or emp.position_group.id != jd.position_group.id:
                req_pg = jd.position_group.name
                emp_pg = emp.position_group.name if emp.position_group else "None"
                errors.append(f"Position Group: Required '{req_pg}', Employee has '{emp_pg}'")
        
        # 7. GRADING LEVELS CHECK
        if jd.grading_levels and len(jd.grading_levels) > 0:
            emp_grade = emp.grading_level.strip() if emp.grading_level else ""
            emp_grade_normalized = normalize_grading_level(emp_grade)
            normalized_targets = [normalize_grading_level(level.strip()) for level in jd.grading_levels if level]
            
            if emp_grade_normalized not in normalized_targets:
                errors.append(
                    f"Grading Level: Required one of {jd.grading_levels}, "
                    f"Employee has '{emp_grade}'"
                )
        elif jd.grading_level and jd.grading_level.strip():
            emp_grade = emp.grading_level.strip() if emp.grading_level else ""
            jd_grade = jd.grading_level.strip()
            emp_grade_normalized = normalize_grading_level(emp_grade)
            jd_grade_normalized = normalize_grading_level(jd_grade)
            
            if emp_grade_normalized != jd_grade_normalized:
                errors.append(f"Grading Level: Required '{jd_grade}', Employee has '{emp_grade}'")
        
        if errors:
            return False, "; ".join(errors)
        
        return True, "Employee matches all criteria"
    
    def get_employee_matching_details(self):
        """Get detailed matching information"""
        if not self.employee:
            if self.is_vacancy:
                return {
                    'is_vacancy': True,
                    'vacancy_position_id': self.vacancy_position.position_id if self.vacancy_position else None,
                    'overall_match': True,
                    'message': 'Vacancy position'
                }
            return None
        
        emp = self.employee
        jd = self.job_description
        details = {
            'employee_info': {
                'id': emp.id,
                'name': emp.full_name,
                'employee_id': emp.employee_id
            },
            'matches': {},
            'overall_match': True,
            'mismatch_details': []
        }
        
        # JOB TITLE CHECK
        if jd.job_title:
            emp_title = emp.job_title.strip() if emp.job_title else ""
            jd_title = jd.job_title.strip()
            matches = (emp_title.upper() == jd_title.upper())
            
            details['matches']['job_title'] = {
                'required': jd_title,
                'employee_has': emp_title,
                'matches': matches
            }
            
            if not matches:
                details['overall_match'] = False
                details['mismatch_details'].append(f"Job Title: Required '{jd_title}', Employee has '{emp_title}'")
        
        # BUSINESS FUNCTION CHECK
        if jd.business_function:
            req_bf = jd.business_function.name
            emp_bf = emp.business_function.name if emp.business_function else "None"
            matches = (emp.business_function and emp.business_function.id == jd.business_function.id)
            
            details['matches']['business_function'] = {
                'required': req_bf,
                'employee_has': emp_bf,
                'matches': matches
            }
            
            if not matches:
                details['overall_match'] = False
                details['mismatch_details'].append(f"Business Function: Required '{req_bf}', Employee has '{emp_bf}'")
        
        # DEPARTMENT CHECK
        if jd.department:
            req_dept = jd.department.name
            emp_dept = emp.department.name if emp.department else "None"
            matches = (emp.department and emp.department.id == jd.department.id)
            
            details['matches']['department'] = {
                'required': req_dept,
                'employee_has': emp_dept,
                'matches': matches
            }
            
            if not matches:
                details['overall_match'] = False
                details['mismatch_details'].append(f"Department: Required '{req_dept}', Employee has '{emp_dept}'")
        
        # UNIT CHECK
        if jd.unit:
            req_unit = jd.unit.name
            emp_unit = emp.unit.name if emp.unit else "None"
            matches = (emp.unit and emp.unit.id == jd.unit.id)
            
            details['matches']['unit'] = {
                'required': req_unit,
                'employee_has': emp_unit,
                'matches': matches
            }
            
            if not matches:
                details['overall_match'] = False
                details['mismatch_details'].append(f"Unit: Required '{req_unit}', Employee has '{emp_unit}'")
        
        # JOB FUNCTION CHECK
        if jd.job_function:
            req_jf = jd.job_function.name
            emp_jf = emp.job_function.name if emp.job_function else "None"
            matches = (emp.job_function and emp.job_function.id == jd.job_function.id)
            
            details['matches']['job_function'] = {
                'required': req_jf,
                'employee_has': emp_jf,
                'matches': matches
            }
            
            if not matches:
                details['overall_match'] = False
                details['mismatch_details'].append(f"Job Function: Required '{req_jf}', Employee has '{emp_jf}'")
        
        # POSITION GROUP CHECK
        if jd.position_group:
            req_pg = jd.position_group.name
            emp_pg = emp.position_group.name if emp.position_group else "None"
            matches = (emp.position_group and emp.position_group.id == jd.position_group.id)
            
            details['matches']['position_group'] = {
                'required': req_pg,
                'employee_has': emp_pg,
                'matches': matches
            }
            
            if not matches:
                details['overall_match'] = False
                details['mismatch_details'].append(f"Position Group: Required '{req_pg}', Employee has '{emp_pg}'")
        
        # GRADING LEVELS CHECK
        if jd.grading_levels and len(jd.grading_levels) > 0:
            emp_grade = emp.grading_level.strip() if emp.grading_level else ""
            emp_grade_normalized = normalize_grading_level(emp_grade)
            normalized_targets = [normalize_grading_level(level.strip()) for level in jd.grading_levels if level]
            matches = emp_grade_normalized in normalized_targets
            
            details['matches']['grading_levels'] = {
                'required': jd.grading_levels,
                'required_normalized': normalized_targets,
                'employee_has': emp_grade,
                'employee_normalized': emp_grade_normalized,
                'matches': matches,
                'match_type': 'multiple_options'
            }
            
            if not matches:
                details['overall_match'] = False
                details['mismatch_details'].append(
                    f"Grading Levels: Required one of {jd.grading_levels}, Employee has '{emp_grade}'"
                )
        elif jd.grading_level and jd.grading_level.strip():
            emp_grade = emp.grading_level.strip() if emp.grading_level else ""
            jd_grade = jd.grading_level.strip()
            emp_grade_normalized = normalize_grading_level(emp_grade)
            jd_grade_normalized = normalize_grading_level(jd_grade)
            matches = (emp_grade_normalized == jd_grade_normalized)
            
            details['matches']['grading_level'] = {
                'required': jd_grade,
                'employee_has': emp_grade,
                'matches': matches,
                'match_type': 'single_value'
            }
            
            if not matches:
                details['overall_match'] = False
                details['mismatch_details'].append(
                    f"Grading Level: Required '{jd_grade}', Employee has '{emp_grade}'"
                )
        
        return details
    # api/job_description_models.py - PART 2: JobDescription model
# Bu hissəni Part 1-in ardınca əlavə edin

class JobDescription(models.Model):
    """UPDATED: Job Description - now supports multiple employee assignments"""
    
    # Primary fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_title = models.CharField(max_length=200, verbose_name="Job Title")
    
    # Hierarchical and organizational data
    business_function = models.ForeignKey(
        'BusinessFunction',
        on_delete=models.CASCADE,
        verbose_name="Business Function"
    )
    department = models.ForeignKey(
        'Department',
        on_delete=models.CASCADE,
        verbose_name="Department"
    )
    unit = models.ForeignKey(
        'Unit',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Unit"
    )
    job_function = models.ForeignKey(
        'JobFunction',
        on_delete=models.CASCADE,
        verbose_name="Job Function"
    )
    position_group = models.ForeignKey(
        'PositionGroup',
        on_delete=models.CASCADE,
        verbose_name="Position Group/Hierarchy"
    )
    grading_levels = models.JSONField(
        default=list,
        help_text="List of grading levels (e.g., ['M', 'N', 'O'])"
    )
    
    # Backward compatibility
    grading_level = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="DEPRECATED: Use grading_levels instead."
    )
    
    # Job details
    job_purpose = models.TextField(
        validators=[MinLengthValidator(5)],
        help_text="Main purpose and objectives of the role"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_job_descriptions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_job_descriptions'
    )
    
    # Version control
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'job_descriptions'
        verbose_name = 'Job Description'
        verbose_name_plural = 'Job Descriptions'
        ordering = ['-created_at']
    
    def __str__(self):
        assignment_count = self.assignments.count()
        return f"{self.job_title} ({assignment_count} assignments)"
    
    # Aggregated status properties
    @property
    def overall_status(self):
        """Get overall status based on all assignments"""
        assignments = self.assignments.filter(is_active=True)
        if not assignments.exists():
            return 'NO_ASSIGNMENTS'
        
        statuses = list(assignments.values_list('status', flat=True))
        
        if all(s == 'APPROVED' for s in statuses):
            return 'ALL_APPROVED'
        elif all(s == 'DRAFT' for s in statuses):
            return 'ALL_DRAFT'
        elif any(s in ['PENDING_LINE_MANAGER', 'PENDING_EMPLOYEE'] for s in statuses):
            return 'PENDING_APPROVALS'
        elif any(s == 'REJECTED' for s in statuses):
            return 'HAS_REJECTIONS'
        else:
            return 'MIXED'
    
    @property
    def total_assignments(self):
        return self.assignments.filter(is_active=True).count()
    
    @property
    def employee_assignments_count(self):
        return self.assignments.filter(is_active=True, is_vacancy=False, employee__isnull=False).count()
    
    @property
    def vacancy_assignments_count(self):
        return self.assignments.filter(is_active=True, is_vacancy=True).count()
    
    @property
    def approved_count(self):
        return self.assignments.filter(is_active=True, status='APPROVED').count()
    
    @property
    def pending_count(self):
        return self.assignments.filter(
            is_active=True,
            status__in=['PENDING_LINE_MANAGER', 'PENDING_EMPLOYEE']
        ).count()
    
    def get_all_assigned_employees(self):
        """Get all employees assigned to this job description"""
        return self.assignments.filter(
            is_active=True,
            is_vacancy=False,
            employee__isnull=False
        ).select_related('employee', 'reports_to')
    
    def get_all_vacancies(self):
        """Get all vacant assignments"""
        return self.assignments.filter(
            is_active=True,
            is_vacancy=True
        ).select_related('vacancy_position')
    
    def get_assignments_summary(self):
        """Get summary of all assignments"""
        assignments = self.assignments.filter(is_active=True)
        return {
            'total': assignments.count(),
            'employees': assignments.filter(is_vacancy=False, employee__isnull=False).count(),
            'vacancies': assignments.filter(is_vacancy=True).count(),
            'approved': assignments.filter(status='APPROVED').count(),
            'pending': assignments.filter(status__in=['PENDING_LINE_MANAGER', 'PENDING_EMPLOYEE']).count(),
            'draft': assignments.filter(status='DRAFT').count(),
            'rejected': assignments.filter(status='REJECTED').count()
        }
    
    @classmethod
    def get_eligible_employees_with_priority(cls, job_title=None, business_function_id=None,
                                             department_id=None, unit_id=None, job_function_id=None,
                                             position_group_id=None, grading_levels=None):
        """Get employees matching ALL criteria with detailed logging"""
        from .models import Employee
        
        
        
        queryset = Employee.objects.filter(
            is_deleted=False
        ).select_related(
            'business_function', 'department', 'unit', 'job_function',
            'position_group', 'line_manager'
        )
        
        initial_count = queryset.count()
      
        
        # 1. JOB TITLE FILTER
        if job_title:
            job_title_clean = job_title.strip()
            before = queryset.count()
            queryset = queryset.filter(job_title__iexact=job_title_clean)
            after = queryset.count()
            
            
            
            if after == 0:
               
                all_titles = list(Employee.objects.filter(
                    is_deleted=False
                ).values_list('job_title', flat=True).distinct()[:30])
                logger.error(f"  Available job titles: {all_titles}")
                return Employee.objects.none()
          
        
        # 2. BUSINESS FUNCTION FILTER
        if business_function_id:
            before = queryset.count()
            queryset = queryset.filter(business_function_id=business_function_id)
            after = queryset.count()
            
        
        # 3. DEPARTMENT FILTER
        if department_id:
            before = queryset.count()
            try:
                from .models import Department
                target_dept = Department.objects.get(id=department_id)
                dept_name = target_dept.name
                queryset = queryset.filter(department__name__iexact=dept_name)
            except:
                queryset = queryset.filter(department_id=department_id)
            after = queryset.count()
            
        
        # 4. UNIT FILTER
        if unit_id:
            before = queryset.count()
            queryset = queryset.filter(unit_id=unit_id)
            after = queryset.count()
            
        
        # 5. JOB FUNCTION FILTER
        if job_function_id:
            before = queryset.count()
            queryset = queryset.filter(job_function_id=job_function_id)
            after = queryset.count()
            
        
        # 6. POSITION GROUP FILTER
        if position_group_id:
            before = queryset.count()
            queryset = queryset.filter(position_group_id=position_group_id)
            after = queryset.count()
            
        
        # 7. GRADING LEVEL FILTER
        if grading_levels:
            if isinstance(grading_levels, str):
                grading_levels = [grading_levels]
            
            normalized_targets = [normalize_grading_level(gl.strip()) for gl in grading_levels]
            
            
            
            all_remaining = list(queryset)
            matching_ids = []
            
            for emp in all_remaining:
                emp_grade = emp.grading_level.strip() if emp.grading_level else ""
                emp_normalized = normalize_grading_level(emp_grade)
                
                if emp_normalized in normalized_targets:
                    matching_ids.append(emp.id)
            
            before = queryset.count()
            queryset = queryset.filter(id__in=matching_ids)
            after = queryset.count()
            
        
        final_count = queryset.count()
       
        
        
        return queryset.order_by('line_manager_id', 'employee_id')
    
    @classmethod
    def get_eligible_employees(cls, job_title=None, business_function=None, department=None,
                               unit=None, job_function=None, position_group=None, grading_levels=None):
        """Wrapper method for backward compatibility"""
        job_title_str = job_title
        business_function_id = business_function.id if hasattr(business_function, 'id') else business_function
        department_id = department.id if hasattr(department, 'id') else department
        unit_id = unit.id if hasattr(unit, 'id') else unit
        job_function_id = job_function.id if hasattr(job_function, 'id') else job_function
        position_group_id = position_group.id if hasattr(position_group, 'id') else position_group
        
        return cls.get_eligible_employees_with_priority(
            job_title=job_title_str,
            business_function_id=business_function_id,
            department_id=department_id,
            unit_id=unit_id,
            job_function_id=job_function_id,
            position_group_id=position_group_id,
            grading_levels=grading_levels
        )


class JobDescriptionSection(models.Model):
    """Flexible sections for job descriptions"""
    
    SECTION_TYPES = [
        ('CRITICAL_DUTIES', 'Critical Duties'),
        ('MAIN_KPIS', 'Main KPIs'),
        ('JOB_DUTIES', 'Job Duties'),
        ('REQUIREMENTS', 'Requirements'),
        ('CUSTOM', 'Custom Section'),
    ]
    
    job_description = models.ForeignKey(
        JobDescription,
        on_delete=models.CASCADE,
        related_name='sections'
    )
    section_type = models.CharField(max_length=20, choices=SECTION_TYPES)
    title = models.CharField(max_length=200)
    content = models.TextField()
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'job_description_sections'
        ordering = ['order', 'id']
        unique_together = ['job_description', 'section_type', 'order']
    
    def __str__(self):
        return f"{self.job_description.job_title} - {self.get_section_type_display()}"


class JobDescriptionSkill(models.Model):
    """Core skills for job descriptions"""

    job_description = models.ForeignKey(
        JobDescription,
        on_delete=models.CASCADE,
        related_name='required_skills'
    )
    skill = models.ForeignKey(
        'Skill',
        on_delete=models.CASCADE,
        help_text="Skill from competency system"
    )

    class Meta:
        db_table = 'job_description_skills'
        unique_together = ['job_description', 'skill']
    
    def __str__(self):
        return f"{self.skill.name}"


class JobDescriptionBehavioralCompetency(models.Model):
    """Behavioral competencies for job descriptions"""

    job_description = models.ForeignKey(
        JobDescription,
        on_delete=models.CASCADE,
        related_name='behavioral_competencies'
    )
    competency = models.ForeignKey(
        'BehavioralCompetency',
        on_delete=models.CASCADE,
        help_text="Competency from competency system"
    )

    class Meta:
        db_table = 'job_description_behavioral_competencies'
        unique_together = ['job_description', 'competency']
    
    def __str__(self):
        return f"{self.competency.name}"
    
# api/job_description_models.py - PART 3: Resource models
# Bu hissəni Part 2-nin ardınca əlavə edin

class JobBusinessResource(models.Model):
    """Business resources (parent) - e.g., Laptop, Phone, Software"""
    
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'job_business_resources'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class JobBusinessResourceItem(models.Model):
    """Nested items for business resources - e.g., Dell XPS, MacBook Pro"""
    
    resource = models.ForeignKey(
        JobBusinessResource,
        on_delete=models.CASCADE,
        related_name='items',
        help_text="Parent resource category"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'job_business_resource_items'
        ordering = ['resource', 'name']
        unique_together = ['resource', 'name']
    
    def __str__(self):
        return f"{self.resource.name} - {self.name}"


class AccessMatrix(models.Model):
    """Access rights categories (parent) - e.g., Database Access, Admin Panel"""
    
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'access_matrix'
        verbose_name_plural = 'Access Matrix'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class AccessMatrixItem(models.Model):
    """Nested items for access rights - e.g., PostgreSQL Read, AWS S3 Write"""
    
    access_matrix = models.ForeignKey(
        AccessMatrix,
        on_delete=models.CASCADE,
        related_name='items',
        help_text="Parent access category"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'access_matrix_items'
        ordering = ['access_matrix', 'name']
        unique_together = ['access_matrix', 'name']
    
    def __str__(self):
        return f"{self.access_matrix.name} - {self.name}"


class CompanyBenefit(models.Model):
    """Company benefits categories (parent) - e.g., Health Insurance, Leave Policy"""
    
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'company_benefits'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class CompanyBenefitItem(models.Model):
    """Nested items for benefits - e.g., Annual Leave: 21 days"""
    
    benefit = models.ForeignKey(
        CompanyBenefit,
        on_delete=models.CASCADE,
        related_name='items',
        help_text="Parent benefit category"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    value = models.CharField(
        max_length=100,
        blank=True,
        help_text="Benefit value (e.g., '21 days', '100%')"
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional details"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'company_benefit_items'
        ordering = ['benefit', 'name']
        unique_together = ['benefit', 'name']
    
    def __str__(self):
        value_str = f" ({self.value})" if self.value else ""
        return f"{self.benefit.name} - {self.name}{value_str}"


class JobDescriptionBusinessResource(models.Model):
    """Link job descriptions to business resources"""
    
    job_description = models.ForeignKey(
        'JobDescription',
        on_delete=models.CASCADE,
        related_name='business_resources'
    )
    resource = models.ForeignKey(JobBusinessResource, on_delete=models.CASCADE)
    specific_items = models.ManyToManyField(
        JobBusinessResourceItem,
        blank=True,
        related_name='job_descriptions',
        help_text="Specific items required (leave empty for any)"
    )
    
    class Meta:
        db_table = 'job_description_business_resources'
        unique_together = ['job_description', 'resource']


class JobDescriptionAccessMatrix(models.Model):
    """Link job descriptions to access rights"""
    
    job_description = models.ForeignKey(
        'JobDescription',
        on_delete=models.CASCADE,
        related_name='access_rights'
    )
    access_matrix = models.ForeignKey(AccessMatrix, on_delete=models.CASCADE)
    specific_items = models.ManyToManyField(
        AccessMatrixItem,
        blank=True,
        related_name='job_descriptions',
        help_text="Specific access rights required"
    )
    
    class Meta:
        db_table = 'job_description_access_matrix'
        unique_together = ['job_description', 'access_matrix']


class JobDescriptionCompanyBenefit(models.Model):
    """Link job descriptions to company benefits"""
    
    job_description = models.ForeignKey(
        'JobDescription',
        on_delete=models.CASCADE,
        related_name='company_benefits'
    )
    benefit = models.ForeignKey(CompanyBenefit, on_delete=models.CASCADE)
    specific_items = models.ManyToManyField(
        CompanyBenefitItem,
        blank=True,
        related_name='job_descriptions',
        help_text="Specific benefit details"
    )
    
    class Meta:
        db_table = 'job_description_company_benefits'
        unique_together = ['job_description', 'benefit']    