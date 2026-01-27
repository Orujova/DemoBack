# api/tasks/resignation_exit_tasks.py
"""
Celery tasks for resignation, exit interview, contract, and probation management
Automated notifications and status updates
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)


# =====================================
# CONTRACT EXPIRY TASKS
# =====================================

@shared_task
def check_expiring_contracts():
    """
    Check for contracts expiring in 2 weeks
    Send notifications to managers
    Create contract renewal requests
    Runs daily
    """
    from api.models import Employee
    from api.contract_probation_models import ContractRenewalRequest
    from api.system_email_service import system_email_service
    
    try:
        # Calculate date 2 weeks from now
        two_weeks_later = date.today() + timedelta(days=14)
        
        # Find employees with contracts expiring in 2 weeks
        expiring_employees = Employee.objects.filter(
            contract_end_date=two_weeks_later,
            contract_duration__in=['3_MONTHS', '6_MONTHS', '1_YEAR', '2_YEARS'],
            status__affects_headcount=True,
            is_deleted=False
        ).select_related('line_manager', 'business_function', 'department')
        
        for employee in expiring_employees:
            # Check if renewal request already exists
            existing_request = ContractRenewalRequest.objects.filter(
                employee=employee,
                current_contract_end_date=employee.contract_end_date,
                is_deleted=False
            ).exists()
            
            if existing_request:
                continue
            
            # Create contract renewal request
            renewal_request = ContractRenewalRequest.objects.create(
                employee=employee,
                current_contract_end_date=employee.contract_end_date,
                current_contract_type=employee.contract_duration,
                notification_sent_at=timezone.now()
            )
            
            # Send notification to manager
            if employee.line_manager and employee.line_manager.email:
                _send_contract_expiry_notification(employee, renewal_request)
            
            logger.info(f"Contract expiry notification sent for: {employee.employee_id}")
        
        return f"Processed {len(expiring_employees)} expiring contracts"
        
    except Exception as e:
        logger.error(f"Error in check_expiring_contracts: {e}")
        raise


def _send_contract_expiry_notification(employee, renewal_request):
    """Send contract expiry notification to manager"""
    from api.system_email_service import system_email_service
    
    try:
        subject = f"Contract Renewal Decision Required - {employee.full_name}"
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #F59E0B;">Contract Expiring - Action Required</h2>
            
            <p>Dear {employee.line_manager.first_name},</p>
            
            <p>The following employee's contract will expire in 2 weeks. Please make a renewal decision:</p>
            
            <div style="background-color: #FEF3C7; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #F59E0B;">
                <p><strong>Employee:</strong> {employee.full_name} ({employee.employee_id})</p>
                <p><strong>Position:</strong> {employee.job_title}</p>
                <p><strong>Department:</strong> {employee.department.name}</p>
                <p><strong>Current Contract Type:</strong> {employee.get_contract_duration_display()}</p>
                <p><strong>Contract Expires:</strong> {employee.contract_end_date}</p>
                <p><strong>Days Remaining:</strong> 14 days</p>
            </div>
            
            <p><strong>Action Required:</strong></p>
            <ul>
                <li>Review employee's performance and attendance</li>
                <li>Decide whether to renew the contract</li>
                <li>Submit your decision through the HRIS system</li>
            </ul>
            
            <p>Please submit your decision as soon as possible.</p>
            
          
        </body>
        </html>
        """
        
        system_email_service.send_email_as_system(
            from_email="myalmet@almettrading.com",
            to_email=employee.line_manager.email,
            subject=subject,
            body_html=body
        )
        
        # Also send system notification
        system_email_service.send_email_as_system(
            from_email="myalmet@almettrading.com",
            to_email=employee.line_manager.email,
            subject=f"🔔 Contract Renewal: {employee.full_name}",
            body_html=f"Contract expires on {employee.contract_end_date}. Please submit your decision."
        )
        
    except Exception as e:
        logger.error(f"Error sending contract expiry notification: {e}")


# =====================================
# PROBATION REVIEW TASKS
# =====================================

@shared_task
def check_probation_reviews():

    from api.models import Employee, ContractTypeConfig
    from api.contract_probation_models import ProbationReview
    from api.system_email_service import system_email_service
    
    try:
        # Calculate date 3 days from now
        three_days_later = date.today() + timedelta(days=3)
        
        # Find employees in probation status
        probation_employees = Employee.objects.filter(
            status__status_type='PROBATION',
            start_date__isnull=False,
            is_deleted=False
        ).select_related('line_manager', 'business_function', 'department')
        
        review_count = 0
        
        for employee in probation_employees:
            try:
               
                # Calculate review dates
                review_30_date = employee.start_date + timedelta(days=30)
                review_60_date = employee.start_date + timedelta(days=60)
                review_90_date = employee.start_date + timedelta(days=90)
                
                # Check which review is due
                reviews_to_create = []
                
                if review_30_date == three_days_later:
                    reviews_to_create.append(('30_DAY', review_30_date))
                
                if review_60_date == three_days_later:
                    reviews_to_create.append(('60_DAY', review_60_date))
                
                if review_90_date == three_days_later:
                    reviews_to_create.append(('90_DAY', review_90_date))
                
                # Create reviews and send notifications
                for review_period, due_date in reviews_to_create:
                    # Check if review already exists
                    existing_review = ProbationReview.objects.filter(
                        employee=employee,
                        review_period=review_period,
                        is_deleted=False
                    ).exists()
                    
                    if existing_review:
                        continue
                    
                    # Create probation review
                    review = ProbationReview.objects.create(
                        employee=employee,
                        review_period=review_period,
                        due_date=due_date,
                        notification_sent_at=timezone.now()
                    )
                    
                    # Send notification
                    _send_probation_review_notification(employee, review)
                    
                    review_count += 1
                    logger.info(f"Probation review created for: {employee.employee_id} - {review_period}")
                    
            except ContractTypeConfig.DoesNotExist:
                logger.warning(f"No contract config for employee {employee.employee_id}")
                continue
        
        return f"Created {review_count} probation reviews"
        
    except Exception as e:
        logger.error(f"Error in check_probation_reviews: {e}")
        raise


def _send_probation_review_notification(employee, review):
    """Send probation review notification"""
    from api.system_email_service import system_email_service
    
    try:
        # Prepare recipients
        recipients = []
        
        # Employee
        if employee.email:
            recipients.append(employee.email)
        
        # Manager
        if employee.line_manager and employee.line_manager.email:
            recipients.append(employee.line_manager.email)
        
        if not recipients:
            return
        
        subject = f"Probation Review Due - {review.get_review_period_display()}"
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #3B82F6;">Probation Review - Action Required</h2>
            
            <p>A probation review is due in 3 days:</p>
            
            <div style="background-color: #DBEAFE; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #3B82F6;">
                <p><strong>Employee:</strong> {employee.full_name} ({employee.employee_id})</p>
                <p><strong>Position:</strong> {employee.job_title}</p>
                <p><strong>Department:</strong> {employee.department.name}</p>
                <p><strong>Review Period:</strong> {review.get_review_period_display()}</p>
                <p><strong>Due Date:</strong> {review.due_date}</p>
            </div>
            
            <p><strong>Action Required:</strong></p>
            <ul>
                <li><strong>Employee:</strong> Complete your self-assessment questionnaire</li>
                <li><strong>Manager:</strong> Complete manager evaluation questionnaire</li>
            </ul>
            
           
        </body>
        </html>
        """
        
        system_email_service.send_email_as_system(
            from_email="myalmet@almettrading.com",
            to_email=recipients,
            subject=subject,
            body_html=body
        )
        
    except Exception as e:
        logger.error(f"Error sending probation review notification: {e}")


# =====================================
# RESIGNATION REMINDER TASKS
# =====================================

@shared_task
def send_resignation_reminders():

    from api.resignation_models import ResignationRequest
    from api.system_email_service import system_email_service
    
    try:
        # Find pending resignations older than 3 days
        three_days_ago = timezone.now() - timedelta(days=3)
        
        pending_resignations = ResignationRequest.objects.filter(
            status='PENDING_MANAGER',
            created_at__lte=three_days_ago,
            is_deleted=False
        ).select_related('employee__line_manager')
        
        for resignation in pending_resignations:
            if resignation.employee.line_manager and resignation.employee.line_manager.email:
                _send_resignation_reminder(resignation)
        
        return f"Sent reminders for {len(pending_resignations)} resignations"
        
    except Exception as e:
        logger.error(f"Error in send_resignation_reminders: {e}")
        raise


def _send_resignation_reminder(resignation):
    
    from api.system_email_service import system_email_service
    
    try:
        subject = f"Reminder: Resignation Approval Pending - {resignation.employee.full_name}"
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #F59E0B;">Reminder: Resignation Approval Pending</h2>
            
            <p>Dear {resignation.employee.line_manager.first_name},</p>
            
            <p>This is a reminder that a resignation request is pending your approval:</p>
            
            <div style="background-color: #FEF3C7; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #F59E0B;">
                <p><strong>Employee:</strong> {resignation.employee.full_name}</p>
                <p><strong>Submitted:</strong> {resignation.submission_date}</p>
                <p><strong>Last Working Day:</strong> {resignation.last_working_day}</p>
                <p><strong>Days Remaining:</strong> {resignation.get_days_until_last_working_day()} days</p>
            </div>
            
            <p>Please review and approve/reject this resignation as soon as possible.</p>
            

        </body>
        </html>
        """
        
        system_email_service.send_email_as_system(
            from_email="myalmet@almettrading.com",
            to_email=resignation.employee.line_manager.email,
            subject=subject,
            body_html=body
        )
        
    except Exception as e:
        logger.error(f"Error sending resignation reminder: {e}")


# =====================================
# EXIT INTERVIEW REMINDER TASKS
# =====================================

@shared_task
def send_exit_interview_reminders():
 
    from api.exit_interview_models import ExitInterview
    from api.system_email_service import system_email_service
    
    try:
        # Find pending exit interviews
        pending_interviews = ExitInterview.objects.filter(
            status='PENDING',
            last_working_day__gte=date.today(),
            is_deleted=False
        ).select_related('employee')
        
        for interview in pending_interviews:
            # Calculate days until last working day
            days_remaining = (interview.last_working_day - date.today()).days
            
            # Send reminder if 7 days or less remaining
            if days_remaining <= 7 and interview.employee.email:
                _send_exit_interview_reminder(interview, days_remaining)
        
        return f"Sent reminders for {len(pending_interviews)} exit interviews"
        
    except Exception as e:
        logger.error(f"Error in send_exit_interview_reminders: {e}")
        raise


def _send_exit_interview_reminder(interview, days_remaining):

    from api.system_email_service import system_email_service
    
    try:
        subject = f"Reminder: Exit Interview Pending - {days_remaining} Days Remaining"
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #EF4444;">Reminder: Exit Interview Pending</h2>
            
            <p>Dear {interview.employee.first_name},</p>
            
            <p>This is a reminder to complete your exit interview before your last working day.</p>
            
            <div style="background-color: #FEE2E2; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #EF4444;">
                <p><strong>Last Working Day:</strong> {interview.last_working_day}</p>
                <p><strong>Days Remaining:</strong> {days_remaining} days</p>
            </div>
            
            <p>Your feedback is valuable and will help us improve our workplace.</p>
            
            <p>Please complete the exit interview through the HRIS system.</p>
            
        
        </body>
        </html>
        """
        
        system_email_service.send_email_as_system(
            from_email="myalmet@almettrading.com",
            to_email=interview.employee.email,
            subject=subject,
            body_html=body
        )
        
    except Exception as e:
        logger.error(f"Error sending exit interview reminder: {e}")


