# api/policy_views.py - UPDATED with PolicyCompany Support

from rest_framework import viewsets, status, filters, parsers, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Sum, Prefetch
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging

from .policy_models import (
    PolicyFolder, CompanyPolicy, PolicyAcknowledgment, PolicyCompany
)
from .policy_serializers import (
    PolicyFolderSerializer, PolicyFolderCreateUpdateSerializer,
    CompanyPolicyListSerializer, CompanyPolicyDetailSerializer,
    CompanyPolicyCreateUpdateSerializer, PolicyAcknowledgmentSerializer,
    BusinessFunctionWithFoldersSerializer,
    PolicyCompanySerializer, PolicyCompanyCreateUpdateSerializer,
)
from .models import BusinessFunction, Employee

logger = logging.getLogger(__name__)


# ==================== POLICY COMPANY VIEWS ====================

class PolicyCompanyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing manual policy companies
    """
    
    queryset = PolicyCompany.objects.prefetch_related('policy_folders').order_by('code')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code']
    ordering_fields = ['code', 'name', 'created_at']
    ordering = ['code']
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return PolicyCompanyCreateUpdateSerializer
        return PolicyCompanySerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
        logger.info(f"Policy company created: {serializer.instance.name} by {self.request.user.username}")
    
    def perform_update(self, serializer):
        serializer.save()
        logger.info(f"Policy company updated: {serializer.instance.name} by {self.request.user.username}")
    
    def perform_destroy(self, instance):
        company_name = instance.name
        
        # Check if has folders
        if instance.policy_folders.exists():
            raise serializers.ValidationError(
                f"Cannot delete company '{company_name}' - it has {instance.policy_folders.count()} folders. "
                "Please delete all folders first."
            )
        
        instance.delete()
        logger.info(f"Policy company deleted: {company_name} by {self.request.user.username}")


# ==================== COMBINED COMPANIES VIEW ====================

class AllCompaniesViewSet(viewsets.ViewSet):
    """
    ViewSet that returns both Business Functions AND Manual Companies
    for the Companies view in frontend
    """
    
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get all companies (Business Functions + Manual Companies)",
        responses={
            200: openapi.Response(
                description="List of all companies",
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'name': openapi.Schema(type=openapi.TYPE_STRING),
                            'code': openapi.Schema(type=openapi.TYPE_STRING),
                            'type': openapi.Schema(type=openapi.TYPE_STRING, description="'business_function' or 'policy_company'"),
                            'folder_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'total_policy_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                        }
                    )
                )
            )
        }
    )
    def list(self, request):
        """Get all companies (both types)"""
        companies = []
        
        # 1. Get Business Functions
        business_functions = BusinessFunction.objects.filter(
            is_active=True
        ).prefetch_related('policy_folders')
        
        for bf in business_functions:
            folders = bf.policy_folders.filter(is_active=True)
            total_policies = sum(folder.get_policy_count() for folder in folders)
            
            companies.append({
                'id': bf.id,
                'name': bf.name,
                'code': bf.code,
                'type': 'business_function',
                'folder_count': folders.count(),
                'total_policy_count': total_policies,
            })
        
        # 2. Get Manual Policy Companies
        policy_companies = PolicyCompany.objects.filter(
            is_active=True
        ).prefetch_related('policy_folders')
        
        for pc in policy_companies:
            folders = pc.policy_folders.filter(is_active=True)
            total_policies = sum(folder.get_policy_count() for folder in folders)
            
            # Generate code from name
            generated_code = pc.name[:4].upper().replace(' ', '') if pc.name else 'COMP'
            
            companies.append({
                'id': pc.id,
                'name': pc.name,
                'code': generated_code,
                'type': 'policy_company',
                'folder_count': folders.count(),
                'total_policy_count': total_policies,
            })
        
        # Sort by code
        companies.sort(key=lambda x: x['code'])
        
        return Response(companies)


# ==================== POLICY FOLDER VIEWS ====================

class PolicyFolderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing policy folders
    """
    
    queryset = PolicyFolder.objects.select_related(
        'business_function', 'policy_company', 'created_by'
    ).prefetch_related('policies')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['business_function', 'policy_company', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return PolicyFolderCreateUpdateSerializer
        return PolicyFolderSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
        logger.info(f"Policy folder created: {serializer.instance.name} by {self.request.user.username}")
    
    def perform_update(self, serializer):
        serializer.save()
        logger.info(f"Policy folder updated: {serializer.instance.name} by {self.request.user.username}")
    
    def perform_destroy(self, instance):
        folder_name = instance.name
        instance.delete()
        logger.info(f"Policy folder deleted: {folder_name} by {self.request.user.username}")
    
    @action(detail=False, methods=['get'], url_path='by-company/(?P<company_type>[^/]+)/(?P<company_id>[^/.]+)')
    def by_company(self, request, company_type=None, company_id=None):
        """
        Get all folders for a specific company
        company_type: 'business_function' or 'policy_company'
        company_id: ID of the company
        """
        if company_type == 'business_function':
            folders = self.queryset.filter(
                business_function_id=company_id,
                is_active=True
            )
        elif company_type == 'policy_company':
            folders = self.queryset.filter(
                policy_company_id=company_id,
                is_active=True
            )
        else:
            return Response(
                {'error': 'Invalid company_type. Must be "business_function" or "policy_company"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(folders, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def policies(self, request, pk=None):
        """Get all policies in this folder"""
        folder = self.get_object()
        
        policies = CompanyPolicy.objects.filter(
            folder=folder,
            is_active=True
        ).select_related('folder', 'created_by', 'updated_by').order_by('-updated_at')
        
        serializer = CompanyPolicyListSerializer(
            policies,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)


# ==================== COMPANY POLICY VIEWS ====================

class CompanyPolicyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing company policies with FILE UPLOAD support
    """
    
    queryset = CompanyPolicy.objects.select_related(
        'folder', 'folder__business_function', 'folder__policy_company',
        'created_by', 'updated_by', 
    ).prefetch_related('acknowledgments')
    
    permission_classes = [IsAuthenticated]
    
    parser_classes = [
        parsers.MultiPartParser,
        parsers.FormParser,
        parsers.JSONParser,
    ]
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['folder', 'requires_acknowledgment', 'is_active']
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'updated_at', 'created_at', 'view_count', 'download_count']
    ordering = ['-updated_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CompanyPolicyListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return CompanyPolicyCreateUpdateSerializer
        return CompanyPolicyDetailSerializer
    
    def create(self, request, *args, **kwargs):
        """Create new policy with file upload"""
        logger.info(f"Policy creation request from {request.user.username}")
        
        if 'policy_file' not in request.FILES:
            return Response(
                {'error': 'policy_file is required', 'detail': 'Please upload a PDF file'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            
            logger.info(f"Policy created successfully: {serializer.instance.title} (ID: {serializer.instance.id})")
            
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except Exception as e:
            logger.error(f"Policy creation failed: {str(e)}")
            raise
    
    def update(self, request, *args, **kwargs):
        """Update policy with optional file replacement"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        logger.info(f"Policy update request for '{instance.title}' by {request.user.username}")
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Policy update failed: {str(e)}")
            raise
    
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        policy = serializer.save(created_by=self.request.user)
        logger.info(f"Policy created: {policy.title} by {self.request.user.username}")
    
    def perform_update(self, serializer):
        policy = serializer.save(updated_by=self.request.user)
        logger.info(f"Policy updated: {policy.title} by {self.request.user.username}")
    
    def perform_destroy(self, instance):
        policy_title = instance.title
        instance.delete()
        logger.info(f"Policy deleted: {policy_title} by {self.request.user.username}")
    
    @action(detail=False, methods=['get'], url_path='by-folder/(?P<folder_id>[^/.]+)')
    def by_folder(self, request, folder_id=None):
        """Get all policies for a specific folder"""
        try:
            folder = PolicyFolder.objects.get(id=folder_id)
        except PolicyFolder.DoesNotExist:
            return Response({'error': 'Folder not found'}, status=status.HTTP_404_NOT_FOUND)
        
        policies = self.queryset.filter(folder=folder, is_active=True)
        serializer = CompanyPolicyListSerializer(policies, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def view(self, request, pk=None):
        """Track policy view"""
        policy = self.get_object()
        policy.increment_view_count()
        
        return Response({
            'message': 'Policy view tracked successfully',
            'view_count': policy.view_count,
        })
    
    @action(detail=True, methods=['post'])
    def download(self, request, pk=None):
        """Track policy download"""
        policy = self.get_object()
        policy.increment_download_count()
        
        return Response({
            'message': 'Policy download tracked successfully',
            'download_count': policy.download_count,
            'file_url': request.build_absolute_uri(policy.policy_file.url) if policy.policy_file else None
        })
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Acknowledge policy reading"""
        policy = self.get_object()
        
        try:
            employee = Employee.objects.get(user=request.user)
        except Employee.DoesNotExist:
            return Response(
                {'error': 'Employee profile not found for this user'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if PolicyAcknowledgment.objects.filter(policy=policy, employee=employee).exists():
            return Response(
                {'message': 'Policy already acknowledged', 'already_acknowledged': True},
                status=status.HTTP_200_OK
            )
        
        acknowledgment = PolicyAcknowledgment.objects.create(
            policy=policy,
            employee=employee,
            ip_address=self._get_client_ip(request),
            notes=request.data.get('notes', '')
        )
        
        serializer = PolicyAcknowledgmentSerializer(acknowledgment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def acknowledgments(self, request, pk=None):
        """Get all acknowledgments for this policy"""
        policy = self.get_object()
        
        acknowledgments = PolicyAcknowledgment.objects.filter(
            policy=policy
        ).select_related('employee').order_by('-acknowledged_at')
        
        page = self.paginate_queryset(acknowledgments)
        if page is not None:
            serializer = PolicyAcknowledgmentSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = PolicyAcknowledgmentSerializer(acknowledgments, many=True)
        return Response(serializer.data)
    
    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# ==================== STATISTICS VIEWS ====================

class PolicyStatisticsViewSet(viewsets.ViewSet):
    """
    ViewSet for policy statistics and analytics
    """
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get overall policy statistics"""
        total_policies = CompanyPolicy.objects.filter(is_active=True).count()
        total_folders = PolicyFolder.objects.filter(is_active=True).count()
        
        # Count both types of companies
        total_business_functions = BusinessFunction.objects.filter(
            is_active=True,
            policy_folders__isnull=False
        ).distinct().count()
        
        total_policy_companies = PolicyCompany.objects.filter(
            is_active=True,
            policy_folders__isnull=False
        ).distinct().count()
        
        policies = CompanyPolicy.objects.filter(is_active=True)
        policies_requiring_ack = policies.filter(requires_acknowledgment=True).count()
        
        total_views = sum(p.view_count for p in policies)
        total_downloads = sum(p.download_count for p in policies)
        
        return Response({
            'total_policies': total_policies,
            'total_folders': total_folders,
            'total_business_functions': total_business_functions + total_policy_companies,
            'policies_requiring_acknowledgment': policies_requiring_ack,
            'total_views': total_views,
            'total_downloads': total_downloads,
        })