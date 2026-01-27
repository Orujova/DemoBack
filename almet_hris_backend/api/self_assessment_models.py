# api/self_assessment_models.py - SIMPLIFIED: Core Skills Assessment Only

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from .models import Employee
from .competency_models import Skill


class AssessmentPeriod(models.Model):
    """6 ayda bir assessment periodu"""
  
    
    name = models.CharField(max_length=200, help_text="e.g., H1 2025, H2 2025")
    start_date = models.DateField()
    end_date = models.DateField()
    submission_deadline = models.DateField()
 
    
    is_active = models.BooleanField(default=False, help_text="Only one period can be active")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-start_date']
        db_table = 'assessment_periods'
    
    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"
    
    def save(self, *args, **kwargs):
        # Əgər bu period active edilərsə, digərlərini deactive et
        if self.is_active:
            AssessmentPeriod.objects.exclude(id=self.id).update(is_active=False)
        super().save(*args, **kwargs)
    
    @property
    def days_remaining(self):
        """Submission deadline-a qədər qalan günlər"""
        if self.submission_deadline:
            delta = self.submission_deadline - timezone.now().date()
            return max(0, delta.days)
        return 0
    
    @property
    def is_overdue(self):
        """Deadline keçibmi?"""
        return timezone.now().date() > self.submission_deadline
    
    @classmethod
    def get_active_period(cls):
        """Active assessment period"""
        return cls.objects.filter(is_active=True).first()


class SelfAssessment(models.Model):
    """Employee-nin Core Skills Self Assessment-i"""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('REVIEWED', 'Reviewed by Manager'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='self_assessments')
    period = models.ForeignKey(AssessmentPeriod, on_delete=models.CASCADE, related_name='self_assessments')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Overall score (calculated from all skill ratings)
    overall_score = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True,
        help_text="Average of all skill ratings"
    )
    
    # Manager review
    manager_reviewed_at = models.DateTimeField(null=True, blank=True)
    manager_reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, 
        related_name='reviewed_assessments'
    )
    manager_comments = models.TextField(blank=True, help_text="Overall manager feedback")
    
    # Timestamps
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['employee', 'period']
        ordering = ['-created_at']
        db_table = 'self_assessments'
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.period.name}"
    
    def calculate_overall_score(self):
        """Bütün skill ratinglərdən average hesabla"""
        skill_ratings = self.skill_ratings.all()
        if skill_ratings.exists():
            total = sum(r.rating for r in skill_ratings)
            self.overall_score = total / skill_ratings.count()
            self.save()
    
    def submit(self):
        """Submit assessment"""
        if self.status == 'DRAFT':
            self.status = 'SUBMITTED'
            self.submitted_at = timezone.now()
            self.calculate_overall_score()
            self.save()
            
            # Log activity
            AssessmentActivity.objects.create(
                assessment=self,
                activity_type='SUBMITTED',
                description='Assessment submitted',
                performed_by=self.employee.user,
                metadata={'overall_score': float(self.overall_score) if self.overall_score else 0}
            )


class SkillRating(models.Model):
    """Core Skill Rating - 1-dən 5-ə qədər"""
    assessment = models.ForeignKey(
        SelfAssessment, on_delete=models.CASCADE, 
        related_name='skill_ratings'
    )
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    
    # Rating 1-5
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1 (Basic) to 5 (Expert)"
    )
    
    # Comments
    self_comment = models.TextField(
        blank=True, 
        help_text="Employee's self-reflection on this skill"
    )
    manager_comment = models.TextField(
        blank=True, 
        help_text="Manager's feedback on this skill rating"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['assessment', 'skill']
        ordering = ['skill__group__name', 'skill__name']
        db_table = 'skill_ratings'
    
    def __str__(self):
        return f"{self.skill.name}: {self.rating}/5"
    
    def get_rating_level(self):
        """Rating level description"""
        levels = {
            1: 'Basic',
            2: 'Limited',
            3: 'Intermediate',
            4: 'Advanced',
            5: 'Expert'
        }
        return levels.get(self.rating, 'Unknown')


class AssessmentActivity(models.Model):
    """Assessment üzərində activity tracking"""
    ACTIVITY_TYPES = [
        ('CREATED', 'Assessment Created'),
        ('UPDATED', 'Assessment Updated'),
        ('SUBMITTED', 'Assessment Submitted'),
        ('REVIEWED', 'Reviewed by Manager'),
        ('RATING_CHANGED', 'Rating Changed'),
    ]
    
    assessment = models.ForeignKey(
        SelfAssessment, on_delete=models.CASCADE, 
        related_name='activities'
    )
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField()
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        db_table = 'assessment_activities'
        verbose_name_plural = 'Assessment Activities'
    
    def __str__(self):
        return f"{self.assessment.employee.full_name} - {self.activity_type}"