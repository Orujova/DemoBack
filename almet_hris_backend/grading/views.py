# grading/views.py - SIMPLIFIED: Removed unnecessary complexity, fixed API issues

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
import logging


from .models import GradingSystem, SalaryGrade, SalaryScenario, ScenarioHistory
from .serializers import (
    GradingSystemSerializer, SalaryGradeSerializer, CurrentStructureSerializer,
    SalaryScenarioListSerializer, SalaryScenarioDetailSerializer,
    SalaryScenarioCreateSerializer,
 
)
from .managers import SalaryCalculationManager
from api.views import ModernPagination
from api.models import PositionGroup

logger = logging.getLogger(__name__)

class GradingSystemViewSet(viewsets.ModelViewSet):
    queryset = GradingSystem.objects.all()
    serializer_class = GradingSystemSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ModernPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['is_active']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    @action(detail=False, methods=['get'])
    def current_structure(self, request):
        """Get current grade structure from database - SIMPLIFIED"""
        try:
            # Create current structure from database
            current_data = SalaryCalculationManager.create_current_structure_from_db()
            
            if current_data is None:
                return Response({
                    'error': 'No position groups found in database',
                    'message': 'Please configure position groups in the admin panel first'
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = CurrentStructureSerializer(current_data)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error getting current structure: {str(e)}")
            return Response({
                'error': 'Failed to get current structure',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def position_groups(self, request):
        """Get position groups from database for frontend"""
        try:
            position_groups = SalaryCalculationManager.get_position_groups_from_db()
            
            if not position_groups.exists():
                return Response({
                    'error': 'No position groups found in database',
                    'position_groups': []
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Format for frontend
            formatted_positions = []
            for pos in position_groups:
                formatted_positions.append({
                    'id': pos.id,
                    'name': pos.name,
                    'display_name': pos.get_name_display(),
                    'hierarchy_level': pos.hierarchy_level,
                    'is_active': pos.is_active
                })
            
            return Response({
                'position_groups': formatted_positions,
                'count': len(formatted_positions)
            })
            
        except Exception as e:
            logger.error(f"Error getting position groups: {str(e)}")
            return Response({
                'error': 'Failed to get position groups',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SalaryGradeViewSet(viewsets.ModelViewSet):
    serializer_class = SalaryGradeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['grading_system']
    ordering = ['position_group__hierarchy_level']
    
    def get_queryset(self):
        return SalaryGrade.objects.select_related('grading_system', 'position_group')

class SalaryScenarioViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = ModernPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['status']  # FIXED: Removed grading_system filter that was causing 400 errors
    ordering_fields = ['name', 'created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return SalaryScenario.objects.select_related(
            'grading_system', 'created_by', 'applied_by'
        )
    
    def get_serializer_class(self):
        if self.action == 'list':
            return SalaryScenarioListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return SalaryScenarioCreateSerializer
        else:
            return SalaryScenarioDetailSerializer

    @action(detail=False, methods=['post'], url_path='calculate_dynamic')
    def calculate_dynamic(self, request):
        """SIMPLIFIED: Calculate scenario dynamically"""
        try:
           
            
            # Extract and validate request data
            base_value = request.data.get('baseValue1')
            input_rates = request.data.get('grades', {})
            
            # Enhanced validation
            if not base_value or float(base_value) <= 0:
                return Response({
                    'errors': ['Base value must be greater than 0'],
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not input_rates:
                return Response({
                    'errors': ['Grade input rates are required'],
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get position groups from database
            position_groups = SalaryCalculationManager.get_position_groups_from_db()
            
            if not position_groups.exists():
                return Response({
                    'errors': ['No position groups found in database'],
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate inputs
            validation_errors = SalaryCalculationManager.validate_scenario_inputs(float(base_value), input_rates)
            if validation_errors:
                return Response({
                    'errors': validation_errors,
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Calculate grades
            calculated_grades = SalaryCalculationManager.calculate_scenario_grades(
                float(base_value), input_rates, position_groups
            )
            
            # Format output for frontend
            calculated_outputs = {}
            for position_name, grades in calculated_grades.items():
                if isinstance(grades, dict):
                    calculated_outputs[position_name] = {
                        'LD': grades.get('LD', 0) if grades.get('LD', 0) > 0 else "",
                        'LQ': grades.get('LQ', 0) if grades.get('LQ', 0) > 0 else "",
                        'M': grades.get('M', 0) if grades.get('M', 0) > 0 else "",
                        'UQ': grades.get('UQ', 0) if grades.get('UQ', 0) > 0 else "",
                        'UD': grades.get('UD', 0) if grades.get('UD', 0) > 0 else ""
                    }
            
            return Response({
                'calculatedOutputs': calculated_outputs,
                'success': True
            })
            
        except Exception as e:
            logger.error(f"Calculate dynamic error: {str(e)}")
            return Response({
                'errors': [f'Calculation error: {str(e)}'],
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='save_draft')
    def save_draft(self, request):
        """SIMPLIFIED: Save scenario with clean data handling"""
        try:
      
            
            # Extract data
            name = request.data.get('name')
            description = request.data.get('description', '')
            base_value = request.data.get('baseValue1')
            grade_order = request.data.get('gradeOrder', [])
            input_rates = request.data.get('grades', {})
            global_horizontal_intervals = request.data.get('globalHorizontalIntervals', {})
            calculated_outputs = request.data.get('calculatedOutputs', {})
            
            # Simple validation
            if not name or not base_value or float(base_value) <= 0:
                return Response({
                    'success': False,
                    'error': 'Name and valid base value are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get or create grading system
            grading_system, created = GradingSystem.objects.get_or_create(
                name="Default Grading System",
                defaults={
                    'description': "Default grading system",
                    'is_active': True,
                    'created_by': request.user
                }
            )
            
            # Format input rates with global intervals
            formatted_input_rates = {}
            for position_name in grade_order:
                position_input = input_rates.get(position_name, {})
                
                # Handle vertical
                vertical_value = position_input.get('vertical')
                if vertical_value in ['', None]:
                    vertical_value = None
                else:
                    try:
                        vertical_value = float(vertical_value)
                    except (ValueError, TypeError):
                        vertical_value = None
                
                # Apply global intervals
                clean_intervals = {}
                if global_horizontal_intervals:
                    for interval_key, interval_value in global_horizontal_intervals.items():
                        try:
                            clean_value = float(interval_value) if interval_value not in ['', None] else 0
                            clean_intervals[interval_key] = clean_value
                        except (ValueError, TypeError):
                            clean_intervals[interval_key] = 0
                
                formatted_input_rates[position_name] = {
                    'vertical': vertical_value,
                    'horizontal_intervals': clean_intervals
                }
            
            # Calculate averages
            vertical_sum = 0
            vertical_count = 0
            horizontal_sum = 0
            horizontal_count = 0
            
            # Vertical averages (exclude base position)
            for i, position_name in enumerate(grade_order):
                is_base_position = (i == len(grade_order) - 1)
                if is_base_position:
                    continue
                    
                position_data = formatted_input_rates.get(position_name, {})
                vertical_value = position_data.get('vertical')
                if vertical_value is not None and vertical_value != 0:
                    vertical_sum += vertical_value
                    vertical_count += 1
            
            # Horizontal averages from global intervals
            if global_horizontal_intervals:
                for interval_value in global_horizontal_intervals.values():
                    if interval_value not in ['', None, 0]:
                        try:
                            horizontal_sum += float(interval_value)
                            horizontal_count += 1
                        except (ValueError, TypeError):
                            pass
            
            vertical_avg = (vertical_sum / vertical_count / 100) if vertical_count > 0 else 0
            horizontal_avg = (horizontal_sum / horizontal_count / 100) if horizontal_count > 0 else 0
            
            # Create scenario
            with transaction.atomic():
                scenario = SalaryScenario.objects.create(
                    grading_system=grading_system,
                    name=name.strip(),
                    description=description,
                    base_value=Decimal(str(float(base_value))),
                    grade_order=grade_order,
                    input_rates=formatted_input_rates,
                    calculated_grades=calculated_outputs,
                    calculation_timestamp=timezone.now(),
                    vertical_avg=Decimal(str(vertical_avg)),
                    horizontal_avg=Decimal(str(horizontal_avg)),
                    created_by=request.user
                )
            
            # Format response
            scenario_serializer = SalaryScenarioDetailSerializer(scenario)
            
            return Response({
                'success': True,
                'message': 'Scenario saved successfully!',
                'scenario_id': str(scenario.id),
                'scenario': scenario_serializer.data
            })
            
        except Exception as e:
            logger.error(f"Save draft error: {str(e)}")
            return Response({
                'success': False,
                'error': f'Failed to save scenario: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def apply_as_current(self, request, pk=None):
        """Apply scenario as current"""
        try:
            scenario = self.get_object()
            
            if scenario.status != 'DRAFT':
                return Response({
                    'success': False,
                    'error': 'Only draft scenarios can be applied'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Apply scenario using manager
            with transaction.atomic():
                applied_scenario = SalaryCalculationManager.apply_scenario(scenario.id, request.user)
            
            return Response({
                'success': True,
                'message': 'Scenario applied successfully!',
                'scenario': SalaryScenarioDetailSerializer(applied_scenario).data
            })
            
        except Exception as e:
            logger.error(f"Error applying scenario: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive scenario"""
        try:
            scenario = self.get_object()
            
            if scenario.status == 'CURRENT':
                return Response({
                    'success': False,
                    'error': 'Cannot archive current scenario'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Archive scenario
            with transaction.atomic():
                scenario.status = 'ARCHIVED'
                scenario.save()
                
                # Create history record
                ScenarioHistory.objects.create(
                    scenario=scenario,
                    action='ARCHIVED',
                    performed_by=request.user,
                    changes_made={'archived_by': request.user.get_full_name()}
                )
            
            return Response({
                'success': True,
                'message': 'Scenario archived successfully'
            })
            
        except Exception as e:
            logger.error(f"Error archiving scenario: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
    
    @action(detail=False, methods=['post'], url_path='compare_scenarios')
    def compare_scenarios(self, request):
        """
        Enhanced Scenario Comparison - Salary auto-calculated from grading
        """
        try:
            from api.models import Employee
            from collections import defaultdict
            
            scenario_ids = request.data.get('scenario_ids', [])
            
            if not scenario_ids or len(scenario_ids) < 2:
                return Response({
                    'success': False,
                    'error': 'At least 2 scenario IDs are required for comparison'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Separate 'current' from scenario IDs
            has_current = 'current' in scenario_ids
            scenario_uuids = [sid for sid in scenario_ids if sid != 'current']
            
            # Get scenarios
            scenarios = list(SalaryScenario.objects.filter(id__in=scenario_uuids))
            
            # Get CURRENT scenario
            try:
                current_scenario = SalaryScenario.objects.get(status='CURRENT')
            except SalaryScenario.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'No current scenario found. Please apply a scenario first.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get all active employees
            employees = list(Employee.objects.filter(
                is_deleted=False,
                status__affects_headcount=True
            ).select_related(
                'position_group', 'business_function', 'department'
            ).values(
                'id', 'employee_id', 'full_name', 
                'position_group__name', 'position_group__hierarchy_level',
                'grading_level', 'start_date',
                'business_function__name', 'department__name',
                'job_title'
            ))
            
         
            
            # Build comparison result
            comparison_result = {
                'total_cost_comparison': self._build_total_cost_comparison(
                    current_scenario, scenarios, employees
                ),
                'employee_analysis': self._build_employee_analysis(
                    current_scenario, scenarios, employees
                ),
                'underpaid_overpaid_lists': self._build_underpaid_overpaid_lists(
                    current_scenario, scenarios, employees
                ),
                'scenarios_comparison': self._build_scenarios_percentage_comparison(
                    current_scenario, scenarios
                )
            }
            
            # Prepare scenario list for response
            response_scenarios = []
            if has_current:
                response_scenarios.append({
                    'id': 'current',
                    'name': 'Current Structure',
                    'is_current': True
                })
            
            for s in scenarios:
                response_scenarios.append({
                    'id': str(s.id),
                    'name': s.name,
                    'is_current': False
                })
            
            return Response({
                'success': True,
                'comparison': comparison_result,
                'scenarios': response_scenarios
            })
            
        except Exception as e:
            logger.error(f"❌ Comparison error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _normalize_grade_level(self, grade_level):
        """
        Normalize grade level - convert all variations to standard format
        Examples: 
          - MGR_M, MGR_m, MGR_Median -> M
          - MGR_UQ, MGR_uq, MGR_UpperQuartile -> UQ
          - DIRECTOR_LD -> LD
        """
        if not grade_level:
            return None
        
        grade_upper = grade_level.upper()
        
        # Mapping for all possible variations
        level_mappings = {
            'LD': ['LD', 'LOWERDECILE', 'LOWER_DECILE', 'L_D', 'LOWER-DECILE'],
            'LQ': ['LQ', 'LOWERQUARTILE', 'LOWER_QUARTILE', 'L_Q', 'LOWER-QUARTILE'],
            'M': ['M', 'MEDIAN', 'MED'],
            'UQ': ['UQ', 'UPPERQUARTILE', 'UPPER_QUARTILE', 'U_Q', 'UPPER-QUARTILE'],
            'UD': ['UD', 'UPPERDECILE', 'UPPER_DECILE', 'U_D', 'UPPER-DECILE']
        }
        
        # Split by underscore to get level part
        parts = grade_upper.split('_')
        
        if len(parts) >= 2:
            level_part = parts[-1]  # Last part is the level
            
            # Find matching standard level
            for standard_level, variations in level_mappings.items():
                if level_part in variations or any(v in level_part for v in variations):
                    return standard_level
        
        # If no underscore, check if entire string matches
        for standard_level, variations in level_mappings.items():
            if grade_upper in variations:
                return standard_level
        
        logger.warning(f"⚠️ Could not normalize grade level: {grade_level}")
        return None
    
    def _get_employee_current_salary(self, employee, current_scenario):
        """
        Get employee's current salary from current scenario based on their grading level
        This is their ACTUAL current salary, not what it should be
        """
        grading_level = employee.get('grading_level')
        position_name = employee.get('position_group__name')
        
        if not grading_level or not current_scenario.calculated_grades:
            logger.warning(f"⚠️ No grading level or calculated grades for {employee.get('full_name')}")
            return 0
        
        # Normalize the grade level
        normalized_level = self._normalize_grade_level(grading_level)
        
        if not normalized_level:
            logger.warning(f"⚠️ Could not normalize grade level: {grading_level} for {employee.get('full_name')}")
            return 0
        
        # Find matching position in current scenario
        for pos_name, grades in current_scenario.calculated_grades.items():
            if self._positions_match(position_name, pos_name):
                if isinstance(grades, dict):
                    salary = grades.get(normalized_level, 0)
                    return float(salary) if salary else 0
        
        logger.warning(f"⚠️ No matching position {position_name} found in current scenario for {employee.get('full_name')}")
        return 0
    
    def _get_employee_scenario_salary(self, employee, scenario):
        """
        Get what employee's salary SHOULD BE according to a scenario
        """
        grading_level = employee.get('grading_level')
        position_name = employee.get('position_group__name')
        
        if not grading_level or not scenario.calculated_grades:
            return 0
        
        # Normalize the grade level
        normalized_level = self._normalize_grade_level(grading_level)
        
        if not normalized_level:
            return 0
        
        # Find matching position in scenario
        for pos_name, grades in scenario.calculated_grades.items():
            if self._positions_match(position_name, pos_name):
                if isinstance(grades, dict):
                    salary = grades.get(normalized_level, 0)
                    return float(salary) if salary else 0
        
        return 0
    
    def _positions_match(self, emp_position, scenario_position):
        """Check if employee position matches scenario position"""
        if not emp_position or not scenario_position:
            return False
        
        emp_pos_upper = emp_position.upper().replace(' ', '_').replace('-', '_')
        scen_pos_upper = scenario_position.upper().replace(' ', '_').replace('-', '_')
        
        # Direct match
        if emp_pos_upper == scen_pos_upper:
            return True
        
        # Partial match
        if emp_pos_upper in scen_pos_upper or scen_pos_upper in emp_pos_upper:
            return True
        
        return False
    
    def _build_total_cost_comparison(self, current_scenario, scenarios, employees):
        """
        Figure 1: Total Cost Comparison Table
        Total salary cost per position for current vs scenarios
        """
        from collections import defaultdict
        
        position_costs = defaultdict(lambda: {
            'current': 0,
            'scenarios': {}
        })
        
        for emp in employees:
            position = emp['position_group__name']
            
            # Current salary (from current scenario + employee grading)
            current_salary = self._get_employee_current_salary(emp, current_scenario)
            position_costs[position]['current'] += current_salary
            
            # Each scenario salary
            for scenario in scenarios:
                scenario_name = scenario.name
                if scenario_name not in position_costs[position]['scenarios']:
                    position_costs[position]['scenarios'][scenario_name] = 0
                
                scenario_salary = self._get_employee_scenario_salary(emp, scenario)
                position_costs[position]['scenarios'][scenario_name] += scenario_salary
        
        # Format output with totals
        result = {
            'positions': {},
            'totals': {
                'current': 0,
                'scenarios': {}
            }
        }
        
        for position, costs in position_costs.items():
            result['positions'][position] = {
                'current': round(costs['current']),
                'scenarios': {
                    name: round(value) 
                    for name, value in costs['scenarios'].items()
                }
            }
            
            result['totals']['current'] += costs['current']
            for scenario_name, value in costs['scenarios'].items():
                if scenario_name not in result['totals']['scenarios']:
                    result['totals']['scenarios'][scenario_name] = 0
                result['totals']['scenarios'][scenario_name] += value
        
        result['totals']['current'] = round(result['totals']['current'])
        result['totals']['scenarios'] = {
            name: round(value)
            for name, value in result['totals']['scenarios'].items()
        }
        
        for name, value in result['totals']['scenarios'].items():
            logger.info(f"💰 Total Cost - {name}: {value}")
        
        return result
    
    def _build_employee_analysis(self, current_scenario, scenarios, employees):
        """
        Figure 2: Employee Analysis - Headcount by Grade
        Shows distribution: how many employees are over/under/at their grade
        """
        from collections import defaultdict
        
        analysis = {}
        positions = set(emp['position_group__name'] for emp in employees)
        
        for position in positions:
            position_employees = [
                emp for emp in employees 
                if emp['position_group__name'] == position
            ]
            
            if not position_employees:
                continue
            
            analysis[position] = {
                'total_employees': len(position_employees),
                'current_grading': defaultdict(lambda: {
                    'count': 0,
                    'over': 0,
                    'at': 0,
                    'under': 0
                }),
                'scenarios': {}
            }
            
            # Current scenario analysis
            for emp in position_employees:
                grade = self._normalize_grade_level(emp['grading_level'])
                if not grade:
                    continue
                
                # Employee's current salary (from current scenario)
                current_salary = self._get_employee_current_salary(emp, current_scenario)
                
                # What the grade midpoint is in current scenario
                grade_salary = self._get_grade_salary(current_scenario, emp['position_group__name'], grade)
                
                analysis[position]['current_grading'][grade]['count'] += 1
                
                if grade_salary == 0:
                    continue
                
                # Over/Under/At calculation with 2% tolerance
                if current_salary > grade_salary * 1.02:
                    analysis[position]['current_grading'][grade]['over'] += 1
                elif current_salary < grade_salary * 0.98:
                    analysis[position]['current_grading'][grade]['under'] += 1
                else:
                    analysis[position]['current_grading'][grade]['at'] += 1
            
            # Each scenario analysis
            for scenario in scenarios:
                scenario_name = scenario.name
                scenario_data = defaultdict(lambda: {
                    'count': 0,
                    'over': 0,
                    'at': 0,
                    'under': 0
                })
                
                for emp in position_employees:
                    grade = self._normalize_grade_level(emp['grading_level'])
                    if not grade:
                        continue
                    
                    # Employee's current salary (stays same)
                    current_salary = self._get_employee_current_salary(emp, current_scenario)
                    
                    # What the grade midpoint WOULD BE in this scenario
                    scenario_salary = self._get_grade_salary(scenario, emp['position_group__name'], grade)
                    
                    scenario_data[grade]['count'] += 1
                    
                    if scenario_salary == 0:
                        continue
                    
                    if current_salary > scenario_salary * 1.02:
                        scenario_data[grade]['over'] += 1
                    elif current_salary < scenario_salary * 0.98:
                        scenario_data[grade]['under'] += 1
                    else:
                        scenario_data[grade]['at'] += 1
                
                analysis[position]['scenarios'][scenario_name] = dict(scenario_data)
            
            analysis[position]['current_grading'] = dict(analysis[position]['current_grading'])
        
        return analysis
    
    def _get_grade_salary(self, scenario, position_name, grade_level):
        """
        Get the midpoint (M) salary for a specific grade level in a scenario
        """
        if not scenario.calculated_grades:
            return 0
        
        for pos_name, grades in scenario.calculated_grades.items():
            if self._positions_match(position_name, pos_name):
                if isinstance(grades, dict):
                    # Return median (M) value for the grade
                    return float(grades.get(grade_level, 0) or 0)
        
        return 0
    
    def _build_underpaid_overpaid_lists(self, current_scenario, scenarios, employees):
        """
        Underpaid and Overpaid employee lists
        Compares employee's current salary vs what scenario says it should be
        """
        result = {}
        
        for scenario in scenarios:
            scenario_name = scenario.name
            underpaid = []
            overpaid = []
            
            for emp in employees:
                # Employee's current salary (from current scenario + their grading)
                current_salary = self._get_employee_current_salary(emp, current_scenario)
                
                if current_salary == 0:
                    continue
                
                # What salary SHOULD BE according to this scenario
                grade_level = self._normalize_grade_level(emp['grading_level'])
                if not grade_level:
                    continue
                
                scenario_salary = self._get_grade_salary(
                    scenario, 
                    emp['position_group__name'], 
                    grade_level
                )
                
                if scenario_salary == 0:
                    continue
                
                # Calculate difference
                difference = scenario_salary - current_salary
                diff_percent = (difference / current_salary * 100) if current_salary > 0 else 0
                
                employee_info = {
                    'employee_id': emp['employee_id'],
                    'employee_name': emp['full_name'],
                    'position': emp['position_group__name'],
                    'department': emp['department__name'] or 'N/A',
                    'start_date': str(emp['start_date']) if emp['start_date'] else 'N/A',
                    'current_salary': round(current_salary),
                    'scenario_salary': round(scenario_salary),
                    'difference': round(difference),
                    'difference_percent': round(diff_percent, 1),
                    'grading_level': grade_level
                }
                
                # 2% tolerance for classification
                if scenario_salary < current_salary * 0.98:
                    # Scenario suggests lower salary - employee is OVERPAID
                    overpaid.append(employee_info)
                elif scenario_salary > current_salary * 1.02:
                    # Scenario suggests higher salary - employee is UNDERPAID
                    underpaid.append(employee_info)
            
            # Sort by absolute difference
            underpaid.sort(key=lambda x: x['difference'], reverse=True)
            overpaid.sort(key=lambda x: abs(x['difference']), reverse=True)
            
            result[scenario_name] = {
                'underpaid': underpaid,
                'overpaid': overpaid
            }
            
          
        
        return result
    
    def _build_scenarios_percentage_comparison(self, current_scenario, scenarios):
        """
        Figure 3: Scenarios Comparison - Percentage Differences
        Shows percentage difference of each grade level from current to scenarios
        """
        result = {}
        
        if not current_scenario.calculated_grades:
            return result
        
        for position_name in current_scenario.grade_order:
            current_grades = current_scenario.calculated_grades.get(position_name, {})
            
            if not isinstance(current_grades, dict):
                continue
            
            result[position_name] = {
                'current': {
                    'LD': float(current_grades.get('LD', 0) or 0),
                    'LQ': float(current_grades.get('LQ', 0) or 0),
                    'M': float(current_grades.get('M', 0) or 0),
                    'UQ': float(current_grades.get('UQ', 0) or 0),
                    'UD': float(current_grades.get('UD', 0) or 0)
                },
                'scenarios': {}
            }
            
            for scenario in scenarios:
                scenario_name = scenario.name
                scenario_grades = scenario.calculated_grades.get(position_name, {})
                
                if not isinstance(scenario_grades, dict):
                    continue
                
                scenario_comparison = {}
                
                for level in ['LD', 'LQ', 'M', 'UQ', 'UD']:
                    current_value = float(current_grades.get(level, 0) or 0)
                    scenario_value = float(scenario_grades.get(level, 0) or 0)
                    
                    diff_percent = 0
                    if current_value > 0:
                        diff_percent = ((scenario_value - current_value) / current_value) * 100
                    
                    scenario_comparison[level] = {
                        'value': round(scenario_value),
                        'diff_percent': round(diff_percent, 1),
                        'diff_amount': round(scenario_value - current_value)
                    }
                
                result[position_name]['scenarios'][scenario_name] = scenario_comparison
        
        return result
    @action(detail=False, methods=['get'])
    def current_scenario(self, request):
        """Get current active scenario"""
        try:
            try:
                current_scenario = SalaryScenario.objects.get(status='CURRENT')
                serializer = SalaryScenarioDetailSerializer(current_scenario)
                return Response(serializer.data)
            except SalaryScenario.DoesNotExist:
                return Response({
                    'message': 'No current scenario found',
                    'current_scenario': None
                }, status=status.HTTP_404_NOT_FOUND)
                
        except Exception as e:
            logger.error(f"Error getting current scenario: {str(e)}")
            return Response({
                'error': 'Failed to get current scenario',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
