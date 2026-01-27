# api/celebration_test_views.py
"""
OPTIONAL: Test endpoints for celebration notifications
Use these to manually trigger notifications for testing
"""

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .celebration_notification_service import celebration_notification_service
from .models import Employee

logger = logging.getLogger(__name__)


@swagger_auto_schema(
    method='post',
    operation_description="🧪 TEST: Send birthday notification for specific employee",
    operation_summary="Test Birthday Notification",
    tags=['Celebrations - Test'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['employee_id'],
        properties={
            'employee_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Employee ID')
        }
    ),
    responses={200: openapi.Response(description='Success')}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_birthday_notification(request):
    """Test birthday notification for specific employee"""
    try:
        employee_id = request.data.get('employee_id')
        
        if not employee_id:
            return Response({
                'error': 'employee_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return Response({
                'error': 'Employee not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if not employee.date_of_birth:
            return Response({
                'error': 'Employee has no birth date'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        success = celebration_notification_service.send_birthday_notification(employee)
        
        if success:
            return Response({
                'success': True,
                'message': f'Birthday notification sent for {employee.first_name} {employee.last_name}',
                'employee': {
                    'id': employee.id,
                    'name': f'{employee.first_name} {employee.last_name}',
                    'birth_date': employee.date_of_birth
                }
            })
        else:
            return Response({
                'success': False,
                'error': 'Failed to send notification'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"Error in test birthday notification: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='post',
    operation_description="🧪 TEST: Send anniversary notification for specific employee",
    operation_summary="Test Anniversary Notification",
    tags=['Celebrations - Test'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['employee_id', 'years'],
        properties={
            'employee_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Employee ID'),
            'years': openapi.Schema(type=openapi.TYPE_INTEGER, description='Years of service')
        }
    ),
    responses={200: openapi.Response(description='Success')}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_anniversary_notification(request):
    """Test work anniversary notification for specific employee"""
    try:
        employee_id = request.data.get('employee_id')
        years = request.data.get('years')
        
        if not employee_id or not years:
            return Response({
                'error': 'employee_id and years are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return Response({
                'error': 'Employee not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if not employee.start_date:
            return Response({
                'error': 'Employee has no start date'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        success = celebration_notification_service.send_work_anniversary_notification(employee, years)
        
        if success:
            return Response({
                'success': True,
                'message': f'{years}-year anniversary notification sent for {employee.first_name} {employee.last_name}',
                'employee': {
                    'id': employee.id,
                    'name': f'{employee.first_name} {employee.last_name}',
                    'start_date': employee.start_date,
                    'years': years
                }
            })
        else:
            return Response({
                'success': False,
                'error': 'Failed to send notification'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"Error in test anniversary notification: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='post',
    operation_description="🧪 TEST: Send promotion notification",
    operation_summary="Test Promotion Notification",
    tags=['Celebrations - Test'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['employee_id', 'new_job_title'],
        properties={
            'employee_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Employee ID'),
            'new_job_title': openapi.Schema(type=openapi.TYPE_STRING, description='New job title')
        }
    ),
    responses={200: openapi.Response(description='Success')}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_position_change_notification(request):
    """Test promotion notification"""
    try:
        employee_id = request.data.get('employee_id')
        new_job_title = request.data.get('new_job_title')
        
        if not employee_id or not new_job_title:
            return Response({
                'error': 'employee_id and new_job_title are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return Response({
                'error': 'Employee not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        success = celebration_notification_service.send_promotion_notification(
            employee=employee,
            new_job_title=new_job_title
        )
        
        if success:
            return Response({
                'success': True,
                'message': f'Promotion notification sent for {employee.first_name} {employee.last_name}',
                'employee': {
                    'id': employee.id,
                    'name': f'{employee.first_name} {employee.last_name}',
                    'new_job_title': new_job_title
                }
            })
        else:
            return Response({
                'success': False,
                'error': 'Failed to send notification'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"Error in test promotion notification: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='post',
    operation_description="🧪 TEST: Run daily celebration check manually",
    operation_summary="Test Daily Celebration Check",
    tags=['Celebrations - Test'],
    responses={200: openapi.Response(description='Success')}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_daily_celebration_check(request):
    """Manually trigger daily celebration check"""
    try:
        results = celebration_notification_service.check_and_send_daily_celebrations()
        
        return Response({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error in test daily celebration check: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='post',
    operation_description="🧪 TEST: Send welcome email to specific employee",
    operation_summary="Test Welcome Email",
    tags=['Celebrations - Test'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['employee_id'],
        properties={
            'employee_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Employee ID')
        }
    ),
    responses={200: openapi.Response(description='Success')}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_welcome_email(request):
    """Test welcome email for specific employee"""
    try:
        employee_id = request.data.get('employee_id')
        
        if not employee_id:
            return Response({
                'error': 'employee_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return Response({
                'error': 'Employee not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        success = celebration_notification_service.send_welcome_email(employee)
        
        if success:
            return Response({
                'success': True,
                'message': f'Welcome email sent for {employee.first_name} {employee.last_name}',
                'employee': {
                    'id': employee.id,
                    'name': f'{employee.first_name} {employee.last_name}',
                    'position': str(employee.position_group) if employee.position_group else None,
                    'department': str(employee.department) if employee.department else None,
                    'start_date': employee.start_date
                }
            })
        else:
            return Response({
                'success': False,
                'error': 'Failed to send notification'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"Error in test welcome email: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)