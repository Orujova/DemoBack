# api/competency_models.py

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class SkillGroup(models.Model):
    name = models.CharField(max_length=200, unique=True)
  
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['name']
        db_table = 'competency_skill_groups'
        
    def __str__(self):
        return self.name
    
    @property
    def skills_count(self):
        return self.skills.count()

class Skill(models.Model):
    group = models.ForeignKey(SkillGroup, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField(max_length=200)
   
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['name']
        unique_together = ['group', 'name']
        db_table = 'competency_skills'
        
    def __str__(self):
        return f"{self.group.name} - {self.name}"

class BehavioralCompetencyGroup(models.Model):
    name = models.CharField(max_length=200, unique=True)
   
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['name']
        db_table = 'competency_behavioral_groups'
        
    def __str__(self):
        return self.name
    
    @property
    def competencies_count(self):
        return self.competencies.count()

class BehavioralCompetency(models.Model):
    group = models.ForeignKey(BehavioralCompetencyGroup, on_delete=models.CASCADE, related_name='competencies')
    name = models.CharField(max_length=200)
 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['name']
        unique_together = ['group', 'name']
        db_table = 'competency_behavioral'
        
    def __str__(self):
        return f"{self.group.name} - {self.name}"

# YENİ: Leadership Competency modelleri
class LeadershipCompetencyMainGroup(models.Model):
    name = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['name']
        db_table = 'competency_leadership_main_groups'
        
    def __str__(self):
        return self.name
    
    @property
    def child_groups_count(self):
        return self.child_groups.count()
    
    @property
    def total_items_count(self):
        return LeadershipCompetencyItem.objects.filter(child_group__main_group=self).count()

class LeadershipCompetencyChildGroup(models.Model):
    main_group = models.ForeignKey(LeadershipCompetencyMainGroup, on_delete=models.CASCADE, related_name='child_groups')
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['name']
        unique_together = ['main_group', 'name']
        db_table = 'competency_leadership_child_groups'
        
    def __str__(self):
        return f"{self.main_group.name} - {self.name}"
    
    @property
    def items_count(self):
        return self.items.count()

class LeadershipCompetencyItem(models.Model):
    child_group = models.ForeignKey(LeadershipCompetencyChildGroup, on_delete=models.CASCADE, related_name='items')
    name = models.TextField()  # Description kimi uzun mətn ola bilər
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['id']
        db_table = 'competency_leadership_items'
        
    def __str__(self):
        return f"{self.child_group.main_group.name} - {self.child_group.name} - {self.name[:50]}"