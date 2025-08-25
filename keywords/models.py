from django.db import models
from django.utils import timezone
from django.conf import settings
from project.models import Project


class Keyword(models.Model):
    RANK_STATUS_CHOICES = [
        ('no_change', 'No Change'),
        ('up', 'Up'),
        ('down', 'Down'),
        ('new', 'New'),
    ]
    
    IMPACT_CHOICES = [
        ('no', 'No'),
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    
    # Core fields
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='keywords')
    keyword = models.CharField(max_length=255, db_index=True)
    country = models.CharField(max_length=50, default='US', db_index=True)
    country_code = models.CharField(max_length=10, default='US', db_index=True)  # Alias for country
    location = models.CharField(max_length=255, blank=True, null=True, help_text='Location for local search (e.g., "New York, NY, United States")')
    uule = models.CharField(max_length=255, blank=True, null=True, help_text='UULE parameter for exact location targeting')
    
    # Ranking fields
    rank = models.IntegerField(default=0, db_index=True)
    on_map = models.BooleanField(default=False)
    rank_status = models.CharField(max_length=20, choices=RANK_STATUS_CHOICES, default='no_change')
    rank_diff_from_last_time = models.IntegerField(default=0)
    rank_url = models.URLField(max_length=500, blank=True, null=True)
    number_of_results = models.BigIntegerField(default=0)
    initial_rank = models.IntegerField(default=0, null=True, blank=True)
    highest_rank = models.IntegerField(default=0)
    
    # Scraping fields
    scraped_at = models.DateTimeField(null=True, blank=True, db_index=True)
    scrape_do_file_path = models.CharField(max_length=500, blank=True, null=True, help_text='Latest HTML file path')
    scrape_do_files = models.JSONField(default=list, blank=True, help_text='Ordered list of HTML files, latest first')
    scrape_do_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default='')
    last_error_message = models.CharField(max_length=255, blank=True, null=True, help_text='Minimal error message')
    success_api_hit_count = models.IntegerField(default=0)
    failed_api_hit_count = models.IntegerField(default=0)
    
    # Management fields
    impact = models.CharField(max_length=20, choices=IMPACT_CHOICES, default='no')
    processing = models.BooleanField(default=False, db_index=True)
    archive = models.BooleanField(default=False, db_index=True)
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['keyword', 'country', 'project']
        indexes = [
            models.Index(fields=['project', 'keyword']),
            models.Index(fields=['project', 'rank']),
            models.Index(fields=['project', 'archive']),
            models.Index(fields=['project', '-created_at']),
            models.Index(fields=['processing', 'archive']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.keyword} - {self.project.domain} ({self.country})"
    
    def update_rank(self, new_rank, url=None):
        """Update rank and calculate differences"""
        old_rank = self.rank
        
        # Handle not found in top 100 case
        if new_rank == 0 or new_rank > 100:
            new_rank = 101  # Use 101 to indicate not in top 100
        
        # Calculate rank difference (negative means improvement)
        if old_rank > 0:
            self.rank_diff_from_last_time = old_rank - new_rank
            
            # Determine rank status
            if new_rank < old_rank:
                self.rank_status = 'up'  # Improved (lower number is better)
            elif new_rank > old_rank:
                self.rank_status = 'down'  # Declined
            else:
                self.rank_status = 'no_change'
        else:
            # First time ranking
            self.rank_status = 'new'
            self.rank_diff_from_last_time = 0
            if self.initial_rank is None or self.initial_rank == 0:
                self.initial_rank = new_rank
        
        # Update current rank
        self.rank = new_rank
        
        # Update rank URL if provided
        if url:
            self.rank_url = url
        
        # Update highest rank (lowest number is best)
        if self.highest_rank == 0 or (new_rank > 0 and new_rank < self.highest_rank):
            self.highest_rank = new_rank
        
        # Calculate impact based on rank change
        self.impact = self.calculate_impact(old_rank, new_rank)
        
        # Update scraped timestamp
        self.scraped_at = timezone.now()
        self.save()
    
    def calculate_impact(self, old_rank, new_rank):
        """Calculate impact based on rank change"""
        if old_rank == 0:
            # New ranking
            if new_rank <= 3:
                return 'high'
            elif new_rank <= 10:
                return 'medium'
            elif new_rank <= 30:
                return 'low'
            else:
                return 'no'
        
        # Calculate change magnitude
        change = abs(old_rank - new_rank)
        
        # Determine impact based on position and change
        if new_rank <= 3:  # Top 3 positions
            if change >= 2:
                return 'high'
            elif change >= 1:
                return 'medium'
        elif new_rank <= 10:  # Top 10
            if old_rank > 10 or change >= 5:  # Entering top 10 or big jump
                return 'high'
            elif change >= 3:
                return 'medium'
            elif change >= 1:
                return 'low'
        elif new_rank <= 30:  # Top 30
            if old_rank > 30 or change >= 15:  # Entering top 30 or huge jump
                return 'high'
            elif change >= 10:
                return 'medium'
            elif change >= 5:
                return 'low'
        else:  # Beyond 30
            if change >= 20:
                return 'medium'
            elif change >= 10:
                return 'low'
        
        return 'no'


class Rank(models.Model):
    keyword = models.ForeignKey(Keyword, on_delete=models.CASCADE, related_name='ranks')
    
    # Ranking data
    rank = models.IntegerField(default=0, db_index=True)
    is_organic = models.BooleanField(default=True)  # True for organic, False for sponsored/ad
    
    # Special result types
    has_map_result = models.BooleanField(default=False)
    has_video_result = models.BooleanField(default=False)
    has_image_result = models.BooleanField(default=False)
    
    # Search results metadata
    search_results_file = models.CharField(max_length=500, blank=True, null=True, help_text='R2 path to parsed JSON results')
    
    # Timestamp
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['keyword', '-created_at']),
            models.Index(fields=['keyword', 'rank']),
            models.Index(fields=['keyword', 'is_organic']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        rank_type = "Organic" if self.is_organic else "Sponsored"
        return f"{rank_type} Rank #{self.rank} for {self.keyword.keyword} on {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    def save(self, *args, **kwargs):
        """Update parent keyword's rank on save"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new and self.keyword:
            # Get URL from the rank record if available
            url = None
            if hasattr(self, '_rank_url'):
                url = self._rank_url
            self.keyword.update_rank(self.rank, url=url)


class Tag(models.Model):
    """Tag model for categorizing keywords - user specific"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tags',
        help_text='User who owns this tag'
    )
    name = models.CharField(max_length=50, db_index=True)
    slug = models.SlugField(max_length=50)
    color = models.CharField(max_length=7, default='#6B7280', help_text='Hex color code')
    description = models.TextField(blank=True, help_text='Optional description for this tag')
    is_active = models.BooleanField(default=True, help_text='Whether this tag is active')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'name']  # Unique per user
        ordering = ['name']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['user', 'slug']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.user.username})"
    
    def save(self, *args, **kwargs):
        """Auto-generate slug from name"""
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.name)
            slug = base_slug
            num = 1
            # Ensure slug is unique for this user
            while Tag.objects.filter(user=self.user, slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{num}"
                num += 1
            self.slug = slug
        super().save(*args, **kwargs)
    
    def get_keyword_count(self):
        """Get count of keywords using this tag"""
        return self.keyword_tags.count()


class KeywordTag(models.Model):
    """Many-to-many relationship between Keywords and Tags"""
    keyword = models.ForeignKey(Keyword, on_delete=models.CASCADE, related_name='keyword_tags')
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name='keyword_tags')
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ['keyword', 'tag']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.keyword.keyword} - {self.tag.name}"
