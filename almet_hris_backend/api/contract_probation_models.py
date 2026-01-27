# api/contract_probation_models.py
"""
Contract Expiry and Probation Management Models
Handles contract renewals and probation period reviews
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta
from .models import Employee, SoftDeleteModel
import logging

logger = logging.getLogger(__name__)


class ContractRenewalRequest(SoftDeleteModel):
    """
    Contract renewal decision request
    Triggered 2 weeks before contract expiry
    """
    
    STATUS_CHOICES = [
        ('PENDING_MANAGER', 'Pending Manager Decision'),
        ('MANAGER_DECIDED', 'Manager Decision Made'),
        ('PENDING_HR', 'Pending HR Processing'),
        ('HR_PROCESSED', 'HR Processed'),
        ('COMPLETED', 'Completed'),
        ('EXPIRED', 'Contract Expired'),
    ]
    
    DECISION_CHOICES = [
        ('RENEW', 'Renew Contract'),
        ('NOT_RENEW', 'Do Not Renew'),
    ]
    
    CONTRACT_TYPE_CHOICES = [
        ('PERMANENT', 'Permanent'),
        ('3_MONTHS', '3 Months'),
        ('6_MONTHS', '6 Months'),
        ('1_YEAR', '1 Year'),
        ('2_YEARS', '2 Years'),
    ]
    
    # Employee Information
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='contract_renewal_requests'
    )
    
    # Contract Details
    current_contract_end_date = models.DateField(
        help_text="Current contract end date"
    )
    current_contract_type = models.CharField(
        max_length=20,
        help_text="Current contract type"
    )
    
    # Notification
    notification_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When notification was sent to manager"
    )
    
    # Manager Decision
    manager_decision = models.CharField(
        max_length=10,
        choices=DECISION_CHOICES,
        blank=True,
        help_text="Manager's renewal decision"
    )
    manager_decided_at = models.DateTimeField(null=True, blank=True)
    manager_decided_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contract_decisions_as_manager'
    )
    
    # Renewal Details (if renewing)
    new_contract_type = models.CharField(
        max_length=20,
        choices=CONTRACT_TYPE_CHOICES,
        blank=True,
        help_text="New contract type if renewing"
    )
    new_contract_duration_months = models.IntegerField(
        null=True,
        blank=True,
        help_text="Duration in months for fixed-term contracts"
    )
    salary_change = models.BooleanField(
        default=False,
        help_text="Is there a salary change?"
    )
    new_salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="New salary amount"
    )
    position_change = models.BooleanField(
        default=False,
        help_text="Is there a position change?"
    )
    new_position = models.CharField(
        max_length=200,
        blank=True,
        help_text="New position title"
    )
    
    # Comments
    manager_comments = models.TextField(
        blank=True,
        help_text="Manager's comments on decision"
    )
    
    # HR Processing
    hr_processed_at = models.DateTimeField(null=True, blank=True)
    hr_processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contract_processed_as_hr'
    )
    hr_comments = models.TextField(
        blank=True,
        help_text="HR's notes on processing"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING_MANAGER'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Contract Renewal Request"
        verbose_name_plural = "Contract Renewal Requests"
    
    def __str__(self):
        return f"{self.employee.full_name} - Contract Renewal ({self.current_contract_end_date})"
    
    def get_days_until_expiry(self):
        """Calculate days until contract expiry"""
        today = date.today()
        if self.current_contract_end_date <= today:
            return 0
        return (self.current_contract_end_date - today).days
    
    def manager_make_decision(self, user, decision, data):
        """
        Manager makes renewal decision
        data = {
            'new_contract_type': str,
            'new_contract_duration_months': int (optional),
            'salary_change': bool,
            'new_salary': decimal (optional),
            'position_change': bool,
            'new_position': str (optional),
            'comments': str
        }
        """
        if self.status != 'PENDING_MANAGER':
            raise ValueError("Request is not pending manager decision")
        
        self.manager_decision = decision
        self.manager_decided_at = timezone.now()
        self.manager_decided_by = user
        self.manager_comments = data.get('comments', '')
        
        if decision == 'RENEW':
            self.new_contract_type = data.get('new_contract_type')
            self.new_contract_duration_months = data.get('new_contract_duration_months')
            self.salary_change = data.get('salary_change', False)
            self.new_salary = data.get('new_salary')
            self.position_change = data.get('position_change', False)
            self.new_position = data.get('new_position', '')
            self.status = 'PENDING_HR'
        else:
            # Not renewing - will expire
            self.status = 'MANAGER_DECIDED'
        
        self.save()
        
        # Send notifications
        if decision == 'RENEW':
            self._send_hr_notification()
            self._send_employee_notification('renewal_approved')
        else:
            self._send_employee_notification('not_renewing')
        
        logger.info(f"Contract decision made by manager: {self.employee.employee_id} - {decision}")
    
    def hr_process_renewal(self, user, comments=''):
        """HR processes the contract renewal"""
        if self.status != 'PENDING_HR':
            raise ValueError("Request is not pending HR processing")
        
        if self.manager_decision != 'RENEW':
            raise ValueError("Cannot process - manager decided not to renew")
        
        # Update employee contract details
        self.employee.contract_duration = self.new_contract_type
        
        if self.new_contract_type != 'PERMANENT':
            from dateutil.relativedelta import relativedelta
            self.employee.contract_start_date = self.current_contract_end_date + timedelta(days=1)
            
            # Calculate new contract end date
            if self.new_contract_duration_months:
                self.employee.contract_end_date = self.employee.contract_start_date + relativedelta(
                    months=self.new_contract_duration_months
                )
        
        # Update salary if changed
        # (Note: You may have a separate salary field/model)
        
        # Update position if changed
        if self.position_change and self.new_position:
            self.employee.job_title = self.new_position
        
        self.employee.save()
        
        # Update request status
        self.status = 'COMPLETED'
        self.hr_processed_at = timezone.now()
        self.hr_processed_by = user
        self.hr_comments = comments
        self.save()
        
        # Send confirmation to employee
        self._send_employee_notification('renewal_completed')
        
        logger.info(f"Contract renewal processed by HR: {self.employee.employee_id}")
    
    def hr_handle_expiry(self, user, comments=''):
        """HR handles contract expiry (not renewing)"""
        if self.status not in ['MANAGER_DECIDED', 'EXPIRED']:
            raise ValueError("Invalid status for handling expiry")
        
        # Update employee status to inactive
        from .models import EmployeeStatus
        
        try:
            inactive_status = EmployeeStatus.objects.filter(
                status_type='INACTIVE',
                is_active=True
            ).first()
            
            if inactive_status:
                self.employee.status = inactive_status
                self.employee.end_date = self.current_contract_end_date
                self.employee.save()
        except Exception as e:
            logger.error(f"Error updating employee status: {e}")
        
        self.status = 'COMPLETED'
        self.hr_processed_at = timezone.now()
        self.hr_processed_by = user
        self.hr_comments = comments
        self.save()
        
        logger.info(f"Contract expiry processed by HR: {self.employee.employee_id}")
    
    def _send_hr_notification(self):
        """Send notification to HR"""
        from .system_email_service import system_email_service
        
        try:
            hr_email = "hr@almettrading.com"
            
            subject = f"Contract Renewal - Action Required - {self.employee.full_name}"
            
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #10B981;">Contract Renewal - Manager Decision</h2>
                
                <p>Manager has decided to renew the contract for:</p>
                
                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0;">
                    <p><strong>Employee:</strong> {self.employee.full_name} ({self.employee.employee_id})</p>
                    <p><strong>Position:</strong> {self.employee.job_title}</p>
                    <p><strong>Department:</strong> {self.employee.department.name}</p>
                    <p><strong>Current Contract Expires:</strong> {self.current_contract_end_date}</p>
                </div>
                
                <h3>Renewal Details:</h3>
                <div style="background-color: #EFF6FF; padding: 15px; border-radius: 5px; margin: 15px 0;">
                    <p><strong>New Contract Type:</strong> {self.get_new_contract_type_display()}</p>
                    {f'<p><strong>Duration:</strong> {self.new_contract_duration_months} months</p>' if self.new_contract_duration_months else ''}
                    {f'<p><strong>New Salary:</strong> {self.new_salary} AZN</p>' if self.salary_change else ''}
                    {f'<p><strong>New Position:</strong> {self.new_position}</p>' if self.position_change else ''}
                </div>
                
                {f'<p><strong>Manager Comments:</strong><br>{self.manager_comments}</p>' if self.manager_comments else ''}
                
                <p>Please process this contract renewal in the HRIS system.</p>
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
        """Send notification to employee"""
        from .system_email_service import system_email_service
        
        try:
            if not self.employee.email:
                return
            
            subject_map = {
                'renewal_approved': 'Contract Renewal - Manager Approval',
                'not_renewing': 'Contract Expiry Notice',
                'renewal_completed': 'Contract Renewal Confirmed',
            }
            
            subject = subject_map.get(notification_type, 'Contract Status Update')
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
        
        if notification_type == 'renewal_approved':
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #10B981;">Contract Renewal - Manager Approval</h2>
                
                <p>Dear {self.employee.first_name},</p>
                
                <p>We are pleased to inform you that your manager has approved your contract renewal.</p>
                
                <div style="background-color: #EFF6FF; padding: 15px; border-radius: 5px; margin: 15px 0;">
                    <p><strong>New Contract Type:</strong> {self.get_new_contract_type_display()}</p>
                    {f'<p><strong>Duration:</strong> {self.new_contract_duration_months} months</p>' if self.new_contract_duration_months else ''}
                    {f'<p><strong>New Salary:</strong> {self.new_salary} AZN</p>' if self.salary_change else ''}
                    {f'<p><strong>New Position:</strong> {self.new_position}</p>' if self.position_change else ''}
                </div>
                
                <p>HR will process your contract renewal and notify you once it is finalized.</p>
                
                <p>Congratulations!</p>
                
             
            </body>
            </html>
            """
        
        elif notification_type == 'not_renewing':
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #F59E0B;">Contract Expiry Notice</h2>
                
                <p>Dear {self.employee.first_name},</p>
                
                <p>We regret to inform you that your contract will not be renewed and will expire on <strong>{self.current_contract_end_date}</strong>.</p>
                
                <p>Please contact HR for more information and to discuss the next steps.</p>
                
                <p>Thank you for your service.</p>
                
          
            </body>
            </html>
            """
        
        elif notification_type == 'renewal_completed':
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #10B981;">Contract Renewal Confirmed</h2>
                
                <p>Dear {self.employee.first_name},</p>
                
                <p>Your contract renewal has been processed and confirmed by HR.</p>
                
                <div style="background-color: #EFF6FF; padding: 15px; border-radius: 5px; margin: 15px 0;">
                    <p><strong>Contract Type:</strong> {self.get_new_contract_type_display()}</p>
                    {f'<p><strong>Contract Period:</strong> {self.employee.contract_start_date} to {self.employee.contract_end_date}</p>' if self.employee.contract_end_date else ''}
                    {f'<p><strong>Salary:</strong> {self.new_salary} AZN</p>' if self.salary_change else ''}
                    {f'<p><strong>Position:</strong> {self.new_position}</p>' if self.position_change else ''}
                </div>
                
                <p>Congratulations and thank you for your continued service!</p>
                
               
            </body>
            </html>
            """
        
        return ""


class ProbationReviewQuestion(SoftDeleteModel):
    """
    Configurable probation review questions
    Used for 30-day, 60-day, and 90-day reviews
    """
    
    QUESTION_TYPES = [
        ('RATING', 'Rating (1-5)'),
        ('YES_NO', 'Yes/No'),
        ('TEXT', 'Text Response'),
        ('TEXTAREA', 'Long Text Response'),
    ]
    
    REVIEW_TYPE_CHOICES = [
        ('EMPLOYEE_30', 'Employee 30-Day'),
        ('MANAGER_30', 'Manager 30-Day'),
        ('EMPLOYEE_60', 'Employee 60-Day'),
        ('MANAGER_60', 'Manager 60-Day'),
        ('EMPLOYEE_90', 'Employee 90-Day'),
        ('MANAGER_90', 'Manager 90-Day'),
    ]
    
    # Question Details
    review_type = models.CharField(
        max_length=15,
        choices=REVIEW_TYPE_CHOICES,
        help_text="Which review this question belongs to"
    )
    question_text_en = models.TextField(
        help_text="Question text in English"
    )
    question_text_az = models.TextField(
        blank=True,
        help_text="Question text in Azerbaijani"
    )
    question_type = models.CharField(
        max_length=10,
        choices=QUESTION_TYPES,
        default='YES_NO'
    )
    
    # Order and Status
    order = models.IntegerField(
        default=0,
        help_text="Display order"
    )
    is_required = models.BooleanField(
        default=False,
        help_text="Is this question mandatory?"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Is this question active?"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_probation_questions'
    )
    
    class Meta:
        ordering = ['review_type', 'order']
        verbose_name = "Probation Review Question"
        verbose_name_plural = "Probation Review Questions"
    
    def __str__(self):
        return f"{self.get_review_type_display()} - {self.question_text_en[:50]}"


class ProbationReview(SoftDeleteModel):
    """
    Probation review instance (30/60/90 day)
    """
    
    REVIEW_PERIOD_CHOICES = [
        ('30_DAY', '30-Day Review'),
        ('60_DAY', '60-Day Review'),
        ('90_DAY', '90-Day Review'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Response'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
    ]
    
    # Employee Information
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='probation_reviews'
    )
    
    # Review Details
    review_period = models.CharField(
        max_length=10,
        choices=REVIEW_PERIOD_CHOICES,
        help_text="Which review period (30/60/90 days)"
    )
    due_date = models.DateField(
        help_text="Review due date"
    )
    
    # Notification
    notification_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When notification was sent"
    )
    
    # Status
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    
    # Completion
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-due_date']
        unique_together = ['employee', 'review_period']
        verbose_name = "Probation Review"
        verbose_name_plural = "Probation Reviews"
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.get_review_period_display()}"
    
    def complete_review(self):
        """Mark review as completed"""
        if self.status != 'COMPLETED':
            self.status = 'COMPLETED'
            self.completed_at = timezone.now()
            self.save()
            
            # Send notification to manager and HR
            self._send_completion_notification()
    
    def _send_completion_notification(self):
        """Notify manager and HR about completed review"""
        from .system_email_service import system_email_service
        
        try:
            recipients = []
            
            # Manager email
            if self.employee.line_manager and self.employee.line_manager.email:
                recipients.append(self.employee.line_manager.email)
            
            # HR email
            recipients.append("hr@almettrading.com")
            
            if not recipients:
                return
            
            subject = f"Probation Review Completed - {self.employee.full_name}"
            
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #10B981;">Probation Review Completed</h2>
                
                <p>A probation review has been completed:</p>
                
                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0;">
                    <p><strong>Employee:</strong> {self.employee.full_name} ({self.employee.employee_id})</p>
                    <p><strong>Position:</strong> {self.employee.job_title}</p>
                    <p><strong>Department:</strong> {self.employee.department.name}</p>
                    <p><strong>Review Period:</strong> {self.get_review_period_display()}</p>
                    <p><strong>Completed:</strong> {self.completed_at.strftime('%Y-%m-%d %H:%M')}</p>
                </div>
                
                <p>Please review the responses in the HRIS system.</p>
            </body>
            </html>
            """
            
            system_email_service.send_email_as_system(
                from_email="myalmet@almettrading.com",
                to_email=recipients,
                subject=subject,
                body_html=body
            )
        except Exception as e:
            logger.error(f"Error sending completion notification: {e}")


class ProbationReviewResponse(models.Model):
    """
    Response to probation review question
    Separate for employee and manager responses
    """
    
    RESPONDENT_TYPE_CHOICES = [
        ('EMPLOYEE', 'Employee'),
        ('MANAGER', 'Manager'),
    ]
    
    review = models.ForeignKey(
        ProbationReview,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    question = models.ForeignKey(
        ProbationReviewQuestion,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    respondent_type = models.CharField(
        max_length=10,
        choices=RESPONDENT_TYPE_CHOICES,
        help_text="Who is responding (employee or manager)"
    )
    
    # Response data
    rating_value = models.IntegerField(null=True, blank=True)
    yes_no_value = models.BooleanField(null=True, blank=True)
    text_value = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['question__order']
        unique_together = ['review', 'question', 'respondent_type']
        verbose_name = "Probation Review Response"
        verbose_name_plural = "Probation Review Responses"
    
    def __str__(self):
        return f"{self.review.employee.full_name} - {self.respondent_type} - {self.question.question_text_en[:30]}"
    
    def get_response_value(self):
        """Get the actual response value based on question type"""
        if self.question.question_type == 'RATING':
            return self.rating_value
        elif self.question.question_type == 'YES_NO':
            return self.yes_no_value
        elif self.question.question_type in ['TEXT', 'TEXTAREA']:
            return self.text_value
        return None