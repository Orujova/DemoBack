from rest_framework import serializers
from .vacation_models import *
from .models import Employee

# ============= SETTINGS SERIALIZERS =============

class ProductionCalendarSerializer(serializers.Serializer):
    """✅ ENHANCED: Dual Production Calendar serializer"""
    non_working_days_az = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(),
            required=True
        ),
        required=False,
        help_text="Azerbaijan qeyri-iş günlərinin siyahısı"
    )
    non_working_days_uk = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(),
            required=True
        ),
        required=False,
        help_text="UK qeyri-iş günlərinin siyahısı"
    )
    
    def validate_non_working_days_az(self, value):
        """Tarixlərin düzgünlüyünü yoxla"""
        return self._validate_non_working_days(value, 'Azerbaijan')
    
    def validate_non_working_days_uk(self, value):
        """Tarixlərin düzgünlüyünü yoxla"""
        return self._validate_non_working_days(value, 'UK')
    
    def _validate_non_working_days(self, value, country):
        """Ümumi validation məntiqi"""
        if not isinstance(value, list):
            raise serializers.ValidationError(f"{country} non working days siyahı olmalıdır")
        
        dates_seen = set()
        for item in value:
            if not isinstance(item, dict):
                raise serializers.ValidationError("Hər element dict formatında olmalıdır")
            
            if 'date' not in item:
                raise serializers.ValidationError("Date field mütləqdir")
            
            if 'name' not in item:
                item['name'] = ''
            
            # Date formatını yoxla
            try:
                from datetime import datetime
                datetime.strptime(item['date'], '%Y-%m-%d')
            except ValueError:
                raise serializers.ValidationError(
                    f"Date format səhvdir: {item['date']}. YYYY-MM-DD istifadə edin"
                )
            
            # Duplicate yoxla
            if item['date'] in dates_seen:
                raise serializers.ValidationError(f"Təkrarlanan tarix: {item['date']}")
            dates_seen.add(item['date'])
        
        return value


class GeneralVacationSettingsSerializer(serializers.Serializer):
    """General Vacation Settings serializer"""
    allow_negative_balance = serializers.BooleanField(
        required=False,
        help_text="Balans 0 olduqda request yaratmağa icazə ver"
    )
    max_schedule_edits = serializers.IntegerField(
        required=False,
        min_value=0,
        help_text="Schedule neçə dəfə edit oluna bilər"
    )
    notification_days_before = serializers.IntegerField(
        required=False,
        min_value=1,
        help_text="Məzuniyyət başlamazdan neçə gün əvvəl bildiriş göndər"
    )
    notification_frequency = serializers.IntegerField(
        required=False,
        min_value=1,
        help_text="Bildirişi neçə dəfə göndər"
    )


class UKAdditionalApproverSerializer(serializers.Serializer):
    """✅ FIXED: UK Additional Approver serializer"""
    uk_additional_approver_id = serializers.IntegerField(
        help_text="UK Additional Approver Employee ID (Position Group: Vice Chairman)"
    )
    
    def validate_uk_additional_approver_id(self, value):
        """UK approver mövcudluğunu yoxla"""
        try:
            employee = Employee.objects.get(id=value, is_deleted=False)
            
            # ✅ FIXED: Check for both full name and abbreviation
            if employee.position_group:
                position_name = employee.position_group.name.lower().strip()
                
                # Check if contains any of these variations
                valid_positions = [
                    'vc',                # ✅ Added abbreviation
                    'vice chairman',
                    'vice-chairman', 
                    'vicechairman',
                    'vice chair',
                    'deputy chairman'
                ]
                
                is_valid_position = any(
                    pos == position_name or pos in position_name 
                    for pos in valid_positions
                )
                
                if not is_valid_position:
                    raise serializers.ValidationError(
                        f"Seçilən işçi Vice Chairman (VC) position group-da deyil. "
                        f"Cari position: {employee.position_group.name}"
                    )
            else:
                raise serializers.ValidationError(
                    "Seçilən işçinin position group məlumatı yoxdur"
                )
            
            return value
            
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Approver tapılmadı")
class HRRepresentativeSerializer(serializers.Serializer):
    """HR Representative serializer"""
    default_hr_representative_id = serializers.IntegerField(
        help_text="Default HR nümayəndəsi Employee ID"
    )
    class Meta:
        ref_name = 'VacationHRRepresentative' 
    def validate_default_hr_representative_id(self, value):
        """HR employee mövcudluğunu yoxla"""
        try:
            employee = Employee.objects.get(id=value, is_deleted=False)
            return value
        except Employee.DoesNotExist:
            raise serializers.ValidationError("HR nümayəndəsi tapılmadı")


class VacationSettingSerializer(serializers.ModelSerializer):
    """✅ ENHANCED: Complete Vacation Settings serializer"""
    class Meta:
        model = VacationSetting
        fields = [
            'id', 'non_working_days_az', 'non_working_days_uk',
            'default_hr_representative', 'uk_additional_approver',
            'allow_negative_balance', 'max_schedule_edits', 
            'notification_days_before', 'notification_frequency', 'is_active'
        ]
        read_only_fields = ['created_by', 'updated_by']


# ============= VACATION TYPE =============

class VacationTypeSerializer(serializers.ModelSerializer):
    """✅ ENHANCED: Vacation Type with UK-specific fields"""
    
    class Meta:
        model = VacationType
        fields = [
            'id', 'name', 'description', 
            'is_uk_only', 'requires_time_selection',
            'is_active'
        ]
        read_only_fields = ['created_by', 'updated_by']


class VacationTypeListSerializer(serializers.ModelSerializer):
    """✅ NEW: Filtered list based on user's business function"""
    
    class Meta:
        model = VacationType
        fields = ['id', 'name', 'description', 'is_uk_only', 'requires_time_selection']
    
    def to_representation(self, instance):
        """Filter based on user context"""
        data = super().to_representation(instance)
        
        # Get user from context
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            try:
                employee = Employee.objects.get(user=request.user, is_deleted=False)
                is_uk = False
                
                if employee.business_function:
                    code = getattr(employee.business_function, 'code', '')
                    is_uk = code.upper() == 'UK'
                
                # Əgər UK deyilsə və type UK-only-dirsə, None qaytarırıq
                if instance.is_uk_only and not is_uk:
                    return None
                
            except Employee.DoesNotExist:
                # UK-only types-ı gizlət
                if instance.is_uk_only:
                    return None
        
        return data


# ============= REQUEST SERIALIZERS =============

class VacationRequestListSerializer(serializers.ModelSerializer):
    """✅ ENHANCED: List serializer for vacation requests"""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    department_name = serializers.CharField(source='employee.department.name', read_only=True)
    business_function_name = serializers.CharField(
        source='employee.business_function.name', 
        read_only=True
    )
    business_function_code = serializers.SerializerMethodField()
    vacation_type_name = serializers.CharField(source='vacation_type.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    attachments_count = serializers.SerializerMethodField()
    is_uk = serializers.SerializerMethodField()
    requires_uk_approval = serializers.SerializerMethodField()
    
    class Meta:
        model = VacationRequest
        fields = [
            'id', 'request_id', 'employee_name', 'employee_id', 
            'department_name', 'business_function_name', 'business_function_code',
            'vacation_type_name', 'start_date', 'end_date', 'return_date', 
            'number_of_days', 'status', 'status_display', 'comment', 
            'attachments_count', 'is_uk', 'requires_uk_approval',
            'is_half_day', 'half_day_start_time', 'half_day_end_time',
            'created_at'
        ]
    
    def get_business_function_code(self, obj):
        return obj.get_business_function_code()
    
    def get_attachments_count(self, obj):
        return obj.attachments.filter(is_deleted=False).count()
    
    def get_is_uk(self, obj):
        return obj.is_uk_employee()
    
    def get_requires_uk_approval(self, obj):
        return obj.requires_uk_additional_approval()


class VacationRequestDetailSerializer(serializers.ModelSerializer):
    """✅ ENHANCED: Detailed serializer with UK approval chain"""
    employee_info = serializers.SerializerMethodField()
    vacation_type_detail = VacationTypeSerializer(source='vacation_type', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Approvers
    line_manager_name = serializers.CharField(source='line_manager.full_name', read_only=True)
    uk_additional_approver_name = serializers.CharField(
        source='uk_additional_approver.full_name', 
        read_only=True
    )
    hr_representative_name = serializers.CharField(
        source='hr_representative.full_name', 
        read_only=True
    )
    
    # Attachments
    attachments = serializers.SerializerMethodField()
    
    # UK specific
    is_uk = serializers.SerializerMethodField()
    requires_uk_approval = serializers.SerializerMethodField()
    
    class Meta:
        model = VacationRequest
        fields = [
            'id', 'request_id', 'employee_info', 'vacation_type_detail', 
            'start_date', 'end_date', 'return_date', 'number_of_days', 
            'comment', 'status', 'status_display',
            'is_half_day', 'half_day_start_time', 'half_day_end_time',
            'is_uk', 'requires_uk_approval',
            'line_manager_name', 'line_manager_comment', 'line_manager_approved_at',
            'uk_additional_approver_name', 'uk_additional_comment', 'uk_additional_approved_at',
            'hr_representative_name', 'hr_comment', 'hr_approved_at',
            'rejection_reason', 'rejected_at', 
            'attachments', 'created_at', 'updated_at'
        ]
    
    def get_employee_info(self, obj):
        return {
            'id': obj.employee.id,
            'name': obj.employee.full_name,
            'employee_id': getattr(obj.employee, 'employee_id', ''),
            'department': obj.employee.department.name if obj.employee.department else None,
            'business_function': obj.employee.business_function.name if obj.employee.business_function else None,
            'business_function_code': obj.get_business_function_code(),
            'unit': obj.employee.unit.name if obj.employee.unit else None,
            'job_function': obj.employee.job_function.name if obj.employee.job_function else None,
            'phone': obj.employee.phone
        }
    
    def get_attachments(self, obj):
        attachments = obj.attachments.filter(is_deleted=False).order_by('-uploaded_at')
        return VacationAttachmentSerializer(
            attachments,
            many=True,
            context=self.context
        ).data
    
    def get_is_uk(self, obj):
        return obj.is_uk_employee()
    
    def get_requires_uk_approval(self, obj):
        return obj.requires_uk_additional_approval()


class VacationRequestCreateSerializer(serializers.Serializer):
    """✅ ENHANCED: Serializer for creating vacation requests with half-day support"""
    requester_type = serializers.ChoiceField(choices=['for_me', 'for_my_employee'])
    employee_id = serializers.IntegerField(required=False)
    employee_manual = serializers.DictField(required=False)
    vacation_type_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False)  # ✅ Half day üçün optional
    comment = serializers.CharField(required=False, allow_blank=True)
    hr_representative_id = serializers.IntegerField(required=False)
    
    # ✅ HALF DAY FIELDS
    is_half_day = serializers.BooleanField(required=False, default=False)
    half_day_start_time = serializers.TimeField(required=False, allow_null=True)
    half_day_end_time = serializers.TimeField(required=False, allow_null=True)
    
    def validate(self, data):
        # Employee validation
        if data['requester_type'] == 'for_my_employee':
            if not data.get('employee_id') and not data.get('employee_manual'):
                raise serializers.ValidationError(
                    "For my employee seçildikdə employee_id və ya employee_manual məlumatları lazımdır"
                )
        
        # Vacation type mövcudluğu
        try:
            vac_type = VacationType.objects.get(
                id=data['vacation_type_id'], 
                is_active=True, 
                is_deleted=False
            )
            
            # ✅ Half day validation
            if data.get('is_half_day'):
                if not vac_type.requires_time_selection:
                    raise serializers.ValidationError(
                        "Bu vacation type half day dəstəkləmir"
                    )
                
                if not data.get('half_day_start_time') or not data.get('half_day_end_time'):
                    raise serializers.ValidationError(
                        "Half day üçün start_time və end_time mütləqdir"
                    )
                
                if data['half_day_start_time'] >= data['half_day_end_time']:
                    raise serializers.ValidationError(
                        "Start time end time-dan kiçik olmalıdır"
                    )
                
                # Half day üçün end_date istənmir
                if not data.get('end_date'):
                    data['end_date'] = data['start_date']
                elif data['end_date'] != data['start_date']:
                    raise serializers.ValidationError(
                        "Half day üçün start və end date eyni olmalıdır"
                    )
            
            else:
                # Normal vacation - end_date mütləqdir
                if not data.get('end_date'):
                    raise serializers.ValidationError(
                        "End date mütləqdir (Half day deyilsə)"
                    )
                
                if data['start_date'] >= data['end_date']:
                    raise serializers.ValidationError(
                        "End date start date-dən böyük olmalıdır"
                    )
        
        except VacationType.DoesNotExist:
            raise serializers.ValidationError("Vacation type tapılmadı və ya aktiv deyil")
        
        return data


class VacationApprovalSerializer(serializers.Serializer):
    """Serializer for approval/rejection actions"""
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    comment = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        if data['action'] == 'reject' and not data.get('reason'):
            raise serializers.ValidationError("Reject edərkən səbəb mütləqdir")
        return data


# ============= BALANCE SERIALIZER =============

class EmployeeVacationBalanceSerializer(serializers.ModelSerializer):
    """Employee vacation balance serializer"""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    department_name = serializers.CharField(source='employee.department.name', read_only=True)
    business_function_name = serializers.CharField(
        source='employee.business_function.name', 
        read_only=True
    )
    business_function_code = serializers.SerializerMethodField()
   
    
    total_balance = serializers.ReadOnlyField()
    remaining_balance = serializers.ReadOnlyField()
    available_for_planning = serializers.ReadOnlyField()  # ✅ NEW
    should_be_planned = serializers.ReadOnlyField()
    
    class Meta:
        model = EmployeeVacationBalance
        fields = [
            'id', 'employee', 'employee_name', 'employee_id', 
            'department_name', 'business_function_name', 'business_function_code',
            'year', 'start_balance', 'yearly_balance', 
            'used_days', 'scheduled_days', 
            'total_balance', 'remaining_balance', 
            'available_for_planning',  # ✅ NEW
            'should_be_planned', 
            'updated_at'
        ]
    
    def get_business_function_code(self, obj):
        if obj.employee.business_function:
            return getattr(obj.employee.business_function, 'code', None)
        return None


# ============= ATTACHMENT SERIALIZER =============

class VacationAttachmentSerializer(serializers.ModelSerializer):
    """Vacation attachment serializer with file URLs"""
    file_url = serializers.SerializerMethodField()
    file_size_display = serializers.ReadOnlyField()
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
    class Meta:
        model = VacationAttachment
        fields = [
            'id', 'file', 'file_url', 'original_filename', 
            'file_size', 'file_size_display', 'file_type', 
            'uploaded_by_name', 'uploaded_at'
        ]
        read_only_fields = ['file_size', 'uploaded_by', 'uploaded_at']
    
    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and hasattr(obj.file, 'url'):
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


# ============= SCHEDULE SERIALIZERS =============


class VacationScheduleSerializer(serializers.ModelSerializer):
    """List serializer for vacation schedules"""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    department_name = serializers.CharField(source='employee.department.name', read_only=True)
    vacation_type_name = serializers.CharField(source='vacation_type.name', read_only=True)
    vacation_type_detail = VacationTypeSerializer(source='vacation_type', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    can_edit = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    last_edited_by_name = serializers.CharField(source='last_edited_by.get_full_name', read_only=True)
    
    class Meta:
        model = VacationSchedule
        fields = [
            'id', 'employee_name', 'employee_id', 'department_name', 
            'vacation_type_name', 'vacation_type_detail',
            'start_date', 'end_date', 'return_date', 'number_of_days', 
            'status', 'status_display',
            'edit_count', 'can_edit', 
            'created_by_name', 'last_edited_by_name',
            'last_edited_at',
            'comment', 'created_at', 'updated_at'
        ]
    
    def get_can_edit(self, obj):
        return obj.can_edit()


class VacationScheduleCreateSerializer(serializers.Serializer):
    """Serializer for creating vacation schedules"""
    requester_type = serializers.ChoiceField(choices=['for_me', 'for_my_employee'])
    employee_id = serializers.IntegerField(required=False)
    employee_manual = serializers.DictField(required=False)
    vacation_type_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    comment = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        if data['requester_type'] == 'for_my_employee':
            if not data.get('employee_id') and not data.get('employee_manual'):
                raise serializers.ValidationError(
                    "For my employee seçildikdə employee_id və ya employee_manual məlumatları lazımdır"
                )
        
        # ✅ FIXED: Allow single day schedules
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("End date start date-dən kiçik ola bilməz")
        
        try:
            VacationType.objects.get(id=data['vacation_type_id'], is_active=True, is_deleted=False)
        except VacationType.DoesNotExist:
            raise serializers.ValidationError("Vacation type tapılmadı və ya aktiv deyil")
        
        return data


class VacationScheduleEditSerializer(serializers.ModelSerializer):
    """Serializer for editing vacation schedules"""
    class Meta:
        model = VacationSchedule
        fields = ['vacation_type', 'start_date', 'end_date', 'comment']
    
    def validate(self, data):
        # ✅ FIXED: Allow single day schedules
        if 'start_date' in data and 'end_date' in data:
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError("End date start date-dən kiçik ola bilməz")
        return data
