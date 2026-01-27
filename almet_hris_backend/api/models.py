# api/models.py - ENHANCED: Complete Employee Management System with Advanced Contract Status Management

from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date, timedelta
from django.db import transaction
import os
import logging
from django.db.models import Q

import traceback
from datetime import datetime, timedelta
try:
    from dateutil.relativedelta import relativedelta
except ImportError:
    # Fallback if dateutil is not available
    relativedelta = None

logger = logging.getLogger(__name__)
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class UserGraphToken(models.Model):
    """Store Microsoft Graph access tokens for users"""
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        related_name='graph_token'
    )
    access_token = models.TextField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_graph_tokens'
        verbose_name = 'User Graph Token'
        verbose_name_plural = 'User Graph Tokens'
    
    def __str__(self):
        return f"Graph Token for {self.user.username}"
    
    def is_expired(self):
        """Check if token is expired"""
        return timezone.now() >= self.expires_at
    
    def is_valid(self):
        """Check if token is still valid (with 5 min buffer)"""
        buffer = timedelta(minutes=5)
        return timezone.now() < (self.expires_at - buffer)
    
    @classmethod
    def store_token(cls, user, access_token, expires_in=3600):
        """
        Store or update Graph token for user
        
        Args:
            user: Django User object
            access_token: Microsoft Graph access token
            expires_in: Token lifetime in seconds (default: 3600 = 1 hour)
        """
        expires_at = timezone.now() + timedelta(seconds=expires_in)
        
        token, created = cls.objects.update_or_create(
            user=user,
            defaults={
                'access_token': access_token,
                'expires_at': expires_at
            }
        )
        
        return token
    
    @classmethod
    def get_valid_token(cls, user):
        """
        Get valid Graph token for user
        
        Returns:
            str: Access token if valid, None otherwise
        """
        try:
            token = cls.objects.get(user=user)
            if token.is_valid():
                return token.access_token
            else:
                return None
        except cls.DoesNotExist:
            return None
class MicrosoftUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='microsoft_user')
    microsoft_id = models.CharField(max_length=255, unique=True)
    access_token = models.TextField(blank=True, null=True)
    refresh_token = models.TextField(blank=True, null=True)
    token_expires = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.microsoft_id}"

    class Meta:
        verbose_name = "Microsoft User"
        verbose_name_plural = "Microsoft Users"

class ActiveManager(models.Manager):
    """Manager that excludes soft-deleted objects"""
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class AllObjectsManager(models.Manager):
    """Manager that includes soft-deleted objects"""
    def get_queryset(self):
        return super().get_queryset()

class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_%(class)ss')
    
    objects = ActiveManager()  # Default manager excludes deleted
    all_objects = AllObjectsManager()  # Manager that includes deleted
    
    class Meta:
        abstract = True
    
    def soft_delete(self, user=None):
        """Soft delete the object"""
        if isinstance(self, Employee) and not self.end_date:
           self.end_date = timezone.now().date()
           
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save()
    
    def restore(self):
        """Restore a soft-deleted object"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save()

class BusinessFunction(SoftDeleteModel):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
   
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

    class Meta:
        ordering = ['code']

class Department(SoftDeleteModel):
    name = models.CharField(max_length=100)
    business_function = models.ForeignKey(BusinessFunction, on_delete=models.CASCADE, related_name='departments')

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.business_function.code} - {self.name}"

    class Meta:
        ordering = ['business_function__code']
        unique_together = ['business_function', 'name']

class Unit(SoftDeleteModel):
    name = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='units')
 
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.department.business_function.code} - {self.name}"

    class Meta:
        ordering = ['department__business_function__code']
        unique_together = ['department', 'name']

class JobFunction(SoftDeleteModel):
    name = models.CharField(max_length=100, unique=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class PositionGroup(SoftDeleteModel):
    POSITION_LEVELS = [
        ('VC', 'Vice Chairman'),
        ('Chairman', 'Chairman'),
        ('DIRECTOR', 'Director'),
        ('MANAGER', 'Manager'),
        ('C-SUITE EXECUTIVE', 'C-Suite Executive'),
        
        ('HEAD OF DEPARTMENT', 'Head of Department'),
        ('SENIOR SPECIALIST', 'Senior Specialist'),
        ('SPECIALIST', 'Specialist'),
        ('JUNIOR SPECIALIST', 'Junior Specialist'),
        ('BLUE COLLAR', 'Blue Collar'),
    ]
    
    # Grading shorthand mappings for level display
    GRADING_SHORTCUTS = {
        'VC': 'VC',
        'DIRECTOR': 'DIR',
        'MANAGER': 'MGR',
        'HEAD OF DEPARTMENT': 'HOD',
        'SENIOR SPECIALIST': 'SS',
        'SPECIALIST': 'SP',
        'JUNIOR SPECIALIST': 'JS',
        'BLUE COLLAR': 'BC',
        'C-SUITE EXECUTIVE': 'C-SE',
    }
    
    name = models.CharField(max_length=50, choices=POSITION_LEVELS, unique=True)
    hierarchy_level = models.IntegerField(unique=True)
    grading_shorthand = models.CharField(max_length=10, editable=False)  # Auto-generated
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-generate grading shorthand
        self.grading_shorthand = self.GRADING_SHORTCUTS.get(self.name, self.name[:3].upper())
        super().save(*args, **kwargs)

    def get_grading_levels(self):
        """Returns grading levels with shortcuts for this position"""
        return [
            {'code': f"{self.grading_shorthand}_LD", 'display': f"{self.grading_shorthand}-LD", 'full_name': 'Lower Decile'},
            {'code': f"{self.grading_shorthand}_LQ", 'display': f"{self.grading_shorthand}-LQ", 'full_name': 'Lower Quartile'},
            {'code': f"{self.grading_shorthand}_M", 'display': f"{self.grading_shorthand}-M", 'full_name': 'Median'},
            {'code': f"{self.grading_shorthand}_UQ", 'display': f"{self.grading_shorthand}-UQ", 'full_name': 'Upper Quartile'},
            {'code': f"{self.grading_shorthand}_UD", 'display': f"{self.grading_shorthand}-UD", 'full_name': 'Upper Decile'},
        ]

    def __str__(self):
        return self.get_name_display()

    class Meta:
        ordering = ['hierarchy_level']


class JobTitle(SoftDeleteModel):
    """Job Title model for standardized job titles"""
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, help_text="Description of this job title")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']
        verbose_name = "Job Title"
        verbose_name_plural = "Job Titles"
class EmployeeTag(SoftDeleteModel):
  
    
    name = models.CharField(max_length=50, unique=True)

    color = models.CharField(max_length=7, default='#6B7280')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = [ 'name']

class ContractTypeConfig(SoftDeleteModel):
    """Configuration for different contract types and their status transitions"""
    
    contract_type = models.CharField(
        max_length=50, 
        unique=True, 
        help_text="Contract type identifier (e.g., 3_MONTHS, 5_MONTHS, 18_MONTHS, etc.)"
    )
    display_name = models.CharField(max_length=100)
    
    # Status Configuration

    probation_days = models.IntegerField(default=0, help_text="Days for probation status after onboarding")
    
    # Auto-transition settings
    enable_auto_transitions = models.BooleanField(default=True, help_text="Enable automatic status transitions")
    transition_to_inactive_on_end = models.BooleanField(default=True, help_text="Auto transition to inactive when contract ends")
    
    # Notification settings
    notify_days_before_end = models.IntegerField(default=30, help_text="Days before contract end to send notifications")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def get_total_days_until_active(self):
        """Get total days until employee becomes active"""
        return  self.probation_days
    
    @classmethod
    def get_contract_choices(cls):
        """Get dynamic contract choices from database"""
        active_configs = cls.objects.filter(is_active=True)
        return [(config.contract_type, config.display_name) for config in active_configs]
    

    def __str__(self):
        return self.display_name
    
    class Meta:
        ordering = ['contract_type']
        verbose_name = "Contract Type Configuration"
        verbose_name_plural = "Contract Type Configurations"

class EmployeeStatus(SoftDeleteModel):
    STATUS_TYPES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('PROBATION', 'Probation'),  # ✅ ONBOARDING silindi
        ('VACANT', 'Vacant Position'),
    ]
    
    STATUS_COLOR_HIERARCHY = {
        'ACTIVE': '#10B981',      # Green
        'PROBATION': '#F59E0B',   # Yellow
        'VACANT': '#F97316',      # Orange
        'INACTIVE': '#9CA3AF',    # Gray
    }
    # Basic Information
    name = models.CharField(max_length=50, unique=True)
    status_type = models.CharField(max_length=20, choices=STATUS_TYPES, default='ACTIVE')
    color = models.CharField(max_length=7, default='#6B7280')
    description = models.TextField(blank=True, help_text="Description of this status")
    
    # Display Order
    order = models.IntegerField(default=0, help_text="Display order for status")
    
    # Behavior Settings
    affects_headcount = models.BooleanField(default=True, help_text="Whether this status counts toward active headcount")
    allows_org_chart = models.BooleanField(default=True, help_text="Whether employees with this status appear in org chart")
    
    # Auto Transition Settings
    auto_transition_enabled = models.BooleanField(default=False, help_text="Enable automatic status transitions")
    auto_transition_days = models.IntegerField(null=True, blank=True, help_text="Days after which to auto-transition")
    auto_transition_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, 
                                         related_name='transitions_from', help_text="Status to transition to")
    is_transitional = models.BooleanField(default=False, help_text="Whether this is a transitional status")
    transition_priority = models.IntegerField(default=0, null=True, blank=True, help_text="Priority for transitions")
    
    # Notification Settings
    send_notifications = models.BooleanField(default=False, help_text="Send notifications for this status")
    notification_template = models.TextField(default='', blank=True, help_text="Notification template")
    
    # System Settings
    is_system_status = models.BooleanField(default=False, help_text="Whether this is a system-managed status")
    is_default_for_new_employees = models.BooleanField(default=False, help_text="Use as default for new employees")
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-assign color based on status type if not explicitly set
        if not self.color or self.color == '#6B7280':
            self.color = self.STATUS_COLOR_HIERARCHY.get(self.status_type, '#6B7280')
        
        # Auto-assign order based on status type if not set
        if not self.order:
            status_order_mapping = {
             
                'PROBATION': 1,
                'ACTIVE': 2,
                'INACTIVE': 3,      
                'VACANT': 4,
            }
            self.order = status_order_mapping.get(self.status_type, 99)
        
        # Auto-set transitional flag for certain status types
        if self.status_type in [ 'PROBATION']:
            self.is_transitional = True
        
        super().save(*args, **kwargs)


    def __str__(self):
        return self.name

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Employee Status"
        verbose_name_plural = "Employee Statuses"

class VacantPosition(SoftDeleteModel):
    """Enhanced Vacant Position with business function based position_id generation"""
    
    # Auto-generated position ID (business function based)
    position_id = models.CharField(
        max_length=50, 
        unique=True, 
        help_text="Auto-generated position ID based on business function code",
        editable=False  # Make it read-only like employee_id
    )
    original_employee_pk = models.IntegerField(
        null=True,
        blank=True,
        help_text="Original employee database ID (pk) that created this vacancy"
    )
    # Basic Information - REQUIRED FIELDS
    job_title = models.CharField(max_length=200, help_text="Job title for the vacant position")
    
    # REQUIRED: Organizational Structure
    business_function = models.ForeignKey(
        BusinessFunction, 
        on_delete=models.PROTECT,
        help_text="Business function (required for position_id generation)"
    )
    department = models.ForeignKey(
        Department, 
        on_delete=models.PROTECT,
        help_text="Department (required)"
    )
    unit = models.ForeignKey(
        Unit, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True,
        help_text="Unit (optional)"
    )
    job_function = models.ForeignKey(
        JobFunction, 
        on_delete=models.PROTECT,
        help_text="Job function (required)"
    )
    position_group = models.ForeignKey(
        PositionGroup, 
        on_delete=models.PROTECT,
        help_text="Position group (required)"
    )
    
    # REQUIRED: Grading and Position Details
    grading_level = models.CharField(
        max_length=15, 
        help_text="Grading level (e.g., MGR_UQ)"
    )
    
    # REQUIRED: Management
    reporting_to = models.ForeignKey(
        'Employee', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='managed_vacant_positions',
        help_text="Line manager for this position"
    )
    
    # REQUIRED: Configuration
    is_visible_in_org_chart = models.BooleanField(
        default=True,
        help_text="Show this position in organizational chart"
    )
    include_in_headcount = models.BooleanField(
        default=True,
        help_text="Include this position in headcount calculations"
    )
    
    # REQUIRED: Additional Information
    notes = models.TextField(
        blank=True, 
        help_text="Additional notes about this position"
    )
    
    # Auto-generated display name
    display_name = models.CharField(max_length=300, editable=False, default='')
    
    # Status tracking
    is_filled = models.BooleanField(default=False)
    filled_by_employee = models.ForeignKey(
        'Employee', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='filled_vacancy_position'
    )
    filled_date = models.DateField(null=True, blank=True)
    
    # Status integration
    vacancy_status = models.ForeignKey(
        EmployeeStatus, 
        on_delete=models.PROTECT,
        related_name='vacant_positions_with_status'
    )
    
    # Management
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def generate_position_id(self):
        """Generate position ID based on business function code - same format as employee_id"""
        if not self.business_function:
            raise ValueError("Business function is required to generate position ID")
        
        business_code = self.business_function.code
        
        with transaction.atomic():
            # Get ALL existing position IDs for this business function (including filled and deleted)
            existing_ids = set()
            
            # Get from VacantPosition
            vacancy_ids = VacantPosition.all_objects.filter(
                position_id__startswith=business_code,
                position_id__regex=f'^{business_code}[0-9]+$'  # Only numeric suffixes
            ).values_list('position_id', flat=True)
            existing_ids.update(vacancy_ids)
            
            # IMPORTANT: Also check Employee IDs to avoid conflicts
            employee_ids = Employee.all_objects.filter(
                employee_id__startswith=business_code,
                employee_id__regex=f'^{business_code}[0-9]+$'  # Only numeric suffixes
            ).values_list('employee_id', flat=True)
            existing_ids.update(employee_ids)
            
            # Extract numbers from existing IDs
            used_numbers = set()
            for pos_id in existing_ids:
                try:
                    number_part = pos_id[len(business_code):]
                    if number_part.isdigit():
                        used_numbers.add(int(number_part))
                except (ValueError, IndexError):
                    continue
            
            # Find the next available number
            next_number = 1
            while next_number in used_numbers:
                next_number += 1
            
            new_position_id = f"{business_code}{next_number}"
            
            # Final safety check against both vacancy and employee IDs
            while (VacantPosition.all_objects.filter(position_id=new_position_id).exists() or 
                   Employee.all_objects.filter(employee_id=new_position_id).exists()):
                next_number += 1
                new_position_id = f"{business_code}{next_number}"
            
            return new_position_id
    
    @classmethod
    def get_next_position_id_preview(cls, business_function_id):
        """Preview next position ID for business function"""
        try:
            business_function = BusinessFunction.objects.get(id=business_function_id)
            business_code = business_function.code
            
            # Get all existing IDs (both vacancy and employee)
            existing_ids = set()
            
            # From vacancies
            vacancy_ids = cls.all_objects.filter(
                position_id__startswith=business_code,
                position_id__regex=f'^{business_code}[0-9]+$'
            ).values_list('position_id', flat=True)
            existing_ids.update(vacancy_ids)
            
            # From employees
            employee_ids = Employee.all_objects.filter(
                employee_id__startswith=business_code,
                employee_id__regex=f'^{business_code}[0-9]+$'
            ).values_list('employee_id', flat=True)
            existing_ids.update(employee_ids)
            
            # Extract numbers
            used_numbers = set()
            for id_value in existing_ids:
                try:
                    number_part = id_value[len(business_code):]
                    if number_part.isdigit():
                        used_numbers.add(int(number_part))
                except (ValueError, IndexError):
                    continue
            
            # Find next available number
            next_number = 1
            while next_number in used_numbers:
                next_number += 1
            
            return f"{business_code}{next_number}"
            
        except BusinessFunction.DoesNotExist:
            return None

    def save(self, *args, **kwargs):
        """FIXED: Properly preserve original_employee_pk during all save operations"""
        
        # CRITICAL: Store original_employee_pk BEFORE any operations
        original_pk_to_preserve = self.original_employee_pk
        
        # Auto-generate position_id if not set
        if not self.position_id and self.business_function:
            self.position_id = self.generate_position_id()
        
        # Auto-generate display name
        self.display_name = f"[VACANT]"
        
        # Auto-generate grading level based on position group if not set
        if self.position_group and not self.grading_level:
            self.grading_level = f"{self.position_group.grading_shorthand}_M"
        
        # Auto-assign vacancy status if not set
        if not self.vacancy_status_id:
            vacant_status, created = EmployeeStatus.objects.get_or_create(
                name='VACANT',
                defaults={
                    'status_type': 'VACANT',
                    'color': '#F97316',
                    'affects_headcount': True,
                    'allows_org_chart': True,
                    'is_active': True,
                }
            )
            self.vacancy_status = vacant_status
        
 
        if original_pk_to_preserve is not None:
            self.original_employee_pk = original_pk_to_preserve
    
        
        # Call parent save with explicit field preservation
        if original_pk_to_preserve is not None:
            # First save without the PK field in update_fields to avoid conflicts
            super().save(*args, **kwargs)
            
            # Then explicitly update the PK field if it was lost
            if self.original_employee_pk != original_pk_to_preserve:
               
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE api_vacantposition SET original_employee_pk = %s WHERE id = %s",
                        [original_pk_to_preserve, self.id]
                    )
                # Refresh from database
                self.refresh_from_db()
               
        else:
            # Normal save when no PK to preserve
            super().save(*args, **kwargs)
        
       
        # CRITICAL: Double-check that the value is actually in the database
        if original_pk_to_preserve is not None:
            self.refresh_from_db()
            if self.original_employee_pk != original_pk_to_preserve:
                logger.error(f"CRITICAL: original_employee_pk still not saved correctly! Expected: {original_pk_to_preserve}, Got: {self.original_employee_pk}")
                raise Exception(f"Failed to preserve original_employee_pk: {original_pk_to_preserve}")
    def mark_as_filled(self, employee):
        """Mark vacancy as filled by an employee"""
        self.is_filled = True
        self.filled_by_employee = employee
        self.filled_date = timezone.now().date()
        self.include_in_headcount = False  # Remove from headcount when filled
        
        # Link employee to this vacancy
        employee.original_vacancy = self
        employee.save()
        
        self.save()
    
    def get_as_employee_data(self):
        """Return vacancy data in employee-like format for unified display"""
        return {
            'id': f"vacancy_{self.id}",
            'employee_id': self.position_id,  # Use position_id as employee_id equivalent
            'name': self.display_name,
            'full_name': self.display_name,
            'email': None,
            'job_title': self.job_title,
            'business_function': self.business_function,
            'business_function_name': self.business_function.name if self.business_function else 'N/A',
            'department': self.department,
            'department_name': self.department.name if self.department else 'N/A',
            'unit': self.unit,
            'unit_name': self.unit.name if self.unit else None,
            'job_function': self.job_function,
            'job_function_name': self.job_function.name if self.job_function else 'N/A',
            'position_group': self.position_group,
            'position_group_name': self.position_group.get_name_display() if self.position_group else 'N/A',
            'grading_level': self.grading_level,
            'status': self.vacancy_status,
            'status_name': self.vacancy_status.name if self.vacancy_status else 'VACANT',
            'status_color': self.vacancy_status.color if self.vacancy_status else '#F97316',
            'line_manager': self.reporting_to,
            'line_manager_name': self.reporting_to.full_name if self.reporting_to else None,
            'is_visible_in_org_chart': self.is_visible_in_org_chart,
            'is_vacancy': True,
            'created_at': self.created_at,
            'notes': self.notes,
            'filled_by': self.filled_by_employee.full_name if self.filled_by_employee else None,
            'vacancy_details': {
                'internal_id': self.id,
                'position_id': self.position_id,
                'include_in_headcount': self.include_in_headcount,
                'is_filled': self.is_filled,
                'filled_date': self.filled_date,
                'business_function_based_id': True
            }
        }

    def __str__(self):
        return f"{self.position_id} - {self.job_title} [VACANT]"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Vacant Position"
        verbose_name_plural = "Vacant Positions"

class EmployeeArchive(models.Model):
    """ENHANCED: Archive for both soft and hard deleted employees"""
    
    # Original employee information
    original_employee_id = models.CharField(max_length=50, db_index=True)
    original_employee_pk = models.CharField(max_length=50, db_index=True)
    full_name = models.CharField(max_length=300)
    email = models.EmailField()
    job_title = models.CharField(max_length=200)
    
    # Organizational info - FIXED: Allow blank and null for unit_name
    business_function_name = models.CharField(max_length=100, blank=True)
    department_name = models.CharField(max_length=100, blank=True)
    unit_name = models.CharField(max_length=100, blank=True, null=True)  # FIXED: Added null=True
    job_function_name = models.CharField(max_length=100, blank=True)
    
    # Employment dates
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    contract_duration = models.CharField(max_length=50)
    
    # Management info
    line_manager_name = models.CharField(max_length=300, blank=True)
    
    deletion_notes = models.TextField(
        blank=True, 
        help_text="Additional notes about deletion and any restorations"
    )
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    deleted_at = models.DateTimeField()
    
    # NEW: Track if employee still exists in main table (for soft deletes)
    employee_still_exists = models.BooleanField(
        default=False, 
        help_text="True if this was a soft delete and employee data still exists in main table"
    )
    
    # Enhanced data preservation
    original_data = models.JSONField(
        default=dict, 
        help_text="Complete original employee data in JSON format"
    )
    data_quality = models.CharField(
        max_length=20,
        choices=[
            ('COMPLETE', 'Complete Data'),
            ('PARTIAL', 'Partial Data'),
            ('BASIC', 'Basic Info Only'),
            ('MINIMAL', 'Minimal Data')
        ],
        default='BASIC'
    )
    
    # Archive metadata
    archive_version = models.CharField(max_length=10, default='2.0')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def get_archive_reference(self):
        """Generate unique archive reference"""
        return f"{self.id}-{self.original_employee_id}"
    
    def get_deletion_summary(self):
        """Enhanced deletion summary"""
        return {
            'original_employee_pk': self.original_employee_pk,
            'employee_id': self.original_employee_id,
            'name': self.full_name,
            'deleted_by': self.deleted_by.get_full_name() if self.deleted_by else 'System',
            'deleted_at': self.deleted_at,
            'data_quality': self.get_data_quality_display(),
            'archive_reference': self.get_archive_reference(),
            'deletion_notes': self.deletion_notes,
            'employee_still_exists': self.employee_still_exists,
            'last_updated': self.updated_at
        }
    
    @classmethod
    def get_soft_deleted_archives(cls):
        """Get archives from soft deletions (employee still exists)"""
        return cls.objects.filter(employee_still_exists=True)
    
    @classmethod
    def get_hard_deleted_archives(cls):
        """Get archives from hard deletions (employee completely removed)"""
        return cls.objects.filter(employee_still_exists=False)
    
    def get_deletion_type(self):
        """Get the type of deletion this archive represents"""
        return 'soft_delete' if self.employee_still_exists else 'hard_delete'
    
    def get_deletion_type_display(self):
        """Get human readable deletion type"""
        return 'Soft Delete (Restorable)' if self.employee_still_exists else 'Hard Delete (Permanent)'
    
    def can_be_restored(self):
        """Check if this archived employee can be restored"""
        if not self.employee_still_exists:
            return False
        
        # Check if employee still exists in database
        try:
            from .models import Employee
            Employee.all_objects.get(
                employee_id=self.original_employee_id,
                is_deleted=True
            )
            return True
        except Employee.DoesNotExist:
            return False
    
    def get_enhanced_deletion_summary(self):
        """Enhanced deletion summary with type information"""
        base_summary = self.get_deletion_summary()
        base_summary.update({
            'deletion_type': self.get_deletion_type(),
            'deletion_type_display': self.get_deletion_type_display(),
            'can_be_restored': self.can_be_restored(),
            'is_restorable': self.employee_still_exists,
            'restoration_available': self.can_be_restored()
        })
        return base_summary
    
    def __str__(self):
        return f"Archive: {self.original_employee_id} - {self.full_name}"
    
    class Meta:
        ordering = ['-deleted_at']
        verbose_name = "Employee Archive"
        verbose_name_plural = "Employee Archives"
        indexes = [
            models.Index(fields=['original_employee_id']),
            models.Index(fields=['original_employee_pk']),
            models.Index(fields=['deleted_at']),
            models.Index(fields=['employee_still_exists']),
            models.Index(fields=['data_quality']),
            models.Index(fields=['business_function_name']),
            models.Index(fields=['department_name']),
        ]
class Employee(SoftDeleteModel):
    GENDER_CHOICES = [
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
    ]
    
    profile_image = models.ImageField(
        upload_to='employee_profiles/%Y/%m/',
        null=True, 
        blank=True,
        help_text="Employee profile photo"
    )

    # CHANGED: Make user field optional - only create when employee needs system access
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='employee_profile',
        null=True,
        blank=True,
        help_text="Django user account (created when employee needs system access)"
    )

    # Basic Information
    employee_id = models.CharField(
        max_length=50, 
        unique=True, 
        editable=False,
        help_text="Auto-generated based on Business Function code"
    )
    original_employee_pk = models.IntegerField(
        null=True,
        blank=True,
        help_text="Original employee database ID (pk) that created this vacancy"
    )
    
    # Auto-generated full name
    full_name = models.CharField(max_length=300, editable=False, default='')
    
    # ENHANCED: Add first_name and last_name directly to Employee model
    first_name = models.CharField(
        max_length=150, 
        help_text="Employee's first name"
    )
    last_name = models.CharField(
        max_length=150, 
        help_text="Employee's last name"
    )
    
    # Personal Information (ENHANCED with father_name)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, null=True, blank=True)
    father_name = models.CharField(max_length=200, blank=True, null=True, help_text="Father's name (optional)")
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    email = models.CharField(max_length=60, blank=True, null=True)  # Primary email for employee
    emergency_contact = models.TextField(blank=True, null=True)
    
    
    # Job Information
    business_function = models.ForeignKey(BusinessFunction, on_delete=models.PROTECT, related_name='employees')
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='employees')
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name='employees', null=True, blank=True)
    job_function = models.ForeignKey(JobFunction, on_delete=models.PROTECT, related_name='employees')
    job_title = models.CharField(max_length=200)
    position_group = models.ForeignKey(PositionGroup, on_delete=models.PROTECT, related_name='employees')
   
    # Enhanced grading system integration
    grading_level = models.CharField(max_length=15, default='', help_text="Specific grading level (e.g., MGR_UQ)")
    

    # Employment Dates
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    # Enhanced contract management
    contract_duration = models.CharField(
        max_length=50, 
        default='PERMANENT',
        help_text="Contract duration type - references ContractTypeConfig"
    )
    contract_start_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True, editable=False)  # Auto-calculated
    contract_extensions = models.IntegerField(default=0, help_text="Number of contract extensions")
    last_extension_date = models.DateField(null=True, blank=True)
    
    
    # Management Hierarchy (ENHANCED)
    line_manager = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='direct_reports', help_text="Line manager for this employee")
    
    # Status and Visibility
    status = models.ForeignKey(EmployeeStatus, on_delete=models.PROTECT, related_name='employees')
    is_visible_in_org_chart = models.BooleanField(default=True)
    
    # Tags and categorization
    tags = models.ManyToManyField(EmployeeTag, blank=True, related_name='employees')
    
    # Additional Information
    notes = models.TextField(default='', blank=True)
    
    original_vacancy = models.OneToOneField('VacantPosition', on_delete=models.SET_NULL, null=True, blank=True, 
                                          related_name='employee_hired_for_position', 
                                          help_text="Original vacancy this employee was hired for")
    
    # Audit fields
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_employees')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_employees')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def generate_employee_id(self):
        """FIXED: Generate employee ID with better uniqueness logic"""
        if not self.business_function:
            raise ValueError("Business function is required to generate employee ID")
        
        business_code = self.business_function.code
        
        with transaction.atomic():
            # Get ALL existing employee IDs for this business function (including deleted ones)
            existing_ids = set(
                Employee.all_objects.filter(
                    employee_id__startswith=business_code,
                    employee_id__regex=f'^{business_code}[0-9]+$'  # Only numeric suffixes
                ).values_list('employee_id', flat=True)
            )
            
            # Extract numbers from existing IDs
            used_numbers = set()
            for emp_id in existing_ids:
                try:
                    number_part = emp_id[len(business_code):]
                    if number_part.isdigit():
                        used_numbers.add(int(number_part))
                except (ValueError, IndexError):
                    continue
            
            # Find the next available number
            next_number = 1
            while next_number in used_numbers:
                next_number += 1
            
            new_employee_id = f"{business_code}{next_number}"
            
            # Final safety check
            while Employee.all_objects.filter(employee_id=new_employee_id).exists():
                next_number += 1
                new_employee_id = f"{business_code}{next_number}"
            
            return new_employee_id
    
    @classmethod
    def get_next_employee_id_preview(cls, business_function_id):
        """FIXED: Preview next employee ID"""
        try:
            business_function = BusinessFunction.objects.get(id=business_function_id)
            business_code = business_function.code
            
            # Get all existing IDs for this business function
            existing_ids = set(
                cls.all_objects.filter(
                    employee_id__startswith=business_code,
                    employee_id__regex=f'^{business_code}[0-9]+$'
                ).values_list('employee_id', flat=True)
            )
            
            # Extract numbers
            used_numbers = set()
            for emp_id in existing_ids:
                try:
                    number_part = emp_id[len(business_code):]
                    if number_part.isdigit():
                        used_numbers.add(int(number_part))
                except (ValueError, IndexError):
                    continue
            
            # Find next available number
            next_number = 1
            while next_number in used_numbers:
                next_number += 1
            
            return f"{business_code}{next_number}"
            
        except BusinessFunction.DoesNotExist:
            return None
    def save(self, *args, **kwargs):
        # Auto-generate employee_id BEFORE calling super().save()
        if not self.employee_id and self.business_function:
            self.employee_id = self.generate_employee_id()
        
        if self.first_name or self.last_name:
            # Priority 1: Use employee's own first_name/last_name fields
            self.full_name = f"{self.first_name} {self.last_name}".strip()
        elif self.user and (self.user.first_name or self.user.last_name):
            # Priority 2: Use user's first_name/last_name as fallback
            self.full_name = f"{self.user.first_name} {self.user.last_name}".strip()
        if not self.pk and not self.status_id:  # pk None = yeni object
            self.auto_assign_status()
        # Sync email: if user exists and employee email is empty, use user email
        if self.user and self.user.email and not self.email:
            self.email = self.user.email
        # Auto-calculate contract end date
        if self.contract_start_date and self.contract_duration != 'PERMANENT':
            try:
                if relativedelta:
                    if self.contract_duration == '3_MONTHS':
                        self.contract_end_date = self.contract_start_date + relativedelta(months=3)
                    elif self.contract_duration == '6_MONTHS':
                        self.contract_end_date = self.contract_start_date + relativedelta(months=6)
                    elif self.contract_duration == '1_YEAR':
                        self.contract_end_date = self.contract_start_date + relativedelta(years=1)
                    elif self.contract_duration == '2_YEARS':
                        self.contract_end_date = self.contract_start_date + relativedelta(years=2)
                    elif self.contract_duration == '3_YEARS':
                        self.contract_end_date = self.contract_start_date + relativedelta(years=3)
                else:
                    # Fallback calculation
                    days_mapping = {
                        '3_MONTHS': 90,
                        '6_MONTHS': 180,
                        '1_YEAR': 365,
                        '2_YEARS': 730,
                        '3_YEARS': 1095
                    }
                    days = days_mapping.get(self.contract_duration, 365)
                    self.contract_end_date = self.contract_start_date + timedelta(days=days)
            except Exception as e:
                logger.error(f"Error calculating contract end date: {e}")
                self.contract_end_date = None
        else:
            self.contract_end_date = None
        
        # Auto-generate grading level based on position group
        if self.position_group and not self.grading_level:
            self.grading_level = f"{self.position_group.grading_shorthand}_M"
        
        # CRITICAL: Status təyini - yalnız yeni işçi yaradılarkən
        if not self.pk and not self.status_id:  # pk None = yeni object
            self.auto_assign_status()
        
        # Contract start date default
        if not self.contract_start_date:
            self.contract_start_date = self.start_date
        
        
        
        
        
        # Link to vacant position if applicable
        if not self.original_vacancy and hasattr(self, '_vacancy_id'):
            try:
                vacancy = VacantPosition.objects.get(id=self._vacancy_id)
                vacancy.mark_as_filled(self)
                self.original_vacancy= vacancy
            except VacantPosition.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
    
    def link_with_user_account(self, user):
        """
        Properly link this employee with a user account
        Used during Microsoft authentication
        """
        if self.user and self.user != user:
            raise ValueError(f"Employee {self.employee_id} is already linked to a different user account")
        
        # Link user to employee
        self.user = user
        
        # Sync information
        if not self.email and user.email:
            self.email = user.email
        if not self.first_name and user.first_name:
            self.first_name = user.first_name
        if not self.last_name and user.last_name:
            self.last_name = user.last_name
        
        self.save()
       
    
    def create_user_account_for_microsoft_auth(self, email, first_name, last_name, microsoft_id):
        """
        Create user account specifically for Microsoft authentication
        This ensures proper linking during auth process
        """
        if self.user:
            raise ValueError(f"Employee {self.employee_id} already has a user account")
        
        from django.db import transaction
        
        with transaction.atomic():
            # Create user
            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=first_name,
                last_name=last_name
            )
            user.set_unusable_password()  # Microsoft auth only
            user.save()
            
            # Link to employee
            self.link_with_user_account(user)
            
            # Create Microsoft link
            MicrosoftUser.objects.create(
                user=user,
                microsoft_id=microsoft_id
            )
            
            return user
    def has_system_access(self):
        """Check if employee has system access (user account)"""
        return bool(self.user)
    
    def can_login_with_microsoft(self):
        """Check if employee can login with Microsoft"""
        return bool(self.user and hasattr(self.user, 'microsoft_user'))
    
    def get_display_name(self):
        """Get display name for employee"""
        return self.full_name or f"{self.first_name} {self.last_name}".strip()
    def get_display_first_name(self):
        """Get display name for employee"""
        return self.first_name or f"{self.first_name} ".strip()
    def get_display_last_name(self):
        """Get display name for employee"""
        return self.last_name or f" {self.last_name}".strip()
    
    def get_contact_email(self):
        """Get primary contact email for employee"""
        return self.email or (self.user.email if self.user else None)
    
    def auto_assign_status(self):
        """✅ FIXED: Yeni employee üçün status - start_date və probation days əsasında"""
        try:
            current_date = date.today()
            
            # ✅ PERMANENT contract → directly ACTIVE
            if self.contract_duration == 'PERMANENT':
                active_status = EmployeeStatus.objects.filter(
                    status_type='ACTIVE',
                    is_active=True
                ).first()
                
                if active_status:
                    self.status = active_status
                 
                    return
            
            # ✅ Check if start_date is in the past (back-dated employee)
            if not self.start_date:
                # No start date, use PROBATION as default
                probation_status = EmployeeStatus.objects.filter(
                    status_type='PROBATION',
                    is_active=True
                ).first()
                
                if probation_status:
                    self.status = probation_status
                return
            
            # ✅ Calculate days since start
            days_since_start = (current_date - self.start_date).days
            
     
            
            # ✅ Get contract config
            try:
                contract_config = ContractTypeConfig.objects.get(
                    contract_type=self.contract_duration,
                    is_active=True
                )
            except ContractTypeConfig.DoesNotExist:
                # Fallback to PROBATION
                probation_status = EmployeeStatus.objects.filter(
                    status_type='PROBATION',
                    is_active=True
                ).first()
                
                if probation_status:
                    self.status = probation_status
                logger.warning(f"No contract config for {self.contract_duration}")
                return
            
            probation_days = contract_config.probation_days
            
            # ✅ Check if probation period is over
            if days_since_start >= probation_days:
                # Probation completed → ACTIVE
                active_status = EmployeeStatus.objects.filter(
                    status_type='ACTIVE',
                    is_active=True
                ).first()
                
                if active_status:
                    self.status = active_status
                  
                else:
                    # Fallback
                    probation_status = EmployeeStatus.objects.filter(
                        status_type='PROBATION',
                        is_active=True
                    ).first()
                    self.status = probation_status
            else:
                # Still in probation
                probation_status = EmployeeStatus.objects.filter(
                    status_type='PROBATION',
                    is_active=True
                ).first()
                
                if probation_status:
                    self.status = probation_status
                    remaining_days = probation_days - days_since_start
                    
                else:
                    # Fallback to ACTIVE if PROBATION not found
                    active_status = EmployeeStatus.objects.filter(
                        status_type='ACTIVE',
                        is_active=True
                    ).first()
                    self.status = active_status

                    
        except Exception as e:
         
            if not self.status:
                fallback_status = EmployeeStatus.objects.filter(is_active=True).first()
                if fallback_status:
                    self.status = fallback_status
        
    def get_required_status_based_on_contract(self):
        """✅ UPDATED: Contract-based status (ONBOARDING yoxdur)"""
        try:
            current_date = date.today()
            
            # Contract bitib?
            if self.contract_end_date and self.contract_end_date <= current_date:
                inactive_status = EmployeeStatus.objects.filter(status_type='INACTIVE').first()
                return inactive_status, f"Contract ended on {self.contract_end_date}"
            
            # Contract config
            try:
                contract_config = ContractTypeConfig.objects.get(contract_type=self.contract_duration)
            except ContractTypeConfig.DoesNotExist:
                contract_configs = ContractTypeConfig.get_or_create_defaults()
                contract_config = contract_configs.get(self.contract_duration)
                if not contract_config:
                    return self.status, "No contract configuration found"
            
            if not contract_config.enable_auto_transitions:
                return self.status, "Auto transitions disabled for this contract type"
            
            # ✅ PERMANENT → directly ACTIVE
            if self.contract_duration == 'PERMANENT':
                active_status = EmployeeStatus.objects.filter(status_type='ACTIVE').first()
                return active_status, "Permanent contract - no probation period"
            
            # Days since start
            days_since_start = (current_date - self.start_date).days
            
            # ✅ Probation period?
            if days_since_start <= contract_config.probation_days:
                probation_status = EmployeeStatus.objects.filter(status_type='PROBATION').first()
                remaining_days = contract_config.probation_days - days_since_start
                return probation_status, f"Probation period ({remaining_days} days remaining)"
            
            else:
                # ✅ Probation completed → ACTIVE
                active_status = EmployeeStatus.objects.filter(status_type='ACTIVE').first()
                return active_status, "Probation period completed"
                
        except Exception as e:
            logger.error(f"Error calculating required status for {self.employee_id}: {e}")
            return self.status, f"Error: {str(e)}"
    
    def update_status_automatically(self, force_update=False):
        """Update employee status based on contract configuration"""
        try:
            required_status, reason = self.get_required_status_based_on_contract()
            
            if not required_status:
                return False
            
            # Check if status needs to be updated
            if self.status != required_status or force_update:
                old_status = self.status
                self.status = required_status
                self.save()
                
                # Log activity
                EmployeeActivity.objects.create(
                    employee=self,
                    activity_type='STATUS_CHANGED',
                    description=f"Status automatically updated from {old_status.name} to {required_status.name}. Reason: {reason}",
                    performed_by=None,  # System update
                    metadata={
                        'old_status': old_status.name,
                        'new_status': required_status.name,
                        'reason': reason,
                        'automatic': True,
                        'contract_type': self.contract_duration,
                        'days_since_start': (date.today() - self.start_date).days
                    }
                )
                
              
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating status automatically for {self.employee_id}: {e}")
            return False
 
    def extend_contract(self, extension_months, user=None):
        """Extend employee contract"""
        if self.contract_duration == 'PERMANENT':
            return False, "Cannot extend permanent contract"
        
        if not self.contract_end_date:
            return False, "No contract end date to extend"
        
        try:
            if relativedelta:
                new_end_date = self.contract_end_date + relativedelta(months=extension_months)
            else:
                # Approximate calculation
                new_end_date = self.contract_end_date + timedelta(days=extension_months * 30)
            
            old_end_date = self.contract_end_date
            self.contract_end_date = new_end_date
            self.contract_extensions += 1
            self.last_extension_date = timezone.now().date()
           
            
            if user:
                self.updated_by = user
            
            self.save()
            
            # Log activity
            EmployeeActivity.objects.create(
                employee=self,
                activity_type='CONTRACT_UPDATED',
                description=f"Contract extended by {extension_months} months. New end date: {new_end_date}",
                performed_by=user,
                metadata={
                    'extension_months': extension_months,
                    'old_end_date': str(old_end_date),
                    'new_end_date': str(new_end_date),
                    'extension_count': self.contract_extensions
                }
            )
            
            return True, f"Contract extended successfully until {new_end_date}"
            
        except Exception as e:
            logger.error(f"Error extending contract for {self.employee_id}: {e}")
            return False, f"Error extending contract: {str(e)}"

    # models.py - Employee model-də add_tag metodunu yenilə

    def add_tag(self, tag, user=None, skip_status_change=False):
        """
        ✅ UPDATED: Add tag and optionally auto-set status to INACTIVE
        """
        if not self.tags.filter(id=tag.id).exists():
            self.tags.add(tag)
            
            # ✅ Status-u INACTIVE et (əgər skip edilməyibsə)
            status_changed = False
            old_status = self.status
            
            if not skip_status_change:
                try:
                    inactive_status = EmployeeStatus.objects.filter(
                        status_type='INACTIVE',
                        is_active=True
                    ).first()
                    
                    if inactive_status and self.status != inactive_status:
                        self.status = inactive_status
                        self.save(update_fields=['status'])  # ✅ CRITICAL: Explicitly save status
                        status_changed = True
                        
                        # Log the status change
                        EmployeeActivity.objects.create(
                            employee=self,
                            activity_type='STATUS_CHANGED',
                            description=f"Status automatically changed to INACTIVE when tag '{tag.name}' was added",
                            performed_by=user,
                            metadata={
                                'tag_id': tag.id,
                                'tag_name': tag.name,
                                'old_status': old_status.name if old_status else None,
                                'new_status': inactive_status.name,
                                'auto_change_reason': 'tag_added',
                                'automatic': True
                            }
                        )
                        
                      
                    else:
                        logger.warning(f"⚠️ INACTIVE status not found or employee already INACTIVE")
                except Exception as e:
                    logger.error(f"❌ Error setting INACTIVE status for employee {self.employee_id}: {e}")
            
            # Log tag addition
            EmployeeActivity.objects.create(
                employee=self,
                activity_type='TAG_ADDED',
                description=f"Tag '{tag.name}' added" + (
                    " - Status changed to INACTIVE" if status_changed else ""
                ),
                performed_by=user,
                metadata={
                    'tag_id': tag.id, 
                    'tag_name': tag.name,
                    'status_changed_to_inactive': status_changed,
                    'skip_status_change': skip_status_change
                }
            )
            
            return True
        return False
    def remove_tag(self, tag, user=None):
        """
        ✅ UPDATED: Remove tag and auto-set status to ACTIVE
        """
        if self.tags.filter(id=tag.id).exists():
            self.tags.remove(tag)
            
            # ✅ Status-u ACTIVE et
            status_changed = False
            old_status = self.status
            
            try:
                active_status = EmployeeStatus.objects.filter(
                    status_type='ACTIVE',
                    is_active=True
                ).first()
                
                if active_status and self.status != active_status:
                    self.status = active_status
                    self.save()
                    status_changed = True
                    
                    # Log the status change
                    EmployeeActivity.objects.create(
                        employee=self,
                        activity_type='STATUS_CHANGED',
                        description=f"Status automatically changed to ACTIVE when tag '{tag.name}' was removed",
                        performed_by=user,
                        metadata={
                            'tag_id': tag.id,
                            'tag_name': tag.name,
                            'old_status': old_status.name if old_status else None,
                            'new_status': active_status.name,
                            'auto_change_reason': 'tag_removed',
                            'automatic': True
                        }
                    )
                    
                   
            except Exception as e:
                logger.error(f"Error setting ACTIVE status for employee {self.employee_id}: {e}")
            
            # Log tag removal
            EmployeeActivity.objects.create(
                employee=self,
                activity_type='TAG_REMOVED',
                description=f"Tag '{tag.name}' removed" + (
                    " - Status changed to ACTIVE" if status_changed else ""
                ),
                performed_by=user,
                metadata={
                    'tag_id': tag.id, 
                    'tag_name': tag.name,
                    'status_changed_to_active': status_changed
                }
            )
            
            return True
        return False
    def change_line_manager(self, new_manager, user=None):
        """Change employee's line manager"""
        old_manager = self.line_manager
        self.line_manager = new_manager
        if user:
            self.updated_by = user
        self.save()
        
        # Log activity
        old_manager_name = old_manager.full_name if old_manager else 'None'
        new_manager_name = new_manager.full_name if new_manager else 'None'
        
        EmployeeActivity.objects.create(
            employee=self,
            activity_type='MANAGER_CHANGED',
            description=f"Line manager changed from {old_manager_name} to {new_manager_name}",
            performed_by=user,
            metadata={
                'old_manager_id': old_manager.id if old_manager else None,
                'new_manager_id': new_manager.id if new_manager else None,
                'old_manager_name': old_manager_name,
                'new_manager_name': new_manager_name
            }
        )
    
   
    def get_profile_image_url(self, request=None):
        """Get profile image URL safely"""
        if self.profile_image:
            try:
                if hasattr(self.profile_image, 'url'):
                    if request:
                        return request.build_absolute_uri(self.profile_image.url)
                    return self.profile_image.url
            except Exception as e:
                logger.warning(f"Could not get profile image URL for employee {self.employee_id}: {e}")
        return None
    
    def has_profile_image(self):
        """Check if employee has a profile image"""
        return bool(self.profile_image and hasattr(self.profile_image, 'url'))
    
    @property
    def years_of_service(self):
        """Calculate years of service"""
        if self.start_date:
            end_date = self.end_date or date.today()
            delta = end_date - self.start_date
            return round(delta.days / 365.25, 1)
        return 0

    @property
    def current_status_display(self):
        """Get formatted status display"""
        if self.status:
            return f"{self.status.name}"
        return "No Status"

    def _serialize_complete_employee_data(self):
        """Serialize complete employee data for archiving"""
        try:
            return {
                'id': self.id,
                'employee_id': self.employee_id,
                'full_name': self.full_name,
                'user_info': {
                    'id': self.user.id if self.user else None,
                    'username': self.user.username if self.user else None,
                    'email': self.user.email if self.user else None,
                    'first_name': self.user.first_name if self.user else None,
                    'last_name': self.user.last_name if self.user else None,
                },
                'personal_info': {
                    'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
                    'gender': self.gender,
                    'father_name': self.father_name,
                    'address': self.address,
                    'phone': self.phone,
                    'emergency_contact': self.emergency_contact,
                },
                'job_info': {
                    'business_function': self.business_function.name if self.business_function else None,
                    'business_function_code': self.business_function.code if self.business_function else None,
                    'department': self.department.name if self.department else None,
                    'unit': self.unit.name if self.unit else None,
                    'job_function': self.job_function.name if self.job_function else None,
                    'job_title': self.job_title,
                    'position_group': self.position_group.get_name_display() if self.position_group else None,
                    'grading_level': self.grading_level,
                },
                'employment_details': {
                    'start_date': self.start_date.isoformat() if self.start_date else None,
                    'end_date': self.end_date.isoformat() if self.end_date else None,
                    'contract_duration': self.contract_duration,
                    'contract_start_date': self.contract_start_date.isoformat() if self.contract_start_date else None,
                    'contract_end_date': self.contract_end_date.isoformat() if self.contract_end_date else None,
                    'contract_extensions': self.contract_extensions,
                    'last_extension_date': self.last_extension_date.isoformat() if self.last_extension_date else None,
                },
                'management': {
                    'line_manager_id': self.line_manager.employee_id if self.line_manager else None,
                    'line_manager_name': self.line_manager.full_name if self.line_manager else None,
                    'direct_reports': [
                        {
                            'id': report.employee_id,
                            'name': report.full_name,
                            'job_title': report.job_title
                        }
                        for report in self.direct_reports.filter(is_deleted=False)
                    ]
                },
                'status_info': {
                    'status_name': self.status.name if self.status else None,
                    'status_type': self.status.status_type if self.status else None,
                    'is_visible_in_org_chart': self.is_visible_in_org_chart,
                },
                'tags': [
                    {'id': tag.id, 'name': tag.name, 'color': tag.color}
                    for tag in self.tags.all()
                ],
                'calculated_fields': {
                    'years_of_service': self.years_of_service,
                    'grading_display': self.get_grading_display(),
                },
                'metadata': {
                    'created_at': self.created_at.isoformat() if self.created_at else None,
                    'updated_at': self.updated_at.isoformat() if self.updated_at else None,
                    'created_by': self.created_by.username if self.created_by else None,
                    'updated_by': self.updated_by.username if self.updated_by else None,
                },
                'notes': self.notes,
                'original_vacancy': {
                    'id': self.original_vacancy.id if self.original_vacancy else None,
                    'position_id': self.original_vacancy.position_id if self.original_vacancy else None,
                } if self.original_vacancy else None,
                'documents_info': {
                    'total_documents': self.documents.count() if hasattr(self, 'documents') else 0,
                    'document_types': list(
                        self.documents.values_list('document_type', flat=True).distinct()
                    ) if hasattr(self, 'documents') else [],
                },
                'profile_image_info': {
                    'has_profile_image': bool(self.profile_image),
                    'image_name': self.profile_image.name if self.profile_image else None,
                }
            }
        except Exception as e:

            return {
                'error': f'Could not serialize complete data: {str(e)}',
                'basic_info': {
                    'employee_id': self.employee_id,
                    'full_name': self.full_name,
                    'email': self.user.email if self.user else None,
                },
                'serialization_error': True,
                'error_timestamp': timezone.now().isoformat()
            }
    
    def prepare_for_archiving(self):
        """Prepare employee data for archiving (can be called before deletion)"""
        return {
            'archive_preview': self._serialize_complete_employee_data(),
            'deletion_impact': {
                'direct_reports_count': self.direct_reports.filter(is_deleted=False).count(),
                'documents_count': self.documents.count() if hasattr(self, 'documents') else 0,
                'activities_count': self.activities.count(),
                'has_profile_image': bool(self.profile_image),
                'will_create_vacancy': True if hasattr(self, 'job_title') else False,
                'line_manager_exists': bool(self.line_manager),
            },
            'data_quality_check': {
                'has_user_account': bool(self.user),
                'has_complete_job_info': all([
                    self.business_function, self.department, 
                    self.job_function, self.position_group, self.job_title
                ]),
                'has_personal_info': any([
                    self.date_of_birth, self.phone, self.address, self.father_name
                ]),
                'has_employment_dates': bool(self.start_date),
                'has_contract_info': bool(self.contract_duration),
            }
        }
    
    def can_be_safely_deleted(self):
        """Check if employee can be safely deleted"""
        issues = []
        warnings = []
        
        # Check for blocking issues
        if self.direct_reports.filter(is_deleted=False).exists() and not self.line_manager:
            issues.append("Employee has direct reports but no line manager to reassign them to")
        
        # Check for warnings
        if self.direct_reports.filter(is_deleted=False).count() > 10:
            warnings.append(f"Employee has {self.direct_reports.filter(is_deleted=False).count()} direct reports")
        
        if hasattr(self, 'documents') and self.documents.filter(is_confidential=True).exists():
            warnings.append("Employee has confidential documents")
        
        if self.status and self.status.name == 'ACTIVE':
            warnings.append("Employee is currently active")
        
        return {
            'can_delete': len(issues) == 0,
            'blocking_issues': issues,
            'warnings': warnings,
            'recommendation': 'safe_to_delete' if len(issues) == 0 and len(warnings) == 0 else (
                'proceed_with_caution' if len(issues) == 0 else 'resolve_issues_first'
            )
        }

    @classmethod
    def get_soft_deleted_employees(cls, include_details=False):
        """Get all soft deleted employees with optional details"""
        deleted_employees = cls.all_objects.filter(is_deleted=True).select_related(
            'user', 'business_function', 'department', 'status', 'line_manager'
        ).order_by('-deleted_at')
        
        if not include_details:
            return deleted_employees
        
        detailed_list = []
        for emp in deleted_employees:
            emp_data = {
                'id': emp.id,
                'employee_id': emp.employee_id,
                'full_name': emp.full_name,
                'email': emp.user.email if emp.user else None,
                'job_title': emp.job_title,
                'business_function_name': emp.business_function.name if emp.business_function else None,
                'department_name': emp.department.name if emp.department else None,
                'deleted_at': emp.deleted_at,
                'deleted_by': emp.deleted_by.username if emp.deleted_by else None,
                'can_restore': True,
                'days_since_deletion': (timezone.now() - emp.deleted_at).days if emp.deleted_at else 0,
                'related_vacancies': VacantPosition.objects.filter(
                    business_function=emp.business_function,
                    department=emp.department,
                    job_title=emp.job_title,
                    notes__icontains=f"vacated by {emp.full_name}"
                ).count()
            }
            detailed_list.append(emp_data)
        
        return detailed_list
    
    @classmethod 
    def cleanup_old_soft_deleted(cls, days_old=90, user=None):
        """
        Convert old soft-deleted employees to hard delete with archive
        Useful for data cleanup
        """
        cutoff_date = timezone.now() - timedelta(days=days_old)
        old_deleted = cls.all_objects.filter(
            is_deleted=True,
            deleted_at__lt=cutoff_date
        )
        
        cleanup_results = {
            'total_found': old_deleted.count(),
            'successfully_archived': 0,
            'failed': 0,
            'errors': [],
            'archived_employees': []
        }
        
        for employee in old_deleted:
            try:
                # Store info before hard deletion
                emp_info = {
                    'original_employee_pk': employee.pk,
                    'employee_id': employee.employee_id,
                    'full_name': employee.full_name,
                    'deleted_at': employee.deleted_at
                }
                
                # Hard delete with archive
                archive = employee.hard_delete_with_archive(user)
                
                # Update archive to reflect cleanup process
                if archive:
       
                    archive.deletion_notes = f"Automatic cleanup of employee soft-deleted {days_old}+ days ago"
                    archive.save()
                
                cleanup_results['successfully_archived'] += 1
                cleanup_results['archived_employees'].append({
                    'original_employee_id': emp_info['employee_id'],
                    'original_employee_pk': emp_info['original_employee_pk'],
                    'name': emp_info['full_name'],
                    'originally_deleted': emp_info['deleted_at'],
                    'archive_id': archive.id if archive else None
                })
                
            except Exception as e:
                cleanup_results['failed'] += 1
                cleanup_results['errors'].append(f"Failed to archive {employee.employee_id}: {str(e)}")
                logger.error(f"Cleanup failed for employee {employee.employee_id}: {e}")
        
        return cleanup_results
    
    @classmethod
    def get_deletion_statistics(cls):
        """Get comprehensive deletion statistics"""
        total_employees = cls.all_objects.count()
        active_employees = cls.objects.count()
        soft_deleted = cls.all_objects.filter(is_deleted=True).count()
        
        # Archive statistics
        archived_count = EmployeeArchive.objects.count()
        
        # Recent deletions (last 30 days)
        recent_cutoff = timezone.now() - timedelta(days=30)
        recent_soft_deletions = cls.all_objects.filter(
            is_deleted=True,
            deleted_at__gte=recent_cutoff
        ).count()
        
        recent_hard_deletions = EmployeeArchive.objects.filter(
            deleted_at__gte=recent_cutoff
        ).count()
        
       
        
        return {
            'overview': {
                'total_employees_ever': total_employees + archived_count,
                'currently_active': active_employees,
                'soft_deleted': soft_deleted,
                'hard_deleted_archived': archived_count,
                'total_deletions': soft_deleted + archived_count
            },
            'recent_activity': {
                'soft_deletions_last_30_days': recent_soft_deletions,
                'hard_deletions_last_30_days': recent_hard_deletions,
                'total_deletions_last_30_days': recent_soft_deletions + recent_hard_deletions
            },
           
            'data_quality': {
                'employees_with_complete_archive_data': EmployeeArchive.objects.filter(
                    data_quality='COMPLETE'
                ).count(),
                'employees_needing_cleanup': cls.all_objects.filter(
                    is_deleted=True,
                    deleted_at__lt=timezone.now() - timedelta(days=90)
                ).count()
            }
        }

    def soft_delete_and_create_vacancy(self, user=None):
        """
        ✅ UPDATED: Soft delete employee, remove name from all processes, add end_date
        """
        with transaction.atomic():
            # Store original employee PK
            original_employee_pk = self.pk
            deletion_date = timezone.now().date()
            
   
            
            # ✅ YENİ: End date əlavə et
            if not self.end_date:
                self.end_date = deletion_date
            
            # Store employee data for vacancy creation
            employee_data = {
                'job_title': self.job_title,
                'business_function': self.business_function,
                'department': self.department,
                'unit': self.unit,
                'job_function': self.job_function,
                'position_group': self.position_group,
                'grading_level': self.grading_level,
                'reporting_to': self.line_manager,
                'is_visible_in_org_chart': self.is_visible_in_org_chart,
                'notes': f"Position vacated by [{self.employee_id}] on {deletion_date}"  # ✅ Adı deyil, ID göstər
            }
            
            # ✅ YENİ: Remove name from all related processes
            self._remove_name_from_processes()
            
            # Create vacancy with explicit original_employee_pk setting
            vacancy = VacantPosition(
                job_title=employee_data['job_title'],
                business_function=employee_data['business_function'],
                department=employee_data['department'],
                unit=employee_data['unit'],
                job_function=employee_data['job_function'],
                position_group=employee_data['position_group'],
                grading_level=employee_data['grading_level'],
                reporting_to=employee_data['reporting_to'],
                include_in_headcount=True,
                is_visible_in_org_chart=employee_data['is_visible_in_org_chart'],
                notes=employee_data['notes'],
                created_by=user
            )
            
            vacancy.original_employee_pk = original_employee_pk
            vacancy.save()
            
            # Verify vacancy PK
            vacancy.refresh_from_db()
            if vacancy.original_employee_pk != original_employee_pk:
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE api_vacantposition SET original_employee_pk = %s WHERE id = %s",
                        [original_employee_pk, vacancy.id]
                    )
                vacancy.refresh_from_db()
            
            # Update direct reports
            direct_reports_updated = 0
            if self.line_manager:
                direct_reports = self.direct_reports.filter(is_deleted=False)
                for report in direct_reports:
                    report.line_manager = self.line_manager
                    report.updated_by = user
                    report.save()
                    direct_reports_updated += 1
                    
                    # ✅ Activity log-da da ID göstər
                    EmployeeActivity.objects.create(
                        employee=report,
                        activity_type='MANAGER_CHANGED',
                        description=f"Line manager changed from [{self.employee_id}] to {self.line_manager.full_name} due to manager departure",
                        performed_by=user,
                        metadata={
                            'reason': 'manager_departure',
                            'old_manager_id': self.employee_id,
                            'new_manager_id': self.line_manager.id,
                            'vacancy_created': vacancy.id
                        }
                    )
            
            # Create archive record
            archive = self._create_archive_record(
                deletion_notes=f"Employee [{self.employee_id}] soft deleted and vacancy {vacancy.position_id} created. End date set to {deletion_date}.",
                deleted_by=user,
                preserve_original_data=True
            )
            
            # Soft delete the employee
            self.soft_delete(user)
            
            # Log the soft delete activity
            EmployeeActivity.objects.create(
                employee=self,
                activity_type='SOFT_DELETED',
                description=f"Employee [{self.employee_id}] soft deleted, vacancy {vacancy.position_id} created, end date set to {deletion_date}",
                performed_by=user,
                metadata={
                    'delete_type': 'soft_with_vacancy',
                    'vacancy_created': True,
                    'vacancy_id': vacancy.id,
                    'vacancy_position_id': vacancy.position_id,
                    'original_employee_pk': original_employee_pk,
                    'end_date_set': str(deletion_date),
                    'name_removed_from_processes': True
                }
            )
            
           
            return vacancy, archive
    
    def _remove_name_from_processes(self):
        """
        ✅ YENİ: Remove employee name from all related processes
        Name → Employee ID conversion everywhere
        """
        try:
            # 1. Job Descriptions - manager assignments
            from .job_description_models import JobDescriptionAssignment
            
            jd_assignments = JobDescriptionAssignment.objects.filter(
                reports_to=self,
                is_active=True
            )
            
            # Update notes to show ID instead of name
            for assignment in jd_assignments:
                if self.full_name in assignment.notes:
                    assignment.notes = assignment.notes.replace(
                        self.full_name, 
                        f"[{self.employee_id}]"
                    )
                    assignment.save()
            
            # 2. Performance Management - if employee is evaluator/manager
            from .performance_models import EmployeePerformance
            
            performances = EmployeePerformance.objects.filter(
                Q(employee__line_manager=self) | 
                Q(created_by=self.user)
            )
            
            # Update any notes or comments that contain employee name
            for perf in performances:
                if hasattr(perf, 'objectives_comments') and self.full_name in str(perf.objectives_comments):
                    perf.objectives_comments = str(perf.objectives_comments).replace(
                        self.full_name, 
                        f"[{self.employee_id}]"
                    )
                    perf.save()
            
            # 3. Asset Management - if employee is in asset activities
            from .asset_models import AssetActivity
            
            asset_activities = AssetActivity.objects.filter(
                performed_by=self.user
            )
            
            for activity in asset_activities:
                if self.full_name in activity.description:
                    activity.description = activity.description.replace(
                        self.full_name, 
                        f"[{self.employee_id}]"
                    )
                    activity.save()
            
            # 4. Employee Activities - update all descriptions
            activities = EmployeeActivity.objects.filter(
                Q(employee=self) | Q(performed_by=self.user)
            )
            
            for activity in activities:
                if self.full_name in activity.description:
                    activity.description = activity.description.replace(
                        self.full_name, 
                        f"[{self.employee_id}]"
                    )
                    activity.save()
            
            # 5. Update full_name field in Employee model to show ID
            # Keep original name in metadata for archive purposes
            original_full_name = self.full_name
            self.full_name = f"[DELETED-{self.employee_id}]"
            self.first_name = "[DELETED]"
            self.last_name = self.employee_id
            
            # Store original name in notes for reference
            if self.notes:
                self.notes = f"[ORIGINAL NAME: {original_full_name}]\n\n{self.notes}"
            else:
                self.notes = f"[ORIGINAL NAME: {original_full_name}]"
            
            
            return True
            
        except Exception as e:
            logger.error(f"Error removing name from processes: {e}")
            return False
    def hard_delete_with_archive(self, user=None):
        """
        FIXED: Hard delete employee completely and create comprehensive archive - NO VACANCY CREATION
        """
        if not self.end_date:
            self.end_date = timezone.now().date()
            self.save(update_fields=['end_date'])
        
        # Store employee info before any database operations
        employee_info = {
            'id': self.id,
            'employee_id': self.employee_id,
            'full_name': self.full_name,
            'original_employee_pk': self.pk,
            'end_date': self.end_date,  # ✅ Include in archive
            'direct_reports_count': self.direct_reports.filter(is_deleted=False).count()
        }
        
        
        try:
            # Create archive record FIRST, outside of transaction
            archive = self._create_archive_record(
                deletion_notes="Employee hard deleted and completely removed from system - NO VACANCY CREATED",
                deleted_by=user,
                preserve_original_data=False  # Employee will be removed from database
            )
            
            # Now handle the deletion in transaction
            with transaction.atomic():
                # Update direct reports to report to this employee's manager
                direct_reports_updated = 0
                if self.line_manager:
                    direct_reports = self.direct_reports.filter(is_deleted=False)
                    for report in direct_reports:
                        report.line_manager = self.line_manager
                        report.updated_by = user
                        report.save()
                        direct_reports_updated += 1
                
                # Delete related data
                self.activities.all().delete()
                if hasattr(self, 'documents'):
                    self.documents.all().delete()
                
                # Delete profile image file
                if self.profile_image:
                    try:
                        if hasattr(self.profile_image, 'path') and os.path.exists(self.profile_image.path):
                            os.remove(self.profile_image.path)
                    except Exception as e:
                        logger.warning(f"Could not delete profile image file: {e}")
                
                # Store user for deletion after employee deletion
                user_to_delete = self.user if self.user else None
                
                
                super().delete()  # This bypasses soft delete and does hard delete
                
                # Delete user account after employee deletion
                if user_to_delete:
                    user_to_delete.delete()
            
           
            
            return archive
            
        except Exception as e:
            logger.error(f"Hard delete failed for employee {employee_info['employee_id']}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise e
    
    def _create_archive_record(self, deletion_notes, deleted_by, preserve_original_data=True):
        """
        FIXED: Create archive record for both soft and hard delete with proper null handling
        """
        try:
            actual_employee_pk = str(self.pk) 
            # FIXED: Safely handle unit_name with proper null checking
            unit_name = None
            if self.unit and hasattr(self.unit, 'name'):
                unit_name = self.unit.name
            
            # FIXED: Safely handle all field extraction
            archive_data = {
                'original_employee_id': self.employee_id or '',
                'original_employee_pk': actual_employee_pk or '',
                'full_name': self.full_name or '',
                'email': self.user.email if self.user else '',
                'job_title': self.job_title or '',
                'business_function_name': self.business_function.name if self.business_function else '',
                'department_name': self.department.name if self.department else '',
                'unit_name': unit_name,  # FIXED: This can now be None/null
                'job_function_name': self.job_function.name if self.job_function else '',
                'start_date': self.start_date,
                'end_date': self.end_date,
                'contract_duration': self.contract_duration or 'PERMANENT',
                'line_manager_name': self.line_manager.full_name if self.line_manager else '',
                'deletion_notes': deletion_notes or '',
                'deleted_by': deleted_by,
                'deleted_at': timezone.now(),
                'employee_still_exists': preserve_original_data,  # True for soft delete, False for hard delete
                'original_data': self._serialize_complete_employee_data(),
                'data_quality': 'COMPLETE' if preserve_original_data else 'BASIC',
                'archive_version': '2.0'
            }
            
            # Create the archive record
            archive = EmployeeArchive.objects.create(**archive_data)
            
            
            return archive
            
        except Exception as e:
            logger.error(f"Failed to create archive record for employee {self.employee_id}: {e}")
            logger.error(f"Archive creation traceback: {traceback.format_exc()}")
            
            # Try to create a minimal archive record as fallback
            try:
                fallback_pk = str(self.pk) if self.pk else 'UNKNOWN'
                minimal_archive = EmployeeArchive.objects.create(
                    original_employee_pk=fallback_pk,
                    original_employee_id=self.employee_id or 'UNKNOWN',
                    full_name=self.full_name or 'Unknown Employee',
                    email=self.user.email if self.user else 'unknown@example.com',
                    job_title=self.job_title or 'Unknown Position',
                    business_function_name=self.business_function.name if self.business_function else 'Unknown',
                    department_name=self.department.name if self.department else 'Unknown',
                    unit_name=None,  # FIXED: Safe to be null
                    job_function_name=self.job_function.name if self.job_function else 'Unknown',
                    start_date=self.start_date or timezone.now().date(),
                    end_date=self.end_date,
                    contract_duration=self.contract_duration or 'PERMANENT',
                    line_manager_name='',
                    deletion_notes=f"Minimal archive due to error: {str(e)}",
                    deleted_by=deleted_by,
                    deleted_at=timezone.now(),
                    employee_still_exists=preserve_original_data,
                    original_data={'error': f'Could not serialize: {str(e)}'},
                    data_quality='MINIMAL',
                    archive_version='2.0'
                )
               
                return minimal_archive
            except Exception as fallback_error:
                logger.error(f"Even minimal archive creation failed: {fallback_error}")
                return None
    
    def restore_from_soft_delete(self, user=None):
        """
        ENHANCED: Restore employee from soft delete, handle vacancy cleanup, and REMOVE archive
        FIXED: Vacancy-ləri mütləq şəkildə silir - HƏLL EDİLMİŞ VERSİYA
        """
        if not self.is_deleted:
            return False, "Employee is not deleted"
        
        try:
            with transaction.atomic():
                # DEBUG: Employee PK-ni və məlumatları logla
                employee_pk = self.pk
                employee_id = self.employee_id
            
                
                # FIXED: Vacancy-ləri tapıb sil - Bütün mümkün variantları yoxla
                related_vacancies = VacantPosition.objects.filter(
                    original_employee_pk=employee_pk
                )
                
              
                
                # Əlavə olaraq, notes sahəsindəki məlumatla da axtarış
                notes_based_vacancies = VacantPosition.objects.filter(
                    notes__icontains=f"vacated by {self.full_name}",
                    is_filled=False
                )
                
                
                all_vacancies = (related_vacancies | notes_based_vacancies).distinct()
                
             
                
                # Vacancy məlumatlarını saxla və sil
                vacancy_info = []
                deleted_vacancy_count = 0
                
                for vacancy in all_vacancies:
                    vacancy_data = {
                        'id': vacancy.id,
                        'position_id': vacancy.position_id,
                        'job_title': vacancy.job_title,
                        'original_employee_pk': vacancy.original_employee_pk,
                        'notes': vacancy.notes[:100] + "..." if len(vacancy.notes) > 100 else vacancy.notes
                    }
                    vacancy_info.append(vacancy_data)
                    
               
                    
                    # VACANCY-Nİ SİL
                    vacancy.delete()
                    deleted_vacancy_count += 1
                    
           
                
                # Verify vacancy deletion - təsdiq et ki, silinib
                remaining_vacancies = VacantPosition.objects.filter(
                    Q(original_employee_pk=employee_pk) | 
                    Q(notes__icontains=f"vacated by {self.full_name}")
                )
                
                if remaining_vacancies.exists():
             
                    for rv in remaining_vacancies:
                        logger.error(f"Remaining vacancy: ID={rv.id}, position_id={rv.position_id}")
                else:
                    logger.info(f"RESTORE SUCCESS: All {deleted_vacancy_count} vacancies successfully deleted")
                
                # Archive record-ları tap və sil
                soft_delete_archives = EmployeeArchive.objects.filter(
                    original_employee_id=employee_id,
                    employee_still_exists=True
                ).order_by('-deleted_at')
                
        
                
                archive_info = []
                for archive in soft_delete_archives:
                    archive_data = {
                        'id': archive.id,
                        'reference': archive.get_archive_reference(),
                        'deleted_at': archive.deleted_at.isoformat() if archive.deleted_at else None
                    }
                    archive_info.append(archive_data)
                    
             
                    archive.delete()
                  
                
              
                self.restore()
                
                # Activity log et
                EmployeeActivity.objects.create(
                    employee=self,
                    activity_type='RESTORED',
                    description=f"Employee {self.full_name} restored from soft deletion. {deleted_vacancy_count} vacancies DELETED. {len(archive_info)} archives deleted.",
                    performed_by=user,
                    metadata={
                        'restored_from_soft_delete': True,
                        'vacancies_deleted': vacancy_info,
                        'archives_deleted': archive_info,
                        'restoration_date': timezone.now().isoformat(),
                        'restored_by': user.username if user else 'System',
                        'original_employee_pk_restored': employee_pk,
                        'total_vacancies_deleted': deleted_vacancy_count,
                        'total_archives_deleted': len(archive_info),
                        'vacancy_deletion_verified': not remaining_vacancies.exists()
                    }
                )
                
               
                
                return True, f"Employee restored successfully. {deleted_vacancy_count} vacancies DELETED. {len(archive_info)} archives deleted."
                
        except Exception as e:
            logger.error(f"Restore failed for employee {self.employee_id}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise e
    def get_contract_duration_choices(self):
        """Get available contract duration choices"""
        return ContractTypeConfig.get_contract_choices()
    
    def get_contract_config(self):
        """Get contract configuration for this employee"""
        try:
            return ContractTypeConfig.objects.get(
                contract_type=self.contract_duration,
                is_active=True
            )
        except ContractTypeConfig.DoesNotExist:
            return None
    
    def clean(self):
        """Validate contract_duration exists in configurations"""
        super().clean()
        if self.contract_duration:
            try:
                ContractTypeConfig.objects.get(
                    contract_type=self.contract_duration,
                    is_active=True
                )
            except ContractTypeConfig.DoesNotExist:
                from django.core.exceptions import ValidationError
                raise ValidationError(f"Contract type '{self.contract_duration}' is not configured or inactive")

    def get_direct_reports_count(self):
        """Get count of direct reports"""
        return self.direct_reports.filter(status__affects_headcount=True, is_deleted=False).count()

    def get_grading_display(self):
        """Get formatted grading display with shorthand"""
        if self.grading_level:
            parts = self.grading_level.split('_')
            if len(parts) == 2:
                position_short, level = parts
                return f"{position_short}-{level}"
        return "No Grade"

    def get_status_preview(self):
        """Get status preview without updating"""
        required_status, reason = self.get_required_status_based_on_contract()
        current_status = self.status
        
        return {
            'current_status': current_status.name if current_status else None,
            'required_status': required_status.name if required_status else None,
            'needs_update': current_status != required_status,
            'reason': reason,
            'contract_type': self.contract_duration,
            'days_since_start': (date.today() - self.start_date).days,
            'contract_end_date': self.contract_end_date
        }

    @classmethod
    def get_combined_with_vacancies(cls, request_params):
        """
        ENHANCED: Get combined list of employees and vacant positions
        """
        # Get active employees
        employees = cls.objects.filter(
            status__affects_headcount=True,
            is_deleted=False
        ).select_related(
            'user', 'business_function', 'department', 'unit', 'job_function',
            'position_group', 'status', 'line_manager'
        )
        
        # Get vacant positions that should be included in headcount
        vacancies = VacantPosition.objects.filter(
            include_in_headcount=True,
            is_filled=False,
            is_deleted=False
        ).select_related(
            'business_function', 'department', 'unit', 'job_function',
            'position_group', 'vacancy_status', 'reporting_to'
        )
        
        # Convert to unified format
        employee_data = []
        for emp in employees:
            emp_data = {
                'id': emp.id,
                'employee_id': emp.employee_id,
                'name': emp.full_name,
                'email': emp.user.email if emp.user else None,
                'job_title': emp.job_title,
                'business_function_name': emp.business_function.name,
                'department_name': emp.department.name,
                'unit_name': emp.unit.name if emp.unit else None,
                'position_group_name': emp.position_group.get_name_display(),
                'status_name': emp.status.name,
                'status_color': emp.status.color,
                'grading_level': emp.grading_level,
                'line_manager_name': emp.line_manager.full_name if emp.line_manager else None,
                'start_date': emp.start_date,
                'is_visible_in_org_chart': emp.is_visible_in_org_chart,
                'is_vacancy': False,
                'created_at': emp.created_at,
                'phone': emp.phone,
                'father_name': emp.father_name,
            }
            employee_data.append(emp_data)
        
        # Add vacancy data
        vacancy_data = []
        for vacancy in vacancies:
            vac_data = vacancy.get_as_employee_data()
            vacancy_data.append(vac_data)
        
        # Combine and return
        combined_data = employee_data + vacancy_data
        
        # Sort by employee_id
        combined_data.sort(key=lambda x: x.get('employee_id', ''))
        
        return combined_data, len(employee_data), len(vacancy_data)
    
    def __str__(self):
        return f"{self.employee_id} - {self.full_name}"

    class Meta:
        ordering = ['employee_id']
        indexes = [
            models.Index(fields=['employee_id']),
            models.Index(fields=['start_date']),
               models.Index(fields=['email']),  # Add index for email lookups
            models.Index(fields=['status']),
            models.Index(fields=['position_group']),
            models.Index(fields=['business_function', 'department']),
            models.Index(fields=['is_deleted']),
            models.Index(fields=['contract_end_date']),
            models.Index(fields=['line_manager']),
        ]

class EmployeeDeletionManager:
    """Utility class for managing employee deletions"""
    
    @staticmethod
    def bulk_soft_delete_with_vacancy_creation(employee_ids, user=None, reason="Bulk restructuring"):
        """Bulk soft delete employees and create vacancies"""
        employees = Employee.objects.filter(id__in=employee_ids, is_deleted=False)
        results = {
            'successful': 0,
            'failed': 0,
            'vacancies_created': [],
            'errors': []
        }
        
        for employee in employees:
            try:
                vacancy = employee.soft_delete_and_create_vacancy(user)
                results['successful'] += 1
                results['vacancies_created'].append({
                    'employee_id': employee.employee_id,
                    'employee_name': employee.full_name,
                    'vacancy_id': vacancy.id,
                    'vacancy_position_id': vacancy.position_id
                })
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"Failed to delete {employee.employee_id}: {str(e)}")
        
        return results
    
    @staticmethod
    def bulk_hard_delete_with_archiving(employee_ids, user=None,):
        """Bulk hard delete employees and create archives"""
        employees = Employee.objects.filter(id__in=employee_ids)
        results = {
            'successful': 0,
            'failed': 0,
            'archives_created': [],
            'errors': []
        }
        
        for employee in employees:
            try:
                # Store info before deletion
                emp_info = {
                    'employee_id': employee.employee_id,
                    'full_name': employee.full_name,
                    'original_employee_pk': employee.pk,
                }
                
                archive = employee.hard_delete_with_archive(user)
                
                if archive:
                 
                    archive.save()
                
                results['successful'] += 1
                results['archives_created'].append({
                    'original_employee_id': emp_info['employee_id'],
                    'original_employee_pk': emp_info['original_employee_pk'],
                    'employee_name': emp_info['full_name'],
                    'archive_id': archive.id if archive else None,
                    'archive_reference': archive.get_archive_reference() if archive else None
                })
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"Failed to delete {employee.employee_id}: {str(e)}")
        
        return results
    
    @staticmethod
    def validate_deletion_request(employee_ids, deletion_type='soft'):
        """Validate bulk deletion request"""
        validation_results = {
            'valid': True,
            'warnings': [],
            'blocking_issues': [],
            'employee_analysis': []
        }
        
        employees = Employee.objects.filter(id__in=employee_ids)
        
        if employees.count() != len(employee_ids):
            validation_results['blocking_issues'].append(
                f"Some employee IDs not found. Expected {len(employee_ids)}, found {employees.count()}"
            )
            validation_results['valid'] = False
        
        for employee in employees:
            analysis = employee.can_be_safely_deleted()
            validation_results['employee_analysis'].append({
                'employee_id': employee.employee_id,
                'employee_name': employee.full_name,
                'can_delete': analysis['can_delete'],
                'issues': analysis['blocking_issues'],
                'warnings': analysis['warnings']
            })
            
            validation_results['warnings'].extend([
                f"{employee.employee_id}: {warning}" for warning in analysis['warnings']
            ])
            validation_results['blocking_issues'].extend([
                f"{employee.employee_id}: {issue}" for issue in analysis['blocking_issues']
            ])
        
        if validation_results['blocking_issues']:
            validation_results['valid'] = False
        
        return validation_results

class EmployeeDocument(SoftDeleteModel):
    DOCUMENT_TYPES = [
        ('CONTRACT', 'Employment Contract'),
        ('ID', 'ID Document'),
        ('CERTIFICATE', 'Certificate'),
        ('CV', 'Curriculum Vitae'),
        ('PERFORMANCE', 'Performance Review'),
        ('MEDICAL', 'Medical Certificate'),
        ('TRAINING', 'Training Certificate'),
        ('OTHER', 'Other'),
    ]
    
    DOCUMENT_STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
        ('ARCHIVED', 'Archived'),
    ]
    
    
    
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=255, help_text="Document name or title")
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, default='OTHER')
    
    # Version field
    version = models.PositiveIntegerField(default=1, help_text="Document version number")
    
    # Actual file field
    document_file = models.FileField(
        upload_to='employee_documents/%Y/%m/',
        help_text="Upload document file",
        null=True,
        blank=True
    )
    
    # Document status field
    document_status = models.CharField(
        max_length=20, 
        choices=DOCUMENT_STATUS_CHOICES, 
        default='ACTIVE',
        help_text="Current status of the document"
    )
    
    # File metadata
    file_size = models.PositiveIntegerField(null=True, blank=True, help_text="File size in bytes")
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    original_filename = models.CharField(max_length=255, blank=True, null=True)
    
    # Document metadata
    description = models.TextField(blank=True, help_text="Document description")
    expiry_date = models.DateField(null=True, blank=True, help_text="Document expiry date")
    is_confidential = models.BooleanField(default=False, help_text="Mark as confidential")
    is_required = models.BooleanField(default=False, help_text="Is this document required for employee?")
    
    notify_before_expiry_days = models.PositiveIntegerField(
        default=30, 
        help_text="Days before expiry to send notification"
    )
    
    # Upload tracking
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_documents')
    
    # File access tracking
    download_count = models.PositiveIntegerField(default=0)
    last_accessed = models.DateTimeField(null=True, blank=True)
    
    # Version control
    replaced_by = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='replaces',
        help_text="Document that replaces this version"
    )
    is_current_version = models.BooleanField(default=True, help_text="Is this the current version?")
    
    # Timestamps from SoftDeleteModel
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        # Auto-populate file metadata
        if self.document_file:
            self.file_size = self.document_file.size
            self.original_filename = self.document_file.name
            # Get MIME type
            import mimetypes
            self.mime_type, _ = mimetypes.guess_type(self.document_file.name)
        
        # Ensure notify_before_expiry_days has a default value
        if self.notify_before_expiry_days is None:
            self.notify_before_expiry_days = 30
        
        # Handle version control more carefully
        if self.pk is None:  # New document
            if not hasattr(self, '_skip_version_check'):
                # Check if there are existing documents with the same name for this employee
                existing_docs = EmployeeDocument.objects.filter(
                    employee=self.employee,
                    name=self.name,
                    document_type=self.document_type,
                    is_deleted=False
                ).exclude(pk=self.pk if self.pk else None).order_by('-version')
                
                if existing_docs.exists() and not self.version:
                    # This is a new version of an existing document
                    latest_doc = existing_docs.first()
                    self.version = latest_doc.version + 1
                    
                    # Mark previous versions as not current
                    existing_docs.update(is_current_version=False)
                elif not self.version:
                    # New document with unique name
                    self.version = 1
        
        # Ensure version is set
        if not self.version:
            self.version = 1
        
        # Ensure is_current_version is set
        if not hasattr(self, 'is_current_version') or self.is_current_version is None:
            self.is_current_version = True
        
        super().save(*args, **kwargs)
    
    def get_file_size_display(self):
        """Human readable file size"""
        if self.file_size:
            if self.file_size < 1024:
                return f"{self.file_size} B"
            elif self.file_size < 1024 * 1024:
                return f"{self.file_size / 1024:.1f} KB"
            else:
                return f"{self.file_size / (1024 * 1024):.1f} MB"
        return "Unknown"
    
    def is_image(self):
        """Check if document is an image"""
        if self.mime_type:
            return self.mime_type.startswith('image/')
        return False
    
    def is_pdf(self):
        """Check if document is a PDF"""
        return self.mime_type == 'application/pdf'
    
    def is_expired(self):
        """Check if document is expired"""
        return self.expiry_date and self.expiry_date < date.today()
    
    def increment_download_count(self):
        """Increment download counter"""
        self.download_count += 1
        self.last_accessed = timezone.now()
        self.save(update_fields=['download_count', 'last_accessed'])
    
    def get_version_history(self):
        """Get all versions of this document"""
        if not self.name or not self.employee_id:
            return EmployeeDocument.objects.none()
        
        return EmployeeDocument.objects.filter(
            employee=self.employee,
            name=self.name,
            document_type=self.document_type
        ).order_by('-version')
    
    def get_previous_version(self):
        """Get the previous version of this document"""
        try:
            return EmployeeDocument.objects.filter(
                employee=self.employee,
                name=self.name,
                document_type=self.document_type,
                version__lt=self.version,
                is_deleted=False
            ).order_by('-version').first()
        except:
            return None
    
    def get_next_version(self):
        """Get the next version of this document"""
        return self.replaced_by
    
    def __str__(self):
        version_str = f" (v{self.version})" if self.version > 1 else ""
        return f"{self.employee.full_name} - {self.name}{version_str}"
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Employee Document"
        verbose_name_plural = "Employee Documents"
        # Unique constraint to prevent duplicate current versions
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'name', 'document_type'],
                condition=models.Q(is_current_version=True, is_deleted=False),
                name='unique_current_version_per_employee_document'
            )
        ]

class EmployeeActivity(models.Model):
   
    ACTIVITY_TYPES = [
        ('CREATED', 'Employee Created'),
        ('UPDATED', 'Employee Updated'),
        ('STATUS_CHANGED', 'Status Changed'),
        ('MANAGER_CHANGED', 'Manager Changed'),
        ('POSITION_CHANGED', 'Position Changed'),
        ('CONTRACT_UPDATED', 'Contract Updated'),
        ('DOCUMENT_UPLOADED', 'Document Uploaded'),
        ('GRADE_CHANGED', 'Grade Changed'),
        ('TAG_ADDED', 'Tag Added'),
        ('TAG_REMOVED', 'Tag Removed'),
        ('SOFT_DELETED', 'Employee Soft Deleted'),
        ('RESTORED', 'Employee Restored'),
        ('BULK_CREATED', 'Bulk Created'),
        ('STATUS_AUTO_UPDATED', 'Status Auto Updated'),
        # YENİ ACTIVITY TYPES LAZIMDIR:
        ('ASSET_ACCEPTED', 'Asset Accepted'),  # 14 hərf
        ('ASSET_CLARIFICATION_REQUESTED', 'Asset Clarification Requested'),  # 29 hərf - ÇOX UZUN!
    ]
    
  
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    description = models.TextField()
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee.full_name} - {self.activity_type}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Employee Activity"
        verbose_name_plural = "Employee Activities"

class ContractStatusManager:
    """Helper class for managing contract-based status transitions"""
    
    @staticmethod
    def bulk_update_employee_statuses(employee_ids=None, force_update=False):
        """Bulk update employee statuses based on contract configurations"""
        # Import here to avoid circular import
        from .status_management import EmployeeStatusManager
        
        if employee_ids:
            employees = Employee.objects.filter(id__in=employee_ids)
        else:
            employees = Employee.objects.all()
        
        updated_count = 0
        for employee in employees:
            if EmployeeStatusManager.update_employee_status(employee, force_update):
                updated_count += 1
        
    
        return updated_count
    
    @staticmethod
    def get_employees_needing_status_update():
        """Get employees whose status needs to be updated"""
        # Import here to avoid circular import
        from .status_management import EmployeeStatusManager
        
        employees_to_update = []
        
        for employee in Employee.objects.all():
            preview = EmployeeStatusManager.get_status_preview(employee)
            if preview['needs_update']:
                employees_to_update.append({
                    'employee': employee,
                    'current_status': preview['current_status'],
                    'required_status': preview['required_status'],
                    'reason': preview['reason']
                })
        
        return employees_to_update
    
    @staticmethod
    def get_contract_expiring_soon(days=30):
        """Get employees whose contracts are expiring soon"""
        expiry_date = date.today() + timedelta(days=days)
        
        return Employee.objects.filter(
            contract_end_date__lte=expiry_date,
            contract_end_date__gte=date.today(),
            contract_duration__in=['3_MONTHS', '6_MONTHS', '1_YEAR', '2_YEARS', '3_YEARS'],
            is_deleted=False
        ).select_related('status', 'business_function', 'department')

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Employee)
def employee_post_save_handler(sender, instance, created, **kwargs):
    """Handle employee post-save operations"""
    if created:
        # Log creation activity
        EmployeeActivity.objects.create(
            employee=instance,
            activity_type='CREATED',
            description=f"Employee {instance.full_name} was created",
            performed_by=getattr(instance, '_created_by_user', None),
            metadata={
                'employee_id': instance.employee_id,
                'contract_type': instance.contract_duration,
                'initial_status': instance.status.name if instance.status else None
            }
        )
        
