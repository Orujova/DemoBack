from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'systems', views.GradingSystemViewSet, basename='gradingsystem')
router.register(r'salary-grades', views.SalaryGradeViewSet, basename='salarygrade')
router.register(r'scenarios', views.SalaryScenarioViewSet, basename='salaryscenario')


urlpatterns = [
    path('', include(router.urls)),
]