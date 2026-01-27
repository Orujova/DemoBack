# api/status_management.py - ENHANCED: Advanced Contract Status Management with Line Manager Integration

from django.utils import timezone
from datetime import timedelta, date
from .models import Employee, EmployeeStatus, EmployeeActivity, ContractTypeConfig
import logging
logger = logging.getLogger(__name__)

class EmployeeStatusManager:
    """
    Employee status-larını avtomatik idarə etmək üçün enhanced class
    Contract configuration əsasında statusları idarə edir
    """
    
   
    
    @staticmethod
    def calculate_required_status(employee):
        """✅ COMPLETELY FIXED: Status calculation with proper logic"""
        try:
            current_date = date.today()
            
            # ✅ CHECK 1: Has start date?
            if not employee.start_date:
              
                return employee.status, "No start date defined"
            
            # ✅ CHECK 2: Not started yet?
            if employee.start_date > current_date:
                days_until_start = (employee.start_date - current_date).days
               
                return employee.status, f"Employee hasn't started yet (starts in {days_until_start} days)"
            
            # ✅ CHECK 3: Calculate days since start
            days_since_start = (current_date - employee.start_date).days
            
        
            
            # ✅ CHECK 4: Contract ended?
            if employee.contract_end_date and employee.contract_end_date <= current_date:
                inactive_status = EmployeeStatus.objects.filter(
                    status_type='INACTIVE',
                    is_active=True
                ).first()
                
                if inactive_status:
                   
                    return inactive_status, f"Contract ended on {employee.contract_end_date}"
            
            # ✅ CHECK 5: Get contract config
            try:
                contract_config = ContractTypeConfig.objects.get(
                    contract_type=employee.contract_duration,
                    is_active=True
                )
            except ContractTypeConfig.DoesNotExist:
             
                
                # DEFAULT: If no config, use ACTIVE after 90 days
                if days_since_start > 90:
                    active_status = EmployeeStatus.objects.filter(
                        status_type='ACTIVE',
                        is_active=True
                    ).first()
                    return active_status, "No contract config - defaulting to ACTIVE after 90 days"
                else:
                    return employee.status, "No contract configuration found"
            
            # ✅ CHECK 6: Auto transitions enabled?
            if not contract_config.enable_auto_transitions:
      
                return employee.status, "Auto transitions disabled for this contract type"
            
            # ✅ CHECK 7: PERMANENT contracts → directly ACTIVE (NO probation)
            if employee.contract_duration == 'PERMANENT':
                active_status = EmployeeStatus.objects.filter(
                    status_type='ACTIVE',
                    is_active=True
                ).first()
                
                if active_status:
           
                    return active_status, "Permanent contract - directly active (no probation period)"
                else:
                   
                    return employee.status, "ACTIVE status not found"
            
            # ✅ CHECK 8: For ALL other contracts → Check probation period
            probation_days = contract_config.probation_days
            
          
            
            # ✅ CRITICAL: Still in probation?
            if days_since_start < probation_days:
                probation_status = EmployeeStatus.objects.filter(
                    status_type='PROBATION',
                    is_active=True
                ).first()
                
                if not probation_status:
                  
                    active_status = EmployeeStatus.objects.filter(
                        status_type='ACTIVE',
                        is_active=True
                    ).first()
                    return active_status, "PROBATION status not found - using ACTIVE"
                
                remaining_days = probation_days - days_since_start
         
                return probation_status, f"In probation period ({remaining_days} days remaining of {probation_days})"
            
            # ✅ CHECK 9: Probation completed → ACTIVE
            else:
                active_status = EmployeeStatus.objects.filter(
                    status_type='ACTIVE',
                    is_active=True
                ).first()
                
                if not active_status:
          
                    return employee.status, "ACTIVE status not found"
                
                
                return active_status, f"Probation period completed ({days_since_start} days since start, probation was {probation_days} days)"
                
        except Exception as e:
            logger.error(f"Error calculating status for employee {employee.employee_id}: {str(e)}")
            return employee.status, f"Error: {str(e)}"
    @staticmethod
    def update_employee_status(employee, force_update=False, user=None):
        """
        Tək employee üçün status-u yenilə
        """
        required_status, reason = EmployeeStatusManager.calculate_required_status(employee)
        current_status = employee.status
        
        # Status dəyişməlidirsə və ya zorla yeniləmə tələb edilirsə
        if current_status != required_status or force_update:
            if required_status:
                old_status = employee.status
                employee.status = required_status
                if user:
                    employee.updated_by = user
                employee.save()
                
                # Activity log
                EmployeeActivity.objects.create(
                    employee=employee,
                    activity_type='STATUS_CHANGED',
                    description=f"Status automatically updated from {old_status.name} to {required_status.name}. Reason: {reason}",
                    performed_by=user,
                    metadata={
                        'old_status': old_status.name,
                        'new_status': required_status.name,
                        'reason': reason,
                        'automatic': True,
                        'contract_type': employee.contract_duration,
                        'days_since_start': (date.today() - employee.start_date).days,
                        'force_update': force_update
                    }
                )
                
              
                return True
        
        return False
    
    @staticmethod
    def bulk_update_statuses(employee_ids=None, force_update=False, user=None):
        """
        Bulk status yeniləmə
        """
        if employee_ids:
            employees = Employee.objects.filter(id__in=employee_ids)
        else:
            employees = Employee.objects.filter(is_deleted=False)
        
        updated_count = 0
        error_count = 0
        
        for employee in employees:
            try:
                if EmployeeStatusManager.update_employee_status(employee, force_update, user):
                    updated_count += 1
            except Exception as e:
                error_count += 1
                logger.error(f"Error updating status for {employee.employee_id}: {e}")
        
       
        return {'updated': updated_count, 'errors': error_count}
    
    @staticmethod
    def get_status_preview(employee):
        """
        Employee üçün status preview-ını qaytar (actual update etmədən)
        """
        required_status, reason = EmployeeStatusManager.calculate_required_status(employee)
        current_status = employee.status
        
        return {
            'employee_id': employee.employee_id,
            'employee_name': employee.full_name,
            'current_status': current_status.name if current_status else None,
            'required_status': required_status.name if required_status else None,
            'needs_update': current_status != required_status,
            'reason': reason,
            'contract_type': employee.contract_duration,
            'days_since_start': (date.today() - employee.start_date).days,
            'contract_end_date': employee.contract_end_date,
            'line_manager': employee.line_manager.full_name if employee.line_manager else None
        }
    
    @staticmethod
    def get_employees_needing_update(contract_type=None, department_id=None):
        """
        Status yeniləməyə ehtiyacı olan employee-ləri qaytar
        """
        queryset = Employee.objects.filter(is_deleted=False)
        
        if contract_type:
            queryset = queryset.filter(contract_duration=contract_type)
        
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        
        needing_updates = []
        
        for employee in queryset:
            try:
                preview = EmployeeStatusManager.get_status_preview(employee)
                if preview and preview.get('needs_update', False):
                    # Return a dictionary with employee and preview data
                    update_info = {
                        'employee': employee,
                        'current_status': preview.get('current_status', ''),
                        'required_status': preview.get('required_status', ''),
                        'reason': preview.get('reason', ''),
                        'needs_update': preview.get('needs_update', False),
                        'contract_type': preview.get('contract_type', ''),
                        'days_since_start': preview.get('days_since_start', 0)
                    }
                    needing_updates.append(update_info)
            except Exception as e:
                logger.error(f"Error getting status preview for employee {employee.employee_id}: {e}")
                continue
        
        return needing_updates
        
    
    @staticmethod
    def get_contract_expiry_analysis(days=30):
        """
        Contract-ı bitən employee-ləri analiz et
        """
        expiry_date = date.today() + timedelta(days=days)
        
        expiring_employees = Employee.objects.filter(
            contract_end_date__lte=expiry_date,
            contract_end_date__gte=date.today(),
            contract_duration__in=['3_MONTHS', '6_MONTHS', '1_YEAR', '2_YEARS', '3_YEARS'],
            is_deleted=False
        ).select_related('status', 'business_function', 'department', 'line_manager')
        
        analysis = {
            'total_expiring': expiring_employees.count(),
            'by_urgency': {},
            'by_department': {},
            'by_line_manager': {},
            'employees': []
        }
        
        for employee in expiring_employees:
            days_left = (employee.contract_end_date - date.today()).days
            
            # Urgency analysis
            if days_left <= 7:
                urgency = 'critical'
            elif days_left <= 14:
                urgency = 'high'
            elif days_left <= 30:
                urgency = 'medium'
            else:
                urgency = 'low'
            
            analysis['by_urgency'][urgency] = analysis['by_urgency'].get(urgency, 0) + 1
            
            # Department analysis
            dept_key = employee.department.name
            analysis['by_department'][dept_key] = analysis['by_department'].get(dept_key, 0) + 1
            
            # Line manager analysis
            manager_key = employee.line_manager.full_name if employee.line_manager else 'No Manager'
            analysis['by_line_manager'][manager_key] = analysis['by_line_manager'].get(manager_key, 0) + 1
            
            # Employee details
            analysis['employees'].append({
                'employee_id': employee.employee_id,
                'name': employee.full_name,
                'department': employee.department.name,
                'line_manager': employee.line_manager.full_name if employee.line_manager else None,
                'contract_end_date': employee.contract_end_date,
                'days_remaining': days_left,
                'urgency': urgency,
                
            })
        
        return analysis
    
    @staticmethod
    def get_status_transition_analytics():
        """
        Status transition analytics
        """
        all_employees = Employee.objects.filter(is_deleted=False)
        
        analytics = {
            'total_employees': all_employees.count(),
            'by_current_status': {},
            'by_required_status': {},
            'transitions_needed': {},
            'by_contract_type': {},
            'line_manager_impact': {}
        }
        
        for employee in all_employees:
            preview = EmployeeStatusManager.get_status_preview(employee)
            
            # Current status
            current = preview['current_status']
            analytics['by_current_status'][current] = analytics['by_current_status'].get(current, 0) + 1
            
            # Required status
            required = preview['required_status']
            analytics['by_required_status'][required] = analytics['by_required_status'].get(required, 0) + 1
            
            # Transitions
            if preview['needs_update']:
                transition = f"{current} → {required}"
                analytics['transitions_needed'][transition] = analytics['transitions_needed'].get(transition, 0) + 1
            
            # Contract type
            contract = preview['contract_type']
            if contract not in analytics['by_contract_type']:
                analytics['by_contract_type'][contract] = {'total': 0, 'needs_update': 0}
            analytics['by_contract_type'][contract]['total'] += 1
            if preview['needs_update']:
                analytics['by_contract_type'][contract]['needs_update'] += 1
            
            # Line manager impact
            manager = preview['line_manager'] or 'No Manager'
            if manager not in analytics['line_manager_impact']:
                analytics['line_manager_impact'][manager] = {'total': 0, 'needs_update': 0}
            analytics['line_manager_impact'][manager]['total'] += 1
            if preview['needs_update']:
                analytics['line_manager_impact'][manager]['needs_update'] += 1
        
        return analytics

# Enhanced Line Manager Status Integration
class LineManagerStatusIntegration:
    """
    Line manager və status-ların inteqrasiyası üçün helper class
    """
    
    @staticmethod
    def get_manager_team_status_overview(manager_employee_id):
        """
        Line manager-in team-inin status overview-ını qaytar
        """
        try:
            manager = Employee.objects.get(employee_id=manager_employee_id)
            direct_reports = manager.direct_reports.filter(
                is_deleted=False,
                status__affects_headcount=True
            )
            
            overview = {
                'manager': {
                    'employee_id': manager.employee_id,
                    'name': manager.full_name,
                    'job_title': manager.job_title
                },
                'team_size': direct_reports.count(),
                'status_distribution': {},
                'employees_needing_update': [],
                'contract_expiry_alerts': []
            }
            
            for employee in direct_reports:
                # Status distribution
                status_name = employee.status.name
                overview['status_distribution'][status_name] = overview['status_distribution'].get(status_name, 0) + 1
                
                # Check if status update needed
                preview = EmployeeStatusManager.get_status_preview(employee)
                if preview['needs_update']:
                    overview['employees_needing_update'].append({
                        'employee_id': employee.employee_id,
                        'name': employee.full_name,
                        'current_status': preview['current_status'],
                        'required_status': preview['required_status'],
                        'reason': preview['reason']
                    })
                
                # Contract expiry alerts
                if employee.contract_end_date:
                    days_left = (employee.contract_end_date - date.today()).days
                    if 0 <= days_left <= 30:
                        overview['contract_expiry_alerts'].append({
                            'employee_id': employee.employee_id,
                            'name': employee.full_name,
                            'contract_end_date': employee.contract_end_date,
                            'days_remaining': days_left
                        })
            
            return overview
            
        except Employee.DoesNotExist:
            return None
    
    @staticmethod
    def get_managers_needing_attention():
        """
        Diqqət tələb edən manager-ləri qaytar
        """
        managers = Employee.objects.filter(
            direct_reports__isnull=False,
            is_deleted=False
        ).distinct()
        
        managers_needing_attention = []
        
        for manager in managers:
            overview = LineManagerStatusIntegration.get_manager_team_status_overview(manager.employee_id)
            
            if overview:
                attention_score = 0
                reasons = []
                
                # Status updates needed
                if overview['employees_needing_update']:
                    attention_score += len(overview['employees_needing_update']) * 2
                    reasons.append(f"{len(overview['employees_needing_update'])} employees need status updates")
                
                # Contract expiries
                if overview['contract_expiry_alerts']:
                    attention_score += len(overview['contract_expiry_alerts']) * 3
                    reasons.append(f"{len(overview['contract_expiry_alerts'])} contracts expiring soon")
                
                # Large team without recent activity
                if overview['team_size'] > 10:
                    attention_score += 1
                    reasons.append(f"Large team ({overview['team_size']} members)")
                
                if attention_score > 0:
                    managers_needing_attention.append({
                        'manager': overview['manager'],
                        'attention_score': attention_score,
                        'reasons': reasons,
                        'team_overview': overview
                    })
        
        # Sort by attention score
        managers_needing_attention.sort(key=lambda x: x['attention_score'], reverse=True)
        
        return managers_needing_attention


# Status Automation Rules
class StatusAutomationRules:
    
    @staticmethod
    def check_and_apply_rules():
        """✅ UPDATED: Yalnız 2 rule"""
        results = {
            'probation_to_active': 0,
            'contract_expired_to_inactive': 0,
            'errors': []
        }
        
        try:
            # Rule 1: Probation to Active
            results['probation_to_active'] = StatusAutomationRules._apply_probation_to_active()
            
            # Rule 2: Contract Expired to Inactive
            results['contract_expired_to_inactive'] = StatusAutomationRules._apply_contract_expired_to_inactive()
            
        except Exception as e:
            results['errors'].append(str(e))
            logger.error(f"Error in status automation rules: {e}")
        
        return results
    
    @staticmethod
    def _apply_probation_to_active():
        """✅ Probation → Active transition"""
        count = 0
        probation_employees = Employee.objects.filter(
            status__status_type__iexact='PROBATION',
            is_deleted=False
        )
        
        for employee in probation_employees:
            preview = EmployeeStatusManager.get_status_preview(employee)
            if preview['needs_update'] and preview['required_status'] == 'ACTIVE':
                if EmployeeStatusManager.update_employee_status(employee):
                    count += 1
        
        return count
    
    @staticmethod
    def _apply_contract_expired_to_inactive():
        """Apply contract expired to inactive rule"""
        count = 0
        today = date.today()
        
        expired_contracts = Employee.objects.filter(
            contract_end_date__lt=today,
            status__affects_headcount=True,
            is_deleted=False
        )
        
        inactive_status = EmployeeStatus.objects.filter(status_type__iexact='INACTIVE').first()
        
        if inactive_status:
            for employee in expired_contracts:
                if employee.status != inactive_status:
                    employee.status = inactive_status
                    employee.save()
                    
                    # Log activity
                    EmployeeActivity.objects.create(
                        employee=employee,
                        activity_type='STATUS_CHANGED',
                        description=f"Status automatically changed to INACTIVE due to contract expiry",
                        performed_by=None,
                        metadata={
                            'automatic': True,
                            'rule': 'contract_expired_to_inactive',
                            'contract_end_date': str(employee.contract_end_date)
                        }
                    )
                    count += 1
        
        return count