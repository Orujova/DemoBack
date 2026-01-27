# grading/models.py - FIXED: Removed competitiveness/riskLevel, Fixed calculate_averages

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.postgres.fields import JSONField
from django.contrib.postgres.indexes import GinIndex
from api.models import PositionGroup
import uuid
import logging

logger = logging.getLogger(__name__)

class GradingSystem(models.Model):
    """Main grading system configuration"""
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    base_currency = models.CharField(max_length=3, default='AZN')
    
    # Default initial data from Excel (matches frontend initialExcelData)
    initial_data = models.JSONField(default=dict, help_text="Initial salary data from Excel")
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Grading System"
        verbose_name_plural = "Grading Systems"
        ordering = ['name']

class SalaryGrade(models.Model):
    """Current salary grade structure (matches current situation in frontend)"""
    grading_system = models.ForeignKey(GradingSystem, on_delete=models.CASCADE, related_name='salary_grades')
    position_group = models.ForeignKey(PositionGroup, on_delete=models.CASCADE, related_name='salary_grades')
    
    # Grade range values (matches frontend: LD, LQ, M, UQ, UD)
    lower_decile = models.DecimalField(max_digits=15, decimal_places=2, help_text="LD - Lower Decile")
    lower_quartile = models.DecimalField(max_digits=15, decimal_places=2, help_text="LQ - Lower Quartile") 
    median = models.DecimalField(max_digits=15, decimal_places=2, help_text="M - Median")
    upper_quartile = models.DecimalField(max_digits=15, decimal_places=2, help_text="UQ - Upper Quartile")
    upper_decile = models.DecimalField(max_digits=15, decimal_places=2, help_text="UD - Upper Decile")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.grading_system.name} - {self.position_group.get_name_display()}"

    class Meta:
        unique_together = ['grading_system', 'position_group']
        ordering = ['position_group__hierarchy_level']

class SalaryScenario(models.Model):
    """Salary scenarios for testing different configurations (matches frontend draft scenarios)"""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('CURRENT', 'Current'),
        ('ARCHIVED', 'Archived'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grading_system = models.ForeignKey(GradingSystem, on_delete=models.CASCADE, related_name='scenarios')
    name = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT', db_index=True)
    
    # Base configuration (matches frontend scenarioInputs)
    base_value = models.DecimalField(max_digits=15, decimal_places=2, help_text="Base minimum value (Blue Collar LD)")
    
    # Grade order (to match frontend gradeOrder)
    grade_order = models.JSONField(default=list, help_text="Order of position groups")
    
    # Input rates from user (matches frontend scenarioInputs.grades)
    input_rates = models.JSONField(default=dict, help_text="User input vertical and horizontal rates")
    
    # Calculated results (matches frontend calculatedOutputs)
    calculated_grades = models.JSONField(default=dict, help_text="Calculated salary grades")
    calculation_timestamp = models.DateTimeField(null=True, blank=True)
    
    # Averages for display (matches frontend calculations)
    vertical_avg = models.DecimalField(max_digits=5, decimal_places=4, default=0, help_text="Average vertical percentage as decimal")
    horizontal_avg = models.DecimalField(max_digits=5, decimal_places=4, default=0, help_text="Average horizontal percentage as decimal")
    
    # Basic metrics for comparison (REMOVED competitiveness/riskLevel)
    metrics = models.JSONField(default=dict, help_text="Basic calculated metrics")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    applied_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='applied_scenarios')

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    def calculate_averages(self):
        """COMPLETELY FIXED: Calculate vertical and horizontal averages properly"""
      
        
        if not self.input_rates or not self.grade_order:
            logger.info("No input_rates or grade_order, setting averages to 0")
            self.vertical_avg = 0
            self.horizontal_avg = 0
            return
        
       
        
        vertical_sum = 0
        vertical_count = 0
        horizontal_values = []
        
        # FIXED: Collect vertical rates (skip base position)
        for i, grade_name in enumerate(self.grade_order):
            # Base position is the LAST in the order - skip it for vertical
            is_base_position = (i == len(self.grade_order) - 1)
            if is_base_position:
                logger.info(f"Skipping {grade_name} - base position (no vertical needed)")
                continue
                
            grade_data = self.input_rates.get(grade_name, {})
            vertical_value = grade_data.get('vertical')
            
            
            
            if vertical_value is not None and vertical_value != '' and vertical_value != 0:
                try:
                    vertical_float = float(vertical_value)
                    vertical_sum += vertical_float
                    vertical_count += 1
                    
                except (ValueError, TypeError):
                    logger.warning(f"  ❌ Could not convert vertical value: {vertical_value}")
        
        # COMPLETELY FIXED: Global horizontal intervals collection
        # Look for horizontal_intervals in ANY position (they should be the same for all)
        global_intervals = None
        for grade_name in self.grade_order:
            grade_data = self.input_rates.get(grade_name, {})
            intervals = grade_data.get('horizontal_intervals', {})
            
            # Check if this position has meaningful horizontal intervals
            if intervals and isinstance(intervals, dict):
                has_values = any(
                    v is not None and v != '' and v != 0 
                    for v in intervals.values()
                )
                if has_values:
                    global_intervals = intervals
                   
                    break
        
        # Collect horizontal values from global intervals
        if global_intervals:
            interval_names = ['LD_to_LQ', 'LQ_to_M', 'M_to_UQ', 'UQ_to_UD']
            for interval_name in interval_names:
                interval_value = global_intervals.get(interval_name)
                
                
                if interval_value is not None and interval_value != '' and interval_value != 0:
                    try:
                        interval_float = float(interval_value)
                        horizontal_values.append(interval_float)
                       
                    except (ValueError, TypeError):
                        logger.warning(f"    ❌ Could not convert horizontal value: {interval_value}")
        else:
            logger.info("❌ No global horizontal intervals found in any position")
        
        # Calculate final averages
        self.vertical_avg = (vertical_sum / vertical_count / 100) if vertical_count > 0 else 0
        self.horizontal_avg = (sum(horizontal_values) / len(horizontal_values) / 100) if horizontal_values else 0
        
      
    def calculate_metrics(self, current_data=None):
        """SIMPLIFIED: Calculate basic metrics (removed competitiveness/riskLevel)"""
        if not self.calculated_grades:
            return
        
        total_budget_impact = 0
        avg_salary_increase = 0
        
        if current_data and current_data.get('grades'):
            # Calculate budget impact and salary increases
            increase_sum = 0
            grade_count = 0
            
            for grade_name in self.grade_order:
                if grade_name in self.calculated_grades and grade_name in current_data['grades']:
                    scenario_median = self.calculated_grades[grade_name].get('M', 0)
                    current_median = current_data['grades'][grade_name].get('M', 0)
                    
                    total_budget_impact += scenario_median
                    
                    if current_median > 0:
                        increase = ((scenario_median - current_median) / current_median) * 100
                        increase_sum += increase
                        grade_count += 1
            
            avg_salary_increase = increase_sum / grade_count if grade_count > 0 else 0
        
        # SIMPLIFIED metrics (removed competitiveness/riskLevel)
        self.metrics = {
            'totalBudgetImpact': total_budget_impact,
            'avgSalaryIncrease': avg_salary_increase,
            'positionsAffected': len(self.grade_order)
        }

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['grading_system', 'status']),
            models.Index(fields=['status', 'created_at']),
            GinIndex(fields=['calculated_grades']),
            GinIndex(fields=['input_rates']),
        ]

class ScenarioHistory(models.Model):
    """History of scenario applications"""
    scenario = models.ForeignKey(SalaryScenario, on_delete=models.CASCADE, related_name='history')
    action = models.CharField(max_length=30, db_index=True)
    previous_current_scenario = models.ForeignKey(SalaryScenario, on_delete=models.SET_NULL, null=True, blank=True)
    changes_made = models.JSONField(default=dict)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"{self.scenario.name} - {self.action}"

    class Meta:
        ordering = ['-timestamp']