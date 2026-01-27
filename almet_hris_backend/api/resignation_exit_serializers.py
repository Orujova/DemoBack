# api/serializers/resignation_exit_serializers.py
"""
Serializers for Resignation, Exit Interview, Contract, and Probation Management
"""

from rest_framework import serializers
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


# =====================================
# RESIGNATION SERIALIZERS
# =====================================

class ResignationActivitySerializer(serializers.ModelSerializer):
    """Resignation activity log"""
    
    performed_by_name = serializers.CharField(
        source='performed_by.get_full_name',
        read_only=True
    )
    
    class Meta:
        model = ResignationActivity
        fields = [
            'id', 'activity_type', 'description',
            'performed_by', 'performed_by_name',
            'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ResignationRequestListSerializer(serializers.ModelSerializer):
    """List view serializer for resignation requests"""
    
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    position = serializers.CharField(source='employee.job_title', read_only=True)
    department = serializers.CharField(source='employee.department.name', read_only=True)
    manager_name = serializers.CharField(source='employee.line_manager.full_name', read_only=True)
    days_remaining = serializers.SerializerMethodField()
    notice_period = serializers.SerializerMethodField()
    
    class Meta:
        model = ResignationRequest
        fields = [
            'id', 'employee', 'employee_name', 'employee_id',
            'position', 'department', 'manager_name',
            'submission_date', 'last_working_day',
            'status', 'days_remaining', 'notice_period',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_days_remaining(self, obj):
        return obj.get_days_until_last_working_day()
    
    def get_notice_period(self, obj):
        return obj.get_notice_period_days()


class ResignationRequestDetailSerializer(serializers.ModelSerializer):
    """Detail view serializer for resignation requests"""
    
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    position = serializers.CharField(source='employee.job_title', read_only=True)
    department = serializers.CharField(source='employee.department.name', read_only=True)
    manager_name = serializers.CharField(source='employee.line_manager.full_name', read_only=True)
    
    manager_approved_by_name = serializers.CharField(
        source='manager_approved_by.get_full_name',
        read_only=True
    )
    hr_approved_by_name = serializers.CharField(
        source='hr_approved_by.get_full_name',
        read_only=True
    )
    
    days_remaining = serializers.SerializerMethodField()
    notice_period = serializers.SerializerMethodField()
    activities = ResignationActivitySerializer(many=True, read_only=True)
    
    class Meta:
        model = ResignationRequest
        fields = [
            'id', 'employee', 'employee_name', 'employee_id',
            'position', 'department', 'manager_name',
            'submission_date', 'last_working_day',
            'resignation_letter', 'employee_comments',
            'status', 'days_remaining', 'notice_period',
            'manager_approved_at', 'manager_approved_by',
            'manager_approved_by_name', 'manager_comments',
            'hr_approved_at', 'hr_approved_by',
            'hr_approved_by_name', 'hr_comments',
            'completed_at', 'activities',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'manager_approved_at',
            'manager_approved_by', 'hr_approved_at',
            'hr_approved_by', 'completed_at',
            'created_at', 'updated_at'
        ]
    
    def get_days_remaining(self, obj):
        return obj.get_days_until_last_working_day()
    
    def get_notice_period(self, obj):
        return obj.get_notice_period_days()

class ResignationRequestCreateSerializer(serializers.ModelSerializer):
    """Create serializer for resignation requests"""
    
    class Meta:
        model = ResignationRequest
        fields = [
            'employee', 'last_working_day',
            'resignation_letter', 'employee_comments'
        ]
    
    def validate(self, data):
        from datetime import date
        
        # ✅ FIX: Allow today as last_working_day (only reject past dates)
        if data['last_working_day'] < date.today():
            raise serializers.ValidationError({
                'last_working_day': 'Last working day cannot be in the past'
            })
        
        return data
    
    def create(self, validated_data):
        # Set submission date
        from datetime import date
        validated_data['submission_date'] = date.today()
        
        resignation = ResignationRequest.objects.create(**validated_data)
        
        # Create activity log
        ResignationActivity.objects.create(
            resignation=resignation,
            activity_type='CREATED',
            description=f"Resignation submitted by {resignation.employee.full_name}",
            performed_by=self.context['request'].user,
            metadata={
                'last_working_day': str(resignation.last_working_day),
                'notice_period_days': resignation.get_notice_period_days()
            }
        )
        
        return resignation

class ResignationApprovalSerializer(serializers.Serializer):
    """Serializer for manager/HR approval"""
    
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    comments = serializers.CharField(required=False, allow_blank=True)


# =====================================
# EXIT INTERVIEW SERIALIZERS
# =====================================

class ExitInterviewQuestionSerializer(serializers.ModelSerializer):
    """Exit interview question serializer"""
    
    class Meta:
        model = ExitInterviewQuestion
        fields = [
            'id', 'section', 'question_text_en', 'question_text_az',
            'question_type', 'order', 'is_required', 'is_active',
            'choices', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ExitInterviewResponseSerializer(serializers.ModelSerializer):
    """Exit interview response serializer"""
    
    question_text_en = serializers.CharField(
        source='question.question_text_en',
        read_only=True
    )
    question_type = serializers.CharField(
        source='question.question_type',
        read_only=True
    )
    section = serializers.CharField(
        source='question.section',
        read_only=True
    )
    
    class Meta:
        model = ExitInterviewResponse
        fields = [
            'id', 'question', 'question_text_en',
            'question_type', 'section',
            'rating_value', 'text_value', 'choice_value',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ExitInterviewSummarySerializer(serializers.ModelSerializer):
    """Exit interview summary serializer"""
    
    class Meta:
        model = ExitInterviewSummary
        fields = [
            'id', 'role_avg_rating', 'management_avg_rating',
            'compensation_avg_rating', 'conditions_avg_rating',
            'culture_avg_rating', 'overall_avg_rating',
            'main_reason_for_leaving', 'would_recommend_company',
            'retention_suggestions', 'generated_at', 'updated_at'
        ]
        read_only_fields = ['id', 'generated_at', 'updated_at']


class ExitInterviewListSerializer(serializers.ModelSerializer):
    """List view serializer for exit interviews"""
    
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    position = serializers.CharField(source='employee.job_title', read_only=True)
    department = serializers.CharField(source='employee.department.name', read_only=True)
    
    class Meta:
        model = ExitInterview
        fields = [
            'id', 'employee', 'employee_name', 'employee_id',
            'position', 'department', 'last_working_day',
            'status', 'started_at', 'completed_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ExitInterviewDetailSerializer(serializers.ModelSerializer):
    """Detail view serializer for exit interviews"""
    
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    position = serializers.CharField(source='employee.job_title', read_only=True)
    department = serializers.CharField(source='employee.department.name', read_only=True)
    
    responses = ExitInterviewResponseSerializer(many=True, read_only=True)
    summary = ExitInterviewSummarySerializer(read_only=True)
    
    class Meta:
        model = ExitInterview
        fields = [
            'id', 'employee', 'employee_name', 'employee_id',
            'position', 'department', 'last_working_day',
            'resignation_request', 'status',
            'started_at', 'completed_at',
            'responses', 'summary',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'started_at', 'completed_at',
            'created_at', 'updated_at'
        ]


class ExitInterviewCreateSerializer(serializers.ModelSerializer):
    """Create serializer for exit interviews"""
    
    class Meta:
        model = ExitInterview
        fields = [
            'employee', 'last_working_day', 'resignation_request'
        ]
    
    def create(self, validated_data):
        """Create exit interview and set created_by"""
        validated_data['created_by'] = self.context['request'].user
        exit_interview = ExitInterview.objects.create(**validated_data)
        
        # ✅ Log for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"✅ Created Exit Interview ID: {exit_interview.id} for employee: {exit_interview.employee.full_name}")
        
        return exit_interview


class ExitInterviewResponseCreateSerializer(serializers.Serializer):
    """Serializer for submitting exit interview responses"""
    
    responses = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False
    )
    
    def validate_responses(self, responses):
        """Validate response format"""
        for response in responses:
            if 'question' not in response:
                raise serializers.ValidationError("Each response must have a 'question' field")
            
            # Check that at least one value field is provided
            has_value = any([
                'rating_value' in response,
                'text_value' in response,
                'choice_value' in response
            ])
            
            if not has_value:
                raise serializers.ValidationError(
                    "Each response must have at least one value field"
                )
        
        return responses


# =====================================
# CONTRACT RENEWAL SERIALIZERS
# =====================================

class ContractRenewalRequestListSerializer(serializers.ModelSerializer):
    """List view serializer for contract renewal requests"""
    
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    position = serializers.CharField(source='employee.job_title', read_only=True)
    department = serializers.CharField(source='employee.department.name', read_only=True)
    manager_name = serializers.CharField(source='employee.line_manager.full_name', read_only=True)
    days_until_expiry = serializers.SerializerMethodField()
    
    class Meta:
        model = ContractRenewalRequest
        fields = [
            'id', 'employee', 'employee_name', 'employee_id',
            'position', 'department', 'manager_name',
            'current_contract_end_date', 'current_contract_type',
            'manager_decision', 'status', 'days_until_expiry',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_days_until_expiry(self, obj):
        return obj.get_days_until_expiry()


class ContractRenewalRequestDetailSerializer(serializers.ModelSerializer):
    """Detail view serializer for contract renewal requests"""
    
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    position = serializers.CharField(source='employee.job_title', read_only=True)
    department = serializers.CharField(source='employee.department.name', read_only=True)
    manager_name = serializers.CharField(source='employee.line_manager.full_name', read_only=True)
    
    manager_decided_by_name = serializers.CharField(
        source='manager_decided_by.get_full_name',
        read_only=True
    )
    hr_processed_by_name = serializers.CharField(
        source='hr_processed_by.get_full_name',
        read_only=True
    )
    days_until_expiry = serializers.SerializerMethodField()
    
    class Meta:
        model = ContractRenewalRequest
        fields = [
            'id', 'employee', 'employee_name', 'employee_id',
            'position', 'department', 'manager_name',
            'current_contract_end_date', 'current_contract_type',
            'notification_sent_at', 'manager_decision',
            'manager_decided_at', 'manager_decided_by',
            'manager_decided_by_name', 'new_contract_type',
            'new_contract_duration_months', 'salary_change',
            'new_salary', 'position_change', 'new_position',
            'manager_comments', 'hr_processed_at',
            'hr_processed_by', 'hr_processed_by_name',
            'hr_comments', 'status', 'days_until_expiry',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'notification_sent_at',
            'manager_decided_at', 'manager_decided_by',
            'hr_processed_at', 'hr_processed_by',
            'created_at', 'updated_at'
        ]
    
    def get_days_until_expiry(self, obj):
        return obj.get_days_until_expiry()


class ContractRenewalDecisionSerializer(serializers.Serializer):
    """Serializer for manager contract renewal decision"""
    
    decision = serializers.ChoiceField(choices=['RENEW', 'NOT_RENEW'])
    
    # Renewal details (required if decision is RENEW)
    new_contract_type = serializers.ChoiceField(
        choices=ContractRenewalRequest.CONTRACT_TYPE_CHOICES,
        required=False
    )
    new_contract_duration_months = serializers.IntegerField(
        required=False,
        min_value=1
    )
    
    # Optional changes
    salary_change = serializers.BooleanField(default=False)
    new_salary = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False
    )
    position_change = serializers.BooleanField(default=False)
    new_position = serializers.CharField(required=False, allow_blank=True)
    
    comments = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate renewal details"""
        if data['decision'] == 'RENEW':
            # Require contract type
            if not data.get('new_contract_type'):
                raise serializers.ValidationError({
                    'new_contract_type': 'Required when renewing contract'
                })
            
            # Require duration for fixed-term contracts
            if data['new_contract_type'] != 'PERMANENT':
                if not data.get('new_contract_duration_months'):
                    raise serializers.ValidationError({
                        'new_contract_duration_months': 'Required for fixed-term contracts'
                    })
            
            # Require new salary if salary_change is True
            if data.get('salary_change') and not data.get('new_salary'):
                raise serializers.ValidationError({
                    'new_salary': 'Required when salary_change is True'
                })
            
            # Require new position if position_change is True
            if data.get('position_change') and not data.get('new_position'):
                raise serializers.ValidationError({
                    'new_position': 'Required when position_change is True'
                })
        
        return data


# =====================================
# PROBATION REVIEW SERIALIZERS
# =====================================

class ProbationReviewQuestionSerializer(serializers.ModelSerializer):
    """Probation review question serializer"""
    
    class Meta:
        model = ProbationReviewQuestion
        fields = [
            'id', 'review_type', 'question_text_en',
            'question_text_az', 'question_type',
            'order', 'is_required', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProbationReviewResponseSerializer(serializers.ModelSerializer):
    """Probation review response serializer"""
    
    question_text_en = serializers.CharField(
        source='question.question_text_en',
        read_only=True
    )
    question_type = serializers.CharField(
        source='question.question_type',
        read_only=True
    )
    
    class Meta:
        model = ProbationReviewResponse
        fields = [
            'id', 'question', 'question_text_en',
            'question_type', 'respondent_type',
            'rating_value', 'yes_no_value', 'text_value',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProbationReviewListSerializer(serializers.ModelSerializer):
    """List view serializer for probation reviews"""
    
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    position = serializers.CharField(source='employee.job_title', read_only=True)
    department = serializers.CharField(source='employee.department.name', read_only=True)
    
    class Meta:
        model = ProbationReview
        fields = [
            'id', 'employee', 'employee_name', 'employee_id',
            'position', 'department', 'review_period',
            'due_date', 'status', 'completed_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ProbationReviewDetailSerializer(serializers.ModelSerializer):
    """Detail view serializer for probation reviews"""
    
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    position = serializers.CharField(source='employee.job_title', read_only=True)
    department = serializers.CharField(source='employee.department.name', read_only=True)
    
    responses = ProbationReviewResponseSerializer(many=True, read_only=True)
    
    # Separate employee and manager responses
    employee_responses = serializers.SerializerMethodField()
    manager_responses = serializers.SerializerMethodField()
    
    class Meta:
        model = ProbationReview
        fields = [
            'id', 'employee', 'employee_name', 'employee_id',
            'position', 'department', 'review_period',
            'due_date', 'notification_sent_at', 'status',
            'completed_at', 'responses',
            'employee_responses', 'manager_responses',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'notification_sent_at', 'status',
            'completed_at', 'created_at', 'updated_at'
        ]
    
    def get_employee_responses(self, obj):
        """Get employee responses only"""
        responses = obj.responses.filter(respondent_type='EMPLOYEE')
        return ProbationReviewResponseSerializer(responses, many=True).data
    
    def get_manager_responses(self, obj):
        """Get manager responses only"""
        responses = obj.responses.filter(respondent_type='MANAGER')
        return ProbationReviewResponseSerializer(responses, many=True).data


class ProbationReviewResponseCreateSerializer(serializers.Serializer):
    """Serializer for submitting probation review responses"""
    
    respondent_type = serializers.ChoiceField(
        choices=ProbationReviewResponse.RESPONDENT_TYPE_CHOICES
    )
    responses = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False
    )
    
    def validate_responses(self, responses):
        """Validate response format"""
        for response in responses:
            if 'question' not in response:
                raise serializers.ValidationError("Each response must have a 'question' field")
            
            # Check that at least one value field is provided
            has_value = any([
                'rating_value' in response,
                'yes_no_value' in response,
                'text_value' in response
            ])
            
            if not has_value:
                raise serializers.ValidationError(
                    "Each response must have at least one value field"
                )
        
        return responses