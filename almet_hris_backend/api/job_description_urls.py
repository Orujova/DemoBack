# api/job_description_urls.py - COMPLETE: With nested item routes

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .job_description_views import (
    JobDescriptionViewSet,
    JobBusinessResourceViewSet,
    JobBusinessResourceItemViewSet,  # 🆕 New
    AccessMatrixViewSet,
    AccessMatrixItemViewSet,  # 🆕 New
    CompanyBenefitViewSet,
    CompanyBenefitItemViewSet,  # 🆕 New
    JobDescriptionStatsViewSet
)

router = DefaultRouter()

# ============================================
# MAIN JOB DESCRIPTION ROUTES
# ============================================
router.register(r'job-descriptions', JobDescriptionViewSet, basename='jobdescription')

# ============================================
# 🆕 BUSINESS RESOURCES - Parent & Child
# ============================================
router.register(r'business-resources', JobBusinessResourceViewSet, basename='jobbusinessresource')
router.register(r'business-resource-items', JobBusinessResourceItemViewSet, basename='jobbusinessresourceitem')

# ============================================
# 🆕 ACCESS MATRIX - Parent & Child
# ============================================
router.register(r'access-matrix', AccessMatrixViewSet, basename='accessmatrix')
router.register(r'access-matrix-items', AccessMatrixItemViewSet, basename='accessmatrixitem')

# ============================================
# 🆕 COMPANY BENEFITS - Parent & Child
# ============================================
router.register(r'company-benefits', CompanyBenefitViewSet, basename='companybenefit')
router.register(r'company-benefit-items', CompanyBenefitItemViewSet, basename='companybenefititem')

# ============================================
# STATISTICS
# ============================================
router.register(r'job-description-stats', JobDescriptionStatsViewSet, basename='jobdescriptionstats')

urlpatterns = [
    path('', include(router.urls)),
    
    # ============================================
    # JOB DESCRIPTION PDF DOWNLOADS
    # ============================================
    path('job-descriptions/<uuid:pk>/download-pdf/', 
         JobDescriptionViewSet.as_view({'get': 'download_pdf'}), 
         name='job-description-download-pdf'),
    
    path('job-descriptions/<uuid:pk>/download-signed/', 
         JobDescriptionViewSet.as_view({'get': 'download_signed'}), 
         name='job-description-download-signed'),
]

