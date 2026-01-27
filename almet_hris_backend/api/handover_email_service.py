# api/handover_email_service.py
"""
Handover Email Notification Service
Handles all email notifications for handover system
"""

import logging
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .system_email_service import system_email_service
from .notification_models import NotificationSettings, NotificationLog

logger = logging.getLogger(__name__)


class HandoverEmailService:
    """Service for sending handover-related email notifications"""
    
    def __init__(self):
        self.settings = None
    
    def get_settings(self):
        """Lazy load notification settings"""
        if not self.settings:
            self.settings = NotificationSettings.get_active()
        return self.settings
    
    def send_handover_notification(self, handover, recipient_email, recipient_name, 
                                   notification_type, additional_data=None):

        settings = self.get_settings()
        
        if not settings.enable_email_notifications:
            logger.info("Email notifications are disabled")
            return False
        
        # Build email context
        context = {
            'handover': handover,
            'recipient_name': recipient_name,
            'notification_type': notification_type,
            'handover_url': f'https://www.myalmet.com/requests/handover-takeover/',
            'company_name': 'Almet Holding',
            **(additional_data or {})
        }
        
        # Determine email subject and template based on notification type
        subject_suffix, template_name = self._get_email_config(notification_type, handover)
        
        # Build full subject
        subject = f"{settings.handover_subject_prefix} {subject_suffix}"
        
        # Render HTML email
        try:
            html_content = render_to_string(
                f'emails/handover_{template_name}.html', 
                context
            )
        except Exception as e:
            logger.error(f"Failed to render email template: {e}")
            # Fallback to generic template
            html_content = self._get_fallback_email_html(context)
        
        # Send email using system email service
        try:
            # Handle both single email and list
            if isinstance(recipient_email, str):
                recipients = [recipient_email]
            else:
                recipients = recipient_email
            
            # Create notification log
            for email in recipients:
                NotificationLog.objects.create(
                    notification_type='EMAIL',
                    recipient_email=email,
                    subject=subject,
                    body=html_content,
                    related_model='HandoverRequest',
                    related_object_id=handover.request_id,
                    status='PENDING',
                    sent_by=handover.created_by
                )
            
            # Send email
            result = system_email_service.send_email_as_system(
                from_email=settings.handover_sender_email,
                to_email=recipients,
                subject=subject,
                body_html=html_content
            )
            
            if result['success']:
      
                
                # Update notification logs
                for email in recipients:
                    try:
                        log = NotificationLog.objects.filter(
                            recipient_email=email,
                            related_object_id=handover.request_id,
                            status='PENDING'
                        ).latest('created_at')
                        log.mark_as_sent(result.get('message_id'))
                    except NotificationLog.DoesNotExist:
                        pass
                
                return True
            else:
                logger.error(f"❌ Failed to send handover email: {result['message']}")
                
                # Mark as failed
                for email in recipients:
                    try:
                        log = NotificationLog.objects.filter(
                            recipient_email=email,
                            related_object_id=handover.request_id,
                            status='PENDING'
                        ).latest('created_at')
                        log.mark_as_failed(result['message'])
                    except NotificationLog.DoesNotExist:
                        pass
                
                return False
                
        except Exception as e:
            error_msg = f"Exception sending handover email: {str(e)}"
            logger.error(error_msg)
            return False
    
    def _get_email_config(self, notification_type, handover):
        """Get email subject and template name based on notification type"""
        
        configs = {
            'created': (
                f"New Handover Request - {handover.request_id}",
                'created'
            ),
            'ho_signature_needed': (
                f"Action Required: Sign Handover - {handover.request_id}",
                'signature_needed'
            ),
            'to_signature_needed': (
                f"Action Required: Sign Handover - {handover.request_id}",
                'signature_needed'
            ),
            'lm_approval_needed': (
                f"Action Required: Approve Handover - {handover.request_id}",
                'approval_needed'
            ),
            'approved': (
                f"Handover Approved - {handover.request_id}",
                'approved'
            ),
            'rejected': (
                f"Handover Rejected - {handover.request_id}",
                'rejected'
            ),
            'clarification_requested': (
                f"Clarification Requested - {handover.request_id}",
                'clarification_requested'
            ),
            'resubmitted': (
                f"Handover Resubmitted - {handover.request_id}",
                'resubmitted'
            ),
            'takeover_ready': (
                f"Ready for Takeover - {handover.request_id}",
                'takeover_ready'
            ),
            'taken_over': (
                f"Responsibilities Taken Over - {handover.request_id}",
                'taken_over'
            ),
            'taken_back': (
                f"Handover Completed - {handover.request_id}",
                'completed'
            ),
        }
        
        return configs.get(notification_type, (
            f"Handover Update - {handover.request_id}",
            'generic'
        ))
    
    def _get_fallback_email_html(self, context):
        handover = context['handover']
        recipient_name = context['recipient_name']
        action_required = context.get('action_required', None)
    
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    background-color: #f1f5f9;
                    font-family: Arial, Helvetica, sans-serif;
                    color: #0f172a;
                }}
                .container {{
                    max-width: 600px;
                    margin: 40px auto;
                    background: #ffffff;
                    border-radius: 10px;
                    overflow: hidden;
                    box-shadow: 0 10px 25px rgba(0,0,0,0.08);
                }}
                .header {{
                    background: #1e3a8a;
                    color: #ffffff;
                    padding: 24px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 22px;
                }}
                .content {{
                    padding: 30px;
                }}
                .content p {{
                    font-size: 14px;
                    line-height: 1.6;
                    margin: 0 0 16px;
                }}
                .info-box {{
                    background: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    padding: 16px;
                    margin: 20px 0;
                }}
                .info-row {{
                    font-size: 14px;
                    margin-bottom: 8px;
                }}
                .info-row strong {{
                    display: inline-block;
                    width: 140px;
                    color: #334155;
                }}
                .action {{
                    background: #eff6ff;
                    border-left: 4px solid #2563eb;
                    padding: 14px;
                    margin: 20px 0;
                    font-size: 14px;
                }}
                .button-wrapper {{
                    text-align: center;
                    margin: 30px 0;
                }}
                .button {{
                  
                    color: #00000;
                    padding: 14px 34px;
                    text-decoration: none;
                    font-size: 14px;
                    border-radius: 8px;
                    display: inline-block;
                }}
                .footer {{
                    background: #f8fafc;
                    text-align: center;
                    padding: 20px;
                    font-size: 12px;
                    color: #64748b;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Handover Notification</h1>
                </div>
    
                <div class="content">
                    <p>Dear <strong>{recipient_name}</strong>,</p>
    
                    <p>You have a new update regarding the following handover request:</p>
    
                    <div class="info-box">
                        <div class="info-row">
                            <strong>Request ID:</strong> {handover.request_id}
                        </div>
                        <div class="info-row">
                            <strong>Handing Over:</strong> {handover.handing_over_employee.full_name}
                        </div>
                        <div class="info-row">
                            <strong>Taking Over:</strong> {handover.taking_over_employee.full_name}
                        </div>
                        <div class="info-row">
                            <strong>Status:</strong> {handover.get_status_display()}
                        </div>
                    </div>
    
                    {f'''
                    <div class="action">
                        <strong>Action required:</strong><br/>
                        {action_required}
                    </div>
                    ''' if action_required else ''}
    
                    <div class="button-wrapper">
                        <a href="{context['handover_url']}" class="button">
                            View Handover
                        </a>
                    </div>
    
                    
                </div>
    
                <div class="footer">
                    <p>This is an automated message from MyAlmet Handover System</p>
                    <p>© 2026 Almet Holding</p>
                </div>
            </div>
        </body>
        </html>
        """
    
        # Helper methods for specific notifications
        
    def notify_handover_created(self, handover):
        """Notify HO employee that handover was created"""
        if handover.handing_over_employee.email:
            return self.send_handover_notification(
                handover=handover,
                recipient_email=handover.handing_over_employee.email,
                recipient_name=handover.handing_over_employee.full_name,
                notification_type='created',
                additional_data={
                    'action_required': 'Please review and sign the handover request'
                }
            )
        return False
    
    def notify_ho_signature_needed(self, handover):
        """Notify HO employee signature is needed"""
        if handover.handing_over_employee.email:
            return self.send_handover_notification(
                handover=handover,
                recipient_email=handover.handing_over_employee.email,
                recipient_name=handover.handing_over_employee.full_name,
                notification_type='ho_signature_needed',
                additional_data={
                    'action_required': 'Your signature is required to proceed'
                }
            )
        return False
    
    def notify_to_signature_needed(self, handover):
        """Notify TO employee signature is needed"""
        
       
        
        if not handover.taking_over_employee.email:
            logger.error(f"❌ TO employee has no email address!")
            return False
        
        result = self.send_handover_notification(
            handover=handover,
            recipient_email=handover.taking_over_employee.email,
            recipient_name=handover.taking_over_employee.full_name,
            notification_type='to_signature_needed',
            additional_data={
                'action_required': 'Your signature is required to proceed'
            }
        )
        
       
        return result
    
    def notify_lm_approval_needed(self, handover):
        """Notify Line Manager approval is needed"""
        if handover.line_manager and handover.line_manager.email:
            return self.send_handover_notification(
                handover=handover,
                recipient_email=handover.line_manager.email,
                recipient_name=handover.line_manager.full_name,
                notification_type='lm_approval_needed',
                additional_data={
                    'action_required': 'Your approval is required'
                }
            )
        return False
    
    def notify_approved(self, handover):
        """Notify both employees that handover is approved"""
        recipients = []
        names = []
        
        if handover.handing_over_employee.email:
            recipients.append(handover.handing_over_employee.email)
            names.append(handover.handing_over_employee.full_name)
        
        if handover.taking_over_employee.email:
            recipients.append(handover.taking_over_employee.email)
            names.append(handover.taking_over_employee.full_name)
        
        if recipients:
            return self.send_handover_notification(
                handover=handover,
                recipient_email=recipients,
                recipient_name=", ".join(names),
                notification_type='approved',
                additional_data={
                    'approver': handover.line_manager.full_name if handover.line_manager else 'Line Manager',
                    'comment': handover.lm_comment
                }
            )
        return False
    
    def notify_rejected(self, handover):
        """Notify both employees that handover is rejected"""
        recipients = []
        names = []
        
        if handover.handing_over_employee.email:
            recipients.append(handover.handing_over_employee.email)
            names.append(handover.handing_over_employee.full_name)
        
        if handover.taking_over_employee.email:
            recipients.append(handover.taking_over_employee.email)
            names.append(handover.taking_over_employee.full_name)
        
        if recipients:
            return self.send_handover_notification(
                handover=handover,
                recipient_email=recipients,
                recipient_name=", ".join(names),
                notification_type='rejected',
                additional_data={
                    'rejector': handover.line_manager.full_name if handover.line_manager else 'Line Manager',
                    'reason': handover.rejection_reason
                }
            )
        return False
    
    def notify_clarification_requested(self, handover):
        """Notify HO employee that clarification is requested"""
        if handover.handing_over_employee.email:
            return self.send_handover_notification(
                handover=handover,
                recipient_email=handover.handing_over_employee.email,
                recipient_name=handover.handing_over_employee.full_name,
                notification_type='clarification_requested',
                additional_data={
                    'clarification_comment': handover.lm_clarification_comment,
                    'action_required': 'Please provide clarification and resubmit'
                }
            )
        return False
    
    def notify_resubmitted(self, handover):
        """Notify LM that handover is resubmitted"""
        if handover.line_manager and handover.line_manager.email:
            return self.send_handover_notification(
                handover=handover,
                recipient_email=handover.line_manager.email,
                recipient_name=handover.line_manager.full_name,
                notification_type='resubmitted',
                additional_data={
                    'action_required': 'Please review the resubmitted handover'
                }
            )
        return False
    
    def notify_takeover_ready(self, handover):
        """Notify TO employee that handover is ready for takeover"""
        if handover.taking_over_employee.email:
            return self.send_handover_notification(
                handover=handover,
                recipient_email=handover.taking_over_employee.email,
                recipient_name=handover.taking_over_employee.full_name,
                notification_type='takeover_ready',
                additional_data={
                    'action_required': 'Handover is approved and ready for you to take over'
                }
            )
        return False
    
    def notify_taken_over(self, handover):
        """Notify HO employee that responsibilities are taken over"""
        if handover.handing_over_employee.email:
            return self.send_handover_notification(
                handover=handover,
                recipient_email=handover.handing_over_employee.email,
                recipient_name=handover.handing_over_employee.full_name,
                notification_type='taken_over',
                additional_data={
                    'action_required': 'Please confirm takeback when you return'
                }
            )
        return False
    
    def notify_completed(self, handover):
        """Notify all parties that handover is completed"""
        recipients = []
        names = []
        
        if handover.handing_over_employee.email:
            recipients.append(handover.handing_over_employee.email)
            names.append(handover.handing_over_employee.full_name)
        
        if handover.taking_over_employee.email:
            recipients.append(handover.taking_over_employee.email)
            names.append(handover.taking_over_employee.full_name)
        
        if handover.line_manager and handover.line_manager.email:
            recipients.append(handover.line_manager.email)
            names.append(handover.line_manager.full_name)
        
        if recipients:
            return self.send_handover_notification(
                handover=handover,
                recipient_email=recipients,
                recipient_name=", ".join(names),
                notification_type='taken_back',
                additional_data={
                    'message': 'Handover process has been completed successfully'
                }
            )
        return False


# Singleton instance
handover_email_service = HandoverEmailService()