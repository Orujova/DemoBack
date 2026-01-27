# api/business_trip_models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from .models import Employee, SoftDeleteModel
from datetime import date, timedelta
import os

class TravelType(SoftDeleteModel):
    """Travel type configuration (Domestic, Overseas)"""
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='travel_type_updates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "Travel Type"
        verbose_name_plural = "Travel Types"
        db_table = 'travel_types'

class TransportType(SoftDeleteModel):
    """Transport type configuration (Taxi, Train, Airplane, etc.)"""
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='transport_type_updates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "Transport Type"
        verbose_name_plural = "Transport Types"
        db_table = 'transport_types'

class TripPurpose(SoftDeleteModel):
    """Trip purpose configuration (Conference, Meeting, Training, etc.)"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='trip_purpose_updates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "Trip Purpose"
        verbose_name_plural = "Trip Purposes"
        db_table = 'trip_purposes'

class TripSettings(SoftDeleteModel):
    """Business trip system settings"""
    
    # Default Approvers
    default_hr_representative = models.ForeignKey(
        Employee, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='trip_hr_settings',
        help_text="Default HR representative"
    )
    default_finance_approver = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trip_finance_settings',
        help_text="Default Finance/Payroll approver"
    )
    
    # Notifications
    notification_days_before = models.PositiveIntegerField(
        default=7,
        help_text="Send notification X days before trip starts"
    )
    
    # System fields
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='trip_settings_updates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Trip Setting"
        verbose_name_plural = "Trip Settings"
        db_table = 'trip_settings'
    
    def __str__(self):
        return f"Trip Settings - Active: {self.is_active}"
    
    @classmethod
    def get_active(cls):
        """Get active settings"""
        return cls.objects.filter(is_active=True, is_deleted=False).first()
    
    def clean(self):
        """Validation - only one active setting"""
        if self.is_active:
            existing = TripSettings.objects.filter(
                is_active=True, 
                is_deleted=False
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError("Only one active trip setting allowed")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

class BusinessTripRequest(SoftDeleteModel):
    """Main business trip request model"""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('PENDING_LINE_MANAGER', 'Pending Line Manager'),
        ('PENDING_FINANCE', 'Pending Finance/Payroll'),
        ('PENDING_HR', 'Pending HR'),
        ('APPROVED', 'Approved'),
        ('REJECTED_LINE_MANAGER', 'Rejected by Line Manager'),
        ('REJECTED_FINANCE', 'Rejected by Finance'),
        ('REJECTED_HR', 'Rejected by HR'),
        ('CANCELLED', 'Cancelled'),
    ]

    REQUESTER_TYPE_CHOICES = [
        ('for_me', 'For Me'),
        ('for_my_employee', 'For My Employee'),
    ]

    # Request identification
    request_id = models.CharField(max_length=20, unique=True, editable=False)
    
    # Requester information
    requester_type = models.CharField(max_length=20, choices=REQUESTER_TYPE_CHOICES, default='for_me')
    requester = models.ForeignKey(User, on_delete=models.CASCADE,null=True, related_name='created_trip_requests')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='trip_requests')
    
    # Travel details
    travel_type = models.ForeignKey(TravelType, on_delete=models.PROTECT)
    transport_type = models.ForeignKey(TransportType, on_delete=models.PROTECT)
    purpose = models.ForeignKey(TripPurpose, on_delete=models.PROTECT)
    
    # Dates
    start_date = models.DateField()
    end_date = models.DateField()
    return_date = models.DateField(editable=False, null=True, blank=True)
    number_of_days = models.DecimalField(max_digits=5, decimal_places=1, editable=False, default=0)
    
    comment = models.TextField(blank=True, help_text="Employee comment")
    
    # Approvers
    line_manager = models.ForeignKey(
        Employee, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='trips_to_approve'
    )
    finance_approver = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trips_finance'
    )
    hr_representative = models.ForeignKey(
        Employee, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='trips_hr'
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
        related_name='trip_lm_approvals'
    )
    line_manager_comment = models.TextField(blank=True)
    
    # Finance Approval
    finance_approved_at = models.DateTimeField(null=True, blank=True)
    finance_approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='trip_finance_approvals'
    )
    finance_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    finance_comment = models.TextField(blank=True)
    
    # HR Approval
    hr_approved_at = models.DateTimeField(null=True, blank=True)
    hr_approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='trip_hr_approvals'
    )
    hr_comment = models.TextField(blank=True)
    
    # Rejection
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='trip_rejections'
    )
    rejection_reason = models.TextField(blank=True)
    
    # Cancellation
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trip_cancellations'
    )
    
    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Business Trip Request"
        verbose_name_plural = "Business Trip Requests"
        db_table = 'business_trip_requests'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.request_id} - {self.employee.full_name} - {self.travel_type.name}"
    
    def clean(self):
        """Validation"""
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("End date must be after start date")
    
    def save(self, *args, **kwargs):
        # Generate request ID
        if not self.request_id:
            year = timezone.now().year
            last = BusinessTripRequest.objects.filter(
                request_id__startswith=f'BT{year}'
            ).order_by('-request_id').first()
            num = int(last.request_id[6:]) + 1 if last else 1
            self.request_id = f'BT{year}{num:04d}'
        
        # Calculate days
        if self.start_date and self.end_date:
            self.number_of_days = (self.end_date - self.start_date).days + 1
            self.return_date = self.end_date + timedelta(days=1)
        
        # Auto-assign approvers
        if not self.line_manager and self.employee.line_manager:
            requester_emp = getattr(self.requester, 'employee', None)
            if not (requester_emp and self.employee.line_manager == requester_emp):
                self.line_manager = self.employee.line_manager
        
        settings = TripSettings.get_active()
        if not self.hr_representative and settings:
            self.hr_representative = settings.default_hr_representative
        
        self.clean()
        super().save(*args, **kwargs)
    
    def submit_request(self, user):
        """Submit for approval"""
        requester_emp = getattr(user, 'employee', None)
        is_manager_request = requester_emp and self.employee.line_manager == requester_emp
        
        if is_manager_request:
            self.status = 'PENDING_FINANCE' if self.finance_approver else ('PENDING_HR' if self.hr_representative else 'APPROVED')
        else:
            self.status = 'PENDING_LINE_MANAGER' if self.line_manager else ('PENDING_FINANCE' if self.finance_approver else ('PENDING_HR' if self.hr_representative else 'APPROVED'))
        
        self.save()
    
    def approve_by_line_manager(self, user, comment=''):
        """Line Manager approval"""
        self.line_manager_approved_at = timezone.now()
        self.line_manager_approved_by = user
        self.line_manager_comment = comment
        self.status = 'PENDING_FINANCE' if self.finance_approver else ('PENDING_HR' if self.hr_representative else 'APPROVED')
        self.save()
    
    def reject_by_line_manager(self, user, reason):
        """Line Manager rejection"""
        self.status = 'REJECTED_LINE_MANAGER'
        self.rejected_at = timezone.now()
        self.rejected_by = user
        self.rejection_reason = reason
        self.save()
    
    def approve_by_finance(self, user, amount=None, comment=''):
        """Finance approval"""
        self.finance_approved_at = timezone.now()
        self.finance_approved_by = user
        self.finance_amount = amount
        self.finance_comment = comment
        self.status = 'PENDING_HR' if self.hr_representative else 'APPROVED'
        self.save()
    
    def reject_by_finance(self, user, reason):
        """Finance rejection"""
        self.status = 'REJECTED_FINANCE'
        self.rejected_at = timezone.now()
        self.rejected_by = user
        self.rejection_reason = reason
        self.save()
    
    def approve_by_hr(self, user, comment=''):
        """HR approval"""
        self.hr_approved_at = timezone.now()
        self.hr_approved_by = user
        self.hr_comment = comment
        self.status = 'APPROVED'
        self.save()
    
    def reject_by_hr(self, user, reason):
        """HR rejection"""
        self.status = 'REJECTED_HR'
        self.rejected_at = timezone.now()
        self.rejected_by = user
        self.rejection_reason = reason
        self.save()

class TripSchedule(SoftDeleteModel):
    """Trip schedule/itinerary details"""
    trip_request = models.ForeignKey(BusinessTripRequest, on_delete=models.CASCADE, related_name='schedules')
    date = models.DateField()
    from_location = models.CharField(max_length=200)
    to_location = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.trip_request.request_id} - {self.date}: {self.from_location} → {self.to_location}"

    class Meta:
        ordering = ['trip_request', 'date', 'order']
        verbose_name = "Trip Schedule"
        verbose_name_plural = "Trip Schedules"
        db_table = 'trip_schedules'

class TripHotel(SoftDeleteModel):
    """Hotel accommodation details"""
    trip_request = models.ForeignKey(BusinessTripRequest, on_delete=models.CASCADE, related_name='hotels')
    hotel_name = models.CharField(max_length=200)
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    location = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.trip_request.request_id} - {self.hotel_name}"

    @property
    def nights_count(self):
        """Calculate number of nights"""
        if self.check_in_date and self.check_out_date:
            return (self.check_out_date - self.check_in_date).days
        return 0

    class Meta:
        ordering = ['trip_request', 'check_in_date']
        verbose_name = "Trip Hotel"
        verbose_name_plural = "Trip Hotels"
        db_table = 'trip_hotels'


def trip_attachment_path(instance, filename):
    """Generate upload path for trip attachments"""
    # business_trips/2025/BT202500001/filename.pdf
    year = instance.trip_request.created_at.year
    request_id = instance.trip_request.request_id
    return f'business_trips/{year}/{request_id}/{filename}'


class TripAttachment(SoftDeleteModel):
    """File attachments for business trip requests"""
    trip_request = models.ForeignKey(
        BusinessTripRequest, 
        on_delete=models.CASCADE, 
        related_name='attachments'
    )
    file = models.FileField(upload_to=trip_attachment_path)
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    file_type = models.CharField(max_length=100, blank=True)

    
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Trip Attachment"
        verbose_name_plural = "Trip Attachments"
        db_table = 'trip_attachments'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.trip_request.request_id} - {self.original_filename}"
    
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
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super().delete(*args, **kwargs)