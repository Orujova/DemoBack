# api/training_urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .training_views import (

    TrainingViewSet,
    TrainingAssignmentViewSet,
    TrainingMaterialViewSet
)

router = DefaultRouter()

router.register(r'trainings', TrainingViewSet, basename='training')
router.register(r'assignments', TrainingAssignmentViewSet, basename='training-assignment')
router.register(r'materials', TrainingMaterialViewSet, basename='training-material')

urlpatterns = [
    path('', include(router.urls)),
]