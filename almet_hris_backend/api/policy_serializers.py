# api/policy_serializers.py - UPDATED with PolicyCompany Support

from rest_framework import serializers
from .policy_models import (
    PolicyFolder, CompanyPolicy, PolicyAcknowledgment, PolicyCompany
)
from .models import BusinessFunction
from django.utils import timezone


# ==================== POLICY COMPANY SERIALIZERS ====================

class PolicyCompanySerializer(serializers.ModelSerializer):
    """Serializer for manual policy companies"""
    
    folder_count = serializers.SerializerMethodField()
    total_policy_count = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    code = serializers.SerializerMethodField()  # Generate code from name
    
    class Meta:
        model = PolicyCompany
        fields = [
            'id', 'name', 'code', 'description', 'icon',
            'folder_count', 'total_policy_count',
            'is_active', 'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']
    
    def get_code(self, obj):
        """Generate code from name (first 3-4 letters uppercase)"""
        if obj.name:
            return obj.name[:4].upper().replace(' ', '')
        return 'COMP'
    
    def get_folder_count(self, obj):
        return obj.policy_folders.filter(is_active=True).count()
    
    def get_total_policy_count(self, obj):
        total = 0
        for folder in obj.policy_folders.filter(is_active=True):
            total += folder.get_policy_count()
        return total
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None


class PolicyCompanyCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating policy companies"""
    
    class Meta:
        model = PolicyCompany
        fields = ['id', 'name', 'description', 'icon', 'is_active']
    
    def validate_name(self, value):
        """Validate company name"""
        if not value or not value.strip():
            raise serializers.ValidationError("Company name cannot be empty")
        
        value = value.strip()
        
        # Check for duplicates
        instance_pk = self.instance.pk if self.instance else None
        if PolicyCompany.objects.filter(name__iexact=value).exclude(pk=instance_pk).exists():
            raise serializers.ValidationError(f"Company with name '{value}' already exists")
        
        return value


# ==================== BUSINESS FUNCTION SERIALIZERS ====================

class BusinessFunctionSimpleSerializer(serializers.ModelSerializer):
    """Simple serializer for business function"""
    
    class Meta:
        model = BusinessFunction
        fields = ['id', 'name', 'code', 'is_active']
        read_only_fields = ['id', 'name', 'code', 'is_active']


class BusinessFunctionWithFoldersSerializer(serializers.ModelSerializer):
    """Business function with all its policy folders and statistics"""
    
    folders = serializers.SerializerMethodField()
    folder_count = serializers.SerializerMethodField()
    total_policy_count = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessFunction
        fields = [
            'id', 'name', 'code', 'folder_count', 'total_policy_count',
            'folders', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_folders(self, obj):
        folders = obj.policy_folders.filter(is_active=True).order_by('name')
        return PolicyFolderSerializer(folders, many=True, context=self.context).data
    
    def get_folder_count(self, obj):
        return obj.policy_folders.filter(is_active=True).count()
    
    def get_total_policy_count(self, obj):
        total = 0
        for folder in obj.policy_folders.filter(is_active=True):
            total += folder.get_policy_count()
        return total


# ==================== POLICY FOLDER SERIALIZERS ====================

class PolicyFolderSerializer(serializers.ModelSerializer):
    """Full serializer for policy folders"""
    
    # Company info (could be from BusinessFunction OR PolicyCompany)
    company_name = serializers.SerializerMethodField()
    company_code = serializers.SerializerMethodField()
    company_type = serializers.SerializerMethodField()
    
    # Computed fields
    policy_count = serializers.SerializerMethodField()
    total_views = serializers.SerializerMethodField()
    total_downloads = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = PolicyFolder
        fields = [
            'id', 'business_function', 'policy_company',
            'company_name', 'company_code', 'company_type',
            'name', 'description', 'icon', 'is_active',
            'policy_count', 'total_views', 'total_downloads',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']
    
    def get_company_name(self, obj):
        return obj.get_company_name()
    
    def get_company_code(self, obj):
        return obj.get_company_code()
    
    def get_company_type(self, obj):
        """Returns 'business_function' or 'policy_company'"""
        if obj.business_function:
            return 'business_function'
        elif obj.policy_company:
            return 'policy_company'
        return None
    
    def get_policy_count(self, obj):
        return obj.get_policy_count()
    
    def get_total_views(self, obj):
        return obj.get_total_views()
    
    def get_total_downloads(self, obj):
        return obj.get_total_downloads()
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None


class PolicyFolderCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating folders"""
    
    class Meta:
        model = PolicyFolder
        fields = [
            'id', 'business_function', 'policy_company',
            'name', 'description', 'icon', 'is_active'
        ]
    
    def validate_name(self, value):
        """Validate folder name"""
        if not value or not value.strip():
            raise serializers.ValidationError("Folder name cannot be empty")
        
        if len(value) > 200:
            raise serializers.ValidationError("Folder name is too long (max 200 characters)")
        
        return value.strip()
    
    def validate(self, data):
        """Validate complete folder data"""
        business_function = data.get('business_function')
        policy_company = data.get('policy_company')
        
        # MUST have exactly ONE
        if not business_function and not policy_company:
            raise serializers.ValidationError(
                "Folder must belong to either a Business Function or a Company"
            )
        
        if business_function and policy_company:
            raise serializers.ValidationError(
                "Folder cannot belong to both Business Function and Company"
            )
        
        # Check for duplicate names within same parent
        name = data.get('name')
        if name:
            instance_pk = self.instance.pk if self.instance else None
            
            if business_function:
                existing = PolicyFolder.objects.filter(
                    business_function=business_function,
                    name__iexact=name.strip()
                ).exclude(pk=instance_pk)
                parent_name = business_function.name
            else:
                existing = PolicyFolder.objects.filter(
                    policy_company=policy_company,
                    name__iexact=name.strip()
                ).exclude(pk=instance_pk)
                parent_name = policy_company.name
            
            if existing.exists():
                raise serializers.ValidationError({
                    'name': f"A folder with this name already exists in {parent_name}"
                })
        
        return data


# ==================== COMPANY POLICY SERIALIZERS ====================

class CompanyPolicyListSerializer(serializers.ModelSerializer):
    """Serializer for policy list view"""
    
    folder_name = serializers.CharField(source='folder.name', read_only=True)
    company_code = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    file_size_display = serializers.CharField(source='get_file_size_display', read_only=True)
    policy_url = serializers.SerializerMethodField()
    
    class Meta:
        model = CompanyPolicy
        fields = [
            'id', 'folder', 'folder_name', 'company_code', 'company_name',
            'title', 'description', 'requires_acknowledgment',
            'file_size', 'file_size_display', 'download_count', 'view_count',
            'policy_url', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['file_size', 'download_count', 'view_count', 'created_at', 'updated_at']
    
    def get_company_code(self, obj):
        return obj.get_company_code()
    
    def get_company_name(self, obj):
        return obj.get_company_name()
    
    def get_policy_url(self, obj):
        if obj.policy_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.policy_file.url)
            return obj.policy_file.url
        return None


class CompanyPolicyDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single policy view"""
    
    folder_details = PolicyFolderSerializer(source='folder', read_only=True)
    file_size_display = serializers.CharField(source='get_file_size_display', read_only=True)
    policy_url = serializers.SerializerMethodField()
    acknowledgment_count = serializers.SerializerMethodField()
    acknowledgment_percentage = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    company_code = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    
    class Meta:
        model = CompanyPolicy
        fields = [
            'id', 'folder', 'folder_details', 'company_code', 'company_name',
            'title', 'description', 'policy_file', 'policy_url',
            'file_size', 'file_size_display', 'requires_acknowledgment',
            'download_count', 'view_count', 'is_active',
            'created_by', 'created_by_name', 'updated_by', 'updated_by_name',
            'acknowledgment_count', 'acknowledgment_percentage',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'created_by', 'created_at', 'updated_at',
            'file_size', 'download_count', 'view_count'
        ]
    
    def get_company_code(self, obj):
        return obj.get_company_code()
    
    def get_company_name(self, obj):
        return obj.get_company_name()
    
    def get_policy_url(self, obj):
        if obj.policy_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.policy_file.url)
            return obj.policy_file.url
        return None
    
    def get_acknowledgment_count(self, obj):
        return obj.get_acknowledgment_count()
    
    def get_acknowledgment_percentage(self, obj):
        return obj.get_acknowledgment_percentage()
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None
    
    def get_updated_by_name(self, obj):
        if obj.updated_by:
            return obj.updated_by.get_full_name() or obj.updated_by.username
        return None


class CompanyPolicyCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating policies"""
    
    policy_file = serializers.FileField(
        required=True,
        allow_empty_file=False,
        help_text="PDF file (max 10MB)",
        write_only=False
    )
    
    class Meta:
        model = CompanyPolicy
        fields = [
            'id', 'folder', 'title', 'description', 'policy_file',
            'requires_acknowledgment', 'is_active'
        ]
    
    def validate_policy_file(self, value):
        if not value:
            raise serializers.ValidationError("Policy file is required")
        
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError(
                f"File size cannot exceed 10MB (current: {value.size / (1024 * 1024):.2f}MB)"
            )
        
        if not value.name.lower().endswith('.pdf'):
            raise serializers.ValidationError(
                f"Only PDF files are allowed. Current file: {value.name}"
            )
        
        return value
    
    def validate_title(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Policy title cannot be empty")
        
        if len(value) > 300:
            raise serializers.ValidationError("Title is too long (max 300 characters)")
        
        return value.strip()
    
    def validate_folder(self, value):
        if not value:
            raise serializers.ValidationError("Folder is required")
        
        if not value.is_active:
            raise serializers.ValidationError(f"Folder '{value.name}' is not active")
        
        return value
    
    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['updated_by'] = request.user
        
        return super().update(instance, validated_data)
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        if instance.policy_file:
            request = self.context.get('request')
            if request:
                representation['policy_url'] = request.build_absolute_uri(instance.policy_file.url)
            else:
                representation['policy_url'] = instance.policy_file.url
        
        return representation


# ==================== ACKNOWLEDGMENT SERIALIZERS ====================

class PolicyAcknowledgmentSerializer(serializers.ModelSerializer):
    """Serializer for policy acknowledgments"""
    
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    employee_email = serializers.CharField(source='employee.email', read_only=True)
    policy_title = serializers.CharField(source='policy.title', read_only=True)
    
    class Meta:
        model = PolicyAcknowledgment
        fields = [
            'id', 'policy', 'policy_title',
            'employee', 'employee_name', 'employee_id', 'employee_email',
            'acknowledged_at', 'ip_address', 'notes'
        ]
        read_only_fields = ['acknowledged_at']
    
    def validate(self, data):
        policy = data.get('policy')
        employee = data.get('employee')
        
        if PolicyAcknowledgment.objects.filter(policy=policy, employee=employee).exists():
            raise serializers.ValidationError(
                "This policy has already been acknowledged by this employee"
            )
        
        return data