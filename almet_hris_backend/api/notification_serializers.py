# api/notification_serializers.py
from rest_framework import serializers
from .notification_models import NotificationSettings


class NotificationSettingsSerializer(serializers.ModelSerializer):
    """Notification Settings Serializer"""
    
    class Meta:
        model = NotificationSettings
        fields = [
            'id', 
            'enable_email_notifications', 'email_retry_attempts',
            'email_retry_delay_minutes', 
            'business_trip_subject_prefix',
            'vacation_subject_prefix',
            'timeoff_subject_prefix',  # ✅ NEW
                        'handover_subject_prefix',  # ⭐ NEW
            'handover_sender_email',    # ⭐ NEW
            'company_news_subject_prefix',
            'company_news_sender_email',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']




