# api/celebration_test_urls.py
"""
OPTIONAL: URL patterns for celebration notification testing
Add to main urls.py:
    path('api/celebrations/test/', include('api.celebration_test_urls')),
"""

from django.urls import path
from . import celebration_test_views

urlpatterns = [
    path('birthday/', celebration_test_views.test_birthday_notification, name='test-birthday-notification'),
    path('anniversary/', celebration_test_views.test_anniversary_notification, name='test-anniversary-notification'),
    path('position-change/', celebration_test_views.test_position_change_notification, name='test-position-change'),
    path('daily-check/', celebration_test_views.test_daily_celebration_check, name='test-daily-check'),
    path('welcome/', celebration_test_views.test_welcome_email, name='test-welcome-email'),
]