# api/procedure_views.py

from rest_framework import viewsets, status, filters, parsers, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Sum
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging

from .procedure_models import ProcedureFolder, CompanyProcedure, ProcedureCompany
from .procedure_serializers import (
    ProcedureFolderSerializer, ProcedureFolderCreateUpdateSerializer,
    CompanyProcedureListSerializer, CompanyProcedureDetailSerializer,
    CompanyProcedureCreateUpdateSerializer,
    ProcedureCompanySerializer, ProcedureCompanyCreateUpdateSerializer,
)
from .models import BusinessFunction

logger = logging.getLogger(__name__)


# ==================== PROCEDURE COMPANY VIEWS ====================

class ProcedureCompanyViewSet(viewsets.ModelViewSet):
    """ViewSet for managing manual procedure companies"""
    
    queryset = ProcedureCompany.objects.prefetch_related('procedure_folders').order_by('name')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProcedureCompanyCreateUpdateSerializer
        return ProcedureCompanySerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
      
    
    def perform_update(self, serializer):
        serializer.save()
  
    
    def perform_destroy(self, instance):
        company_name = instance.name
        
        if instance.procedure_folders.exists():
            raise serializers.ValidationError(
                f"Cannot delete company '{company_name}' - it has {instance.procedure_folders.count()} folders. "
                "Please delete all folders first."
            )
        
        instance.delete()
        


# ==================== COMBINED COMPANIES VIEW ====================

class AllProcedureCompaniesViewSet(viewsets.ViewSet):
    """ViewSet that returns both Business Functions AND Manual Companies"""
    
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get all companies (Business Functions + Manual Companies)",
        responses={200: "List of all companies"}
    )
    def list(self, request):
        """Get all companies (both types)"""
        companies = []
        
        # 1. Get Business Functions
        business_functions = BusinessFunction.objects.filter(
            is_active=True
        ).prefetch_related('procedure_folders')
        
        for bf in business_functions:
            folders = bf.procedure_folders.filter(is_active=True)
            total_procedures = sum(folder.get_procedure_count() for folder in folders)
            
            companies.append({
                'id': bf.id,
                'name': bf.name,
                'code': bf.code,
                'type': 'business_function',
                'folder_count': folders.count(),
                'total_procedure_count': total_procedures,
            })
        
        # 2. Get Manual Procedure Companies
        procedure_companies = ProcedureCompany.objects.filter(
            is_active=True
        ).prefetch_related('procedure_folders')
        
        for pc in procedure_companies:
            folders = pc.procedure_folders.filter(is_active=True)
            total_procedures = sum(folder.get_procedure_count() for folder in folders)
            
            generated_code = pc.name[:4].upper().replace(' ', '') if pc.name else 'COMP'
            
            companies.append({
                'id': pc.id,
                'name': pc.name,
                'code': generated_code,
                'type': 'procedure_company',
                'folder_count': folders.count(),
                'total_procedure_count': total_procedures,
            })
        
        companies.sort(key=lambda x: x['code'])
        
        return Response(companies)


# ==================== PROCEDURE FOLDER VIEWS ====================

class ProcedureFolderViewSet(viewsets.ModelViewSet):
    """ViewSet for managing procedure folders"""
    
    queryset = ProcedureFolder.objects.select_related(
        'business_function', 'procedure_company', 'created_by'
    ).prefetch_related('procedures')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['business_function', 'procedure_company', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProcedureFolderCreateUpdateSerializer
        return ProcedureFolderSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
        logger.info(f"Procedure folder created: {serializer.instance.name} by {self.request.user.username}")
    
    def perform_update(self, serializer):
        serializer.save()
        logger.info(f"Procedure folder updated: {serializer.instance.name} by {self.request.user.username}")
    
    def perform_destroy(self, instance):
        folder_name = instance.name
        instance.delete()
        logger.info(f"Procedure folder deleted: {folder_name} by {self.request.user.username}")
    
    @action(detail=False, methods=['get'], url_path='by-company/(?P<company_type>[^/]+)/(?P<company_id>[^/.]+)')
    def by_company(self, request, company_type=None, company_id=None):
        """Get all folders for a specific company"""
        if company_type == 'business_function':
            folders = self.queryset.filter(
                business_function_id=company_id,
                is_active=True
            )
        elif company_type == 'procedure_company':
            folders = self.queryset.filter(
                procedure_company_id=company_id,
                is_active=True
            )
        else:
            return Response(
                {'error': 'Invalid company_type. Must be "business_function" or "procedure_company"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(folders, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def procedures(self, request, pk=None):
        """Get all procedures in this folder"""
        folder = self.get_object()
        
        procedures = CompanyProcedure.objects.filter(
            folder=folder,
            is_active=True
        ).select_related('folder', 'created_by', 'updated_by').order_by('-updated_at')
        
        serializer = CompanyProcedureListSerializer(
            procedures,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)


# ==================== COMPANY PROCEDURE VIEWS ====================

class CompanyProcedureViewSet(viewsets.ModelViewSet):
    """ViewSet for managing company procedures with FILE UPLOAD support"""
    
    queryset = CompanyProcedure.objects.select_related(
        'folder', 'folder__business_function', 'folder__procedure_company',
        'created_by', 'updated_by'
    )
    
    permission_classes = [IsAuthenticated]
    
    parser_classes = [
        parsers.MultiPartParser,
        parsers.FormParser,
        parsers.JSONParser,
    ]
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['folder', 'is_active']
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'updated_at', 'created_at', 'view_count', 'download_count']
    ordering = ['-updated_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CompanyProcedureListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return CompanyProcedureCreateUpdateSerializer
        return CompanyProcedureDetailSerializer
    
    def create(self, request, *args, **kwargs):
        """Create new procedure with file upload"""
        logger.info(f"Procedure creation request from {request.user.username}")
        
        if 'procedure_file' not in request.FILES:
            return Response(
                {'error': 'procedure_file is required', 'detail': 'Please upload a PDF file'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            
            logger.info(f"Procedure created successfully: {serializer.instance.title} (ID: {serializer.instance.id})")
            
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except Exception as e:
            logger.error(f"Procedure creation failed: {str(e)}")
            raise
    
    def perform_create(self, serializer):
        procedure = serializer.save(created_by=self.request.user)
        logger.info(f"Procedure created: {procedure.title} by {self.request.user.username}")
    
    def perform_update(self, serializer):
        procedure = serializer.save(updated_by=self.request.user)
        logger.info(f"Procedure updated: {procedure.title} by {self.request.user.username}")
    
    def perform_destroy(self, instance):
        procedure_title = instance.title
        instance.delete()
        logger.info(f"Procedure deleted: {procedure_title} by {self.request.user.username}")
    
    @action(detail=False, methods=['get'], url_path='by-folder/(?P<folder_id>[^/.]+)')
    def by_folder(self, request, folder_id=None):
        """Get all procedures for a specific folder"""
        try:
            folder = ProcedureFolder.objects.get(id=folder_id)
        except ProcedureFolder.DoesNotExist:
            return Response({'error': 'Folder not found'}, status=status.HTTP_404_NOT_FOUND)
        
        procedures = self.queryset.filter(folder=folder, is_active=True)
        serializer = CompanyProcedureListSerializer(procedures, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def view(self, request, pk=None):
        """Track procedure view"""
        procedure = self.get_object()
        procedure.increment_view_count()
        
        return Response({
            'message': 'Procedure view tracked successfully',
            'view_count': procedure.view_count,
        })
    
    @action(detail=True, methods=['post'])
    def download(self, request, pk=None):
        """Track procedure download"""
        procedure = self.get_object()
        procedure.increment_download_count()
        
        return Response({
            'message': 'Procedure download tracked successfully',
            'download_count': procedure.download_count,
            'file_url': request.build_absolute_uri(procedure.procedure_file.url) if procedure.procedure_file else None
        })


# ==================== STATISTICS VIEWS ====================

class ProcedureStatisticsViewSet(viewsets.ViewSet):
    """ViewSet for procedure statistics and analytics"""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get overall procedure statistics"""
        total_procedures = CompanyProcedure.objects.filter(is_active=True).count()
        total_folders = ProcedureFolder.objects.filter(is_active=True).count()
        
        total_business_functions = BusinessFunction.objects.filter(
            is_active=True,
            procedure_folders__isnull=False
        ).distinct().count()
        
        total_procedure_companies = ProcedureCompany.objects.filter(
            is_active=True,
            procedure_folders__isnull=False
        ).distinct().count()
        
        procedures = CompanyProcedure.objects.filter(is_active=True)
        
        total_views = sum(p.view_count for p in procedures)
        total_downloads = sum(p.download_count for p in procedures)
        
        return Response({
            'total_procedures': total_procedures,
            'total_folders': total_folders,
            'total_business_functions': total_business_functions + total_procedure_companies,
            'total_views': total_views,
            'total_downloads': total_downloads,
        })