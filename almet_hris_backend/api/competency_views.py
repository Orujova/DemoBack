# api/competency_views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.db.models import Q, Count
from django.db import transaction

from .competency_models import (
    SkillGroup, Skill, 
    BehavioralCompetencyGroup, BehavioralCompetency,
    LeadershipCompetencyMainGroup, LeadershipCompetencyChildGroup, LeadershipCompetencyItem
)
from .competency_serializers import (
    SkillGroupSerializer, SkillGroupListSerializer, SkillSerializer, SkillCreateSerializer,
    BehavioralCompetencyGroupSerializer, BehavioralCompetencyGroupListSerializer,
    BehavioralCompetencySerializer, BehavioralCompetencyCreateSerializer,
    LeadershipCompetencyMainGroupSerializer, LeadershipCompetencyMainGroupListSerializer,
    LeadershipCompetencyChildGroupSerializer, LeadershipCompetencyChildGroupListSerializer,
    LeadershipCompetencyChildGroupCreateSerializer,
    LeadershipCompetencyItemSerializer, LeadershipCompetencyItemCreateSerializer,
    CompetencyStatsSerializer
)

# Skill ViewSets
class SkillGroupViewSet(viewsets.ModelViewSet):
    queryset = SkillGroup.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return SkillGroupListSerializer
        return SkillGroupSerializer
    
    def get_queryset(self):
        queryset = SkillGroup.objects.all()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(name__icontains=search))
        return queryset.order_by('name')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def skills(self, request, pk=None):
        """Qrup üçün skills siyahısı"""
        group = self.get_object()
        skills = group.skills.all()
        
        search = request.query_params.get('search', None)
        if search:
            skills = skills.filter(name__icontains=search)
            
        serializer = SkillSerializer(skills, many=True)
        return Response(serializer.data)

class SkillViewSet(viewsets.ModelViewSet):
    queryset = Skill.objects.select_related('group').all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return SkillCreateSerializer
        return SkillSerializer
    
    def get_queryset(self):
        queryset = Skill.objects.select_related('group').all()
        
        group_id = self.request.query_params.get('group', None)
        if group_id:
            queryset = queryset.filter(group_id=group_id)
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(group__name__icontains=search)
            )
        
        return queryset.order_by('group__name', 'name')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

# Behavioral Competency ViewSets
class BehavioralCompetencyGroupViewSet(viewsets.ModelViewSet):
    queryset = BehavioralCompetencyGroup.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return BehavioralCompetencyGroupListSerializer
        return BehavioralCompetencyGroupSerializer
    
    def get_queryset(self):
        queryset = BehavioralCompetencyGroup.objects.all()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(name__icontains=search))
        return queryset.order_by('name')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def competencies(self, request, pk=None):
        """Qrup üçün competencies siyahısı"""
        group = self.get_object()
        competencies = group.competencies.all()
        
        search = request.query_params.get('search', None)
        if search:
            competencies = competencies.filter(name__icontains=search)
            
        serializer = BehavioralCompetencySerializer(competencies, many=True)
        return Response(serializer.data)

class BehavioralCompetencyViewSet(viewsets.ModelViewSet):
    queryset = BehavioralCompetency.objects.select_related('group').all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return BehavioralCompetencyCreateSerializer
        return BehavioralCompetencySerializer
    
    def get_queryset(self):
        queryset = BehavioralCompetency.objects.select_related('group').all()
        
        group_id = self.request.query_params.get('group', None)
        if group_id:
            queryset = queryset.filter(group_id=group_id)
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(group__name__icontains=search)
            )
        
        return queryset.order_by('group__name', 'name')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

# Leadership Competency ViewSets
class LeadershipCompetencyMainGroupViewSet(viewsets.ModelViewSet):
    queryset = LeadershipCompetencyMainGroup.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return LeadershipCompetencyMainGroupListSerializer
        return LeadershipCompetencyMainGroupSerializer
    
    def get_queryset(self):
        queryset = LeadershipCompetencyMainGroup.objects.all()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(name__icontains=search))
        return queryset.order_by('name')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def child_groups(self, request, pk=None):
        """Main group üçün child groups siyahısı"""
        main_group = self.get_object()
        child_groups = main_group.child_groups.all()
        
        search = request.query_params.get('search', None)
        if search:
            child_groups = child_groups.filter(name__icontains=search)
            
        serializer = LeadershipCompetencyChildGroupListSerializer(child_groups, many=True)
        return Response(serializer.data)

class LeadershipCompetencyChildGroupViewSet(viewsets.ModelViewSet):
    queryset = LeadershipCompetencyChildGroup.objects.select_related('main_group').all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return LeadershipCompetencyChildGroupCreateSerializer
        elif self.action == 'list':
            return LeadershipCompetencyChildGroupListSerializer
        return LeadershipCompetencyChildGroupSerializer
    
    def get_queryset(self):
        queryset = LeadershipCompetencyChildGroup.objects.select_related('main_group').all()
        
        main_group_id = self.request.query_params.get('main_group', None)
        if main_group_id:
            queryset = queryset.filter(main_group_id=main_group_id)
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(main_group__name__icontains=search)
            )
        
        return queryset.order_by('main_group__name', 'name')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """Child group üçün items siyahısı"""
        child_group = self.get_object()
        items = child_group.items.all()
        
        search = request.query_params.get('search', None)
        if search:
            items = items.filter(name__icontains=search)
            
        serializer = LeadershipCompetencyItemSerializer(items, many=True)
        return Response(serializer.data)

class LeadershipCompetencyItemViewSet(viewsets.ModelViewSet):
    queryset = LeadershipCompetencyItem.objects.select_related('child_group__main_group').all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return LeadershipCompetencyItemCreateSerializer
        return LeadershipCompetencyItemSerializer
    
    def get_queryset(self):
        queryset = LeadershipCompetencyItem.objects.select_related('child_group__main_group').all()
        
        child_group_id = self.request.query_params.get('child_group', None)
        if child_group_id:
            queryset = queryset.filter(child_group_id=child_group_id)
        
        main_group_id = self.request.query_params.get('main_group', None)
        if main_group_id:
            queryset = queryset.filter(child_group__main_group_id=main_group_id)
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(name__icontains=search))
        
        return queryset.order_by('id')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

# Stats View
class CompetencyStatsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        stats = {
            'total_skill_groups': SkillGroup.objects.count(),
            'total_skills': Skill.objects.count(),
            'total_behavioral_groups': BehavioralCompetencyGroup.objects.count(),
            'total_behavioral_competencies': BehavioralCompetency.objects.count(),
            'total_leadership_main_groups': LeadershipCompetencyMainGroup.objects.count(),
            'total_leadership_child_groups': LeadershipCompetencyChildGroup.objects.count(),
            'total_leadership_items': LeadershipCompetencyItem.objects.count(),
        }
        
        serializer = CompetencyStatsSerializer(stats)
        return Response(serializer.data)