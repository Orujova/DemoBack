# api/news_models.py


from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import FileExtensionValidator
import uuid
from .models import Employee, SoftDeleteModel, BusinessFunction, Department, PositionGroup


class NewsCategory(SoftDeleteModel):
    """
    Dynamic News Categories (CRUD enabled)
    Replaces hardcoded CATEGORY_CHOICES
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    

    name = models.CharField(
        max_length=100,
        help_text="Display name (e.g., 'Announcement', 'Event')"
    )

    

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Active categories can be used for news"
    )
    
    # Audit
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='news_categories_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'company_news_categories'
        verbose_name = 'News Category'
        verbose_name_plural = 'News Categories'
        ordering = [ 'name']
        indexes = [
  
            models.Index(fields=['is_active']),
       
        ]
    
    def __str__(self):
        return self.name
    
  

class TargetGroup(SoftDeleteModel):
    """
    Target Groups for sending news to specific employee segments
    Similar to email distribution lists
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic Information
    name = models.CharField(
        max_length=100, 
        unique=True,
        help_text="Target group name (e.g., 'Leadership Team', 'All Employees')"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of this target group"
    )
    
    # Members - Many-to-Many relationship with Employee
    members = models.ManyToManyField(
        Employee,
        related_name='news_target_groups',
        blank=True,
        help_text="Employees in this target group"
    )
    
    # Group Settings
    is_active = models.BooleanField(
        default=True,
        help_text="Active groups can be used for news distribution"
    )
    
    # Audit fields
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='news_target_groups_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'company_target_groups'
        verbose_name = 'Target Group'
        verbose_name_plural = 'Target Groups'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
            models.Index(fields=['is_deleted']),
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def member_count(self):
        """Get active member count"""
        return self.members.filter(is_deleted=False).count()
    
    def get_active_members(self):
        """Get list of active members"""
        return self.members.filter(is_deleted=False).select_related(
            'business_function', 'department', 'job_function'
        )
    
    def get_member_emails(self):
        """Get list of member email addresses for notifications"""
        return list(
            self.get_active_members()
            .exclude(email__isnull=True)
            .exclude(email='')
            .values_list('email', flat=True)
        )


class CompanyNews(SoftDeleteModel):
    """
    Company News/Announcements
    Can be targeted to specific employee groups with email notifications
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic Information
    title = models.CharField(
        max_length=300,
        help_text="News title/headline"
    )
    excerpt = models.TextField(
        max_length=500,
        help_text="Brief summary (shown in list view)"
    )
    content = models.TextField(
        help_text="Full news content (supports rich text)"
    )
    
    # Categorization - FK to NewsCategory instead of choices
    category = models.ForeignKey(
        NewsCategory,
        on_delete=models.PROTECT,
        related_name='news_items',
        help_text="News category"
    )
    tags = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated tags (e.g., 'HR, Benefits, 2025')"
    )
    
    # Media
    image = models.ImageField(
        upload_to='news_images/%Y/%m/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'gif', 'webp'])],
        help_text="Featured image for the news"
    )
    image_preview_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="External image URL (alternative to uploaded image)"
    )
    
    # Target Groups
    target_groups = models.ManyToManyField(
        TargetGroup,
        related_name='news_items',
        blank=True,
        help_text="Target groups to receive this news"
    )
    notify_members = models.BooleanField(
        default=False,
        help_text="Send email notification to target group members"
    )
    
    # Publishing
    is_published = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Published news are visible to users"
    )
    is_pinned = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Pinned news appear at the top"
    )
    published_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Publication date/time"
    )
    
    # Engagement Tracking
    view_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times news was viewed"
    )
    
    # Author Information
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='news_authored',
        help_text="News author"
    )
    author_display_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Display name for author (e.g., 'CEO Office', 'HR Department')"
    )
    
    # Notification Status
    notification_sent = models.BooleanField(
        default=False,
        help_text="Whether notification emails were sent"
    )
    notification_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When notifications were sent"
    )
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='news_created'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='news_updated'
    )
    
    class Meta:
        db_table = 'company_news'
        verbose_name = 'Company News'
        verbose_name_plural = 'Company News'
        ordering = ['-is_pinned', '-published_at']
        indexes = [
            models.Index(fields=['-is_pinned', '-published_at']),
            models.Index(fields=['category', '-published_at']),
            models.Index(fields=['is_published', '-published_at']),
            models.Index(fields=['is_deleted']),
        ]
    
    def __str__(self):
        return self.title
    
    def increment_view_count(self):
        """Increment view counter"""
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    def get_tags_list(self):
        """Get tags as list"""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
    
    def set_tags_from_list(self, tags_list):
        """Set tags from list"""
        self.tags = ', '.join(tags_list)
    
    def get_image_url(self):
        """Get image URL (uploaded or external)"""
        if self.image:
            return self.image.url
        return self.image_preview_url or None
    
    @property
    def total_recipients(self):
        """Get total number of recipients from target groups"""
        total = 0
        for group in self.target_groups.all():
            total += group.member_count
        return total
    
    def get_recipient_emails(self):
        """Get all unique recipient emails from target groups"""
        emails = set()
        for group in self.target_groups.all():
            emails.update(group.get_member_emails())
        return list(emails)



