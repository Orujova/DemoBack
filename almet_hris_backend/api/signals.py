# api/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Employee
from .status_management import EmployeeStatusManager
import logging

logger = logging.getLogger(__name__)

# ==================== STATUS MANAGEMENT SIGNALS ====================

@receiver(post_save, sender=Employee)
def auto_update_employee_status(sender, instance, created, **kwargs):
    """
    ✅ Avtomatik status yenilənməsi - FIXED
    """
    
    # Skip if explicitly disabled (for bulk operations)
    if getattr(instance, '_skip_auto_status_update', False):
        return
    
    # Skip if deleted
    if instance.is_deleted:
        return
    

    if created:
 
        return
    
    try:
        # Check if status needs update
        required_status, reason = EmployeeStatusManager.calculate_required_status(instance)
        
        # If status needs to change
        if required_status and required_status != instance.status:
            logger.info(
                f"🔄 Auto-updating status for {instance.employee_id}: "
                f"{instance.status.name if instance.status else 'None'} -> {required_status.name}"
            )
            logger.info(f"   Reason: {reason}")
            
            # ✅ CRITICAL: Update using queryset to avoid triggering signal again
            Employee.objects.filter(pk=instance.pk).update(status=required_status)
            
            # Refresh instance
            instance.refresh_from_db()
            
            # Log activity
            from .models import EmployeeActivity
            EmployeeActivity.objects.create(
                employee=instance,
                activity_type='STATUS_CHANGED',
                description=f"Status automatically updated to {required_status.name}. Reason: {reason}",
                performed_by=None,
                metadata={
                    'automatic': True,
                    'trigger': 'post_save_signal',
                    'reason': reason,
                    'new_status': required_status.name
                }
            )
            
           
        else:
            logger.debug(f"   ℹ️  No status update needed for {instance.employee_id}")
            
    except Exception as e:
        logger.error(f"❌ Error in auto_update_employee_status for {instance.employee_id}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


# ==================== CELEBRATION NOTIFICATION SIGNALS ====================

@receiver(pre_save, sender=Employee)
def track_position_change(sender, instance, **kwargs):
    """
    📝 Track position_group changes before saving
    Stores old position in instance for comparison
    """
    if instance.pk:  # Only for existing employees
        try:
            old_employee = Employee.objects.get(pk=instance.pk)
            instance._old_position_group = old_employee.position_group
        except Employee.DoesNotExist:
            instance._old_position_group = None
    else:
        instance._old_position_group = None


@receiver(post_save, sender=Employee)
def send_position_change_notification(sender, instance, created, **kwargs):

    if created:
        # New employee - no notification needed
        return
    
    # Check if position_group changed
    old_position = getattr(instance, '_old_position_group', None)
    new_position = instance.position_group
    
    if old_position and new_position and old_position != new_position:
      
        
       
        change_type = 'promotion'  # or 'transfer' based on your logic
        
        # Send notification asynchronously using Celery
        try:
            from .tasks import send_position_change_email
            send_position_change_email.delay(
                employee_id=instance.id,
                old_position=str(old_position),
                new_position=str(new_position),
                change_type=change_type
            )
        
        except Exception as e:
            logger.error(f"❌ Failed to queue position change notification: {e}")
            
            # Fallback: Send synchronously if Celery fails
            try:
                from .celebration_notification_service import celebration_notification_service
                celebration_notification_service.send_position_change_notification(
                    employee=instance,
                    old_position=str(old_position),
                    new_position=str(new_position),
                    change_type=change_type
                )
            except Exception as fallback_error:
                logger.error(f"❌ Fallback notification also failed: {fallback_error}")


# ==================== WELCOME EMAIL SIGNAL ====================

@receiver(pre_save, sender=Employee)
def track_employee_changes_for_welcome(sender, instance, **kwargs):
    """
    📝 Track changes before saving for welcome email detection
    """
    if instance.pk:
        try:
            old = Employee.objects.get(pk=instance.pk)
            instance._old_status = old.status
            instance._old_start_date = old.start_date
            instance._old_is_deleted = old.is_deleted
            
          
        except Employee.DoesNotExist:
            instance._old_status = None
            instance._old_start_date = None
            instance._old_is_deleted = None
           
    else:
        instance._old_status = None
        instance._old_start_date = None
        instance._old_is_deleted = None
      


@receiver(post_save, sender=Employee)
def welcome_new_employee(sender, instance, created, **kwargs):
 
    
    should_send_welcome = False
    trigger_reason = ""
    
    # Case 1: Brand new employee with start_date
    if created and not instance.is_deleted and instance.start_date:
        should_send_welcome = True
        trigger_reason = "New employee created with start_date"
     
    
    # Case 2: Existing employee changes
    elif not created and not instance.is_deleted:
        old_status = getattr(instance, '_old_status', None)
        old_start_date = getattr(instance, '_old_start_date', None)
        old_is_deleted = getattr(instance, '_old_is_deleted', None)
        
    
        
        # Status: Vacant → Not Vacant (and has start_date)
        status_changed_from_vacant = (
            old_status and 
            old_status.name == 'Vacant' and 
            instance.status and 
            instance.status.name != 'Vacant' and
            instance.start_date  # Must have start_date
        )
        
        # Start date added (was None, now has value)
        start_date_added = (
            not old_start_date and 
            instance.start_date and
            instance.status and
            instance.status.name != 'Vacant'  # Not vacant status
        )
        
        # Was deleted, now active
        reactivated = (
            old_is_deleted == True and
            instance.is_deleted == False and
            instance.start_date and
            instance.status and
            instance.status.name != 'Vacant'
        )
        
        if status_changed_from_vacant:
            should_send_welcome = True
            trigger_reason = f"Status changed from Vacant to {instance.status.name}"
           
            
        elif start_date_added:
            should_send_welcome = True
            trigger_reason = "Start date added to existing employee"
      
            
        elif reactivated:
            should_send_welcome = True
            trigger_reason = "Employee reactivated from deleted state"
       
        else:
            logger.info(f"❌ NO TRIGGER: Conditions not met")
    else:
        logger.info(f"❌ NO TRIGGER: Either deleted or brand new without start_date")
    
  
    
    if should_send_welcome:
       
        
        # ✅ FIRST TRY: Direct synchronous send (most reliable)
        try:
         
            
            from .celebration_notification_service import celebration_notification_service

        except Exception as e:
            logger.error(f"❌ Failed to send welcome email directly: {e}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            
            # ✅ SECOND TRY: Celery (if available)
            try:
               
                from .tasks import send_welcome_email_task
                
                send_welcome_email_task.delay(employee_id=instance.id)
                
                
            except Exception as celery_error:
                logger.error(f"❌ Celery also failed: {celery_error}")
                import traceback
                logger.error(f"   Traceback: {traceback.format_exc()}")
    else:
        logger.info(f"❌ NOT sending welcome email - conditions not met")
    
    logger.info("=" * 80)
    


from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender='api.Employee')
def auto_assign_job_description_to_employee(sender, instance, created, **kwargs):
  
    
    # Skip if employee is deleted
    if instance.is_deleted:
        return
    
    # Lazy import to avoid circular dependency
    from .job_description_models import JobDescription, JobDescriptionAssignment, normalize_grading_level
    
    try:
       
        
        # Find matching job descriptions
        matching_jds = JobDescription.objects.filter(
            job_title__iexact=instance.job_title.strip() if instance.job_title else '',
            business_function=instance.business_function,
            department=instance.department,
            job_function=instance.job_function,
            position_group=instance.position_group,
            is_active=True
        )
        
        if instance.unit:
            matching_jds = matching_jds.filter(unit=instance.unit)
        
        # Filter by grading level
        for jd in matching_jds:
            emp_grade_normalized = normalize_grading_level(instance.grading_level or '')
            jd_grades_normalized = [normalize_grading_level(gl) for gl in jd.grading_levels]
            
            if emp_grade_normalized not in jd_grades_normalized:
                continue
            
            # Check if already assigned
            existing_assignment = JobDescriptionAssignment.objects.filter(
                job_description=jd,
                employee=instance,
                is_active=True
            ).exists()
            
            if existing_assignment:
    
                continue
            
            # Check if there's a vacant assignment for this job description
            vacant_assignment = JobDescriptionAssignment.objects.filter(
                job_description=jd,
                is_vacancy=True,
                is_active=True,
                vacancy_position__job_title__iexact=instance.job_title.strip() if instance.job_title else '',
                vacancy_position__business_function=instance.business_function,
                vacancy_position__department=instance.department
            ).first()
            
            if vacant_assignment:
                # ✅ Vacant assignment-ı employee-ə çevir
                vacant_assignment.assign_new_employee(instance)
              
            else:
                # ✅ Yeni assignment yarat
                with transaction.atomic():
                    assignment = JobDescriptionAssignment.objects.create(
                        job_description=jd,
                        employee=instance,
                        is_vacancy=False,
                        reports_to=instance.line_manager
                    )
                    logger.info(f"✅ Auto-assigned: {instance.full_name} -> {jd.job_title}")
            
            # Only assign to first matching JD
            break
    
    except Exception as e:
        logger.error(f"❌ Error in auto_assign_job_description: {str(e)}", exc_info=True)


@receiver(pre_delete, sender='api.Employee')
def convert_employee_assignment_to_vacant(sender, instance, **kwargs):
  
    
    # Lazy import
    from .job_description_models import JobDescriptionAssignment
    
    try:
      
        
        # Get all active assignments for this employee
        active_assignments = JobDescriptionAssignment.objects.filter(
            employee=instance,
            is_active=True
        )
        
        for assignment in active_assignments:
          
            
            # Mark as vacant (don't delete)
            assignment.mark_as_vacant(reason="Employee deleted")

    
    except Exception as e:
        logger.error(f"❌ Error in convert_employee_assignment_to_vacant: {str(e)}", exc_info=True)


@receiver(post_save, sender='api.VacantPosition')
def handle_vacant_position_filled(sender, instance, created, **kwargs):
   
    
    # Only handle when vacant position is filled
    if not instance.is_filled or not instance.filled_by_employee:
        return
    
    # Lazy import
    from .job_description_models import JobDescriptionAssignment
    
    try:
        
        
        # Find vacant assignment for this position
        vacant_assignment = JobDescriptionAssignment.objects.filter(
            vacancy_position=instance,
            is_vacancy=True,
            is_active=True
        ).first()
        
        if vacant_assignment:
            # ✅ Convert to employee assignment
            vacant_assignment.assign_new_employee(instance.filled_by_employee)
           
        else:
            # No vacant assignment, trigger auto-assign for new employee
            logger.info(f"ℹ️ No vacant assignment found, will auto-assign if matching JD exists")
    
    except Exception as e:
        logger.error(f"❌ Error in handle_vacant_position_filled: {str(e)}", exc_info=True)


# ============================================
# HELPER FUNCTION FOR MANAGEMENT COMMAND
# ============================================

def assign_missing_job_descriptions():
    
    from .models import Employee
    from .job_description_models import JobDescription, JobDescriptionAssignment, normalize_grading_level
    

    
    total_assigned = 0
    total_checked = 0
    
    # Get all active employees
    employees = Employee.objects.filter(is_deleted=False).select_related(
        'business_function', 'department', 'unit', 'job_function', 'position_group', 'line_manager'
    )
    
    for employee in employees:
        total_checked += 1
        
        if not employee.job_title:
         
            continue
        
        # Find matching job descriptions
        matching_jds = JobDescription.objects.filter(
            job_title__iexact=employee.job_title.strip(),
            business_function=employee.business_function,
            department=employee.department,
            job_function=employee.job_function,
            position_group=employee.position_group,
            is_active=True
        )
        
        if employee.unit:
            matching_jds = matching_jds.filter(unit=employee.unit)
        
        for jd in matching_jds:
            # Check grading level
            emp_grade_normalized = normalize_grading_level(employee.grading_level or '')
            jd_grades_normalized = [normalize_grading_level(gl) for gl in jd.grading_levels]
            
            if emp_grade_normalized not in jd_grades_normalized:
                continue
            
            # Check if already assigned
            existing_assignment = JobDescriptionAssignment.objects.filter(
                job_description=jd,
                employee=employee,
                is_active=True
            ).exists()
            
            if existing_assignment:

                continue
            
            # Create assignment
            try:
                with transaction.atomic():
                    assignment = JobDescriptionAssignment.objects.create(
                        job_description=jd,
                        employee=employee,
                        is_vacancy=False,
                        reports_to=employee.line_manager
                    )
                    total_assigned += 1
                   
            except Exception as e:
                logger.error(f"❌ Failed to assign {employee.full_name}: {str(e)}")
            
            # Only assign to first matching JD
            break
  
    
    return {
        'total_checked': total_checked,
        'total_assigned': total_assigned
    }