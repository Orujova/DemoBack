# api/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

# Competency Views Import
from .competency_views import (
    SkillGroupViewSet, SkillViewSet,
    BehavioralCompetencyGroupViewSet, BehavioralCompetencyViewSet,
    LeadershipCompetencyMainGroupViewSet, LeadershipCompetencyChildGroupViewSet, 
    LeadershipCompetencyItemViewSet,  
    CompetencyStatsView
)

# Job Description Views Import
from .job_description_views import (
    JobDescriptionViewSet,
    JobBusinessResourceViewSet,
    AccessMatrixViewSet,
    CompanyBenefitViewSet,
    JobDescriptionStatsViewSet
)

# Asset Management Views Import
from .asset_views import (
    AssetCategoryViewSet,
    AssetViewSet,
)

from .competency_assessment_views import (
    CoreCompetencyScaleViewSet, BehavioralScaleViewSet, LetterGradeMappingViewSet,
    PositionCoreAssessmentViewSet, PositionBehavioralAssessmentViewSet,
    PositionLeadershipAssessmentViewSet,  
    EmployeeCoreAssessmentViewSet, EmployeeBehavioralAssessmentViewSet,
    EmployeeLeadershipAssessmentViewSet,  
    AssessmentDashboardViewSet
)

from .role_views import RoleViewSet, PermissionViewSet, EmployeeRoleViewSet

from api.resignation_exit_views import (
    ResignationRequestViewSet,
    ExitInterviewQuestionViewSet,
    ExitInterviewViewSet,
    ContractRenewalRequestViewSet,
    ProbationReviewQuestionViewSet,
    ProbationReviewViewSet
)

from .timeoff_views import (
    TimeOffBalanceViewSet,
    TimeOffRequestViewSet,
    TimeOffSettingsViewSet,
    TimeOffActivityViewSet,
    TimeOffDashboardViewSet
)

from .self_assessment_views import (
    AssessmentPeriodViewSet, SelfAssessmentViewSet,
 AssessmentStatsView
)

router = DefaultRouter()



# Router-ə əlavə et
router.register(r'self-assessments-periods', AssessmentPeriodViewSet, basename='assessment-period')
router.register(r'self-assessments', SelfAssessmentViewSet, basename='self-assessment')

# urlpatterns-ə əlavə et

router.register(r'timeoff/balances', TimeOffBalanceViewSet, basename='timeoff-balance')
router.register(r'timeoff/requests', TimeOffRequestViewSet, basename='timeoff-request')
router.register(r'timeoff/settings', TimeOffSettingsViewSet, basename='timeoff-settings')
router.register(r'timeoff/activity', TimeOffActivityViewSet, basename='timeoff-activity')
router.register(r'timeoff/dashboard', TimeOffDashboardViewSet, basename='timeoff-dashboard')

# ==================== ROLE & PERMISSION MANAGEMENT ====================
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'permissions', PermissionViewSet, basename='permission')
router.register(r'employee-roles', EmployeeRoleViewSet, basename='employee-role')


# ==================== BUSINESS STRUCTURE ====================
router.register(r'business-functions', views.BusinessFunctionViewSet, basename='businessfunction')
router.register(r'departments', views.DepartmentViewSet, basename='department')
router.register(r'job-titles', views.JobTitleViewSet, basename='job-title')
router.register(r'units', views.UnitViewSet, basename='unit')
router.register(r'job-functions', views.JobFunctionViewSet, basename='jobfunction')
router.register(r'position-groups', views.PositionGroupViewSet, basename='positiongroup')


# ==================== EMPLOYEE MANAGEMENT ====================
router.register(r'employees', views.EmployeeViewSet, basename='employee')
router.register(r'employee-tags', views.EmployeeTagViewSet, basename='employeetag')
router.register(r'employee-statuses', views.EmployeeStatusViewSet, basename='employeestatus')
router.register(r'profile-images', views.ProfileImageViewSet, basename='profileimage')
router.register(r'contract-configs', views.ContractTypeConfigViewSet, basename='contractconfig')
router.register(r'vacant-positions', views.VacantPositionViewSet, basename='vacantposition')
router.register(r'org-chart', views.OrgChartViewSet, basename='orgchart')
router.register(r'bulk-upload', views.BulkEmployeeUploadViewSet, basename='bulkupload')


# ==================== COMPETENCY MANAGEMENT ====================
# Skills
router.register(r'competency/skill-groups', SkillGroupViewSet, basename='competency-skillgroup')
router.register(r'competency/skills', SkillViewSet, basename='competency-skill')

# Behavioral Competencies
router.register(r'competency/behavioral-groups', BehavioralCompetencyGroupViewSet, basename='competency-behavioralgroup')
router.register(r'competency/behavioral-competencies', BehavioralCompetencyViewSet, basename='competency-behavioral')

# Leadership Competencies
router.register(r'competency/leadership-main-groups', LeadershipCompetencyMainGroupViewSet, basename='competency-leadership-main')
router.register(r'competency/leadership-child-groups', LeadershipCompetencyChildGroupViewSet, basename='competency-leadership-child')
router.register(r'competency/leadership-items', LeadershipCompetencyItemViewSet, basename='competency-leadership-items')


# ========================== JOB DESCRIPTIONS ========================================
router.register(r'job-descriptions', JobDescriptionViewSet, basename='jobdescription')
router.register(r'job-description/business-resources', JobBusinessResourceViewSet, basename='jobbusinessresource')
router.register(r'job-description/access-matrix', AccessMatrixViewSet, basename='accessmatrix')
router.register(r'job-description/company-benefits', CompanyBenefitViewSet, basename='companybenefit')
router.register(r'job-description/stats', JobDescriptionStatsViewSet, basename='jobdescriptionstats')




# ==================== COMPETENCY ASSESSMENTS ====================
# Scale Management
router.register(r'assessments/core-scales', CoreCompetencyScaleViewSet, basename='assessment-core-scales')
router.register(r'assessments/behavioral-scales', BehavioralScaleViewSet, basename='assessment-behavioral-scales')
router.register(r'assessments/letter-grades', LetterGradeMappingViewSet, basename='assessment-letter-grades')

# Position Assessment Templates
router.register(r'assessments/position-core', PositionCoreAssessmentViewSet, basename='assessment-position-core')
router.register(r'assessments/position-behavioral', PositionBehavioralAssessmentViewSet, basename='assessment-position-behavioral')
router.register(r'assessments/position-leadership', PositionLeadershipAssessmentViewSet, basename='assessment-position-leadership')  # NEW

# Employee Assessments
router.register(r'assessments/employee-core', EmployeeCoreAssessmentViewSet, basename='assessment-employee-core')
router.register(r'assessments/employee-behavioral', EmployeeBehavioralAssessmentViewSet, basename='assessment-employee-behavioral')
router.register(r'assessments/employee-leadership', EmployeeLeadershipAssessmentViewSet, basename='assessment-employee-leadership')  # NEW

# Assessment Dashboard
router.register(r'assessments/dashboard', AssessmentDashboardViewSet, basename='assessment-dashboard')

# Register viewsets
router.register(r'resignations', ResignationRequestViewSet, basename='resignation')
router.register(r'exit-interview-questions', ExitInterviewQuestionViewSet, basename='exit-interview-question')
router.register(r'exit-interviews', ExitInterviewViewSet, basename='exit-interview')
router.register(r'contract-renewals', ContractRenewalRequestViewSet, basename='contract-renewal')
router.register(r'probation-review-questions', ProbationReviewQuestionViewSet, basename='probation-review-question')
router.register(r'probation-reviews', ProbationReviewViewSet, basename='probation-review')


# ==================== URL PATTERNS ====================
urlpatterns = [
    
    path('auth/microsoft/', views.authenticate_microsoft, name='auth_microsoft'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', views.user_info, name='user_info'),
    
    
    path('competency/stats/', CompetencyStatsView.as_view(), name='competency-stats'),

    path('self-assessments-stats/', AssessmentStatsView.as_view(), name='assessment-stats'),

    path('assets/assets/<uuid:pk>/activities/', 
         AssetViewSet.as_view({'get': 'activities'}), 
         name='asset-activities'),
    
    path('assets/assets/export/', 
         AssetViewSet.as_view({'post': 'export_assets'}), 
         name='asset-export'),
    
    path('handovers/', include('api.handover_urls')),
    path('assets/', include('api.asset_urls')),
    path('trainings/', include('api.training_urls')),
    path('vacation/', include('api.vacation_urls')),
    path('business-trips/', include('api.business_trip_urls')),
    path('notifications/', include('api.notification_urls')),
    path('news/', include('api.news_urls')),
    path('performance/', include('api.performance_urls')),
    path('policies/', include('api.policy_urls')),
    path('procedures/', include('api.procedure_urls')), 
    path('', include('api.celebration_urls')),
    path('', include('api.celebration_test_urls')),
    
    
    path('', include(router.urls)),
]