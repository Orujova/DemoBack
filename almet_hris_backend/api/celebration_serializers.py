from rest_framework import serializers
from .celebration_models import Celebration, CelebrationImage, CelebrationWish
from .models import Employee
from datetime import date, timedelta


class CelebrationImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = CelebrationImage
        fields = ['id', 'image', 'image_url', 'uploaded_at']
        read_only_fields = ['uploaded_at']
    
    def get_image_url(self, obj):
        request = self.context.get('request')
        if request and obj.image:
            return request.build_absolute_uri(obj.image.url)
        return None


class CelebrationWishSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = CelebrationWish
        fields = ['id', 'user', 'user_name', 'message', 'created_at']
        read_only_fields = ['created_at']


class CelebrationSerializer(serializers.ModelSerializer):
    images = CelebrationImageSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=False, use_url=False),
        write_only=True,
        required=False
    )
    wishes = CelebrationWishSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = Celebration
        fields = [
            'id', 'type', 'title',  'date', 'message',
            'wishes_count', 'images', 'uploaded_images', 'wishes',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['wishes_count', 'created_by', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        uploaded_images = validated_data.pop('uploaded_images', [])
        celebration = Celebration.objects.create(**validated_data)
        
        # Create images
        for image in uploaded_images:
            CelebrationImage.objects.create(celebration=celebration, image=image)
        
        return celebration
    
    def update(self, instance, validated_data):
        uploaded_images = validated_data.pop('uploaded_images', [])
        
        # Update celebration fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Add new images
        for image in uploaded_images:
            CelebrationImage.objects.create(celebration=instance, image=image)
        
        return instance


class AutoCelebrationSerializer(serializers.Serializer):
    """
    Serializer for auto-generated celebrations (birthdays and work anniversaries)
    """
    id = serializers.CharField()
    type = serializers.CharField()
    employee_name = serializers.CharField()
    employee_id = serializers.IntegerField()
    position = serializers.CharField()

    date = serializers.DateField()
    images = serializers.ListField(child=serializers.CharField())
    message = serializers.CharField()
    wishes = serializers.IntegerField()
    years = serializers.IntegerField(required=False)
    is_auto = serializers.BooleanField(default=True)


class CombinedCelebrationSerializer(serializers.Serializer):
    """
    Combined serializer for both manual and auto celebrations
    """
    id = serializers.CharField()
    type = serializers.CharField()
    title = serializers.CharField(required=False)
    employee_name = serializers.CharField(required=False)
    position = serializers.CharField(required=False)

    date = serializers.DateField()
    images = serializers.ListField()
    message = serializers.CharField()
    wishes = serializers.IntegerField()
    years = serializers.IntegerField(required=False)
    is_auto = serializers.BooleanField(default=False)