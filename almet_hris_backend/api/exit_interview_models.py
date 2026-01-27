# api/exit_interview_models.py
"""
Exit Interview Management Models
Handles exit interview questions and responses
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Employee, SoftDeleteModel
import logging

logger = logging.getLogger(__name__)


class ExitInterviewQuestion(SoftDeleteModel):
    """
    Configurable exit interview questions
    Admin can create, update, delete questions
    """
    
    QUESTION_TYPES = [
        ('RATING', 'Rating (1-5)'),
        ('TEXT', 'Text Response'),
        ('TEXTAREA', 'Long Text Response'),
        ('CHOICE', 'Multiple Choice'),
    ]
    
    SECTION_CHOICES = [
        ('ROLE', 'Role & Responsibilities'),
        ('MANAGEMENT', 'Work Environment & Management'),
        ('COMPENSATION', 'Compensation & Career Development'),
        ('CONDITIONS', 'Work Conditions'),
        ('CULTURE', 'Company Culture & Values'),
        ('FINAL', 'Final Comments'),
    ]
    
    # Question Details
    section = models.CharField(
        max_length=20,
        choices=SECTION_CHOICES,
        help_text="Question section/category"
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
        default='RATING'
    )
    
    # Order and Status
    order = models.IntegerField(
        default=0,
        help_text="Display order within section"
    )
    is_required = models.BooleanField(
        default=False,
        help_text="Is this question mandatory?"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Is this question active?"
    )
    
    # For multiple choice questions
    choices = models.JSONField(
        default=list,
        blank=True,
        help_text="Choices for multiple choice questions"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_exit_questions'
    )
    
    class Meta:
        ordering = ['section', 'order']
        verbose_name = "Exit Interview Question"
        verbose_name_plural = "Exit Interview Questions"
    
    def __str__(self):
        return f"{self.get_section_display()} - {self.question_text_en[:50]}"


class ExitInterview(SoftDeleteModel):
    """
    Exit interview instance for an employee
    Created by admin/HR and assigned to employee
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Employee Response'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    # Employee Information
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='exit_interviews'
    )
    
    # Interview Details
    last_working_day = models.DateField(
        help_text="Employee's last working day"
    )
    resignation_request = models.OneToOneField(
        'ResignationRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exit_interview',
        help_text="Linked resignation request"
    )
    
    # Status
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    
    # Completion
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Admin/HR who created
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_exit_interviews'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Exit Interview"
        verbose_name_plural = "Exit Interviews"
    
    def __str__(self):
        return f"{self.employee.full_name} - Exit Interview ({self.last_working_day})"
    
    def start_interview(self):
        """Mark interview as started"""
        if self.status == 'PENDING':
            self.status = 'IN_PROGRESS'
            self.started_at = timezone.now()
            self.save()
    
    def complete_interview(self):
        """Mark interview as completed"""
        if self.status == 'IN_PROGRESS':
            self.status = 'COMPLETED'
            self.completed_at = timezone.now()
            self.save()
            
            # Send notification to HR
            self._send_hr_notification()
    
    def _send_hr_notification(self):
        """Notify HR that exit interview is completed"""
        from .system_email_service import system_email_service
        
        try:
            hr_email = "hr@almettrading.com"
            
            subject = f"Exit Interview Completed - {self.employee.full_name}"
            
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #10B981;">Exit Interview Completed</h2>
                
                <p>An exit interview has been completed and is ready for review:</p>
                
                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0;">
                    <p><strong>Employee:</strong> {self.employee.full_name} ({self.employee.employee_id})</p>
                    <p><strong>Position:</strong> {self.employee.job_title}</p>
                    <p><strong>Department:</strong> {self.employee.department.name}</p>
                    <p><strong>Last Working Day:</strong> {self.last_working_day}</p>
                    <p><strong>Completed:</strong> {self.completed_at.strftime('%Y-%m-%d %H:%M')}</p>
                </div>
                
              
             
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


class ExitInterviewResponse(models.Model):
    """
    Employee's response to exit interview question
    """
    
    exit_interview = models.ForeignKey(
        ExitInterview,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    question = models.ForeignKey(
        ExitInterviewQuestion,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    
    # Response data (depends on question type)
    rating_value = models.IntegerField(
        null=True,
        blank=True,
        help_text="Rating value for rating questions (1-5)"
    )
    text_value = models.TextField(
        blank=True,
        help_text="Text response for text/textarea questions"
    )
    choice_value = models.CharField(
        max_length=255,
        blank=True,
        help_text="Selected choice for multiple choice questions"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['question__section', 'question__order']
        unique_together = ['exit_interview', 'question']
        verbose_name = "Exit Interview Response"
        verbose_name_plural = "Exit Interview Responses"
    
    def __str__(self):
        return f"{self.exit_interview.employee.full_name} - {self.question.question_text_en[:30]}"
    
    def get_response_value(self):
        """Get the actual response value based on question type"""
        if self.question.question_type == 'RATING':
            return self.rating_value
        elif self.question.question_type in ['TEXT', 'TEXTAREA']:
            return self.text_value
        elif self.question.question_type == 'CHOICE':
            return self.choice_value
        return None


class ExitInterviewSummary(models.Model):
    """
    Analytics/summary data for exit interviews
    Auto-generated when interview is completed
    """
    
    exit_interview = models.OneToOneField(
        ExitInterview,
        on_delete=models.CASCADE,
        related_name='summary'
    )
    
    # Average ratings by section
    role_avg_rating = models.FloatField(default=0)
    management_avg_rating = models.FloatField(default=0)
    compensation_avg_rating = models.FloatField(default=0)
    conditions_avg_rating = models.FloatField(default=0)
    culture_avg_rating = models.FloatField(default=0)
    
    # Overall average
    overall_avg_rating = models.FloatField(default=0)
    
    # Key insights (auto-extracted from responses)
    main_reason_for_leaving = models.CharField(max_length=255, blank=True)
    would_recommend_company = models.BooleanField(default=True)
    retention_suggestions = models.TextField(blank=True)
    
    # Metadata
    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Exit Interview Summary"
        verbose_name_plural = "Exit Interview Summaries"
    
    def __str__(self):
        return f"Summary - {self.exit_interview.employee.full_name}"
    
    @classmethod
    def generate_summary(cls, exit_interview):
        """Generate summary from exit interview responses"""
        summary, created = cls.objects.get_or_create(exit_interview=exit_interview)
        
        responses = exit_interview.responses.filter(
            question__question_type='RATING'
        ).select_related('question')
        
        # Calculate section averages
        section_ratings = {}
        for response in responses:
            section = response.question.section
            if section not in section_ratings:
                section_ratings[section] = []
            if response.rating_value:
                section_ratings[section].append(response.rating_value)
        
        summary.role_avg_rating = sum(section_ratings.get('ROLE', [0])) / len(section_ratings.get('ROLE', [1])) if section_ratings.get('ROLE') else 0
        summary.management_avg_rating = sum(section_ratings.get('MANAGEMENT', [0])) / len(section_ratings.get('MANAGEMENT', [1])) if section_ratings.get('MANAGEMENT') else 0
        summary.compensation_avg_rating = sum(section_ratings.get('COMPENSATION', [0])) / len(section_ratings.get('COMPENSATION', [1])) if section_ratings.get('COMPENSATION') else 0
        summary.conditions_avg_rating = sum(section_ratings.get('CONDITIONS', [0])) / len(section_ratings.get('CONDITIONS', [1])) if section_ratings.get('CONDITIONS') else 0
        summary.culture_avg_rating = sum(section_ratings.get('CULTURE', [0])) / len(section_ratings.get('CULTURE', [1])) if section_ratings.get('CULTURE') else 0
        
        # Overall average
        all_ratings = []
        for ratings in section_ratings.values():
            all_ratings.extend(ratings)
        summary.overall_avg_rating = sum(all_ratings) / len(all_ratings) if all_ratings else 0
        
        summary.save()
        return summary