# api/performance_urls.py - UPDATED with new endpoints

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .performance_views import *

router = DefaultRouter()

router.register(r'performance/years', PerformanceYearViewSet, basename='performance-year')
router.register(r'performance/weight-configs', PerformanceWeightConfigViewSet, basename='performance-weight')
router.register(r'performance/goal-limits', GoalLimitConfigViewSet, basename='performance-goal-limit')
router.register(r'performance/department-objectives', DepartmentObjectiveViewSet, basename='performance-dept-objective')
router.register(r'performance/evaluation-scales', EvaluationScaleViewSet, basename='performance-eval-scale')
router.register(r'performance/evaluation-targets', EvaluationTargetConfigViewSet, basename='performance-eval-target')
router.register(r'performance/objective-statuses', ObjectiveStatusViewSet, basename='performance-obj-status')
router.register(r'performance/performances', EmployeePerformanceViewSet, basename='employee-performance')
router.register(r'performance/dashboard', PerformanceDashboardViewSet, basename='performance-dashboard')
router.register(r'performance/notification-templates', PerformanceNotificationTemplateViewSet, basename='performance-notification')

urlpatterns = [
    path('', include(router.urls)),
]
