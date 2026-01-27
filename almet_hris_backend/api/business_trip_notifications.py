# api/business_trip_notifications.py


import logging
from .notification_service import notification_service
from .notification_models import NotificationSettings

logger = logging.getLogger(__name__)


class BusinessTripNotificationManager:
    """Manager for Business Trip related notifications"""
    
    def __init__(self):
        self.service = notification_service
        self._settings = None
    
    @property
    def settings(self):
        """Lazy load settings to avoid import-time database access"""
        if self._settings is None:
            try:
                self._settings = NotificationSettings.get_active()
            except Exception as e:
                logger.warning(f"Could not load notification settings: {e}")
                # Return default settings object
                from types import SimpleNamespace
                self._settings = SimpleNamespace(
                    business_trip_subject_prefix='[BUSINESS TRIP]'
                )
        return self._settings
    
    def _get_subject_prefix(self, request_id):
        """Generate subject prefix with request ID"""
        prefix = self.settings.business_trip_subject_prefix
        return f"{prefix} Request #{request_id}"
    
    def notify_request_created(self, trip_request, access_token=None):
        """
        Notify Line Manager when a new trip request is created
        
        Args:
            trip_request: BusinessTripRequest instance
            access_token: Microsoft Graph access token
        """
        try:
            line_manager = trip_request.line_manager
            if not line_manager or not line_manager.user or not line_manager.user.email:
                logger.warning(f"No line manager email for trip request {trip_request.request_id}")
                return False
            
            subject = f"{self._get_subject_prefix(trip_request.request_id)} - Pending Your Approval"
            
            body_html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #366092; color: white; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
                    .info-row {{ margin: 10px 0; }}
                    .label {{ font-weight: bold; color: #366092; }}
                    .button {{ 
                        display: inline-block; 
                        padding: 12px 24px; 
                        background-color: #366092; 
                        color: white; 
                        text-decoration: none; 
                        border-radius: 5px; 
                        margin: 20px 0;
                    }}
                    .footer {{ margin-top: 20px; font-size: 12px; color: #777; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>New Business Trip Request</h2>
                    </div>
                    <div class="content">
                        <p>Dear {line_manager.full_name},</p>
                        <p>A new business trip request has been submitted and requires your approval.</p>
                        
                        <div class="info-row">
                            <span class="label">Request ID:</span> {trip_request.request_id}
                        </div>
                        <div class="info-row">
                            <span class="label">Employee:</span> {trip_request.employee.full_name}
                        </div>
                        <div class="info-row">
                            <span class="label">Travel Type:</span> {trip_request.travel_type.name}
                        </div>
                        <div class="info-row">
                            <span class="label">Transport:</span> {trip_request.transport_type.name}
                        </div>
                        <div class="info-row">
                            <span class="label">Purpose:</span> {trip_request.purpose.name}
                        </div>
                        <div class="info-row">
                            <span class="label">Period:</span> {trip_request.start_date.strftime('%Y-%m-%d')} to {trip_request.end_date.strftime('%Y-%m-%d')}
                        </div>
                        <div class="info-row">
                            <span class="label">Duration:</span> {trip_request.number_of_days} days
                        </div>
                        {f'<div class="info-row"><span class="label">Comment:</span> {trip_request.comment}</div>' if trip_request.comment else ''}
                        
                        <center>
                            <a href="https://myalmet.com/business-trip" class="button">
                                Review Request
                            </a>
                        </center>
                        
                        <p style="margin-top: 20px; font-size: 14px; color: #666;">
                            Please review and approve/reject this request at your earliest convenience.
                        </p>
                    </div>
                    <div class="footer">
                        
                        <p>Please do not reply to this email</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return self.service.send_email(
                recipient_email=line_manager.user.email,
                subject=subject,
                body_html=body_html,
                access_token=access_token,
                related_model='BusinessTripRequest',
                related_object_id=trip_request.id,
                sent_by=trip_request.requester
            )
            
        except Exception as e:
            logger.error(f"Error sending request created notification: {e}")
            return False
    
    def notify_line_manager_approved(self, trip_request, access_token=None):
        """
        Notify Finance when Line Manager approves
        
        Args:
            trip_request: BusinessTripRequest instance
            access_token: Microsoft Graph access token
        """
        try:
            finance = trip_request.finance_approver
            if not finance or not finance.user or not finance.user.email:
                logger.warning(f"No finance approver email for trip request {trip_request.request_id}")
                return False
            
            subject = f"{self._get_subject_prefix(trip_request.request_id)} - Line Manager Approved - Pending Finance Approval"
            
            body_html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #366092; color: white; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
                    .info-row {{ margin: 10px 0; }}
                    .label {{ font-weight: bold; color: #366092; }}
                    .approved {{ color: #28a745; font-weight: bold; }}
                    .button {{ 
                        display: inline-block; 
                        padding: 12px 24px; 
                        background-color: #366092; 
                        color: white; 
                        text-decoration: none; 
                        border-radius: 5px; 
                        margin: 20px 0;
                    }}
                    .footer {{ margin-top: 20px; font-size: 12px; color: #777; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>Business Trip - Finance Approval Required</h2>
                    </div>
                    <div class="content">
                        <p>Dear {finance.full_name},</p>
                        <p class="approved">✓ Line Manager has approved this business trip request.</p>
                        <p>The request now requires your financial approval.</p>
                        
                        <div class="info-row">
                            <span class="label">Request ID:</span> {trip_request.request_id}
                        </div>
                        <div class="info-row">
                            <span class="label">Employee:</span> {trip_request.employee.full_name}
                        </div>
                        <div class="info-row">
                            <span class="label">Travel Type:</span> {trip_request.travel_type.name}
                        </div>
                        <div class="info-row">
                            <span class="label">Period:</span> {trip_request.start_date.strftime('%Y-%m-%d')} to {trip_request.end_date.strftime('%Y-%m-%d')}
                        </div>
                        <div class="info-row">
                            <span class="label">Duration:</span> {trip_request.number_of_days} days
                        </div>
                        <div class="info-row">
                            <span class="label">Approved by:</span> {trip_request.line_manager.full_name}
                        </div>
                        {f'<div class="info-row"><span class="label">Line Manager Comment:</span> {trip_request.line_manager_comment}</div>' if trip_request.line_manager_comment else ''}
                        
                        <center>
                            <a href="https://myalmet.com/business-trip" class="button">
                                Review & Approve Budget
                            </a>
                        </center>
                        
                        <p style="margin-top: 20px; font-size: 14px; color: #666;">
                            Please review the financial aspects and provide budget approval.
                        </p>
                    </div>
                    <div class="footer">
                        <p>This is an automated notification from Almet HRIS System</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return self.service.send_email(
                recipient_email=finance.user.email,
                subject=subject,
                body_html=body_html,
                access_token=access_token,
                related_model='BusinessTripRequest',
                related_object_id=trip_request.id,
                sent_by=trip_request.line_manager_approved_by
            )
            
        except Exception as e:
            logger.error(f"Error sending line manager approved notification: {e}")
            return False
    
    def notify_finance_approved(self, trip_request, access_token=None):
        """
        Notify HR when Finance approves
        
        Args:
            trip_request: BusinessTripRequest instance
            access_token: Microsoft Graph access token
        """
        try:
            hr = trip_request.hr_representative
            if not hr or not hr.user or not hr.user.email:
                logger.warning(f"No HR representative email for trip request {trip_request.request_id}")
                return False
            
            subject = f"{self._get_subject_prefix(trip_request.request_id)} - Finance Approved - Pending HR Processing"
            
            body_html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #366092; color: white; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
                    .info-row {{ margin: 10px 0; }}
                    .label {{ font-weight: bold; color: #366092; }}
                    .approved {{ color: #28a745; font-weight: bold; }}
                    .button {{ 
                        display: inline-block; 
                        padding: 12px 24px; 
                        background-color: #366092; 
                        color: white; 
                        text-decoration: none; 
                        border-radius: 5px; 
                        margin: 20px 0;
                    }}
                    .footer {{ margin-top: 20px; font-size: 12px; color: #777; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>Business Trip - HR Processing Required</h2>
                    </div>
                    <div class="content">
                        <p>Dear {hr.full_name},</p>
                        <p class="approved">✓ Line Manager and Finance have approved this business trip request.</p>
                        <p>The request now requires your final HR processing and approval.</p>
                        
                        <div class="info-row">
                            <span class="label">Request ID:</span> {trip_request.request_id}
                        </div>
                        <div class="info-row">
                            <span class="label">Employee:</span> {trip_request.employee.full_name}
                        </div>
                        <div class="info-row">
                            <span class="label">Department:</span> {trip_request.employee.department.name if trip_request.employee.department else 'N/A'}
                        </div>
                        <div class="info-row">
                            <span class="label">Travel Type:</span> {trip_request.travel_type.name}
                        </div>
                        <div class="info-row">
                            <span class="label">Period:</span> {trip_request.start_date.strftime('%Y-%m-%d')} to {trip_request.end_date.strftime('%Y-%m-%d')}
                        </div>
                        <div class="info-row">
                            <span class="label">Duration:</span> {trip_request.number_of_days} days
                        </div>
                        <div class="info-row">
                            <span class="label">Approved Budget:</span> {trip_request.finance_amount} AZN
                        </div>
                        {f'<div class="info-row"><span class="label">Finance Comment:</span> {trip_request.finance_comment}</div>' if trip_request.finance_comment else ''}
                        
                        <center>
                            <a href="https://myalmet.com/business-trip" class="button">
                                Process Request
                            </a>
                        </center>
                        
                        <p style="margin-top: 20px; font-size: 14px; color: #666;">
                            Please complete the HR processing and final approval.
                        </p>
                    </div>
                    <div class="footer">
                        <p>This is an automated notification from Almet HRIS System</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return self.service.send_email(
                recipient_email=hr.user.email,
                subject=subject,
                body_html=body_html,
                access_token=access_token,
                related_model='BusinessTripRequest',
                related_object_id=trip_request.id,
                sent_by=trip_request.finance_approved_by
            )
            
        except Exception as e:
            logger.error(f"Error sending finance approved notification: {e}")
            return False
    
    def notify_hr_approved(self, trip_request, access_token=None):
        """
        Notify Employee when HR approves (final approval)
        
        Args:
            trip_request: BusinessTripRequest instance
            access_token: Microsoft Graph access token
        """
        try:
            employee = trip_request.employee
            if not employee.user or not employee.user.email:
                logger.warning(f"No employee email for trip request {trip_request.request_id}")
                return False
            
            subject = f"{self._get_subject_prefix(trip_request.request_id)} - APPROVED ✓"
            
            body_html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #28a745; color: white; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
                    .info-row {{ margin: 10px 0; }}
                    .label {{ font-weight: bold; color: #366092; }}
                    .success-box {{ 
                        background-color: #d4edda; 
                        border: 1px solid #c3e6cb; 
                        padding: 15px; 
                        margin: 20px 0; 
                        border-radius: 5px;
                        color: #155724;
                        text-align: center;
                        font-size: 18px;
                        font-weight: bold;
                    }}
                    .button {{ 
                        display: inline-block; 
                        padding: 12px 24px; 
                        background-color: #28a745; 
                        color: white; 
                        text-decoration: none; 
                        border-radius: 5px; 
                        margin: 20px 0;
                    }}
                    .footer {{ margin-top: 20px; font-size: 12px; color: #777; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>✓ Business Trip Approved</h2>
                    </div>
                    <div class="content">
                        <p>Dear {employee.full_name},</p>
                        
                        <div class="success-box">
                            ✓ Your business trip request has been APPROVED!
                        </div>
                        
                        <p>All required approvals have been completed. Your trip details are as follows:</p>
                        
                        <div class="info-row">
                            <span class="label">Request ID:</span> {trip_request.request_id}
                        </div>
                        <div class="info-row">
                            <span class="label">Travel Type:</span> {trip_request.travel_type.name}
                        </div>
                        <div class="info-row">
                            <span class="label">Transport:</span> {trip_request.transport_type.name}
                        </div>
                        <div class="info-row">
                            <span class="label">Purpose:</span> {trip_request.purpose.name}
                        </div>
                        <div class="info-row">
                            <span class="label">Period:</span> {trip_request.start_date.strftime('%Y-%m-%d')} to {trip_request.end_date.strftime('%Y-%m-%d')}
                        </div>
                        <div class="info-row">
                            <span class="label">Duration:</span> {trip_request.number_of_days} days
                        </div>
                        <div class="info-row">
                            <span class="label">Approved Budget:</span> {trip_request.finance_amount} AZN
                        </div>
                        
                        <center>
                            <a href="https://myalmet.com/business-trip" class="button">
                                View Trip Details
                            </a>
                        </center>
                        
                       
                    </div>
                    <div class="footer">
                        <p>This is an automated notification from Almet HRIS System</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return self.service.send_email(
                recipient_email=employee.user.email,
                subject=subject,
                body_html=body_html,
                access_token=access_token,
                related_model='BusinessTripRequest',
                related_object_id=trip_request.id,
                sent_by=trip_request.hr_approved_by
            )
            
        except Exception as e:
            logger.error(f"Error sending HR approved notification: {e}")
            return False
    
    def notify_request_rejected(self, trip_request, access_token=None):
        """
        Notify Employee when request is rejected
        
        Args:
            trip_request: BusinessTripRequest instance
            access_token: Microsoft Graph access token
        """
        try:
            employee = trip_request.employee
            if not employee.user or not employee.user.email:
                logger.warning(f"No employee email for trip request {trip_request.request_id}")
                return False
            
            # Determine who rejected
            rejected_by_name = "Unknown"
            rejection_stage = "Unknown"
            
            if trip_request.status == 'REJECTED_LINE_MANAGER':
                rejected_by_name = trip_request.line_manager.full_name if trip_request.line_manager else "Line Manager"
                rejection_stage = "Line Manager Review"
            elif trip_request.status == 'REJECTED_FINANCE':
                rejected_by_name = trip_request.finance_approver.full_name if trip_request.finance_approver else "Finance"
                rejection_stage = "Finance Review"
            elif trip_request.status == 'REJECTED_HR':
                rejected_by_name = trip_request.hr_representative.full_name if trip_request.hr_representative else "HR"
                rejection_stage = "HR Review"
            
            subject = f"{self._get_subject_prefix(trip_request.request_id)} - REJECTED ✗"
            
            body_html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #dc3545; color: white; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
                    .info-row {{ margin: 10px 0; }}
                    .label {{ font-weight: bold; color: #366092; }}
                    .reject-box {{ 
                        background-color: #f8d7da; 
                        border: 1px solid #f5c6cb; 
                        padding: 15px; 
                        margin: 20px 0; 
                        border-radius: 5px;
                        color: #721c24;
                    }}
                    .button {{ 
                        display: inline-block; 
                        padding: 12px 24px; 
                        background-color: #366092; 
                        color: white; 
                        text-decoration: none; 
                        border-radius: 5px; 
                        margin: 20px 0;
                    }}
                    .footer {{ margin-top: 20px; font-size: 12px; color: #777; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>✗ Business Trip Request Rejected</h2>
                    </div>
                    <div class="content">
                        <p>Dear {employee.full_name},</p>
                        
                        <div class="reject-box">
                            <p style="margin: 0; font-weight: bold;">Your business trip request has been rejected.</p>
                        </div>
                        
                        <div class="info-row">
                            <span class="label">Request ID:</span> {trip_request.request_id}
                        </div>
                        <div class="info-row">
                            <span class="label">Rejected at:</span> {rejection_stage}
                        </div>
                        <div class="info-row">
                            <span class="label">Rejected by:</span> {rejected_by_name}
                        </div>
                        <div class="info-row">
                            <span class="label">Travel Type:</span> {trip_request.travel_type.name}
                        </div>
                        <div class="info-row">
                            <span class="label">Period:</span> {trip_request.start_date.strftime('%Y-%m-%d')} to {trip_request.end_date.strftime('%Y-%m-%d')}
                        </div>
                        
                        {f'''
                        <div class="reject-box" style="margin-top: 20px;">
                            <p style="margin: 0;"><span class="label">Reason for Rejection:</span></p>
                            <p style="margin: 10px 0 0 0;">{trip_request.rejection_reason}</p>
                        </div>
                        ''' if trip_request.rejection_reason else ''}
                        
                        <center>
                            <a href="https://www.myalmet.com/requests/business-trip/" class="button">
                                View Request Details
                            </a>
                        </center>
                        
                        <p style="margin-top: 20px; font-size: 14px; color: #666;">
                            If you have questions about this rejection, please contact {rejected_by_name} or your HR representative.
                        </p>
                    </div>
                    <div class="footer">
                        <p>This is an automated notification from Almet HRIS System</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return self.service.send_email(
                recipient_email=employee.user.email,
                subject=subject,
                body_html=body_html,
                access_token=access_token,
                related_model='BusinessTripRequest',
                related_object_id=trip_request.id,
                sent_by=trip_request.rejected_by
            )
            
        except Exception as e:
            logger.error(f"Error sending rejection notification: {e}")
            return False
    
    def notify_trip_cancelled(self, trip_request, access_token=None):
        """
        Notify all approvers when a trip is cancelled
        
        Args:
            trip_request: BusinessTripRequest instance
            access_token: Microsoft Graph access token
        """
        try:
            # Collect all relevant recipients
            recipients = []
            
            if trip_request.line_manager and trip_request.line_manager.user:
                recipients.append(trip_request.line_manager.user.email)
            
            if trip_request.finance_approver and trip_request.finance_approver.user:
                recipients.append(trip_request.finance_approver.user.email)
            
            if trip_request.hr_representative and trip_request.hr_representative.user:
                recipients.append(trip_request.hr_representative.user.email)
            
            if not recipients:
                logger.warning(f"No recipients found for cancelled trip {trip_request.request_id}")
                return False
            
            subject = f"{self._get_subject_prefix(trip_request.request_id)} - CANCELLED"
            
            body_html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #ffc107; color: #333; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
                    .info-row {{ margin: 10px 0; }}
                    .label {{ font-weight: bold; color: #366092; }}
                    .warning-box {{ 
                        background-color: #fff3cd; 
                        border: 1px solid #ffeaa7; 
                        padding: 15px; 
                        margin: 20px 0; 
                        border-radius: 5px;
                        color: #856404;
                        text-align: center;
                        font-weight: bold;
                    }}
                    .footer {{ margin-top: 20px; font-size: 12px; color: #777; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>Business Trip Cancelled</h2>
                    </div>
                    <div class="content">
                        <div class="warning-box">
                            A previously approved business trip has been cancelled
                        </div>
                        
                        <div class="info-row">
                            <span class="label">Request ID:</span> {trip_request.request_id}
                        </div>
                        <div class="info-row">
                            <span class="label">Employee:</span> {trip_request.employee.full_name}
                        </div>
                        <div class="info-row">
                            <span class="label">Travel Type:</span> {trip_request.travel_type.name}
                        </div>
                        <div class="info-row">
                            <span class="label">Period:</span> {trip_request.start_date.strftime('%Y-%m-%d')} to {trip_request.end_date.strftime('%Y-%m-%d')}
                        </div>
                        <div class="info-row">
                            <span class="label">Cancelled by:</span> {trip_request.cancelled_by.get_full_name() if trip_request.cancelled_by else 'System'}
                        </div>
                        <div class="info-row">
                            <span class="label">Cancelled at:</span> {trip_request.cancelled_at.strftime('%Y-%m-%d %H:%M') if trip_request.cancelled_at else 'N/A'}
                        </div>
                        
                        <p style="margin-top: 20px; font-size: 14px; color: #666;">
                            This is for your information. No further action is required.
                        </p>
                    </div>
                    <div class="footer">
                        <p>This is an automated notification from Almet HRIS System</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Send to all recipients
            results = self.service.send_bulk_emails(
                recipients=recipients,
                subject=subject,
                body_html=body_html,
                access_token=access_token,
                sent_by=trip_request.cancelled_by
            )
            
            return results['success'] > 0
            
        except Exception as e:
            logger.error(f"Error sending cancellation notification: {e}")
            return False


# Singleton instance
notification_manager = BusinessTripNotificationManager()