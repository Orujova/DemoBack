# api/asset_serializers.py - COMPLETE REWRITE

from rest_framework import serializers
from .asset_models import (
    AssetCategory, AssetBatch, Asset, AssetAssignment, 
    AssetActivity, EmployeeOffboarding, AssetTransferRequest
)
from .models import Employee
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


# ============================================
# BASIC SERIALIZERS
# ============================================

class AssetUserBasicSerializer(serializers.ModelSerializer):
    """User basic info"""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name', 'email']
        ref_name = 'AssetUserBasic'
    
    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class AssetEmployeeBasicSerializer(serializers.ModelSerializer):
    """Employee basic info"""
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    class Meta:
        model = Employee
        fields = ['id', 'employee_id', 'full_name', 'job_title', 'department', 'department_name']
        ref_name = 'AssetEmployeeBasic'


# ============================================
# CATEGORY SERIALIZERS
# ============================================

class AssetCategorySerializer(serializers.ModelSerializer):
    """Asset Category"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    asset_count = serializers.SerializerMethodField()
    batch_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AssetCategory
        fields = [
            'id', 'name', 'description', 'is_active',
            'asset_count', 'batch_count',
            'created_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'created_by']
        ref_name = 'AssetCategory'
    
    def get_asset_count(self, obj):
        return Asset.objects.filter(category=obj).count()
    
    def get_batch_count(self, obj):
        return obj.batches.count()


# ============================================
# BATCH SERIALIZERS
# ============================================

class AssetBatchListSerializer(serializers.ModelSerializer):
    """Batch list view"""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    quantity_summary = serializers.SerializerMethodField()
    availability_status = serializers.SerializerMethodField()
    
    class Meta:
        model = AssetBatch
        fields = [
            'id', 'batch_number', 'asset_name', 'category', 'category_name',
            'initial_quantity', 'available_quantity', 'assigned_quantity', 
            'out_of_stock_quantity', 'quantity_summary',
            'unit_price', 'total_value', 'status', 'availability_status',
            'purchase_date', 'supplier', 'created_at', 'created_by_name'
        ]
        ref_name = 'AssetBatchList'
    
    def get_quantity_summary(self, obj):
        return obj.get_quantity_summary()
    
    def get_availability_status(self, obj):
        summary = obj.get_quantity_summary()
        percentage = summary['percentage_available']
        
        if percentage == 0:
            return {'status': 'OUT_OF_STOCK', 'color': '#DC2626', 'label': 'Stokda yoxdur'}
        elif percentage <= 20:
            return {'status': 'LOW_STOCK', 'color': '#F59E0B', 'label': 'Az qalıb'}
        else:
            return {'status': 'IN_STOCK', 'color': '#10B981', 'label': 'Mövcuddur'}


class AssetBatchDetailSerializer(serializers.ModelSerializer):
    """Batch detail view"""
    
    category = AssetCategorySerializer(read_only=True)
    created_by_detail = AssetUserBasicSerializer(source='created_by', read_only=True)
    quantity_summary = serializers.SerializerMethodField()
    assets = serializers.SerializerMethodField()
    
    class Meta:
        model = AssetBatch
        fields = [
            'id', 'batch_number', 'asset_name', 'category',
            'initial_quantity', 'available_quantity', 'assigned_quantity',
            'out_of_stock_quantity', 'quantity_summary',
            'unit_price', 'total_value', 'purchase_date', 'useful_life_years',
            'supplier', 'purchase_order_number', 'notes', 'status',
            'assets', 'created_by_detail', 'created_at', 'updated_at'
        ]
        ref_name = 'AssetBatchDetail'
    
    def get_quantity_summary(self, obj):
        return obj.get_quantity_summary()
    
    def get_assets(self, obj):
        from .asset_serializers import AssetListSerializer
        assets = obj.assets.all()[:50]
        return AssetListSerializer(assets, many=True, context=self.context).data


class AssetBatchCreateSerializer(serializers.ModelSerializer):
    """
    🎯 Batch yaratma - SAY BURADAN QEYD EDİLİR
    
    Nümunə:
    {
        "asset_name": "Dell Latitude 5420 Laptop",
        "category": 1,
        "initial_quantity": 10,  👈 BURADAN SAY QEYD EDİLİR
        "unit_price": 1500.00,
        "purchase_date": "2024-01-15",
        "useful_life_years": 5,
        "supplier": "Dell Azerbaijan"
    }
    """
    
    class Meta:
        model = AssetBatch
        fields = [
            'asset_name', 'category', 'initial_quantity',  # 👈 initial_quantity - SAY
            'unit_price', 'purchase_date', 'useful_life_years',
            'supplier', 'purchase_order_number', 'notes'
        ]
        ref_name = 'AssetBatchCreate'
    
    def validate_initial_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Miqdar ən azı 1 olmalıdır")
        if value > 1000:
            raise serializers.ValidationError("Miqdar 1000-dən çox ola bilməz")
        return value
    
    def validate_unit_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Qiymət 0-dan böyük olmalıdır")
        return value
    
    def create(self, validated_data):
        """
        Batch yaradılır və available_quantity = initial_quantity təyin edilir
        """
        # 🎯 BURDA SAY QEYD EDİLİR
        validated_data['available_quantity'] = validated_data['initial_quantity']
        
        batch = AssetBatch.objects.create(**validated_data)
        
        logger.info(f"✅ Batch yaradıldı: {batch.batch_number} - {batch.asset_name} x{batch.initial_quantity}")
        
        return batch


# ============================================
# ASSET SERIALIZERS
# ============================================

class AssetListSerializer(serializers.ModelSerializer):
    """Asset list view"""
    
    batch = AssetBatchListSerializer(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.full_name', read_only=True)
    assigned_to_employee_id = serializers.CharField(source='assigned_to.employee_id', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    status_color = serializers.SerializerMethodField()
    
    class Meta:
        model = Asset
        fields = [
            'id', 'asset_number', 'serial_number', 'asset_name',
            'batch', 
            'category', 'category_name',
            'status', 'status_display', 'status_color',
            'assigned_to', 'assigned_to_name', 'assigned_to_employee_id',
            'created_at', 'updated_at',       'can_be_assigned', 'can_be_approved', 'can_be_checked_in'
        ]
        ref_name = 'AssetList'
    
    def get_can_be_assigned(self, obj):
        return obj.can_be_assigned()
    
    def get_can_be_approved(self, obj):
        return obj.can_be_approved()
    
    def get_can_be_checked_in(self, obj):
        return obj.can_be_checked_in()
    def get_status_color(self, obj):
        colors = {
            'IN_STOCK': '#6B7280',
            'ASSIGNED': '#F59E0B',
            'IN_USE': '#10B981',
            'NEED_CLARIFICATION': '#8B5CF6',
            'IN_REPAIR': '#EF4444',
            'OUT_OF_STOCK': '#DC2626',
            'ARCHIVED': '#7F1D1D',
        }
        return colors.get(obj.status, '#6B7280')


class AssetDetailSerializer(serializers.ModelSerializer):
    """Asset detail view"""
    
    batch = AssetBatchListSerializer(read_only=True)
    category = AssetCategorySerializer(read_only=True)
    assigned_to = AssetEmployeeBasicSerializer(read_only=True)
    
    created_by_detail = AssetUserBasicSerializer(source='created_by', read_only=True)
    updated_by_detail = AssetUserBasicSerializer(source='updated_by', read_only=True)
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    status_color = serializers.SerializerMethodField()
    current_assignment = serializers.SerializerMethodField()
    clarification_info = serializers.SerializerMethodField()
    
    assignments = serializers.SerializerMethodField()
    activities = serializers.SerializerMethodField()
    
    can_be_assigned = serializers.SerializerMethodField()
    can_be_approved = serializers.SerializerMethodField()
    can_be_checked_in = serializers.SerializerMethodField()
    
    class Meta:
        model = Asset
        fields = [
            'id', 'asset_number', 'serial_number', 'asset_name',
            'batch', 'category', 'status', 'status_display', 'status_color',
            'assigned_to', 'current_assignment', 'clarification_info',
            'out_of_stock_reason', 'out_of_stock_at',
            'archived_at', 'archived_by', 'archive_reason',
            'created_by_detail', 'created_at',
            'updated_by_detail', 'updated_at',
            'assignments', 'activities',
            'can_be_assigned', 'can_be_approved', 'can_be_checked_in'
        ]
        ref_name = 'AssetDetail'
    
    def get_status_color(self, obj):
        colors = {
            'IN_STOCK': '#6B7280',
            'ASSIGNED': '#F59E0B',
            'IN_USE': '#10B981',
            'NEED_CLARIFICATION': '#8B5CF6',
            'IN_REPAIR': '#EF4444',
            'OUT_OF_STOCK': '#DC2626',
            'ARCHIVED': '#7F1D1D',
        }
        return colors.get(obj.status, '#6B7280')
    
    def get_current_assignment(self, obj):
        return obj.get_current_assignment()
    
    def get_clarification_info(self, obj):
        if obj.status == 'NEED_CLARIFICATION' or obj.clarification_requested_reason:
            return {
                'requested_reason': obj.clarification_requested_reason,
                'requested_at': obj.clarification_requested_at,
                'response': obj.clarification_response,
                'provided_at': obj.clarification_provided_at,
                'is_pending': bool(obj.clarification_requested_reason and not obj.clarification_response)
            }
        return None
    
    def get_assignments(self, obj):
        from .asset_serializers import AssetAssignmentSerializer
        assignments = obj.assignments.all()[:10]
        return AssetAssignmentSerializer(assignments, many=True, context=self.context).data
    
    def get_activities(self, obj):
        from .asset_serializers import AssetActivitySerializer
        activities = obj.activities.all()[:20]
        return AssetActivitySerializer(activities, many=True, context=self.context).data
    
    def get_can_be_assigned(self, obj):
        return obj.can_be_assigned()
    
    def get_can_be_approved(self, obj):
        return obj.can_be_approved()
    
    def get_can_be_checked_in(self, obj):
        return obj.can_be_checked_in()


class AssetCreateSerializer(serializers.Serializer):
    """
    🎯 Individual Asset yaratma - Batch-dən
    
    ⚠️ DİQQƏT: Asset yaradanda batch-in quantity-si avtomatik azalır!
    
    Nümunə:
    {
        "batch_id": 5,
        "serial_number": "SN123456789"
    }
    
    Prosess:
    1. Batch-in available_quantity yoxlanılır
    2. Asset yaradılır
    3. Batch-in available_quantity 1 azalır (assign_quantity)
    4. Asset IN_STOCK statusunda olur
    """
    
    batch_id = serializers.IntegerField(help_text="Batch ID")
    serial_number = serializers.CharField(
        max_length=100,
        help_text="Serial nömrə (unikal olmalıdır)"
    )
    
    class Meta:
        ref_name = 'AssetCreate'
    
    def validate_batch_id(self, value):
        """Batch mövcud və aktiv olmalıdır"""
        try:
            batch = AssetBatch.objects.get(id=value)
            if batch.status != 'ACTIVE':
                raise serializers.ValidationError(
                    f"Batch aktiv deyil. Status: {batch.get_status_display()}"
                )
            if batch.available_quantity <= 0:
                raise serializers.ValidationError(
                    f"Batch-də mövcud asset yoxdur (Available: {batch.available_quantity})"
                )
            return value
        except AssetBatch.DoesNotExist:
            raise serializers.ValidationError("Batch tapılmadı")
    
    def validate_serial_number(self, value):
        """Serial nömrə unikal olmalıdır"""
        if Asset.objects.filter(serial_number=value).exists():
            raise serializers.ValidationError(
                f"'{value}' serial nömrəli asset artıq mövcuddur"
            )
        return value
    
    def create(self, validated_data):
        """
        🎯 Asset yaradılır və batch-dən 1 say çıxılır
        """
        batch_id = validated_data['batch_id']
        serial_number = validated_data['serial_number']
        
        batch = AssetBatch.objects.get(id=batch_id)
        
        with transaction.atomic():
            # 1️⃣ Batch-dən say azalt (available_quantity → assigned_quantity deyil, sadəcə available azalır)
            # Çünki asset hələ IN_STOCK-dadır, təyin edilməyib
            if not batch.assign_quantity(1):
                raise serializers.ValidationError(
                    f"Batch {batch.batch_number} - kifayət qədər say yoxdur"
                )
            
            # 2️⃣ Asset yarat
            asset = Asset.objects.create(
                batch=batch,
                serial_number=serial_number,
                status='IN_STOCK',
                created_by=self.context['request'].user
            )
            
            logger.info(
                f"✅ Asset yaradıldı: {asset.asset_number} | "
                f"Batch: {batch.batch_number} | "
                f"Available: {batch.available_quantity}/{batch.initial_quantity}"
            )
        
        return asset


class AssetCreateMultipleSerializer(serializers.Serializer):
    """
    🎯 Batch-dən bir neçə asset yaratma
    
    Nümunə:
    {
        "batch_id": 5,
        "serial_numbers": ["SN001", "SN002", "SN003"]
    }
    """
    
    batch_id = serializers.IntegerField()
    serial_numbers = serializers.ListField(
        child=serializers.CharField(max_length=100),
        help_text="Serial nömrələr siyahısı"
    )
    
    class Meta:
        ref_name = 'AssetCreateMultiple'
    
    def validate(self, attrs):
        batch_id = attrs['batch_id']
        serial_numbers = attrs['serial_numbers']
        quantity = len(serial_numbers)
        
        # Batch yoxla
        try:
            batch = AssetBatch.objects.get(id=batch_id)
        except AssetBatch.DoesNotExist:
            raise serializers.ValidationError({"batch_id": "Batch tapılmadı"})
        
        # Batch status yoxla
        if batch.status != 'ACTIVE':
            raise serializers.ValidationError({
                "batch_id": f"Batch aktiv deyil: {batch.get_status_display()}"
            })
        
        # Quantity yoxla
        if batch.available_quantity < quantity:
            raise serializers.ValidationError({
                "serial_numbers": f"Batch-də {quantity} ədəd yoxdur. Mövcud: {batch.available_quantity}"
            })
        
        # Serial nömrələr unikal olmalıdır
        existing = Asset.objects.filter(serial_number__in=serial_numbers).values_list('serial_number', flat=True)
        if existing:
            raise serializers.ValidationError({
                "serial_numbers": f"Bu serial nömrələr artıq mövcuddur: {list(existing)}"
            })
        
        # Duplicate serial nömrələr olmamalıdır
        if len(serial_numbers) != len(set(serial_numbers)):
            raise serializers.ValidationError({
                "serial_numbers": "Serial nömrələr təkrarlanmamalıdır"
            })
        
        attrs['batch'] = batch
        attrs['quantity'] = quantity
        return attrs
    
    def create(self, validated_data):
        """Bir neçə asset yaradılır"""
        batch = validated_data['batch']
        serial_numbers = validated_data['serial_numbers']
        quantity = validated_data['quantity']
        user = self.context['request'].user
        
        created_assets = []
        
        with transaction.atomic():
            # Batch-dən say azalt
            if not batch.assign_quantity(quantity):
                raise serializers.ValidationError(
                    f"Batch {batch.batch_number} - kifayət qədər say yoxdur"
                )
            
            # Asset-ləri yarat
            for serial_number in serial_numbers:
                asset = Asset.objects.create(
                    batch=batch,
                    serial_number=serial_number,
                    status='IN_STOCK',
                    created_by=user
                )
                created_assets.append(asset)
                
                # Activity log
                AssetActivity.objects.create(
                    asset=asset,
                    activity_type='CREATED',
                    description=f"Asset batch-dən yaradıldı: {batch.batch_number}",
                    performed_by=user,
                    metadata={'batch_number': batch.batch_number, 'batch_id': batch.id}
                )
        
        logger.info(
            f"✅ {quantity} asset yaradıldı | "
            f"Batch: {batch.batch_number} | "
            f"Available: {batch.available_quantity}/{batch.initial_quantity}"
        )
        
        return created_assets


# ============================================
# ASSIGNMENT SERIALIZERS
# ============================================

class AssetAssignmentSerializer(serializers.ModelSerializer):
    """Assignment detail"""
    employee_detail = AssetEmployeeBasicSerializer(source='employee', read_only=True)
    asset_detail = serializers.SerializerMethodField()
    assigned_by_detail = AssetUserBasicSerializer(source='assigned_by', read_only=True)
    duration_days = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    
    class Meta:
        model = AssetAssignment
        fields = [
            'id', 'asset', 'asset_detail', 'employee', 'employee_detail',
            'check_out_date', 'check_in_date',
            'check_out_notes', 'check_in_notes',
            'condition_on_checkout', 'condition_on_checkin',
            'assigned_by_detail', 'duration_days', 'is_active',
            'created_at', 'updated_at'
        ]
        ref_name = 'AssetAssignment'
    
    def get_asset_detail(self, obj):
        return {
            'id': str(obj.asset.id),
            'asset_number': obj.asset.asset_number,
            'asset_name': obj.asset.asset_name,
            'serial_number': obj.asset.serial_number
        }
    
    def get_duration_days(self, obj):
        return obj.get_duration_days()
    
    def get_is_active(self, obj):
        return obj.is_active()


class AssetAssignmentCreateSerializer(serializers.Serializer):
    """
    🎯 Asset-ləri işçiyə təyin etmə
    
    ⚠️ DİQQƏT: Batch quantity-si burada dəyişmir!
    Batch-dən asset yaradanda artıq azaldılıb.
    
    Burada yalnız:
    1. Asset status: IN_STOCK → ASSIGNED
    2. Asset assigned_to = employee
    3. Assignment record yaradılır
    """
    
    asset_ids = serializers.ListField(
        child=serializers.UUIDField(),
        help_text="Asset ID-lər siyahısı"
    )
    employee_id = serializers.IntegerField()
    check_out_date = serializers.DateField()
    check_out_notes = serializers.CharField(required=False, allow_blank=True)
    condition_on_checkout = serializers.ChoiceField(
        choices=['EXCELLENT', 'GOOD', 'FAIR', 'POOR'],
        default='GOOD'
    )
    
    class Meta:
        ref_name = 'AssetAssignmentCreate'
    
    def validate(self, attrs):
        # Employee yoxla
        try:
            employee = Employee.objects.get(id=attrs['employee_id'], is_deleted=False)
            attrs['employee'] = employee
        except Employee.DoesNotExist:
            raise serializers.ValidationError({"employee_id": "İşçi tapılmadı"})
        
        # Asset-ləri yoxla
        assets = Asset.objects.filter(id__in=attrs['asset_ids'])
        if assets.count() != len(attrs['asset_ids']):
            raise serializers.ValidationError({"asset_ids": "Bəzi asset-lər tapılmadı"})
        
        # Asset-lər təyin edilə bilərmi?
        for asset in assets:
            if not asset.can_be_assigned():
                raise serializers.ValidationError({
                    "asset_ids": f"Asset {asset.asset_number} təyin edilə bilməz. Status: {asset.get_status_display()}"
                })
        
        attrs['assets'] = list(assets)
        return attrs


class AssetActivitySerializer(serializers.ModelSerializer):
    """Activity log"""
    performed_by_detail = AssetUserBasicSerializer(source='performed_by', read_only=True)
    activity_display = serializers.CharField(source='get_activity_type_display', read_only=True)
    
    class Meta:
        model = AssetActivity
        fields = [
            'id', 'activity_type', 'activity_display', 'description',
            'performed_by_detail', 'performed_at', 'metadata'
        ]
        ref_name = 'AssetActivity'


# ============================================
# EMPLOYEE ACTION SERIALIZERS
# ============================================

class AssetAcceptanceSerializer(serializers.Serializer):
    """İşçi asset-i qəbul edir"""
    
    asset_id = serializers.UUIDField()
    comments = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        ref_name = 'AssetAcceptance'


class AssetClarificationRequestSerializer(serializers.Serializer):
    """İşçi aydınlaşdırma sorğusu göndərir"""
    
    asset_id = serializers.UUIDField()
    clarification_reason = serializers.CharField(max_length=1000)
    
    class Meta:
        ref_name = 'AssetClarificationRequest'


class AssetCancellationSerializer(serializers.Serializer):
    """Admin/IT assignment-i ləğv edir"""
    
    asset_id = serializers.UUIDField()
    cancellation_reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
    
    class Meta:
        ref_name = 'AssetCancellation'


class AssetClarificationProvisionSerializer(serializers.Serializer):
    """Admin/Manager aydınlaşdırma cavabı verir"""
    
    asset_id = serializers.UUIDField()
    clarification_response = serializers.CharField(max_length=1000)
    
    class Meta:
        ref_name = 'AssetClarificationProvision'


# ============================================
# OFFBOARDING SERIALIZERS
# ============================================

class EmployeeOffboardingSerializer(serializers.ModelSerializer):
    """Offboarding detail"""
    employee_detail = AssetEmployeeBasicSerializer(source='employee', read_only=True)
    created_by_detail = AssetUserBasicSerializer(source='created_by', read_only=True)
    approved_by_detail = AssetUserBasicSerializer(source='approved_by', read_only=True)
    it_handover_completed_by_detail = AssetUserBasicSerializer(
        source='it_handover_completed_by', 
        read_only=True
    )
    progress_percentage = serializers.SerializerMethodField()
    offboarding_type_display = serializers.CharField(
        source='get_offboarding_type_display', 
        read_only=True
    )
    
    class Meta:
        model = EmployeeOffboarding
        fields = [
            'id', 'employee', 'employee_detail', 'last_working_day',
            'offboarding_type', 'offboarding_type_display',
            'total_assets', 'assets_transferred', 'assets_returned',
            'progress_percentage', 'status',
            'it_handover_completed', 'it_handover_completed_at', 
            'it_handover_completed_by_detail',
            'approved_by_detail', 'approved_at', 'notes',
            'created_by_detail', 'created_at', 'completed_at'
        ]
        ref_name = 'EmployeeOffboarding'
    
    def get_progress_percentage(self, obj):
        if obj.total_assets == 0:
            return 100
        
        if obj.offboarding_type == 'TRANSFER':
            completed = obj.assets_transferred
        else:
            # RETURN - use it_handover_completed
            return 100 if obj.it_handover_completed else 0
        
        return round((completed / obj.total_assets) * 100, 1)


class AssetTransferRequestSerializer(serializers.ModelSerializer):
    """Transfer request detail"""
    from_employee_detail = AssetEmployeeBasicSerializer(source='from_employee', read_only=True)
    to_employee_detail = AssetEmployeeBasicSerializer(source='to_employee', read_only=True)
    asset_detail = serializers.SerializerMethodField()
    requested_by_detail = AssetUserBasicSerializer(source='requested_by', read_only=True)
    approved_by_detail = AssetUserBasicSerializer(source='approved_by', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = AssetTransferRequest
        fields = [
            'id', 'offboarding', 'asset', 'asset_detail',
            'from_employee', 'from_employee_detail',
            'to_employee', 'to_employee_detail',
            'status', 'status_display',
            'employee_approved', 'employee_approved_at',
            'requested_by_detail', 'requested_at',
            'approved_by_detail', 'approved_at',
            'rejection_reason', 'transfer_notes', 'completed_at'
        ]
        ref_name = 'AssetTransferRequest'
    
    def get_asset_detail(self, obj):
        return {
            'id': str(obj.asset.id),
            'asset_number': obj.asset.asset_number,
            'asset_name': obj.asset.asset_name,
            'serial_number': obj.asset.serial_number,
            'status': obj.asset.status,
            'status_display': obj.asset.get_status_display()
        }


class AssetTransferRequestCreateSerializer(serializers.Serializer):
    """Transfer request yaradılması"""
    
    asset_id = serializers.UUIDField()
    to_employee_id = serializers.IntegerField()
    transfer_notes = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        ref_name = 'AssetTransferRequestCreate'
    
    def validate(self, attrs):
        # Asset yoxla
        try:
            asset = Asset.objects.get(id=attrs['asset_id'])
            if not asset.assigned_to:
                raise serializers.ValidationError({"asset_id": "Asset hal-hazırda təyin edilməyib"})
            attrs['asset'] = asset
            attrs['from_employee'] = asset.assigned_to
        except Asset.DoesNotExist:
            raise serializers.ValidationError({"asset_id": "Asset tapılmadı"})
        
        # To employee yoxla
        try:
            to_employee = Employee.objects.get(id=attrs['to_employee_id'], is_deleted=False)
            attrs['to_employee'] = to_employee
        except Employee.DoesNotExist:
            raise serializers.ValidationError({"to_employee_id": "İşçi tapılmadı"})
        
        # Eyni işçiyə transfer edilə bilməz
        if attrs['from_employee'].id == attrs['to_employee'].id:
            raise serializers.ValidationError({"to_employee_id": "Eyni işçiyə transfer edilə bilməz"})
        
        return attrs


# ============================================
# BULK UPLOAD SERIALIZER
# ============================================

class AssetBulkUploadSerializer(serializers.Serializer):
    """Excel/CSV-dən bulk upload"""
    
    file = serializers.FileField()
    
    class Meta:
        ref_name = 'AssetBulkUpload'
    
    def validate_file(self, value):
        allowed_extensions = ['.xlsx', '.xls', '.csv']
        file_extension = value.name[value.name.rfind('.'):].lower()
        if file_extension not in allowed_extensions:
            raise serializers.ValidationError(
                f"Yalnız bu formatlar qəbul edilir: {', '.join(allowed_extensions)}"
            )
        
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Fayl ölçüsü 10MB-dan çox ola bilməz")
        
        return value