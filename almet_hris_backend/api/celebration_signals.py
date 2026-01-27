# api/celebration_signals.py
"""
Django Signals for Celebration Notifications
Automatically triggers emails when:
- Employee job_title changes (promotion)

⚠️ IMPORTANT: Import this in api/signals.py to register
"""

import logging
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Employee
from .celebration_notification_service import celebration_notification_service

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Employee)
def track_job_title_change(sender, instance, **kwargs):
    """
    📝 Track job_title changes before saving
    Stores old job title in instance for comparison
    """
    if instance.pk:  # Only for existing employees
        try:
            old_employee = Employee.objects.get(pk=instance.pk)
            instance._old_job_title = old_employee.job_title
        except Employee.DoesNotExist:
            instance._old_job_title = None
    else:
        instance._old_job_title = None


@receiver(post_save, sender=Employee)
def send_promotion_notification(sender, instance, created, **kwargs):
    """
    📧 Send celebration email when job_title changes
    AND create a Celebration record for it
    
    Automatically detects job title changes as promotions
    """
    if created:
        # New employee - no notification needed
        return
    
    # Check if job_title changed
    old_title = getattr(instance, '_old_job_title', None)
    new_title = instance.job_title
    
    if old_title and new_title and old_title != new_title:
        logger.info(f"🔔 Job title change detected for {instance.first_name} {instance.last_name}")
        logger.info(f"   Old: {old_title} → New: {new_title}")
        
        # ✅ Create Celebration record for promotion
        from .celebration_models import Celebration
        from datetime import date
        from django.contrib.auth.models import User
        
        try:
            # Get system user or first admin user
            system_user = User.objects.filter(is_superuser=True).first()
            if not system_user:
                system_user = User.objects.first()
            
            # Create promotion celebration
            celebration = Celebration.objects.create(
                type='promotion',
                title=f"Promotion - {instance.first_name} {instance.last_name}",
                date=date.today(),
                message=f"Congratulations to {instance.first_name} {instance.last_name} on their promotion to {new_title}!",
                employee=instance,
                new_job_title=str(new_title),
                created_by=system_user
            )
            logger.info(f"✅ Promotion celebration created with ID: {celebration.id}")
        except Exception as e:
            logger.error(f"❌ Failed to create promotion celebration: {e}")
        
        # Send notification email
        try:
            celebration_notification_service.send_promotion_notification(
                employee=instance,
                new_job_title=str(new_title)
            )
            logger.info(f"✅ Promotion notification sent for {instance.first_name}")
        except Exception as e:
            logger.error(f"❌ Failed to send promotion notification: {e}")


# Optional: Add signal for new employees
@receiver(post_save, sender=Employee)
def welcome_new_employee(sender, instance, created, **kwargs):
    """
    👋 Optional: Send welcome email to new employees
    """
    if created and not instance.is_deleted:
        logger.info(f"👋 New employee created: {instance.first_name} {instance.last_name}")
        # You can add welcome email logic here if needed