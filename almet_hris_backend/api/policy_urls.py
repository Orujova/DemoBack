# api/policy_urls.py - UPDATED URL Configuration

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .policy_views import (
    PolicyFolderViewSet,
    CompanyPolicyViewSet,
    PolicyCompanyViewSet,
    AllCompaniesViewSet,
    PolicyStatisticsViewSet
)

# Create router
router = DefaultRouter()

# Register viewsets
router.register(r'policy-companies', PolicyCompanyViewSet, basename='policy-company')
router.register(r'policy-folders', PolicyFolderViewSet, basename='policy-folder')
router.register(r'policies', CompanyPolicyViewSet, basename='policy')
router.register(r'all-companies', AllCompaniesViewSet, basename='all-companies')
router.register(r'policy-statistics', PolicyStatisticsViewSet, basename='policy-statistics')

# URL patterns
urlpatterns = [
    path('', include(router.urls)),
]