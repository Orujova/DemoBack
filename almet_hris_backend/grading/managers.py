# grading/managers.py - FIXED: Enhanced current structure with proper input data
from django.db import models
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class SalaryCalculationManager:
    """Manager for salary calculations with FIXED current structure data"""
    
    @staticmethod
    def get_position_groups_from_db():
        """Get position groups from database in hierarchy order"""
        from api.models import PositionGroup
        try:
            positions = PositionGroup.objects.filter(is_active=True).order_by('hierarchy_level')
            position_list = list(positions.values_list('name', 'hierarchy_level'))
           
            return positions
        except Exception as e:
            logger.error(f"Error getting position groups: {e}")
            return PositionGroup.objects.none()
    
    @staticmethod
    def create_current_structure_from_db():
        """FIXED: Create current structure data with proper input values for comparison"""
        from .models import SalaryGrade, SalaryScenario
        from api.models import PositionGroup
        
   
        
        # Get position groups from database
        position_groups = SalaryCalculationManager.get_position_groups_from_db()
        
        if not position_groups.exists():
            logger.error("No position groups found for current structure")
            return None
        
        # Try to get current scenario first for input data
        try:
            current_scenario = SalaryScenario.objects.get(status='CURRENT')
          
            
            # Build grade order from database position groups
            grade_order = []
            grades_data = {}
            
            for pos_group in position_groups:
                grade_name = pos_group.get_name_display()
                grade_order.append(grade_name)
                
                # FIXED: Extract both calculated and input data
                if (current_scenario.calculated_grades and 
                    grade_name in current_scenario.calculated_grades):
                    grade_data = current_scenario.calculated_grades[grade_name]
                    
                    # ENHANCED: Get input data from scenario for comparison
                    input_data = current_scenario.input_rates.get(grade_name, {}) if current_scenario.input_rates else {}
                    
                    if isinstance(grade_data, dict):
                        grades_data[grade_name] = {
                            # Calculated values
                            'LD': grade_data.get('LD', 0) or 0,
                            'LQ': grade_data.get('LQ', 0) or 0, 
                            'M': grade_data.get('M', 0) or 0,
                            'UQ': grade_data.get('UQ', 0) or 0,
                            'UD': grade_data.get('UD', 0) or 0,
                            
                            # FIXED: Add input data for comparison (if available)
                            'vertical': input_data.get('vertical') if input_data else None,
                            'verticalInput': input_data.get('vertical') if input_data else None,
                            'horizontal_intervals': input_data.get('horizontal_intervals', {
                                'LD_to_LQ': 0, 'LQ_to_M': 0, 'M_to_UQ': 0, 'UQ_to_UD': 0
                            }) if input_data else {
                                'LD_to_LQ': 0, 'LQ_to_M': 0, 'M_to_UQ': 0, 'UQ_to_UD': 0
                            }
                        }
                    else:
                        # Fallback for invalid grade data
                        grades_data[grade_name] = {
                            'LD': 0, 'LQ': 0, 'M': 0, 'UQ': 0, 'UD': 0,
                            'vertical': None, 'verticalInput': None,
                            'horizontal_intervals': {
                                'LD_to_LQ': 0, 'LQ_to_M': 0, 'M_to_UQ': 0, 'UQ_to_UD': 0
                            }
                        }
                else:
                    # No data for this position
                    grades_data[grade_name] = {
                        'LD': 0, 'LQ': 0, 'M': 0, 'UQ': 0, 'UD': 0,
                        'vertical': None, 'verticalInput': None,
                        'horizontal_intervals': {
                            'LD_to_LQ': 0, 'LQ_to_M': 0, 'M_to_UQ': 0, 'UQ_to_UD': 0
                        }
                    }
            
        
            
            # FIXED: Extract global horizontal intervals from scenario
            global_horizontal_intervals = {
                'LD_to_LQ': 0, 'LQ_to_M': 0, 'M_to_UQ': 0, 'UQ_to_UD': 0
            }
            
            if current_scenario.input_rates:
                # Get global intervals from first position with intervals
                for grade_name in grade_order:
                    grade_input_data = current_scenario.input_rates.get(grade_name, {})
                    if isinstance(grade_input_data, dict):
                        intervals = grade_input_data.get('horizontal_intervals', {})
                        if intervals and isinstance(intervals, dict) and any(intervals.values()):
                            global_horizontal_intervals = intervals
                            break
            
            # FIXED: Extract position vertical inputs for comparison
            position_vertical_inputs = {}
            if current_scenario.input_rates:
                for grade_name in grade_order:
                    grade_input_data = current_scenario.input_rates.get(grade_name, {})
                    if isinstance(grade_input_data, dict):
                        vertical_value = grade_input_data.get('vertical')
                        position_vertical_inputs[grade_name] = vertical_value
            
            # Validate averages
            vertical_avg = float(current_scenario.vertical_avg) if current_scenario.vertical_avg else 0
            horizontal_avg = float(current_scenario.horizontal_avg) if current_scenario.horizontal_avg else 0
            base_value = float(current_scenario.base_value) if current_scenario.base_value else 0
            
            # ENHANCED: Return current structure with input data for comparison
            return {
                'id': 'current',
                'name': 'Current Structure',
                'grades': grades_data,
                'gradeOrder': grade_order,
                'verticalAvg': vertical_avg,
                'horizontalAvg': horizontal_avg,
                'baseValue1': base_value,
                'status': 'current',
                
                # FIXED: Add input data for comparison
                'data': {
                    'baseValue1': base_value,
                    'gradeOrder': grade_order,
                    'grades': grades_data,
                    'globalHorizontalIntervals': global_horizontal_intervals,
                    'verticalAvg': vertical_avg,
                    'horizontalAvg': horizontal_avg,
                    'positionVerticalInputs': position_vertical_inputs,
                    'inputRates': current_scenario.input_rates or {},
                    'hasCalculation': True,
                    'isComplete': True
                },
                
                # FIXED: Preserve original input data for comparison
                'input_rates': current_scenario.input_rates or {},
                'vertical_avg': vertical_avg,
                'horizontal_avg': horizontal_avg
            }
            
        except SalaryScenario.DoesNotExist:
            logger.info("No current scenario, creating empty structure")
            # No current scenario, return empty structure with position groups
            grade_order = []
            grades_data = {}
            
            for pos_group in position_groups:
                grade_name = pos_group.get_name_display()
                grade_order.append(grade_name)
                grades_data[grade_name] = {
                    'LD': 0, 'LQ': 0, 'M': 0, 'UQ': 0, 'UD': 0,
                    'vertical': None, 'verticalInput': None,
                    'horizontal_intervals': {
                        'LD_to_LQ': 0, 'LQ_to_M': 0, 'M_to_UQ': 0, 'UQ_to_UD': 0
                    }
                }
            
            return {
                'id': 'current',
                'name': 'Current Structure',
                'grades': grades_data,
                'gradeOrder': grade_order,
                'verticalAvg': 0.0,
                'horizontalAvg': 0.0,
                'baseValue1': 0,
                'status': 'current',
                'data': {
                    'baseValue1': 0,
                    'gradeOrder': grade_order,
                    'grades': grades_data,
                    'globalHorizontalIntervals': {'LD_to_LQ': 0, 'LQ_to_M': 0, 'M_to_UQ': 0, 'UQ_to_UD': 0},
                    'verticalAvg': 0.0,
                    'horizontalAvg': 0.0,
                    'positionVerticalInputs': {},
                    'inputRates': {},
                    'hasCalculation': False,
                    'isComplete': False
                },
                'input_rates': {},
                'vertical_avg': 0.0,
                'horizontal_avg': 0.0
            }
    
    @staticmethod
    def calculate_scenario_grades(base_value, input_rates, position_groups=None):
        """Calculate scenario grades with enhanced validation"""
   
        
        if position_groups is None:
            position_groups = SalaryCalculationManager.get_position_groups_from_db()
        
        calculated_grades = {}
        
        # Convert queryset to list
        positions_list = list(position_groups)
        logger.info(f"Positions order: {[(p.get_name_display(), p.hierarchy_level) for p in positions_list]}")
        
        if not positions_list:
            logger.error("No positions to calculate")
            return calculated_grades
        
        # Process all positions from bottom (highest index) to top (index 0)
        for i in range(len(positions_list) - 1, -1, -1):
            position = positions_list[i]
            position_name = position.get_name_display()
            position_inputs = input_rates.get(position_name, {})
            
            
            
            # Determine this position's LD
            if i == len(positions_list) - 1:
                # This is the base position - use base_value directly
                position_ld = Decimal(str(base_value))
                
            else:
                # This is NOT the base position - calculate based on vertical rate
                vertical_input = position_inputs.get('vertical', 0)
                
                # Get the LD of the position below (higher index)
                lower_position = positions_list[i + 1]
                lower_position_name = lower_position.get_name_display()
                lower_position_ld = calculated_grades[lower_position_name]['LD']
                
                # Safe vertical conversion
                if vertical_input == '' or vertical_input is None:
                    vertical_rate = Decimal('0')
                    logger.info(f"No vertical input for {position_name}, using 0%")
                else:
                    try:
                        vertical_rate = Decimal(str(vertical_input))
                        logger.info(f"Vertical rate for {position_name}: {vertical_rate}%")
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid vertical input for {position_name}: {vertical_input}, using 0")
                        vertical_rate = Decimal('0')
                
                # Calculate this position's LD based on the position below + vertical rate
                position_ld = Decimal(str(lower_position_ld)) * (Decimal('1') + vertical_rate / Decimal('100'))
                
              
            
            # Get horizontal intervals for this position
            horizontal_intervals = position_inputs.get('horizontal_intervals', {})
            
            # Calculate horizontal grades for this position
            grades = SalaryCalculationManager._calculate_horizontal_grades_with_intervals(
                position_ld, horizontal_intervals
            )
            calculated_grades[position_name] = grades
            
            
        return calculated_grades
    
    @staticmethod
    def _calculate_horizontal_grades_with_intervals(lower_decile, horizontal_intervals):
        """Calculate horizontal grades with 4 separate interval inputs"""
        ld = float(lower_decile)
        
        # Safe conversion function
        def safe_float_conversion(value, default=0.0):
            if value is None or value == '' or value == 'None':
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                logger.warning(f"Could not convert '{value}' to float, using default {default}")
                return default
        
        # Get interval percentages with safe conversion and validation
        intervals = horizontal_intervals if isinstance(horizontal_intervals, dict) else {}
        
        ld_to_lq = safe_float_conversion(intervals.get('LD_to_LQ', 0)) / 100
        lq_to_m = safe_float_conversion(intervals.get('LQ_to_M', 0)) / 100
        m_to_uq = safe_float_conversion(intervals.get('M_to_UQ', 0)) / 100
        uq_to_ud = safe_float_conversion(intervals.get('UQ_to_UD', 0)) / 100
        
        # Calculate step by step
        lq = ld * (1 + ld_to_lq)
        m = lq * (1 + lq_to_m)
        uq = m * (1 + m_to_uq)
        ud = uq * (1 + uq_to_ud)
        
        grades = {
            'LD': round(ld),
            'LQ': round(lq),
            'M': round(m),
            'UQ': round(uq),
            'UD': round(ud)
        }
        
        logger.debug(f"Horizontal calculation:")
        logger.debug(f"  LD→LQ: {ld_to_lq*100:.1f}% → {ld:.0f} → {lq:.0f}")
        logger.debug(f"  LQ→M: {lq_to_m*100:.1f}% → {lq:.0f} → {m:.0f}")
        logger.debug(f"  M→UQ: {m_to_uq*100:.1f}% → {m:.0f} → {uq:.0f}")
        logger.debug(f"  UQ→UD: {uq_to_ud*100:.1f}% → {uq:.0f} → {ud:.0f}")
        
        return grades
    
    @staticmethod
    def calculate_scenario_metrics(scenario_data, current_data):
        """Basic metrics calculation"""
        if not scenario_data.get('grades') or not current_data.get('grades'):
            return {
                'totalBudgetImpact': 0,
                'avgSalaryIncrease': 0,
                'maxSalaryIncrease': 0,
                'positionsAffected': 0
            }
        
        total_budget_impact = 0
        salary_increases = []
        
        for grade_name in scenario_data.get('gradeOrder', []):
            scenario_grade = scenario_data['grades'].get(grade_name, {})
            current_grade = current_data['grades'].get(grade_name, {})
            
            scenario_median = 0
            current_median = 0
            
            if isinstance(scenario_grade, dict):
                scenario_median = float(scenario_grade.get('M', 0) or 0)
            
            if isinstance(current_grade, dict):
                current_median = float(current_grade.get('M', 0) or 0)
            
            total_budget_impact += scenario_median
            
            # Only calculate increase if both values are meaningful
            if current_median > 0 and scenario_median > 0:
                increase = ((scenario_median - current_median) / current_median) * 100
                salary_increases.append(increase)
        
        avg_salary_increase = sum(salary_increases) / len(salary_increases) if salary_increases else 0
        max_salary_increase = max(salary_increases) if salary_increases else 0
        
        return {
            'totalBudgetImpact': total_budget_impact,
            'avgSalaryIncrease': avg_salary_increase,
            'maxSalaryIncrease': max_salary_increase,
            'positionsAffected': len(salary_increases)
        }
    
    @staticmethod
    def apply_scenario(scenario_id, user=None):
        """Apply a scenario to current grading system"""
        from .models import SalaryScenario, SalaryGrade, ScenarioHistory
        
        scenario = SalaryScenario.objects.get(id=scenario_id)
        
        if scenario.status != 'DRAFT':
            raise ValueError("Only draft scenarios can be applied")
        
        if not scenario.calculated_grades:
            raise ValueError("Scenario must be calculated before applying")
        
        # Archive current scenario if exists
        try:
            current_scenario = SalaryScenario.objects.get(
                grading_system=scenario.grading_system,
                status='CURRENT'
            )
            current_scenario.status = 'ARCHIVED'
            current_scenario.save()
            
            ScenarioHistory.objects.create(
                scenario=scenario,
                action='APPLIED',
                previous_current_scenario=current_scenario,
                performed_by=user,
                changes_made={
                    'replaced_scenario': current_scenario.name,
                    'archived_previous': True
                }
            )
            
        except SalaryScenario.DoesNotExist:
            ScenarioHistory.objects.create(
                scenario=scenario,
                action='APPLIED',
                performed_by=user,
                changes_made={'first_application': True}
            )
        
        # Apply new scenario
        scenario.status = 'CURRENT'
        scenario.applied_at = timezone.now()
        scenario.applied_by = user
        scenario.save()
        
        # Update actual salary grades
        SalaryGrade.objects.filter(grading_system=scenario.grading_system).delete()
        
        position_groups = SalaryCalculationManager.get_position_groups_from_db()
        position_map = {pos.get_name_display(): pos for pos in position_groups}
        
        salary_grades_created = 0
        for position_name, grades in scenario.calculated_grades.items():
            if position_name in position_map and isinstance(grades, dict):
                SalaryGrade.objects.create(
                    grading_system=scenario.grading_system,
                    position_group=position_map[position_name],
                    lower_decile=Decimal(str(grades.get('LD', 0) or 0)),
                    lower_quartile=Decimal(str(grades.get('LQ', 0) or 0)),
                    median=Decimal(str(grades.get('M', 0) or 0)),
                    upper_quartile=Decimal(str(grades.get('UQ', 0) or 0)),
                    upper_decile=Decimal(str(grades.get('UD', 0) or 0))
                )
                salary_grades_created += 1
        
       
        return scenario
    
    @staticmethod
    def get_balance_score(scenario_data):
        """Calculate balance score for scenario comparison"""
        vertical_avg = scenario_data.get('verticalAvg', 0)
        horizontal_avg = scenario_data.get('horizontalAvg', 0)
        deviation = abs(vertical_avg - horizontal_avg)
        return (vertical_avg + horizontal_avg) / (1 + deviation) if (vertical_avg + horizontal_avg) > 0 else 0
    
    @staticmethod
    def validate_scenario_inputs(base_value, input_rates):
        """Validate scenario inputs with proper type checking"""
        errors = []
        
        
        
        if not base_value or base_value <= 0:
            errors.append("Base value must be greater than 0")
        
        if not input_rates or not isinstance(input_rates, dict):
            errors.append("Input rates are required and must be valid")
            return errors
        
        for grade_name, rates in input_rates.items():
          
            if isinstance(rates, dict):
                # Validate vertical rate
                if rates.get('vertical') is not None:
                    vertical = rates['vertical']
        
                    
                    if vertical == '' or vertical is None:
                        continue
                    
                    try:
                        vertical_float = float(vertical)
                        if vertical_float < 0 or vertical_float > 100:
                            errors.append(f"Vertical rate for {grade_name} must be between 0-100")
                    except (ValueError, TypeError):
                        errors.append(f"Vertical rate for {grade_name} must be a valid number")
                
                # Validate horizontal intervals
                horizontal_intervals = rates.get('horizontal_intervals', {})
                if horizontal_intervals and isinstance(horizontal_intervals, dict):
                    interval_names = ['LD_to_LQ', 'LQ_to_M', 'M_to_UQ', 'UQ_to_UD']
                    for interval_name in interval_names:
                        interval_value = horizontal_intervals.get(interval_name)
                        if interval_value is not None and interval_value != '':
                            try:
                                interval_float = float(interval_value)
                                if interval_float < 0 or interval_float > 100:
                                    errors.append(f"Horizontal interval {interval_name} for {grade_name} must be between 0-100")
                            except (ValueError, TypeError):
                                errors.append(f"Horizontal interval {interval_name} for {grade_name} must be a valid number")
        
       
        return errors