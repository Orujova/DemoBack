# api/handover_models.py - CORRECTED VERSION WITHOUT OLD METHODS
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Employee, SoftDeleteModel
import os
import logging

logger = logging.getLogger(__name__)


class HandoverType(SoftDeleteModel):
    """Handover Types - Vacation, Business Trip, Resignation, Other"""
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='handover_type_updates'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "Handover Type"
        verbose_name_plural = "Handover Types"
        db_table = 'handover_types'


class HandoverRequest(SoftDeleteModel):
    """Main Handover Request Model"""
    
    STATUS_CHOICES = [
        ('CREATED', 'Created'),
        ('SIGNED_BY_HANDING_OVER', 'Signed by Handing Over'),
        ('SIGNED_BY_TAKING_OVER', 'Signed by Taking Over'),
        ('APPROVED_BY_LINE_MANAGER', 'Approved by Line Manager'),
        ('REJECTED', 'Rejected'),
        ('NEED_CLARIFICATION', 'Need Clarification'),
        ('RESUBMITTED', 'Resubmitted'),
        ('TAKEN_OVER', 'Taken Over'),
        ('TAKEN_BACK', 'Taken Back'),
    ]
    
    # Request identification
    request_id = models.CharField(max_length=20, unique=True, editable=False)
    
    # Employees
    handing_over_employee = models.ForeignKey(
        Employee, 
        on_delete=models.CASCADE, 
        related_name='handovers_given'
    )
    taking_over_employee = models.ForeignKey(
        Employee, 
        on_delete=models.CASCADE, 
        related_name='handovers_received'
    )
    
    # Handover details
    handover_type = models.ForeignKey(HandoverType, on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True) 
    
    # ★ 5 ADDITIONAL INFORMATION FIELDS ★
    contacts = models.TextField(
        blank=True, 
        help_text="Related contacts with their roles and contact information"
    )
    access_info = models.TextField(
        blank=True, 
        help_text="System access information, usernames, password locations"
    )
    documents_info = models.TextField(
        blank=True, 
        help_text="Document and file locations, shared drives"
    )
    open_issues = models.TextField(
        blank=True, 
        help_text="Unresolved problems, pending actions, known issues"
    )
    notes = models.TextField(
        blank=True, 
        help_text="Additional notes, tips, recommendations"
    )
    
    # Approvers
    line_manager = models.ForeignKey(
        Employee, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='handovers_to_approve'
    )
    
    # Status
    status = models.CharField(
        max_length=30, 
        choices=STATUS_CHOICES, 
        default='CREATED'
    )
    
    # Handing Over signatures
    ho_signed = models.BooleanField(default=False)
    ho_signed_date = models.DateTimeField(null=True, blank=True)
    ho_signed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='ho_signatures'
    )
    
    # Taking Over signatures
    to_signed = models.BooleanField(default=False)
    to_signed_date = models.DateTimeField(null=True, blank=True)
    to_signed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='to_signatures'
    )
    
    # Line Manager Approval
    lm_approved = models.BooleanField(default=False)
    lm_approved_date = models.DateTimeField(null=True, blank=True)
    lm_approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='lm_handover_approvals'
    )
    lm_comment = models.TextField(blank=True)
    lm_clarification_comment = models.TextField(blank=True)
    
    # Rejection
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='handover_rejections'
    )
    rejection_reason = models.TextField(blank=True)
    
    # Takeover
    taken_over = models.BooleanField(default=False)
    taken_over_date = models.DateTimeField(null=True, blank=True)
    taken_back = models.BooleanField(default=False)
    taken_back_date = models.DateTimeField(null=True, blank=True)
    
    # System fields
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Handover Request"
        verbose_name_plural = "Handover Requests"
        db_table = 'handover_requests'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.request_id} - {self.handing_over_employee.full_name} → {self.taking_over_employee.full_name}"
    
    def clean(self):
        """Validation"""
        errors = {}
        
        # ✅ Yalnız end_date varsa check et
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            errors['end_date'] = "End date must be after start date"
        
        if self.handing_over_employee == self.taking_over_employee:
            errors['taking_over_employee'] = "Handing over and taking over cannot be the same person"
        
        if errors:
            raise ValidationError(errors)
    
    # api/handover_models.py - COMPLETE save() method

    def save(self, *args, **kwargs):
        # Generate request ID
        if not self.request_id:
            year = timezone.now().year
            last = HandoverRequest.objects.filter(
                request_id__startswith=f'HO{year}'
            ).order_by('-request_id').first()
            num = int(last.request_id[6:]) + 1 if last else 1
            self.request_id = f'HO{year}{num:04d}'
        
        is_new = self.pk is None
        requester_employee = None
        
        # Get requester's employee profile
        if self.created_by:
            try:
                requester_employee = Employee.objects.get(user=self.created_by, is_deleted=False)
            except Employee.DoesNotExist:
                pass
        
        # ⭐ AUTO-ASSIGN LINE MANAGER
        if not self.line_manager and requester_employee:
            # SCENARIO 1: User creates handover for themselves (as HO)
            if self.handing_over_employee == requester_employee:
                if self.handing_over_employee.line_manager:
                    self.line_manager = self.handing_over_employee.line_manager
            
            # SCENARIO 2: Manager creates handover for their employee
            elif self.handing_over_employee.line_manager == requester_employee:
                self.line_manager = requester_employee
            
            # SCENARIO 3: Someone else (e.g., HR/Admin) creates handover
            else:
                if self.handing_over_employee.line_manager:
                    self.line_manager = self.handing_over_employee.line_manager
        
        self.clean()
        
        # ⭐ AUTO-SIGN HO if creator is HO (NEW LOGIC)
        if is_new and requester_employee:
            # If requester is creating handover for themselves (HO)
            if self.handing_over_employee == requester_employee and not self.ho_signed:
                self.ho_signed = True
                self.ho_signed_date = timezone.now()
                self.ho_signed_by = self.created_by
                self.status = 'SIGNED_BY_HANDING_OVER'
             
        
        super().save(*args, **kwargs)
        
        # ⭐ Log auto-sign activity if it happened
        if is_new and requester_employee and self.handing_over_employee == requester_employee:
            if self.ho_signed:
                HandoverActivity.objects.create(
                    handover=self,
                    actor=self.created_by,
                    action='Auto-signed by Handing Over employee (creator)',
                    comment='Handover automatically signed as creator is HO.',
                    status=self.status
                )
        
        # ⭐ Send appropriate email notification
        if is_new:
            try:
                from .handover_email_service import handover_email_service
                
                # If already signed by HO (auto-signed), notify TO
                if self.ho_signed:
              
                    
                    result = handover_email_service.notify_to_signature_needed(self)
                    
                    if result:
                        logger.info(f"✅ Email sent successfully to TO")
                    else:
                        logger.error(f"❌ Failed to send email to TO")
                else:
                  
                    
                    result = handover_email_service.notify_handover_created(self)
                    
                    if result:
                        logger.info(f"✅ Email sent successfully to HO")
                    else:
                        logger.error(f"❌ Failed to send email to HO")
                        
            except Exception as e:
                logger.error(f"❌ Exception sending creation email: {e}")
                import traceback
                logger.error(traceback.format_exc())
    
    
    
    def sign_by_handing_over(self, user):
        """Sign as Handing Over employee"""
        self.ho_signed = True
        self.ho_signed_date = timezone.now()
        self.ho_signed_by = user
        self.status = 'SIGNED_BY_HANDING_OVER'
        self.save()
        
        # Log activity
        self.log_activity(
            user=user,
            action='Signed by Handing Over employee',
            comment='Handover signed by handing over employee.'
        )
        
        # ⭐ Send notification to Taking Over employee
        try:
            from .handover_email_service import handover_email_service
            handover_email_service.notify_to_signature_needed(self)
        except Exception as e:
            logger.error(f"Failed to send TO signature email: {e}")
    
    def sign_by_taking_over(self, user):
        """Sign as Taking Over employee"""
        if not self.ho_signed:
            raise ValidationError("Handing over employee must sign first")
        
        self.to_signed = True
        self.to_signed_date = timezone.now()
        self.to_signed_by = user
        self.status = 'SIGNED_BY_TAKING_OVER'
        self.save()
        
        # Log activity
        self.log_activity(
            user=user,
            action='Signed by Taking Over employee',
            comment='Handover signed by taking over employee.'
        )
        
        # ⭐ Send notification to Line Manager
        if self.line_manager:
            try:
                from .handover_email_service import handover_email_service
                handover_email_service.notify_lm_approval_needed(self)
            except Exception as e:
                logger.error(f"Failed to send LM approval email: {e}")
    
    def approve_by_line_manager(self, user, comment=''):
        """Approve as Line Manager"""
        if not self.to_signed:
            raise ValidationError("Both employees must sign first")
        
        self.lm_approved = True
        self.lm_approved_date = timezone.now()
        self.lm_approved_by = user
        self.lm_comment = comment
        self.status = 'APPROVED_BY_LINE_MANAGER'
        self.save()
        
        # Log activity
        self.log_activity(
            user=user,
            action='Approved by Line Manager',
            comment=comment or 'Approved by line manager.'
        )
        
        # ⭐ Notify both employees and TO about takeover readiness
        try:
            from .handover_email_service import handover_email_service
            handover_email_service.notify_approved(self)
            handover_email_service.notify_takeover_ready(self)
        except Exception as e:
            logger.error(f"Failed to send approval emails: {e}")
    
    def reject_by_line_manager(self, user, reason):
        """Reject as Line Manager"""
        if not reason:
            raise ValidationError("Rejection reason is required")
        
        self.status = 'REJECTED'
        self.rejected_at = timezone.now()
        self.rejected_by = user
        self.rejection_reason = reason
        self.save()
        
        # Log activity
        self.log_activity(
            user=user,
            action='Rejected by Line Manager',
            comment=reason
        )
        
        # ⭐ Notify both employees
        try:
            from .handover_email_service import handover_email_service
            handover_email_service.notify_rejected(self)
        except Exception as e:
            logger.error(f"Failed to send rejection email: {e}")
    
    def request_clarification(self, user, clarification_comment):
        """Request clarification as Line Manager"""
        if not clarification_comment:
            raise ValidationError("Clarification comment is required")
        
        self.status = 'NEED_CLARIFICATION'
        self.lm_clarification_comment = clarification_comment
        self.save()
        
        # Log activity
        self.log_activity(
            user=user,
            action='Clarification Requested',
            comment=clarification_comment
        )
        
        # ⭐ Notify HO employee
        try:
            from .handover_email_service import handover_email_service
            handover_email_service.notify_clarification_requested(self)
        except Exception as e:
            logger.error(f"Failed to send clarification email: {e}")
    
    def resubmit_after_clarification(self, user, response_comment):
        """Resubmit after clarification"""
        if self.status != 'NEED_CLARIFICATION':
            raise ValidationError("Status must be 'Need Clarification'")
        
        if not response_comment:
            raise ValidationError("Response comment is required")
        
        self.status = 'SIGNED_BY_TAKING_OVER'
        self.lm_clarification_comment = ''
        self.save()
        
        # Log activity
        self.log_activity(
            user=user,
            action='Resubmitted after clarification',
            comment=response_comment
        )
        
        # ⭐ Notify LM
        try:
            from .handover_email_service import handover_email_service
            handover_email_service.notify_resubmitted(self)
        except Exception as e:
            logger.error(f"Failed to send resubmission email: {e}")
    
    def takeover(self, user, comment=''):
        """Take over responsibilities"""
        if self.status != 'APPROVED_BY_LINE_MANAGER':
            raise ValidationError("Status must be 'Approved by Line Manager'")
        
        self.taken_over = True
        self.taken_over_date = timezone.now()
        self.status = 'TAKEN_OVER'
        self.save()
        
        # Log activity
        self.log_activity(
            user=user,
            action='Responsibilities Taken Over',
            comment=comment or 'Taken over.'
        )
        
        # ⭐ Notify HO employee
        try:
            from .handover_email_service import handover_email_service
            handover_email_service.notify_taken_over(self)
        except Exception as e:
            logger.error(f"Failed to send takeover email: {e}")
    
    def takeback(self, user, comment=''):
        """Take back responsibilities"""
        if self.status != 'TAKEN_OVER':
            raise ValidationError("Status must be 'Taken Over'")
        
        self.taken_back = True
        self.taken_back_date = timezone.now()
        self.status = 'TAKEN_BACK'
        self.save()
        
        # Log activity
        self.log_activity(
            user=user,
            action='Responsibilities Taken Back',
            comment=comment or 'Taken back.'
        )
        
        # ⭐ Notify all parties - handover completed
        try:
            from .handover_email_service import handover_email_service
            handover_email_service.notify_completed(self)
        except Exception as e:
            logger.error(f"Failed to send completion email: {e}")
    
    def log_activity(self, user, action, comment=''):
        """Add to activity log"""
        HandoverActivity.objects.create(
            handover=self,
            actor=user,
            action=action,
            comment=comment,
            status=self.status
        )


class HandoverTask(SoftDeleteModel):
    """Handover Tasks"""
    
    TASK_STATUS_CHOICES = [
        ('NOT_STARTED', 'Not Started'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELED', 'Canceled'),
        ('POSTPONED', 'Postponed'),
    ]
    
    handover = models.ForeignKey(
        HandoverRequest, 
        on_delete=models.CASCADE, 
        related_name='tasks'
    )
    description = models.TextField()
    current_status = models.CharField(
        max_length=20, 
        choices=TASK_STATUS_CHOICES, 
        default='NOT_STARTED'
    )
    initial_comment = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.handover.request_id} - {self.description[:50]}"
    
    def update_status(self, user, new_status, comment=''):
        """Update task status"""
        old_status = self.current_status
        self.current_status = new_status
        self.save()
        
        # Log activity
        TaskActivity.objects.create(
            task=self,
            actor=user,
            action='Status Updated',
            old_status=old_status,
            new_status=new_status,
            comment=comment
        )
    
    class Meta:
        ordering = ['handover', 'order']
        verbose_name = "Handover Task"
        verbose_name_plural = "Handover Tasks"
        db_table = 'handover_tasks'


class TaskActivity(models.Model):
    """Task activity log"""
    task = models.ForeignKey(
        HandoverTask, 
        on_delete=models.CASCADE, 
        related_name='activity_log'
    )
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    comment = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
        verbose_name = "Task Activity"
        verbose_name_plural = "Task Activities"
        db_table = 'task_activities'
    
    def __str__(self):
        return f"{self.task.handover.request_id} - {self.action} - {self.timestamp}"


class HandoverImportantDate(SoftDeleteModel):
    """Important dates"""
    handover = models.ForeignKey(
        HandoverRequest, 
        on_delete=models.CASCADE, 
        related_name='important_dates'
    )
    date = models.DateField()
    description = models.CharField(max_length=500)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['handover', 'date']
        verbose_name = "Important Date"
        verbose_name_plural = "Important Dates"
        db_table = 'handover_important_dates'
    
    def __str__(self):
        return f"{self.handover.request_id} - {self.date}: {self.description}"


class HandoverActivity(models.Model):
    """Handover activity log"""
    handover = models.ForeignKey(
        HandoverRequest, 
        on_delete=models.CASCADE, 
        related_name='activity_log'
    )
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=200)
    comment = models.TextField(blank=True)
    status = models.CharField(max_length=30, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
        verbose_name = "Handover Activity"
        verbose_name_plural = "Handover Activities"
        db_table = 'handover_activities'
    
    def __str__(self):
        return f"{self.handover.request_id} - {self.action} - {self.timestamp}"


def handover_attachment_path(instance, filename):
    """Generate upload path for handover attachments"""
    year = instance.handover.created_at.year
    request_id = instance.handover.request_id
    return f'handovers/{year}/{request_id}/{filename}'


class HandoverAttachment(SoftDeleteModel):
    """File attachments for handover requests"""
    handover = models.ForeignKey(
        HandoverRequest, 
        on_delete=models.CASCADE, 
        related_name='attachments'
    )
    file = models.FileField(upload_to=handover_attachment_path)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    file_type = models.CharField(max_length=100, blank=True)
    
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Handover Attachment"
        verbose_name_plural = "Handover Attachments"
        db_table = 'handover_attachments'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.handover.request_id}"
    
    @property
    def file_size_display(self):
        """Human readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def delete(self, *args, **kwargs):
        """Delete file from storage when model is deleted"""
        if self.file:
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super().delete(*args, **kwargs)