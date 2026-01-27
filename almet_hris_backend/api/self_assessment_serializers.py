# api/self_assessment_serializers.py - Core Skills Only

from rest_framework import serializers
from .self_assessment_models import (
    AssessmentPeriod, SelfAssessment, SkillRating, AssessmentActivity
)
from .competency_serializers import SkillSerializer


# Assessment Period Serializers
class AssessmentPeriodSerializer(serializers.ModelSerializer):
    days_remaining = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    total_assessments = serializers.SerializerMethodField()
    submitted_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AssessmentPeriod
        fields = [
            'id', 'name', 'start_date', 'end_date', 'submission_deadline',
            'is_active', 'days_remaining', 'is_overdue',
            'total_assessments', 'submitted_count', 'created_at'
        ]
    
    def get_total_assessments(self, obj):
        return obj.self_assessments.count()
    
    def get_submitted_count(self, obj):
        return obj.self_assessments.filter(status__in=['SUBMITTED', 'REVIEWED']).count()


class AssessmentPeriodCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssessmentPeriod
        fields = ['name', 'start_date', 'end_date', 'submission_deadline', 'is_active']


# Skill Rating Serializers
class SkillRatingSerializer(serializers.ModelSerializer):
    skill_info = SkillSerializer(source='skill', read_only=True)
    skill_group_name = serializers.CharField(source='skill.group.name', read_only=True)
    rating_level = serializers.CharField(source='get_rating_level', read_only=True)
    
    class Meta:
        model = SkillRating
        fields = [
            'id', 'skill', 'skill_info', 'skill_group_name', 
            'rating', 'rating_level',
            'self_comment', 'manager_comment', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['manager_comment']


class SkillRatingCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillRating
        fields = ['skill', 'rating', 'self_comment']


# Self Assessment Serializers
class SelfAssessmentDetailSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    employee_position = serializers.CharField(source='employee.job_title', read_only=True)
    period_info = AssessmentPeriodSerializer(source='period', read_only=True)
    
    # Skill ratings with details
    skill_ratings = SkillRatingSerializer(many=True, read_only=True)
    
    # Manager info
    manager_name = serializers.SerializerMethodField()
    line_manager_name = serializers.SerializerMethodField()
    
    # Permissions
    can_edit = serializers.SerializerMethodField()
    can_submit = serializers.SerializerMethodField()
    can_review = serializers.SerializerMethodField()
    
    class Meta:
        model = SelfAssessment
        fields = [
            'id', 'employee', 'employee_name', 'employee_id', 'employee_position',
            'period', 'period_info', 'status',
            'overall_score', 'skill_ratings',
            'manager_comments', 'manager_name', 'manager_reviewed_at',
            'line_manager_name',
            'submitted_at', 'created_at', 'updated_at',
            'can_edit', 'can_submit', 'can_review'
        ]
    
    def get_manager_name(self, obj):
        if obj.manager_reviewed_by:
            return obj.manager_reviewed_by.get_full_name() or obj.manager_reviewed_by.username
        return None
    
    def get_line_manager_name(self, obj):
        if obj.employee.line_manager:
            return obj.employee.line_manager.full_name
        return None
    
    def get_can_edit(self, obj):
        request = self.context.get('request')
        if not request or not request.user:
            return False
        
        # Employee can edit if DRAFT and their own assessment
        if obj.employee.user == request.user and obj.status == 'DRAFT':
            return True
        
        # Admin can always edit
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        return False
    
    def get_can_submit(self, obj):
        request = self.context.get('request')
        if not request or not request.user:
            return False
        
        # Can submit if DRAFT, has ratings, and is own assessment
        if obj.employee.user == request.user and obj.status == 'DRAFT':
            return obj.skill_ratings.exists()
        
        return False
    
    def get_can_review(self, obj):
        request = self.context.get('request')
        if not request or not request.user:
            return False
        
        # Manager can review if SUBMITTED and they are line manager
        if obj.status == 'SUBMITTED':
            if obj.employee.line_manager and obj.employee.line_manager.user == request.user:
                return True
        
        # Admin can always review
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        return False


class SelfAssessmentListSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    period_name = serializers.CharField(source='period.name', read_only=True)
    ratings_count = serializers.SerializerMethodField()
    
    class Meta:
        model = SelfAssessment
        fields = [
            'id', 'employee', 'employee_name', 'employee_id',
            'period', 'period_name', 'status',
            'overall_score', 'ratings_count',
            'submitted_at', 'created_at'
        ]
    
    def get_ratings_count(self, obj):
        return obj.skill_ratings.count()


class SelfAssessmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SelfAssessment
        fields = ['period']


# Activity Serializer
class AssessmentActivitySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = AssessmentActivity
        fields = [
            'id', 'activity_type', 'description',
            'performed_by', 'performed_by_name', 'metadata', 'created_at'
        ]
    
    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return obj.performed_by.get_full_name() or obj.performed_by.username
        return 'System'


# Statistics Serializer
class AssessmentStatsSerializer(serializers.Serializer):
    total_periods = serializers.IntegerField()
    active_period = AssessmentPeriodSerializer(allow_null=True)
    my_assessments_count = serializers.IntegerField()
    team_assessments_count = serializers.IntegerField()
    pending_reviews = serializers.IntegerField()
    my_average_score = serializers.FloatField()
    team_average_score = serializers.FloatField()
    my_last_assessment = SelfAssessmentListSerializer(allow_null=True)