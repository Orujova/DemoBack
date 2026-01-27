# api/handover_urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .handover_views import (
    HandoverTypeViewSet,
    HandoverRequestViewSet,
    HandoverTaskViewSet,
    HandoverAttachmentViewSet
)

# Create router
router = DefaultRouter()

# Register viewsets
router.register(r'types', HandoverTypeViewSet, basename='handover-type')
router.register(r'requests', HandoverRequestViewSet, basename='handover-request')
router.register(r'tasks', HandoverTaskViewSet, basename='handover-task')
router.register(r'attachments', HandoverAttachmentViewSet, basename='handover-attachment')

# URL patterns
urlpatterns = [
    path('', include(router.urls)),
]
