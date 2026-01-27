# api/notification_urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import notification_views

router = DefaultRouter()


urlpatterns = [

  

    path('outlook/mark-read/', notification_views.mark_email_read, name='notification-mark-read'),
    path('outlook/mark-unread/', notification_views.mark_email_unread, name='notification-mark-unread'),
    path('outlook/mark-all-read/', notification_views.mark_all_emails_read, name='notification-mark-all-read'),
    path('outlook/emails/', notification_views.get_outlook_emails, name='notification-outlook-emails'),
     path('outlook/email/<str:message_id>/', notification_views.get_email_detail, name='notification-email-detail'),
    path('', include(router.urls)),
]