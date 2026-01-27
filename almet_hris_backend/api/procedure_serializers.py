# api/procedure_serializers.py

from rest_framework import serializers
from .procedure_models import ProcedureFolder, CompanyProcedure, ProcedureCompany
from .models import BusinessFunction


# ==================== PROCEDURE COMPANY SERIALIZERS ====================

class ProcedureCompanySerializer(serializers.ModelSerializer):
    """Serializer for manual procedure companies"""
    
    folder_count = serializers.SerializerMethodField()
    total_procedure_count = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    code = serializers.SerializerMethodField()
    
    class Meta:
        model = ProcedureCompany
        fields = [
            'id', 'name', 'code', 'description', 'icon',
            'folder_count', 'total_procedure_count',
            'is_active', 'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']
    
    def get_code(self, obj):
        if obj.name:
            return obj.name[:4].upper().replace(' ', '')
        return 'COMP'
    
    def get_folder_count(self, obj):
        return obj.procedure_folders.filter(is_active=True).count()
    
    def get_total_procedure_count(self, obj):
        total = 0
        for folder in obj.procedure_folders.filter(is_active=True):
            total += folder.get_procedure_count()
        return total
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None


class ProcedureCompanyCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating procedure companies"""
    
    class Meta:
        model = ProcedureCompany
        fields = ['id', 'name', 'description', 'icon', 'is_active']
    
    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Company name cannot be empty")
        
        value = value.strip()
        
        instance_pk = self.instance.pk if self.instance else None
        if ProcedureCompany.objects.filter(name__iexact=value).exclude(pk=instance_pk).exists():
            raise serializers.ValidationError(f"Company with name '{value}' already exists")
        
        return value


# ==================== PROCEDURE FOLDER SERIALIZERS ====================

class ProcedureFolderSerializer(serializers.ModelSerializer):
    """Full serializer for procedure folders"""
    
    company_name = serializers.SerializerMethodField()
    company_code = serializers.SerializerMethodField()
    company_type = serializers.SerializerMethodField()
    
    procedure_count = serializers.SerializerMethodField()
    total_views = serializers.SerializerMethodField()
    total_downloads = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ProcedureFolder
        fields = [
            'id', 'business_function', 'procedure_company',
            'company_name', 'company_code', 'company_type',
            'name', 'description', 'icon', 'is_active',
            'procedure_count', 'total_views', 'total_downloads',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']
    
    def get_company_name(self, obj):
        return obj.get_company_name()
    
    def get_company_code(self, obj):
        return obj.get_company_code()
    
    def get_company_type(self, obj):
        if obj.business_function:
            return 'business_function'
        elif obj.procedure_company:
            return 'procedure_company'
        return None
    
    def get_procedure_count(self, obj):
        return obj.get_procedure_count()
    
    def get_total_views(self, obj):
        return obj.get_total_views()
    
    def get_total_downloads(self, obj):
        return obj.get_total_downloads()
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None


class ProcedureFolderCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating folders"""
    
    class Meta:
        model = ProcedureFolder
        fields = [
            'id', 'business_function', 'procedure_company',
            'name', 'description', 'icon', 'is_active'
        ]
    
    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Folder name cannot be empty")
        
        if len(value) > 200:
            raise serializers.ValidationError("Folder name is too long (max 200 characters)")
        
        return value.strip()
    
    def validate(self, data):
        business_function = data.get('business_function')
        procedure_company = data.get('procedure_company')
        
        if not business_function and not procedure_company:
            raise serializers.ValidationError(
                "Folder must belong to either a Business Function or a Company"
            )
        
        if business_function and procedure_company:
            raise serializers.ValidationError(
                "Folder cannot belong to both Business Function and Company"
            )
        
        name = data.get('name')
        if name:
            instance_pk = self.instance.pk if self.instance else None
            
            if business_function:
                existing = ProcedureFolder.objects.filter(
                    business_function=business_function,
                    name__iexact=name.strip()
                ).exclude(pk=instance_pk)
                parent_name = business_function.name
            else:
                existing = ProcedureFolder.objects.filter(
                    procedure_company=procedure_company,
                    name__iexact=name.strip()
                ).exclude(pk=instance_pk)
                parent_name = procedure_company.name
            
            if existing.exists():
                raise serializers.ValidationError({
                    'name': f"A folder with this name already exists in {parent_name}"
                })
        
        return data


# ==================== COMPANY PROCEDURE SERIALIZERS ====================

class CompanyProcedureListSerializer(serializers.ModelSerializer):
    """Serializer for procedure list view"""
    
    folder_name = serializers.CharField(source='folder.name', read_only=True)
    company_code = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    file_size_display = serializers.CharField(source='get_file_size_display', read_only=True)
    procedure_url = serializers.SerializerMethodField()
    
    class Meta:
        model = CompanyProcedure
        fields = [
            'id', 'folder', 'folder_name', 'company_code', 'company_name',
            'title', 'description', 'file_size', 'file_size_display',
            'download_count', 'view_count', 'procedure_url',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['file_size', 'download_count', 'view_count', 'created_at', 'updated_at']
    
    def get_company_code(self, obj):
        return obj.get_company_code()
    
    def get_company_name(self, obj):
        return obj.get_company_name()
    
    def get_procedure_url(self, obj):
        if obj.procedure_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.procedure_file.url)
            return obj.procedure_file.url
        return None


class CompanyProcedureDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single procedure view"""
    
    folder_details = ProcedureFolderSerializer(source='folder', read_only=True)
    file_size_display = serializers.CharField(source='get_file_size_display', read_only=True)
    procedure_url = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    company_code = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    
    class Meta:
        model = CompanyProcedure
        fields = [
            'id', 'folder', 'folder_details', 'company_code', 'company_name',
            'title', 'description', 'procedure_file', 'procedure_url',
            'file_size', 'file_size_display',
            'download_count', 'view_count', 'is_active',
            'created_by', 'created_by_name', 'updated_by', 'updated_by_name',
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
    
    def get_procedure_url(self, obj):
        if obj.procedure_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.procedure_file.url)
            return obj.procedure_file.url
        return None
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None
    
    def get_updated_by_name(self, obj):
        if obj.updated_by:
            return obj.updated_by.get_full_name() or obj.updated_by.username
        return None


class CompanyProcedureCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating procedures"""
    
    procedure_file = serializers.FileField(
        required=True,
        allow_empty_file=False,
        help_text="PDF file (max 10MB)",
        write_only=False
    )
    
    class Meta:
        model = CompanyProcedure
        fields = [
            'id', 'folder', 'title', 'description',
            'procedure_file', 'is_active'
        ]
    
    def validate_procedure_file(self, value):
        if not value:
            raise serializers.ValidationError("Procedure file is required")
        
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
            raise serializers.ValidationError("Procedure title cannot be empty")
        
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
        
        if instance.procedure_file:
            request = self.context.get('request')
            if request:
                representation['procedure_url'] = request.build_absolute_uri(instance.procedure_file.url)
            else:
                representation['procedure_url'] = instance.procedure_file.url
        
        return representation