# api/resignation_models.py
"""
Resignation Management Models
Handles employee resignation requests and approval workflow
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Employee, SoftDeleteModel
import logging

logger = logging.getLogger(__name__)


class ResignationRequest(SoftDeleteModel):
    """
    Employee resignation request with approval workflow
    """
    
    STATUS_CHOICES = [
        ('PENDING_MANAGER', 'Pending Manager Approval'),
        ('MANAGER_APPROVED', 'Manager Approved'),
        ('MANAGER_REJECTED', 'Manager Rejected'),
        ('PENDING_HR', 'Pending HR Approval'),
        ('HR_APPROVED', 'HR Approved'),
        ('HR_REJECTED', 'HR Rejected'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    # Employee Information
    employee = models.ForeignKey(
        Employee, 
        on_delete=models.CASCADE, 
        related_name='resignation_requests'
    )
    
    # Resignation Details
    submission_date = models.DateField(
        default=timezone.now,
        help_text="Date when resignation was submitted"
    )
    last_working_day = models.DateField(
        help_text="Employee's last working day"
    )
    
    # Documentation
    resignation_letter = models.FileField(
        upload_to='resignations/%Y/%m/',
        null=True,
        blank=True,
        help_text="Uploaded resignation letter/document"
    )
    employee_comments = models.TextField(
        blank=True,
        help_text="Employee's additional comments"
    )
    
    # Approval Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING_MANAGER'
    )
    
    # Manager Approval
    manager_approved_at = models.DateTimeField(null=True, blank=True)
    manager_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_resignations_as_manager'
    )
    manager_comments = models.TextField(
        blank=True,
        help_text="Manager's comments on resignation"
    )
    
    # HR Approval
    hr_approved_at = models.DateTimeField(null=True, blank=True)
    hr_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_resignations_as_hr'
    )
    hr_comments = models.TextField(
        blank=True,
        help_text="HR's comments on resignation"
    )
    
    # Completion
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-submission_date']
        verbose_name = "Resignation Request"
        verbose_name_plural = "Resignation Requests"
    
    def __str__(self):
        return f"{self.employee.full_name} - Resignation ({self.submission_date})"
    
    def get_notice_period_days(self):
        """Calculate notice period in days"""
        from datetime import datetime
        submission = datetime.combine(self.submission_date, datetime.min.time())
        last_day = datetime.combine(self.last_working_day, datetime.min.time())
        return (last_day - submission).days
    
    def get_days_until_last_working_day(self):
        """Calculate days remaining until last working day"""
        from datetime import datetime, date
        today = date.today()
        if self.last_working_day <= today:
            return 0
        return (self.last_working_day - today).days
    
    def manager_approve(self, user, comments=''):
        """Manager approves resignation"""
        if self.status != 'PENDING_MANAGER':
            raise ValueError("Resignation is not pending manager approval")
        
        self.status = 'PENDING_HR'
        self.manager_approved_at = timezone.now()
        self.manager_approved_by = user
        self.manager_comments = comments
        self.save()
        
        # Send notification to HR
        self._send_hr_notification()
        
        # Send notification to employee
        self._send_employee_notification('manager_approved')
        
        logger.info(f"Resignation approved by manager: {self.employee.employee_id}")
    
    def manager_reject(self, user, comments=''):
        """Manager rejects resignation"""
        if self.status != 'PENDING_MANAGER':
            raise ValueError("Resignation is not pending manager approval")
        
        self.status = 'MANAGER_REJECTED'
        self.manager_approved_at = timezone.now()
        self.manager_approved_by = user
        self.manager_comments = comments
        self.save()
        
        # Send notification to employee
        self._send_employee_notification('manager_rejected')
        
        logger.info(f"Resignation rejected by manager: {self.employee.employee_id}")
    
    def hr_approve(self, user, comments=''):
        """HR approves resignation"""
        if self.status != 'PENDING_HR':
            raise ValueError("Resignation is not pending HR approval")
        
        self.status = 'COMPLETED'
        self.hr_approved_at = timezone.now()
        self.hr_approved_by = user
        self.hr_comments = comments
        self.completed_at = timezone.now()
        self.save()
        
        # Update employee status to inactive
        self._update_employee_status()
        
        # Send notification to employee
        self._send_employee_notification('hr_approved')
        
        logger.info(f"Resignation approved by HR: {self.employee.employee_id}")
    
    def hr_reject(self, user, comments=''):
        """HR rejects resignation"""
        if self.status != 'PENDING_HR':
            raise ValueError("Resignation is not pending HR approval")
        
        self.status = 'HR_REJECTED'
        self.hr_approved_at = timezone.now()
        self.hr_approved_by = user
        self.hr_comments = comments
        self.save()
        
        # Send notification to employee
        self._send_employee_notification('hr_rejected')
        
        logger.info(f"Resignation rejected by HR: {self.employee.employee_id}")
    
    def _update_employee_status(self):
        """Update employee status when resignation is approved"""
        from .models import EmployeeStatus
        
        try:
            inactive_status = EmployeeStatus.objects.filter(
                status_type='INACTIVE',
                is_active=True
            ).first()
            
            if inactive_status:
                self.employee.status = inactive_status
                self.employee.end_date = self.last_working_day
                self.employee.save()
        except Exception as e:
            logger.error(f"Error updating employee status: {e}")
    
    def _send_hr_notification(self):
        """Send notification to HR about resignation"""
        from .system_email_service import system_email_service
        
        try:
            hr_email = "hr@almettrading.com"
            
            subject = f"Resignation Approval Required - {self.employee.full_name}"
            
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #FF6B35;">Resignation Approval Required</h2>
                
                <p>A resignation request has been approved by the manager and requires HR approval:</p>
                
                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0;">
                    <p><strong>Employee:</strong> {self.employee.full_name} ({self.employee.employee_id})</p>
                    <p><strong>Position:</strong> {self.employee.job_title}</p>
                    <p><strong>Department:</strong> {self.employee.department.name}</p>
                    <p><strong>Submission Date:</strong> {self.submission_date}</p>
                    <p><strong>Last Working Day:</strong> {self.last_working_day}</p>
                    <p><strong>Notice Period:</strong> {self.get_notice_period_days()} days</p>
                </div>
                
                {f'<p><strong>Manager Comments:</strong><br>{self.manager_comments}</p>' if self.manager_comments else ''}
                
               
            </body>
            </html>
            """
            
            system_email_service.send_email_as_system(
                from_email="myalmet@almettrading.com",
                to_email=hr_email,
                subject=subject,
                body_html=body
            )
        except Exception as e:
            logger.error(f"Error sending HR notification: {e}")
    
    def _send_employee_notification(self, notification_type):
        """Send notification to employee about resignation status"""
        from .system_email_service import system_email_service
        
        try:
            if not self.employee.email:
                return
            
            subject_map = {
                'manager_approved': 'Resignation Approved by Manager',
                'manager_rejected': 'Resignation Not Approved',
                'hr_approved': 'Resignation Process Completed',
                'hr_rejected': 'Resignation Not Approved by HR',
            }
            
            subject = subject_map.get(notification_type, 'Resignation Status Update')
            
            body = self._get_employee_notification_body(notification_type)
            
            system_email_service.send_email_as_system(
                from_email="myalmet@almettrading.com",
                to_email=self.employee.email,
                subject=subject,
                body_html=body
            )
        except Exception as e:
            logger.error(f"Error sending employee notification: {e}")
    
    def _get_employee_notification_body(self, notification_type):
        """Get email body for employee notification"""
        
        if notification_type == 'manager_approved':
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #10B981;">Resignation Approved by Manager</h2>
                
                <p>Dear {self.employee.first_name},</p>
                
                <p>Your resignation request has been approved by your manager and forwarded to HR for final approval.</p>
                
                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0;">
                    <p><strong>Last Working Day:</strong> {self.last_working_day}</p>
                    {f'<p><strong>Manager Comments:</strong><br>{self.manager_comments}</p>' if self.manager_comments else ''}
                </div>
                
                <p>HR will review your resignation and notify you of the final decision.</p>
                
           
            </body>
            </html>
            """
        
        elif notification_type == 'manager_rejected':
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #EF4444;">Resignation Not Approved</h2>
                
                <p>Dear {self.employee.first_name},</p>
                
                <p>Your resignation request was not approved by your manager.</p>
                
                {f'<p><strong>Manager Comments:</strong><br>{self.manager_comments}</p>' if self.manager_comments else ''}
                
                <p>Please contact your manager for more information.</p>
                
              
            </body>
            </html>
            """
        
        elif notification_type == 'hr_approved':
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #10B981;">Resignation Process Completed</h2>
                
                <p>Dear {self.employee.first_name},</p>
                
                <p>Your resignation has been approved by HR. Your employment will end on <strong>{self.last_working_day}</strong>.</p>
                
                <div style="background-color: #FEF3C7; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #F59E0B;">
                    <p><strong>Important Reminders:</strong></p>
                    <ul>
                        <li>Complete all pending work and handover procedures</li>
                        <li>Return all company assets (laptop, ID card, etc.)</li>
                        <li>Complete exit interview if scheduled</li>
                        <li>Settle any pending expenses or advances</li>
                    </ul>
                </div>
                
                <p>We wish you all the best in your future endeavors.</p>
                
                
            </body>
            </html>
            """
        
        elif notification_type == 'hr_rejected':
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #EF4444;">Resignation Not Approved by HR</h2>
                
                <p>Dear {self.employee.first_name},</p>
                
                <p>Your resignation request was not approved by HR.</p>
                
                {f'<p><strong>HR Comments:</strong><br>{self.hr_comments}</p>' if self.hr_comments else ''}
                
                <p>Please contact HR for more information.</p>
                
               
            </body>
            </html>
            """
        
        return ""


class ResignationActivity(models.Model):
    """Track resignation request activities"""
    
    ACTIVITY_TYPES = [
        ('CREATED', 'Resignation Submitted'),
        ('MANAGER_APPROVED', 'Manager Approved'),
        ('MANAGER_REJECTED', 'Manager Rejected'),
        ('HR_APPROVED', 'HR Approved'),
        ('HR_REJECTED', 'HR Rejected'),
        ('COMPLETED', 'Process Completed'),
        ('CANCELLED', 'Cancelled'),
        ('COMMENT_ADDED', 'Comment Added'),
    ]
    
    resignation = models.ForeignKey(
        ResignationRequest,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField()
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Resignation Activity"
        verbose_name_plural = "Resignation Activities"
    
    def __str__(self):
        return f"{self.resignation.employee.full_name} - {self.activity_type}"