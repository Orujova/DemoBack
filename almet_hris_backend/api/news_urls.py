# api/news_urls.py - COMPLETE VERSION
"""
Company News System URL Configuration
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import news_views

router = DefaultRouter()

# Register ViewSets
router.register(r'categories', news_views.NewsCategoryViewSet, basename='news-category')
router.register(r'target-groups', news_views.TargetGroupViewSet, basename='target-group')
router.register(r'', news_views.CompanyNewsViewSet, basename='news')

urlpatterns = [
    # Permissions endpoint
    path('permissions/', news_views.NewsPermissionsView.as_view(), name='news-permissions'),
    
    # ViewSet routes
    path('', include(router.urls)),
]