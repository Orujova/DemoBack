# api/vacation_urls.py - Fixed URL ordering

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import vacation_views as views

# Router for ViewSets
router = DefaultRouter()
router.register(r'types', views.VacationTypeViewSet, basename='vacation-types')

urlpatterns = [
    # ============= DASHBOARD =============
    path('dashboard/', views.vacation_dashboard, name='vacation-dashboard'),
    
    # ============= VACATION TYPES (specific routes BEFORE router) =============
    # ✅ IMPORTANT: Put specific 'types/' endpoints BEFORE router.urls
    path('types/filtered/', views.get_vacation_types_filtered, name='vacation-types-filtered'),
    
    # ============= SETTINGS ENDPOINTS =============
    
    # Production Calendar Settings
    path('production-calendar/', views.get_production_calendar, name='vacation-get-production-calendar'),
    path('production-calendar/set/', views.set_production_calendar, name='vacation-set-production-calendar'),
    path('production-calendar/update/', views.update_production_calendar, name='vacation-update-production-calendar'),
    
    # UK Additional Approver Settings
    path('uk-additional-approver/', views.get_uk_additional_approver, name='get-uk-additional-approver'),
    path('uk-additional-approver/set/', views.set_uk_additional_approver, name='set-uk-additional-approver'),
    
    # General Vacation Settings
    path('settings/', views.get_general_vacation_settings, name='vacation-get-general-settings'),
    path('settings/set/', views.set_general_vacation_settings, name='vacation-set-general-settings'),
    path('settings/update/', views.update_general_vacation_settings, name='vacation-update-general-settings'),
    
    # HR Representative Settings
    path('hr-representatives/', views.get_hr_representatives, name='vacation-get-hr-representatives'),
    path('hr-representatives/set-default/', views.set_default_hr_representative, name='vacation-set-default-hr'),
    path('hr-representatives/update-default/', views.update_default_hr_representative, name='vacation-update-default-hr'),
    
    # ============= REQUEST MANAGEMENT =============
    path('requests/immediate/', views.create_immediate_request, name='vacation-create-immediate-request'),
    path('requests/<int:pk>/', views.get_vacation_request_detail, name='vacation-request-detail'),
    
    # Vacation Request Attachments
    path('vacation-requests/<str:request_id>/attachments/', views.list_vacation_request_attachments, name='vacation-request-attachments-list'),
    path('vacation-requests/<str:request_id>/attachments/bulk-upload/', views.bulk_upload_vacation_attachments, name='vacation-request-attachments-bulk-upload'),
    path('vacation-attachments/<int:attachment_id>/', views.get_vacation_attachment_details, name='vacation-attachment-detail'),
    path('vacation-attachments/<int:attachment_id>/delete/', views.delete_vacation_attachment, name='vacation-attachment-delete'),
    
    # ============= SCHEDULING =============
    path('schedules/create/', views.create_schedule, name='vacation-create-schedule'),
    path('schedules/tabs/', views.my_schedule_tabs, name='vacation-my-schedule-tabs'),
    path('schedules/<int:pk>/register/', views.register_schedule, name='vacation-register-schedule'),
    path('schedules/<int:pk>/edit/', views.edit_schedule, name='vacation-edit-schedule'),
    path('schedules/<int:pk>/delete/', views.delete_schedule, name='vacation-delete-schedule'),
    path('vacation-schedules/<int:pk>/detail/', views.get_vacation_schedule_detail, name='vacation-schedule-detail'),
    path('schedules/bulk-create/', views.bulk_create_schedules, name='bulk-create-schedules'),
    # ============= APPROVAL =============
    path('approval/pending/', views.approval_pending_requests, name='vacation-approval-pending'),
    path('approval/history/', views.approval_history, name='vacation-approval-history'),
    path('requests/<int:pk>/approve-reject/', views.approve_reject_request, name='vacation-approve-reject-request'),
    # Schedule approval
path('schedules/<int:pk>/approve/', views.approve_schedule, name='vacation-approve-schedule'),
    # ============= MY RECORDS =============
    path('my-all/', views.my_all_requests_schedules, name='vacation-my-all-requests-schedules'),
    path('my-all/export/', views.export_my_vacations, name='vacation-export-my-vacations'),
    path('all-vacation-records/', views.all_vacation_records, name='all-vacation-records'),
    path('all-records/export/', views.export_all_vacation_records, name='vacation-export-all-records'),
    
    # ============= BALANCE MANAGEMENT =============
    path('balances/', views.get_all_balances, name='get_all_balances'),
    path('balances/export/', views.export_all_balances, name='export_all_balances'),
    path('balances/update/', views.update_employee_balance, name='update_employee_balance'),
    path('balances/reset/', views.reset_balances, name='reset_balances'),
    path('balances/bulk-upload/', views.bulk_upload_balances, name='vacation-bulk-upload-balances'),
    path('balances/template/', views.download_balance_template, name='vacation-download-balance-template'),
    
    # ============= CALENDAR =============
    path('calendar/', views.get_calendar_events, name='calendar-events'),
    
    # ============= UTILITIES =============
    path('calculate-working-days/', views.calculate_working_days, name='vacation-calculate-working-days'),
    
    # ============= ROUTER URLs (MUST BE LAST) =============
    # ✅ Router URLs go at the END to avoid catching specific routes
    path('', include(router.urls)),
]