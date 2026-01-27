# api/timeoff_serializers.py
"""
Time Off System Serializers
"""

from rest_framework import serializers
from .timeoff_models import TimeOffBalance, TimeOffRequest, TimeOffSettings, TimeOffActivity
from .models import Employee
from django.utils import timezone
from datetime import datetime, timedelta


class TimeOffBalanceSerializer(serializers.ModelSerializer):
    """Time Off Balance Serializer"""
    
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    employee_email = serializers.CharField(source='employee.email', read_only=True)
    
    class Meta:
        model = TimeOffBalance
        fields = [
            'id', 'employee', 'employee_name', 'employee_id', 'employee_email',
            'monthly_allowance_hours', 'current_balance_hours', 
            'used_hours_this_month', 'last_reset_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TimeOffRequestSerializer(serializers.ModelSerializer):
    """Time Off Request Serializer"""
    
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    employee_email = serializers.CharField(source='employee.email', read_only=True)
    
    line_manager_name = serializers.CharField(source='line_manager.full_name', read_only=True)
    line_manager_email = serializers.CharField(source='line_manager.email', read_only=True)
    
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    

    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    current_balance = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    can_approve = serializers.SerializerMethodField()
    
    class Meta:
        model = TimeOffRequest
        fields = [
            'id', 'employee', 'employee_name', 'employee_id', 'employee_email',
            'date', 'start_time', 'end_time', 'duration_hours', 'reason',
            'status', 'status_display', 
            'line_manager', 'line_manager_name', 'line_manager_email',
            'approved_by', 'approved_by_name', 'approved_at', 
            'rejection_reason', 'balance_deducted',
            'hr_notified', 'hr_notified_at',
            'created_at', 'updated_at', 'created_by',
            'current_balance', 'can_cancel', 'can_approve'
        ]
        read_only_fields = [
            'id', 'duration_hours', 'status', 'approved_by', 
            'approved_at', 'balance_deducted', 'hr_notified', 
            'hr_notified_at', 'created_at', 'updated_at'
        ]
    

    
    def get_current_balance(self, obj):
        """Employee-in cari balansı"""
        try:
            balance = TimeOffBalance.get_or_create_for_employee(obj.employee)
            return float(balance.current_balance_hours)
        except:
            return 0.0
    
    def get_can_cancel(self, obj):
        """Request cancel edilə bilər?"""
        return obj.status in ['PENDING', 'APPROVED']
    
    def get_can_approve(self, obj):
        """Request approve edilə bilər?"""
        request = self.context.get('request')
        if not request or not request.user:
            return False
        
        # Yalnız line manager approve edə bilər
        if obj.line_manager and hasattr(request.user, 'employee_profile'):
            return (
                obj.status == 'PENDING' and 
                request.user.employee_profile == obj.line_manager
            )
        return False
    
    def validate(self, data):
        """Validation"""
        # Tarix keçmişdə olmamalıdır
        if data.get('date') and data['date'] < timezone.now().date():
            raise serializers.ValidationError({
                'date': 'Cannot request time off for past dates'
            })
        
        # Start time < End time
        if data.get('start_time') and data.get('end_time'):
            if data['start_time'] >= data['end_time']:
                raise serializers.ValidationError({
                    'end_time': 'End time must be after start time'
                })
        
        # Employee-in balansı yoxla
        employee = data.get('employee') or self.instance.employee
        if employee:
            balance = TimeOffBalance.get_or_create_for_employee(employee)
            
            # Duration hesabla
            if data.get('start_time') and data.get('end_time'):
                start_dt = datetime.combine(datetime.today(), data['start_time'])
                end_dt = datetime.combine(datetime.today(), data['end_time'])
                if end_dt < start_dt:
                    end_dt += timedelta(days=1)
                duration = (end_dt - start_dt).total_seconds() / 3600
                
                if not balance.has_sufficient_balance(duration):
                    raise serializers.ValidationError({
                        'duration_hours': f'Insufficient balance. Available: {balance.current_balance_hours}h, Requested: {duration}h'
                    })
        
        
       
        return data


class TimeOffRequestCreateSerializer(serializers.ModelSerializer):
    """Time Off Request yaratmaq üçün serializer"""
    
    class Meta:
        model = TimeOffRequest
        fields = [
            'employee', 'date', 'start_time', 'end_time', 'reason'
        ]
    
    def validate(self, data):
        """Validation"""
        # Tarix keçmişdə olmamalıdır
        if data.get('date') and data['date'] < timezone.now().date():
            raise serializers.ValidationError({
                'date': 'Cannot request time off for past dates'
            })
        
        # Start time < End time
        if data.get('start_time') >= data.get('end_time'):
            raise serializers.ValidationError({
                'end_time': 'End time must be after start time'
            })
        
        # Duration hesabla və yoxla
        start_dt = datetime.combine(datetime.today(), data['start_time'])
        end_dt = datetime.combine(datetime.today(), data['end_time'])
        if end_dt < start_dt:
            end_dt += timedelta(days=1)
        duration = (end_dt - start_dt).total_seconds() / 3600
        
        # Balance yoxla
        employee = data['employee']
        balance = TimeOffBalance.get_or_create_for_employee(employee)
        
        if not balance.has_sufficient_balance(duration):
            raise serializers.ValidationError({
                'duration_hours': f'Insufficient balance. Available: {balance.current_balance_hours}h, Requested: {duration}h'
            })
        
        # Settings yoxla
        settings = TimeOffSettings.get_settings()
        
        # Max hours yoxla
        if duration > float(settings.max_request_hours):
            raise serializers.ValidationError({
                'duration_hours': f'Maximum {settings.max_request_hours} hours per request'
            })
        
        # Advance booking yoxla
        min_date = timezone.now() + timedelta(hours=settings.min_advance_hours)
        request_datetime = datetime.combine(data['date'], data['start_time'])
        
      
        
        return data
    
    def create(self, validated_data):
        """Request yarat"""
        request = self.context.get('request')
        
        # ✅ FIX: Don't pass created_by here, let the model handle it
        instance = TimeOffRequest.objects.create(
            **validated_data
        )
        
        # Set created_by after creation if needed
        if request and request.user:
            instance.created_by = request.user
            instance.save(update_fields=['created_by'])
        
        # Activity log
        TimeOffActivity.objects.create(
            request=instance,
            activity_type='CREATED',
            description=f"Time off request created by {instance.employee.full_name}",
            performed_by=request.user if request else None,
            metadata={
                'date': str(instance.date),
                'duration_hours': float(instance.duration_hours),
                'reason': instance.reason
            }
        )
        
        return instance


class TimeOffApproveSerializer(serializers.Serializer):
    """Approve action üçün serializer"""
    pass


class TimeOffRejectSerializer(serializers.Serializer):
    """Reject action üçün serializer"""
    rejection_reason = serializers.CharField(required=True)


class TimeOffSettingsSerializer(serializers.ModelSerializer):
    """Time Off Settings Serializer"""
    
    hr_emails_list = serializers.SerializerMethodField()
    
    class Meta:
        model = TimeOffSettings
        fields = [
            'id', 'default_monthly_hours', 'max_request_hours',
            'min_advance_hours', 'hr_notification_emails', 'hr_emails_list',
            'enable_auto_approval', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_hr_emails_list(self, obj):
        return obj.get_hr_emails_list()


class TimeOffActivitySerializer(serializers.ModelSerializer):
    """Time Off Activity Serializer"""
    
    performed_by_name = serializers.CharField(source='performed_by.get_full_name', read_only=True)
    activity_type_display = serializers.CharField(source='get_activity_type_display', read_only=True)
    
    class Meta:
        model = TimeOffActivity
        fields = [
            'id', 'request', 'activity_type', 'activity_type_display',
            'description', 'performed_by', 'performed_by_name',
            'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


