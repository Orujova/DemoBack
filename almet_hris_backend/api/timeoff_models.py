# api/timeoff_models.py
"""
Time Off System Models
- Aylıq 4 saat icazə sistemi
- Line manager approval
- HR notification
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import logging

logger = logging.getLogger(__name__)


class TimeOffBalance(models.Model):
    """
    Employee-lərin aylıq time off balansı
    Hər ay avtomatik 4 saat əlavə olunur
    """
    employee = models.OneToOneField(
        'Employee',
        on_delete=models.CASCADE,
        related_name='timeoff_balance'
    )
    
    # Balance məlumatları
    monthly_allowance_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=4.0,
        help_text="Aylıq icazə saatı (default: 4 saat)"
    )
    current_balance_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0.0,
        help_text="Cari balans (saat)"
    )
    used_hours_this_month = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.0,
        help_text="Bu ay istifadə olunan saat"
    )
    
    # Last reset tracking
    last_reset_date = models.DateField(
        default=timezone.now,
        help_text="Son reset tarixi"
    )
    
    # Track if balance was initialized
    is_initialized = models.BooleanField(
        default=False,
        help_text="Balance initialized by admin?"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'timeoff_balances'
        verbose_name = 'Time Off Balance'
        verbose_name_plural = 'Time Off Balances'
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.current_balance_hours}h available"
    
    def check_and_reset_monthly(self):
        """
        ✅ FIXED: Aylıq reset yoxla və tətbiq et
        - Yalnız initialized balances üçün işləyir
        - HƏR AY yeni monthly_allowance əlavə edir (istifadə etməsə də)
        - used_hours_this_month 0-a çevrilir
        """
        if not self.is_initialized:
          
            return False
        
        today = timezone.now().date()
        
        # Əgər yeni ay başlayıbsa
        if today.month != self.last_reset_date.month or today.year != self.last_reset_date.year:
            # Yeni ay üçün monthly_allowance əlavə et (istifadə etməsə də)
            old_balance = self.current_balance_hours
            self.current_balance_hours += self.monthly_allowance_hours
            self.used_hours_this_month = Decimal('0.0')
            self.last_reset_date = today
            self.save()
            
            logger.info(
                f"✅ Monthly reset: {self.employee.full_name} - "
                f"Added {self.monthly_allowance_hours}h, "
                f"{old_balance}h → {self.current_balance_hours}h"
            )
            return True
        
        return False
    
    def has_sufficient_balance(self, hours_requested):
        """Kifayət qədər balans var?"""
        return self.current_balance_hours >= Decimal(str(hours_requested))
    
    def deduct_hours(self, hours):
        """Saatları balansdan çıxart"""
        if not self.has_sufficient_balance(hours):
            raise ValueError(
                f"Insufficient balance. Available: {self.current_balance_hours}h, "
                f"Requested: {hours}h"
            )
        
        self.current_balance_hours -= Decimal(str(hours))
        self.used_hours_this_month += Decimal(str(hours))
        self.save()
        
        logger.info(
            f"💰 Deducted {hours}h from {self.employee.full_name} - "
            f"New balance: {self.current_balance_hours}h"
        )
    
    def refund_hours(self, hours):
        """Saatları geri qaytar (məsələn, reject zamanı)"""
        self.current_balance_hours += Decimal(str(hours))
        # Used hours-dan da çıxart
        self.used_hours_this_month = max(
            Decimal('0.0'), 
            self.used_hours_this_month - Decimal(str(hours))
        )
        self.save()
        
        logger.info(
            f"💵 Refunded {hours}h to {self.employee.full_name} - "
            f"New balance: {self.current_balance_hours}h"
        )
    
    @classmethod
    def get_or_create_for_employee(cls, employee):
        """
        Employee üçün balance yarat və ya tap
        Artıq avtomatik 4 saat vermir
        """
        balance, created = cls.objects.get_or_create(
            employee=employee,
            defaults={
                'monthly_allowance_hours': Decimal('4.0'),
                'current_balance_hours': Decimal('4.0'),
                'used_hours_this_month': Decimal('0.0'),
                'last_reset_date': timezone.now().date(),
                'is_initialized': False
            }
        )
        
        if created:
            logger.info(
                f"📝 Created time off balance for {employee.full_name} "
                f"with 0h (not initialized)"
            )
        else:
            # Monthly reset yoxla (yalnız initialized olanlar üçün)
            balance.check_and_reset_monthly()
        
        return balance


class TimeOffRequest(models.Model):
    """
    Time Off Request Model
    Employee-lər icazə sorğusu yaradır
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Line Manager Approval'),
        ('APPROVED', 'Approved by Line Manager'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled by Employee'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Request məlumatları
    employee = models.ForeignKey(
        'Employee',
        on_delete=models.CASCADE,
        related_name='timeoff_requests'
    )
    
    # Tarix və saat məlumatları
    date = models.DateField(
        help_text="İcazə tarixi"
    )
    start_time = models.TimeField(
        help_text="Başlama saatı"
    )
    end_time = models.TimeField(
        help_text="Bitmə saatı"
    )
    duration_hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        validators=[MinValueValidator(0.5), MaxValueValidator(8)],
        help_text="Müddət (saat)"
    )
    
    # Səbəb
    reason = models.TextField(
        help_text="İcazə səbəbi"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )
    
    # Approval məlumatları
    line_manager = models.ForeignKey(
        'Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='timeoff_requests_to_approve'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_timeoff_requests'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Balance tracking
    balance_deducted = models.BooleanField(
        default=False,
        help_text="Balansdan çıxarılıb?"
    )
    
    # HR notification
    hr_notified = models.BooleanField(
        default=False,
        help_text="HR-lara bildiriş göndərilib?"
    )
    hr_notified_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_timeoff_requests'
    )
    
    class Meta:
        db_table = 'timeoff_requests'
        verbose_name = 'Time Off Request'
        verbose_name_plural = 'Time Off Requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['employee', 'status']),
            models.Index(fields=['date']),
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self):
        return (
            f"{self.employee.full_name} - {self.date} "
            f"({self.duration_hours}h) - {self.status}"
        )
    
    def save(self, *args, **kwargs):
        # Duration hesabla
        if self.start_time and self.end_time:
            start_datetime = datetime.combine(datetime.today(), self.start_time)
            end_datetime = datetime.combine(datetime.today(), self.end_time)
            
            if end_datetime < start_datetime:
                end_datetime += timedelta(days=1)
            
            duration = (end_datetime - start_datetime).total_seconds() / 3600
            self.duration_hours = Decimal(str(round(duration, 2)))
        
        # Line manager təyin et
        if not self.line_manager and self.employee.line_manager:
            self.line_manager = self.employee.line_manager
        
        super().save(*args, **kwargs)
    
    def approve(self, approved_by_user):
        """Line manager tərəfindən approve"""
        if self.status != 'PENDING':
            raise ValueError(f"Cannot approve request with status: {self.status}")
        
        # Balance-dən çıxart
        balance = TimeOffBalance.get_or_create_for_employee(self.employee)
        
        if not balance.has_sufficient_balance(self.duration_hours):
            raise ValueError(
                f"Insufficient balance. Available: {balance.current_balance_hours}h"
            )
        
        balance.deduct_hours(self.duration_hours)
        
        self.status = 'APPROVED'
        self.approved_by = approved_by_user
        self.approved_at = timezone.now()
        self.balance_deducted = True
        self.save()
        
        # HR-lara bildiriş göndər
        self.notify_hr()
    
    def reject(self, rejection_reason, rejected_by_user):
        """Line manager tərəfindən reject"""
        if self.status != 'PENDING':
            raise ValueError(f"Cannot reject request with status: {self.status}")
        
        self.status = 'REJECTED'
        self.rejection_reason = rejection_reason
        self.approved_by = rejected_by_user
        self.approved_at = timezone.now()
        self.save()
    
    def cancel(self):
        """Employee tərəfindən cancel"""
        if self.status == 'APPROVED' and self.balance_deducted:
            # Balance-ə geri qaytar
            balance = TimeOffBalance.get_or_create_for_employee(self.employee)
            balance.refund_hours(self.duration_hours)
            self.balance_deducted = False
        
        self.status = 'CANCELLED'
        self.save()
    
    def notify_hr(self):
        """HR-lara bildiriş göndər"""
        self.hr_notified = True
        self.hr_notified_at = timezone.now()
        self.save()
    
    @classmethod
    def get_pending_for_manager(cls, manager_employee):
        """Manager üçün pending request-lər"""
        return cls.objects.filter(
            line_manager=manager_employee,
            status='PENDING'
        ).select_related('employee', 'employee__user')
    
    @classmethod
    def get_employee_requests(cls, employee, year=None, month=None):
        """Employee-in request-ləri"""
        requests = cls.objects.filter(employee=employee)
        
        if year:
            requests = requests.filter(date__year=year)
        if month:
            requests = requests.filter(date__month=month)
        
        return requests.order_by('-date')


class TimeOffSettings(models.Model):
    """
    Time Off System Settings
    """
    
    # Monthly allowance
    default_monthly_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=4.0,
        help_text="Default aylıq icazə saatı"
    )
    
    # Maximum request hours
    max_request_hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=8.0,
        help_text="Bir request-də maksimum saat"
    )
    
    # Advance booking
    min_advance_hours = models.IntegerField(
        default=24,
        help_text="Neçə saat əvvəldən sorğu göndərmək lazımdır"
    )
    
    # HR notification emails
    hr_notification_emails = models.TextField(
        default='hr@almettrading.com',
        help_text="HR email-ləri (vergüllə ayrılmış)"
    )
    
    # Auto-approval settings
    enable_auto_approval = models.BooleanField(
        default=False,
        help_text="Avtomatik approve (testing üçün)"
    )
    
    # System status
    is_active = models.BooleanField(
        default=True,
        help_text="Sistem aktiv?"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'timeoff_settings'
        verbose_name = 'Time Off Settings'
        verbose_name_plural = 'Time Off Settings'
    
    def __str__(self):
        return f"Time Off Settings - {self.default_monthly_hours}h/month"
    
    @classmethod
    def get_settings(cls):
        """Get or create settings"""
        settings, created = cls.objects.get_or_create(
            id=1,
            defaults={
                'default_monthly_hours': Decimal('4.0'),
                'max_request_hours': Decimal('8.0'),
                'min_advance_hours': 24,
                'hr_notification_emails': 'hr@almettrading.com',
                'enable_auto_approval': False,
                'is_active': True
            }
        )
        return settings
    
    def get_hr_emails_list(self):
        """HR email-lərini list kimi qaytar"""
        return [
            email.strip() 
            for email in self.hr_notification_emails.split(',') 
            if email.strip()
        ]


class TimeOffActivity(models.Model):
    """
    Time Off request activity log
    """
    
    ACTIVITY_TYPES = [
        ('CREATED', 'Request Created'),
        ('APPROVED', 'Approved by Manager'),
        ('REJECTED', 'Rejected by Manager'),
        ('CANCELLED', 'Cancelled by Employee'),
        ('HR_NOTIFIED', 'HR Notified'),
        ('BALANCE_UPDATED', 'Balance Updated'),
    ]
    
    request = models.ForeignKey(
        TimeOffRequest,
        on_delete=models.CASCADE,
        related_name='activities',
        null=True,
        blank=True
    )
    
    activity_type = models.CharField(
        max_length=20,
        choices=ACTIVITY_TYPES
    )
    description = models.TextField()
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'timeoff_activities'
        verbose_name = 'Time Off Activity'
        verbose_name_plural = 'Time Off Activities'
        ordering = ['-created_at']
    
    def __str__(self):
        if self.request:
            return f"{self.request.employee.full_name} - {self.activity_type}"
        return f"System - {self.activity_type}"