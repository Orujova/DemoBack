from django.db import models
from django.contrib.auth.models import User
from .models import Employee

class Celebration(models.Model):
    """
    Model for storing manual celebrations (company events, achievements, etc.)
    Birthdays and work anniversaries are auto-generated from Employee model
    """
    CELEBRATION_TYPES = [
        ('company_event', 'Company Event'),
        ('achievement', 'Achievement'),
        ('promotion', 'Promotion'),  # ✅ Added promotion type
        ('other', 'Other'),
    ]
    
    type = models.CharField(max_length=50, choices=CELEBRATION_TYPES)
    title = models.CharField(max_length=200)
    date = models.DateField()
    message = models.TextField()
    wishes_count = models.IntegerField(default=0)
    
    # ✅ Added for promotion tracking
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='celebrations', null=True, blank=True)
    new_job_title = models.CharField(max_length=200, null=True, blank=True)  # For promotions
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='celebrations_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', '-created_at']
        
    def __str__(self):
        return f"{self.title} - {self.date}"


class CelebrationImage(models.Model):
    """Model for storing celebration images"""
    celebration = models.ForeignKey(Celebration, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='celebrations/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['uploaded_at']
        
    def __str__(self):
        return f"Image for {self.celebration.title}"


class CelebrationWish(models.Model):
    """Model for storing wishes/greetings for celebrations"""
    celebration = models.ForeignKey(Celebration, on_delete=models.CASCADE, related_name='wishes', null=True, blank=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='celebration_wishes', null=True, blank=True)
    celebration_type = models.CharField(max_length=50)  # birthday, work_anniversary, or promotion for auto celebrations
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishes_sent')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        if self.celebration:
            return f"Wish from {self.user.username} for {self.celebration.title}"
        return f"Wish from {self.user.username} for {self.employee}"