# api/procedure_urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .procedure_views import (
    ProcedureFolderViewSet,
    CompanyProcedureViewSet,
    ProcedureCompanyViewSet,
    AllProcedureCompaniesViewSet,
    ProcedureStatisticsViewSet
)

# Create router
router = DefaultRouter()

# Register viewsets
router.register(r'procedure-companies', ProcedureCompanyViewSet, basename='procedure-company')
router.register(r'procedure-folders', ProcedureFolderViewSet, basename='procedure-folder')
router.register(r'procedures', CompanyProcedureViewSet, basename='procedure')
router.register(r'all-companies', AllProcedureCompaniesViewSet, basename='all-procedure-companies')
router.register(r'procedure-statistics', ProcedureStatisticsViewSet, basename='procedure-statistics')

# URL patterns
urlpatterns = [
    path('', include(router.urls)),
]