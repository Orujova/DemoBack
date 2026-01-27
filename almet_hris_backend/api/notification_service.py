# api/notification_service.py - UPDATED WITH SENT/RECEIVED SEPARATION

import logging
import requests
from django.conf import settings
from .notification_models import NotificationSettings, NotificationLog
from .token_helpers import extract_graph_token_from_request

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications via Microsoft Graph API"""
    
    def __init__(self):
        self.graph_endpoint = "https://graph.microsoft.com/v1.0"
        self._settings = None
        self._verified_mailboxes = {}  # Cache for verified mailboxes
    
    @property
    def settings(self):
        """Lazy load settings"""
        if self._settings is None:
            try:
                self._settings = NotificationSettings.get_active()
            except Exception as e:
                logger.warning(f"Could not load notification settings: {e}")
                from types import SimpleNamespace
                self._settings = SimpleNamespace(
                    enable_email_notifications=True,
                    business_trip_subject_prefix='[BUSINESS TRIP]',
                    vacation_subject_prefix='[VACATION]',
                    company_news_subject_prefix='[COMPANY NEWS]',
                    company_news_sender_email='myalmet@almettrading.com'
                )
        return self._settings
    
    def verify_shared_mailbox_access(self, shared_mailbox_email, access_token):
        """
        ✅ Verify if shared mailbox exists and is accessible
        
        Returns:
            tuple: (success: bool, error_message: str)
        """
        # Check cache first
        cache_key = f"{shared_mailbox_email}_{access_token[:20]}"
        if cache_key in self._verified_mailboxes:
            return self._verified_mailboxes[cache_key]
        
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
   
            
            response = requests.get(
                f"{self.graph_endpoint}/users/{shared_mailbox_email}",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                mailbox_info = response.json()
            
                result = (True, None)
                self._verified_mailboxes[cache_key] = result
                return result
            
            elif response.status_code == 404:
                error = f"❌ Mailbox '{shared_mailbox_email}' not found in Exchange"
                logger.error(error)
                logger.error(f"Response: {response.text}")
                result = (False, error)
                self._verified_mailboxes[cache_key] = result
                return result
            
            elif response.status_code == 403:
                error = f"❌ Access denied to mailbox '{shared_mailbox_email}'"
                logger.error(error)
                logger.error(f"Response: {response.text}")
                result = (False, error)
                self._verified_mailboxes[cache_key] = result
                return result
            
            else:
                error = f"❌ Unexpected response ({response.status_code}): {response.text}"
                logger.error(error)
                result = (False, error)
                return result
                
        except Exception as e:
            error = f"❌ Exception verifying mailbox: {str(e)}"
            logger.error(error)
            return (False, error)
    
    def send_email_from_shared_mailbox(self, shared_mailbox_email, recipient_email, 
                                     subject, body_html, body_text=None, 
                                     access_token=None, related_model=None, 
                                     related_object_id=None, sent_by=None, request=None):
        """
        📧 Send email from shared mailbox with verification and fallback
        
        Args:
            shared_mailbox_email: The shared mailbox email address
            recipient_email: Recipient's email
            subject: Email subject
            body_html: HTML body
            body_text: Plain text body (optional)
            access_token: Graph API token
            related_model: Related model name
            related_object_id: Related object ID
            sent_by: User who triggered the email
            request: Django request object
        
        Returns:
            bool: Success status
        """
        
        if not self.settings.enable_email_notifications:
           
            return False
        
        if not access_token:
            if request:
                access_token = extract_graph_token_from_request(request)
        
        if not access_token:
            logger.error("❌ Microsoft Graph token is required")
            return False
        
        # Create notification log
        notification_log = NotificationLog.objects.create(
            notification_type='EMAIL',
            recipient_email=recipient_email,
            subject=subject,
            body=body_html,
            related_model=related_model or '',
            related_object_id=str(related_object_id) if related_object_id else '',
            status='PENDING',
            sent_by=sent_by
        )
        
        try:
            # ✅ STEP 1: Verify shared mailbox access
            is_accessible, error_message = self.verify_shared_mailbox_access(
                shared_mailbox_email, 
                access_token
            )
            
            if not is_accessible:
        
                
                # FALLBACK: Send from user's mailbox with clear indication
                return self._send_from_user_mailbox_with_note(
                    recipient_email=recipient_email,
                    subject=subject,
                    body_html=body_html,
                    access_token=access_token,
                    shared_mailbox_email=shared_mailbox_email,
                    notification_log=notification_log
                )
            
            # ✅ STEP 2: Shared mailbox is accessible, send normally
            message = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML",
                        "content": body_html
                    },
                    "toRecipients": [
                        {
                            "emailAddress": {
                                "address": recipient_email
                            }
                        }
                    ],
                    "from": {
                        "emailAddress": {
                            "address": shared_mailbox_email
                        }
                    }
                },
                "saveToSentItems": "true"
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
       
            
            # Use shared mailbox endpoint
            response = requests.post(
                f"{self.graph_endpoint}/users/{shared_mailbox_email}/sendMail",
                headers=headers,
                json=message,
                timeout=30
            )
            
            if response.status_code == 202:
     
                notification_log.mark_as_sent()
                return True
            else:
                error_msg = f"Failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                
            
                return self._send_from_user_mailbox_with_note(
                    recipient_email=recipient_email,
                    subject=subject,
                    body_html=body_html,
                    access_token=access_token,
                    shared_mailbox_email=shared_mailbox_email,
                    notification_log=notification_log
                )
                
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error(error_msg)
            
          
            return self._send_from_user_mailbox_with_note(
                recipient_email=recipient_email,
                subject=subject,
                body_html=body_html,
                access_token=access_token,
                shared_mailbox_email=shared_mailbox_email,
                notification_log=notification_log
            )
    
    def _send_from_user_mailbox_with_note(self, recipient_email, subject, body_html, 
                                         access_token, shared_mailbox_email, notification_log):
        """
        🔄 FALLBACK: Send from user's own mailbox with note about intended sender
        """
        try:
            # Add note to email body
            fallback_note = f"""
            <div style="background-color: #fff3cd; border: 1px solid #ffc107; padding: 15px; margin-bottom: 20px; border-radius: 5px;">
                <p style="margin: 0; color: #856404;">
                    <strong>⚠️ Note:</strong> This email was intended to be sent from <strong>{shared_mailbox_email}</strong> 
                    but is being sent from the user's mailbox due to access limitations.
                </p>
            </div>
            """
            
            modified_body = fallback_note + body_html
            
            message = {
                "message": {
                    "subject": f"{subject}",
                    "body": {
                        "contentType": "HTML",
                        "content": modified_body
                    },
                    "toRecipients": [
                        {
                            "emailAddress": {
                                "address": recipient_email
                            }
                        }
                    ]
                },
                "saveToSentItems": "true"
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
      
            
            response = requests.post(
                f"{self.graph_endpoint}/me/sendMail",
                headers=headers,
                json=message,
                timeout=30
            )
            
            if response.status_code == 202:

                notification_log.mark_as_sent()
                return True
            else:
                error_msg = f"Fallback failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                notification_log.mark_as_failed(error_msg)
                return False
                
        except Exception as e:
            error_msg = f"Fallback error: {str(e)}"
            logger.error(error_msg)
            notification_log.mark_as_failed(error_msg)
            return False
    def get_received_emails(self, access_token, subject_filter, top=50):
        """
        📥 RECEIVED EMAILS - Gələn mailləri gətir
        
        Args:
            access_token: Microsoft Graph access token
            subject_filter: Subject text to filter by
            top: Number of emails to retrieve
        
        Returns:
            list: List of received email objects
        """
        return self._get_emails_from_folder(
            access_token=access_token,
            folder_endpoint="/me/messages",  # Default inbox
            subject_filter=subject_filter,
            top=top,
            email_type="RECEIVED"
        )
    
    def get_sent_emails(self, access_token, subject_filter, top=50):
        """
        📤 SENT EMAILS - Göndərilən mailləri gətir
        
        Args:
            access_token: Microsoft Graph access token
            subject_filter: Subject text to filter by
            top: Number of emails to retrieve
        
        Returns:
            list: List of sent email objects
        """
        return self._get_emails_from_folder(
            access_token=access_token,
            folder_endpoint="/me/mailFolders/sentitems/messages",  # Sent items folder
            subject_filter=subject_filter,
            top=top,
            email_type="SENT"
        )
    
    def _get_emails_from_folder(self, access_token, folder_endpoint, subject_filter, top=50, email_type="RECEIVED"):
        """
        Internal method to get emails from specific folder
        
        Args:
            access_token: Microsoft Graph access token
            folder_endpoint: Graph API endpoint for folder
            subject_filter: Subject filter
            top: Number of emails
            email_type: "RECEIVED" or "SENT"
        
        Returns:
            list: Email objects with type tag
        """
        try:
            escaped_filter = subject_filter.replace("'", "''")
            filter_query = f"contains(subject, '{escaped_filter}')"
            
            params = {
                '$filter': filter_query,
                '$top': min(top, 50),
                '$orderby': 'receivedDateTime desc',
                '$select': 'id,subject,from,toRecipients,receivedDateTime,sentDateTime,isRead,hasAttachments,importance,bodyPreview'
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
          
            
            response = requests.get(
                f"{self.graph_endpoint}{folder_endpoint}",
                headers=headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                emails = data.get('value', [])
                
                # Add email_type tag to each email
                for email in emails:
                    email['email_type'] = email_type
                
          
                return emails
            
            elif response.status_code == 400:
               
                return self._get_emails_client_side_filter(
                    access_token, folder_endpoint, subject_filter, top, email_type
                )
            else:
                logger.error(f"Failed to get {email_type} emails: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting {email_type} emails: {str(e)}")
            return []
    
    def _get_emails_client_side_filter(self, access_token, folder_endpoint, subject_filter, top=50, email_type="RECEIVED"):
        """
        Fallback: Client-side filtering
        """
        try:
            params = {
                '$top': min(top * 3, 100),
                '$orderby': 'receivedDateTime desc',
                '$select': 'id,subject,from,toRecipients,receivedDateTime,sentDateTime,isRead,hasAttachments,importance,bodyPreview'
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{self.graph_endpoint}{folder_endpoint}",
                headers=headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                all_emails = data.get('value', [])
                
                subject_filter_lower = subject_filter.lower()
                filtered_emails = [
                    email for email in all_emails 
                    if subject_filter_lower in email.get('subject', '').lower()
                ]
                
                # Add email_type tag
                for email in filtered_emails:
                    email['email_type'] = email_type
                
                filtered_emails = filtered_emails[:top]
                
              
                return filtered_emails
            
            return []
                
        except Exception as e:
            logger.error(f"Client-side filter failed: {str(e)}")
            return []
    
    def get_all_emails_by_type(self, access_token, subject_filter, top=50, email_type="all"):
        """
        📬 COMBINED - Həm gələn həm də göndərilən mailləri gətir
        
        Args:
            access_token: Microsoft Graph access token
            subject_filter: Subject filter
            top: Number of emails per type
            email_type: "received", "sent", or "all"
        
        Returns:
            dict: {"received": [...], "sent": [...], "all": [...]}
        """
        result = {
            "received": [],
            "sent": [],
            "all": []
        }
        
        try:
            if email_type in ["received", "all"]:
                result["received"] = self.get_received_emails(access_token, subject_filter, top)
            
            if email_type in ["sent", "all"]:
                result["sent"] = self.get_sent_emails(access_token, subject_filter, top)
            
            if email_type == "all":
                # Combine and sort by date
                all_emails = result["received"] + result["sent"]
                all_emails.sort(key=lambda x: x.get('receivedDateTime', ''), reverse=True)
                result["all"] = all_emails[:top]
            
            return result
            
        except Exception as e:
            logger.error(f"Error in get_all_emails_by_type: {str(e)}")
            return result
    
    # ==================== EXISTING METHODS ====================
    
    def send_email(self, recipient_email, subject, body_html, body_text=None, 
                   sender_email=None, access_token=None, related_model=None, 
                   related_object_id=None, sent_by=None, request=None):
        """Send email via Microsoft Graph API"""
        
        if not self.settings.enable_email_notifications:
     
            return False
        
        if not access_token:
            if request:
                access_token = extract_graph_token_from_request(request)
        
        if not access_token:
            logger.error("❌ Microsoft Graph token is required")
            return False
        
        notification_log = NotificationLog.objects.create(
            notification_type='EMAIL',
            recipient_email=recipient_email,
            subject=subject,
            body=body_html,
            related_model=related_model or '',
            related_object_id=str(related_object_id) if related_object_id else '',
            status='PENDING',
            sent_by=sent_by
        )
        
        try:
            message = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML",
                        "content": body_html
                    },
                    "toRecipients": [
                        {
                            "emailAddress": {
                                "address": recipient_email
                            }
                        }
                    ]
                },
                "saveToSentItems": "true"
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
        
            
            response = requests.post(
                f"{self.graph_endpoint}/me/sendMail",
                headers=headers,
                json=message,
                timeout=30
            )
            
            if response.status_code == 202:
        
                notification_log.mark_as_sent()
                return True
            else:
                error_msg = f"Failed: {response.status_code}"
                logger.error(error_msg)
                notification_log.mark_as_failed(error_msg)
                return False
                
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error(error_msg)
            notification_log.mark_as_failed(error_msg)
            return False
    
    def mark_email_as_read(self, access_token, message_id):
        """Mark email as read"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.patch(
                f"{self.graph_endpoint}/me/messages/{message_id}",
                headers=headers,
                json={"isRead": True},
                timeout=30
            )
            
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error marking email as read: {str(e)}")
            return False
    
    def mark_email_as_unread(self, access_token, message_id):
        """Mark email as unread"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.patch(
                f"{self.graph_endpoint}/me/messages/{message_id}",
                headers=headers,
                json={"isRead": False},
                timeout=30
            )
            
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error marking email as unread: {str(e)}")
            return False
    
    def mark_multiple_emails_as_read(self, access_token, message_ids):
        """Mark multiple emails as read"""
        results = {'success': 0, 'failed': 0, 'total': len(message_ids)}
        
        for message_id in message_ids:
            if self.mark_email_as_read(access_token, message_id):
                results['success'] += 1
            else:
                results['failed'] += 1
        
        return results
    
    
    
# Singleton instance
notification_service = NotificationService()