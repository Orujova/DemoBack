# api/celebration_notification_service.py

import logging
from datetime import date
from .models import Employee
from .system_email_service import system_email_service

logger = logging.getLogger(__name__)


class CelebrationNotificationService:

    
    # 🚫 Business functions that should NOT receive celebration emails
    EXCLUDED_BUSINESS_FUNCTIONS = [
        'ASPM',  # Add other business functions here as needed
        # 'LLC',
        # 'UK',
    ]
    
    def __init__(self):
        # self.system_sender = 'hr@almettrading.com'
        self.system_sender = 'n.orujova@almettrading.com'
        
        # 📧 Distribution lists for all staff
        self.all_staff_emails = [
            # 'alltradeuk@almettrading.co.uk',    # UK
            # 'alltrade@almettrading.com',       
            # 'allholding@almettrading.com',  
             'n.orujova@almettrading.com',  # Test
            # 'n.garibova@almettrading.com',
        
        ]
    
    def should_send_email(self, employee):
     
        # Check if employee has business_function field
        if not hasattr(employee, 'business_function'):
            return True  # Default: send email if field doesn't exist
        
        business_function = getattr(employee, 'business_function', None)
        
        # If no business function set, send email
        if not business_function:
            return True
        
        # Convert to string and check against excluded list
        business_function_str = str(business_function).strip().upper()
        
        excluded = any(
            excluded_bf.upper() in business_function_str 
            for excluded_bf in self.EXCLUDED_BUSINESS_FUNCTIONS
        )
        
        if excluded:
            logger.info(f"🚫 Email skipped for {employee.first_name} {employee.last_name} - Business function: {business_function}")
            return False
        
        return True
    
    def send_birthday_notification(self, employee):
  
        try:
            if not employee.date_of_birth:
                logger.warning(f"No birth date for {employee.first_name} {employee.last_name}")
                return False
            
            # ✅ CHECK: Should we send email for this employee?
            if not self.should_send_email(employee):
      
                return True  # Return True because celebration is still valid
            
            # Email subject
            subject = f"🎂 Happy Birthday {employee.first_name} {employee.last_name}!"
            
            # Email body (Outlook-friendly / table-based)
            body_html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Happy Birthday</title>
</head>

<body style="margin:0; padding:0; background:#EEF2F7;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#EEF2F7; padding:26px 0;">
    <tr>
      <td align="center">

        <!-- Outer wrapper -->
        <table role="presentation" width="800" cellspacing="0" cellpadding="0"
               style="width:800px; max-width:800px;">

          <!-- Card -->
          <tr>
            <td style="background:#FFFFFF; border-radius:18px; overflow:hidden; box-shadow:0 10px 26px rgba(16,24,40,0.10);">

              <!-- Slim header bar -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td style="background:#30539b; height:8px; line-height:8px; font-size:0;">&nbsp;</td>
                </tr>
              </table>

              <!-- Header content -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:22px 26px 10px 26px;">
                <tr>
                  <td style="font-family:Segoe UI, Arial, sans-serif;">
                    
                    <div style="font-size:26px; font-weight:800; color:#101828; margin-top:6px; letter-spacing:-0.2px;">
                      Happy Birthday, {employee.first_name} {employee.last_name}! <span style="font-weight:700;">🎉</span>
                    </div>
                  </td>
                </tr>
              </table>

              <!-- Main content -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:0 26px 22px 26px;">
                <tr>
                  <td style="font-family:Segoe UI, Arial, sans-serif; color:#101828;">

                    <!-- Greeting -->
                    <div style="font-size:16px; line-height:1.7; margin-top:8px;">
                      Dear Team,<br><br>
                      Today we celebrate <b>{employee.first_name} {employee.last_name}</b>'s birthday. 🎈🎂
                    </div>

                    <!-- Soft highlight (NOT boxy) -->
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                           style="margin:16px 0 10px 0; background:#F6F8FF; border-radius:14px;">
                      <tr>
                        <td style="padding: 14px;">
                          <div style="font-size:14px; font-weight:800; color:#30539b; margin-bottom:6px;">
                            A warm wish 💙
                          </div>
                          <div style="font-size:15px; line-height:1.7; color:#101828;">
                            Please join us in wishing {employee.first_name} a wonderful day filled with joy,
                            positivity, and success.
                          </div>
                        </td>
                      </tr>
                    </table>

                    <div style="font-size:14px; line-height:1.7; color:#475467; margin-top:12px;">
                      Thank you for being a valued member of the Almet family. We appreciate your hard work and dedication.
                    </div>

                    <!-- CTA button -->
                    <table role="presentation" cellspacing="0" cellpadding="0" style="margin-top:16px;">
                      <tr>
                        <td style=" border-radius:12px;">
                          <span style="display:inline-block; padding:12px 16px; color:#30539b; font-size:14px; font-weight:800;">
                            🎁 Wishing you a fantastic year ahead!
                          </span>
                        </td>
                      </tr>
                    </table>

                  </td>
                </tr>
              </table>

              <!-- Footer -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#FBFCFE; border-top:1px solid #EEF2F6;">
                <tr>
                  <td style="padding:14px 26px; font-family:Segoe UI, Arial, sans-serif; color:#667085; font-size:12px; line-height:1.6;">
                    This is an automated celebration notification from Almet Holding.<br>
                    © {date.today().year} Almet Holding. All rights reserved.
                  </td>
                </tr>
              </table>

            </td>
          </tr>

        </table>

      </td>
    </tr>
  </table>
</body>
</html>
"""
            
            # ✅ Send to ALL staff in ONE email
            result = system_email_service.send_email_as_system(
                from_email=self.system_sender,
                to_email=self.all_staff_emails,
                subject=subject,
                body_html=body_html
            )
            
            if result.get('success'):
    
                return True
            else:
                logger.error(f"❌ Failed to send birthday email: {result.get('message')}")
                return False
        
        except Exception as e:
            logger.error(f"Error sending birthday notification: {e}")
            return False

    def send_work_anniversary_notification(self, employee, years):
       
        try:
            if not employee.start_date:
                logger.warning(f"No start date for {employee.first_name} {employee.last_name}")
                return False
            
            # ✅ CHECK: Should we send email for this employee?
            if not self.should_send_email(employee):
                logger.info(f"✅ Anniversary celebration recorded but email skipped for {employee.first_name}")
                return True
            
            subject = f"🏆 {years} Year{'s' if years != 1 else ''} with Almet — {employee.first_name}!"
            
            body_html = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Work Anniversary</title>
</head>

<body style="margin:0; padding:0; background:#f4f6f8; font-family:'Segoe UI', Arial, sans-serif;">

<!-- Outer container -->
<table width="100%" cellspacing="0" cellpadding="0" style="padding:40px 0; background:#f4f6f8;">
<tr>
<td align="center">

<!-- Card -->
<table  cellspacing="0" cellpadding="0" style="background:#ffffff; border-radius:16px; overflow:hidden; box-shadow:0 4px 20px rgba(0,0,0,0.08);">

<!-- Header -->
<tr>
<td style="background:#253360; padding:21px; text-align:center; color:#ffffff;">
    <h1 style="margin:0; font-size:28px;">🎉 {years}-Year Anniversary</h1>
    <p style="margin:8px 0 0 0; font-size:16px;">Celebrating {employee.first_name} {employee.last_name}</p>
</td>
</tr>


<!-- Body -->
<tr>
<td style="padding:30px; color:#101828; line-height:1.6; font-size:16px;">

<p>Dear Team,</p>

<p>We are pleased to celebrate <strong>{employee.first_name} {employee.last_name}</strong> and mark <strong>{years} years</strong> of dedication, commitment, and contribution to our organization.</p>



<!-- Highlighted thank you box -->
<table width="100%" cellspacing="0" cellpadding="0" style="margin:20px 0; background:#f0f4ff; border-left:6px solid #3b82f6; border-radius:8px;">
<tr>
<td style="padding:16px;">
<p style="margin:0; font-weight:600; color:#1e40af;">💙 Thank you for your journey!</p>
<p style="margin:6px 0 0 0;">Your hard work and dedication have made a meaningful difference to our team and company.</p>
</td>
</tr>
</table>

<p>We sincerely appreciate <strong>{employee.first_name} {employee.last_name}</strong>'s hard work and loyalty, and we thank them for being a valued member of our team. Please join us in congratulating them on this milestone and wishing them continued success in the years ahead.</p>

</td>
</tr>

<!-- Footer -->
<tr>
<td style="padding:20px 30px; font-size:12px; color:#667085; text-align:center; border-top:1px solid #e2e8f0;">
    This is an automated celebration notification from Almet Holding.<br>
    © {date.today().year} Almet Holding. All rights reserved.
</td>
</tr>

</table>

</td>
</tr>
</table>

</body>
</html>
"""


            
            result = system_email_service.send_email_as_system(
                from_email=self.system_sender,
                to_email=self.all_staff_emails,
                subject=subject,
                body_html=body_html
            )
            
            if result.get("success"):
                logger.info(f"✅ Anniversary email sent to {len(self.all_staff_emails)} distribution lists")
                return True
            else:
                logger.error(f"❌ Failed to send anniversary email: {result.get('message')}")
                return False
        
        except Exception as e:
            logger.error(f"Error sending anniversary notification: {e}")
            return False

    def send_promotion_notification(self, employee, new_job_title):
      
        try:
            # ✅ CHECK: Should we send email for this employee?
            if not self.should_send_email(employee):
                logger.info(f"✅ Promotion recorded but email skipped for {employee.first_name}")
                return True
            
            subject = f"🎉 Congratulations {employee.first_name} {employee.last_name} on Your Promotion!"
            
            # Get department name
            department = str(employee.department) if employee.department else ""
            
            body_html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Promotion Announcement</title>
</head>

<body style="margin:0; padding:0; background:#EEF2F7;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#EEF2F7; padding:26px 0;">
    <tr>
      <td align="center">

        <table role="presentation" width="800" cellspacing="0" cellpadding="0" style="width:800px; max-width:800px;">

          <!-- Card -->
          <tr>
            <td style="background:#FFFFFF; border-radius:18px; overflow:hidden; box-shadow:0 10px 26px rgba(16,24,40,0.10);">

              <!-- Accent bar -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td style="background:linear-gradient(135deg, #0B6B4D 0%, #10B981 100%); height:8px; line-height:8px; font-size:0;">&nbsp;</td>
                </tr>
              </table>

              <!-- Header -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:22px 26px 10px 26px;">
                <tr>
                  <td style="font-family:Segoe UI, Arial, sans-serif;">
                    
                    <div style="font-size:26px; font-weight:800; color:#101828; margin-top:6px; letter-spacing:-0.2px;">
                      🎉 Promotion Announcement
                    </div>
                    <div style="font-size:14px; color:#475467; margin-top:8px; line-height:1.6;">
                      Celebrating excellence and growth
                    </div>
                  </td>
                </tr>
              </table>

              <!-- Content -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:0 26px 22px 26px;">
                <tr>
                  <td style="font-family:Segoe UI, Arial, sans-serif; color:#101828;">

                    <div style="font-size:16px;margin-bottom:8px; line-height:1.7; margin-top:8px;">
                      Dear Team,<br><br>
                      We are delighted to announce that <b>{employee.first_name} {employee.last_name}</b> has been promoted to a new position within our organization. 
                    </div>

                    <!-- New Position Highlight -->
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                           style="margin:18px 0; background:linear-gradient(135deg, #F0FDF4 0%, #ECFDF5 100%); border-radius:14px; border:2px solid #10B981;">
                      <tr>
                        <td style="padding:12px; text-align:center;">
                          <div style="font-size:13px; font-weight:700; color:#059669;  letter-spacing:0.5px; margin-bottom:8px;">
                            New Position
                          </div>
                          <div style="font-size:22px; font-weight:800; color:#065F46; margin-bottom:4px;">
                            {new_job_title}
                          </div>
                     
                        </td>
                      </tr>
                    </table>

                    <!-- Achievement message -->
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                           style="margin:16px 0; margin-top:16px; background:#F6F8FF; border-radius:14px;">
                      <tr>
                        <td style="padding:16px;">
                          <div style="font-size:14px; font-weight:800; color:#30539b; margin-bottom:6px;">
                            🏆 Well-deserved recognition
                          </div>
                          <div style="font-size:15px; line-height:1.7; color:#101828;">
                            {employee.first_name} has consistently demonstrated exceptional performance, leadership,
                            and dedication to our organization. This promotion reflects their hard work and the
                            valuable contributions they've made to our team.
                          </div>
                        </td>
                      </tr>
                    </table>


              

                  </td>
                </tr>
              </table>

              <!-- Footer -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#FBFCFE; border-top:1px solid #EEF2F6;">
                <tr>
                  <td style="padding:14px 26px; font-family:Segoe UI, Arial, sans-serif; color:#667085; font-size:12px; line-height:1.6;">
                    This is an automated celebration notification from Almet Holding.<br>
                    © {date.today().year} Almet Holding. All rights reserved.
                  </td>
                </tr>
              </table>

            </td>
          </tr>

        </table>

      </td>
    </tr>
  </table>
</body>
</html>
"""
            
            result = system_email_service.send_email_as_system(
                from_email=self.system_sender,
                to_email=self.all_staff_emails,
                subject=subject,
                body_html=body_html
            )
            
            if result.get("success"):
                logger.info(f"✅ Promotion email sent to {len(self.all_staff_emails)} distribution lists")
                return True
            else:
                logger.error(f"❌ Failed to send promotion email: {result.get('message')}")
                return False
        
        except Exception as e:
            logger.error(f"Error sending promotion notification: {e}")
            return False
    
    def send_welcome_email(self, employee):
      
        try:
            # ✅ CHECK: Should we send email for this employee?
            if not self.should_send_email(employee):
                logger.info(f"✅ Welcome recorded but email skipped for {employee.first_name}")
                return True
            
            subject = f"🎉 Welcome to Almet Holding, {employee.first_name}!"
            
            full_name = f"{employee.first_name} {employee.last_name}".strip()
            position = employee.position_group or "Team Member"
            department = employee.department or "N/A"
            
            body_html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Welcome</title>
</head>

<body style="margin:0; padding:0; background:#EEF2F7;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#EEF2F7; padding:26px 0;">
    <tr>
      <td align="center">

        <table role="presentation" width="800" cellspacing="0" cellpadding="0" style="width:800px; max-width:800px;">

          <!-- Card -->
          <tr>
            <td style="background:#FFFFFF; border-radius:18px; overflow:hidden; box-shadow:0 10px 26px rgba(16,24,40,0.10);">

              <!-- Accent line -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr><td style="background:#30539b; height:8px; font-size:0; line-height:8px;">&nbsp;</td></tr>
              </table>

              <!-- Header -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:22px 26px 10px 26px;">
                <tr>
                  <td style="font-family:Segoe UI, Arial, sans-serif;">
                  
                    <div style="font-size:26px; font-weight:800; color:#101828; margin-top:6px; letter-spacing:-0.2px;">
                      Welcome to the team, {employee.first_name}! 🎉
                    </div>
                    <div style="font-size:14px; color:#475467; margin-top:8px; line-height:1.6;">
                      We're excited to have you with us.
                    </div>
                  </td>
                </tr>
              </table>

              <!-- Content -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:0 26px 22px 26px;">
                <tr>
                  <td style="font-family:Segoe UI, Arial, sans-serif; color:#101828;">

                    <div style="font-size:16px; margin-bottom:12px; line-height:1.7; margin-top:6px;">
                      Dear Team,<br><br>
                      Please join us in welcoming <b>{full_name}</b> to the Almet Holding family. 🌟
                    </div>

                    <!-- Profile (soft, not boxy) -->
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                           style="margin:16px 0; background:#F6F8FF; border-radius:14px;">
                      <tr>
                        <td style="padding:16px;">
                          <div style="font-size:14px; font-weight:800; color:#30539b; margin-bottom:10px;">
                            New team member
                          </div>

                          <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                            <tr>
                              <td style="padding:10px 12px; background:#FFFFFF; border-radius:12px;">
                                <div style="font-size:18px; font-weight:800; color:#101828;">{full_name}</div>
                                <div style="font-size:13px; color:#475467; margin-top:4px;">
                                  {position}{f" • {department}" if department != "N/A" else ""}
                                </div>
                              </td>
                            </tr>
                          </table>

                        </td>
                      </tr>
                    </table>

                    <div style="font-size:15px; line-height:1.7; color:#101828; margin-top:12px;">
                      {employee.first_name} is joining us as <b>{position}</b>
                      {f"in the <b>{department}</b> department" if department != "N/A" else ""}.
                      We're confident {employee.first_name} will be a valuable addition to our team.
                    </div>

                    <div style="font-size:14px; line-height:1.7; color:#475467; margin-top:12px;">
                      Let's make sure {employee.first_name} feels right at home and has everything needed to succeed in this new role.
                    </div>

                    <!-- CTA -->
                    <table role="presentation" cellspacing="0" cellpadding="0" style="margin-top:16px;">
                      <tr>
                        <td style=" border-radius:12px;">
                          <span style="display:inline-block; padding:12px 16px; color:#30539b; font-size:14px; font-weight:800;">
                            🎉 Welcome aboard, {employee.first_name}!
                          </span>
                        </td>
                      </tr>
                    </table>

                  </td>
                </tr>
              </table>

              <!-- Footer -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#FBFCFE; border-top:1px solid #EEF2F6;">
                <tr>
                  <td style="padding:14px 26px; font-family:Segoe UI, Arial, sans-serif; color:#667085; font-size:12px; line-height:1.6;">
                    This is an automated welcome notification from Almet Holding.<br>
                    © {date.today().year} Almet Holding. All rights reserved.
                  </td>
                </tr>
              </table>

            </td>
          </tr>

        </table>

      </td>
    </tr>
  </table>
</body>
</html>
"""
            
            result = system_email_service.send_email_as_system(
                from_email=self.system_sender,
                to_email=self.all_staff_emails,
                subject=subject,
                body_html=body_html
            )
            
            if result.get("success"):
                logger.info(f"✅ Welcome email sent to {len(self.all_staff_emails)} distribution lists")
                return True
            else:
                logger.error(f"❌ Failed to send welcome email: {result.get('message')}")
                return False
        
        except Exception as e:
            logger.error(f"Error sending welcome notification: {e}")
            return False

    def check_and_send_daily_celebrations(self):
        """
        🔄 Daily check for birthdays and work anniversaries
        Run this as a scheduled task (e.g., daily at 9 AM)
        
        Returns:
            dict: Summary of sent notifications
        """
        today = date.today()
        results = {
            'birthdays_sent': 0,
            'anniversaries_sent': 0,
            'skipped': 0,
            'errors': []
        }
        
        try:
            employees = Employee.objects.filter(is_deleted=False)
            
            for emp in employees:
                # Check birthdays
                if emp.date_of_birth:
                    if emp.date_of_birth.month == today.month and emp.date_of_birth.day == today.day:
                        logger.info(f"🎂 Processing birthday for {emp.first_name} {emp.last_name}")
                        
                        if self.should_send_email(emp):
                            if self.send_birthday_notification(emp):
                                results['birthdays_sent'] += 1
                        else:
                            results['skipped'] += 1
                
                # Check work anniversaries
                if emp.start_date:
                    if emp.start_date.month == today.month and emp.start_date.day == today.day:
                        years = today.year - emp.start_date.year
                        if years > 0:  # At least 1 year
                            logger.info(f"🏆 Processing {years}-year anniversary for {emp.first_name} {emp.last_name}")
                            
                            if self.should_send_email(emp):
                                if self.send_work_anniversary_notification(emp, years):
                                    results['anniversaries_sent'] += 1
                            else:
                                results['skipped'] += 1
            
            logger.info(f"✅ Daily celebration check complete: {results}")
            return results
            
        except Exception as e:
            error_msg = f"Error in daily celebration check: {e}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            return results


# Singleton instance
celebration_notification_service = CelebrationNotificationService()