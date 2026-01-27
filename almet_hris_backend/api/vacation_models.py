# api/vacation_models.py - Enhanced and Fixed

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from .models import Employee, SoftDeleteModel
import uuid

class VacationSetting(SoftDeleteModel):
    """Vacation sistem parametrləri - DUAL CALENDAR SUPPORT"""
    
    # ✅ DUAL PRODUCTION CALENDAR
    non_working_days_az = models.JSONField(
        default=list, 
        help_text="Azerbaijan qeyri-iş günləri JSON formatında"
    )
    non_working_days_uk = models.JSONField(
        default=list,
        help_text="UK qeyri-iş günləri JSON formatında"
    )
    
    # Default HR
    default_hr_representative = models.ForeignKey(
        Employee, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='hr_settings',
        help_text="Default HR nümayəndəsi"
    )
    
    # ✅ UK SPECIFIC: Additional approver for 5+ day requests
    uk_additional_approver = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uk_additional_approvals',
        help_text="UK: 5+ günlük requestlər üçün əlavə approver (Position Group: Vice Chairman)"
    )
    
    # Settings
    allow_negative_balance = models.BooleanField(
        default=False, 
        help_text="Balans 0 olduqda request yaratmağa icazə ver"
    )
    max_schedule_edits = models.PositiveIntegerField(
        default=3, 
        help_text="Schedule neçə dəfə edit oluna bilər"
    )
    
    # Notifications
    notification_days_before = models.PositiveIntegerField(
        default=7,
        help_text="Məzuniyyət başlamazdan neçə gün əvvəl bildiriş göndər"
    )
    notification_frequency = models.PositiveIntegerField(
        default=2,
        help_text="Bildirişi neçə dəfə göndər"
    )
    
    # System fields
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='vacation_settings_updates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Vacation Setting"
        verbose_name_plural = "Vacation Settings"
        db_table = 'vacation_settings'
    
    def __str__(self):
        return f"Vacation Settings - Active: {self.is_active}"
    
    @classmethod
    def get_active(cls):
        """Aktiv settingi qaytarır"""
        return cls.objects.filter(is_active=True, is_deleted=False).first()
    
    def clean(self):
        """Validation - yalnız bir aktiv setting ola bilər"""
        if self.is_active:
            existing = VacationSetting.objects.filter(
                is_active=True, 
                is_deleted=False
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError("Yalnız bir aktiv vacation setting ola bilər")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def is_working_day(self, check_date, business_function_code=None):
        """
        ✅ ENHANCED: Verilən tarixi iş günü olub-olmadığını yoxlayır
        
        Azerbaijan: Həftəsonu günləri də iş günü sayılır, yalnız non_working_days istisna
        UK: Həftəsonu (Saturday, Sunday) VƏ holidays istisna edilir
        
        Args:
            check_date: yoxlanılacaq tarix
            business_function_code: 'UK' və ya digər
        """
        date_str = check_date.strftime('%Y-%m-%d')
        
        # ✅ UK LOGIC
        if business_function_code and business_function_code.upper() == 'UK':
            # Check weekends
            if check_date.weekday() in [5, 6]:  # Saturday=5, Sunday=6
                return False
            
            # Check UK holidays
            for holiday in self.non_working_days_uk:
                if isinstance(holiday, dict) and holiday.get('date') == date_str:
                    return False
                elif isinstance(holiday, str) and holiday == date_str:
                    return False
            
            return True
        
        # ✅ AZERBAIJAN LOGIC (default)
        else:
            # Check AZ holidays only (weekends are working days)
            for holiday in self.non_working_days_az:
                if isinstance(holiday, dict) and holiday.get('date') == date_str:
                    return False
                elif isinstance(holiday, str) and holiday == date_str:
                    return False
            
            return True
    
    def calculate_working_days(self, start, end, business_function_code=None):
        """
        ✅ ENHANCED: İki tarix arasındakı iş günlərinin sayını hesablayır
        
        Args:
            start: başlanğıc tarix
            end: bitmə tarixi
            business_function_code: 'UK' və ya digər
        """
        if start > end:
            return 0
            
        days = 0
        current = start
        while current <= end:
            if self.is_working_day(current, business_function_code):
                days += 1
            current += timedelta(days=1)
        return days
    
    def calculate_return_date(self, end_date, business_function_code=None):
        """
        ✅ ENHANCED: Məzuniyyət bitdikdən sonra ilk iş gününü hesablayır
        
        Args:
            end_date: məzuniyyət bitmə tarixi
            business_function_code: 'UK' və ya digər
        """
        ret = end_date + timedelta(days=1)
        while not self.is_working_day(ret, business_function_code):
            ret += timedelta(days=1)
        return ret


class VacationType(SoftDeleteModel):
    """✅ ENHANCED: Məzuniyyət növləri - UK-specific types dəstəyi"""
    
    name = models.CharField(max_length=100, unique=True, help_text="Məzuniyyət növü adı")
    description = models.TextField(blank=True, help_text="Təsvir")
    
    # ✅ UK SPECIFIC
    is_uk_only = models.BooleanField(
        default=False,
        help_text="Yalnız UK business function üçün görünən tip (məs: Half Day)"
    )
    requires_time_selection = models.BooleanField(
        default=False,
        help_text="Saat seçimi tələb edir (Half Day üçün)"
    )
    
    # System fields
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='vacation_type_updates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Vacation Type"
        verbose_name_plural = "Vacation Types"
        db_table = 'vacation_types'
        ordering = ['name']
    
    def __str__(self):
        return self.name



class EmployeeVacationBalance(SoftDeleteModel):
    """İşçinin illik vacation balansı"""
    
    employee = models.ForeignKey(
        Employee, 
        on_delete=models.CASCADE, 
        related_name='vacation_balances'
    )
    year = models.PositiveIntegerField(help_text="İl (məsələn: 2025)")
    
    # Balance fields
    start_balance = models.DecimalField(
        max_digits=5, 
        decimal_places=1, 
        default=0,
        help_text="Əvvəlki ildən qalan balans"
    )
    yearly_balance = models.DecimalField(
        max_digits=5, 
        decimal_places=1, 
        default=0,
        help_text="İllik məzuniyyət balansı"
    )
    used_days = models.DecimalField(
        max_digits=5, 
        decimal_places=1, 
        default=0,
        help_text="İstifadə edilmiş günlər"
    )
    scheduled_days = models.DecimalField(
        max_digits=5, 
        decimal_places=1, 
        default=0,
        help_text="Planlaşdırılmış günlər"
    )
    
    # System fields
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Employee Vacation Balance"
        verbose_name_plural = "Employee Vacation Balances"
        unique_together = ['employee', 'year']
        db_table = 'employee_vacation_balances'
        ordering = ['-year', 'employee__full_name']
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.year} - Balance: {self.total_balance}"
    
    @property
    def total_balance(self):
        """Ümumi balans"""
        return float(self.start_balance) + float(self.yearly_balance)
    
    @property
    def remaining_balance(self):
        """✅ FIXED: Qalan balans - yalnız used_days çıxılır"""
        total = self.total_balance
        used = float(self.used_days)
        return total - used  # scheduled_days artıq çıxılmır
    
    @property
    def available_for_planning(self):
        """✅ NEW: Planlaşdırma üçün mövcud balans"""
        return self.remaining_balance - float(self.scheduled_days)
    
    
    @property
    def should_be_planned(self):
        """✅ CRITICAL: Yalnız yearly_balance əsasında planlaşdırılmalı"""
        planned_and_used = float(self.scheduled_days) + float(self.used_days)
        remaining_from_yearly = max(0, float(self.yearly_balance) - planned_and_used)
        return remaining_from_yearly
    
    
    def clean(self):
        """Validation"""
        if self.year < 2020 or self.year > 2030:
            raise ValidationError("İl 2020-2030 aralığında olmalıdır")


class VacationRequest(SoftDeleteModel):
    """✅ ENHANCED: Vacation Request - UK approval chain support"""
    
    REQUEST_TYPE_CHOICES = [
        ('IMMEDIATE', 'Immediate'),
        ('SCHEDULING', 'Scheduling'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('IN_PROGRESS', 'In Progress'),
        ('PENDING_LINE_MANAGER', 'Pending Line Manager'),
        ('PENDING_UK_ADDITIONAL', 'Pending UK Additional Approver'),  # ✅ NEW
        ('PENDING_HR', 'Pending HR'),
        ('APPROVED', 'Approved'),
        ('REJECTED_LINE_MANAGER', 'Rejected by Line Manager'),
        ('REJECTED_UK_ADDITIONAL', 'Rejected by UK Additional Approver'),  # ✅ NEW
        ('REJECTED_HR', 'Rejected by HR'),
    ]
    
    # Request identification
    request_id = models.CharField(max_length=50, unique=True, editable=False)
    
    # Employee and requester
    employee = models.ForeignKey(
        Employee, 
        on_delete=models.CASCADE, 
        related_name='vacation_requests'
    )
    requester = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='created_vacation_requests'
    )
    
    # Request details
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES, default='IMMEDIATE')
    vacation_type = models.ForeignKey(VacationType, on_delete=models.PROTECT)
    
    # Dates
    start_date = models.DateField()
    end_date = models.DateField()
    return_date = models.DateField(editable=False, null=True, blank=True)
    number_of_days = models.DecimalField(max_digits=5, decimal_places=1, editable=False, default=0)
    comment = models.TextField(blank=True, help_text="İşçinin şərhi")
    
    # ✅ HALF DAY SUPPORT
    is_half_day = models.BooleanField(default=False, help_text="Half day request-dirsə True")
    half_day_start_time = models.TimeField(null=True, blank=True, help_text="Half day başlama saatı")
    half_day_end_time = models.TimeField(null=True, blank=True, help_text="Half day bitmə saatı")
    
    # Approvers
    line_manager = models.ForeignKey(
        Employee, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='requests_to_approve'
    )
    
    # ✅ UK ADDITIONAL APPROVER
    uk_additional_approver = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uk_additional_requests',
        help_text="UK: 5+ günlük requestlər üçün əlavə approver"
    )
    
    hr_representative = models.ForeignKey(
        Employee, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='requests_hr'
    )
    
    # Status
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='DRAFT')
    
    # Line Manager Approval
    line_manager_approved_at = models.DateTimeField(null=True, blank=True)
    line_manager_approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='lm_approvals'
    )
    line_manager_comment = models.TextField(blank=True)
    
    # ✅ UK ADDITIONAL APPROVER
    uk_additional_approved_at = models.DateTimeField(null=True, blank=True)
    uk_additional_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uk_additional_approvals'
    )
    uk_additional_comment = models.TextField(blank=True)
    
    # HR Approval
    hr_approved_at = models.DateTimeField(null=True, blank=True)
    hr_approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='hr_approvals'
    )
    hr_comment = models.TextField(blank=True)
    
    # Rejection
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='rejections'
    )
    rejection_reason = models.TextField(blank=True)
    
    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Vacation Request"
        verbose_name_plural = "Vacation Requests"
        db_table = 'vacation_requests'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.request_id} - {self.employee.full_name} - {self.vacation_type.name}"
    
    def get_business_function_code(self):
        """Employee-in business function kodunu qaytarır"""
        if self.employee.business_function:
            return getattr(self.employee.business_function, 'code', None)
        return None
    
    def is_uk_employee(self):
        """✅ UK employee-dirsə True"""
        code = self.get_business_function_code()
        return code and code.upper() == 'UK'
    
    def requires_uk_additional_approval(self):
        """✅ UK əlavə approval tələb edirmi?"""
        if not self.is_uk_employee():
            return False
        
        # 5+ günlük requestlər üçün
        if self.number_of_days >= 5:
            return True
        
        return False
    
    def clean(self):
        """Validation"""
        # Half day validation
        if self.is_half_day:
            if not self.half_day_start_time or not self.half_day_end_time:
                raise ValidationError("Half day üçün start və end time mütləqdir")
            
            if self.half_day_start_time >= self.half_day_end_time:
                raise ValidationError("Start time end time-dan kiçik olmalıdır")
            
            # Half day - start və end date eyni olmalıdır
            if self.start_date != self.end_date:
                raise ValidationError("Half day üçün start və end date eyni olmalıdır")
        
        else:
            # Normal vacation - end date > start date
            if self.start_date and self.end_date and self.start_date >= self.end_date:
                raise ValidationError("End date start date-dən böyük olmalıdır")
        
        # Kəsişmə yoxla
        has_conflict, conflicts = self.check_date_conflicts()
        if has_conflict:
            conflict_details = ", ".join([
                f"{c['id']} ({c['start_date']} - {c['end_date']})" 
                for c in conflicts
            ])
            raise ValidationError(
                f"Bu tarixlərdə artıq vacation var: {conflict_details}"
            )
    
    def save(self, *args, **kwargs):
        # Generate request ID
        if not self.request_id:
            year = timezone.now().year
            last = VacationRequest.objects.filter(
                request_id__startswith=f'VR{year}'
            ).order_by('-request_id').first()
            num = int(last.request_id[6:]) + 1 if last else 1
            self.request_id = f'VR{year}{num:04d}'
        
        # Calculate working days and return date
        settings = VacationSetting.get_active()
        if settings and self.start_date and self.end_date:
            bf_code = self.get_business_function_code()
            
            if self.is_half_day:
                # Half day = 0.5 gün
                self.number_of_days = 0.5
                self.return_date = self.end_date + timedelta(days=1)
            else:
                # Normal calculation
                self.number_of_days = settings.calculate_working_days(
                    self.start_date, 
                    self.end_date,
                    bf_code
                )
                self.return_date = settings.calculate_return_date(self.end_date, bf_code)
        
        # Auto-assign approvers
        if not self.line_manager and self.employee.line_manager:
            requester_emp = getattr(self.requester, 'employee', None)
            if not (requester_emp and self.employee.line_manager == requester_emp):
                self.line_manager = self.employee.line_manager
        
        # ✅ UK ADDITIONAL APPROVER
        if self.requires_uk_additional_approval():
            if settings and settings.uk_additional_approver:
                # Yalnız əgər approver employee-in özü deyilsə
                if self.employee != settings.uk_additional_approver:
                    self.uk_additional_approver = settings.uk_additional_approver
        
        if not self.hr_representative and settings:
            self.hr_representative = settings.default_hr_representative
        
        self.clean()
        super().save(*args, **kwargs)
    
    def submit_request(self, user):
        """✅ ENHANCED: Submit for approval - UK chain dəstəyi"""
        requester_emp = getattr(user, 'employee', None)
        is_manager_request = requester_emp and self.employee.line_manager == requester_emp
        
        if is_manager_request:
            # Manager öz işçisi üçün request edir
            if self.requires_uk_additional_approval():
                self.status = 'PENDING_UK_ADDITIONAL'
            elif self.hr_representative:
                self.status = 'PENDING_HR'
            else:
                self.status = 'APPROVED'
        else:
            # Normal işçi request edir - Line Manager-ə göndər
            if self.line_manager:
                self.status = 'PENDING_LINE_MANAGER'
            elif self.requires_uk_additional_approval():
                self.status = 'PENDING_UK_ADDITIONAL'
            elif self.hr_representative:
                self.status = 'PENDING_HR'
            else:
                self.status = 'APPROVED'
        
        self.save()
    

    def reject_by_line_manager(self, user, reason):
        """Line Manager reject edir"""
        self.status = 'REJECTED_LINE_MANAGER'
        self.rejected_at = timezone.now()
        self.rejected_by = user
        self.rejection_reason = reason
        self.save()
    

    def reject_by_uk_additional(self, user, reason):
        """✅ NEW: UK Additional Approver reject edir"""
        self.status = 'REJECTED_UK_ADDITIONAL'
        self.rejected_at = timezone.now()
        self.rejected_by = user
        self.rejection_reason = reason
        self.save()
    

    def reject_by_hr(self, user, reason):
        """HR reject edir"""
        self.status = 'REJECTED_HR'
        self.rejected_at = timezone.now()
        self.rejected_by = user
        self.rejection_reason = reason
        self.save()


    def approve_by_line_manager(self, user, comment=''):
        """✅ ENHANCED: Line Manager təsdiq edir"""
        self.line_manager_approved_at = timezone.now()
        self.line_manager_approved_by = user
        self.line_manager_comment = comment
        
        # ✅ Determine next step
        if self.requires_uk_additional_approval():
            next_status = 'PENDING_UK_ADDITIONAL'
        elif self.hr_representative:
            next_status = 'PENDING_HR'
        else:
            next_status = 'APPROVED'
        
        self.status = next_status
        self.save()
        
        # Only update balance if fully approved
        if self.status == 'APPROVED':
            self._update_balance()
    
    
    def approve_by_uk_additional(self, user, comment=''):
        """✅ FIXED: UK Additional Approver təsdiq edir"""
        from django.utils import timezone
        
        # Set approval data
        self.uk_additional_approved_at = timezone.now()
        self.uk_additional_approved_by = user
        self.uk_additional_comment = comment
        
        # ✅ CRITICAL FIX: Force refresh hr_representative from DB
        self.refresh_from_db()
        
        # Determine next status
        if self.hr_representative and self.hr_representative.id:
            next_status = 'PENDING_HR'
        else:
            next_status = 'APPROVED'
        
        self.status = next_status
        
        # ✅ Save with update_fields to force status change
        self.save(update_fields=[
            'uk_additional_approved_at',
            'uk_additional_approved_by',
            'uk_additional_comment',
            'status',
            'updated_at'
        ])
        
        # Only update balance if fully approved
        if self.status == 'APPROVED':
            self._update_balance()
    
    
    def approve_by_hr(self, user, comment=''):
        """✅ HR təsdiq edir - FINAL APPROVAL"""
        self.hr_approved_at = timezone.now()
        self.hr_approved_by = user
        self.hr_comment = comment
        self.status = 'APPROVED'
        
        # Save first
        self.save(update_fields=[
            'hr_approved_at',
            'hr_approved_by',
            'hr_comment',
            'status',
            'updated_at'
        ])
        
        # Then update balance
        self._update_balance()
    
    
    def _update_balance(self):
        """✅ Approved olduqda balansı yenilə"""
        try:
            balance, created = EmployeeVacationBalance.objects.get_or_create(
                employee=self.employee,
                year=self.start_date.year,
                defaults={
                    'start_balance': 0,
                    'yearly_balance': 28
                }
            )
            
            # ✅ Add used_days
            balance.used_days = float(balance.used_days) + float(self.number_of_days)
            balance.save()
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"✅ Balance updated: {self.employee.full_name} - Used: {balance.used_days}")
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"❌ Balance update failed: {e}")
    def check_date_conflicts(self):
        """Eyni employee üçün kəsişən tarixlərdə request/schedule olub-olmadığını yoxla"""
        conflicting_requests = VacationRequest.objects.filter(
            employee=self.employee,
            is_deleted=False,
            status__in=['PENDING_LINE_MANAGER', 'PENDING_UK_ADDITIONAL', 'PENDING_HR', 'APPROVED']
        ).filter(
            start_date__lte=self.end_date,
            end_date__gte=self.start_date
        ).exclude(pk=self.pk)
        
        conflicting_schedules = VacationSchedule.objects.filter(
            employee=self.employee,
            is_deleted=False,
            status='SCHEDULED'
        ).filter(
            start_date__lte=self.end_date,
            end_date__gte=self.start_date
        )
        
        conflicts = []
        
        for req in conflicting_requests:
            conflicts.append({
                'type': 'request',
                'id': req.request_id,
                'start_date': req.start_date,
                'end_date': req.end_date,
                'vacation_type': req.vacation_type.name,
                'status': req.get_status_display()
            })
        
        for sch in conflicting_schedules:
            conflicts.append({
                'type': 'schedule',
                'id': f'SCH{sch.id}',
                'start_date': sch.start_date,
                'end_date': sch.end_date,
                'vacation_type': sch.vacation_type.name,
                'status': sch.get_status_display()
            })
        
        return len(conflicts) > 0, conflicts


class VacationSchedule(SoftDeleteModel):
    """✅ ENHANCED: Vacation Schedule with approval workflow"""
    
    STATUS_CHOICES = [
        ('PENDING_MANAGER', 'Pending Manager Approval'),  # ✅ NEW
        ('SCHEDULED', 'Scheduled'),
        ('REGISTERED', 'Registered'),
    ]
    
    employee = models.ForeignKey(
        Employee, 
        on_delete=models.CASCADE, 
        related_name='schedules'
    )
    vacation_type = models.ForeignKey(VacationType, on_delete=models.PROTECT)
    
    # Dates
    start_date = models.DateField()
    end_date = models.DateField()
    return_date = models.DateField(editable=False, null=True, blank=True)
    number_of_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    
    # ✅ NEW: Approval fields
    line_manager = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedules_to_approve',
        help_text="Line Manager for approval"
    )
    manager_approved_at = models.DateTimeField(null=True, blank=True)
    manager_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_approvals'
    )
    manager_comment = models.TextField(blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING_MANAGER')
    
    # Edit tracking
    edit_count = models.PositiveIntegerField(default=0)
    last_edited_at = models.DateTimeField(null=True, blank=True)
    last_edited_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='schedule_edits'
    )
    
    comment = models.TextField(blank=True)
    
    # System fields
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def approve_by_manager(self, user, comment=''):
        """✅ NEW: Manager təsdiq edir"""
        self.manager_approved_at = timezone.now()
        self.manager_approved_by = user
        self.manager_comment = comment
        self.status = 'SCHEDULED'
        self.save()
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.vacation_type.name} - {self.start_date} to {self.end_date}"
    
    def check_date_conflicts(self):
        """
        Eyni employee üçün kəsişən tarixlərdə request/schedule olub-olmadığını yoxla
        Returns: (has_conflict, conflicting_records)
        """
        # Mövcud approved/pending requestlər
        conflicting_requests = VacationRequest.objects.filter(
            employee=self.employee,
            is_deleted=False,
            status__in=['PENDING_LINE_MANAGER', 'PENDING_HR', 'APPROVED']
        ).filter(
            start_date__lte=self.end_date,
            end_date__gte=self.start_date
        )
        
        # Başqa scheduled schedules
        conflicting_schedules = VacationSchedule.objects.filter(
            employee=self.employee,
            is_deleted=False,
            status='SCHEDULED'
        ).filter(
            start_date__lte=self.end_date,
            end_date__gte=self.start_date
        ).exclude(pk=self.pk)
        
        conflicts = []
        
        for req in conflicting_requests:
            conflicts.append({
                'type': 'request',
                'id': req.request_id,
                'start_date': req.start_date,
                'end_date': req.end_date,
                'vacation_type': req.vacation_type.name,
                'status': req.get_status_display()
            })
        
        for sch in conflicting_schedules:
            conflicts.append({
                'type': 'schedule',
                'id': f'SCH{sch.id}',
                'start_date': sch.start_date,
                'end_date': sch.end_date,
                'vacation_type': sch.vacation_type.name,
                'status': sch.get_status_display()
            })
        
        return len(conflicts) > 0, conflicts
    
    def clean(self):
        """Validation"""
        # ✅ FIXED: Allow single day schedules (start_date == end_date)
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError("End date start date-dən kiçik ola bilməz")
        
        # ✅ Conflict check
        has_conflict, conflicts = self.check_date_conflicts()
        if has_conflict:
            conflict_details = ", ".join([
                f"{c['id']} ({c['start_date']} - {c['end_date']})" 
                for c in conflicts
            ])
            raise ValidationError(
                f"Bu tarixlərdə artıq vacation var: {conflict_details}"
            )
    
    def save(self, *args, **kwargs):
        # Calculate working days and return date
        settings = VacationSetting.get_active()
        if settings and self.start_date and self.end_date:
            bf_code = None
            if self.employee.business_function:
                bf_code = getattr(self.employee.business_function, 'code', None)
            self.number_of_days = settings.calculate_working_days(
                self.start_date, 
                self.end_date,
                bf_code
            )
            self.return_date = settings.calculate_return_date(self.end_date, bf_code)
        
        # ✅ Track status changes
        is_new = not self.pk
        old_status = None
        if not is_new:
            try:
                old_status = VacationSchedule.objects.get(pk=self.pk).status
            except VacationSchedule.DoesNotExist:
                pass
        
        self.clean()
        super().save(*args, **kwargs)
        
        # ✅ ENHANCED: Update scheduled_days when status changes to SCHEDULED
        if is_new and self.status == 'SCHEDULED':
            # New schedule created as SCHEDULED
            self._update_scheduled_balance(add=True)
        elif not is_new and old_status == 'PENDING_MANAGER' and self.status == 'SCHEDULED':
            # ✅ FIX: Status changed from PENDING → SCHEDULED (manager approved)
            self._update_scheduled_balance(add=True)
    
    def register_as_taken(self, user):
        """Schedule-i registered et"""
        if self.status != 'SCHEDULED':
            return
        
        # Get or create balance
        balance, created = EmployeeVacationBalance.objects.get_or_create(
            employee=self.employee, 
            year=self.start_date.year,
            defaults={
                'start_balance': 0,
                'yearly_balance': 28,
                'updated_by': user
            }
        )
        
        # DÜZƏLTMƏ: Scheduled-dən sil, used-ə əlavə et
        balance.scheduled_days = max(0, float(balance.scheduled_days) - float(self.number_of_days))
        balance.used_days = float(balance.used_days) + float(self.number_of_days)
        balance.updated_by = user
        balance.save()
        
        # Status dəyiş
        self.status = 'REGISTERED'
        self.save()
    
    def _update_scheduled_balance(self, add=True):
        """Scheduled balansı yenilə"""
        balance, created = EmployeeVacationBalance.objects.get_or_create(
            employee=self.employee,
            year=self.start_date.year,
           
        )
        
        if add:
            balance.scheduled_days += self.number_of_days
        else:
            balance.scheduled_days = max(0, balance.scheduled_days - self.number_of_days)
        
        balance.save()
    
    def can_edit(self):
        """Edit edilə bilərmi?"""
        if self.status != 'SCHEDULED':
            return False
        
        settings = VacationSetting.get_active()
        max_edits = settings.max_schedule_edits if settings else 3
        return self.edit_count < max_edits

def vacation_attachment_path(instance, filename):
    """Generate upload path for vacation attachments"""
    # vacation/2025/VR202500001/filename.pdf
    year = instance.vacation_request.created_at.year
    request_id = instance.vacation_request.request_id
    return f'vacation/{year}/{request_id}/{filename}'


class VacationAttachment(SoftDeleteModel):
    """File attachments for vacation requests"""
    vacation_request = models.ForeignKey(
        VacationRequest, 
        on_delete=models.CASCADE, 
        related_name='attachments'
    )
    file = models.FileField(upload_to=vacation_attachment_path)
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    file_type = models.CharField(max_length=100, blank=True)
    
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Vacation Attachment"
        verbose_name_plural = "Vacation Attachments"
        db_table = 'vacation_attachments'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.vacation_request.request_id} - {self.original_filename}"
    
    @property
    def file_size_display(self):
        """Human readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def delete(self, *args, **kwargs):
        """Delete file from storage when model is deleted"""
        if self.file:
            import os
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super().delete(*args, **kwargs)