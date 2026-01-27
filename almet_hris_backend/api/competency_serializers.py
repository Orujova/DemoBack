# api/competency_serializers.py

from rest_framework import serializers
from django.contrib.auth.models import User
from .competency_models import (
    SkillGroup, Skill, 
    BehavioralCompetencyGroup, BehavioralCompetency,
    LeadershipCompetencyMainGroup, LeadershipCompetencyChildGroup, LeadershipCompetencyItem
)

# Skill serializers
class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class SkillCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['group', 'name']

class SkillGroupSerializer(serializers.ModelSerializer):
    skills = SkillSerializer(many=True, read_only=True)
    skills_count = serializers.ReadOnlyField()
    
    class Meta:
        model = SkillGroup
        fields = ['id', 'name', 'skills', 'skills_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class SkillGroupListSerializer(serializers.ModelSerializer):
    skills_count = serializers.ReadOnlyField()
    
    class Meta:
        model = SkillGroup
        fields = ['id', 'name', 'skills_count', 'created_at', 'updated_at']

# Behavioral Competency serializers
class BehavioralCompetencySerializer(serializers.ModelSerializer):
    class Meta:
        model = BehavioralCompetency
        fields = ['id', 'name', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class BehavioralCompetencyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BehavioralCompetency
        fields = ['group', 'name']

class BehavioralCompetencyGroupSerializer(serializers.ModelSerializer):
    competencies = BehavioralCompetencySerializer(many=True, read_only=True)
    competencies_count = serializers.ReadOnlyField()
    
    class Meta:
        model = BehavioralCompetencyGroup
        fields = ['id', 'name', 'competencies', 'competencies_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class BehavioralCompetencyGroupListSerializer(serializers.ModelSerializer):
    competencies_count = serializers.ReadOnlyField()
    
    class Meta:
        model = BehavioralCompetencyGroup
        fields = ['id', 'name', 'competencies_count', 'created_at', 'updated_at']

# Leadership Competency serializers
class LeadershipCompetencyItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadershipCompetencyItem
        fields = ['id', 'name', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class LeadershipCompetencyItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadershipCompetencyItem
        fields = ['child_group', 'name']

class LeadershipCompetencyChildGroupSerializer(serializers.ModelSerializer):
    items = LeadershipCompetencyItemSerializer(many=True, read_only=True)
    items_count = serializers.ReadOnlyField()
    main_group_name = serializers.CharField(source='main_group.name', read_only=True)
    
    class Meta:
        model = LeadershipCompetencyChildGroup
        fields = ['id', 'main_group', 'main_group_name', 'name', 'items', 'items_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class LeadershipCompetencyChildGroupListSerializer(serializers.ModelSerializer):
    items_count = serializers.ReadOnlyField()
    main_group_name = serializers.CharField(source='main_group.name', read_only=True)
    
    class Meta:
        model = LeadershipCompetencyChildGroup
        fields = ['id', 'main_group', 'main_group_name', 'name', 'items_count', 'created_at', 'updated_at']

class LeadershipCompetencyChildGroupCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadershipCompetencyChildGroup
        fields = ['main_group', 'name']

class LeadershipCompetencyMainGroupSerializer(serializers.ModelSerializer):
    child_groups = LeadershipCompetencyChildGroupListSerializer(many=True, read_only=True)
    child_groups_count = serializers.ReadOnlyField()
    total_items_count = serializers.ReadOnlyField()
    
    class Meta:
        model = LeadershipCompetencyMainGroup
        fields = ['id', 'name', 'child_groups', 'child_groups_count', 'total_items_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class LeadershipCompetencyMainGroupListSerializer(serializers.ModelSerializer):
    child_groups_count = serializers.ReadOnlyField()
    total_items_count = serializers.ReadOnlyField()
    
    class Meta:
        model = LeadershipCompetencyMainGroup
        fields = ['id', 'name', 'child_groups_count', 'total_items_count', 'created_at', 'updated_at']

# Stats serializer
class CompetencyStatsSerializer(serializers.Serializer):
    total_skill_groups = serializers.IntegerField()
    total_skills = serializers.IntegerField()
    total_behavioral_groups = serializers.IntegerField()
    total_behavioral_competencies = serializers.IntegerField()
    total_leadership_main_groups = serializers.IntegerField()
    total_leadership_child_groups = serializers.IntegerField()
    total_leadership_items = serializers.IntegerField()