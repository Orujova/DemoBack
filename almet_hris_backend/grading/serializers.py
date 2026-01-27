# grading/serializers.py - FIXED: Complete input data preservation in both list and detail

from rest_framework import serializers
from .models import GradingSystem, SalaryGrade, SalaryScenario, ScenarioHistory
from api.models import PositionGroup
import logging

logger = logging.getLogger(__name__)

# Helper serializers
class _GradeValueSerializer(serializers.Serializer):
    """Helper serializer for a single grade's details"""
    LD = serializers.CharField(allow_blank=True, required=False)
    LQ = serializers.CharField(allow_blank=True, required=False)
    M = serializers.CharField(allow_blank=True, required=False)
    UQ = serializers.CharField(allow_blank=True, required=False)
    UD = serializers.CharField(allow_blank=True, required=False)
    vertical = serializers.FloatField(required=False, allow_null=True)
    horizontal_intervals = serializers.DictField(
        child=serializers.FloatField(min_value=0, max_value=100),
        required=False,
        allow_empty=True
    )

# Main serializers
class CurrentStructureSerializer(serializers.Serializer):
    """Serializer for the current grade structure"""
    id = serializers.CharField()
    name = serializers.CharField()
    grades = serializers.DictField(child=_GradeValueSerializer(), required=False)
    gradeOrder = serializers.ListField(child=serializers.CharField())
    verticalAvg = serializers.FloatField()
    horizontalAvg = serializers.FloatField()
    baseValue1 = serializers.FloatField()
    status = serializers.CharField()


class GradingSystemSerializer(serializers.ModelSerializer):
    salary_grades_count = serializers.SerializerMethodField()
    scenarios_count = serializers.SerializerMethodField()
    current_scenario = serializers.SerializerMethodField()
    
    class Meta:
        model = GradingSystem
        fields = [
            'id', 'name', 'description', 'is_active', 'base_currency',
            'salary_grades_count', 'scenarios_count', 'current_scenario',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_salary_grades_count(self, obj):
        return obj.salary_grades.count()
    
    def get_scenarios_count(self, obj):
        return obj.scenarios.count()
    
    def get_current_scenario(self, obj):
        try:
            current = obj.scenarios.get(status='CURRENT')
            return {'id': str(current.id), 'name': current.name}
        except SalaryScenario.DoesNotExist:
            return None

class SalaryGradeSerializer(serializers.ModelSerializer):
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    hierarchy_level = serializers.IntegerField(source='position_group.hierarchy_level', read_only=True)
    
    class Meta:
        model = SalaryGrade
        fields = [
            'id', 'grading_system', 'position_group', 'position_group_name', 
            'hierarchy_level', 'lower_decile', 'lower_quartile', 'median', 
            'upper_quartile', 'upper_decile', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class SalaryScenarioListSerializer(serializers.ModelSerializer):
    """FIXED: List serializer with complete input data for comparison"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    is_calculated = serializers.SerializerMethodField()
    grading_system_name = serializers.CharField(source='grading_system.name', read_only=True)
    data = serializers.SerializerMethodField()
    
    class Meta:
        model = SalaryScenario
        fields = [
            'id', 'name', 'status', 'grading_system_name', 'base_value', 
            'vertical_avg', 'horizontal_avg', 'metrics', 'data',
            'is_calculated', 'created_by_name', 
            'created_at', 'calculation_timestamp',
            # FIXED: Add input_rates to list for comparison
            'input_rates'
        ]
    
    def get_is_calculated(self, obj):
        return bool(obj.calculated_grades and obj.calculation_timestamp)
    
    def get_data(self, obj):
        """FIXED: Format data for list display with complete input preservation"""
      
        
        calculated_grades = {}
        if obj.calculated_grades and isinstance(obj.calculated_grades, dict):
            calculated_grades = obj.calculated_grades
        
        grade_order = obj.grade_order if obj.grade_order else []
        
        # FIXED: Extract input data just like in detail serializer
        position_vertical_inputs = {}
        global_horizontal_intervals = {
            'LD_to_LQ': 0,
            'LQ_to_M': 0,
            'M_to_UQ': 0,
            'UQ_to_UD': 0
        }
        
        if obj.input_rates and isinstance(obj.input_rates, dict):
            # Get vertical inputs for each position
            for grade_name in grade_order:
                grade_input_data = obj.input_rates.get(grade_name, {})
                if isinstance(grade_input_data, dict):
                    vertical_value = grade_input_data.get('vertical')
                    position_vertical_inputs[grade_name] = vertical_value
                    
                    # Get global intervals from first position with intervals
                    intervals = grade_input_data.get('horizontal_intervals', {})
                    if intervals and isinstance(intervals, dict) and not any(global_horizontal_intervals.values()):
                        for key in global_horizontal_intervals.keys():
                            if key in intervals and intervals[key] is not None:
                                try:
                                    global_horizontal_intervals[key] = float(intervals[key])
                                except (ValueError, TypeError):
                                    pass
        
     
        
        # FIXED: Enhanced grades with input data for comparison
        enhanced_grades = {}
        for grade_name in grade_order:
            if grade_name not in calculated_grades:
                calculated_grades[grade_name] = {
                    'LD': 0, 'LQ': 0, 'M': 0, 'UQ': 0, 'UD': 0
                }
            else:
                grade_data = calculated_grades[grade_name]
                if isinstance(grade_data, dict):
                    for field in ['LD', 'LQ', 'M', 'UQ', 'UD']:
                        if field not in grade_data or grade_data[field] is None:
                            grade_data[field] = 0
                else:
                    calculated_grades[grade_name] = {
                        'LD': 0, 'LQ': 0, 'M': 0, 'UQ': 0, 'UD': 0
                    }
            
            # FIXED: Add input data to grades for comparison
            enhanced_grades[grade_name] = {
                **calculated_grades[grade_name],
                'verticalInput': position_vertical_inputs.get(grade_name),
                'vertical': position_vertical_inputs.get(grade_name),
                'horizontal_intervals': global_horizontal_intervals
            }
        
        return {
            'baseValue1': float(obj.base_value) if obj.base_value else 0,
            'gradeOrder': grade_order,
            'grades': enhanced_grades,  # FIXED: Now includes input data
            'verticalAvg': float(obj.vertical_avg) if obj.vertical_avg else 0,
            'horizontalAvg': float(obj.horizontal_avg) if obj.horizontal_avg else 0,
            
            # FIXED: Add input data for comparison
            'positionVerticalInputs': position_vertical_inputs,
            'globalHorizontalIntervals': global_horizontal_intervals,
            'inputRates': obj.input_rates or {},
            'hasCalculation': bool(obj.calculated_grades and obj.calculation_timestamp)
        }

class SalaryScenarioDetailSerializer(serializers.ModelSerializer):
    """ENHANCED: Detail serializer with proper input data preservation"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    applied_by_name = serializers.CharField(source='applied_by.get_full_name', read_only=True)
    is_calculated = serializers.SerializerMethodField()
    grading_system_name = serializers.CharField(source='grading_system.name', read_only=True)
    data = serializers.SerializerMethodField()
    
    class Meta:
        model = SalaryScenario
        fields = [
            'id', 'name', 'description', 'status', 'grading_system_name',
            'base_value', 'grade_order', 'input_rates', 'calculated_grades', 
            'vertical_avg', 'horizontal_avg', 'metrics', 'data',
            'is_calculated', 'created_by_name', 'applied_by_name',
            'created_at', 'calculation_timestamp', 'applied_at'
        ]
    
    def get_is_calculated(self, obj):
        return bool(obj.calculated_grades and obj.calculation_timestamp)
    
    def get_data(self, obj):
        """Enhanced data with proper input preservation for detail view"""
    
        
        # Validate calculated_grades
        calculated_grades = {}
        if obj.calculated_grades and isinstance(obj.calculated_grades, dict):
            calculated_grades = obj.calculated_grades.copy()
        
        # Validate grade_order
        grade_order = []
        if obj.grade_order and isinstance(obj.grade_order, list):
            grade_order = obj.grade_order.copy()
        
        # Extract global horizontal intervals from input_rates
        global_horizontal_intervals = {
            'LD_to_LQ': 0,
            'LQ_to_M': 0,
            'M_to_UQ': 0,
            'UQ_to_UD': 0
        }
        
        # Extract vertical inputs and global intervals
        position_vertical_inputs = {}
        
        if obj.input_rates and isinstance(obj.input_rates, dict):
            # Get vertical inputs for each position
            for grade_name in grade_order:
                grade_input_data = obj.input_rates.get(grade_name, {})
                if isinstance(grade_input_data, dict):
                    vertical_value = grade_input_data.get('vertical')
                    position_vertical_inputs[grade_name] = vertical_value
                    
                    # Get global intervals from first position with intervals
                    intervals = grade_input_data.get('horizontal_intervals', {})
                    if intervals and isinstance(intervals, dict) and not any(global_horizontal_intervals.values()):
                        for key in global_horizontal_intervals.keys():
                            if key in intervals and intervals[key] is not None:
                                try:
                                    global_horizontal_intervals[key] = float(intervals[key])
                                except (ValueError, TypeError):
                                    pass
        
      
        
        # Enhanced grades with proper input data preservation
        enhanced_grades = {}
        for grade_name in grade_order:
            if grade_name not in calculated_grades:
                calculated_grades[grade_name] = {
                    'LD': 0, 'LQ': 0, 'M': 0, 'UQ': 0, 'UD': 0
                }
            else:
                grade_data = calculated_grades[grade_name]
                if isinstance(grade_data, dict):
                    for field in ['LD', 'LQ', 'M', 'UQ', 'UD']:
                        if field not in grade_data or grade_data[field] is None:
                            grade_data[field] = 0
                        else:
                            try:
                                grade_data[field] = float(grade_data[field])
                            except (ValueError, TypeError):
                                grade_data[field] = 0
                else:
                    calculated_grades[grade_name] = {
                        'LD': 0, 'LQ': 0, 'M': 0, 'UQ': 0, 'UD': 0
                    }
            
            # Add input data to each grade for comparison
            enhanced_grades[grade_name] = {
                **calculated_grades[grade_name],
                'verticalInput': position_vertical_inputs.get(grade_name),
                'vertical': position_vertical_inputs.get(grade_name),
                'horizontal_intervals': global_horizontal_intervals
            }
        
        # Validate averages
        vertical_avg = 0
        horizontal_avg = 0
        
        try:
            if obj.vertical_avg is not None:
                vertical_avg = float(obj.vertical_avg)
        except (ValueError, TypeError):
            vertical_avg = 0
        
        try:
            if obj.horizontal_avg is not None:
                horizontal_avg = float(obj.horizontal_avg)
        except (ValueError, TypeError):
            horizontal_avg = 0
        
        # Validate base_value
        base_value = 0
        try:
            if obj.base_value is not None:
                base_value = float(obj.base_value)
        except (ValueError, TypeError):
            base_value = 0
        
        result = {
            'baseValue1': base_value,
            'gradeOrder': grade_order,
            'grades': enhanced_grades,
            'globalHorizontalIntervals': global_horizontal_intervals,
            'verticalAvg': vertical_avg,
            'horizontalAvg': horizontal_avg,
            'hasCalculation': bool(obj.calculated_grades and obj.calculation_timestamp),
            
            # Enhanced input data preservation for comparison
            'positionVerticalInputs': position_vertical_inputs,
            'inputRates': obj.input_rates or {},
            
            'isComplete': bool(calculated_grades and all(
                isinstance(grade, dict) and sum(float(v) for v in [grade.get('LD', 0), grade.get('LQ', 0), grade.get('M', 0), grade.get('UQ', 0), grade.get('UD', 0)] if v is not None) > 0 
                for grade in calculated_grades.values()
            ))
        }
        
        
        
        return result

class SalaryScenarioCreateSerializer(serializers.ModelSerializer):
    """Create/Update serializer for scenarios"""
    
    class Meta:
        model = SalaryScenario
        fields = [
            'name', 'description', 'grading_system', 'base_value', 
            'grade_order', 'input_rates'
        ]
    
    def validate_base_value(self, value):
        if value <= 0:
            raise serializers.ValidationError("Base value must be greater than 0")
        return value
    
    def validate_input_rates(self, value):
        """Validate input rates format"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Input rates must be a dictionary")
        
        for grade_name, rates in value.items():
            if not isinstance(rates, dict):
                raise serializers.ValidationError(f"Rates for {grade_name} must be a dictionary")
            
            # Validate vertical rate
            if 'vertical' in rates and rates['vertical'] is not None:
                try:
                    vertical_value = float(rates['vertical'])
                    if vertical_value < 0 or vertical_value > 100:
                        raise serializers.ValidationError(
                            f"Vertical rate for {grade_name} must be between 0-100"
                        )
                except (ValueError, TypeError):
                    raise serializers.ValidationError(
                        f"Invalid vertical rate for {grade_name}"
                    )
            
            # Validate horizontal intervals
            if 'horizontal_intervals' in rates and rates['horizontal_intervals']:
                intervals = rates['horizontal_intervals']
                if not isinstance(intervals, dict):
                    raise serializers.ValidationError(
                        f"Horizontal intervals for {grade_name} must be a dictionary"
                    )
                
                interval_names = ['LD_to_LQ', 'LQ_to_M', 'M_to_UQ', 'UQ_to_UD']
                for interval_name in interval_names:
                    if interval_name in intervals and intervals[interval_name] is not None:
                        try:
                            interval_value = float(intervals[interval_name])
                            if interval_value < 0 or interval_value > 100:
                                raise serializers.ValidationError(
                                    f"Horizontal interval {interval_name} for {grade_name} must be between 0-100"
                                )
                        except (ValueError, TypeError):
                            raise serializers.ValidationError(
                                f"Invalid horizontal interval {interval_name} for {grade_name}"
                            )
        
        return value
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        
        # Create scenario
        scenario = SalaryScenario.objects.create(**validated_data)
        
        # Calculate averages
        scenario.calculate_averages()
        scenario.save()
        
        return scenario


