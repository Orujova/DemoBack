# api/notification_views.py - COMPLETE VERSION WITH EMAIL DETAIL

import logging
import requests  # ✅ REQUIRED for email detail endpoint
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .notification_models import NotificationSettings, NotificationLog
from .notification_service import notification_service
from .models import UserGraphToken

logger = logging.getLogger(__name__)


def get_graph_token_from_request(request):
    """
    ✅ Extract Microsoft Graph token from request
    Tries multiple sources in priority order
    """
    # 1. Try custom header
    graph_token = request.META.get('HTTP_X_GRAPH_TOKEN')
    if graph_token:
        logger.info("✅ Graph token found in X-Graph-Token header")
        return graph_token
    
    # 2. Try database (stored during login)
    if request.user and request.user.is_authenticated:
        try:
            graph_token = UserGraphToken.get_valid_token(request.user)
            if graph_token:
                logger.info(f"✅ Graph token found in database for {request.user.username}")
                return graph_token
            else:
                logger.warning(f"⚠️ Graph token in database is expired for {request.user.username}")
        except Exception as e:
            logger.error(f"❌ Error retrieving Graph token from database: {e}")
    
    logger.warning("❌ No valid Graph token found")
    return None


@swagger_auto_schema(
    method='get',
    operation_description="Get emails from Outlook with sent/received separation",
    operation_summary="Get Outlook Emails (Sent/Received)",
    tags=['Notifications'],
    manual_parameters=[
        openapi.Parameter(
            'module',
            openapi.IN_QUERY,
            type=openapi.TYPE_STRING,
            enum=['business_trip', 'vacation', 'timeoff', 'handover', 'company_news', 'all'],
            required=False,
            default='all',
            description='Filter by module'
        ),
        openapi.Parameter(
            'email_type',
            openapi.IN_QUERY,
            type=openapi.TYPE_STRING,
            enum=['received', 'sent', 'all'],
            required=False,
            default='all',
            description='📬 Email type: received, sent, or all'
        ),
        openapi.Parameter(
            'top',
            openapi.IN_QUERY,
            type=openapi.TYPE_INTEGER,
            required=False,
            default=50,
            description='Number of emails per type (max 50)'
        )
    ],
    responses={200: openapi.Response(description='Outlook emails with sent/received separation')}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_outlook_emails(request):
    try:
        # Get parameters
        module = request.GET.get('module', 'all')
        email_type = request.GET.get('email_type', 'all')
        top = int(request.GET.get('top', 50))
        
        # Get Graph token
        graph_token = get_graph_token_from_request(request)
        
        if not graph_token:
            logger.warning(f"No Graph token for user {request.user.username}")
            return Response({
                'error': 'Microsoft Graph token not available',
                'message': 'Please login again to refresh your Graph token',
                'received_emails': [],
                'sent_emails': [],
                'all_emails': [],
                'counts': {'received': 0, 'sent': 0, 'total': 0},
                'graph_token_status': 'missing'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Get settings
        settings = NotificationSettings.get_active()
        
        # Prepare result structure
        result = {
            'success': True,
            'module_filter': module,
            'email_type_filter': email_type,
            'received_emails': [],
            'sent_emails': [],
            'all_emails': [],
            'counts': {
                'received': 0,
                'sent': 0,
                'total': 0
            },
            'graph_token_status': 'valid'
        }
        
        # Determine subject filter based on module
        subject_filters = []
        if module == 'handover':
            subject_filters = [getattr(settings, 'handover_subject_prefix', '[HANDOVER]')]
        elif module == 'business_trip':
            subject_filters = [settings.business_trip_subject_prefix]
        elif module == 'vacation':
            subject_filters = [settings.vacation_subject_prefix]
        elif module == 'timeoff': 
            subject_filters = [getattr(settings, 'timeoff_subject_prefix', '[TIME OFF]')]
        elif module == 'company_news':
            subject_filters = [settings.company_news_subject_prefix]
        else:  # all
            subject_filters = [
                settings.business_trip_subject_prefix,
                settings.vacation_subject_prefix,
                getattr(settings, 'timeoff_subject_prefix', '[TIME OFF]'),
                getattr(settings, 'handover_subject_prefix', '[HANDOVER]'),
                settings.company_news_subject_prefix
            ]
        
        # Fetch emails for each subject filter
        for subject_filter in subject_filters:
            emails_by_type = notification_service.get_all_emails_by_type(
                access_token=graph_token,
                subject_filter=subject_filter,
                top=top,
                email_type=email_type
            )
            
            # Accumulate results
            result['received_emails'].extend(emails_by_type['received'])
            result['sent_emails'].extend(emails_by_type['sent'])
        
        # Sort received emails by date
        result['received_emails'].sort(
            key=lambda x: x.get('receivedDateTime', ''), 
            reverse=True
        )
        result['received_emails'] = result['received_emails'][:top]
        
        # Sort sent emails by date
        result['sent_emails'].sort(
            key=lambda x: x.get('sentDateTime', ''), 
            reverse=True
        )
        result['sent_emails'] = result['sent_emails'][:top]
        
        # Combine all emails based on email_type filter
        if email_type == 'all':
            all_combined = result['received_emails'] + result['sent_emails']
            all_combined.sort(
                key=lambda x: x.get('receivedDateTime') or x.get('sentDateTime', ''), 
                reverse=True
            )
            result['all_emails'] = all_combined[:top]
        elif email_type == 'received':
            result['all_emails'] = result['received_emails']
        elif email_type == 'sent':
            result['all_emails'] = result['sent_emails']
        
        # Format emails with module tags
        result['received_emails'] = [
            format_email(email, settings, 'RECEIVED') 
            for email in result['received_emails']
        ]
        
        result['sent_emails'] = [
            format_email(email, settings, 'SENT') 
            for email in result['sent_emails']
        ]
        
        result['all_emails'] = [
            format_email(email, settings, email.get('email_type', 'RECEIVED')) 
            for email in result['all_emails']
        ]
        
        # Update counts
        result['counts'] = {
            'received': len(result['received_emails']),
            'sent': len(result['sent_emails']),
            'total': len(result['all_emails'])
        }
        
        return Response(result)
        
    except Exception as e:
        logger.error(f"Error getting Outlook emails: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        return Response({
            'error': str(e),
            'received_emails': [],
            'sent_emails': [],
            'all_emails': [],
            'counts': {'received': 0, 'sent': 0, 'total': 0},
            'graph_token_status': 'error'
        }, status=status.HTTP_400_BAD_REQUEST)


def format_email(email, settings, email_type):
    """Format email with module detection - HANDOVER SUPPORT"""
    subject = email.get('subject', '')
    
    # Determine module from subject
    email_module = 'unknown'
    if settings.business_trip_subject_prefix in subject:
        email_module = 'business_trip'
    elif settings.vacation_subject_prefix in subject:
        email_module = 'vacation'
    elif getattr(settings, 'timeoff_subject_prefix', '[TIME OFF]') in subject:
        email_module = 'timeoff'
    elif getattr(settings, 'handover_subject_prefix', '[HANDOVER]') in subject:
        email_module = 'handover'
    elif settings.company_news_subject_prefix in subject:
        email_module = 'company_news'
    
    # Get sender/recipient info based on type
    if email_type == 'SENT':
        to_recipients = email.get('toRecipients', [])
        primary_recipient = to_recipients[0] if to_recipients else {}
        contact_email = primary_recipient.get('emailAddress', {}).get('address')
        contact_name = primary_recipient.get('emailAddress', {}).get('name')
    else:
        from_info = email.get('from', {}).get('emailAddress', {})
        contact_email = from_info.get('address')
        contact_name = from_info.get('name')
    
    return {
        'id': email.get('id'),
        'subject': subject,
        'module': email_module,
        'email_type': email_type,
        'contact_email': contact_email,
        'contact_name': contact_name,
        'received_at': email.get('receivedDateTime'),
        'sent_at': email.get('sentDateTime'),
        'is_read': email.get('isRead'),
        'has_attachments': email.get('hasAttachments', False),
        'importance': email.get('importance'),
        'preview': email.get('bodyPreview', '')[:200]
    }


@swagger_auto_schema(
    methods=['get'],
    operation_description="Get full email details by ID",
    operation_summary="Get Email Detail",
    tags=['Notifications'],
    responses={
        200: openapi.Response(description='Email details with full body'),
        404: openapi.Response(description='Email not found')
    }
)
@swagger_auto_schema(
    methods=['delete'],
    operation_description="Delete email (move to Deleted Items)",
    operation_summary="Delete Email",
    tags=['Notifications'],
    responses={
        200: openapi.Response(description='Email deleted successfully'),
        400: openapi.Response(description='Error deleting email')
    }
)
@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def get_email_detail(request, message_id):
    """Get full email details OR delete email"""
    
    if request.method == 'DELETE':
        return delete_email_handler(request, message_id)
    
    # GET method
    try:
        # Get Graph token
        graph_token = get_graph_token_from_request(request)
        
        if not graph_token:
            return Response({
                'error': 'Microsoft Graph token not available'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        headers = {
            "Authorization": f"Bearer {graph_token}",
            "Content-Type": "application/json"
        }
        
        # Fetch full email details
        response = requests.get(
            f"https://graph.microsoft.com/v1.0/me/messages/{message_id}",
            headers=headers,
            params={
                '$select': 'id,subject,from,toRecipients,ccRecipients,receivedDateTime,sentDateTime,isRead,hasAttachments,importance,body,bodyPreview,attachments'
            },
            timeout=30
        )
        
        if response.status_code == 200:
            email_data = response.json()
            
            # Get settings for module detection
            settings = NotificationSettings.get_active()
            
            # Determine module from subject
            subject = email_data.get('subject', '')
            email_module = 'unknown'
            
            if settings.business_trip_subject_prefix in subject:
                email_module = 'business_trip'
            elif settings.vacation_subject_prefix in subject:
                email_module = 'vacation'
            elif getattr(settings, 'timeoff_subject_prefix', '[TIME OFF]') in subject:
                email_module = 'timeoff'
            elif getattr(settings, 'handover_subject_prefix', '[HANDOVER]') in subject:
                email_module = 'handover'
            elif settings.company_news_subject_prefix in subject:
                email_module = 'company_news'
            
            # Format response
            formatted_email = {
                'id': email_data.get('id'),
                'subject': email_data.get('subject'),
                'module': email_module,
                'from': {
                    'name': email_data.get('from', {}).get('emailAddress', {}).get('name'),
                    'email': email_data.get('from', {}).get('emailAddress', {}).get('address')
                },
                'to_recipients': [
                    {
                        'name': r.get('emailAddress', {}).get('name'),
                        'email': r.get('emailAddress', {}).get('address')
                    }
                    for r in email_data.get('toRecipients', [])
                ],
                'cc_recipients': [
                    {
                        'name': r.get('emailAddress', {}).get('name'),
                        'email': r.get('emailAddress', {}).get('address')
                    }
                    for r in email_data.get('ccRecipients', [])
                ],
                'received_at': email_data.get('receivedDateTime'),
                'sent_at': email_data.get('sentDateTime'),
                'is_read': email_data.get('isRead'),
                'has_attachments': email_data.get('hasAttachments', False),
                'importance': email_data.get('importance'),
                'body_html': email_data.get('body', {}).get('content') if email_data.get('body', {}).get('contentType') == 'html' else None,
                'body_text': email_data.get('body', {}).get('content') if email_data.get('body', {}).get('contentType') == 'text' else None,
                'preview': email_data.get('bodyPreview', ''),
                'attachments': [
                    {
                        'id': att.get('id'),
                        'name': att.get('name'),
                        'size': att.get('size'),
                        'content_type': att.get('contentType'),
                        'is_inline': att.get('isInline', False)
                    }
                    for att in email_data.get('attachments', [])
                ] if email_data.get('hasAttachments') else []
            }
            
            return Response(formatted_email)
        
        elif response.status_code == 404:
            return Response({
                'error': 'Email not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        else:
            logger.error(f"Failed to get email detail: {response.status_code} - {response.text}")
            return Response({
                'error': f'Failed to fetch email: {response.status_code}'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error in get_email_detail: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


def delete_email_handler(request, message_id):
    """Delete email (move to Deleted Items folder) - Internal Handler"""
    try:
        # Get Graph token
        graph_token = get_graph_token_from_request(request)
        
        if not graph_token:
            return Response({
                'error': 'Microsoft Graph token not available'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        headers = {
            "Authorization": f"Bearer {graph_token}",
            "Content-Type": "application/json"
        }
        
        # Delete email (moves to Deleted Items)
        response = requests.delete(
            f"https://graph.microsoft.com/v1.0/me/messages/{message_id}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 204:
            logger.info(f"✅ Email {message_id} deleted successfully")
            return Response({
                'success': True,
                'message': 'Email deleted successfully'
            })
        else:
            logger.error(f"Failed to delete email: {response.status_code} - {response.text}")
            return Response({
                'error': f'Failed to delete email: {response.status_code}'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error in delete_email: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_description="Mark all emails as read by module and type",
    operation_summary="Mark All Emails as Read",
    tags=['Notifications'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['module'],
        properties={
            'module': openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=['business_trip', 'vacation', 'timeoff', 'handover', 'company_news', 'all'],
                description='Module filter'
            ),
            'email_type': openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=['received', 'sent', 'all'],
                default='all',
                description='Mark only received, sent, or all emails'
            )
        }
    ),
    responses={200: openapi.Response(description='Batch result')}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_emails_read(request):
    """Mark all emails as read filtered by module and type"""
    try:
        module = request.data.get('module', 'all')
        email_type = request.data.get('email_type', 'all')
        
        graph_token = get_graph_token_from_request(request)
        
        if not graph_token:
            return Response({
                'error': 'Microsoft Graph token not available'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        settings = NotificationSettings.get_active()
        
        # Collect unread email IDs
        unread_ids = []
        
        # Determine subject filters
        subject_filters = []
        if module in ['business_trip', 'all']:
            subject_filters.append(settings.business_trip_subject_prefix)
        if module in ['vacation', 'all']:
            subject_filters.append(settings.vacation_subject_prefix)
        if module in ['timeoff', 'all']:
            subject_filters.append(getattr(settings, 'timeoff_subject_prefix', '[TIME OFF]'))
        if module in ['handover', 'all']:
            subject_filters.append(getattr(settings, 'handover_subject_prefix', '[HANDOVER]'))
        if module in ['company_news', 'all']:
            subject_filters.append(settings.company_news_subject_prefix)
        
        # Collect unread emails
        for subject_filter in subject_filters:
            emails_by_type = notification_service.get_all_emails_by_type(
                access_token=graph_token,
                subject_filter=subject_filter,
                top=50,
                email_type=email_type
            )
            
            # Get unread IDs based on email_type filter
            if email_type in ['received', 'all']:
                unread_ids.extend([
                    email['id'] for email in emails_by_type['received']
                    if not email.get('isRead', False)
                ])
            
            if email_type in ['sent', 'all']:
                unread_ids.extend([
                    email['id'] for email in emails_by_type['sent']
                    if not email.get('isRead', False)
                ])
        
        if not unread_ids:
            return Response({
                'success': True,
                'message': f'No unread emails for module: {module}, type: {email_type}',
                'marked_count': 0,
                'module': module,
                'email_type': email_type
            })
        
        # Mark all as read
        results = notification_service.mark_multiple_emails_as_read(
            access_token=graph_token,
            message_ids=unread_ids
        )
        
        return Response({
            'success': True,
            'marked_count': results['success'],
            'failed_count': results['failed'],
            'total_unread': len(unread_ids),
            'module': module,
            'email_type': email_type
        })
        
    except Exception as e:
        logger.error(f"Error marking emails as read: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_description="Mark email as read",
    operation_summary="Mark Email as Read",
    tags=['Notifications'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['message_id'],
        properties={
            'message_id': openapi.Schema(type=openapi.TYPE_STRING, description='Email message ID')
        }
    ),
    responses={
        200: openapi.Response(description='Success'),
        400: openapi.Response(description='Error')
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_email_read(request):
    """Mark an email as read"""
    try:
        message_id = request.data.get('message_id')
        
        if not message_id:
            return Response(
                {'error': 'message_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get Graph token
        graph_token = get_graph_token_from_request(request)
        
        if not graph_token:
            return Response({
                'error': 'Microsoft Graph token not available',
                'message': 'Please login again'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Mark as read
        success = notification_service.mark_email_as_read(
            access_token=graph_token,
            message_id=message_id
        )
        
        if success:
            return Response({
                'success': True,
                'message': 'Email marked as read',
                'message_id': message_id
            })
        else:
            return Response({
                'error': 'Failed to mark email as read'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error in mark_email_read: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_description="Mark email as unread",
    operation_summary="Mark Email as Unread",
    tags=['Notifications'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['message_id'],
        properties={
            'message_id': openapi.Schema(type=openapi.TYPE_STRING, description='Email message ID')
        }
    ),
    responses={200: openapi.Response(description='Success')}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_email_unread(request):
    """Mark an email as unread"""
    try:
        message_id = request.data.get('message_id')
        
        if not message_id:
            return Response(
                {'error': 'message_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        graph_token = get_graph_token_from_request(request)
        
        if not graph_token:
            return Response({
                'error': 'Microsoft Graph token not available'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        success = notification_service.mark_email_as_unread(
            access_token=graph_token,
            message_id=message_id
        )
        
        if success:
            return Response({
                'success': True,
                'message': 'Email marked as unread',
                'message_id': message_id
            })
        else:
            return Response({
                'error': 'Failed to mark email as unread'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)