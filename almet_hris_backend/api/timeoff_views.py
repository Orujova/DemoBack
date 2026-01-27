# api/timeoff_views.py
"""
Time Off System Views - ROLE-BASED ACCESS CONTROL
NO PERMISSION DECORATORS - Only role checks
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum 
from django.utils import timezone
from rest_framework.parsers import MultiPartParser
import pandas as pd
from django.http import HttpResponse
from io import BytesIO
import logging

from .timeoff_models import (
    TimeOffBalance, TimeOffRequest, TimeOffSettings, TimeOffActivity
)
from .timeoff_serializers import (
    TimeOffBalanceSerializer, TimeOffRequestSerializer,
    TimeOffRequestCreateSerializer, TimeOffApproveSerializer,
    TimeOffRejectSerializer, TimeOffSettingsSerializer,
    TimeOffActivitySerializer
)
from .models import Employee
from .notification_service import notification_service
from .token_helpers import extract_graph_token_from_request
from .timeoff_permissions import (
    get_timeoff_request_access,
    filter_timeoff_requests_by_access,
    filter_timeoff_balances_by_access,
    can_approve_timeoff_role_based,
    can_view_timeoff_request_role_based,
    is_admin_user
)

logger = logging.getLogger(__name__)


class TimeOffBalanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Time Off Balance ViewSet - ROLE-BASED ACCESS
    ✅ FIX: No parser_classes to allow both JSON and multipart
    """
    queryset = TimeOffBalance.objects.all()
    serializer_class = TimeOffBalanceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter by user and role-based access"""
        queryset = super().get_queryset()
        
        # Apply role-based filtering
        queryset = filter_timeoff_balances_by_access(self.request.user, queryset)
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        """List balances - role-based access"""
        access = get_timeoff_request_access(request.user)
        
        if not access['can_view_all'] and not access['is_manager'] and not access['employee']:
            return Response(
                {
                    'error': 'No access',
                    'detail': 'You need appropriate permissions to view balances'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().list(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'])
    def my_balance(self, request):
        """Get own balance"""
        if not hasattr(request.user, 'employee_profile'):
            return Response(
                {'error': 'No employee profile found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        employee = request.user.employee_profile
        balance = TimeOffBalance.get_or_create_for_employee(employee)
        serializer = self.get_serializer(balance)
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def team_balances(self, request):
        """
        Get team balances
        - Admin: All employees' balances
        - Line Manager: Own + direct reports' balances
        - Employee: Only own balance
        """
        access = get_timeoff_request_access(request.user)
        
        # Get balances based on access
        if access['can_view_all']:
            # Admin - all balances
            balances = TimeOffBalance.objects.all().select_related(
                'employee', 
                'employee__user',
                'employee__department',
                'employee__line_manager'
            ).order_by('employee__full_name')
            
            view_type = 'admin'
        elif access['is_manager'] and access['accessible_employee_ids']:
            # Manager - team balances
            balances = TimeOffBalance.objects.filter(
                employee_id__in=access['accessible_employee_ids']
            ).select_related(
                'employee',
                'employee__user',
                'employee__department',
                'employee__line_manager'
            ).order_by('employee__full_name')
            
            view_type = 'manager'
        elif access['employee']:
            # Employee - only own
            balances = TimeOffBalance.objects.filter(
                employee=access['employee']
            ).select_related(
                'employee',
                'employee__user',
                'employee__department',
                'employee__line_manager'
            )
            
            view_type = 'employee'
        else:
            return Response(
                {'error': 'No access to view balances'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(balances, many=True)
        
        # Calculate statistics
        total_balance = sum(float(b.current_balance_hours) for b in balances)
        total_used = sum(float(b.used_hours_this_month) for b in balances)
        avg_balance = total_balance / max(balances.count(), 1)
        
        return Response({
            'count': balances.count(),
            'balances': serializer.data,
            'view_type': view_type,
            'access_level': access['access_level'],
            'statistics': {
                'total_balance_hours': round(total_balance, 2),
                'total_used_hours': round(total_used, 2),
                'average_balance_hours': round(avg_balance, 2),
                'employee_count': balances.count()
            }
        })
    
    @action(detail=True, methods=['post'])
    def update_balance(self, request, pk=None):
        """
        Update employee balance manually - Admin only
        Also marks balance as initialized
        ✅ FIX: Accepts JSON (no parser_classes restriction)
        """
        if not is_admin_user(request.user):
            return Response(
                {'error': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        balance = self.get_object()
        
        new_balance = request.data.get('new_balance')
        reason = request.data.get('reason', 'Manual adjustment by admin')
        
        if new_balance is None:
            return Response(
                {'error': 'new_balance is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from decimal import Decimal
            old_balance = balance.current_balance_hours
            new_balance_decimal = Decimal(str(new_balance))
            
            # Validate
            if new_balance_decimal < 0:
                return Response(
                    {'error': 'Balance cannot be negative'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update balance
            balance.current_balance_hours = new_balance_decimal
            balance.is_initialized = True
            balance.last_reset_date = timezone.now().date()
            balance.save()
            
            # Log activity
            TimeOffActivity.objects.create(
                request=None,
                activity_type='BALANCE_UPDATED',
                description=f"Balance updated from {old_balance}h to {new_balance}h. Reason: {reason}",
                performed_by=request.user,
                metadata={
                    'employee_id': balance.employee.employee_id,
                    'employee_name': balance.employee.full_name,
                    'old_balance': float(old_balance),
                    'new_balance': float(new_balance),
                    'reason': reason,
                    'initialized': True
                }
            )
            
            logger.info(
                f"✅ Balance updated and initialized for {balance.employee.full_name}: "
                f"{old_balance}h → {new_balance}h"
            )
            
            return Response({
                'success': True,
                'message': 'Balance updated successfully',
                'old_balance': float(old_balance),
                'new_balance': float(new_balance),
                'employee_name': balance.employee.full_name,
                'employee_id': balance.employee.employee_id
            })
            
        except Exception as e:
            logger.error(f"❌ Balance update failed: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser])
    def bulk_upload_balances(self, request):
        """
        Bulk upload balances from Excel file - Admin only
        Also marks balances as initialized
        ✅ FIX: Only this endpoint uses MultiPartParser
        """
        if not is_admin_user(request.user):
            return Response(
                {'error': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['file']
        
        # Validate file extension
        if not file.name.endswith(('.xlsx', '.xls', '.csv')):
            return Response(
                {'error': 'Invalid file format. Please upload Excel (.xlsx, .xls) or CSV file'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Read file
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
            
            # Validate columns
            required_columns = ['employee_id', 'new_balance']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                return Response(
                    {
                        'error': f'Missing required columns: {", ".join(missing_columns)}',
                        'required_columns': required_columns,
                        'found_columns': list(df.columns)
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Process rows
            success_count = 0
            failed_count = 0
            results = []
            
            for index, row in df.iterrows():
                try:
                    employee_id = str(row['employee_id']).strip()
                    new_balance = float(row['new_balance'])
                    reason = str(row.get('reason', 'Bulk upload by admin')).strip()
                    
                    # Validate balance
                    if new_balance < 0:
                        raise ValueError('Balance cannot be negative')
                    
                    # Find employee
                    employee = Employee.objects.get(
                        employee_id=employee_id,
                        is_deleted=False
                    )
                    
                    # Get or create balance
                    balance = TimeOffBalance.get_or_create_for_employee(employee)
                    old_balance = balance.current_balance_hours
                    
                    # Update balance
                    from decimal import Decimal
                    balance.current_balance_hours = Decimal(str(new_balance))
                    balance.is_initialized = True
                    balance.last_reset_date = timezone.now().date()
                    balance.save()
                    
                    # Log activity
                    TimeOffActivity.objects.create(
                        request=None,
                        activity_type='BALANCE_UPDATED',
                        description=f"Bulk upload: Balance updated from {old_balance}h to {new_balance}h. Reason: {reason}",
                        performed_by=request.user,
                        metadata={
                            'employee_id': employee.employee_id,
                            'employee_name': employee.full_name,
                            'old_balance': float(old_balance),
                            'new_balance': new_balance,
                            'reason': reason,
                            'upload_type': 'bulk',
                            'initialized': True
                        }
                    )
                    
                    success_count += 1
                    results.append({
                        'row': index + 2,
                        'employee_id': employee_id,
                        'employee_name': employee.full_name,
                        'old_balance': float(old_balance),
                        'new_balance': new_balance,
                        'status': 'success'
                    })
                    
                except Employee.DoesNotExist:
                    failed_count += 1
                    results.append({
                        'row': index + 2,
                        'employee_id': employee_id,
                        'status': 'failed',
                        'error': 'Employee not found'
                    })
                    
                except Exception as e:
                    failed_count += 1
                    results.append({
                        'row': index + 2,
                        'employee_id': employee_id if 'employee_id' in locals() else 'N/A',
                        'status': 'failed',
                        'error': str(e)
                    })
            
      
            
            return Response({
                'success': True,
                'message': f'Bulk upload completed: {success_count} succeeded, {failed_count} failed',
                'total_rows': len(df),
                'success_count': success_count,
                'failed_count': failed_count,
                'results': results
            })
            
        except Exception as e:
            logger.error(f"❌ Bulk upload failed: {e}")
            return Response(
                {'error': f'Failed to process file: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def reset_monthly_balances(self, request):
        """
        Reset monthly balances - Admin only
        Only resets initialized balances
        ✅ FIXED: HƏR AY 4 saat əlavə edir (istifadə etməsə də)
        """
        if not is_admin_user(request.user):
            return Response(
                {'error': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        reset_count = 0
        skipped_count = 0
        failed_count = 0
        results = []
        
        for balance in TimeOffBalance.objects.all():
            try:
                if not balance.is_initialized:
                    skipped_count += 1
                    results.append({
                        'employee_id': balance.employee.employee_id,
                        'employee_name': balance.employee.full_name,
                        'status': 'skipped',
                        'reason': 'Not initialized'
                    })
                    continue
                
                if balance.check_and_reset_monthly():
                    reset_count += 1
                    results.append({
                        'employee_id': balance.employee.employee_id,
                        'employee_name': balance.employee.full_name,
                        'new_balance': float(balance.current_balance_hours),
                        'status': 'reset'
                    })
            except Exception as e:
                failed_count += 1
                results.append({
                    'employee_id': balance.employee.employee_id,
                    'employee_name': balance.employee.full_name,
                    'status': 'failed',
                    'error': str(e)
                })
        
        return Response({
            'success': True,
            'message': f'{reset_count} balances reset, {skipped_count} skipped (not initialized), {failed_count} failed',
            'reset_count': reset_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count,
            'results': results
        })
    
    @action(detail=False, methods=['get'])
    def download_template(self, request):
        """
        Download Excel template for bulk upload - Admin only
        """
        if not is_admin_user(request.user):
            return Response(
                {'error': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Create sample DataFrame
        data = {
            'employee_id': ['EMP001', 'EMP002', 'EMP003'],
            'new_balance': [4.0, 3.5, 2.0],
            'reason': ['Monthly reset', 'Adjustment', 'Manual update']
        }
        df = pd.DataFrame(data)
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Balances')
            
            # Format worksheet
            worksheet = writer.sheets['Balances']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(cell.value)
                    except:
                        pass
                adjusted_width = (max_length + 2)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=timeoff_balances_template.xlsx'
        
        return response


class TimeOffRequestViewSet(viewsets.ModelViewSet):
    """
    Time Off Request ViewSet - ROLE-BASED ACCESS
    Complete CRUD + Approve/Reject/Cancel actions
    """
    queryset = TimeOffRequest.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TimeOffRequestCreateSerializer
        elif self.action == 'approve':
            return TimeOffApproveSerializer
        elif self.action == 'reject':
            return TimeOffRejectSerializer
        return TimeOffRequestSerializer
    
    def get_queryset(self):
        """Filter requests based on role-based access"""
        queryset = super().get_queryset().select_related(
            'employee', 'employee__user', 'line_manager', 
            'approved_by', 'created_by'
        )
        
        user = self.request.user
        
        # Filter parameters
        status_filter = self.request.query_params.get('status')
        employee_id = self.request.query_params.get('employee_id')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        # Apply filters
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if employee_id:
            queryset = queryset.filter(employee__employee_id=employee_id)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        # Apply role-based filtering
        queryset = filter_timeoff_requests_by_access(user, queryset)
        
        return queryset.order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        """List requests - role-based access"""
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """Get single request - role-based check"""
        instance = self.get_object()
        
        # Check if user can view this specific request
        can_view, reason = can_view_timeoff_request_role_based(request.user, instance)
        
        if not can_view:
            return Response(
                {'error': 'Cannot view this request', 'reason': reason},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        """Create time off request"""
        if not hasattr(request.user, 'employee_profile'):
            return Response(
                {'error': 'No employee profile found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        employee = request.user.employee_profile
        
        # Create with employee
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Force employee to be the logged-in user
        instance = serializer.save(
            employee=employee,
            created_by=request.user
        )
        
        # Send notification to line manager
        self._send_line_manager_notification(instance, request)
        
        # Return created request
        response_serializer = TimeOffRequestSerializer(instance)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, *args, **kwargs):
        """Update time off request - only own, only if PENDING"""
        instance = self.get_object()
        
        if not hasattr(request.user, 'employee_profile'):
            return Response(
                {'error': 'No employee profile found'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if instance.employee != request.user.employee_profile:
            return Response(
                {'error': 'Can only update your own requests'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if instance.status != 'PENDING':
            return Response(
                {'error': f'Cannot update request with status: {instance.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Delete time off request - only own, only if PENDING"""
        instance = self.get_object()
        
        if not hasattr(request.user, 'employee_profile'):
            return Response(
                {'error': 'No employee profile found'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if instance.employee != request.user.employee_profile:
            return Response(
                {'error': 'Can only delete your own requests'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if instance.status != 'PENDING':
            return Response(
                {'error': f'Cannot delete request with status: {instance.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve time off request - Admin OR Line Manager"""
        request_obj = self.get_object()
        
        # Role-based authorization
        can_approve, reason = can_approve_timeoff_role_based(request.user, request_obj)
        
        if not can_approve:
            return Response(
                {'error': 'Cannot approve this request', 'reason': reason},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request_obj.status != 'PENDING':
            return Response(
                {'error': f'Cannot approve request with status: {request_obj.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Approve
            request_obj.approve(request.user)
            
            # Activity log
            TimeOffActivity.objects.create(
                request=request_obj,
                activity_type='APPROVED',
                description=f"Approved by {request.user.get_full_name()}",
                performed_by=request.user,
                metadata={
                    'approved_at': timezone.now().isoformat(),
                    'balance_deducted': True,
                    'approved_by_role': reason
                }
            )
            
            # Send notifications
            self._send_employee_notification(request_obj, 'approved', request)
            self._send_hr_notification(request_obj, request)
            
            serializer = self.get_serializer(request_obj)
            return Response({
                'success': True,
                'message': 'Request approved successfully',
                'request': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Approve failed: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject time off request - Admin OR Line Manager"""
        request_obj = self.get_object()
        
        # Role-based authorization
        can_approve, reason = can_approve_timeoff_role_based(request.user, request_obj)
        
        if not can_approve:
            return Response(
                {'error': 'Cannot reject this request', 'reason': reason},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request_obj.status != 'PENDING':
            return Response(
                {'error': f'Cannot reject request with status: {request_obj.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        rejection_reason = serializer.validated_data['rejection_reason']
        
        try:
            # Reject
            request_obj.reject(rejection_reason, request.user)
            
            # Activity log
            TimeOffActivity.objects.create(
                request=request_obj,
                activity_type='REJECTED',
                description=f"Rejected by {request.user.get_full_name()}: {rejection_reason}",
                performed_by=request.user,
                metadata={
                    'rejected_at': timezone.now().isoformat(),
                    'rejection_reason': rejection_reason
                }
            )
            
            # Send notification to employee
            self._send_employee_notification(request_obj, 'rejected', request)
            
            serializer = TimeOffRequestSerializer(request_obj)
            return Response({
                'success': True,
                'message': 'Request rejected',
                'request': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Reject failed: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel time off request - only own requests"""
        request_obj = self.get_object()
        
        if not hasattr(request.user, 'employee_profile'):
            return Response(
                {'error': 'No employee profile found'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request_obj.employee != request.user.employee_profile:
            return Response(
                {'error': 'Can only cancel your own requests'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request_obj.status not in ['PENDING', 'APPROVED']:
            return Response(
                {'error': f'Cannot cancel request with status: {request_obj.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Cancel
            request_obj.cancel()
            
            # Activity log
            TimeOffActivity.objects.create(
                request=request_obj,
                activity_type='CANCELLED',
                description=f"Cancelled by {request.user.get_full_name()}",
                performed_by=request.user,
                metadata={
                    'cancelled_at': timezone.now().isoformat()
                }
            )
            
            serializer = self.get_serializer(request_obj)
            return Response({
                'success': True,
                'message': 'Request cancelled successfully',
                'request': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Cancel failed: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def my_requests(self, request):
        """Get own time off requests"""
        if not hasattr(request.user, 'employee_profile'):
            return Response(
                {'error': 'No employee profile found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        employee = request.user.employee_profile
        requests = TimeOffRequest.objects.filter(employee=employee).order_by('-created_at')
        
        serializer = self.get_serializer(requests, many=True)
        return Response({
            'count': requests.count(),
            'requests': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def pending_approvals(self, request):
        """
        Get pending approvals - role-based
        - Admin: All pending requests
        - Line Manager: Only their team's pending requests
        """
        access = get_timeoff_request_access(request.user)
        
        # Get pending requests
        requests = TimeOffRequest.objects.filter(
            status='PENDING'
        ).select_related(
            'employee', 
            'employee__user',
            'employee__department',
            'line_manager'
        )
        
        # Apply role-based filtering
        requests = filter_timeoff_requests_by_access(request.user, requests)
        
        serializer = self.get_serializer(requests.order_by('-created_at'), many=True)
        
        return Response({
            'count': requests.count(),
            'requests': serializer.data,
            'access_level': access['access_level'],
            'can_view_all': access['can_view_all'],
            'is_manager': access['is_manager']
        })
    
    # ==================== NOTIFICATION HELPERS ====================
    
    def _send_line_manager_notification(self, request_obj, request):
        """Send notification to line manager"""
        if not request_obj.line_manager or not request_obj.line_manager.email:
            logger.warning(f"No line manager email for request {request_obj.id}")
            return
        
        try:
            access_token = extract_graph_token_from_request(request)
            if not access_token:
                logger.error("No Graph token for notification")
                return
            
            subject = f"[TIME OFF] {request_obj.employee.full_name} - {request_obj.date}"
            
            body_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
                <h2 style="color: #2563EB;">Time Off Request - Approval Needed</h2>
                
                <div style="background-color: #F3F4F6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Request Details</h3>
                    <p><strong>Employee:</strong> {request_obj.employee.full_name}</p>
                    <p><strong>Employee ID:</strong> {request_obj.employee.employee_id}</p>
                    <p><strong>Date:</strong> {request_obj.date.strftime('%B %d, %Y')}</p>
                    <p><strong>Time:</strong> {request_obj.start_time.strftime('%H:%M')} - {request_obj.end_time.strftime('%H:%M')}</p>
                    <p><strong>Duration:</strong> {request_obj.duration_hours} hours</p>
                    <p><strong>Reason:</strong> {request_obj.reason}</p>
                </div>
                
                <p style="color: #DC2626; font-weight: bold;">
                    ⚠️ This request requires your approval.
                </p>
                
                <p>Please log in to the system to approve or reject this request.</p>
            </div>
            """
            
            notification_service.send_email(
                recipient_email=request_obj.line_manager.email,
                subject=subject,
                body_html=body_html,
                access_token=access_token,
                related_model='TimeOffRequest',
                related_object_id=str(request_obj.id),
                sent_by=request.user
            )
            
        except Exception as e:
            logger.error(f"Failed to send line manager notification: {e}")
    
    def _send_hr_notification(self, request_obj, request):
        """Send notification to HR"""
        settings = TimeOffSettings.get_settings()
        hr_emails = settings.get_hr_emails_list()
        
        if not hr_emails:
            logger.warning("No HR emails configured")
            return
        
        try:
            access_token = extract_graph_token_from_request(request)
            if not access_token:
                logger.error("No Graph token for HR notification")
                return
            
            subject = f"[TIME OFF] {request_obj.employee.full_name} - {request_obj.date}"
            
            body_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
                <h2 style="color: #10B981;">Time Off Approved - HR Notification</h2>
                
                <div style="background-color: #F3F4F6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Request Details</h3>
                    <p><strong>Employee:</strong> {request_obj.employee.full_name}</p>
                    <p><strong>Employee ID:</strong> {request_obj.employee.employee_id}</p>
                    <p><strong>Department:</strong> {request_obj.employee.department.name if request_obj.employee.department else 'N/A'}</p>
                    <p><strong>Date:</strong> {request_obj.date.strftime('%B %d, %Y')}</p>
                    <p><strong>Time:</strong> {request_obj.start_time.strftime('%H:%M')} - {request_obj.end_time.strftime('%H:%M')}</p>
                    <p><strong>Duration:</strong> {request_obj.duration_hours} hours</p>
                    <p><strong>Reason:</strong> {request_obj.reason}</p>
                </div>
                
                <div style="background-color: #ECFDF5; padding: 15px; border-radius: 8px; border-left: 4px solid #10B981;">
                    <p style="margin: 0;"><strong>Approved by:</strong> {request_obj.line_manager.full_name if request_obj.line_manager else 'N/A'}</p>
                    <p style="margin: 5px 0 0 0;"><strong>Approved at:</strong> {request_obj.approved_at.strftime('%B %d, %Y %H:%M') if request_obj.approved_at else 'N/A'}</p>
                </div>
            </div>
            """
            
            # Send to all HR emails
            for hr_email in hr_emails:
                notification_service.send_email(
                    recipient_email=hr_email,
                    subject=subject,
                    body_html=body_html,
                    access_token=access_token,
                    related_model='TimeOffRequest',
                    related_object_id=str(request_obj.id),
                    sent_by=request.user
                )
            
            # Mark as notified
            request_obj.hr_notified = True
            request_obj.hr_notified_at = timezone.now()
            request_obj.save()
            
        except Exception as e:
            logger.error(f"Failed to send HR notification: {e}")
    
    def _send_employee_notification(self, request_obj, notification_type, request):
        """Send notification to employee"""
        if not request_obj.employee.email:
            logger.warning(f"No employee email for request {request_obj.id}")
            return
        
        try:
            access_token = extract_graph_token_from_request(request)
            if not access_token:
                logger.error("No Graph token for employee notification")
                return
            
            if notification_type == 'approved':
                subject = f"[TIME OFF] Your request for {request_obj.date} - APPROVED"
                color = "#10B981"
                status_text = "APPROVED ✓"
                message = "Your time off request has been approved by your line manager."
            else:  # rejected
                subject = f"[TIME OFF] Your request for {request_obj.date} - REJECTED"
                color = "#EF4444"
                status_text = "REJECTED ✗"
                message = "Your time off request has been rejected by your line manager."
            
            body_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
                <h2 style="color: {color};">Time Off Request {status_text}</h2>
                
                <p>{message}</p>
                
                <div style="background-color: #F3F4F6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Your Request Details</h3>
                    <p><strong>Date:</strong> {request_obj.date.strftime('%B %d, %Y')}</p>
                    <p><strong>Time:</strong> {request_obj.start_time.strftime('%H:%M')} - {request_obj.end_time.strftime('%H:%M')}</p>
                    <p><strong>Duration:</strong> {request_obj.duration_hours} hours</p>
                    <p><strong>Reason:</strong> {request_obj.reason}</p>
                </div>
            """
            
            if notification_type == 'rejected' and request_obj.rejection_reason:
                body_html += f"""
                <div style="background-color: #FEE2E2; padding: 15px; border-radius: 8px; border-left: 4px solid #EF4444;">
                    <p style="margin: 0;"><strong>Rejection Reason:</strong></p>
                    <p style="margin: 5px 0 0 0;">{request_obj.rejection_reason}</p>
                </div>
                """
            
            body_html += """
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #E5E7EB;">
                    <p style="color: #6B7280; font-size: 12px;">
                        This is an automated notification from HR Management System.
                    </p>
                </div>
            </div>
            """
            
            notification_service.send_email(
                recipient_email=request_obj.employee.email,
                subject=subject,
                body_html=body_html,
                access_token=access_token,
                related_model='TimeOffRequest',
                related_object_id=str(request_obj.id),
                sent_by=request.user
            )
            
        except Exception as e:
            logger.error(f"Failed to send employee notification: {e}")


class TimeOffSettingsViewSet(viewsets.ModelViewSet):
    """
    Time Off Settings ViewSet - Admin Only
    """
    queryset = TimeOffSettings.objects.all()
    serializer_class = TimeOffSettingsSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Only 1 settings object exists
        return TimeOffSettings.objects.all()[:1]
    
    def list(self, request, *args, **kwargs):
        """List settings - Admin only"""
        if not is_admin_user(request.user):
            return Response(
                {'error': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """Get settings detail - Admin only"""
        if not is_admin_user(request.user):
            return Response(
                {'error': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().retrieve(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current settings - Admin only"""
        if not is_admin_user(request.user):
            return Response(
                {'error': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        settings = TimeOffSettings.get_settings()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)
    
    def update(self, request, *args, **kwargs):
        """Update settings - Admin only"""
        if not is_admin_user(request.user):
            return Response(
                {'error': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().update(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def update_hr_emails(self, request, pk=None):
        """Update HR notification emails - Admin only"""
        if not is_admin_user(request.user):
            return Response(
                {'error': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        settings = self.get_object()
        
        hr_emails = request.data.get('hr_notification_emails')
        if not hr_emails:
            return Response(
                {'error': 'hr_notification_emails is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        settings.hr_notification_emails = hr_emails
        settings.save()
        
        return Response({
            'success': True,
            'message': 'HR emails updated successfully',
            'hr_emails': settings.get_hr_emails_list()
        })


class TimeOffActivityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Time Off Activity ViewSet - ROLE-BASED ACCESS
    Read-only - activities are auto-created
    """
    queryset = TimeOffActivity.objects.all()
    serializer_class = TimeOffActivitySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter activities based on role-based access"""
        queryset = super().get_queryset().select_related(
            'request', 'request__employee', 'performed_by'
        )
        
        access = get_timeoff_request_access(self.request.user)
        
        # Admin - see all activities
        if access['can_view_all']:
            return queryset.order_by('-created_at')
        
        # Manager or Employee - filter by accessible requests
        if access['accessible_employee_ids']:
            return queryset.filter(
                request__employee_id__in=access['accessible_employee_ids']
            ).order_by('-created_at')
        
        # No access
        return queryset.none()
    
    def list(self, request, *args, **kwargs):
        """List activities - role-based access"""
        return super().list(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'])
    def my_activities(self, request):
        """Get own activities"""
        if not hasattr(request.user, 'employee_profile'):
            return Response(
                {'error': 'No employee profile found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        employee = request.user.employee_profile
        activities = TimeOffActivity.objects.filter(
            request__employee=employee
        ).order_by('-created_at')
        
        serializer = self.get_serializer(activities, many=True)
        return Response({
            'count': activities.count(),
            'activities': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def by_request(self, request):
        """Get activities for specific request - Admin only"""
        if not is_admin_user(request.user):
            return Response(
                {'error': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        request_id = request.query_params.get('request_id')
        
        if not request_id:
            return Response(
                {'error': 'request_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        activities = TimeOffActivity.objects.filter(
            request_id=request_id
        ).order_by('created_at')
        
        serializer = self.get_serializer(activities, many=True)
        return Response({
            'request_id': request_id,
            'count': activities.count(),
            'activities': serializer.data
        })


# ==================== DASHBOARD VIEW ====================

class TimeOffDashboardViewSet(viewsets.ViewSet):
    """
    Time Off Dashboard ViewSet - ROLE-BASED ACCESS
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def my_access_info(self, request):
        """
        Get my time off request access info - ROLE-BASED
        No permission required - everyone can check their own access
        """
        access = get_timeoff_request_access(request.user)
        
        # Count accessible requests
        if access['can_view_all']:
            accessible_count = TimeOffRequest.objects.count()
            accessible_count_str = "All"
        else:
            accessible_count = TimeOffRequest.objects.filter(
                employee_id__in=access['accessible_employee_ids']
            ).count() if access['accessible_employee_ids'] else 0
            accessible_count_str = str(accessible_count)
        
        # Employee info
        employee = access['employee']
        employee_info = None
        if employee:
            employee_info = {
                'id': employee.id,
                'employee_id': employee.employee_id,
                'full_name': employee.full_name,
                'email': employee.email,
                'department': employee.department.name if employee.department else None
            }
        
        return Response({
            'can_view_all': access['can_view_all'],
            'is_manager': access['is_manager'],
            'is_admin': is_admin_user(request.user),
            'access_level': access['access_level'],
            'accessible_count': accessible_count_str,
            'employee_info': employee_info
        })
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """
        Get dashboard overview - role-based
        """
        access = get_timeoff_request_access(request.user)
        
        if access['can_view_all']:
            # Full dashboard for Admin
            return self._get_full_dashboard(request)
        else:
            # Personal dashboard for Employee/Manager
            return self._get_personal_dashboard(request, access)
    
    def _get_personal_dashboard(self, request, access):
        """Personal dashboard for employee/manager"""
        if not access['employee']:
            return Response(
                {'error': 'No employee profile found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        employee = access['employee']
        
        # Get balance
        balance = TimeOffBalance.get_or_create_for_employee(employee)
        
        # Get requests (filtered by access)
        if access['accessible_employee_ids']:
            my_requests = TimeOffRequest.objects.filter(
                employee_id__in=access['accessible_employee_ids']
            )
        else:
            my_requests = TimeOffRequest.objects.none()
        
        # Statistics
        dashboard_data = {
            'access_level': access['access_level'],
            'is_manager': access['is_manager'],
            'balance': {
                'current_balance': float(balance.current_balance_hours),
                'monthly_allowance': float(balance.monthly_allowance_hours),
                'used_this_month': float(balance.used_hours_this_month),
                'last_reset': balance.last_reset_date.isoformat()
            },
            'requests': {
                'total': my_requests.count(),
                'pending': my_requests.filter(status='PENDING').count(),
                'approved': my_requests.filter(status='APPROVED').count(),
                'rejected': my_requests.filter(status='REJECTED').count(),
            },
            'recent_requests': TimeOffRequestSerializer(
                my_requests.order_by('-created_at')[:5],
                many=True
            ).data
        }
        
        # If manager, add team stats
        if access['is_manager']:
            team_requests = my_requests.exclude(employee=employee)
            dashboard_data['team_stats'] = {
                'total_team_requests': team_requests.count(),
                'pending_approvals': team_requests.filter(status='PENDING').count(),
            }
        
        return Response(dashboard_data)
    
    def _get_full_dashboard(self, request):
        """Full dashboard for Admin"""
        # System-wide statistics
        all_balances = TimeOffBalance.objects.all()
        all_requests = TimeOffRequest.objects.all()
        
        dashboard_data = {
            'access_level': 'Admin - Full Access',
            'is_admin': True,
            'system_stats': {
                'total_employees': all_balances.count(),
                'total_balance_hours': float(all_balances.aggregate(
                    total=Sum('current_balance_hours')
                )['total'] or 0),
                'average_balance': float(all_balances.aggregate(
                    avg=Sum('current_balance_hours')
                )['avg'] or 0) / max(all_balances.count(), 1),
            },
            'requests': {
                'total': all_requests.count(),
                'pending': all_requests.filter(status='PENDING').count(),
                'approved': all_requests.filter(status='APPROVED').count(),
                'rejected': all_requests.filter(status='REJECTED').count(),
                'cancelled': all_requests.filter(status='CANCELLED').count(),
            },
            'recent_requests': TimeOffRequestSerializer(
                all_requests.order_by('-created_at')[:10],
                many=True
            ).data,
            'pending_approvals': TimeOffRequestSerializer(
                all_requests.filter(status='PENDING').order_by('-created_at')[:10],
                many=True
            ).data
        }
        
        return Response(dashboard_data)
    
    @action(detail=False, methods=['get'])
    def team_overview(self, request):
        """
        Get team dashboard for line manager
        """
        access = get_timeoff_request_access(request.user)
        
        if not access['is_manager']:
            return Response(
                {'error': 'Not a line manager'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not access['employee']:
            return Response(
                {'error': 'No employee profile found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        employee = access['employee']
        
        # Get team requests (where user is line manager)
        team_requests = TimeOffRequest.objects.filter(
            line_manager=employee
        )
        
        dashboard_data = {
            'team_stats': {
                'total_requests': team_requests.count(),
                'pending_approvals': team_requests.filter(status='PENDING').count(),
                'approved': team_requests.filter(status='APPROVED').count(),
                'rejected': team_requests.filter(status='REJECTED').count(),
            },
            'pending_approvals': TimeOffRequestSerializer(
                team_requests.filter(status='PENDING').order_by('-created_at'),
                many=True
            ).data,
            'recent_approvals': TimeOffRequestSerializer(
                team_requests.filter(status__in=['APPROVED', 'REJECTED']).order_by('-updated_at')[:10],
                many=True
            ).data
        }
        
        return Response(dashboard_data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get statistics - Admin only
        """
        if not is_admin_user(request.user):
            return Response(
                {'error': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Time-based filters
        from datetime import datetime, timedelta
        today = timezone.now().date()
        
        month_start = today.replace(day=1)
        last_month = (month_start - timedelta(days=1)).replace(day=1)
        
        # Statistics
        stats = {
            'current_month': {
                'total_requests': TimeOffRequest.objects.filter(
                    date__gte=month_start
                ).count(),
                'approved': TimeOffRequest.objects.filter(
                    date__gte=month_start,
                    status='APPROVED'
                ).count(),
                'pending': TimeOffRequest.objects.filter(
                    date__gte=month_start,
                    status='PENDING'
                ).count(),
            },
            'last_month': {
                'total_requests': TimeOffRequest.objects.filter(
                    date__gte=last_month,
                    date__lt=month_start
                ).count(),
                'approved': TimeOffRequest.objects.filter(
                    date__gte=last_month,
                    date__lt=month_start,
                    status='APPROVED'
                ).count(),
            },
            'by_department': []
        }
        
        # Department breakdown
        from django.db.models import Count
        from .models import Department
        
        dept_stats = TimeOffRequest.objects.filter(
            date__gte=month_start
        ).values(
            'employee__department__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')
        
        stats['by_department'] = list(dept_stats)
        
        return Response(stats)