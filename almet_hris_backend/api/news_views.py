# api/news_views.py - UPDATED WITH ADMIN-ONLY RESTRICTIONS

import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q, Sum
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .news_models import NewsCategory, CompanyNews, TargetGroup
from .news_serializers import (
    NewsCategorySerializer,
    NewsListSerializer,
    NewsDetailSerializer,
    NewsCreateUpdateSerializer,
    TargetGroupListSerializer,
    TargetGroupDetailSerializer,
    TargetGroupCreateUpdateSerializer,
)
from .news_permissions import (
    IsAdminOnly,
    CanViewNews,
    is_admin_user,
)
from .news_notifications import news_notification_manager
from .token_helpers import extract_graph_token_from_request

logger = logging.getLogger(__name__)


# ==================== NEWS CATEGORY VIEWSET ====================

class NewsCategoryViewSet(viewsets.ModelViewSet):
    """
    ✅ NEWS CATEGORY - ADMIN ONLY
    Only Admin can create/update/delete categories
    """
    
    queryset = NewsCategory.objects.filter(is_deleted=False)
    serializer_class = NewsCategorySerializer
    permission_classes = [IsAdminOnly]  # ✅ Admin only
    
    def get_queryset(self):
        queryset = NewsCategory.objects.filter(is_deleted=False)
        
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        return queryset.order_by('name')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ==================== TARGET GROUP VIEWSET ====================

class TargetGroupViewSet(viewsets.ModelViewSet):
    """
    ✅ TARGET GROUPS - ADMIN ONLY
    Only Admin can manage target groups
    """
    
    queryset = TargetGroup.objects.filter(is_deleted=False)
    permission_classes = [IsAdminOnly]  # ✅ Admin only
    
    def get_serializer_class(self):
        if self.action == 'list':
            return TargetGroupListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return TargetGroupCreateUpdateSerializer
        return TargetGroupDetailSerializer
    
    def get_queryset(self):
        queryset = TargetGroup.objects.filter(is_deleted=False)
        
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        return queryset.prefetch_related('members')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def add_members(self, request, pk=None):
        """Add members to target group"""
        group = self.get_object()
        
        employee_ids = request.data.get('employee_ids', [])
        
        if not employee_ids:
            return Response(
                {'error': 'employee_ids is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from .models import Employee
        employees = Employee.objects.filter(id__in=employee_ids, is_deleted=False)
        
        if not employees.exists():
            return Response(
                {'error': 'No valid employees found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        added_count = 0
        for employee in employees:
            if not group.members.filter(id=employee.id).exists():
                group.members.add(employee)
                added_count += 1
        
        return Response({
            'message': f'{added_count} member(s) added successfully',
            'group_id': str(group.id),
            'total_members': group.member_count
        })
    
    @action(detail=True, methods=['post'])
    def remove_members(self, request, pk=None):
        """Remove members from target group"""
        group = self.get_object()
        
        employee_ids = request.data.get('employee_ids', [])
        
        if not employee_ids:
            return Response(
                {'error': 'employee_ids is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from .models import Employee
        employees = Employee.objects.filter(id__in=employee_ids)
        
        removed_count = 0
        for employee in employees:
            if group.members.filter(id=employee.id).exists():
                group.members.remove(employee)
                removed_count += 1
        
        return Response({
            'message': f'{removed_count} member(s) removed successfully',
            'group_id': str(group.id),
            'total_members': group.member_count
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get target group statistics"""
        total_groups = TargetGroup.objects.filter(is_deleted=False).count()
        active_groups = TargetGroup.objects.filter(is_deleted=False, is_active=True).count()
        
        from .models import Employee
        all_member_ids = set()
        for group in TargetGroup.objects.filter(is_deleted=False):
            all_member_ids.update(group.members.values_list('id', flat=True))
        
        return Response({
            'total_groups': total_groups,
            'active_groups': active_groups,
            'inactive_groups': total_groups - active_groups,
            'total_unique_members': len(all_member_ids)
        })


# ==================== COMPANY NEWS VIEWSET ====================

class CompanyNewsViewSet(viewsets.ModelViewSet):
    """
    ✅ COMPANY NEWS with simplified permissions
    - Create/Update/Delete: Admin only
    - View: Everyone can see published news in their target groups
    """
    
    queryset = CompanyNews.objects.filter(is_deleted=False)
    
    def get_serializer_class(self):
        if self.action in ['toggle_pin', 'toggle_publish']:
            return None
        
        if self.action == 'list':
            return NewsListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return NewsCreateUpdateSerializer
        return NewsDetailSerializer
    
    def get_permissions(self):
        """✅ Dynamic permissions"""
        if self.action in ['list', 'retrieve']:
            return [CanViewNews()]
        elif self.action in ['create', 'update', 'partial_update', 'destroy', 
                           'toggle_pin', 'toggle_publish', 'statistics']:
            return [IsAdminOnly()]  # ✅ Admin only
        
        return [IsAuthenticated()]
    
    def get_queryset(self):
        queryset = CompanyNews.objects.filter(is_deleted=False)
        user = self.request.user
        
        # ✅ Admin sees all news
        if is_admin_user(user):
            pass  # Admin sees everything
        else:
            # ✅ Regular users see only published news in their target groups
            try:
                from .models import Employee
                employee = Employee.objects.get(user=user, is_deleted=False)
                
                # Get target groups where this employee is a member
                employee_target_groups = TargetGroup.objects.filter(
                    members=employee,
                    is_active=True,
                    is_deleted=False
                )
                
                # Filter: published news in user's target groups OR news without target groups
                queryset = queryset.filter(
                    Q(is_published=True) &
                    (
                        Q(target_groups__in=employee_target_groups) |
                        Q(target_groups__isnull=True)
                    )
                ).distinct()
                
            except Employee.DoesNotExist:
                # No employee profile = only see published news without target groups
                queryset = queryset.filter(
                    is_published=True,
                    target_groups__isnull=True
                )
        
        # Filter by category
        category_id = self.request.query_params.get('category', None)
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Search
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(excerpt__icontains=search) |
                Q(content__icontains=search) |
                Q(tags__icontains=search)
            )
        
        return queryset.select_related('author', 'category').prefetch_related('target_groups')

    def retrieve(self, request, *args, **kwargs):
        """Get news detail with access check"""
        instance = self.get_object()
        
        user = request.user
        
        # ✅ Admin can view all
        if is_admin_user(user):
            pass  # Allow
        else:
            # ✅ Regular users: check if they have access
            if not instance.is_published:
                return Response(
                    {'error': 'News not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            try:
                from .models import Employee
                employee = Employee.objects.get(user=user, is_deleted=False)
                
                news_target_groups = instance.target_groups.filter(is_active=True, is_deleted=False)
                
                # If news has target groups, user must be in one of them
                if news_target_groups.exists():
                    user_in_target_group = news_target_groups.filter(members=employee).exists()
                    
                    if not user_in_target_group:
                        return Response(
                            {'error': 'You do not have access to this news'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                
            except Employee.DoesNotExist:
                return Response(
                    {'error': 'Employee profile not found'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Increment view count
        instance.increment_view_count()
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def perform_create(self, serializer):
        """Create news and send notifications if published"""
        news = serializer.save(
            created_by=self.request.user,
            author=self.request.user
        )
        
        # Auto-send notifications if published
        if news.is_published and news.notify_members and not news.notification_sent:
            self._send_notifications_async(news)
        
        return news
    
    def perform_update(self, serializer):
        """Update news"""
        instance = self.get_object()
        was_published = instance.is_published
        
        news = serializer.save(updated_by=self.request.user)
        
        # Send notifications if newly published
        if not was_published and news.is_published and news.notify_members and not news.notification_sent:
            self._send_notifications_async(news)
        
        return news
    
    @action(detail=True, methods=['post'], serializer_class=None)
    def toggle_pin(self, request, pk=None):
        """Toggle pin status"""
        news = self.get_object()
        
        news.is_pinned = not news.is_pinned
        news.save(update_fields=['is_pinned'])
        
        return Response({
            'message': f'News {"pinned" if news.is_pinned else "unpinned"} successfully',
            'is_pinned': news.is_pinned
        })
    
    @action(detail=True, methods=['post'], serializer_class=None)
    def toggle_publish(self, request, pk=None):
        """Toggle publish status"""
        news = self.get_object()
        
        news.is_published = not news.is_published
        news.save(update_fields=['is_published'])
        
        response_data = {
            'message': f'News {"published" if news.is_published else "unpublished"} successfully',
            'is_published': news.is_published
        }
        
        # Auto-send notifications when publishing
        if news.is_published and news.notify_members and not news.notification_sent:
            graph_token = extract_graph_token_from_request(request)
            
            if graph_token:
                notification_result = news_notification_manager.send_news_notification(
                    news=news,
                    access_token=graph_token,
                    request=request
                )
                
                if notification_result:
                    response_data['notification_status'] = {
                        'sent': notification_result['success'],
                        'total_recipients': notification_result.get('total_recipients', 0)
                    }
        
        return Response(response_data)
    
    def _send_notifications_async(self, news):
        """Helper to send notifications"""
        try:
            graph_token = extract_graph_token_from_request(self.request)
            
            if graph_token:
                news_notification_manager.send_news_notification(
                    news=news,
                    access_token=graph_token,
                    request=self.request
                )
        except Exception as e:
            logger.error(f"Failed to send notifications for news {news.id}: {e}")
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """✅ Get statistics - Admin only"""
        base_queryset = CompanyNews.objects.filter(is_deleted=False)
        
        total_news = base_queryset.count()
        published_news = base_queryset.filter(is_published=True).count()
        pinned_news = base_queryset.filter(is_pinned=True).count()
        
        total_views = base_queryset.aggregate(
            total=Sum('view_count')
        )['total'] or 0
        
        return Response({
            'total_news': total_news,
            'published_news': published_news,
            'pinned_news': pinned_news,
            'draft_news': total_news - published_news,
            'total_views': total_views
        })


# ==================== NEWS PERMISSIONS VIEW ====================

from rest_framework.views import APIView

class NewsPermissionsView(APIView):
    """Get current user's news permissions"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """✅ Return simplified permissions"""
        user = request.user
        is_admin = is_admin_user(user)
        
        return Response({
            'is_admin': is_admin,
            'capabilities': {
                'can_view_news': True,  # Everyone can view
                'can_create_news': is_admin,
                'can_update_news': is_admin,
                'can_delete_news': is_admin,
                'can_pin_news': is_admin,
                'can_publish_news': is_admin,
                'can_view_target_groups': is_admin,
                'can_create_target_groups': is_admin,
                'can_update_target_groups': is_admin,
                'can_delete_target_groups': is_admin,
                'can_view_statistics': is_admin,
            }
        })