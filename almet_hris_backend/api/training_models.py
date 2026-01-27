# api/training_models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Employee, SoftDeleteModel



class Training(SoftDeleteModel):
    """Əsas training modeli"""
    
    
    
    # Basic Information
    training_id = models.CharField(max_length=50, unique=True, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()

    

    

    is_active = models.BooleanField(default=True)
    
    # Filters - Business Structure
    business_functions = models.ManyToManyField(
        'BusinessFunction', 
        blank=True,
        help_text="Specific business functions for this training"
    )
    departments = models.ManyToManyField(
        'Department', 
        blank=True,
        help_text="Specific departments for this training"
    )
    position_groups = models.ManyToManyField(
        'PositionGroup', 
        blank=True,
        help_text="Specific position groups for this training"
    )
    
    # Completion Settings
    requires_completion = models.BooleanField(default=False)
    completion_deadline_days = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Days after assignment to complete"
    )
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_trainings')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.training_id:
            # Auto-generate training ID
            last_training = Training.objects.all().order_by('-id').first()
            if last_training and last_training.training_id:
                try:
                    last_num = int(last_training.training_id.replace('TRN', ''))
                    new_num = last_num + 1
                except:
                    new_num = 1
            else:
                new_num = 1
            self.training_id = f'TRN{new_num:04d}'
        
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = [ '-created_at']
        verbose_name = 'Training'
        verbose_name_plural = 'Trainings'
    
    def __str__(self):
        return f"{self.training_id} - {self.title}"


class TrainingMaterial(SoftDeleteModel):
    """Training materials (PDF, video, etc.)"""
    
    training = models.ForeignKey(
        Training, 
        on_delete=models.CASCADE, 
        related_name='materials'
    )
    
    # File upload
    file = models.FileField(
        upload_to='training_materials/%Y/%m/',
        null=True,
        blank=True,
        help_text="Upload file for PDF, Video, etc."
    )
    
    # Metadata
    file_size = models.BigIntegerField(
        null=True, 
        blank=True, 
        help_text="File size in bytes"
    )
    
    uploaded_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['training', 'created_at']
        verbose_name = 'Training Material'
        verbose_name_plural = 'Training Materials'
    
    def __str__(self):
        filename = self.file.name.split('/')[-1] if self.file else 'No file'
        return f"{self.training.training_id} - {filename}"
class TrainingAssignment(SoftDeleteModel):
    """Training assignment to employees"""
    
    STATUS_CHOICES = [
        ('ASSIGNED', 'Assigned'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    # Assignment Details
    training = models.ForeignKey(Training, on_delete=models.CASCADE, related_name='assignments')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='training_assignments')
    
    # Status & Dates
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ASSIGNED')
    assigned_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)
    started_date = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)
    
    # Progress Tracking
    progress_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Completion progress 0-100"
    )
    materials_completed = models.ManyToManyField(
        TrainingMaterial,
        blank=True,
        help_text="Materials that have been viewed/completed"
    )
    
    # Completion Details
    completion_notes = models.TextField(blank=True)
    completion_certificate_generated = models.BooleanField(default=False)
    
    # Assignment Metadata
    assigned_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='assigned_trainings'
    )
    is_mandatory = models.BooleanField(
        default=False,
        help_text="Is this assignment mandatory for the employee"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-assigned_date']
        unique_together = ['training', 'employee']
        verbose_name = 'Training Assignment'
        verbose_name_plural = 'Training Assignments'
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.training.title}"
    
    def calculate_progress(self):
        """Calculate progress based on completed materials"""
        if self.status == 'COMPLETED':
            return 100.0
        
        # Remove is_mandatory filter
        total_required = self.training.materials.filter(is_deleted=False).count()
        if total_required == 0:
            return 0.0
        
        # Remove is_mandatory filter
        completed = self.materials_completed.filter(is_deleted=False).count()
        progress = (completed / total_required) * 100
        
        self.progress_percentage = round(progress, 2)
        self.save(update_fields=['progress_percentage'])
        
        return self.progress_percentage
    
    def check_completion(self):
        """Check if training is completed"""
        # Remove is_mandatory filter
        total_required = self.training.materials.filter(is_deleted=False).count()
        completed = self.materials_completed.filter(is_deleted=False).count()
        
        if total_required > 0 and completed >= total_required:
            self.status = 'COMPLETED'
            self.completed_date = timezone.now()
            self.progress_percentage = 100
            self.save()
            return True
        
        return False
    def is_overdue(self):
        """Check if assignment is overdue"""
        if self.status not in ['COMPLETED', 'CANCELLED'] and self.due_date:
            return timezone.now().date() > self.due_date
        return False

class TrainingActivity(models.Model):
    """Training activity log"""
    
    ACTIVITY_TYPES = [
        ('ASSIGNED', 'Training Assigned'),
        ('STARTED', 'Training Started'),
        ('MATERIAL_VIEWED', 'Material Viewed'),
        ('PROGRESS_UPDATED', 'Progress Updated'),
        ('COMPLETED', 'Training Completed'),
        ('CANCELLED', 'Training Cancelled'),
    ]
    
    assignment = models.ForeignKey(
        TrainingAssignment, 
        on_delete=models.CASCADE, 
        related_name='activities'
    )
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    description = models.TextField()
    
    material = models.ForeignKey(
        TrainingMaterial,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Related material if applicable"
    )
    
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Training Activity'
        verbose_name_plural = 'Training Activities'
    
    def __str__(self):
        return f"{self.assignment.employee.full_name} - {self.activity_type}"