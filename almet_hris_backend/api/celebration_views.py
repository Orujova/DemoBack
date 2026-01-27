from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count
from datetime import date, timedelta
from .celebration_models  import Celebration, CelebrationImage, CelebrationWish
from .celebration_serializers  import (
    CelebrationSerializer, 
    CelebrationImageSerializer,
    CelebrationWishSerializer,

)
from .models import Employee


class CelebrationViewSet(viewsets.ModelViewSet):
    queryset = Celebration.objects.all()
    serializer_class = CelebrationSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def get_auto_wishes(self, request):
        """
        Get wishes for auto celebration (birthday, work anniversary, or promotion)
        """
        employee_id = request.query_params.get('employee_id')
        celebration_type = request.query_params.get('celebration_type')
        
        if not employee_id or not celebration_type:
            return Response({'error': 'employee_id and celebration_type are required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return Response({'error': 'Employee not found'}, status=status.HTTP_404_NOT_FOUND)
        
        wishes = CelebrationWish.objects.filter(
            employee=employee,
            celebration_type=celebration_type
        ).select_related('user').order_by('-created_at')
        
        return Response(CelebrationWishSerializer(wishes, many=True).data)
    
    @action(detail=False, methods=['get'])
    def all_celebrations(self, request):
        """
        Get all celebrations including auto-generated birthdays, work anniversaries, and promotions
        """
        today = date.today()
        
        # Get auto celebrations (birthdays & anniversaries)
        auto_celebrations = self.get_auto_celebrations(today)
        
        # ✅ Get promotions from last 30 days
        promotion_celebrations = self.get_promotion_celebrations()
        
        # Get manual celebrations
        manual_celebrations = Celebration.objects.exclude(type='promotion')
        manual_data = []
        
        for celebration in manual_celebrations:
            wishes_count = CelebrationWish.objects.filter(celebration=celebration).count()
            
            images_data = CelebrationImageSerializer(
                celebration.images.all(), 
                many=True, 
                context={'request': request}
            ).data
            
            manual_data.append({
                'id': str(celebration.id),
                'type': celebration.type,
                'title': celebration.title,
                'date': celebration.date.isoformat(),
                'images': images_data,
                'message': celebration.message,
                'wishes': wishes_count,
                'is_auto': False
            })
        
        # Combine all celebrations
        all_celebrations = auto_celebrations + promotion_celebrations + manual_data
        
        # Sort by date (newest first)
        all_celebrations.sort(key=lambda x: x['date'], reverse=True)
        
        return Response(all_celebrations)
    
    def get_auto_celebrations(self, today):
        """
        Generate auto celebrations for birthdays and work anniversaries
        """
        auto_celebrations = []
        employees = Employee.objects.filter(is_deleted=False)
        
        for emp in employees:
            # Check for birthdays (10 days before until birthday)
            if emp.date_of_birth:
                birth_date = emp.date_of_birth
                this_year_birthday = date(today.year, birth_date.month, birth_date.day)
                
                ten_days_before = this_year_birthday - timedelta(days=10)
                
                # Show from 10 days before until birthday, then hide
                if ten_days_before <= today <= this_year_birthday:
                    age = today.year - birth_date.year
                    wishes_count = CelebrationWish.objects.filter(
                        employee=emp,
                        celebration_type='birthday'
                    ).count()
                    position = str(emp.position_group) if emp.position_group else 'Employee'
                    auto_celebrations.append({
                        'id': f'birthday-{emp.id}',
                        'type': 'birthday',
                        'employee_name': f'{emp.first_name} {emp.last_name}',
                        'employee_id': emp.id,
                        'position': position,
                        'date': this_year_birthday.isoformat(),
                        'images': ['https://www.sugar.org/wp-content/uploads/Birthday-Cake-1.png'],
                        'message': f"Wishing you a wonderful {age}th birthday filled with joy and happiness! Thank you for all your contributions to the team.",
                        'wishes': wishes_count,
                        'is_auto': True
                    })
            
            # Check for work anniversaries (10 days before until 5 days after)
            if emp.start_date:
                start_date = emp.start_date
                this_year_anniversary = date(today.year, start_date.month, start_date.day)
                
                ten_days_before = this_year_anniversary - timedelta(days=10)
                five_days_after = this_year_anniversary + timedelta(days=5)
                
                # Show from 10 days before until 5 days after anniversary
                if ten_days_before <= today <= five_days_after:
                    years = today.year - start_date.year
                    
                    # Only show if at least 1 year
                    if years > 0:
                        wishes_count = CelebrationWish.objects.filter(
                            employee=emp,
                            celebration_type='work_anniversary'
                        ).count()
                        position = str(emp.position_group) if emp.position_group else 'Employee'
                        auto_celebrations.append({
                            'id': f'anniversary-{emp.id}',
                            'type': 'work_anniversary',
                            'employee_name': f'{emp.first_name} {emp.last_name}',
                            'employee_id': emp.id,
                            'position': position,
                            'date': this_year_anniversary.isoformat(),
                            'years': years,
                            'images': ['https://media.istockphoto.com/id/2219719967/vector/happy-work-anniversary-clipart-design-company-office-celebration-greeting-text-clip-art-with.jpg?s=612x612&w=0&k=20&c=tLT5yhtCjLw2gSsUNElBOOPHBFeVjCtSzcJTQzuPY1M='],
                            'message': f"Congratulations on {years} {'year' if years == 1 else 'years'} with Almet Holding! Thank you for your dedication and valuable contributions to our team.",
                            'wishes': wishes_count,
                            'is_auto': True
                        })
        
        return auto_celebrations
    
    def get_promotion_celebrations(self):
        """
        ✅ Get promotion celebrations from last 30 days
        """
        thirty_days_ago = date.today() - timedelta(days=30)
        promotion_celebrations = []
        
        promotions = Celebration.objects.filter(
            type='promotion',
            date__gte=thirty_days_ago
        ).select_related('employee')
        
        for promo in promotions:
            if promo.employee:
                wishes_count = CelebrationWish.objects.filter(
                    employee=promo.employee,
                    celebration_type='promotion'
                ).count()
                
                position = str(promo.employee.position_group) if promo.employee.position_group else 'Employee'
                
                promotion_celebrations.append({
                    'id': f'promotion-{promo.id}',
                    'type': 'promotion',
                    'employee_name': f'{promo.employee.first_name} {promo.employee.last_name}',
                    'employee_id': promo.employee.id,
                    'position': position,
                    'new_job_title': promo.new_job_title,
                    'date': promo.date.isoformat(),
                    'images': ['https://cdn-icons-png.flaticon.com/512/3176/3176366.png'],
                    'message': promo.message,
                    'wishes': wishes_count,
                    'is_auto': True
                })
        
        return promotion_celebrations
    
    @action(detail=True, methods=['post'])
    def add_wish(self, request, pk=None):
        """
        Add a wish to a manual celebration
        """
        celebration = self.get_object()
        message = request.data.get('message', '')
        
        if not message:
            return Response({'error': 'Message is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Manual celebrations can only be celebrated on the day
        celebration_date = celebration.date
        today = date.today()
        
        if celebration_date != today:
            return Response(
                {'error': 'You can only celebrate on the celebration day'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        wish = CelebrationWish.objects.create(
            celebration=celebration,
            user=request.user,
            celebration_type=celebration.type,
            message=message
        )
        
        # Update wishes count
        celebration.wishes_count = CelebrationWish.objects.filter(celebration=celebration).count()
        celebration.save()
        
        return Response(CelebrationWishSerializer(wish).data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    def add_auto_wish(self, request):
        """
        Add a wish to an auto celebration (birthday, work anniversary, or promotion)
        ✅ Auto celebrations can be celebrated anytime
        """
        employee_id = request.data.get('employee_id')
        celebration_type = request.data.get('celebration_type')  # 'birthday', 'work_anniversary', or 'promotion'
        message = request.data.get('message', '')
        
        if not employee_id or not celebration_type or not message:
            return Response({'error': 'employee_id, celebration_type, and message are required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return Response({'error': 'Employee not found'}, status=status.HTTP_404_NOT_FOUND)
        
        wish = CelebrationWish.objects.create(
            employee=employee,
            user=request.user,
            celebration_type=celebration_type,
            message=message
        )
        
        return Response(CelebrationWishSerializer(wish).data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['delete'])
    def remove_image(self, request, pk=None):
        """
        Remove an image from celebration
        """
        celebration = self.get_object()
        image_id = request.data.get('image_id')
        
        if not image_id:
            return Response({'error': 'image_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            image = CelebrationImage.objects.get(id=image_id, celebration=celebration)
            image.delete()
            return Response({'message': 'Image deleted successfully'}, status=status.HTTP_200_OK)
        except CelebrationImage.DoesNotExist:
            return Response({'error': 'Image not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get celebration statistics
        """
        today = date.today()
        current_month = today.month
        
        # Get auto celebrations count
        auto_celebrations = self.get_auto_celebrations(today)
        promotion_celebrations = self.get_promotion_celebrations()
        
        # Get manual celebrations count
        manual_count = Celebration.objects.exclude(type='promotion').count()
        
        # Total celebrations
        total_count = len(auto_celebrations) + len(promotion_celebrations) + manual_count
        
        # This month count
        this_month_auto = len([c for c in auto_celebrations if date.fromisoformat(c['date']).month == current_month])
        this_month_promo = len([c for c in promotion_celebrations if date.fromisoformat(c['date']).month == current_month])
        this_month_manual = Celebration.objects.exclude(type='promotion').filter(date__month=current_month).count()
        this_month_count = this_month_auto + this_month_promo + this_month_manual
        
        # Upcoming (next 7 days)
        seven_days_later = today + timedelta(days=7)
        upcoming_auto = len([c for c in auto_celebrations if today <= date.fromisoformat(c['date']) <= seven_days_later])
        upcoming_promo = len([c for c in promotion_celebrations if today <= date.fromisoformat(c['date']) <= seven_days_later])
        upcoming_manual = Celebration.objects.exclude(type='promotion').filter(date__gte=today, date__lte=seven_days_later).count()
        upcoming_count = upcoming_auto + upcoming_promo + upcoming_manual
        
        # Total wishes
        total_wishes = CelebrationWish.objects.count()
        
        return Response({
            'total_celebrations': total_count,
            'this_month': this_month_count,
            'upcoming': upcoming_count,
            'total_wishes': total_wishes
        })