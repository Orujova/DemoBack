# api/procedure_models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
import os
import logging

logger = logging.getLogger(__name__)


class ProcedureCompany(models.Model):
    """
    Manual company entries for procedures (independent of BusinessFunction)
    """
    
    name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Company name (e.g., 'External Partner', 'Client Company')"
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
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this company is active"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_procedure_companies',
        help_text="User who created this company"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Procedure Company"
        verbose_name_plural = "Procedure Companies"
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return self.name


class ProcedureFolder(models.Model):
    """
    Procedure folders organized by business function OR manual company
    """
    
    business_function = models.ForeignKey(
        'BusinessFunction',
        on_delete=models.CASCADE,
        related_name='procedure_folders',
        null=True,
        blank=True,
        help_text="Business function this folder belongs to"
    )
    
    procedure_company = models.ForeignKey(
        ProcedureCompany,
        on_delete=models.CASCADE,
        related_name='procedure_folders',
        null=True,
        blank=True,
        help_text="Manual company this folder belongs to"
    )
    
    name = models.CharField(
        max_length=200,
        help_text="Folder name (e.g., 'Operations', 'Quality Control')"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description of what this folder contains"
    )
    
    icon = models.CharField(
        max_length=10,
        default='📋',
        help_text="Emoji icon for the folder"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this folder is active and visible"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_procedure_folders',
        help_text="User who created this folder"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Procedure Folder"
        verbose_name_plural = "Procedure Folders"
        indexes = [
            models.Index(fields=['business_function', 'is_active']),
            models.Index(fields=['procedure_company', 'is_active']),
            models.Index(fields=['created_at']),
        ]
    
    def get_company_name(self):
        if self.business_function:
            return self.business_function.name
        elif self.procedure_company:
            return self.procedure_company.name
        return "Unknown"
    
    def get_company_code(self):
        if self.business_function:
            return self.business_function.code
        elif self.procedure_company:
            return self.procedure_company.name[:4].upper().replace(' ', '')
        return "N/A"
    
    def get_procedure_count(self):
        return self.procedures.filter(is_active=True).count()
    
    def get_total_views(self):
        return sum(proc.view_count for proc in self.procedures.filter(is_active=True))
    
    def get_total_downloads(self):
        return sum(proc.download_count for proc in self.procedures.filter(is_active=True))
    
    def clean(self):
        super().clean()
        
        if not self.business_function and not self.procedure_company:
            raise ValidationError(
                "Folder must belong to either a Business Function or a Company"
            )
        
        if self.business_function and self.procedure_company:
            raise ValidationError(
                "Folder cannot belong to both Business Function and Company"
            )
        
        parent = self.business_function or self.procedure_company
        if parent:
            if self.business_function:
                existing = ProcedureFolder.objects.filter(
                    business_function=self.business_function,
                    name__iexact=self.name
                ).exclude(pk=self.pk)
            else:
                existing = ProcedureFolder.objects.filter(
                    procedure_company=self.procedure_company,
                    name__iexact=self.name
                ).exclude(pk=self.pk)
            
            if existing.exists():
                raise ValidationError(
                    f"A folder with name '{self.name}' already exists in {parent}"
                )
    
    def __str__(self):
        code = self.get_company_code()
        return f"{code} - {self.name}"


class CompanyProcedure(models.Model):
    """
    Company procedure documents
    """
    
    folder = models.ForeignKey(
        ProcedureFolder,
        on_delete=models.CASCADE,
        related_name='procedures',
        help_text="Folder this procedure belongs to"
    )
    
    title = models.CharField(
        max_length=300,
        help_text="Procedure title (e.g., 'Purchase Request Process', 'Quality Check')"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Brief description of the procedure"
    )
    
    procedure_file = models.FileField(
        upload_to='company_procedures/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        help_text="Procedure document (PDF only, max 10MB)"
    )
    
    file_size = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="File size in bytes (auto-calculated)"
    )
    
    download_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this procedure has been downloaded"
    )
    
    view_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this procedure has been viewed"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this procedure is active and visible"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_procedures',
        help_text="User who created this procedure"
    )
    
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_procedures',
        help_text="User who last updated this procedure"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Company Procedure"
        verbose_name_plural = "Company Procedures"
        indexes = [
            models.Index(fields=['folder', 'is_active']),
            models.Index(fields=['-updated_at']),
        ]
    
    def save(self, *args, **kwargs):
        if self.procedure_file:
            try:
                self.file_size = self.procedure_file.size
            except Exception as e:
                logger.warning(f"Could not calculate file size: {e}")
        
        super().save(*args, **kwargs)
    
    def clean(self):
        super().clean()
        
        if self.procedure_file:
            if self.procedure_file.size > 10 * 1024 * 1024:
                raise ValidationError("File size cannot exceed 10MB")
    
    def get_file_size_display(self):
        if self.file_size:
            if self.file_size < 1024:
                return f"{self.file_size} B"
            elif self.file_size < 1024 * 1024:
                return f"{self.file_size / 1024:.1f} KB"
            else:
                return f"{self.file_size / (1024 * 1024):.1f} MB"
        return "Unknown"
    
    def increment_view_count(self):
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    def increment_download_count(self):
        self.download_count += 1
        self.save(update_fields=['download_count'])
    
    def get_company_name(self):
        return self.folder.get_company_name() if self.folder else "Unknown"
    
    def get_company_code(self):
        return self.folder.get_company_code() if self.folder else "N/A"
    
    def __str__(self):
        code = self.get_company_code()
        return f"{code} - {self.title}"


# Signal handlers
from django.db.models.signals import pre_delete
from django.dispatch import receiver

@receiver(pre_delete, sender=CompanyProcedure)
def delete_procedure_file(sender, instance, **kwargs):
    """Delete procedure file when procedure is deleted"""
    if instance.procedure_file:
        try:
            if os.path.isfile(instance.procedure_file.path):
                os.remove(instance.procedure_file.path)
                logger.info(f"Deleted procedure file: {instance.procedure_file.path}")
        except Exception as e:
            logger.error(f"Error deleting procedure file: {e}")