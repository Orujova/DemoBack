# api/self_assessment_views.py - Updated with Permission System

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.db.models import Q, Avg, Count
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from .self_assessment_models import (
    AssessmentPeriod, SelfAssessment, SkillRating, AssessmentActivity
)
from .self_assessment_serializers import (
    AssessmentPeriodSerializer, AssessmentPeriodCreateSerializer,
    SelfAssessmentDetailSerializer, SelfAssessmentListSerializer,
    SelfAssessmentCreateSerializer,
    SkillRatingSerializer, SkillRatingCreateUpdateSerializer,
    AssessmentActivitySerializer, AssessmentStatsSerializer
)
from .models import Employee
from .self_assessment_permissions import (
    get_self_assessment_access, filter_assessment_queryset,
    can_user_view_assessment, can_user_edit_assessment,
    can_user_submit_assessment, can_user_review_assessment,
    can_user_manage_periods
)


class AssessmentPeriodViewSet(viewsets.ModelViewSet):
    """Assessment Period Management - Admin Only"""
    queryset = AssessmentPeriod.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return AssessmentPeriodCreateSerializer
        return AssessmentPeriodSerializer
    
    def list(self, request, *args, **kwargs):
        """All users can view periods"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        """Only admins can create periods"""
        if not can_user_manage_periods(request.user):
            return Response(
                {'detail': 'Only administrators can manage assessment periods'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """Only admins can update periods"""
        if not can_user_manage_periods(request.user):
            return Response(
                {'detail': 'Only administrators can manage assessment periods'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Only admins can delete periods"""
        if not can_user_manage_periods(request.user):
            return Response(
                {'detail': 'Only administrators can manage assessment periods'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active assessment period"""
        active_period = AssessmentPeriod.get_active_period()
        if active_period:
            serializer = self.get_serializer(active_period)
            return Response(serializer.data)
        return Response(
            {'detail': 'No active assessment period'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate this period - Admin only"""
        if not can_user_manage_periods(request.user):
            return Response(
                {'detail': 'Only administrators can activate periods'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        period = self.get_object()
        period.is_active = True
        period.status = 'ACTIVE'
        period.save()
        serializer = self.get_serializer(period)
        return Response(serializer.data)


class SelfAssessmentViewSet(viewsets.ModelViewSet):
    """Self Assessment CRUD with Permission Control"""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return SelfAssessmentCreateSerializer
        elif self.action == 'list':
            return SelfAssessmentListSerializer
        return SelfAssessmentDetailSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = SelfAssessment.objects.select_related(
            'employee', 'period'
        ).prefetch_related('skill_ratings__skill__group').all()
        
        # Apply permission filtering
        return filter_assessment_queryset(user, queryset)
    
    def retrieve(self, request, *args, **kwargs):
        """Check view permission"""
        assessment = self.get_object()
        can_view, message = can_user_view_assessment(request.user, assessment)
        
        if not can_view:
            return Response(
                {'detail': 'You do not have permission to view this assessment'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(assessment)
        return Response(serializer.data)
    
    def perform_create(self, serializer):
        try:
            employee = Employee.objects.get(user=self.request.user)
        except Employee.DoesNotExist:
            raise serializers.ValidationError('Employee profile not found')
        
        assessment = serializer.save(employee=employee)
        
        # Log activity
        AssessmentActivity.objects.create(
            assessment=assessment,
            activity_type='CREATED',
            description=f'Assessment created for period {assessment.period.name}',
            performed_by=self.request.user
        )
    
    @action(detail=False, methods=['get'])
    def my_assessments(self, request):
        """Get current user's assessments"""
        try:
            employee = Employee.objects.get(user=request.user)
        except Employee.DoesNotExist:
            return Response(
                {'detail': 'Employee profile not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        assessments = SelfAssessment.objects.filter(
            employee=employee
        ).select_related('period').order_by('-created_at')
        
        serializer = SelfAssessmentListSerializer(assessments, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def team_assessments(self, request):
        """Get assessments of direct reports (Manager view)"""
        access = get_self_assessment_access(request.user)
        
        if not access['is_manager']:
            return Response(
                {'detail': 'No direct reports found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Admin sees all except own
        if access['can_view_all']:
            if access['employee']:
                assessments = SelfAssessment.objects.exclude(
                    employee=access['employee']
                ).select_related('employee', 'period').order_by('-created_at')
            else:
                assessments = SelfAssessment.objects.all().select_related(
                    'employee', 'period'
                ).order_by('-created_at')
        else:
            # Manager sees direct reports only
            if not access['accessible_employee_ids']:
                return Response([], status=status.HTTP_200_OK)
            
            # Exclude own assessment
            team_ids = [id for id in access['accessible_employee_ids'] 
                        if id != (access['employee'].id if access['employee'] else None)]
            
            if not team_ids:
                return Response([], status=status.HTTP_200_OK)
            
            assessments = SelfAssessment.objects.filter(
                employee_id__in=team_ids
            ).select_related('employee', 'period').order_by('-created_at')
        
        serializer = SelfAssessmentListSerializer(assessments, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def start_assessment(self, request):
        """Start new assessment for active period"""
        try:
            employee = Employee.objects.get(user=request.user)
        except Employee.DoesNotExist:
            return Response(
                {'detail': 'Employee profile not found'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get active period
        period = AssessmentPeriod.get_active_period()
        if not period:
            return Response(
                {'detail': 'No active assessment period'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if already exists
        existing = SelfAssessment.objects.filter(
            employee=employee,
            period=period
        ).first()
        
        if existing:
            serializer = SelfAssessmentDetailSerializer(
                existing, 
                context={'request': request}
            )
            return Response(serializer.data)
        
        # Create new assessment
        assessment = SelfAssessment.objects.create(
            employee=employee,
            period=period,
            status='DRAFT'
        )
        
        # Log activity
        AssessmentActivity.objects.create(
            assessment=assessment,
            activity_type='CREATED',
            description=f'Assessment started for period {period.name}',
            performed_by=request.user
        )
        
        serializer = SelfAssessmentDetailSerializer(
            assessment, 
            context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit assessment"""
        assessment = self.get_object()
        
        # Check permission
        if not can_user_submit_assessment(request.user, assessment):
            return Response(
                {'detail': 'Cannot submit this assessment'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if has ratings
        if not assessment.skill_ratings.exists():
            return Response(
                {'detail': 'Please add skill ratings before submitting'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Submit
        assessment.submit()
        
        serializer = self.get_serializer(assessment)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def manager_review(self, request, pk=None):
        """Manager reviews assessment"""
        assessment = self.get_object()
        
        # Check permission
        if not can_user_review_assessment(request.user, assessment):
            return Response(
                {'detail': 'You do not have permission to review this assessment'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Update manager comments
        manager_comments = request.data.get('manager_comments', '')
        
        with transaction.atomic():
            assessment.status = 'REVIEWED'
            assessment.manager_comments = manager_comments
            assessment.manager_reviewed_by = request.user
            assessment.manager_reviewed_at = timezone.now()
            assessment.save()
            
            # Update individual rating comments if provided
            rating_comments = request.data.get('rating_comments', [])
            for comment_data in rating_comments:
                rating_id = comment_data.get('rating_id')
                manager_comment = comment_data.get('manager_comment', '')
                
                SkillRating.objects.filter(
                    id=rating_id, 
                    assessment=assessment
                ).update(manager_comment=manager_comment)
            
            # Log activity
            AssessmentActivity.objects.create(
                assessment=assessment,
                activity_type='REVIEWED',
                description='Assessment reviewed by manager',
                performed_by=request.user
            )
        
        serializer = self.get_serializer(assessment)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """Get assessment activities"""
        assessment = self.get_object()
        
        # Check view permission
        can_view, _ = can_user_view_assessment(request.user, assessment)
        if not can_view:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        activities = assessment.activities.all()
        serializer = AssessmentActivitySerializer(activities, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_rating(self, request, pk=None):
        """Add or update a skill rating"""
        assessment = self.get_object()
        
        # Check permission
        if not can_user_edit_assessment(request.user, assessment):
            return Response(
                {'detail': 'Cannot modify this assessment'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = SkillRatingCreateUpdateSerializer(data=request.data)
        if serializer.is_valid():
            # Update or create rating
            skill_rating, created = SkillRating.objects.update_or_create(
                assessment=assessment,
                skill=serializer.validated_data['skill'],
                defaults={
                    'rating': serializer.validated_data['rating'],
                    'self_comment': serializer.validated_data.get('self_comment', '')
                }
            )
            
            # Recalculate overall score
            assessment.calculate_overall_score()
            
            # Log activity
            action_text = 'added' if created else 'updated'
            AssessmentActivity.objects.create(
                assessment=assessment,
                activity_type='RATING_CHANGED',
                description=f'Skill rating {action_text}: {skill_rating.skill.name}',
                performed_by=request.user,
                metadata={'skill_id': skill_rating.skill.id, 'rating': skill_rating.rating}
            )
            
            response_serializer = SkillRatingSerializer(skill_rating)
            return Response(response_serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def bulk_add_ratings(self, request, pk=None):
        """Bulk add/update skill ratings"""
        assessment = self.get_object()
        
        # Check permission
        if not can_user_edit_assessment(request.user, assessment):
            return Response(
                {'detail': 'Cannot modify this assessment'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        ratings_data = request.data.get('ratings', [])
        
        with transaction.atomic():
            for rating_data in ratings_data:
                SkillRating.objects.update_or_create(
                    assessment=assessment,
                    skill_id=rating_data['skill'],
                    defaults={
                        'rating': rating_data['rating'],
                        'self_comment': rating_data.get('self_comment', '')
                    }
                )
            
            # Recalculate overall score
            assessment.calculate_overall_score()
            
            # Log activity
            AssessmentActivity.objects.create(
                assessment=assessment,
                activity_type='UPDATED',
                description=f'Bulk updated {len(ratings_data)} skill ratings',
                performed_by=request.user
            )
        
        serializer = self.get_serializer(assessment)
        return Response(serializer.data)


class AssessmentStatsView(APIView):
    """Assessment statistics for current user"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        access = get_self_assessment_access(request.user)
        
        if not access['employee']:
            return Response(
                {'detail': 'Employee profile not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        employee = access['employee']
        
        # Get active period
        active_period = AssessmentPeriod.get_active_period()
        
        # My assessments
        my_assessments = SelfAssessment.objects.filter(employee=employee)
        my_assessments_count = my_assessments.count()
        
        # My average score
        my_avg_data = my_assessments.filter(
            overall_score__isnull=False
        ).aggregate(avg_score=Avg('overall_score'))
        my_average = float(my_avg_data['avg_score'] or 0)
        
        # My last assessment
        my_last = my_assessments.first()
        
        # Team data (if manager or admin)
        team_assessments_count = 0
        pending_reviews = 0
        team_average = 0
        
        if access['is_manager'] or access['is_admin']:
            if access['can_view_all']:
                # Admin sees all except own
                team_assessments = SelfAssessment.objects.exclude(employee=employee)
            else:
                # Manager sees direct reports only
                if access['accessible_employee_ids']:
                    team_ids = [id for id in access['accessible_employee_ids'] 
                               if id != employee.id]
                    team_assessments = SelfAssessment.objects.filter(employee_id__in=team_ids)
                else:
                    team_assessments = SelfAssessment.objects.none()
            
            team_assessments_count = team_assessments.count()
            pending_reviews = team_assessments.filter(status='SUBMITTED').count()
            
            # Team average score
            team_avg_data = team_assessments.filter(
                overall_score__isnull=False
            ).aggregate(avg_score=Avg('overall_score'))
            team_average = float(team_avg_data['avg_score'] or 0)
        
        stats = {
            'total_periods': AssessmentPeriod.objects.count(),
            'active_period': active_period,
            'my_assessments_count': my_assessments_count,
            'team_assessments_count': team_assessments_count,
            'pending_reviews': pending_reviews,
            'my_average_score': round(my_average, 2),
            'team_average_score': round(team_average, 2),
            'my_last_assessment': my_last,
            'is_admin': access['is_admin'],
            'is_manager': access['is_manager']
        }
        
        serializer = AssessmentStatsSerializer(stats)
        return Response(serializer.data)

