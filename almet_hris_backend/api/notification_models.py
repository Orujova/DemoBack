# api/notification_models.py
"""
Notification System Models
- NotificationSettings: System-wide notification configuration
- EmailTemplate: Reusable email templates for different notification types
- NotificationLog: Log of all sent notifications with status tracking
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class NotificationSettings(models.Model):
    """
    Global notification system settings
    Only one active instance should exist at a time
    """
    
    # Notification preferences
    enable_email_notifications = models.BooleanField(
        default=True,
        help_text="Master switch to enable/disable all email notifications"
    )
    email_retry_attempts = models.IntegerField(
        default=3,
        help_text="Number of retry attempts for failed email deliveries"
    )
    email_retry_delay_minutes = models.IntegerField(
        default=5,
        help_text="Delay in minutes between retry attempts"
    )
    timeoff_subject_prefix = models.CharField(
        max_length=50, 
        default='[TIME OFF]',
        help_text="Subject prefix for time off emails"
    )
    # Business Trip specific settings
    business_trip_subject_prefix = models.CharField(
        max_length=50, 
        default='[BUSINESS TRIP]',
        help_text="Subject prefix for business trip emails"
    )
    
    # Vacation specific settings
    vacation_subject_prefix = models.CharField(
        max_length=50, 
        default='[VACATION]',
        help_text="Subject prefix for vacation emails"
    )
    
    # ✅ NEW: Company News specific settings
    company_news_subject_prefix = models.CharField(
        max_length=50, 
        default='[COMPANY NEWS]',
        help_text="Subject prefix for company news emails"
    )
    company_news_sender_email = models.EmailField(
        default='myalmet@almettrading.com',
        help_text="Email address for sending company news (must be valid Outlook/Exchange mailbox)"
    )
    handover_subject_prefix = models.CharField(
        max_length=50, 
        default='[HANDOVER]',
        help_text="Subject prefix for handover emails"
    )
    handover_sender_email = models.EmailField(
        default='myalmet@almettrading.com',
        help_text="Email address for sending handover notifications"
    )
    # System fields
    is_active = models.BooleanField(
        default=True,
        help_text="Only one settings record should be active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        related_name='notification_settings_created'
    )
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        related_name='notification_settings_updated'
    )
    
    class Meta:
        db_table = 'notification_settings'
        verbose_name = 'Notification Settings'
        verbose_name_plural = 'Notification Settings'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Notification Settings"
    
    @classmethod
    def get_active(cls):
        """Get or create active notification settings"""
        settings, created = cls.objects.get_or_create(
            is_active=True,
            defaults={
                'enable_email_notifications': True,
                'email_retry_attempts': 3,
                'email_retry_delay_minutes': 5,
                'business_trip_subject_prefix': '[BUSINESS TRIP]',
                'vacation_subject_prefix': '[VACATION]',
                'company_news_subject_prefix': '[COMPANY NEWS]',  # ✅ NEW
                'company_news_sender_email': 'myalmet@almettrading.com',  # ✅ NEW
                'handover_subject_prefix': '[HANDOVER]',  # ⭐ NEW
                'handover_sender_email': 'myalmet@almettrading.com',  # ⭐ NEW
            }
        )
        return settings
    
    def save(self, *args, **kwargs):
        """Ensure only one active settings record exists"""
        if self.is_active:
            NotificationSettings.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

class NotificationLog(models.Model):
    """
    Log of all sent notifications with delivery status tracking
    Used for monitoring, debugging, and audit trail
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent Successfully'),
        ('FAILED', 'Failed'),
        ('RETRY', 'Retry Scheduled'),
    ]
    
    NOTIFICATION_TYPES = [
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
        ('PUSH', 'Push Notification'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Notification type and recipient
    notification_type = models.CharField(
        max_length=20, 
        choices=NOTIFICATION_TYPES, 
        default='EMAIL',
        db_index=True
    )
    recipient_email = models.EmailField(
        db_index=True,
        help_text="Recipient's email address"
    )
    recipient_name = models.CharField(
        max_length=255, 
        blank=True,
        help_text="Recipient's display name"
    )
    
    # Email content (stored for audit trail)
    subject = models.CharField(
        max_length=500,
        help_text="Email subject line"
    )
    body = models.TextField(
        help_text="Email body (HTML or plain text)"
    )
    
    # Related object tracking (optional)
    related_model = models.CharField(
        max_length=100, 
        blank=True,
        db_index=True,
        help_text="Related model name (e.g., 'BusinessTripRequest', 'VacationRequest')"
    )
    related_object_id = models.CharField(
        max_length=100, 
        blank=True,
        db_index=True,
        help_text="Related object ID for tracking"
    )
    
    # Delivery status
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='PENDING',
        db_index=True
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if delivery failed"
    )
    retry_count = models.IntegerField(
        default=0,
        help_text="Number of delivery retry attempts"
    )
    
    # Microsoft Graph API response
    message_id = models.CharField(
        max_length=255, 
        blank=True,
        help_text="Microsoft Graph message ID (for tracking in Exchange)"
    )
    sent_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Timestamp when email was successfully sent"
    )
    
    # System fields
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the notification was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last update timestamp"
    )
    sent_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        related_name='notifications_sent',
        help_text="User who triggered this notification"
    )
    
    class Meta:
        db_table = 'notification_logs'
        verbose_name = 'Notification Log'
        verbose_name_plural = 'Notification Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['recipient_email', '-created_at']),
            models.Index(fields=['related_model', 'related_object_id']),
            models.Index(fields=['notification_type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.notification_type} to {self.recipient_email} - {self.status}"
    
    def mark_as_sent(self, message_id=None):
        """
        Mark notification as successfully sent
        
        Args:
            message_id (str, optional): Microsoft Graph message ID
        """
        self.status = 'SENT'
        self.sent_at = timezone.now()
        if message_id:
            self.message_id = message_id
        self.save(update_fields=['status', 'sent_at', 'message_id', 'updated_at'])
    
    def mark_as_failed(self, error_message):
        """
        Mark notification as failed
        
        Args:
            error_message (str): Error description
        """
        self.status = 'FAILED'
        self.error_message = error_message
        self.retry_count += 1
        self.save(update_fields=['status', 'error_message', 'retry_count', 'updated_at'])
    
    def schedule_retry(self):
        """
        Schedule notification for retry
        """
        settings = NotificationSettings.get_active()
        
        if self.retry_count < settings.email_retry_attempts:
            self.status = 'RETRY'
            self.retry_count += 1
            self.save(update_fields=['status', 'retry_count', 'updated_at'])
            return True
        else:
            self.mark_as_failed(f"Max retry attempts ({settings.email_retry_attempts}) exceeded")
            return False
    
    @property
    def is_successful(self):
        """Check if notification was successfully delivered"""
        return self.status == 'SENT'
    
    @property
    def is_pending(self):
        """Check if notification is pending delivery"""
        return self.status in ['PENDING', 'RETRY']
    
    @classmethod
    def get_business_trip_notifications(cls, request_id=None):
        """
        Get all Business Trip related notifications
        
        Args:
            request_id (str, optional): Filter by specific request ID
        
        Returns:
            QuerySet: Filtered notification logs
        """
        qs = cls.objects.filter(related_model='BusinessTripRequest')
        
        if request_id:
            qs = qs.filter(related_object_id=request_id)
        
        return qs.order_by('-created_at')
    
    @classmethod
    def get_failed_notifications(cls, days=7):
        """
        Get failed notifications from the last N days
        
        Args:
            days (int): Number of days to look back
        
        Returns:
            QuerySet: Failed notification logs
        """
        from datetime import timedelta
        date_from = timezone.now() - timedelta(days=days)
        
        return cls.objects.filter(
            status='FAILED',
            created_at__gte=date_from
        ).order_by('-created_at')
    
    @classmethod
    def get_vacation_notifications(cls, request_id=None):
        """
        Get all Vacation related notifications
        
        Args:
            request_id (str, optional): Filter by specific request ID
        
        Returns:
            QuerySet: Filtered notification logs
        """
        qs = cls.objects.filter(related_model='VacationRequest')
        
        if request_id:
            qs = qs.filter(related_object_id=request_id)
        
        return qs.order_by('-created_at')
    
    @classmethod
    def get_statistics_by_module(cls, days=30):
        """
        Get notification statistics grouped by module (Business Trip vs Vacation)
        
        Args:
            days (int): Number of days to analyze
        
        Returns:
            dict: Statistics by module
        """
        from django.db.models import Count, Q
        from datetime import timedelta
        
        date_from = timezone.now() - timedelta(days=days)
        
        qs = cls.objects.filter(created_at__gte=date_from)
        
        stats = {
            'business_trip': qs.filter(related_model='BusinessTripRequest').aggregate(
                total=Count('id'),
                sent=Count('id', filter=Q(status='SENT')),
                failed=Count('id', filter=Q(status='FAILED'))
            ),
            'vacation': qs.filter(related_model='VacationRequest').aggregate(
                total=Count('id'),
                sent=Count('id', filter=Q(status='SENT')),
                failed=Count('id', filter=Q(status='FAILED'))
            )
        }
        
        return stats

    
    @classmethod
    def get_statistics(cls, days=30):
        """
        Get notification statistics for the last N days
        
        Args:
            days (int): Number of days to analyze
        
        Returns:
            dict: Statistics summary
        """
        from django.db.models import Count, Q
        from datetime import timedelta
        
        date_from = timezone.now() - timedelta(days=days)
        
        qs = cls.objects.filter(created_at__gte=date_from)
        
        stats = qs.aggregate(
            total=Count('id'),
            sent=Count('id', filter=Q(status='SENT')),
            failed=Count('id', filter=Q(status='FAILED')),
            pending=Count('id', filter=Q(status='PENDING')),
            retry=Count('id', filter=Q(status='RETRY'))
        )
        
        # Calculate success rate
        if stats['total'] > 0:
            stats['success_rate'] = round((stats['sent'] / stats['total']) * 100, 2)
        else:
            stats['success_rate'] = 0
        
        return stats