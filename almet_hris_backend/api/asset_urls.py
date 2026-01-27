# api/asset_urls.py - Complete URL Configuration

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .asset_views import (
    AssetCategoryViewSet,
    AssetBatchViewSet,
    AssetViewSet,
    EmployeeOffboardingViewSet,
    AssetTransferRequestViewSet
)

router = DefaultRouter()

# Asset management endpoints
router.register(r'categories', AssetCategoryViewSet, basename='assetcategory')
router.register(r'batches', AssetBatchViewSet, basename='assetbatch')
router.register(r'assets', AssetViewSet, basename='asset')
router.register(r'offboarding', EmployeeOffboardingViewSet, basename='offboarding')
router.register(r'transfers', AssetTransferRequestViewSet, basename='transfer')

urlpatterns = [
    path('', include(router.urls)),
]