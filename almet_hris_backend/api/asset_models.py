# api/asset_models.py - COMPLETE REWRITE

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid
import logging

logger = logging.getLogger(__name__)


class AssetCategory(models.Model):
    """Asset kateqoriyaları - Laptop, Monitor, Phone və s."""
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'asset_categories'
        verbose_name = 'Asset Category'
        verbose_name_plural = 'Asset Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class AssetBatch(models.Model):
    """
    🎯 Asset Batch - Partiya (Eyni növdən bir neçə asset)
    Məsələn: 10 ədəd Dell Latitude 5420 laptop
    
    Quantity tracking:
    - initial_quantity: Başlanğıc miqdar (10)
    - available_quantity: Hələ təyin edilməmiş (7)
    - assigned_quantity: Təyin edilmiş (3)
    - out_of_stock_quantity: Xarab/itirilmiş (0)
    """
    
    batch_number = models.CharField(max_length=50, unique=True, editable=False)
    asset_name = models.CharField(max_length=200, verbose_name="Asset Adı")
    category = models.ForeignKey(AssetCategory, on_delete=models.CASCADE, related_name='batches')
    
    # 📊 Quantity tracking - MƏRKƏZI SAYĞAC
    initial_quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Başlanğıc miqdar (neçə ədəd alınıb)"
    )
    available_quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        help_text="Hələ təyin edilməmiş miqdar"
    )
    assigned_quantity = models.PositiveIntegerField(
        default=0,
        help_text="İşçilərə təyin edilmiş miqdar"
    )
    out_of_stock_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Xarab/itirilmiş miqdar"
    )
    
    # 💰 Financial
    unit_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Hər birinin qiyməti"
    )
    total_value = models.DecimalField(
        max_digits=14, 
        decimal_places=2,
        editable=False,
        help_text="Ümumi dəyər (auto-calculated)"
    )
    purchase_date = models.DateField()
    useful_life_years = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        default=5
    )
    
    # 📝 Details
    supplier = models.CharField(max_length=200, blank=True)
    purchase_order_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    # 🎯 Status
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('OUT_OF_STOCK', 'Out of Stock'),
        ('ARCHIVED', 'Archived'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    
    # 🕐 Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_batches')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'asset_batches'
        verbose_name = 'Asset Batch'
        verbose_name_plural = 'Asset Batches'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.batch_number} - {self.asset_name} ({self.available_quantity}/{self.initial_quantity})"
    
    def save(self, *args, **kwargs):
        # Generate batch number
        if not self.batch_number:
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            self.batch_number = f"BATCH-{timestamp}"
        
        # Calculate total value
        self.total_value = self.unit_price * self.initial_quantity
        
        # Auto-update status
        if self.available_quantity == 0 and self.assigned_quantity == 0:
            self.status = 'OUT_OF_STOCK'
        elif self.status == 'OUT_OF_STOCK' and self.available_quantity > 0:
            self.status = 'ACTIVE'
        
        super().save(*args, **kwargs)
    
    def is_available(self, quantity=1):
        """Check if requested quantity is available"""
        return self.available_quantity >= quantity and self.status == 'ACTIVE'
    
    def assign_quantity(self, quantity):
        """
        🎯 Asset təyin edəndə çağırılır
        Available-dan assigned-ə keçir
        """
        if self.available_quantity >= quantity:
            self.available_quantity -= quantity
            self.assigned_quantity += quantity
            self.save()
            logger.info(f"✅ Batch {self.batch_number}: Assigned {quantity} (Available: {self.available_quantity})")
            return True
        logger.warning(f"❌ Batch {self.batch_number}: Insufficient quantity")
        return False
    
    def return_quantity(self, quantity):
        """
        🔙 Asset geri qaytarılanda çağırılır
        Assigned-dən available-ə keçir
        """
        self.available_quantity += quantity
        self.assigned_quantity = max(0, self.assigned_quantity - quantity)
        self.save()
        logger.info(f"✅ Batch {self.batch_number}: Returned {quantity} (Available: {self.available_quantity})")
    
    def mark_out_of_stock(self, quantity):
        """
        ❌ Asset xarab/itirildiyi zaman çağırılır
        """
        if self.available_quantity >= quantity:
            self.available_quantity -= quantity
            self.out_of_stock_quantity += quantity
            self.save()
            logger.info(f"✅ Batch {self.batch_number}: Marked {quantity} as out of stock")
            return True
        return False
    
    def get_quantity_summary(self):
        """Miqdar xülasəsi"""
        return {
            'initial': self.initial_quantity,
            'available': self.available_quantity,
            'assigned': self.assigned_quantity,
            'out_of_stock': self.out_of_stock_quantity,
            'total_used': self.assigned_quantity + self.out_of_stock_quantity,
            'percentage_available': round((self.available_quantity / self.initial_quantity * 100), 1) if self.initial_quantity > 0 else 0
        }


class Asset(models.Model):
    """
    🎯 Individual Asset - Hər bir fərdi asset
    Hər asset bir batch-ə aid olur
    """
    
    STATUS_CHOICES = [
        ('IN_STOCK', 'In Stock'),                    # Anbarda
        ('ASSIGNED', 'Assigned (Pending Approval)'), # Təyin edilib, təsdiq gözlənilir
        ('IN_USE', 'In Use'),                        # İstifadədə (təsdiq edilib)
        ('NEED_CLARIFICATION', 'Need Clarification'),# Aydınlaşdırma lazımdır
        ('IN_REPAIR', 'In Repair'),                  # Təmirdə
        ('OUT_OF_STOCK', 'Out of Stock'),            # Xarab/itirilmiş
        ('ARCHIVED', 'Archived'),                    # Arxivləşdirilmiş
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # 📦 Batch relationship - HƏR ASSET BİR BATCH-Ə AİDDİR
    batch = models.ForeignKey(
        AssetBatch, 
        on_delete=models.CASCADE, 
        related_name='assets',
        help_text="Bu asset hansı partiyaya aiddir"
    )
    
    # 🔢 Individual tracking
    asset_number = models.CharField(
        max_length=50, 
        unique=True, 
        editable=False,
        help_text="Fərdi asset nömrəsi (auto-generated)"
    )
    serial_number = models.CharField(
        max_length=100, 
        unique=True,
        help_text="Serial nömrə (manufacturer serial)"
    )
    
    # 📋 Quick access fields (copied from batch)
    asset_name = models.CharField(max_length=200, editable=False)
    category = models.ForeignKey(AssetCategory, on_delete=models.CASCADE, editable=False)
    
    # 🎯 Status
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='IN_STOCK')
    
    # 👤 Assignment
    assigned_to = models.ForeignKey(
        'Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_assets'
    )
    
    # ❓ Clarification tracking
    clarification_requested_reason = models.TextField(blank=True, null=True)
    clarification_response = models.TextField(blank=True, null=True)
    clarification_requested_at = models.DateTimeField(blank=True, null=True)
    clarification_provided_at = models.DateTimeField(blank=True, null=True)
    clarification_requested_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, 
        related_name='clarification_requested_assets'
    )
    clarification_provided_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, 
        related_name='clarification_provided_assets'
    )
    
    # 📦 Archive tracking
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, 
        related_name='archived_assets'
    )
    archive_reason = models.TextField(blank=True, null=True)
    
    # ❌ Out of stock tracking
    out_of_stock_reason = models.TextField(blank=True, null=True)
    out_of_stock_at = models.DateTimeField(null=True, blank=True)
    
    # 🕐 Metadata
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, 
        related_name='created_assets'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, 
        related_name='updated_assets'
    )
    
    class Meta:
        db_table = 'assets'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['asset_number']),
            models.Index(fields=['serial_number']),
            models.Index(fields=['status']),
            models.Index(fields=['batch']),
            models.Index(fields=['assigned_to']),
        ]
    
    def __str__(self):
        return f"{self.asset_number} - {self.asset_name} ({self.serial_number})"
    
    def save(self, *args, **kwargs):
        # Generate asset number
        if not self.asset_number:
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S%f')
            self.asset_number = f"AST-{timestamp}"
        
        # Copy batch fields
        if self.batch_id:
            self.asset_name = self.batch.asset_name
            self.category = self.batch.category
        
        super().save(*args, **kwargs)
    
    def can_be_assigned(self):
        """Asset təyin edilə bilərmi?"""
        return self.status == 'IN_STOCK' and not self.assigned_to
    
    def can_be_approved(self):
        """Asset təsdiq edilə bilərmi?"""
        return self.status == 'ASSIGNED' and self.assigned_to is not None
    
    def can_request_clarification(self):
        """Aydınlaşdırma sorğusu göndərilə bilərmi?"""
        return self.status in ['ASSIGNED', 'NEED_CLARIFICATION'] and self.assigned_to is not None
    
    def can_be_checked_in(self):
        """Asset geri qaytarıla bilərmi?"""
        return self.status == 'IN_USE' and self.assigned_to is not None
    
    def get_current_assignment(self):
        """Hazırkı təyinat məlumatı"""
        if self.assigned_to:
            current_assignment = self.assignments.filter(check_in_date__isnull=True).first()
            
            if current_assignment:
                return {
                    'employee': {
                        'id': self.assigned_to.id,
                        'name': self.assigned_to.full_name,
                        'employee_id': self.assigned_to.employee_id
                    },
                    'assignment': {
                        'id': current_assignment.id,
                        'check_out_date': current_assignment.check_out_date.isoformat(),
                        'check_out_notes': current_assignment.check_out_notes,
                        'condition_on_checkout': current_assignment.condition_on_checkout,
                        'duration_days': current_assignment.get_duration_days(),
                        'assigned_by': current_assignment.assigned_by.get_full_name() if current_assignment.assigned_by else None
                    }
                }
        return None


class AssetAssignment(models.Model):
    """Asset təyinat tarixçəsi - Kimə nə vaxt verildi"""
    
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='assignments')
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='asset_assignments')
    
    # Dates
    check_out_date = models.DateField(verbose_name="Verilmə tarixi")
    check_in_date = models.DateField(null=True, blank=True, verbose_name="Qaytarılma tarixi")
    
    # Notes
    check_out_notes = models.TextField(blank=True)
    check_in_notes = models.TextField(blank=True)
    
    # Condition
    condition_on_checkout = models.CharField(
        max_length=30,
        choices=[
            ('EXCELLENT', 'Excellent'),
            ('GOOD', 'Good'),
            ('FAIR', 'Fair'),
            ('POOR', 'Poor'),
        ],
        default='GOOD'
    )
    condition_on_checkin = models.CharField(
        max_length=35,
        choices=[
            ('EXCELLENT', 'Excellent'),
            ('GOOD', 'Good'),
            ('FAIR', 'Fair'),
            ('POOR', 'Poor'),
            ('DAMAGED', 'Damaged'),
        ],
        blank=True
    )
    
    # Who
    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, 
        related_name='assigned_assets_by'
    )
    checked_in_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, 
        related_name='checked_in_assets_by'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'asset_assignments'
        ordering = ['-created_at']
    
    def __str__(self):
        status = "Active" if not self.check_in_date else "Completed"
        return f"{self.asset.asset_name} → {self.employee.full_name} ({status})"
    
    def is_active(self):
        return self.check_in_date is None
    
    def get_duration_days(self):
        if self.check_in_date:
            return (self.check_in_date - self.check_out_date).days
        return (timezone.now().date() - self.check_out_date).days


class AssetActivity(models.Model):
    """Activity log - Hər bir əməliyyatın qeydi"""
    
    ACTIVITY_TYPES = [
        ('CREATED', 'Created'),
        ('UPDATED', 'Updated'),
        ('ASSIGNED', 'Assigned to Employee'),
        ('ACCEPTED', 'Accepted by Employee'),
        ('CLARIFICATION_REQUESTED', 'Clarification Requested'),
        ('CLARIFICATION_PROVIDED', 'Clarification Provided'),
        ('CHECKED_IN', 'Checked In'),
        ('STATUS_CHANGED', 'Status Changed'),
        ('OUT_OF_STOCK', 'Marked Out of Stock'),
        ('ARCHIVED', 'Archived'),
        ('RESTORED', 'Restored from Archive'),
        ('TRANSFERRED', 'Transferred (Offboarding)'),
        ('ASSIGNMENT_CANCELLED', 'Assignment Cancelled'),
    ]
    
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    description = models.TextField()
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    performed_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'asset_activities'
        ordering = ['-performed_at']
    
    def __str__(self):
        return f"{self.asset.asset_name} - {self.get_activity_type_display()}"


class EmployeeOffboarding(models.Model):
    """Offboarding - İşdən çıxan işçinin asset transferi"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    OFFBOARDING_TYPE_CHOICES = [
        ('TRANSFER', 'Transfer to Another Employee'),
        ('RETURN', 'Return to IT (No Transfer)'),
    ]
    
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='offboardings')
    last_working_day = models.DateField()
    
    # 🆕 Offboarding type
    offboarding_type = models.CharField(
        max_length=20, 
        choices=OFFBOARDING_TYPE_CHOICES, 
        default='RETURN',
        help_text="Transfer or Return to IT"
    )
    
    # Asset tracking
    total_assets = models.PositiveIntegerField(default=0)
    assets_transferred = models.PositiveIntegerField(default=0)
    assets_returned = models.PositiveIntegerField(default=0)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # 🆕 IT Handover completion
    it_handover_completed = models.BooleanField(
        default=False,
        help_text="IT confirmed all assets received"
    )
    it_handover_completed_at = models.DateTimeField(null=True, blank=True)
    it_handover_completed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='completed_handovers'
    )
    
    # Approval
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, 
        related_name='approved_offboardings'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, 
        related_name='created_offboardings'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'employee_offboardings'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Offboarding: {self.employee.full_name} - {self.status}"


class AssetTransferRequest(models.Model):
    """Asset transfer - Offboarding zamanı başqasına verilir"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed'),
    ]
    
    offboarding = models.ForeignKey(
        EmployeeOffboarding, on_delete=models.CASCADE, 
        related_name='transfer_requests'
    )
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    
    from_employee = models.ForeignKey(
        'Employee', on_delete=models.CASCADE, 
        related_name='asset_transfers_from'
    )
    to_employee = models.ForeignKey(
        'Employee', on_delete=models.CASCADE, 
        related_name='asset_transfers_to'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    requested_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, 
        related_name='requested_transfers'
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    
    # 🆕 Employee approval (to_employee must accept)
    employee_approved = models.BooleanField(default=False)
    employee_approved_at = models.DateTimeField(null=True, blank=True)
    
    # Admin/IT approval
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, 
        related_name='approved_transfers'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    rejection_reason = models.TextField(blank=True)
    transfer_notes = models.TextField(blank=True)
    
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'asset_transfer_requests'
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"Transfer: {self.asset.asset_name} from {self.from_employee.full_name} to {self.to_employee.full_name}"
    """Asset transfer - Offboarding zamanı başqasına verilir"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed'),
    ]
    
    offboarding = models.ForeignKey(
        EmployeeOffboarding, on_delete=models.CASCADE, 
        related_name='transfer_requests'
    )
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    
    from_employee = models.ForeignKey(
        'Employee', on_delete=models.CASCADE, 
        related_name='asset_transfers_from'
    )
    to_employee = models.ForeignKey(
        'Employee', on_delete=models.CASCADE, 
        related_name='asset_transfers_to'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    requested_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, 
        related_name='requested_transfers'
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, 
        related_name='approved_transfers'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    rejection_reason = models.TextField(blank=True)
    transfer_notes = models.TextField(blank=True)
    
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'asset_transfer_requests'
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"Transfer: {self.asset.asset_name} from {self.from_employee.full_name} to {self.to_employee.full_name}"