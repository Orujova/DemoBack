from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .celebration_views import CelebrationViewSet

router = DefaultRouter()
router.register(r'celebrations', CelebrationViewSet, basename='celebration')

urlpatterns = [
    path('', include(router.urls)),
]

# Available endpoints:
# GET    /api/celebrations/                       - List all manual celebrations
# POST   /api/celebrations/                       - Create new celebration
# GET    /api/celebrations/{id}/                  - Get specific celebration
# PUT    /api/celebrations/{id}/                  - Update celebration
# PATCH  /api/celebrations/{id}/                  - Partial update
# DELETE /api/celebrations/{id}/                  - Delete celebration
# GET    /api/celebrations/all_celebrations/      - Get all (manual + auto)
# POST   /api/celebrations/{id}/add_wish/         - Add wish to manual celebration
# POST   /api/celebrations/add_auto_wish/         - Add wish to auto celebration
# DELETE /api/celebrations/{id}/remove_image/     - Remove image
# GET    /api/celebrations/statistics/            - Get statistics