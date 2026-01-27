# api/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import date
import logging
from datetime import timedelta
logger = logging.getLogger(__name__)

# ==================== EMPLOYEE STATUS TASKS ====================

@shared_task(name='api.tasks.update_all_employee_statuses')
def update_all_employee_statuses():
   
    from .models import Employee
    from .status_management import EmployeeStatusManager
    
    try:
    
        
        # Get all active employees (not deleted)
        employees = Employee.objects.filter(is_deleted=False).select_related('status', 'business_function', 'department')
        
        total_employees = employees.count()
        updated_count = 0
        error_count = 0
    
        
        for employee in employees:
            try:
                # Check if status needs update
                preview = EmployeeStatusManager.get_status_preview(employee)
                
                if preview['needs_update']:
                
                    
                    # Update the status
                    if EmployeeStatusManager.update_employee_status(employee, force_update=False, user=None):
                        updated_count += 1
                       
                    else:
                        logger.warning(f"   ⚠️ Update returned False for {employee.employee_id}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Error updating employee {employee.employee_id}: {str(e)}")
                continue
        
        
        
        return {
            'success': True,
            'total_employees': total_employees,
            'updated_count': updated_count,
            'error_count': error_count,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"💥 CRITICAL ERROR in automatic status update: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name='api.tasks.update_single_employee_status')
def update_single_employee_status(employee_id):
    """Update status for a single employee"""
    from .models import Employee
    from .status_management import EmployeeStatusManager
    
    try:
        employee = Employee.objects.get(id=employee_id)
        result = EmployeeStatusManager.update_employee_status(employee, force_update=False, user=None)
     
        return {'success': True, 'updated': result}
        
    except Employee.DoesNotExist:
        logger.error(f"❌ Employee {employee_id} not found")
        return {'success': False, 'error': 'Employee not found'}
    except Exception as e:
        logger.error(f"❌ Error updating employee {employee_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


# ==================== CELEBRATION NOTIFICATION TASKS ====================

@shared_task(name='api.tasks.send_daily_celebration_notifications')
def send_daily_celebration_notifications():
  
    from .celebration_notification_service import celebration_notification_service
    try:
        results = celebration_notification_service.check_and_send_daily_celebrations()
        return {
            'success': True,
            'birthdays_sent': results['birthdays_sent'],
            'anniversaries_sent': results['anniversaries_sent'],
            'errors': results.get('errors', []),
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        error_msg = f"💥 CRITICAL ERROR in daily celebration check: {str(e)}"
        logger.error(error_msg)
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name='api.tasks.send_position_change_email')
def send_position_change_email(employee_id, old_position, new_position, change_type='promotion'):
    
    from .models import Employee
    from .celebration_notification_service import celebration_notification_service
    
    try:
        employee = Employee.objects.get(id=employee_id)

        success = celebration_notification_service.send_position_change_notification(
            employee=employee,
            old_position=old_position,
            new_position=new_position,
            change_type=change_type
        )
        
        if success:
        
            return {'success': True, 'employee_id': employee_id}
        else:
            logger.error(f"❌ Failed to send position change notification")
            return {'success': False, 'employee_id': employee_id, 'error': 'Send failed'}
        
    except Employee.DoesNotExist:
        error_msg = f"❌ Employee {employee_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': 'Employee not found'}
    except Exception as e:
        error_msg = f"❌ Error sending position change email: {str(e)}"
        logger.error(error_msg)
        import traceback
        logger.error(traceback.format_exc())
        return {'success': False, 'error': str(e)}


@shared_task(name='api.tasks.send_birthday_notification')
def send_birthday_notification(employee_id):
    """
    🎂 Send birthday notification email (async)
    """
    from .models import Employee
    from .celebration_notification_service import celebration_notification_service
    
    try:
        employee = Employee.objects.get(id=employee_id)
        
        logger.info(f"🎂 Sending birthday notification for {employee.first_name} {employee.last_name}")
        
        success = celebration_notification_service.send_birthday_notification(employee)
        
        if success:
            logger.info(f"✅ Birthday notification sent successfully")
            return {'success': True, 'employee_id': employee_id}
        else:
            logger.error(f"❌ Failed to send birthday notification")
            return {'success': False, 'employee_id': employee_id, 'error': 'Send failed'}
        
    except Employee.DoesNotExist:
        error_msg = f"❌ Employee {employee_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': 'Employee not found'}
    except Exception as e:
        error_msg = f"❌ Error sending birthday email: {str(e)}"
        logger.error(error_msg)
        return {'success': False, 'error': str(e)}


@shared_task(name='api.tasks.send_anniversary_notification')
def send_anniversary_notification(employee_id, years):
    """
    🏆 Send work anniversary notification email (async)
    """
    from .models import Employee
    from .celebration_notification_service import celebration_notification_service
    
    try:
        employee = Employee.objects.get(id=employee_id)
        
        logger.info(f"🏆 Sending {years}-year anniversary notification for {employee.first_name} {employee.last_name}")
        
        success = celebration_notification_service.send_work_anniversary_notification(employee, years)
        
        if success:
            logger.info(f"✅ Anniversary notification sent successfully")
            return {'success': True, 'employee_id': employee_id, 'years': years}
        else:
            logger.error(f"❌ Failed to send anniversary notification")
            return {'success': False, 'employee_id': employee_id, 'error': 'Send failed'}
        
    except Employee.DoesNotExist:
        error_msg = f"❌ Employee {employee_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': 'Employee not found'}
    except Exception as e:
        error_msg = f"❌ Error sending anniversary email: {str(e)}"
        logger.error(error_msg)
        return {'success': False, 'error': str(e)}

@shared_task(name='api.tasks.resignation_exit_tasks.check_expiring_contracts')
def check_expiring_contracts():
    """
    Check for contracts expiring in 2 weeks
    """
    from .models import Employee
    from .contract_probation_models import ContractRenewalRequest
    from .system_email_service import system_email_service
    
    try:
        two_weeks_later = date.today() + timedelta(days=14)
        
        expiring_employees = Employee.objects.filter(
            contract_end_date=two_weeks_later,
            contract_duration__in=['3_MONTHS', '6_MONTHS', '1_YEAR', '2_YEARS'],
            status__affects_headcount=True,
            is_deleted=False
        ).select_related('line_manager', 'business_function', 'department')
        
        for employee in expiring_employees:
            existing_request = ContractRenewalRequest.objects.filter(
                employee=employee,
                current_contract_end_date=employee.contract_end_date,
                is_deleted=False
            ).exists()
            
            if existing_request:
                continue
            
            renewal_request = ContractRenewalRequest.objects.create(
                employee=employee,
                current_contract_end_date=employee.contract_end_date,
                current_contract_type=employee.contract_duration,
                notification_sent_at=timezone.now()
            )
            
            logger.info(f"✅ Contract expiry notification sent for: {employee.employee_id}")
        
        return f"Processed {len(expiring_employees)} expiring contracts"
        
    except Exception as e:
        logger.error(f"❌ Error in check_expiring_contracts: {e}")
        raise


@shared_task(name='api.tasks.resignation_exit_tasks.check_probation_reviews')
def check_probation_reviews():
    """
    Check probation reviews - creates review 3 days BEFORE milestone
    - Day 27 → Creates 30-day review (due on day 30)
    - Day 57 → Creates 60-day review (due on day 60)  
    - Day 87 → Creates 90-day review (due on day 90)
    """
    from .models import Employee
    from .contract_probation_models import ProbationReview
    from datetime import timedelta
    
    try:
        today = date.today()
        
        probation_employees = Employee.objects.filter(
            status__status_type='PROBATION',
            start_date__isnull=False,
            is_deleted=False
        ).select_related('line_manager', 'business_function', 'department')
        
        review_count = 0
        
        for employee in probation_employees:
            try:
                days_since_start = (today - employee.start_date).days
                
                logger.info(f"🔍 Checking {employee.employee_id}: {days_since_start} days since start")
                
                reviews_to_create = []
                
                # ✅ 30-day review: Create on day 27 (3 days before day 30)
                if days_since_start == 27:
                    due_date = employee.start_date + timedelta(days=30)
                    reviews_to_create.append(('30_DAY', due_date))
                    logger.info(f"   📅 Day 27 reached - should create 30-day review")
                
                # ✅ 60-day review: Create on day 57 (3 days before day 60)
                elif days_since_start == 57:
                    due_date = employee.start_date + timedelta(days=60)
                    reviews_to_create.append(('60_DAY', due_date))
                    logger.info(f"   📅 Day 57 reached - should create 60-day review")
                
                # ✅ 90-day review: Create on day 87 (3 days before day 90)
                elif days_since_start == 87:
                    due_date = employee.start_date + timedelta(days=90)
                    reviews_to_create.append(('90_DAY', due_date))
                    logger.info(f"   📅 Day 87 reached - should create 90-day review")
                
                for review_period, due_date in reviews_to_create:
                    # Check if already exists
                    existing_review = ProbationReview.objects.filter(
                        employee=employee,
                        review_period=review_period,
                        is_deleted=False
                    ).exists()
                    
                    if existing_review:
                        logger.info(f"   ℹ️  {review_period} already exists - skipping")
                        continue
                    
                    # ✅ Create review
                    review = ProbationReview.objects.create(
                        employee=employee,
                        review_period=review_period,
                        due_date=due_date,
                        notification_sent_at=timezone.now(),
                        status='PENDING'
                    )
                    
                    review_count += 1
                    logger.info(f"✅ Created: {employee.employee_id} - {review_period} (due: {due_date})")
                    
                    # TODO: Send notification email to employee & manager
                    
            except Exception as e:
                logger.warning(f"⚠️ Error for employee {employee.employee_id}: {e}")
                continue
        
        logger.info(f"📊 Total reviews created: {review_count}")
        return f"Created {review_count} probation reviews"
        
    except Exception as e:
        logger.error(f"❌ Error in check_probation_reviews: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

@shared_task(name='api.tasks.resignation_exit_tasks.send_resignation_reminders')
def send_resignation_reminders():
    """Send resignation reminders"""
    from .resignation_models import ResignationRequest
    from datetime import timedelta
    
    try:
        three_days_ago = timezone.now() - timedelta(days=3)
        
        pending_resignations = ResignationRequest.objects.filter(
            status='PENDING_MANAGER',
            created_at__lte=three_days_ago,
            is_deleted=False
        ).select_related('employee__line_manager')
        
        logger.info(f"📧 Sending reminders for {len(pending_resignations)} resignations")
        
        return f"Sent reminders for {len(pending_resignations)} resignations"
        
    except Exception as e:
        logger.error(f"❌ Error in send_resignation_reminders: {e}")
        raise


@shared_task(name='api.tasks.resignation_exit_tasks.send_exit_interview_reminders')
def send_exit_interview_reminders():
    """Send exit interview reminders"""
    from .exit_interview_models import ExitInterview
    
    try:
        pending_interviews = ExitInterview.objects.filter(
            status='PENDING',
            last_working_day__gte=date.today(),
            is_deleted=False
        ).select_related('employee')
        
        logger.info(f"📧 Sending reminders for {len(pending_interviews)} exit interviews")
        
        return f"Sent reminders for {len(pending_interviews)} exit interviews"
        
    except Exception as e:
        logger.error(f"❌ Error in send_exit_interview_reminders: {e}")
        raise
@shared_task(name='api.tasks.send_welcome_email_task')
def send_welcome_email_task(employee_id):
    """
    👋 Send welcome email to new employee (async)
    """
    from .models import Employee
    from .celebration_notification_service import celebration_notification_service
    
    try:
        employee = Employee.objects.get(id=employee_id)
        
        logger.info(f"👋 Sending welcome email for {employee.first_name} {employee.last_name}")
        
        success = celebration_notification_service.send_welcome_email(employee)
        
        if success:
            logger.info(f"✅ Welcome email sent successfully")
            return {'success': True, 'employee_id': employee_id}
        else:
            logger.error(f"❌ Failed to send welcome email")
            return {'success': False, 'employee_id': employee_id, 'error': 'Send failed'}
        
    except Employee.DoesNotExist:
        error_msg = f"❌ Employee {employee_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': 'Employee not found'}
    except Exception as e:
        error_msg = f"❌ Error sending welcome email: {str(e)}"
        logger.error(error_msg)
        import traceback
        logger.error(traceback.format_exc())
        return {'success': False, 'error': str(e)}