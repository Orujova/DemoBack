# api/competency_urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .competency_views import (
    SkillGroupViewSet, SkillViewSet,
    BehavioralCompetencyGroupViewSet, BehavioralCompetencyViewSet,
    LeadershipCompetencyMainGroupViewSet, LeadershipCompetencyChildGroupViewSet,
    LeadershipCompetencyItemViewSet,
    CompetencyStatsView
)

router = DefaultRouter()

# Skill routes
router.register(r'skill-groups', SkillGroupViewSet)
router.register(r'skills', SkillViewSet)

# Behavioral Competency routes
router.register(r'behavioral-groups', BehavioralCompetencyGroupViewSet)
router.register(r'behavioral-competencies', BehavioralCompetencyViewSet)

# Leadership Competency routes
router.register(r'leadership-main-groups', LeadershipCompetencyMainGroupViewSet)
router.register(r'leadership-child-groups', LeadershipCompetencyChildGroupViewSet)
router.register(r'leadership-items', LeadershipCompetencyItemViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('stats/', CompetencyStatsView.as_view(), name='competency-stats'),
]