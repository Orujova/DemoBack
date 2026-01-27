# api/views/resignation_exit_views.py
"""
ViewSets for Resignation, Exit Interview, Contract, and Probation Management
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.utils import timezone
from datetime import date, timedelta
import logging

from api.models import Employee
from api.resignation_models import ResignationRequest, ResignationActivity
from api.exit_interview_models import (
    ExitInterviewQuestion,
    ExitInterview,
    ExitInterviewResponse,
    ExitInterviewSummary
)
from api.contract_probation_models import (
    ContractRenewalRequest,
    ProbationReviewQuestion,
    ProbationReview,
    ProbationReviewResponse
)

from api.resignation_exit_serializers import *
from api.job_description_permissions import is_admin_user

logger = logging.getLogger(__name__)


# =====================================
# RESIGNATION VIEWSETS
# =====================================

class ResignationRequestViewSet(viewsets.ModelViewSet):

    
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        try:
            employee = Employee.objects.get(user=user, is_deleted=False)
            
            # Admin sees all
            if is_admin_user(user):
                return ResignationRequest.objects.filter(
                    is_deleted=False
                ).select_related(
                    'employee',
                    'employee__department',
                    'employee__line_manager',
                    'manager_approved_by',
                    'hr_approved_by'
                ).order_by('-created_at')
            
            # Manager sees direct reports + own
            if employee.direct_reports.exists():
                direct_report_ids = employee.direct_reports.filter(
                    is_deleted=False
                ).values_list('id', flat=True)
                
                return ResignationRequest.objects.filter(
                    Q(employee=employee) | Q(employee_id__in=direct_report_ids),
                    is_deleted=False
                ).select_related(
                    'employee',
                    'employee__department',
                    'employee__line_manager'
                ).order_by('-created_at')
            
            # Employee sees only own
            return ResignationRequest.objects.filter(
                employee=employee,
                is_deleted=False
            ).select_related(
                'employee',
                'employee__department',
                'employee__line_manager'
            ).order_by('-created_at')
            
        except Employee.DoesNotExist:
            return ResignationRequest.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ResignationRequestCreateSerializer
        elif self.action == 'list':
            return ResignationRequestListSerializer
        else:
            return ResignationRequestDetailSerializer
    
    def perform_create(self, serializer):
        """Create resignation request"""
        resignation = serializer.save()
        
        # Send notification to manager
        if resignation.employee.line_manager and resignation.employee.line_manager.email:
            self._send_manager_notification(resignation)
    
    def _send_manager_notification(self, resignation):
        """Send notification to manager about new resignation"""
        from api.system_email_service import system_email_service
        
        try:
            subject = f"Resignation Submitted - {resignation.employee.full_name}"
            
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #FF6B35;">New Resignation - Action Required</h2>
                
                <p>Dear {resignation.employee.line_manager.first_name},</p>
                
                <p>An employee has submitted a resignation request:</p>
                
                <div style="background-color: #FEF3C7; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #F59E0B;">
                    <p><strong>Employee:</strong> {resignation.employee.full_name} ({resignation.employee.employee_id})</p>
                    <p><strong>Position:</strong> {resignation.employee.job_title}</p>
                    <p><strong>Department:</strong> {resignation.employee.department.name}</p>
                    <p><strong>Submission Date:</strong> {resignation.submission_date}</p>
                    <p><strong>Last Working Day:</strong> {resignation.last_working_day}</p>
                    <p><strong>Notice Period:</strong> {resignation.get_notice_period_days()} days</p>
                </div>
                
                {f'<p><strong>Employee Comments:</strong><br>{resignation.employee_comments}</p>' if resignation.employee_comments else ''}
                
    
            </body>
            </html>
            """
            
            system_email_service.send_email_as_system(
                from_email="myalmet@almettrading.com",
                to_email=resignation.employee.line_manager.email,
                subject=subject,
                body_html=body
            )
        except Exception as e:
            logger.error(f"Error sending manager notification: {e}")
    
    @action(detail=True, methods=['post'])
    def manager_approve(self, request, pk=None):
        """Manager approves resignation"""
        resignation = self.get_object()
        serializer = ResignationApprovalSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Check permission
            employee = Employee.objects.get(user=request.user, is_deleted=False)
            if resignation.employee.line_manager != employee and not is_admin_user(request.user):
                return Response(
                    {'detail': 'You do not have permission to approve this resignation'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            action_type = serializer.validated_data['action']
            comments = serializer.validated_data.get('comments', '')
            
            if action_type == 'approve':
                resignation.manager_approve(request.user, comments)
                message = 'Resignation approved by manager'
            else:
                resignation.manager_reject(request.user, comments)
                message = 'Resignation rejected by manager'
            
            return Response({
                'message': message,
                'resignation': ResignationRequestDetailSerializer(resignation).data
            })
            
        except Exception as e:
            logger.error(f"Error in manager approval: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def hr_approve(self, request, pk=None):
        """HR approves resignation"""
        resignation = self.get_object()
        serializer = ResignationApprovalSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Check permission - only admin
            if not is_admin_user(request.user):
                return Response(
                    {'detail': 'Only HR admin can process this'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            action_type = serializer.validated_data['action']
            comments = serializer.validated_data.get('comments', '')
            
            if action_type == 'approve':
                resignation.hr_approve(request.user, comments)
                message = 'Resignation approved by HR'
            else:
                resignation.hr_reject(request.user, comments)
                message = 'Resignation rejected by HR'
            
            return Response({
                'message': message,
                'resignation': ResignationRequestDetailSerializer(resignation).data
            })
            
        except Exception as e:
            logger.error(f"Error in HR approval: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# =====================================
# EXIT INTERVIEW VIEWSETS
# =====================================

class ExitInterviewQuestionViewSet(viewsets.ModelViewSet):
 
    
    permission_classes = [IsAuthenticated]
    serializer_class = ExitInterviewQuestionSerializer
    
    def get_queryset(self):
        queryset = ExitInterviewQuestion.objects.filter(
            is_deleted=False,
            is_active=True
        ).order_by('section', 'order')
        
        # Filter by section if provided
        section = self.request.query_params.get('section')
        if section:
            queryset = queryset.filter(section=section)
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Only admin can create"""
        if not is_admin_user(request.user):
            return Response(
                {'detail': 'Only admin can create questions'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """Only admin can update"""
        if not is_admin_user(request.user):
            return Response(
                {'detail': 'Only admin can update questions'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Only admin can delete (soft delete)"""
        if not is_admin_user(request.user):
            return Response(
                {'detail': 'Only admin can delete questions'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        question = self.get_object()
        question.soft_delete(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExitInterviewViewSet(viewsets.ModelViewSet):

    
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        try:
            employee = Employee.objects.get(user=user, is_deleted=False)
            
            # Admin sees all
            if is_admin_user(user):
                return ExitInterview.objects.filter(
                    is_deleted=False
                ).select_related(
                    'employee',
                    'employee__department',
                    'employee__line_manager'
                ).prefetch_related('responses').order_by('-created_at')
            
            # Employee sees only own
            return ExitInterview.objects.filter(
                employee=employee,
                is_deleted=False
            ).select_related(
                'employee',
                'employee__department',
                'employee__line_manager'
            ).prefetch_related('responses').order_by('-created_at')
            
        except Employee.DoesNotExist:
            return ExitInterview.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ExitInterviewCreateSerializer
        elif self.action == 'list':
            return ExitInterviewListSerializer
        else:
            return ExitInterviewDetailSerializer
    
    def create(self, request, *args, **kwargs):
        """Only admin can create exit interviews"""
        if not is_admin_user(request.user):
            return Response(
                {'detail': 'Only admin can create exit interviews'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # Get created instance
        instance = serializer.instance
        
        # ✅ Send notifications to manager, IT team, and Gunay
        self._send_exit_interview_notifications(instance)
        
        # Return full detail
        output_serializer = ExitInterviewDetailSerializer(instance)
        headers = self.get_success_headers(output_serializer.data)
        
        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )
    
    def _send_exit_interview_notifications(self, exit_interview):
        """
        Send notifications when exit interview is created
        - To employee's line manager
        - To IT team
        - To Gunay (HR)
        """
        from api.system_email_service import system_email_service
        
        try:
            employee = exit_interview.employee
            days_remaining = (exit_interview.last_working_day - date.today()).days
            
            # Prepare recipients
            recipients = []
            
            # 1. Line Manager
            if employee.line_manager and employee.line_manager.email:
                recipients.append(employee.line_manager.email)
            
            # # 2. IT Team
            # recipients.append("it-team@almettrading.com")
            
            # # 3. Gunay (HR)
            # recipients.append("g.mammadova@almettrading.com")
            # # 3. HR
            # recipients.append("hr@almettrading.com")
            
            
            
            subject = f"⚠️ Employee Exit Notice - {employee.full_name}"
            
            body = f"""
<html>
<body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        
        <h2 style="color: #1e40af; border-bottom: 3px solid #1e40af; padding-bottom: 10px;">
            Employee Exit Notice
        </h2>
        
        <p style="font-size: 16px; margin: 20px 0;">
            Dear Team,
        </p>
        
        <p style="font-size: 15px; margin: 20px 0;">
            Kindly be informed that <strong>{employee.full_name}</strong>'s last working day is 
            <strong style="color: #EF4444;">{exit_interview.last_working_day.strftime('%B %d, %Y')}</strong>.
        </p>
        
        <div style="background-color: #F3F4F6; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #1e40af;">
            <h3 style="margin-top: 0; color: #1e40af; font-size: 16px;">Employee Details</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 0; color: #666;"><strong>Employee ID:</strong></td>
                    <td style="padding: 8px 0;">{employee.employee_id}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #666;"><strong>Position:</strong></td>
                    <td style="padding: 8px 0;">{employee.job_title}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #666;"><strong>Department:</strong></td>
                    <td style="padding: 8px 0;">{employee.department.name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #666;"><strong>Days Remaining:</strong></td>
                    <td style="padding: 8px 0;"><strong style="color: #EF4444;">{days_remaining} days</strong></td>
                </tr>
            </table>
        </div>
        
       
        
    </div>
</body>
</html>
"""
            
            # Send to all recipients
            system_email_service.send_email_as_system(
                from_email="myalmet@almettrading.com",
                to_email=recipients,
                subject=subject,
                body_html=body
            )
            
            logger.info(f"✅ Exit interview notifications sent for employee: {employee.employee_id}")
            
        except Exception as e:
            logger.error(f"❌ Error sending exit interview notifications: {e}")
    
    @action(detail=True, methods=['post'])
    def submit_responses(self, request, pk=None):
        """
        Employee submits exit interview responses
        POST /api/exit-interviews/{id}/submit_responses/
        
        Body:
        {
            "responses": [
                {
                    "question": 1,
                    "rating_value": 4,
                    "text_value": "Great team environment",
                    "choice_value": "Career Growth"
                }
            ]
        }
        """
        exit_interview = self.get_object()
        serializer = ExitInterviewResponseCreateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Check permission - only employee can submit
            employee = Employee.objects.get(user=request.user, is_deleted=False)
            if exit_interview.employee != employee and not is_admin_user(request.user):
                return Response(
                    {'detail': 'You can only submit your own exit interview'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if already completed
            if exit_interview.status == 'COMPLETED':
                return Response(
                    {'detail': 'Exit interview already completed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Start interview if not started
            if exit_interview.status == 'PENDING':
                exit_interview.start_interview()
            
            # Save responses
            responses_data = serializer.validated_data['responses']
            created_count = 0
            updated_count = 0
            
            for response_data in responses_data:
                question_id = response_data['question']
                
                # Validate question exists and is active
                try:
                    question = ExitInterviewQuestion.objects.get(
                        id=question_id,
                        is_active=True,
                        is_deleted=False
                    )
                except ExitInterviewQuestion.DoesNotExist:
                    continue
                
                # Create or update response
                response, created = ExitInterviewResponse.objects.update_or_create(
                    exit_interview=exit_interview,
                    question=question,
                    defaults={
                        'rating_value': response_data.get('rating_value'),
                        'text_value': response_data.get('text_value', ''),
                        'choice_value': response_data.get('choice_value', '')
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            
            # Complete interview
            exit_interview.complete_interview()
            
            # Generate summary
            ExitInterviewSummary.generate_summary(exit_interview)
            
            logger.info(
                f"Exit interview completed: {exit_interview.employee.employee_id} "
                f"(Created: {created_count}, Updated: {updated_count})"
            )
            
            return Response({
                'message': 'Exit interview submitted successfully',
                'created_responses': created_count,
                'updated_responses': updated_count,
                'exit_interview': ExitInterviewDetailSerializer(exit_interview).data
            })
            
        except Employee.DoesNotExist:
            return Response(
                {'detail': 'Employee not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error submitting exit interview: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def questions(self, request, pk=None):
        """
        Get all active exit interview questions
        GET /api/exit-interviews/{id}/questions/
        """
        questions = ExitInterviewQuestion.objects.filter(
            is_active=True,
            is_deleted=False
        ).order_by('section', 'order')
        
        serializer = ExitInterviewQuestionSerializer(questions, many=True)
        return Response(serializer.data)


# =====================================
# CONTRACT RENEWAL VIEWSETS
# =====================================

class ContractRenewalRequestViewSet(viewsets.ModelViewSet):

    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        try:
            employee = Employee.objects.get(user=user, is_deleted=False)
            
            # Admin sees all
            if is_admin_user(user):
                return ContractRenewalRequest.objects.filter(
                    is_deleted=False
                ).select_related(
                    'employee',
                    'employee__department',
                    'employee__line_manager'
                ).order_by('-created_at')
            
            # Manager sees direct reports + own
            if employee.direct_reports.exists():
                direct_report_ids = employee.direct_reports.filter(
                    is_deleted=False
                ).values_list('id', flat=True)
                
                return ContractRenewalRequest.objects.filter(
                    Q(employee=employee) | Q(employee_id__in=direct_report_ids),
                    is_deleted=False
                ).select_related(
                    'employee',
                    'employee__department',
                    'employee__line_manager'
                ).order_by('-created_at')
            
            # Employee sees only own
            return ContractRenewalRequest.objects.filter(
                employee=employee,
                is_deleted=False
            ).select_related(
                'employee',
                'employee__department',
                'employee__line_manager'
            ).order_by('-created_at')
            
        except Employee.DoesNotExist:
            return ContractRenewalRequest.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ContractRenewalRequestListSerializer
        else:
            return ContractRenewalRequestDetailSerializer
    
    @action(detail=True, methods=['post'])
    def manager_decision(self, request, pk=None):
        """Manager makes contract renewal decision"""
        renewal = self.get_object()
        serializer = ContractRenewalDecisionSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Check permission
            employee = Employee.objects.get(user=request.user, is_deleted=False)
            if renewal.employee.line_manager != employee and not is_admin_user(request.user):
                return Response(
                    {'detail': 'You do not have permission to make this decision'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            decision_data = serializer.validated_data
            renewal.manager_make_decision(request.user, decision_data['decision'], decision_data)
            
            return Response({
                'message': 'Contract decision submitted successfully',
                'renewal': ContractRenewalRequestDetailSerializer(renewal).data
            })
            
        except Exception as e:
            logger.error(f"Error in manager decision: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def hr_process(self, request, pk=None):
        """HR processes contract renewal"""
        renewal = self.get_object()
        
        try:
            # Check permission - only admin
            if not is_admin_user(request.user):
                return Response(
                    {'detail': 'Only HR admin can process renewals'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            comments = request.data.get('comments', '')
            
            if renewal.manager_decision == 'RENEW':
                renewal.hr_process_renewal(request.user, comments)
                message = 'Contract renewal processed successfully'
            else:
                renewal.hr_handle_expiry(request.user, comments)
                message = 'Contract expiry processed successfully'
            
            return Response({
                'message': message,
                'renewal': ContractRenewalRequestDetailSerializer(renewal).data
            })
            
        except Exception as e:
            logger.error(f"Error in HR processing: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# =====================================
# PROBATION REVIEW VIEWSETS
# =====================================

# api/views/resignation_exit_views.py

class ProbationReviewQuestionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ProbationReviewQuestionSerializer
    
    def get_queryset(self):
        queryset = ProbationReviewQuestion.objects.filter(
            is_deleted=False,
            is_active=True
        ).order_by('review_type', 'order')
        
        review_type = self.request.query_params.get('review_type')
        if review_type:
            review_types = review_type.split(',')
            queryset = queryset.filter(review_type__in=review_types)
        
        return queryset
    
    # ✅ NEW: Get questions by review period and respondent
    @action(detail=False, methods=['get'])
    def for_review(self, request):
        """
        Get questions for specific review
        GET /api/probation-review-questions/for_review/?period=30_DAY&respondent=EMPLOYEE
        GET /api/probation-review-questions/for_review/?period=30_DAY&respondent=MANAGER
        """
        period = request.query_params.get('period')  # 30_DAY, 60_DAY, 90_DAY
        respondent = request.query_params.get('respondent')  # EMPLOYEE, MANAGER
        
        if not period or not respondent:
            return Response(
                {'detail': 'Both period and respondent parameters are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Map period to review_type
        review_type_map = {
            '30_DAY': {
                'EMPLOYEE': 'EMPLOYEE_30',
                'MANAGER': 'MANAGER_30'
            },
            '60_DAY': {
                'EMPLOYEE': 'EMPLOYEE_60',
                'MANAGER': 'MANAGER_60'
            },
            '90_DAY': {
                'EMPLOYEE': 'EMPLOYEE_90',
                'MANAGER': 'MANAGER_90'
            }
        }
        
        review_type = review_type_map.get(period, {}).get(respondent)
        
        if not review_type:
            return Response(
                {'detail': 'Invalid period or respondent'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        questions = ProbationReviewQuestion.objects.filter(
            review_type=review_type,
            is_active=True,
            is_deleted=False
        ).order_by('order')
        
        serializer = self.get_serializer(questions, many=True)
        return Response({
            'period': period,
            'respondent': respondent,
            'review_type': review_type,
            'questions': serializer.data
        })
    
    def create(self, request, *args, **kwargs):
        """Only admin can create"""
        if not is_admin_user(request.user):
            return Response(
                {'detail': 'Only admin can create questions'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """Only admin can update"""
        if not is_admin_user(request.user):
            return Response(
                {'detail': 'Only admin can update questions'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Only admin can delete (soft delete)"""
        if not is_admin_user(request.user):
            return Response(
                {'detail': 'Only admin can delete questions'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        question = self.get_object()
        question.soft_delete(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

class ProbationReviewViewSet(viewsets.ModelViewSet):

    
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        try:
            employee = Employee.objects.get(user=user, is_deleted=False)
            
            # Admin sees all
            if is_admin_user(user):
                return ProbationReview.objects.filter(
                    is_deleted=False
                ).select_related(
                    'employee',
                    'employee__department'
                ).order_by('-due_date')
            
            # Manager sees direct reports + own
            if employee.direct_reports.exists():
                direct_report_ids = employee.direct_reports.filter(
                    is_deleted=False
                ).values_list('id', flat=True)
                
                return ProbationReview.objects.filter(
                    Q(employee=employee) | Q(employee_id__in=direct_report_ids),
                    is_deleted=False
                ).select_related(
                    'employee',
                    'employee__department'
                ).order_by('-due_date')
            
            # Employee sees only own
            return ProbationReview.objects.filter(
                employee=employee,
                is_deleted=False
            ).select_related(
                'employee',
                'employee__department'
            ).order_by('-due_date')
            
        except Employee.DoesNotExist:
            return ProbationReview.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ProbationReviewListSerializer
        else:
            return ProbationReviewDetailSerializer
    
    @action(detail=True, methods=['post'])
    def submit_responses(self, request, pk=None):
        """Submit probation review responses (employee or manager)"""
        review = self.get_object()
        serializer = ProbationReviewResponseCreateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            employee = Employee.objects.get(user=request.user, is_deleted=False)
            respondent_type = serializer.validated_data['respondent_type']
            
            # Check permission
            if respondent_type == 'EMPLOYEE':
                if review.employee != employee:
                    return Response(
                        {'detail': 'You can only submit your own review'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            elif respondent_type == 'MANAGER':
                if review.employee.line_manager != employee and not is_admin_user(request.user):
                    return Response(
                        {'detail': 'You can only submit reviews for your direct reports'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            # Save responses
            responses_data = serializer.validated_data['responses']
            
            for response_data in responses_data:
                question_id = response_data['question']
                
                # Create or update response
                response, created = ProbationReviewResponse.objects.update_or_create(
                    review=review,
                    question_id=question_id,
                    respondent_type=respondent_type,
                    defaults={
                        'rating_value': response_data.get('rating_value'),
                        'yes_no_value': response_data.get('yes_no_value'),
                        'text_value': response_data.get('text_value', '')
                    }
                )
            
            # Check if review is complete
            if review.status == 'PENDING':
                review.status = 'IN_PROGRESS'
                review.save()
            
            # Check if both employee and manager have responded
            has_employee_responses = review.responses.filter(
                respondent_type='EMPLOYEE'
            ).exists()
            has_manager_responses = review.responses.filter(
                respondent_type='MANAGER'
            ).exists()
            
            if has_employee_responses and has_manager_responses:
                review.complete_review()
            
            return Response({
                'message': 'Probation review responses submitted successfully',
                'review': ProbationReviewDetailSerializer(review).data
            })
            
        except Exception as e:
            logger.error(f"Error submitting probation review: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )