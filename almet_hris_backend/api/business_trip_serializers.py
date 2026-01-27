# api/business_trip_serializers.py
from rest_framework import serializers
from .business_trip_models import *
from .models import Employee

# ============= SETTINGS SERIALIZERS =============

class TravelTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TravelType
        fields = ['id', 'name', 'description', 'is_active']
        read_only_fields = ['created_by', 'updated_by']

class TransportTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransportType
        fields = ['id', 'name', 'description', 'is_active']
        read_only_fields = ['created_by', 'updated_by']

class TripPurposeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TripPurpose
        fields = ['id', 'name', 'description', 'is_active']
        read_only_fields = ['created_by', 'updated_by']

class TripSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TripSettings
        fields = [
            'id', 'default_hr_representative', 'default_finance_approver',
            'notification_days_before', 'is_active'
        ]
        read_only_fields = ['created_by', 'updated_by']

class HRRepresentativeSerializer(serializers.Serializer):
    """HR Representative serializer"""
    default_hr_representative_id = serializers.IntegerField(
        help_text="Default HR representative Employee ID"
    )
    
    def validate_default_hr_representative_id(self, value):
        """Validate HR employee exists"""
        try:
            employee = Employee.objects.get(id=value, is_deleted=False)
            return value
        except Employee.DoesNotExist:
            raise serializers.ValidationError("HR representative not found")

class FinanceApproverSerializer(serializers.Serializer):
    """Finance Approver serializer"""
    default_finance_approver_id = serializers.IntegerField(
        help_text="Default Finance/Payroll approver Employee ID"
    )
    
    def validate_default_finance_approver_id(self, value):
        """Validate Finance employee exists"""
        try:
            employee = Employee.objects.get(id=value, is_deleted=False)
            return value
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Finance approver not found")

class GeneralTripSettingsSerializer(serializers.Serializer):
    """General Trip Settings serializer"""
    notification_days_before = serializers.IntegerField(required=False, min_value=1)

# ============= ATTACHMENT SERIALIZERS =============

class TripAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    file_size_display = serializers.ReadOnlyField()
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
    class Meta:
        model = TripAttachment
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

class TripAttachmentUploadSerializer(serializers.Serializer):
    """Serializer for uploading attachments"""
    file = serializers.FileField(required=True)
   
    
    def validate_file(self, value):
        """Validate file size and type"""
        # Max file size: 10MB
        max_size = 10 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(f"File size must not exceed 10MB. Current size: {value.size / (1024*1024):.2f}MB")
        
        # Allowed file types
        allowed_types = [
            'application/pdf',
            'image/jpeg', 'image/jpg', 'image/png',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        ]
        
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                f"File type not allowed. Allowed types: PDF, JPG, PNG, DOC, DOCX, XLS, XLSX"
            )
        
        return value

# ============= SCHEDULE & HOTEL SERIALIZERS =============

class TripScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TripSchedule
        fields = ['id', 'date', 'from_location', 'to_location', 'order', 'notes']

class TripHotelSerializer(serializers.ModelSerializer):
    nights_count = serializers.ReadOnlyField()
    
    class Meta:
        model = TripHotel
        fields = ['id', 'hotel_name', 'check_in_date', 'check_out_date', 'location', 'notes', 'nights_count']

# ============= REQUEST SERIALIZERS =============

class BusinessTripRequestListSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    department_name = serializers.CharField(source='employee.department.name', read_only=True)
    travel_type_name = serializers.CharField(source='travel_type.name', read_only=True)
    transport_type_name = serializers.CharField(source='transport_type.name', read_only=True)
    purpose_name = serializers.CharField(source='purpose.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    attachments_count = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessTripRequest
        fields = [
            'id', 'request_id', 'employee_name', 'employee_id', 'department_name',
            'travel_type_name', 'transport_type_name', 'purpose_name',
            'start_date', 'end_date', 'return_date', 'number_of_days',
            'status', 'status_display', 'finance_amount', 'comment', 
            'attachments_count', 'created_at'
        ]
    
    def get_attachments_count(self, obj):
        return obj.attachments.filter(is_deleted=False).count()

class BusinessTripRequestDetailSerializer(serializers.ModelSerializer):
    employee_info = serializers.SerializerMethodField()
    travel_type_detail = TravelTypeSerializer(source='travel_type', read_only=True)
    transport_type_detail = TransportTypeSerializer(source='transport_type', read_only=True)
    purpose_detail = TripPurposeSerializer(source='purpose', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    line_manager_name = serializers.CharField(source='line_manager.full_name', read_only=True)
    finance_approver_name = serializers.CharField(source='finance_approver.full_name', read_only=True)
    hr_representative_name = serializers.CharField(source='hr_representative.full_name', read_only=True)
    
    schedules = TripScheduleSerializer(many=True, read_only=True)
    hotels = TripHotelSerializer(many=True, read_only=True)
    attachments = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessTripRequest
        fields = [
            'id', 'request_id', 'employee_info', 'travel_type_detail', 'transport_type_detail',
            'purpose_detail', 'start_date', 'end_date', 'return_date', 'number_of_days',
            'comment', 'status', 'status_display',
            'line_manager_name', 'line_manager_comment', 'line_manager_approved_at',
            'finance_approver_name', 'finance_amount', 'finance_comment', 'finance_approved_at',
            'hr_representative_name', 'hr_comment', 'hr_approved_at',
            'rejection_reason', 'rejected_at',
            'schedules', 'hotels', 'attachments', 'created_at', 'updated_at'
        ]
    
    def get_employee_info(self, obj):
        return {
            'id': obj.employee.id,
            'name': obj.employee.full_name,
            'employee_id': getattr(obj.employee, 'employee_id', ''),
            'department': obj.employee.department.name if obj.employee.department else None,
            'business_function': obj.employee.business_function.name if obj.employee.business_function else None,
            'unit': obj.employee.unit.name if obj.employee.unit else None,
            'job_function': obj.employee.job_function.name if obj.employee.job_function else None,
            'phone': obj.employee.phone
        }
    
    def get_attachments(self, obj):
        attachments = obj.attachments.filter(is_deleted=False).order_by('-uploaded_at')
        return TripAttachmentSerializer(
            attachments, 
            many=True, 
            context=self.context
        ).data

class EmployeeManualSerializer(serializers.Serializer):
    """Manual employee data"""
    name = serializers.CharField(max_length=200)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    department = serializers.CharField(max_length=100, required=False, allow_blank=True)
    business_function = serializers.CharField(max_length=100, required=False, allow_blank=True)
    unit = serializers.CharField(max_length=100, required=False, allow_blank=True)
    job_function = serializers.CharField(max_length=100, required=False, allow_blank=True)

class BusinessTripRequestCreateSerializer(serializers.Serializer):
    requester_type = serializers.ChoiceField(choices=['for_me', 'for_my_employee'])
    employee_id = serializers.IntegerField(required=False)
    employee_manual = EmployeeManualSerializer(required=False)
    travel_type_id = serializers.IntegerField()
    transport_type_id = serializers.IntegerField()
    purpose_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    comment = serializers.CharField(required=False, allow_blank=True)
    finance_approver_id = serializers.IntegerField(required=False)
    hr_representative_id = serializers.IntegerField(required=False)
    schedules = serializers.ListField(child=serializers.DictField(), required=True)
    hotels = serializers.ListField(child=serializers.DictField(), required=False)
    
    def validate(self, data):
        # Employee validation
        if data['requester_type'] == 'for_my_employee':
            if not data.get('employee_id') and not data.get('employee_manual'):
                raise serializers.ValidationError(
                    "For my employee requires employee_id or employee_manual"
                )
        
        # Date validation
        if data['start_date'] >= data['end_date']:
            raise serializers.ValidationError("End date must be after start date")
        
        # Schedule validation
        if not data.get('schedules'):
            raise serializers.ValidationError("At least one schedule is required")
        
        # Validate types exist
        try:
            TravelType.objects.get(id=data['travel_type_id'], is_active=True, is_deleted=False)
            TransportType.objects.get(id=data['transport_type_id'], is_active=True, is_deleted=False)
            TripPurpose.objects.get(id=data['purpose_id'], is_active=True, is_deleted=False)
        except (TravelType.DoesNotExist, TransportType.DoesNotExist, TripPurpose.DoesNotExist):
            raise serializers.ValidationError("Travel type, transport type or purpose not found")
        
        return data

class TripApprovalSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        if data['action'] == 'reject' and not data.get('reason'):
            raise serializers.ValidationError("Rejection reason is required")
        return data

    department_name = serializers.CharField(source='department.name', read_only=True)
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    job_function_name = serializers.CharField(source='job_function.name', read_only=True)
    
    class Meta:
        model = Employee
        fields = [
            'id', 'full_name', 'employee_id', 'phone', 'department_name',
            'business_function_name', 'unit_name', 'job_function_name'
        ]