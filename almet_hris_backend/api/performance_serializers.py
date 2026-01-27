# api/performance_serializers.py

from rest_framework import serializers
from django.db import transaction
from .performance_models import *
from .models import Employee
from .competency_models import BehavioralCompetency, BehavioralCompetencyGroup  # CHANGED
from .competency_assessment_models import PositionBehavioralAssessment  # ADDED


class PerformanceYearSerializer(serializers.ModelSerializer):
    current_period = serializers.SerializerMethodField()
    
    class Meta:
        model = PerformanceYear
        fields = '__all__'
    
    def get_current_period(self, obj):
        return obj.get_current_period()


class PerformanceWeightConfigSerializer(serializers.ModelSerializer):
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    
    class Meta:
        model = PerformanceWeightConfig
        fields = '__all__'


class GoalLimitConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalLimitConfig
        fields = '__all__'


class DepartmentObjectiveSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    class Meta:
        model = DepartmentObjective
        fields = '__all__'


class EvaluationScaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvaluationScale
        fields = '__all__'


class EvaluationTargetConfigSerializer(serializers.ModelSerializer):
    """UPDATED: Removed competency_score_target"""
    class Meta:
        model = EvaluationTargetConfig
        fields = '__all__'


class ObjectiveStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ObjectiveStatus
        fields = '__all__'


class BehavioralCompetencyGroupWithCompetenciesSerializer(serializers.ModelSerializer):
    """NEW: Behavioral Competency Group with Competencies for performance"""
    competencies = serializers.SerializerMethodField()
    
    class Meta:
        model = BehavioralCompetencyGroup
        fields = ['id', 'name', 'competencies']
    
    def get_competencies(self, obj):
        competencies = obj.competencies.all()
        return [{'id': c.id, 'name': c.name} for c in competencies]


class ObjectiveCommentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = ObjectiveComment
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at', 'updated_at']
    
    def get_created_by_name(self, obj):
        """Get full name or username"""
        if obj.created_by:
            full_name = obj.created_by.get_full_name()
            return full_name if full_name.strip() else obj.created_by.username
        return 'Unknown'


# ✅ UPDATE: EmployeeObjectiveSerializer - comments əlavə et
class EmployeeObjectiveSerializer(serializers.ModelSerializer):
    linked_department_objective_title = serializers.CharField(
        source='linked_department_objective.title', 
        read_only=True,
        allow_null=True
    )
    status_label = serializers.CharField(source='status.label', read_only=True)
    status_value = serializers.CharField(source='status.value', read_only=True)
    end_year_rating_name = serializers.CharField(source='end_year_rating.name', read_only=True, allow_null=True)
    end_year_rating_value = serializers.IntegerField(source='end_year_rating.value', read_only=True, allow_null=True)
    
    # ✅ NEW: Comments
    comments = ObjectiveCommentSerializer(many=True, read_only=True)
    comments_count = serializers.SerializerMethodField()
    
    end_year_rating = serializers.PrimaryKeyRelatedField(
        queryset=EvaluationScale.objects.all(),
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = EmployeeObjective
        fields = '__all__'
    
    def get_comments_count(self, obj):
        """Get total comments count"""
        return obj.comments.count()



class EmployeeCompetencyRatingSerializer(serializers.ModelSerializer):
    """
    ✅ FIXED: Safe handling of None values
    """
    # ✅ PRIMARY: Universal competency name
    competency_name = serializers.SerializerMethodField()
    
    # ✅ BEHAVIORAL fields - with null handling
    behavioral_competency_id = serializers.SerializerMethodField()
    behavioral_competency_name = serializers.SerializerMethodField()
    competency_group_name = serializers.SerializerMethodField()
    
    # ✅ LEADERSHIP fields - with null handling
    leadership_item_id = serializers.SerializerMethodField()
    leadership_item_name = serializers.SerializerMethodField()
    main_group_name = serializers.SerializerMethodField()
    child_group_name = serializers.SerializerMethodField()
    
    # Common fields
    end_year_rating_name = serializers.SerializerMethodField()
    end_year_rating_value = serializers.SerializerMethodField()
    actual_value = serializers.IntegerField(read_only=True)
    gap = serializers.IntegerField(read_only=True)
    gap_status = serializers.SerializerMethodField()
    competency_type = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeCompetencyRating
        fields = [
            'id',
            'performance',
            # Universal
            'competency_name',
            'competency_type',
            # Behavioral
            'behavioral_competency',
            'behavioral_competency_id',
            'behavioral_competency_name',
            'competency_group_name',
            # Leadership
            'leadership_item',
            'leadership_item_id', 
            'leadership_item_name',
            'main_group_name',
            'child_group_name',
            # Ratings
            'required_level',
            'end_year_rating',
            'end_year_rating_name',
            'end_year_rating_value',
            'actual_value',
            'gap',
            'gap_status',
            'notes',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'actual_value', 'gap']
    
    # ✅ SAFE METHODS with None handling
    
    def get_competency_name(self, obj):
        """Get competency name - safe"""
        try:
            if obj.leadership_item:
                return obj.leadership_item.name
            elif obj.behavioral_competency:
                return obj.behavioral_competency.name
        except Exception as e:
            logger.warning(f"Error getting competency name: {e}")
        return 'Unknown Competency'
    
    def get_behavioral_competency_id(self, obj):
        """Safe get behavioral competency ID"""
        try:
            return obj.behavioral_competency.id if obj.behavioral_competency else None
        except:
            return None
    
    def get_behavioral_competency_name(self, obj):
        """Safe get behavioral competency name"""
        try:
            return obj.behavioral_competency.name if obj.behavioral_competency else None
        except:
            return None
    
    def get_competency_group_name(self, obj):
        """Get group name (behavioral only) - safe"""
        try:
            if obj.behavioral_competency and hasattr(obj.behavioral_competency, 'group'):
                return obj.behavioral_competency.group.name
        except Exception as e:
            logger.warning(f"Error getting competency group name: {e}")
        return None
    
    def get_leadership_item_id(self, obj):
        """Safe get leadership item ID"""
        try:
            return obj.leadership_item.id if obj.leadership_item else None
        except:
            return None
    
    def get_leadership_item_name(self, obj):
        """Safe get leadership item name"""
        try:
            return obj.leadership_item.name if obj.leadership_item else None
        except:
            return None
    
    def get_main_group_name(self, obj):
        """Get main group name (leadership only) - safe"""
        try:
            if obj.leadership_item and hasattr(obj.leadership_item, 'child_group'):
                child_group = obj.leadership_item.child_group
                if child_group and hasattr(child_group, 'main_group'):
                    return child_group.main_group.name
        except Exception as e:
            logger.warning(f"Error getting main group name: {e}")
        return None
    
    def get_child_group_name(self, obj):
        """Get child group name (leadership only) - safe"""
        try:
            if obj.leadership_item and hasattr(obj.leadership_item, 'child_group'):
                child_group = obj.leadership_item.child_group
                if child_group:
                    return child_group.name
        except Exception as e:
            logger.warning(f"Error getting child group name: {e}")
        return None
    
    def get_end_year_rating_name(self, obj):
        """Safe get rating name"""
        try:
            return obj.end_year_rating.name if obj.end_year_rating else None
        except:
            return None
    
    def get_end_year_rating_value(self, obj):
        """Safe get rating value"""
        try:
            return obj.end_year_rating.value if obj.end_year_rating else None
        except:
            return None
    
    def get_competency_type(self, obj):
        """Get competency type - safe"""
        try:
            if obj.leadership_item:
                return 'LEADERSHIP'
            elif obj.behavioral_competency:
                return 'BEHAVIORAL'
        except:
            pass
        return 'UNKNOWN'
    
    def get_gap_status(self, obj):
        """Get gap status - safe"""
        try:
            gap = obj.gap
            if gap > 0:
                return 'exceeds'
            elif gap == 0:
                return 'meets'
            else:
                return 'below'
        except:
            return 'unknown'

class DevelopmentNeedSerializer(serializers.ModelSerializer):
    class Meta:
        model = DevelopmentNeed
        fields = '__all__'


class PerformanceCommentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    replies = serializers.SerializerMethodField()
    
    class Meta:
        model = PerformanceComment
        fields = '__all__'
    
    def get_created_by_name(self, obj):
        """Get full name or username"""
        if obj.created_by:
            full_name = obj.created_by.get_full_name()
            return full_name if full_name.strip() else obj.created_by.username
        return 'Unknown'
    
    def get_replies(self, obj):
        if obj.replies.exists():
            return PerformanceCommentSerializer(obj.replies.all(), many=True).data
        return []

class PerformanceActivityLogSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source='performed_by.get_full_name', read_only=True)
    
    class Meta:
        model = PerformanceActivityLog
        fields = '__all__'



# api/performance_serializers.py

import logging
logger = logging.getLogger(__name__)
class EmployeePerformanceListSerializer(serializers.ModelSerializer):
    """Simplified serializer for list view - FIXED"""
    employee_name = serializers.SerializerMethodField()
    employee_id = serializers.SerializerMethodField()
    employee_position_group = serializers.SerializerMethodField()
    employee_department = serializers.SerializerMethodField()
    employee_company = serializers.SerializerMethodField()
    year = serializers.SerializerMethodField()
    
    # CRITICAL FIX: Add current_period
    current_period = serializers.SerializerMethodField()

    
    # Draft status indicators
    has_objectives_draft = serializers.SerializerMethodField()
    has_competencies_draft = serializers.SerializerMethodField()

  
    objectives_percentage = serializers.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        read_only=True
    )
    
    # ✅ NEW: Add competencies_percentage to list
    competencies_percentage = serializers.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        read_only=True
    )
    class Meta:
        model = EmployeePerformance
        fields = [
            'id', 'employee', 'employee_name', 'employee_id', 
            'employee_position_group', 'employee_department','employee_company',
            'year', 'current_period','objectives_percentage', 'competencies_percentage',
            'approval_status',
         
            'objectives_employee_submitted', 'objectives_employee_approved', 
            'objectives_manager_approved',
            'mid_year_completed', 'end_year_completed',
            'final_employee_approved', 'final_manager_approved',
            'overall_weighted_percentage', 'final_rating',
            'competencies_letter_grade',
            'has_objectives_draft', 'has_competencies_draft', 
        
            'created_at', 'updated_at'
        ]
    
    # ✅ ALL SAFE METHODS
    
    def get_employee_name(self, obj):
        """Safe get employee name"""
        try:
            return obj.employee.full_name if obj.employee else 'Unknown'
        except Exception as e:
            logger.warning(f"Error getting employee name: {e}")
            return 'Unknown'
    
    def get_employee_id(self, obj):
        """Safe get employee ID"""
        try:
            return obj.employee.employee_id if obj.employee else None
        except Exception as e:
            logger.warning(f"Error getting employee_id: {e}")
            return None
    
    def get_employee_position_group(self, obj):
        """Safe get position group"""
        try:
            if obj.employee and obj.employee.position_group:
                return obj.employee.position_group.get_name_display()
            return 'Unknown'
        except Exception as e:
            logger.warning(f"Error getting position_group: {e}")
            return 'Unknown'
    def get_employee_company(self, obj):
        """Safe get company"""
        try:
            if obj.employee and obj.employee.business_function:
                # Business function obyektini çək
                bf = obj.employee.business_function
                
                # Name field-i varsa
                if hasattr(bf, 'name'):
                    return bf.name
                
                # Title field-i varsa  
                if hasattr(bf, 'title'):
                    return bf.title
                
                # Yoxsa str() ilə göstər
                return str(bf)
                
            return 'Unknown'
        except Exception as e:
            logger.warning(f"Error getting business_function: {e}")
            return 'Unknown'
    
    def get_employee_department(self, obj):
        """Safe get department"""
        try:
            if obj.employee and obj.employee.department:
                return obj.employee.department.name
            return 'N/A'
        except Exception as e:
            logger.warning(f"Error getting department: {e}")
            return 'N/A'
    
    def get_year(self, obj):
        """Safe get year"""
        try:
            return obj.performance_year.year if obj.performance_year else None
        except Exception as e:
            logger.warning(f"Error getting year: {e}")
            return None
    
    def get_current_period(self, obj):
        """Get current period from performance year - CRITICAL FIX"""
        try:
            if obj.performance_year:
                return obj.performance_year.get_current_period()
            return None
        except Exception as e:
            logger.warning(f"Error getting current_period: {e}")
            return None
    
  
    
    def get_has_objectives_draft(self, obj):
        """Safe check objectives draft"""
        try:
            return obj.objectives_draft_saved_date is not None
        except:
            return False
    
    def get_has_competencies_draft(self, obj):
        """Safe check competencies draft"""
        try:
            return obj.competencies_draft_saved_date is not None
        except:
            return False
    
    
    
    def get_has_dev_needs_draft(self, obj):
        """Safe check dev needs draft"""
        try:
            return obj.development_needs_draft_saved is not None
        except:
            return False
class EmployeePerformanceDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer with all related data"""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    employee_department = serializers.SerializerMethodField()  # ✅ Changed to safe method
    employee_position_group = serializers.CharField(
        source='employee.position_group.get_name_display', 
        read_only=True
    )
    employee_grade_level = serializers.CharField(source='employee.grading_level', read_only=True)
    line_manager_name = serializers.SerializerMethodField()  # ✅ Changed to safe method
    
    year = serializers.IntegerField(source='performance_year.year', read_only=True)
    current_period = serializers.CharField(source='performance_year.get_current_period', read_only=True)
    
    objectives = EmployeeObjectiveSerializer(many=True, read_only=True)
    competency_ratings = EmployeeCompetencyRatingSerializer(many=True, read_only=True)
    development_needs = serializers.SerializerMethodField()
    
    # ✅ Clarification comments
    clarification_comments = serializers.SerializerMethodField()
    
    comments = PerformanceCommentSerializer(many=True, read_only=True)
    activity_logs = PerformanceActivityLogSerializer(many=True, read_only=True)
    
    # Weight configuration
    weight_config = serializers.SerializerMethodField()
    objectives_weight = serializers.SerializerMethodField()
    competencies_weight = serializers.SerializerMethodField()
    
    # Evaluation targets
    evaluation_targets = serializers.SerializerMethodField()
    
    # Goal limits
    goal_limits = serializers.SerializerMethodField()
    
    # Group competency scores breakdown
    group_scores_breakdown = serializers.SerializerMethodField()
    metadata = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeePerformance
        fields = '__all__'
    
    # ✅ SAFE METHODS
    
    def get_employee_department(self, obj):
        """Safe get department name"""
        try:
            return obj.employee.department.name if obj.employee.department else 'N/A'
        except:
            return 'N/A'
    
    def get_line_manager_name(self, obj):
        """Safe get line manager name"""
        try:
            return obj.employee.line_manager.full_name if obj.employee.line_manager else None
        except:
            return None
    def get_development_needs(self, obj):
        """Safe get development needs"""
        try:
            needs = obj.development_needs.all()
            return DevelopmentNeedSerializer(needs, many=True).data
        except Exception as e:
            logger.warning(f"Error getting development_needs: {e}")
            return []
    def get_metadata(self, obj):
        """Get metadata about competency type - safe"""
        try:
            first_rating = obj.competency_ratings.first()
            
            if not first_rating:
                return {
                    'has_competencies': False,
                    'competency_type': None,
                    'is_leadership_position': False
                }
            
            is_leadership = bool(first_rating.leadership_item)
            
            return {
                'has_competencies': True,
                'competency_type': 'LEADERSHIP' if is_leadership else 'BEHAVIORAL',
                'is_leadership_position': is_leadership,
                'had_existing_ratings': obj.competency_ratings.filter(
                    end_year_rating__isnull=False
                ).exists()
            }
        except Exception as e:
            logger.warning(f"Error getting metadata: {e}")
            return {
                'has_competencies': False,
                'competency_type': None,
                'is_leadership_position': False
            }
    
    def get_clarification_comments(self, obj):
        """Get all clarification-related comments - safe"""
        try:
            clarification_comments = obj.comments.filter(
                comment_type__in=['OBJECTIVE_CLARIFICATION', 'FINAL_CLARIFICATION']
            ).select_related('created_by').order_by('-created_at')
            
            return PerformanceCommentSerializer(clarification_comments, many=True).data
        except Exception as e:
            logger.warning(f"Error getting clarification comments: {e}")
            return []
    
    def get_weight_config(self, obj):
        """Safe get weight config"""
        try:
            weight = PerformanceWeightConfig.objects.filter(
                position_group=obj.employee.position_group
            ).first()
            if weight:
                return {
                    'objectives_weight': weight.objectives_weight,
                    'competencies_weight': weight.competencies_weight
                }
        except Exception as e:
            logger.warning(f"Error getting weight config: {e}")
        return None
    
    def get_objectives_weight(self, obj):
        """Get objectives weight percentage - safe"""
        try:
            weight = PerformanceWeightConfig.objects.filter(
                position_group=obj.employee.position_group
            ).first()
            return weight.objectives_weight if weight else 70
        except:
            return 70
    
    def get_competencies_weight(self, obj):
        """Get competencies weight percentage - safe"""
        try:
            weight = PerformanceWeightConfig.objects.filter(
                position_group=obj.employee.position_group
            ).first()
            return weight.competencies_weight if weight else 30
        except:
            return 30
    
    def get_evaluation_targets(self, obj):
        """Safe get evaluation targets"""
        try:
            config = EvaluationTargetConfig.get_active_config()
            return {
                'objective_score_target': config.objective_score_target,
            }
        except:
            return {
                'objective_score_target': 21,
            }
    
    def get_goal_limits(self, obj):
        """Safe get goal limits"""
        try:
            config = GoalLimitConfig.get_active_config()
            return {
                'min_goals': config.min_goals,
                'max_goals': config.max_goals
            }
        except:
            return {
                'min_goals': 3,
                'max_goals': 7
            }
    
    def get_group_scores_breakdown(self, obj):
        """Get detailed breakdown of competency scores by group - safe"""
        try:
            return obj.group_competency_scores or {}
        except:
            return {}
class EmployeePerformanceCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating performance with nested data"""
    objectives_data = serializers.ListField(write_only=True, required=False)
    competency_ratings_data = serializers.ListField(write_only=True, required=False)
    development_needs_data = serializers.ListField(write_only=True, required=False)
    
    class Meta:
        model = EmployeePerformance
        fields = [
            'id', 'employee', 'performance_year', 'approval_status',
            'mid_year_employee_comment', 'mid_year_manager_comment',
            'end_year_employee_comment', 'end_year_manager_comment',
            'objectives_data', 'competency_ratings_data', 'development_needs_data'
        ]
        read_only_fields = ['id']
    
    def create(self, validated_data):
        objectives_data = validated_data.pop('objectives_data', [])
        competency_ratings_data = validated_data.pop('competency_ratings_data', [])
        development_needs_data = validated_data.pop('development_needs_data', [])
        
        with transaction.atomic():
            # Create performance record
            performance = EmployeePerformance.objects.create(**validated_data)
            
            # Create objectives
            for idx, obj_data in enumerate(objectives_data):
                EmployeeObjective.objects.create(
                    performance=performance,
                    display_order=idx,
                    **obj_data
                )
            
            # Create competency ratings
            for comp_data in competency_ratings_data:
                EmployeeCompetencyRating.objects.create(
                    performance=performance,
                    **comp_data
                )
            
            # Create development needs
            for dev_data in development_needs_data:
                DevelopmentNeed.objects.create(
                    performance=performance,
                    **dev_data
                )
            
            # Log activity
            PerformanceActivityLog.objects.create(
                performance=performance,
                action='CREATED',
                description=f'Performance record created for {performance.employee.full_name}',
                performed_by=self.context['request'].user if 'request' in self.context else None
            )
            
            return performance
    
    def update(self, instance, validated_data):
        objectives_data = validated_data.pop('objectives_data', None)
        competency_ratings_data = validated_data.pop('competency_ratings_data', None)
        development_needs_data = validated_data.pop('development_needs_data', None)
        
        with transaction.atomic():
            # Update performance fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            
            # Update objectives if provided
            if objectives_data is not None:
                updated_ids = []
                for idx, obj_data in enumerate(objectives_data):
                    obj_id = obj_data.pop('id', None)
                    if obj_id:
                        EmployeeObjective.objects.filter(id=obj_id, performance=instance).update(
                            display_order=idx, **obj_data
                        )
                        updated_ids.append(obj_id)
                    else:
                        new_obj = EmployeeObjective.objects.create(
                            performance=instance,
                            display_order=idx,
                            **obj_data
                        )
                        updated_ids.append(new_obj.id)
                
                instance.objectives.exclude(id__in=updated_ids).delete()
            
            # Update competency ratings if provided
            if competency_ratings_data is not None:
                for comp_data in competency_ratings_data:
                    comp_id = comp_data.pop('id', None)
                    behavioral_competency_id = comp_data.get('behavioral_competency')
                    
                    if comp_id:
                        EmployeeCompetencyRating.objects.filter(
                            id=comp_id, 
                            performance=instance
                        ).update(**comp_data)
                    else:
                        EmployeeCompetencyRating.objects.update_or_create(
                            performance=instance,
                            behavioral_competency_id=behavioral_competency_id,
                            defaults=comp_data
                        )
            
            # Update development needs if provided
            if development_needs_data is not None:
                updated_dev_ids = []
                for dev_data in development_needs_data:
                    dev_id = dev_data.pop('id', None)
                    if dev_id:
                        DevelopmentNeed.objects.filter(id=dev_id, performance=instance).update(**dev_data)
                        updated_dev_ids.append(dev_id)
                    else:
                        new_dev = DevelopmentNeed.objects.create(performance=instance, **dev_data)
                        updated_dev_ids.append(new_dev.id)
                
                instance.development_needs.exclude(id__in=updated_dev_ids).delete()
            
            # Recalculate scores if end-year ratings provided
            if competency_ratings_data or objectives_data:
                instance.calculate_scores()
            
            # Log activity
            PerformanceActivityLog.objects.create(
                performance=instance,
                action='UPDATED',
                description=f'Performance record updated for {instance.employee.full_name}',
                performed_by=self.context['request'].user if 'request' in self.context else None
            )
            
            return instance


class PerformanceNotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceNotificationTemplate
        fields = '__all__'


class PerformanceDashboardSerializer(serializers.Serializer):
    """Serializer for dashboard statistics"""
    total_employees = serializers.IntegerField()
    objectives_completed = serializers.IntegerField()
    mid_year_completed = serializers.IntegerField()
    end_year_completed = serializers.IntegerField()
    
    current_period = serializers.CharField()
    year = serializers.IntegerField()
    
    timeline = serializers.DictField()
    by_department = serializers.ListField()
    # recent_activities = serializers.ListField()
    
    # Additional stats
    pending_employee_approval = serializers.IntegerField()
    pending_manager_approval = serializers.IntegerField()
    need_clarification = serializers.IntegerField()


class PerformanceInitializeSerializer(serializers.Serializer):
    """
    ✅ FIXED: Load leadership OR behavioral competencies based on position
    """
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    performance_year = serializers.PrimaryKeyRelatedField(queryset=PerformanceYear.objects.all())
    
    def validate(self, data):
        """Validate and determine which assessment type to use"""
        employee = data['employee']
        
        # ✅ Check if this is a leadership position
        position_group = employee.position_group
        position_name = position_group.name.upper().replace('_', ' ').strip()
        
      
        
        leadership_keywords = [
            'MANAGER',
            'VICE CHAIRMAN',
            'VICE_CHAIRMAN',
            'DIRECTOR',
            'VICE',
            'HOD',
            'HEAD OF DEPARTMENT'
        ]
        
        is_leadership = any(
            keyword.upper().replace('_', ' ') == position_name or
            keyword.upper() == employee.position_group.name.upper() or
            position_name.startswith(keyword.upper()) or
            keyword.upper() in position_name
            for keyword in leadership_keywords
        )
        
    
        
        # ✅ CRITICAL FIX: Initialize employee_assessment to None
        employee_assessment = None
        
        if is_leadership:
            # ✅ Load leadership position assessment
            from .competency_assessment_models import PositionLeadershipAssessment, EmployeeLeadershipAssessment
            
            position_assessment = PositionLeadershipAssessment.objects.filter(
                position_group=employee.position_group,
                grade_levels__contains=[employee.grading_level],
                is_active=True
            ).prefetch_related(
                'competency_ratings',
                'competency_ratings__leadership_item',
                'competency_ratings__leadership_item__child_group',
                'competency_ratings__leadership_item__child_group__main_group'
            ).first()
            
            if not position_assessment:
                raise serializers.ValidationError(
                    f"❌ No LEADERSHIP assessment template found for:\n"
                    f"  • Position: {employee.position_group.get_name_display()}\n"
                    f"  • Grade Level: {employee.grading_level}\n"
                    f"  • Position Name (DB): {employee.position_group.name}\n\n"
                    f"👉 ACTION REQUIRED:\n"
                    f"  1. Go to Leadership Assessment Templates\n"
                    f"  2. Create template for '{employee.position_group.get_name_display()}'\n"
                    f"  3. Include grade level '{employee.grading_level}'\n"
                    f"  4. Add all required leadership competencies\n"
                )
            
          
            
            # Get employee leadership assessment if exists
            employee_assessment = EmployeeLeadershipAssessment.objects.filter(
                employee=employee,
                status__in=['DRAFT', 'COMPLETED']
            ).order_by('-assessment_date').first()
            
        else:
            # ✅ Load behavioral position assessment
            from .competency_assessment_models import PositionBehavioralAssessment, EmployeeBehavioralAssessment
            
            position_assessment = PositionBehavioralAssessment.objects.filter(
                position_group=employee.position_group,
                grade_levels__contains=[employee.grading_level],
                is_active=True
            ).prefetch_related(
                'competency_ratings',
                'competency_ratings__behavioral_competency',
                'competency_ratings__behavioral_competency__group'
            ).first()
            
            if not position_assessment:
                raise serializers.ValidationError(
                    f"No behavioral assessment template found for {employee.position_group.get_name_display()} "
                    f"(Grade {employee.grading_level}). Please create position assessment first."
                )
            
         
            
            # Get employee behavioral assessment if exists
            employee_assessment = EmployeeBehavioralAssessment.objects.filter(
                employee=employee,
                status__in=['DRAFT', 'COMPLETED']
            ).order_by('-assessment_date').first()
        
        data['position_assessment'] = position_assessment
        data['employee_assessment'] = employee_assessment  # ✅ Always set (can be None)
        data['is_leadership_position'] = is_leadership
        
        return data
    
    def create(self, validated_data):
        employee = validated_data['employee']
        performance_year = validated_data['performance_year']
        position_assessment = validated_data['position_assessment']
        employee_assessment = validated_data.get('employee_assessment')  # ✅ Use .get() for safety
        is_leadership = validated_data['is_leadership_position']
        
        # Check if already exists
        existing = EmployeePerformance.objects.filter(
            employee=employee,
            performance_year=performance_year
        ).first()
        
        if existing:
            print(f"ℹ️ [Backend] Performance already exists: ID {existing.id}")
            return existing
        
        with transaction.atomic():
            # Create performance record
            performance = EmployeePerformance.objects.create(
                employee=employee,
                performance_year=performance_year,
                approval_status='DRAFT'
            )
            
     
            
            # ✅ CRITICAL: Use PerformanceEvaluationScale
            from .performance_models import EvaluationScale
            
            if is_leadership:
                # ============ LEADERSHIP COMPETENCIES ============
              
                
                position_ratings = position_assessment.competency_ratings.select_related(
                    'leadership_item',
                    'leadership_item__child_group',
                    'leadership_item__child_group__main_group'
                ).all()
                

                
                created_count = 0
                for position_rating in position_ratings:
                    # ✅ CRITICAL CHECK
                    if not position_rating.leadership_item:
                        print(f"⚠️ [Backend] Position rating {position_rating.id} has NULL leadership_item!")
                        continue
                    
                    # Find existing rating from employee assessment (if exists)
                    existing_rating = None
                    end_year_rating_id = None
                    
                    if employee_assessment:  # ✅ Check if not None
                        existing_rating = employee_assessment.competency_ratings.filter(
                            leadership_item=position_rating.leadership_item
                        ).first()
                        
                        # ✅ Convert actual_level to PerformanceEvaluationScale ID
                        if existing_rating and existing_rating.actual_level:
                            performance_scale = EvaluationScale.objects.filter(
                                value=existing_rating.actual_level,
                                is_active=True
                            ).first()
                            if performance_scale:
                                end_year_rating_id = performance_scale.id
                    
                    # ✅ Create competency rating with leadership_item
                    rating = EmployeeCompetencyRating.objects.create(
                        performance=performance,
                        leadership_item=position_rating.leadership_item,
                        required_level=position_rating.required_level,
                        end_year_rating_id=end_year_rating_id,
                        notes=existing_rating.notes if existing_rating else ''
                    )
                    
                    created_count += 1
                    
                    if created_count <= 3:  # Only log first 3
                        print(f"  ✅ Created rating {created_count}: {position_rating.leadership_item.name[:50]}")
                
                log_message = (
                    f'Performance initialized with {created_count} leadership competencies'
                )
                
               
                
            else:
            
                
                position_ratings = position_assessment.competency_ratings.select_related(
                    'behavioral_competency',
                    'behavioral_competency__group'
                ).all()
                
                
                
                created_count = 0
                for position_rating in position_ratings:
                    if not position_rating.behavioral_competency:
                        print(f"⚠️ [Backend] Position rating {position_rating.id} has NULL behavioral_competency!")
                        continue
                    
                    existing_rating = None
                    end_year_rating_id = None
                    
                    if employee_assessment:  # ✅ Check if not None
                        existing_rating = employee_assessment.competency_ratings.filter(
                            behavioral_competency=position_rating.behavioral_competency
                        ).first()
                        
                        if existing_rating and existing_rating.actual_level:
                            performance_scale = EvaluationScale.objects.filter(
                                value=existing_rating.actual_level,
                                is_active=True
                            ).first()
                            if performance_scale:
                                end_year_rating_id = performance_scale.id
                    
                    rating = EmployeeCompetencyRating.objects.create(
                        performance=performance,
                        behavioral_competency=position_rating.behavioral_competency,
                        required_level=position_rating.required_level,
                        end_year_rating_id=end_year_rating_id,
                        notes=existing_rating.notes if existing_rating else ''
                    )
                    
                    created_count += 1
                    
                    if created_count <= 3:
                        print(f"  ✅ Created rating {created_count}: {position_rating.behavioral_competency.name}")
                
                log_message = (
                    f'Performance initialized with {created_count} behavioral competencies'
                )
                
      
            
            if employee_assessment:
                log_message += f' (loaded existing ratings from assessment {employee_assessment.id})'
            
            PerformanceActivityLog.objects.create(
                performance=performance,
                action='INITIALIZED',
                description=log_message,
                performed_by=self.context.get('request').user if self.context.get('request') else None,
                metadata={
                    'position_assessment_id': str(position_assessment.id),
                    'employee_assessment_id': str(employee_assessment.id) if employee_assessment else None,
                    'had_existing_ratings': bool(employee_assessment),
                    'is_leadership_position': is_leadership
                }
            )
            
            return performance