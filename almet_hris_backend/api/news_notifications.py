# api/news_notifications.py - UPDATED TO USE SYSTEM EMAIL SERVICE
"""
Company News Notification Manager
✅ Application Permissions ilə göndərir (user token lazım deyil)
"""

import logging
from django.utils import timezone
from .system_email_service import system_email_service
from .notification_models import NotificationSettings, NotificationLog


logger = logging.getLogger(__name__)


class NewsNotificationManager:
    """Manager for Company News related notifications"""
    
    def __init__(self):
        self.system_service = system_email_service
        self._settings = None
    
    @property
    def settings(self):
        """Lazy load settings"""
        if self._settings is None:
            try:
                self._settings = NotificationSettings.get_active()
            except Exception as e:
                from types import SimpleNamespace
                self._settings = SimpleNamespace(
                    enable_email_notifications=True,
                    company_news_sender_email='myalmet@almettrading.com',
                    company_news_subject_prefix='[COMPANY NEWS]'
                )
        return self._settings
    
    def send_news_notification(self, news, access_token=None, request=None):
        """Send email notifications for company news using system email service"""
        try:
            # Check if notifications are enabled
            if not news.notify_members:
                return {
                    'success': False,
                    'message': 'Notifications not enabled for this news',
                    'total_recipients': 0,
                    'success_count': 0,
                    'failed_count': 0
                }
            
            # Check if already sent
            if news.notification_sent:
                return {
                    'success': False,
                    'message': 'Notifications already sent',
                    'total_recipients': 0,
                    'success_count': 0,
                    'failed_count': 0
                }
            
            # Get recipient emails
            recipient_emails = news.get_recipient_emails()
            
            if not recipient_emails:
                logger.warning(f"News {news.id}: No recipients found")
                return {
                    'success': False,
                    'message': 'No recipients found in target groups',
                    'total_recipients': 0,
                    'success_count': 0,
                    'failed_count': 0
                }
            
            # Prepare email content
            subject = f"{self.settings.company_news_subject_prefix} {news.title}"
            
            # Get author name
            author_name = news.author_display_name or (
                news.author.get_full_name() if news.author else 'Company'
            )
            
            # Get image URL
            image_url = news.get_image_url()
            if image_url and request and not image_url.startswith('http'):
                image_url = request.build_absolute_uri(image_url)
            
            # Build HTML body
            body_html = self._build_email_html(
                news=news,
                author_name=author_name,
                image_url=image_url
            )
            
            # Get sender email - FORCE CORRECT EMAIL
            sender_email = self.settings.company_news_sender_email
            
            # ✅ FORCE USE CORRECT SENDER EMAIL
            if not sender_email or sender_email != 'myalmet@almettrading.com':
                sender_email = 'myalmet@almettrading.com'
                logger.info(f"Using default sender email: {sender_email}")
            
            # ✅ Send using SYSTEM EMAIL SERVICE (Application Permissions)
            bulk_result = self.system_service.send_bulk_emails_as_system(
                from_email=sender_email,
                recipients=recipient_emails,
                subject=subject,
                body_html=body_html
            )
            
            success_count = bulk_result['success_count']
            failed_count = bulk_result['failed_count']
            
            # Log each email in NotificationLog
            for result in bulk_result['results']:
                NotificationLog.objects.create(
                    notification_type='EMAIL',
                    recipient_email=result['recipient'],
                    subject=subject,
                    body=body_html,
                    related_model='CompanyNews',
                    related_object_id=str(news.id),
                    status='SENT' if result['success'] else 'FAILED',
                    error_message='' if result['success'] else result['message'],
                    sent_by=news.author,
                    sent_at=timezone.now() if result['success'] else None
                )
            
            # Update notification status
            if success_count > 0:
                news.notification_sent = True
                news.notification_sent_at = timezone.now()
                news.save(update_fields=['notification_sent', 'notification_sent_at'])
            
            return {
                'success': True,
                'total_recipients': len(recipient_emails),
                'success_count': success_count,
                'failed_count': failed_count,
                'sender_email': sender_email,
                'message': f'Notifications sent from {sender_email} (System) to {success_count} of {len(recipient_emails)} recipients'
            }
            
        except Exception as e:
            logger.error(f"Error sending news notifications: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'total_recipients': 0,
                'success_count': 0,
                'failed_count': 0
            }
    
    def _build_email_html(self, news, author_name, image_url):
        """Build HTML email body with Company News branding"""
        
        # Format tags
        tags_html = ''
        if news.tags:
            tags = news.get_tags_list()
            tags_html = '<p style="color: #6b7280; font-size: 11px; margin-top: 15px;"><strong>Tags:</strong> ' + ', '.join(tags) + '</p>'
        
        # Format image - SMALLER SIZE
        image_html = ''
        if image_url:
            image_html = f'<img src="{image_url}" style="max-width: 100%; max-height: 300px; object-fit: cover; border-radius: 8px; margin: 20px 0;" alt="{news.title}" />'
        
        # Get category name
        category_name = news.category.name if news.category else 'General'
        
        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #1f2937; margin: 0; padding: 0; background-color: #f3f4f6; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; }}
                .header {{ 
                    background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); 
                    color: black; 
                    padding: 25px 20px; 
                    text-align: center; 
                }}
                .header h1 {{ margin: 0; font-size: 22px; font-weight: bold; color: #000000; }}
                .header p {{ margin: 5px 0 0 0; font-size: 12px; opacity: 0.9; }}
                .category-badge {{ 
                    display: inline-block;
                    background-color: rgba(255, 255, 255, 0.2);
                    padding: 4px 12px;
                  
                    border-radius: 20px;
                    font-size: 11px;
                    margin-top: 8px;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                }}
                .content {{ padding: 20px; background-color: #f9fafb; }}
                .news-title {{ color: #1e3a8a; margin-top: 0; font-size: 20px; line-height: 1.3; font-weight: 600; }}
                .meta-info {{ 
                    color: #4b5563; 
                    font-size: 12px; 
                    margin-bottom: 15px; 
                    padding-bottom: 12px; 
                    border-bottom: 2px solid #e5e7eb; 
                }}
                .meta-item {{ display: inline-block; margin-right: 15px; }}
                .excerpt-box {{ 
                    background-color: white; 
                    padding: 15px; 
                    border-left: 4px solid #3b82f6; 
                    border-radius: 8px; 
                    margin: 15px 0; 
                }}
                .content-box {{ 
                    background-color: white; 
                    padding: 18px; 
                    border-radius: 8px; 
                    margin: 15px 0;
                    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                }}
                .image-box {{
                    width: 200px;
                    height: 2000px;
                }}    
                .content-text {{ 
                    font-size: 13px; 
                    line-height: 1.7; 
                    color: #1f2937; 
                    white-space: pre-line; 
                }}
                .footer {{ 
                    background-color: #1e3a8a; 
                    color: white;
                    padding: 18px; 
                    text-align: center; 
                    font-size: 11px; 
                }}
                .footer p {{ margin: 5px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📢 Company News</h1>

                    <div class="category-badge">{category_name}</div>
                </div>
                
                <div class="content">
                    <h2 class="news-title">{news.title}</h2>
                    
                    <div class="meta-info">
                        <span class="meta-item"><strong>📅 Published:</strong> {news.published_at.strftime('%B %d, %Y at %H:%M')}</span>
                        <span class="meta-item"><strong>✍️ By:</strong> {author_name}</span>
                    </div>
                    
                    <div class="image-box">
                        {image_html}
                    </div>
                    
                    <div class="excerpt-box">
                        <p style="font-size: 14px; font-weight: 500; line-height: 1.6; color: #1f2937; margin: 0;">
                            {news.excerpt}
                        </p>
                    </div>
                    
                    <div class="content-box">
                        <p class="content-text">{news.content}</p>
                    </div>
                    
                    {tags_html}
                </div>
                
                <div class="footer">
                    <p>✉️ This email was sent automatically from {self.settings.company_news_sender_email}</p>
                    <p style="margin-top: 10px; opacity: 0.8;">© 2025 Almet Trading. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """


# Singleton instance
news_notification_manager = NewsNotificationManager()