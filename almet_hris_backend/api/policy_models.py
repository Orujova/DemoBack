# api/policy_models.py - UPDATED with PolicyCompany Model

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
import os
import logging

logger = logging.getLogger(__name__)


class PolicyCompany(models.Model):
    """
    Manual company entries for policies (independent of BusinessFunction)
    
    Allows adding companies that don't have a BusinessFunction in the system
    """
    
    name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Company name (e.g., 'External Partner', 'Client Company')"
    )
    
    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Company code (e.g., 'EXT', 'CLIENT')"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description of the company"
    )
    
    icon = models.CharField(
        max_length=10,
        default='🏢',
        help_text="Emoji icon for the company"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this company is active"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_policy_companies',
        help_text="User who created this company"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['code', 'name']
        verbose_name = "Policy Company"
        verbose_name_plural = "Policy Companies"
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class PolicyFolder(models.Model):
    """
    Policy folders organized by business function OR manual company
    
    Each folder belongs to EITHER a business function OR a manual company
    """
    
    # ONE of these must be set (not both)
    business_function = models.ForeignKey(
        'BusinessFunction',
        on_delete=models.CASCADE,
        related_name='policy_folders',
        null=True,
        blank=True,
        help_text="Business function this folder belongs to"
    )
    
    policy_company = models.ForeignKey(
        PolicyCompany,
        on_delete=models.CASCADE,
        related_name='policy_folders',
        null=True,
        blank=True,
        help_text="Manual company this folder belongs to"
    )
    
    name = models.CharField(
        max_length=200,
        help_text="Folder name (e.g., 'Employment Lifecycle', 'Legal & Compliance')"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description of what this folder contains"
    )
    
    icon = models.CharField(
        max_length=10,
        default='📁',
        help_text="Emoji icon for the folder"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this folder is active and visible"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_policy_folders',
        help_text="User who created this folder"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Policy Folder"
        verbose_name_plural = "Policy Folders"
        indexes = [
            models.Index(fields=['business_function', 'is_active']),
            models.Index(fields=['policy_company', 'is_active']),
            models.Index(fields=['created_at']),
        ]
    
    def get_company_name(self):
        """Get the company name (from BusinessFunction or PolicyCompany)"""
        if self.business_function:
            return self.business_function.name
        elif self.policy_company:
            return self.policy_company.name
        return "Unknown"
    
    def get_company_code(self):
        """Get the company code"""
        if self.business_function:
            return self.business_function.code
        elif self.policy_company:
            # Generate code from name for PolicyCompany
            return self.policy_company.name[:4].upper().replace(' ', '')
        return "N/A"
    
    def get_policy_count(self):
        """Get count of active policies in this folder"""
        return self.policies.filter(is_active=True).count()
    
    def get_total_views(self):
        """Get total view count for all policies in folder"""
        return sum(policy.view_count for policy in self.policies.filter(is_active=True))
    
    def get_total_downloads(self):
        """Get total download count for all policies in folder"""
        return sum(policy.download_count for policy in self.policies.filter(is_active=True))
    
    def clean(self):
        """Validate folder data"""
        super().clean()
        
        # MUST have exactly one: business_function OR policy_company
        if not self.business_function and not self.policy_company:
            raise ValidationError(
                "Folder must belong to either a Business Function or a Company"
            )
        
        if self.business_function and self.policy_company:
            raise ValidationError(
                "Folder cannot belong to both Business Function and Company. Choose one."
            )
        
        # Check for duplicate names within same company
        parent = self.business_function or self.policy_company
        if parent:
            if self.business_function:
                existing = PolicyFolder.objects.filter(
                    business_function=self.business_function,
                    name__iexact=self.name
                ).exclude(pk=self.pk)
            else:
                existing = PolicyFolder.objects.filter(
                    policy_company=self.policy_company,
                    name__iexact=self.name
                ).exclude(pk=self.pk)
            
            if existing.exists():
                raise ValidationError(
                    f"A folder with name '{self.name}' already exists in {parent}"
                )
    
    def __str__(self):
        code = self.get_company_code()
        return f"{code} - {self.name}"


class CompanyPolicy(models.Model):
    """
    Company policy documents
    
    Stores policy documents (PDFs) with metadata, versioning, and tracking
    """
    
    # Relationships
    folder = models.ForeignKey(
        PolicyFolder,
        on_delete=models.CASCADE,
        related_name='policies',
        help_text="Folder this policy belongs to"
    )
    
    # Basic Information
    title = models.CharField(
        max_length=300,
        help_text="Policy title (e.g., 'Hiring Procedure', 'Vacation Policy')"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Brief description of the policy"
    )
    
    # Document File
    policy_file = models.FileField(
        upload_to='company_policies/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        help_text="Policy document (PDF only, max 10MB)"
    )
    
    file_size = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="File size in bytes (auto-calculated)"
    )
    
    requires_acknowledgment = models.BooleanField(
        default=False,
        help_text="Do employees need to acknowledge reading this policy?"
    )
    
    # Tracking
    download_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this policy has been downloaded"
    )
    
    view_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this policy has been viewed"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this policy is active and visible"
    )
    
    # User Tracking
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_policies',
        help_text="User who created this policy"
    )
    
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_policies',
        help_text="User who last updated this policy"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Company Policy"
        verbose_name_plural = "Company Policies"
        indexes = [
            models.Index(fields=['folder', 'is_active']),
            models.Index(fields=['-updated_at']),
            models.Index(fields=['requires_acknowledgment']),
        ]
    
    def save(self, *args, **kwargs):
        """Auto-calculate file size"""
        if self.policy_file:
            try:
                self.file_size = self.policy_file.size
            except Exception as e:
                logger.warning(f"Could not calculate file size: {e}")
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate policy data"""
        super().clean()
        
        # Validate file size (10MB max)
        if self.policy_file:
            if self.policy_file.size > 10 * 1024 * 1024:
                raise ValidationError("File size cannot exceed 10MB")
    
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
    
    def increment_view_count(self):
        """Increment view counter"""
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    def increment_download_count(self):
        """Increment download counter"""
        self.download_count += 1
        self.save(update_fields=['download_count'])
    
    def get_company_name(self):
        """Get the company this policy belongs to"""
        return self.folder.get_company_name() if self.folder else "Unknown"
    
    def get_company_code(self):
        """Get company code"""
        return self.folder.get_company_code() if self.folder else "N/A"
    
    def get_acknowledgment_count(self):
        """Get count of employee acknowledgments"""
        return self.acknowledgments.count()
    
    def get_acknowledgment_percentage(self):
        """Get percentage of employees who acknowledged this policy"""
        if not self.requires_acknowledgment:
            return None
        
        from .models import Employee
        total_employees = Employee.objects.filter(is_deleted=False).count()
        
        if total_employees == 0:
            return 0
        
        acknowledged = self.get_acknowledgment_count()
        return round((acknowledged / total_employees) * 100, 1)
    
    def is_acknowledged_by_employee(self, employee):
        """Check if employee has acknowledged this policy"""
        return self.acknowledgments.filter(employee=employee).exists()
    
    def __str__(self):
        code = self.get_company_code()
        return f"{code} - {self.title}"


class PolicyAcknowledgment(models.Model):
    """
    Track employee acknowledgments of policies
    """
    
    policy = models.ForeignKey(
        CompanyPolicy,
        on_delete=models.CASCADE,
        related_name='acknowledgments',
        help_text="Policy that was acknowledged"
    )
    
    employee = models.ForeignKey(
        'Employee',
        on_delete=models.CASCADE,
        related_name='policy_acknowledgments',
        help_text="Employee who acknowledged the policy"
    )
    
    acknowledged_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the acknowledgment was made"
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address from which acknowledgment was made"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Additional notes or comments from employee"
    )
    
    class Meta:
        unique_together = ['policy', 'employee']
        ordering = ['-acknowledged_at']
        verbose_name = "Policy Acknowledgment"
        verbose_name_plural = "Policy Acknowledgments"
        indexes = [
            models.Index(fields=['policy', 'employee']),
            models.Index(fields=['-acknowledged_at']),
            models.Index(fields=['policy', '-acknowledged_at']),
        ]
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.policy.title}"


# Signal handlers
from django.db.models.signals import pre_delete
from django.dispatch import receiver

@receiver(pre_delete, sender=CompanyPolicy)
def delete_policy_file(sender, instance, **kwargs):
    """Delete policy file when policy is deleted"""
    if instance.policy_file:
        try:
            if os.path.isfile(instance.policy_file.path):
                os.remove(instance.policy_file.path)
                logger.info(f"Deleted policy file: {instance.policy_file.path}")
        except Exception as e:
            logger.error(f"Error deleting policy file: {e}")