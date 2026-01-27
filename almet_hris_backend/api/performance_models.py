# api/performance_models.py

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
import uuid
import logging

from .models import Employee, PositionGroup, Department
from .competency_models import BehavioralCompetency, LeadershipCompetencyItem 
from .competency_assessment_models import LetterGradeMapping  # ADDED

logger = logging.getLogger(__name__)


class PerformanceYear(models.Model):
    """Performance Year Configuration"""
    year = models.IntegerField(unique=True)
    is_active = models.BooleanField(default=False)
    
    # Goal Setting Period
    goal_setting_employee_start = models.DateField()
    goal_setting_employee_end = models.DateField()
    goal_setting_manager_start = models.DateField()
    goal_setting_manager_end = models.DateField()
    
    # Mid-Year Review Period
    mid_year_review_start = models.DateField()
    mid_year_review_end = models.DateField()
    
    # End-Year Review Period
    end_year_review_start = models.DateField()
    end_year_review_end = models.DateField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-year']
        db_table = 'performance_years'
    
    def __str__(self):
        return f"Performance Year {self.year}"
    
    def get_current_period(self):
        """✅ FIXED: Get current performance period"""
        today = timezone.now().date()
        
        # ✅ FIX: Check periods in correct order (manager THEN employee)
        if self.goal_setting_manager_start <= today <= self.goal_setting_manager_end:
            return 'GOAL_SETTING'
        elif self.goal_setting_employee_start <= today <= self.goal_setting_employee_end:
            return 'GOAL_SETTING'
        elif self.mid_year_review_start <= today <= self.mid_year_review_end:
            return 'MID_YEAR_REVIEW'
        elif self.end_year_review_start <= today <= self.end_year_review_end:
            return 'END_YEAR_REVIEW'
        else:
            return 'CLOSED'
    
    def is_goal_setting_manager_active(self):
        """Check if MANAGER goal setting period is active"""
        today = timezone.now().date()
        return self.goal_setting_manager_start <= today <= self.goal_setting_manager_end
    
    def is_goal_setting_employee_active(self):
        """Check if EMPLOYEE review period is active"""
        today = timezone.now().date()
        return self.goal_setting_employee_start <= today <= self.goal_setting_employee_end
    
    def is_goal_setting_active(self):
        """Check if ANY goal setting period is active (manager OR employee)"""
        today = timezone.now().date()
        return self.goal_setting_manager_start <= today <= self.goal_setting_employee_end
    
    def is_mid_year_active(self):
        """Check if mid-year review period is active"""
        today = timezone.now().date()
        return self.mid_year_review_start <= today <= self.mid_year_review_end
    
    def is_end_year_active(self):
        """Check if end-year review period is active"""
        today = timezone.now().date()
        return self.end_year_review_start <= today <= self.end_year_review_end
    
    def save(self, *args, **kwargs):
        if self.is_active:
            PerformanceYear.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

class PerformanceWeightConfig(models.Model):
    """Performance Weight Configuration by Position Group"""
    position_group = models.ForeignKey(PositionGroup, on_delete=models.CASCADE)
    objectives_weight = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Objectives weight percentage"
    )
    competencies_weight = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Behavioral Competencies weight percentage"  # CHANGED: Description updated
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'performance_weight_configs'
        unique_together = ['position_group']
    
    def __str__(self):
        return f"{self.position_group.get_name_display()} - Obj:{self.objectives_weight}% Comp:{self.competencies_weight}%"
    
    def clean(self):
        if self.objectives_weight + self.competencies_weight != 100:
            raise ValidationError("Objectives and Competencies weights must sum to 100%")


class GoalLimitConfig(models.Model):
    """Goal Limits Configuration"""
    min_goals = models.IntegerField(default=3, validators=[MinValueValidator(1)])
    max_goals = models.IntegerField(default=7, validators=[MinValueValidator(1)])
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'performance_goal_limits'
    
    def __str__(self):
        return f"Goal Limits: {self.min_goals} - {self.max_goals}"
    
    @classmethod
    def get_active_config(cls):
        config = cls.objects.filter(is_active=True).first()
        if not config:
            config = cls.objects.create(min_goals=3, max_goals=7, is_active=True)
        return config


class DepartmentObjective(models.Model):
    """Department Level Objectives"""
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)  # FIX: Əlavə edildi
    weight = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Weight percentage"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        db_table = 'performance_department_objectives'
        ordering = ['department', 'title']
    
    def __str__(self):
        return f"{self.department.name} - {self.title}"

class EvaluationScale(models.Model):
    """Evaluation Scale Definition"""
    name = models.CharField(max_length=10, unique=True, help_text="e.g., E++, E+, E, E-, E--")
    value = models.IntegerField(help_text="Numeric value for calculations")
    range_min = models.IntegerField(help_text="Minimum percentage")
    range_max = models.IntegerField(help_text="Maximum percentage")
    description = models.TextField(blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'performance_evaluation_scales'
        ordering = ['-range_min']  # ✅ Highest range first
    
    def __str__(self):
        return f"{self.name} ({self.range_min}-{self.range_max}%)"
    
    @classmethod
    def get_rating_by_percentage(cls, percentage):
        """
        ✅ IMPROVED: Find the correct rating scale for given percentage
        """
        try:
            percentage = float(percentage)
            
            # ✅ Normal lookup with explicit ordering
            rating = cls.objects.filter(
                range_min__lte=percentage,
                range_max__gte=percentage,
                is_active=True
            ).order_by('range_min').first()
            
            if rating:
                return rating
            
            # ✅ Fallback for edge cases
            # If percentage is below all ranges
            if percentage < 1:
                return cls.objects.filter(is_active=True).order_by('range_min').first()
            
            # If percentage is above all ranges (>500%)
            return cls.objects.filter(is_active=True).order_by('-range_max').first()
            
        except Exception as e:
            logger.error(f"❌ Error getting rating for {percentage}%: {e}")
            return None

class EvaluationTargetConfig(models.Model):
    """Evaluation Target Configuration - REMOVED competency_score_target"""
    objective_score_target = models.IntegerField(default=21)
    # competency_score_target REMOVED - artıq lazım deyil
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'performance_evaluation_targets'
    
    def __str__(self):
        return f"Target: Obj={self.objective_score_target}"
    
    @classmethod
    def get_active_config(cls):
        config = cls.objects.filter(is_active=True).first()
        if not config:
            config = cls.objects.create(is_active=True)
        return config


class ObjectiveStatus(models.Model):
    """Objective Status Types"""
    label = models.CharField(max_length=50, unique=True)
    value = models.CharField(max_length=50, unique=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'performance_objective_statuses'
    
    def __str__(self):
        return self.label


class EmployeePerformance(models.Model):
    """Employee Performance Record"""
    APPROVAL_STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_EMPLOYEE_APPROVAL', 'Pending Employee Approval'),
        ('PENDING_MANAGER_APPROVAL', 'Pending Manager Approval'),
        ('NEED_CLARIFICATION', 'Need Clarification'),
        ('APPROVED', 'Approved'),
        ('COMPLETED', 'Completed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='performances')
    performance_year = models.ForeignKey(PerformanceYear, on_delete=models.CASCADE)
    
    # Approval workflow
    approval_status = models.CharField(max_length=30, choices=APPROVAL_STATUS_CHOICES, default='DRAFT')
    
    # Objective Setting
    objectives_draft_saved_date = models.DateTimeField(null=True, blank=True)
    objectives_employee_submitted = models.BooleanField(default=False)
    objectives_employee_submitted_date = models.DateTimeField(null=True, blank=True)
    objectives_employee_approved = models.BooleanField(default=False)
    objectives_employee_approved_date = models.DateTimeField(null=True, blank=True)
    objectives_manager_approved = models.BooleanField(default=False)
    objectives_manager_approved_date = models.DateTimeField(null=True, blank=True)
    objectives_deadline = models.DateField(null=True, blank=True)
    
    # Competencies Setting
    competencies_draft_saved_date = models.DateTimeField(null=True, blank=True)
    competencies_submitted = models.BooleanField(default=False)
    competencies_submitted_date = models.DateTimeField(null=True, blank=True)
    
    # Mid-Year Review
    mid_year_employee_comment = models.TextField(blank=True)
    mid_year_employee_draft_saved = models.DateTimeField(null=True, blank=True)
    mid_year_employee_submitted = models.DateTimeField(null=True, blank=True)
    mid_year_manager_comment = models.TextField(blank=True)
    mid_year_manager_draft_saved = models.DateTimeField(null=True, blank=True)
    mid_year_manager_submitted = models.DateTimeField(null=True, blank=True)
    mid_year_completed = models.BooleanField(default=False)
    
    # End-Year Review
    end_year_employee_comment = models.TextField(blank=True)
    end_year_employee_draft_saved = models.DateTimeField(null=True, blank=True)
    end_year_employee_submitted = models.DateTimeField(null=True, blank=True)
    end_year_manager_comment = models.TextField(blank=True)
    end_year_manager_draft_saved = models.DateTimeField(null=True, blank=True)
    end_year_manager_submitted = models.DateTimeField(null=True, blank=True)
    end_year_completed = models.BooleanField(default=False)
    
    # Development Needs
    development_needs_draft_saved = models.DateTimeField(null=True, blank=True)
    development_needs_submitted = models.DateTimeField(null=True, blank=True)
    
    # Final approvals
    final_employee_approved = models.BooleanField(default=False)
    final_employee_approval_date = models.DateTimeField(null=True, blank=True)
    final_manager_approved = models.BooleanField(default=False)
    final_manager_approval_date = models.DateTimeField(null=True, blank=True)
    
    # Final Scores
    total_objectives_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    objectives_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # CHANGED: Behavioral competency scores structure
    total_competencies_required_score = models.IntegerField(default=0, help_text="Total required behavioral competency score from position assessment")
    total_competencies_actual_score = models.IntegerField(default=0, help_text="Total actual behavioral competency score")
    competencies_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="(actual/required) * 100")
    competencies_letter_grade = models.CharField(max_length=10, blank=True, help_text="Letter grade based on percentage")
    
    # Group-level behavioral scores
    group_competency_scores = models.JSONField(
        default=dict,
        help_text="Scores by behavioral competency group: {group_name: {required, actual, percentage, letter_grade}}"
    )
    
    overall_weighted_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    final_rating = models.CharField(max_length=10, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_performances')
    
    class Meta:
        db_table = 'employee_performances'
        unique_together = ['employee', 'performance_year']
        ordering = ['-performance_year__year', 'employee__employee_id']
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.performance_year.year}"
    
    def calculate_scores(self):
        """
        ✅ FIXED: Ensure final_rating is ALWAYS calculated
        """
        from collections import defaultdict
     
        
        eval_target = EvaluationTargetConfig.get_active_config()
        weight_config = PerformanceWeightConfig.objects.filter(
            position_group=self.employee.position_group
        ).first()
        
        if not weight_config:
            logger.warning(f"❌ No weight config for {self.employee.position_group}")
            return
        
        # ========== OBJECTIVES CALCULATION ==========
        objectives = self.objectives.filter(is_cancelled=False)
        obj_score = 0
        
        for obj in objectives:
            if obj.calculated_score and obj.calculated_score > 0:
                obj_score += float(obj.calculated_score)
        
        self.total_objectives_score = round(obj_score, 2)
        self.objectives_percentage = round(
            (self.total_objectives_score / eval_target.objective_score_target) * 100, 2
        ) if eval_target.objective_score_target > 0 else 0
        

        
        # ========== COMPETENCIES CALCULATION ==========
        competencies = self.competency_ratings.select_related(
            'behavioral_competency__group',
            'leadership_item',
            'end_year_rating'
        ).all()
        
        group_data = defaultdict(lambda: {'required_total': 0, 'actual_total': 0, 'count': 0})
        total_required = 0
        total_actual = 0
        
        for comp in competencies:
            # ✅ Handle both behavioral and leadership competencies
            if comp.behavioral_competency:
                group_name = comp.behavioral_competency.group.name
            elif comp.leadership_item:
                group_name = comp.leadership_item.child_group.main_group.name if comp.leadership_item.child_group else 'Leadership'
            else:
                continue
                
            required = comp.required_level or 0
            actual = comp.end_year_rating.value if comp.end_year_rating else 0
            
            group_data[group_name]['required_total'] += required
            group_data[group_name]['actual_total'] += actual
            group_data[group_name]['count'] += 1
            
            total_required += required
            total_actual += actual
        
        # Group scores
        group_scores = {}
        for group_name, data in group_data.items():
            percentage = (data['actual_total'] / data['required_total'] * 100) if data['required_total'] > 0 else 0
            letter_grade = LetterGradeMapping.get_letter_grade(percentage)
            
            group_scores[group_name] = {
                'required_total': data['required_total'],
                'actual_total': data['actual_total'],
                'percentage': round(percentage, 2),
                'letter_grade': letter_grade,
                'count': data['count']
            }
        
        self.group_competency_scores = group_scores
        self.total_competencies_required_score = total_required
        self.total_competencies_actual_score = total_actual
        self.competencies_percentage = round((total_actual / total_required * 100), 2) if total_required > 0 else 0
        self.competencies_letter_grade = LetterGradeMapping.get_letter_grade(self.competencies_percentage)
        
        
        # ========== OVERALL WEIGHTED CALCULATION ==========
        self.overall_weighted_percentage = round(
            (self.objectives_percentage * weight_config.objectives_weight / 100) +
            (self.competencies_percentage * weight_config.competencies_weight / 100),
            2
        )
    
        
        # ✅ CRITICAL: Determine final rating using EvaluationScale
        rating = EvaluationScale.get_rating_by_percentage(self.overall_weighted_percentage)
        
        if rating:
            self.final_rating = rating.name
       
        else:
            # ✅ Fallback: Find closest scale
            all_scales = EvaluationScale.objects.filter(is_active=True).order_by('-range_min')
            if all_scales.exists():
                # Get the lowest scale as fallback
                self.final_rating = all_scales.last().name
            
            else:
                self.final_rating = 'N/A'
                logger.error(f"❌ No rating scales found!")
        
        self.save()
        
     
class EmployeeObjective(models.Model):
    """Employee Objectives - UNCHANGED"""
    performance = models.ForeignKey(EmployeePerformance, on_delete=models.CASCADE, related_name='objectives')
    
    title = models.CharField(max_length=300)
    description = models.TextField()
    linked_department_objective = models.ForeignKey(
        DepartmentObjective, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    
    weight = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Weight percentage"
    )
    
  
    status = models.ForeignKey(ObjectiveStatus, on_delete=models.PROTECT)
    
    end_year_rating = models.ForeignKey(
        EvaluationScale, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='objective_ratings'
    )
    calculated_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    is_cancelled = models.BooleanField(default=False)
    cancelled_date = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    added_mid_year = models.BooleanField(default=False)
    
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'employee_objectives'
        ordering = ['performance', 'display_order']
    
    def __str__(self):
        return f"{self.performance.employee.full_name} - {self.title}"

class ObjectiveComment(models.Model):
    """Comments for individual objectives"""
    objective = models.ForeignKey(
        EmployeeObjective,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    
    content = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'objective_comments'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Comment on {self.objective.title[:30]} by {self.created_by.username}"
class EmployeeCompetencyRating(models.Model):
    """
    Employee Competency Ratings - SUPPORTS BOTH BEHAVIORAL AND LEADERSHIP
    """
    performance = models.ForeignKey(
        EmployeePerformance, 
        on_delete=models.CASCADE, 
        related_name='competency_ratings'
    )
    
    # ✅ BEHAVIORAL COMPETENCY (for non-leadership positions)
    behavioral_competency = models.ForeignKey(
        BehavioralCompetency, 
        on_delete=models.CASCADE,
        help_text="Behavioral competency from competency framework",
        null=True,
        blank=True
    )
    
    # ✅ LEADERSHIP COMPETENCY (for leadership positions)
    leadership_item = models.ForeignKey(
        LeadershipCompetencyItem,
        on_delete=models.CASCADE,
        help_text="Leadership competency item for senior positions",
        null=True,
        blank=True
    )
    
    # Required level from position assessment
    required_level = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Required level from position assessment",
        null=True,
        blank=True
    )
    
    # End-year rating (actual performance)
    end_year_rating = models.ForeignKey(
        EvaluationScale,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='competency_ratings',
        help_text="Actual rating using Evaluation Scale (E++, E+, etc.)"
    )
    
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'employee_competency_ratings'
        ordering = ['id']  # ✅ Simple ordering
    
    def clean(self):
        """Validate that either behavioral_competency OR leadership_item is set, not both"""
        if not self.behavioral_competency and not self.leadership_item:
            raise ValidationError("Either behavioral_competency or leadership_item must be set")
        
        if self.behavioral_competency and self.leadership_item:
            raise ValidationError("Cannot set both behavioral_competency and leadership_item")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        if self.leadership_item:
            comp_name = self.leadership_item.name[:50]
        elif self.behavioral_competency:
            comp_name = self.behavioral_competency.name
        else:
            comp_name = 'N/A'
        
        return f"{self.performance.employee.full_name} - {comp_name}"
    
    @property
    def actual_value(self):
        """Get numeric value from end_year_rating"""
        return self.end_year_rating.value if self.end_year_rating else 0
    
    @property
    def gap(self):
        """Calculate gap between actual and required"""
        if self.required_level:
            return self.actual_value - self.required_level
        return 0
    
    @property
    def competency_name(self):
        """Get competency name (works for both types)"""
        if self.leadership_item:
            return self.leadership_item.name
        elif self.behavioral_competency:
            return self.behavioral_competency.name
        return 'N/A'
    
    @property
    def competency_type(self):
        """Get competency type"""
        if self.leadership_item:
            return 'LEADERSHIP'
        elif self.behavioral_competency:
            return 'BEHAVIORAL'
        return 'UNKNOWN'
class DevelopmentNeed(models.Model):
    """
    Development Needs
    CHANGED: Now based on behavioral competencies with low ratings
    """
    performance = models.ForeignKey(
        EmployeePerformance,
        on_delete=models.CASCADE,
        related_name='development_needs'
    )
    competency_gap = models.CharField(
        max_length=200, 
        help_text="Behavioral competency name with gap"
    )
    development_activity = models.TextField(
        help_text="Planned development activity"
    )
    
    progress = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    comment = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'employee_development_needs'
        ordering = ['performance', 'competency_gap']
    
    def __str__(self):
        return f"{self.performance.employee.full_name} - {self.competency_gap}"


class PerformanceComment(models.Model):
    """Comments and Clarifications - UNCHANGED"""
    COMMENT_TYPE_CHOICES = [
        ('OBJECTIVE_CLARIFICATION', 'Objective Clarification'),
        ('FINAL_CLARIFICATION', 'Final Performance Clarification'),
        ('GENERAL_NOTE', 'General Note'),
    ]
    
    performance = models.ForeignKey(
        EmployeePerformance,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    
    comment_type = models.CharField(max_length=30, choices=COMMENT_TYPE_CHOICES)
    content = models.TextField()
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    parent_comment = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )
    
    class Meta:
        db_table = 'performance_comments'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.performance.employee.full_name} - {self.comment_type}"


class PerformanceNotificationTemplate(models.Model):
    """Notification Templates - UNCHANGED"""
    TRIGGER_TYPE_CHOICES = [
        ('GOAL_SETTING_START', 'Goal Setting Period Started'),
        ('MID_YEAR_START', 'Mid-Year Review Started'),
        ('MID_YEAR_END', 'Mid-Year Review Ending'),
        ('END_YEAR_START', 'End-Year Review Started'),
        ('END_YEAR_END', 'End-Year Review Ending'),
        ('FINAL_SCORE_PUBLISHED', 'Final Score Published'),
    ]
    
    trigger_type = models.CharField(max_length=30, choices=TRIGGER_TYPE_CHOICES, unique=True)
    subject = models.CharField(max_length=200)
    message_template = models.TextField(
        help_text="Use {{employee_name}}, {{year}}, {{deadline}} as placeholders"
    )
    
    days_before = models.IntegerField(
        default=0,
        help_text="Days before deadline to send notification"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'performance_notification_templates'
    
    def __str__(self):
        return f"{self.get_trigger_type_display()}"


class PerformanceActivityLog(models.Model):
    """Activity Log for Performance Records - UNCHANGED"""
    performance = models.ForeignKey(
        EmployeePerformance,
        on_delete=models.CASCADE,
        related_name='activity_logs'
    )
    
    action = models.CharField(max_length=100)
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'performance_activity_logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.performance.employee.full_name} - {self.action}"