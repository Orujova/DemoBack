# api/news_serializers.py
"""
Company News System Serializers
Complete with validation and permission checks
"""

from rest_framework import serializers
from django.utils import timezone
from .news_models import CompanyNews, TargetGroup
from .models import Employee
from .news_models import NewsCategory

# ==================== NEWS CATEGORY SERIALIZER ====================

class NewsCategorySerializer(serializers.ModelSerializer):
    """Serializer for News Category CRUD"""
    
    created_by_name = serializers.SerializerMethodField()
    news_count = serializers.SerializerMethodField()
    
    class Meta:
        model = NewsCategory
        fields = [
            'id',  'name', 
         
            'is_active', 'news_count',
            'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'news_count']
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None
    
    def get_news_count(self, obj):
        """Count of news in this category"""
        return obj.news_items.filter(is_deleted=False).count()
    



# ==================== TARGET GROUP SERIALIZERS ====================

class TargetGroupListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing target groups"""
    
    member_count = serializers.IntegerField(read_only=True)
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = TargetGroup
        fields = [
            'id', 'name', 'description', 'member_count',
            'is_active', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'member_count', 'created_at', 'updated_at']
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None


class TargetGroupMemberSerializer(serializers.ModelSerializer):
    """Serializer for target group members"""
    
    business_function_name = serializers.CharField(
        source='business_function.name', 
        read_only=True
    )
    department_name = serializers.CharField(
        source='department.name', 
        read_only=True
    )
    job_function_name = serializers.CharField(
        source='job_function.name', 
        read_only=True
    )
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'full_name', 'email',
            'business_function_name', 'department_name', 
            'job_function_name', 'job_title'
        ]


class TargetGroupDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for target group with members"""
    
    member_count = serializers.IntegerField(read_only=True)
    members_list = TargetGroupMemberSerializer(
        source='get_active_members', 
        many=True, 
        read_only=True
    )
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = TargetGroup
        fields = [
            'id', 'name', 'description', 'member_count',
            'members_list', 'is_active',
            'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'member_count', 'members_list', 
            'created_by_name', 'created_at', 'updated_at'
        ]
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None


class TargetGroupCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating target groups"""
    
    member_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of employee IDs to add to this group"
    )
    
    class Meta:
        model = TargetGroup
        fields = [
            'id', 'name', 'description', 'is_active',
            'member_ids'
        ]
        read_only_fields = ['id']
    
    def validate_name(self, value):
        """Ensure unique name"""
        instance = self.instance
        if instance:
            # Update - check if name changed and if new name exists
            if instance.name != value:
                if TargetGroup.objects.filter(name=value, is_deleted=False).exists():
                    raise serializers.ValidationError("Target group with this name already exists")
        else:
            # Create - check if name exists
            if TargetGroup.objects.filter(name=value, is_deleted=False).exists():
                raise serializers.ValidationError("Target group with this name already exists")
        return value
    
    def validate_member_ids(self, value):
        """Validate that all member IDs are valid active employees"""
        if value:
            valid_count = Employee.objects.filter(id__in=value, is_deleted=False).count()
            if valid_count != len(value):
                raise serializers.ValidationError(
                    f"Some employee IDs are invalid or inactive. Found {valid_count} of {len(value)} valid employees."
                )
        return value
    
    def create(self, validated_data):
        member_ids = validated_data.pop('member_ids', [])
        
        # Set created_by from request user
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
        
        target_group = TargetGroup.objects.create(**validated_data)
        
        if member_ids:
            employees = Employee.objects.filter(id__in=member_ids, is_deleted=False)
            target_group.members.set(employees)
        
        return target_group
    
    def update(self, instance, validated_data):
        member_ids = validated_data.pop('member_ids', None)
        
        # Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update members if provided
        if member_ids is not None:
            employees = Employee.objects.filter(id__in=member_ids, is_deleted=False)
            instance.members.set(employees)
        
        return instance


# ==================== NEWS SERIALIZERS ====================

class NewsTargetGroupSerializer(serializers.ModelSerializer):
    """Simple target group info for news"""
    
    member_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = TargetGroup
        fields = ['id', 'name', 'member_count']





class NewsListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing news"""
    
    category_display = serializers.CharField(
        source='get_category_display',
        read_only=True
    )
    author_name = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    tags_list = serializers.SerializerMethodField()
    target_groups_info = NewsTargetGroupSerializer(
        source='target_groups',
        many=True,
        read_only=True
    )
    total_recipients = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = CompanyNews
        fields = [
            'id', 'title', 'excerpt', 'category', 'category_display',
            'image_url', 'tags_list', 'is_pinned', 'is_published',
            'published_at', 'view_count', 'author_name',
            'target_groups_info', 'total_recipients', 'notify_members', 
            'notification_sent', 'notification_sent_at',
            'created_at', 'updated_at'
        ]
    
    def get_author_name(self, obj):
        if obj.author_display_name:
            return obj.author_display_name
        if obj.author:
            return obj.author.get_full_name() or obj.author.username
        return 'Unknown'
    
    def get_image_url(self, obj):
        request = self.context.get('request')
        image_url = obj.get_image_url()
        
        if image_url and request and not image_url.startswith('http'):
            return request.build_absolute_uri(image_url)
        return image_url
    
    def get_tags_list(self, obj):
        return obj.get_tags_list()


class NewsDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single news view"""
    
    category_display = serializers.CharField(
        source='get_category_display',
        read_only=True
    )
    author_name = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    tags_list = serializers.SerializerMethodField()
    target_groups_info = NewsTargetGroupSerializer(
        source='target_groups',
        many=True,
        read_only=True
    )
    total_recipients = serializers.IntegerField(read_only=True)
  
    
    class Meta:
        model = CompanyNews
        fields = [
            'id', 'title', 'excerpt', 'content',
            'category', 'category_display', 'tags', 'tags_list',
            'image_url', 'is_pinned', 'is_published', 'published_at',
            'view_count', 'author_name', 'author_display_name',
            'target_groups_info', 'total_recipients',
            'notify_members', 'notification_sent', 'notification_sent_at',
             'created_at', 'updated_at'
        ]
    
    def get_author_name(self, obj):
        if obj.author_display_name:
            return obj.author_display_name
        if obj.author:
            return obj.author.get_full_name() or obj.author.username
        return 'Unknown'
    
    def get_image_url(self, obj):
        request = self.context.get('request')
        image_url = obj.get_image_url()
        
        if image_url and request and not image_url.startswith('http'):
            return request.build_absolute_uri(image_url)
        return image_url
    
    def get_tags_list(self, obj):
        return obj.get_tags_list()


class NewsCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating news"""
    
    tags_list = serializers.ListField(
        child=serializers.CharField(max_length=50),
        write_only=True,
        required=False,
        help_text="List of tags for the news"
    )
    target_group_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        help_text="List of target group UUIDs"
    )
    image_url_external = serializers.URLField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text="External image URL (alternative to uploading file)"
    )
    
    class Meta:
        model = CompanyNews
        fields = [
            'id', 'title', 'excerpt', 'content',
            'category', 'tags_list', 'image', 'image_url_external',
            'is_pinned', 'is_published', 'published_at',
            'author_display_name', 'target_group_ids', 'notify_members'
        ]
        read_only_fields = ['id']
    
    def validate_title(self, value):
        """Validate title length"""
        if len(value) < 5:
            raise serializers.ValidationError("Title must be at least 5 characters long")
        if len(value) > 300:
            raise serializers.ValidationError("Title cannot exceed 300 characters")
        return value
    
    def validate_excerpt(self, value):
        """Validate excerpt length"""
        if len(value) < 10:
            raise serializers.ValidationError("Excerpt must be at least 10 characters long")
        if len(value) > 500:
            raise serializers.ValidationError("Excerpt cannot exceed 500 characters")
        return value
    
    def validate_content(self, value):
        """Validate content"""
        if len(value) < 20:
            raise serializers.ValidationError("Content must be at least 20 characters long")
        return value
    
    def validate_target_group_ids(self, value):
        """Validate target group IDs"""
        if value:
            valid_count = TargetGroup.objects.filter(id__in=value, is_active=True, is_deleted=False).count()
            if valid_count != len(value):
                raise serializers.ValidationError(
                    f"Some target group IDs are invalid or inactive. Found {valid_count} of {len(value)} valid groups."
                )
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        # If notify_members is True, must have target groups
        if data.get('notify_members', False):
            target_group_ids = data.get('target_group_ids', [])
            if not target_group_ids:
                raise serializers.ValidationError({
                    'notify_members': 'Cannot send notifications without target groups. Please select at least one target group.'
                })
        
        return data
    
    def create(self, validated_data):
        tags_list = validated_data.pop('tags_list', [])
        target_group_ids = validated_data.pop('target_group_ids', [])
        image_url_external = validated_data.pop('image_url_external', '')
        
        # Set external image URL if provided
        if image_url_external:
            validated_data['image_preview_url'] = image_url_external
        
        # Set author and created_by from request user
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
            if not validated_data.get('author'):
                validated_data['author'] = request.user
        
        # Create news
        news = CompanyNews.objects.create(**validated_data)
        
        # Set tags
        if tags_list:
            news.set_tags_from_list(tags_list)
            news.save()
        
        # Set target groups
        if target_group_ids:
            target_groups = TargetGroup.objects.filter(id__in=target_group_ids, is_active=True, is_deleted=False)
            news.target_groups.set(target_groups)
        
     
        
        return news
    def update(self, instance, validated_data):
        tags_list = validated_data.pop('tags_list', None)
        target_group_ids = validated_data.pop('target_group_ids', None)
        image_url_external = validated_data.pop('image_url_external', None)
        
        # Track changes for activity log
        changes = []
        
        # Update external image URL if provided
        if image_url_external is not None:
            instance.image_preview_url = image_url_external
            changes.append('image_url')
        
        # Update basic fields
        for attr, value in validated_data.items():
            old_value = getattr(instance, attr)
            if old_value != value:
                changes.append(attr)
            setattr(instance, attr, value)
        
        # Set updated_by
        request = self.context.get('request')
        if request and request.user:
            instance.updated_by = request.user
        
        instance.save()
        
        # Update tags if provided
        if tags_list is not None:
            instance.set_tags_from_list(tags_list)
            instance.save()
            changes.append('tags')
        
        # Update target groups if provided
        if target_group_ids is not None:
            target_groups = TargetGroup.objects.filter(id__in=target_group_ids, is_active=True, is_deleted=False)
            instance.target_groups.set(target_groups)
            changes.append('target_groups')
        
 
        
        return instance