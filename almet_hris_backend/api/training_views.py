# api/training_views.py
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .training_models import (
    Training, TrainingMaterial,
    TrainingAssignment, TrainingActivity
)
from .training_serializers import (
    TrainingListSerializer,
    TrainingDetailSerializer, TrainingMaterialSerializer,
    TrainingAssignmentSerializer, BulkTrainingAssignmentSerializer,
    TrainingMaterialUploadSerializer
)
from .models import Employee
from .views import ModernPagination

import logging
logger = logging.getLogger(__name__)


class TrainingViewSet(viewsets.ModelViewSet):
    """Training ViewSet with CRUD and advanced features"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    pagination_class = ModernPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['title', 'description', 'training_id']
    ordering_fields = ['created_at', 'title']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Training.objects.prefetch_related(
            'materials', 'business_functions', 'departments', 'position_groups'
        ).filter(is_deleted=False)
    
    def get_serializer_class(self):
        if self.action == 'list':
            return TrainingListSerializer
        return TrainingDetailSerializer
    
    @swagger_auto_schema(
        responses={
            201: TrainingDetailSerializer,
            400: 'Bad Request',
            500: 'Internal Server Error'
        },
        auto_schema=None
    )
    def create(self, request, *args, **kwargs):
        """Create training with materials"""
        try:

            title = request.data.get('title')
            description = request.data.get('description')
            
            if not title or not description:
                return Response(
                    {'error': 'Title and description are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get basic data with proper type conversion
            data = {
                'title': str(title).strip(),
                'description': str(description).strip(),
                'is_active': str(request.data.get('is_active', 'true')).lower() == 'true',
                'requires_completion': str(request.data.get('requires_completion', 'false')).lower() == 'true',
            }

            # Add optional completion deadline
            completion_deadline_days = request.data.get('completion_deadline_days')
            if completion_deadline_days:
                try:
                    data['completion_deadline_days'] = int(completion_deadline_days)
           
                except (ValueError, TypeError):
                    print(f"⚠️ Invalid completion_deadline_days: {completion_deadline_days}")
            
            # Create training
            training = Training.objects.create(
                created_by=request.user,
                **data
            )
        
            
            # Process materials
            materials_data_str = request.data.get('materials_data')
            if materials_data_str:
      
                
                try:
                    import json
                    materials_data = json.loads(materials_data_str)
      
                    materials_created = 0
                    for material_info in materials_data:
                        file_index = material_info.get('file_index')
              
                        
                        # Get file from request.FILES
                        if file_index is not None:
                            file_key = f'material_{file_index}_file'
                            file_obj = request.FILES.get(file_key)
                            
                            if file_obj:
   
                                
                                # Create material with file
                                material = TrainingMaterial.objects.create(
                                    training=training,
                                    uploaded_by=request.user,
                                    file=file_obj,
                                    file_size=file_obj.size
                                )
                                materials_created += 1
                               
                            else:
                                print(f"⚠️ No file found for key: {file_key}")
                        else:
                            print(f"⚠️ No file_index in material_info")
                    
                   
                    
                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {str(e)}")
                    print(f"❌ Raw materials_data: {materials_data_str}")
                except Exception as e:
                    print(f"❌ Error processing materials: {str(e)}")
                    import traceback
                    traceback.print_exc()
            else:
                print("ℹ️ No materials_data provided")
            
            
            
            # Return created training with all data
            serializer = TrainingDetailSerializer(training, context={'request': request})
        
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
         
            import traceback
            traceback.print_exc()
            print("=" * 70)
            
            logger.error(f"Training creation failed: {str(e)}")
            return Response(
                {'error': f'Failed to create training: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
    responses={
        200: TrainingDetailSerializer,
        400: 'Bad Request',
        404: 'Not Found',
        500: 'Internal Server Error'
    },
    auto_schema=None
)
    def update(self, request, *args, **kwargs):
        """Update training with materials"""
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            
  
            delete_material_ids_str = request.data.get('delete_material_ids')
            if delete_material_ids_str:

                try:
                    import json
                    delete_material_ids = json.loads(delete_material_ids_str) if isinstance(delete_material_ids_str, str) else delete_material_ids_str
                    
                    if delete_material_ids and isinstance(delete_material_ids, list):
                        # Get materials to delete
                        materials_to_delete = TrainingMaterial.objects.filter(
                            id__in=delete_material_ids,
                            training=instance,
                            is_deleted=False
                        )
                        
                        
                        # Soft delete materials
                        for material in materials_to_delete:
                            material.is_deleted = True
                            material.save()
                           
                    else:
                        print("⚠️ delete_material_ids is empty or invalid")
                        
                except json.JSONDecodeError as e:
            
                    return Response(
                        {'error': f'Invalid delete_material_ids format: {str(e)}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                except Exception as e:
                    print(f"❌ Error deleting materials: {str(e)}")
                    import traceback
                    traceback.print_exc()
            else:
                print("ℹ️ No materials to delete")
       
            # Update basic fields
            if 'title' in request.data:
                instance.title = str(request.data.get('title')).strip()
                
            if 'description' in request.data:
                instance.description = str(request.data.get('description')).strip()
             
                
            if 'is_active' in request.data:
                instance.is_active = str(request.data.get('is_active', 'true')).lower() == 'true'
              
                
            if 'requires_completion' in request.data:
                instance.requires_completion = str(request.data.get('requires_completion', 'false')).lower() == 'true'

            
            # Update completion deadline
            if 'completion_deadline_days' in request.data:
                completion_deadline_days = request.data.get('completion_deadline_days')
                if completion_deadline_days:
                    try:
                        instance.completion_deadline_days = int(completion_deadline_days)
                
                    except (ValueError, TypeError):
                        print(f"⚠️ Invalid completion_deadline_days: {completion_deadline_days}")
                else:
                    instance.completion_deadline_days = None
                
            
            # Save training
            instance.save()
    
            # 📦 ADD NEW MATERIALS (if provided)
            materials_data_str = request.data.get('materials_data')
            if materials_data_str:
                
                try:
                    import json
                    materials_data = json.loads(materials_data_str)
                 
                    
                    materials_created = 0
                    for material_info in materials_data:
                        file_index = material_info.get('file_index')
                        
                        if file_index is not None:
                            file_key = f'material_{file_index}_file'
                            file_obj = request.FILES.get(file_key)
                            
                            if file_obj:
                              
                                
                                material = TrainingMaterial.objects.create(
                                    training=instance,
                                    uploaded_by=request.user,
                                    file=file_obj,
                                    file_size=file_obj.size
                                )
                                materials_created += 1
                                
                            else:
                                print(f"⚠️ No file found for key: {file_key}")
                    
          
                    
                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {str(e)}")
                except Exception as e:
                    print(f"❌ Error processing materials: {str(e)}")
                    import traceback
                    traceback.print_exc()
            else:
                print("ℹ️ No new materials to add")
            
            # Return updated training
            serializer = TrainingDetailSerializer(instance, context={'request': request})
         
            return Response(serializer.data)
            
        except Exception as e:
          
            print(f"❌ FATAL ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
      
            
            logger.error(f"Training update failed: {str(e)}")
            return Response(
                {'error': f'Failed to update training: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    @swagger_auto_schema(
        operation_description="Partial update training",
        responses={
            200: TrainingDetailSerializer,
            400: 'Bad Request',
            404: 'Not Found',
            500: 'Internal Server Error'
        },
        auto_schema=None
    )
    def partial_update(self, request, *args, **kwargs):
        """Partial update training"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_description="Get training statistics",
        responses={200: openapi.Response(description="Training statistics")}
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get overall training statistics"""
        try:
            trainings = Training.objects.filter(is_deleted=False)
            
            total_trainings = trainings.count()
            active_trainings = trainings.filter(is_active=True).count()
            
            # Assignment statistics
            total_assignments = TrainingAssignment.objects.filter(is_deleted=False).count()
            completed = TrainingAssignment.objects.filter(
                status='COMPLETED',
                is_deleted=False
            ).count()
            in_progress = TrainingAssignment.objects.filter(
                status='IN_PROGRESS',
                is_deleted=False
            ).count()
            overdue = TrainingAssignment.objects.filter(
                status='OVERDUE',
                is_deleted=False
            ).count()
            
            completion_rate = 0
            if total_assignments > 0:
                completion_rate = round((completed / total_assignments) * 100, 2)
            
            return Response({
                'overview': {
                    'total_trainings': total_trainings,
                    'active_trainings': active_trainings,
                    'inactive_trainings': total_trainings - active_trainings,
                },
                'assignments': {
                    'total': total_assignments,
                    'completed': completed,
                    'in_progress': in_progress,
                    'overdue': overdue,
                    'completion_rate': completion_rate
                }
            })
        except Exception as e:
            logger.error(f"Statistics retrieval failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        responses={
            201: TrainingMaterialSerializer,
            400: 'Bad Request',
            500: 'Internal Server Error'
        },
        auto_schema=None
    )
    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_material(self, request, pk=None):
        """Upload training material (PDF, video, etc.)"""
        try:
            training = self.get_object()
            
            # Validate input data
            serializer = TrainingMaterialUploadSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            validated_data = serializer.validated_data
            
            # Create material
            material = TrainingMaterial.objects.create(
                training=training,
                file=validated_data.get('file'),
                uploaded_by=request.user
            )
            
            # Set file size if file uploaded
            if material.file:
                material.file_size = material.file.size
                material.save()
            
            response_serializer = TrainingMaterialSerializer(material, context={'request': request})
            
            logger.info(f"Material uploaded for training {training.training_id}")
            
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Material upload failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        operation_description="Bulk assign trainings to employees",
        request_body=BulkTrainingAssignmentSerializer,
        responses={200: openapi.Response(description="Assignment completed")}
    )
    @action(detail=False, methods=['post'])
    def bulk_assign(self, request):
        """Assign multiple trainings to multiple employees"""
        try:
            serializer = BulkTrainingAssignmentSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            training_ids = serializer.validated_data['training_ids']
            employee_ids = serializer.validated_data['employee_ids']
            due_date = serializer.validated_data.get('due_date')
            is_mandatory = serializer.validated_data.get('is_mandatory', False)
            
            # Get trainings and employees
            trainings = Training.objects.filter(id__in=training_ids, is_active=True, is_deleted=False)
            employees = Employee.objects.filter(id__in=employee_ids, is_deleted=False)
            
            if trainings.count() != len(training_ids):
                return Response(
                    {'error': 'Some trainings not found or inactive'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if employees.count() != len(employee_ids):
                return Response(
                    {'error': 'Some employees not found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            created = []
            skipped = []
            
            with transaction.atomic():
                for training in trainings:
                    # Calculate due date for this training if not provided
                    calculated_due_date = due_date
                    if not calculated_due_date and training.completion_deadline_days:
                        calculated_due_date = timezone.now().date() + timedelta(
                            days=training.completion_deadline_days
                        )
                    
                    for employee in employees:
                        # Check if already assigned
                        existing = TrainingAssignment.objects.filter(
                            training=training,
                            employee=employee,
                            is_deleted=False
                        ).first()
                        
                        if existing:
                            skipped.append({
                                'training_id': training.training_id,
                                'training_title': training.title,
                                'employee_id': employee.employee_id,
                                'employee_name': employee.full_name,
                                'reason': 'Already assigned'
                            })
                            continue
                        
                        # Create assignment
                        assignment = TrainingAssignment.objects.create(
                            training=training,
                            employee=employee,
                            due_date=calculated_due_date,
                            is_mandatory=is_mandatory,
                            assigned_by=request.user
                        )
                        
                        # Log activity
                        TrainingActivity.objects.create(
                            assignment=assignment,
                            activity_type='ASSIGNED',
                            description=f"Training assigned to {employee.full_name}",
                            performed_by=request.user,
                            metadata={
                                'due_date': str(calculated_due_date) if calculated_due_date else None,
                              
                            }
                        )
                        
                        created.append({
                            'training_id': training.training_id,
                            'training_title': training.title,
                            'employee_id': employee.employee_id,
                            'employee_name': employee.full_name,
                            'assignment_id': assignment.id
                        })
            
            return Response({
                'success': True,
                'message': f'{len(created)} assignments created',
                'created': created,
                'skipped': skipped,
                'summary': {
                    'total_requested': len(training_ids) * len(employee_ids),
                    'created': len(created),
                    'skipped': len(skipped)
                }
            })
            
        except Exception as e:
            logger.error(f"Bulk assignment failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TrainingAssignmentViewSet(viewsets.ModelViewSet):
    """Training Assignment ViewSet"""
    serializer_class = TrainingAssignmentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ModernPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['training', 'employee', 'status', 'is_mandatory']
    search_fields = ['training__title', 'employee__full_name', 'employee__employee_id']
    ordering_fields = ['assigned_date', 'due_date', 'completed_date']
    ordering = ['-assigned_date', 'due_date']
    
    def get_queryset(self):
        return TrainingAssignment.objects.select_related(
            'training', 'employee', 'assigned_by'
        ).prefetch_related('materials_completed').filter(is_deleted=False)
    
    @swagger_auto_schema(
        operation_description="Get assignments for specific employee",
        responses={200: TrainingAssignmentSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def my_trainings(self, request):
        """Get trainings assigned to current user's employee profile"""
        try:
            employee = Employee.objects.get(user=request.user, is_deleted=False)
            
            assignments = self.get_queryset().filter(employee=employee)
            
            # Apply filters
            status_filter = request.query_params.get('status')
            if status_filter:
                assignments = assignments.filter(status=status_filter)
            
            serializer = self.get_serializer(assignments, many=True)
            
            return Response({
                'employee': {
                    'id': employee.id,
                    'name': employee.full_name,
                    'employee_id': employee.employee_id
                },
                'assignments': serializer.data,
                'summary': {
                    'total': assignments.count(),
                    'assigned': assignments.filter(status='ASSIGNED').count(),
                    'in_progress': assignments.filter(status='IN_PROGRESS').count(),
                    'completed': assignments.filter(status='COMPLETED').count(),
                    'overdue': assignments.filter(status='OVERDUE').count(),
                }
            })
        except Employee.DoesNotExist:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"My trainings retrieval failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        operation_description="Mark material as completed",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'material_id': openapi.Schema(type=openapi.TYPE_INTEGER)
            }
        ),
        responses={200: TrainingAssignmentSerializer}
    )
    @action(detail=True, methods=['post'])
    def complete_material(self, request, pk=None):
        """Mark a training material as completed"""
        try:
            assignment = self.get_object()
            material_id = request.data.get('material_id')
            
            if not material_id:
                return Response(
                    {'error': 'material_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                material = TrainingMaterial.objects.get(
                    id=material_id,
                    training=assignment.training,
                    is_deleted=False
                )
            except TrainingMaterial.DoesNotExist:
                return Response(
                    {'error': 'Material not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Add to completed materials
            if material not in assignment.materials_completed.all():
                assignment.materials_completed.add(material)
                
                # Update status to IN_PROGRESS if ASSIGNED
                if assignment.status == 'ASSIGNED':
                    assignment.status = 'IN_PROGRESS'
                    assignment.started_date = timezone.now()
                
                # Calculate progress
                assignment.calculate_progress()
                
                # Check if training is completed
                assignment.check_completion()
                
                # Log activity
                TrainingActivity.objects.create(
                    assignment=assignment,
                    activity_type='MATERIAL_VIEWED',
                    description=f"Completed material",
                    material=material,
                    performed_by=request.user
                )
                
                if assignment.status == 'COMPLETED':
                    TrainingActivity.objects.create(
                        assignment=assignment,
                        activity_type='COMPLETED',
                        description=f"Training completed",
                        performed_by=request.user
                    )
            
            serializer = self.get_serializer(assignment)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Material completion failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        operation_description="Get overdue assignments",
        responses={200: TrainingAssignmentSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get all overdue training assignments"""
        try:
            today = timezone.now().date()
            
            overdue_assignments = self.get_queryset().filter(
                due_date__lt=today,
                status__in=['ASSIGNED', 'IN_PROGRESS']
            )
            
            # Update status to OVERDUE
            overdue_assignments.update(status='OVERDUE')
            
            serializer = self.get_serializer(overdue_assignments, many=True)
            
            return Response({
                'count': overdue_assignments.count(),
                'assignments': serializer.data
            })
        except Exception as e:
            logger.error(f"Overdue retrieval failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TrainingMaterialViewSet(viewsets.ModelViewSet):
    """Training Material ViewSet"""
    serializer_class = TrainingMaterialSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['training']  #
    ordering_fields = ['created_at']
    
    def get_queryset(self):
        return TrainingMaterial.objects.select_related(
            'training', 'uploaded_by'
        ).filter(is_deleted=False)