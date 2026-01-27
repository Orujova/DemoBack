# api/handover_serializers.py
from rest_framework import serializers
from .handover_models import (
    HandoverType, HandoverRequest, HandoverTask, 
    TaskActivity, HandoverImportantDate, HandoverActivity,
    HandoverAttachment
)
from .models import Employee
from django.contrib.auth.models import User


class HandoverTypeSerializer(serializers.ModelSerializer):
    """Handover Type Serializer"""
    class Meta:
        model = HandoverType
        fields = ['id', 'name',  'is_active', 'created_at']


class TaskActivitySerializer(serializers.ModelSerializer):
    """Task Activity Log Serializer"""
    actor_name = serializers.CharField(source='actor.get_full_name', read_only=True)
    
    class Meta:
        model = TaskActivity
        fields = [
            'id', 'actor', 'actor_name', 'action', 
            'old_status', 'new_status', 'comment', 'timestamp'
        ]


class HandoverTaskSerializer(serializers.ModelSerializer):
    """Handover Task Serializer"""
    activity_log = TaskActivitySerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_current_status_display', read_only=True)
    
    class Meta:
        model = HandoverTask
        fields = [
            'id', 'handover', 'description', 'current_status', 
            'status_display', 'initial_comment', 'order', 
            'activity_log', 'created_at', 'updated_at'
        ]
    
    def create(self, validated_data):
        """Create task with initial activity log"""
        user = self.context['request'].user
        task = HandoverTask.objects.create(**validated_data)
        
        # Log initial activity
        TaskActivity.objects.create(
            task=task,
            actor=user,
            action='Task Created',
            old_status='-',
            new_status=task.current_status,
            comment=validated_data.get('initial_comment', '-')
        )
        
        return task


class HandoverImportantDateSerializer(serializers.ModelSerializer):
    """Important Date Serializer"""
    class Meta:
        model = HandoverImportantDate
        fields = ['id', 'handover', 'date', 'description', 'created_at']


class HandoverActivitySerializer(serializers.ModelSerializer):
    """Handover Activity Log Serializer"""
    actor_name = serializers.CharField(source='actor.get_full_name', read_only=True)
    
    class Meta:
        model = HandoverActivity
        fields = [
            'id', 'actor', 'actor_name', 'action', 
            'comment', 'status', 'timestamp'
        ]


class HandoverAttachmentSerializer(serializers.ModelSerializer):
    """Handover Attachment Serializer"""
    file_url = serializers.SerializerMethodField()
    file_size_display = serializers.CharField(read_only=True)
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
    class Meta:
        model = HandoverAttachment
        fields = [
            'id', 'handover', 'file', 'file_url',
            'file_size', 'file_size_display', 'file_type',
            'uploaded_by', 'uploaded_by_name', 'uploaded_at'
        ]
        read_only_fields = ['file_size', 'file_type', 'uploaded_by', 'uploaded_at']
    
    def get_file_url(self, obj):
        """Get full URL for file"""
        request = self.context.get('request')
        if obj.file and hasattr(obj.file, 'url'):
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


class HandoverRequestSerializer(serializers.ModelSerializer):
    """Handover Request Detail Serializer"""
    # Employee details
    handing_over_employee_name = serializers.CharField(
        source='handing_over_employee.full_name', 
        read_only=True
    )
    handing_over_position = serializers.CharField(
        source='handing_over_employee.job_title', 
        read_only=True
    )
    handing_over_department = serializers.CharField(
        source='handing_over_employee.department.name', 
        read_only=True
    )
    
    taking_over_employee_name = serializers.CharField(
        source='taking_over_employee.full_name', 
        read_only=True
    )
    taking_over_position = serializers.CharField(
        source='taking_over_employee.job_title', 
        read_only=True
    )
    
    line_manager_name = serializers.CharField(
        source='line_manager.full_name', 
        read_only=True
    )
    
    # Type
    handover_type_name = serializers.CharField(
        source='handover_type.name', 
        read_only=True
    )
    
    # Status display
    status_display = serializers.CharField(
        source='get_status_display', 
        read_only=True
    )
    
    # Related data
    tasks = HandoverTaskSerializer(many=True, read_only=True)
    important_dates = HandoverImportantDateSerializer(many=True, read_only=True)
    activity_log = HandoverActivitySerializer(many=True, read_only=True)
    attachments = HandoverAttachmentSerializer(many=True, read_only=True)
    
    # Creator
    created_by_name = serializers.CharField(
        source='created_by.get_full_name', 
        read_only=True
    )
    
    class Meta:
        model = HandoverRequest
        fields = [
            'id', 'request_id', 
            'handing_over_employee', 'handing_over_employee_name', 
            'handing_over_position', 'handing_over_department',
            'taking_over_employee', 'taking_over_employee_name', 
            'taking_over_position',
            'handover_type', 'handover_type_name',
            'start_date', 'end_date',
            'contacts', 'access_info', 'documents_info', 'open_issues', 'notes',
            'line_manager', 'line_manager_name',
            'status', 'status_display',
            'ho_signed', 'ho_signed_date',
            'to_signed', 'to_signed_date',
            'lm_approved', 'lm_approved_date', 'lm_comment', 'lm_clarification_comment',
            'rejected_at', 'rejection_reason',
            'taken_over', 'taken_over_date',
            'taken_back', 'taken_back_date',
            'tasks', 'important_dates', 'activity_log', 'attachments',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'request_id', 'status', 'ho_signed', 'ho_signed_date',
            'to_signed', 'to_signed_date', 'lm_approved', 'lm_approved_date',
            'rejected_at', 'taken_over', 'taken_over_date',
            'taken_back', 'taken_back_date', 'created_at', 'updated_at'
        ]


class HandoverRequestCreateSerializer(serializers.ModelSerializer):
    """Create new handover with nested data and validation"""
    tasks_data = serializers.ListField(
        child=serializers.DictField(), 
        write_only=True,
        required=True,
        allow_empty=False,
        help_text="At least one task is required"
    )
    dates_data = serializers.ListField(
        child=serializers.DictField(), 
        write_only=True,
        required=True,
        allow_empty=False,
        help_text="At least one important date is required"
    )
    
    class Meta:
        model = HandoverRequest
        fields = [
            'handing_over_employee', 'taking_over_employee',
            'handover_type', 'start_date', 'end_date',
            'contacts', 'access_info', 'documents_info', 'open_issues', 'notes',
            'tasks_data', 'dates_data'
        ]
    
    def validate_start_date(self, value):
        """Validate start date"""
        from datetime import date
        if value < date.today():
            raise serializers.ValidationError(
                "Start date cannot be in the past"
            )
        return value
    
    def validate(self, data):
        """Comprehensive validation"""
        errors = {}
        
        # 1. Validate dates
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] >= data['end_date']:
                errors['end_date'] = 'End date must be after start date'
        
        # 2. Validate employees
        if data.get('handing_over_employee') == data.get('taking_over_employee'):
            errors['taking_over_employee'] = 'Cannot be the same as handing over employee'
        
        # 3. Validate tasks
        tasks = data.get('tasks_data', [])
        if not tasks:
            errors['tasks_data'] = 'At least one task is required'
        else:
            valid_tasks = [t for t in tasks if t.get('description', '').strip()]
            if not valid_tasks:
                errors['tasks_data'] = 'At least one task with description is required'
            
            # Validate each task
            for idx, task in enumerate(tasks):
                if not task.get('description', '').strip():
                    errors[f'tasks_data.{idx}.description'] = 'Task description is required'
                
                if task.get('description') and len(task['description']) > 1000:
                    errors[f'tasks_data.{idx}.description'] = 'Task description too long (max 1000 chars)'
        
        # 4. Validate dates
        dates = data.get('dates_data', [])
        if not dates:
            errors['dates_data'] = 'At least one important date is required'
        else:
            valid_dates = [d for d in dates if d.get('date') and d.get('description', '').strip()]
            if not valid_dates:
                errors['dates_data'] = 'At least one important date with description is required'
            
            # Validate each date
            for idx, date_item in enumerate(dates):
                if not date_item.get('date'):
                    errors[f'dates_data.{idx}.date'] = 'Date is required'
                
                if not date_item.get('description', '').strip():
                    errors[f'dates_data.{idx}.description'] = 'Description is required'
                
                if date_item.get('description') and len(date_item['description']) > 500:
                    errors[f'dates_data.{idx}.description'] = 'Description too long (max 500 chars)'
        
        # 5. Validate text fields length
        text_fields = ['contacts', 'access_info', 'documents_info', 'open_issues', 'notes']
        for field in text_fields:
            if data.get(field) and len(data[field]) > 5000:
                errors[field] = f'{field.replace("_", " ").title()} is too long (max 5000 chars)'
        
        if errors:
            raise serializers.ValidationError(errors)
        
        return data
    
    def create(self, validated_data):
        """Create handover with all nested data"""
        tasks_data = validated_data.pop('tasks_data', [])
        dates_data = validated_data.pop('dates_data', [])
        
        user = self.context['request'].user
        validated_data['created_by'] = user
        
        # Create handover
        handover = HandoverRequest.objects.create(**validated_data)
        
        # Create tasks
        for idx, task_data in enumerate(tasks_data):
            description = task_data.get('description', '').strip()
            if not description:
                continue
            
            task = HandoverTask.objects.create(
                handover=handover,
                description=description,
                current_status=task_data.get('status', 'NOT_STARTED'),
                initial_comment=task_data.get('comment', '').strip(),
                order=idx
            )
            
            # Log initial task activity
            TaskActivity.objects.create(
                task=task,
                actor=user,
                action='Initial Status Set',
                old_status='-',
                new_status=task.current_status,
                comment=task.initial_comment or '-'
            )
        
        # Create important dates
        for date_data in dates_data:
            if not date_data.get('date') or not date_data.get('description', '').strip():
                continue
            
            HandoverImportantDate.objects.create(
                handover=handover,
                date=date_data['date'],
                description=date_data['description'].strip()
            )
        
        # Log creation activity
        HandoverActivity.objects.create(
            handover=handover,
            actor=user,
            action='Handover created',
            comment='New handover request created.',
            status=handover.status
        )
        
        return handover


class HandoverRequestUpdateSerializer(serializers.ModelSerializer):
    """Update handover (only certain fields editable)"""
    
    class Meta:
        model = HandoverRequest
        fields = [
            'contacts', 'access_info', 'documents_info', 
            'open_issues', 'notes'
        ]
    
    def validate(self, data):
        """Validate update - only allow if not yet signed"""
        handover = self.instance
        
        if handover.ho_signed or handover.to_signed:
            raise serializers.ValidationError(
                "Cannot update handover after it has been signed"
            )
        
        return data
    
    def update(self, instance, validated_data):
        """Update with activity log"""
        user = self.context['request'].user
        
        # Update fields
        for field, value in validated_data.items():
            setattr(instance, field, value)
        
        instance.save()
        
        # Log update
        HandoverActivity.objects.create(
            handover=instance,
            actor=user,
            action='Handover updated',
            comment='Handover information updated.',
            status=instance.status
        )
        
        return instance