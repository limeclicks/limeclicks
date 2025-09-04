from django.db import models
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
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
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('critical', 'Critical'),
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
    next_crawl_at = models.DateTimeField(null=True, blank=True, db_index=True, help_text='Next scheduled crawl time')
    last_force_crawl_at = models.DateTimeField(null=True, blank=True, help_text='Last time force crawl was used')
    crawl_priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal', db_index=True)
    crawl_interval_hours = models.IntegerField(default=24, help_text='Hours between automatic crawls')
    force_crawl_count = models.IntegerField(default=0, help_text='Number of times force crawl was used')
    scrape_do_file_path = models.CharField(max_length=500, blank=True, null=True, help_text='Latest HTML file path')
    scrape_do_files = models.JSONField(default=list, blank=True, help_text='Ordered list of HTML files, latest first')
    scrape_do_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default='')
    last_error_message = models.CharField(max_length=255, blank=True, null=True, help_text='Minimal error message')
    success_api_hit_count = models.IntegerField(default=0)
    failed_api_hit_count = models.IntegerField(default=0)
    
    # Top ranking pages (stored as JSON array)
    ranking_pages = models.JSONField(
        default=list, 
        blank=True, 
        help_text='Top 3 ranking pages with URL and position'
    )
    
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
            models.Index(fields=['crawl_priority', 'next_crawl_at']),
            models.Index(fields=['next_crawl_at', 'processing']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.keyword} - {self.project.domain} ({self.country})"
    
    def update_rank(self, new_rank, url=None, from_rank_save=False):
        """Update rank and calculate differences
        
        Args:
            new_rank: The new rank position
            url: Optional URL where the site was found
            from_rank_save: Internal flag - when True, skip updating scraped_at as it's managed by the task
        """
        # Get the previous rank from history (not current rank)
        # This ensures we compare against the actual previous rank
        from .models import Rank  # Import here to avoid circular import
        
        # Get the latest rank that's not from today to compare against
        current_ranks = Rank.objects.filter(
            keyword=self,
            created_at__date=timezone.now().date()
        ).values_list('id', flat=True)
        
        previous_rank = Rank.objects.filter(
            keyword=self
        ).exclude(
            id__in=current_ranks  # Exclude today's ranks
        ).order_by('-created_at').first()
        
        # If no previous rank excluding today, just get the previous one
        if not previous_rank:
            previous_rank = Rank.objects.filter(
                keyword=self
            ).order_by('-created_at')[1:2].first()  # Skip the most recent, get the second
        
        old_rank = previous_rank.rank if previous_rank else 0
        
        # Handle not found in top 100 case
        if new_rank == 0 or new_rank > 100:
            new_rank = 101  # Use 101 to indicate not in top 100
        
        # Calculate rank difference (positive means improvement in ranking)
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
        
        # Update scraped timestamp and schedule next crawl (skip if called from Rank save)
        if not from_rank_save:
            self.scraped_at = timezone.now()
            self.next_crawl_at = self.scraped_at + timedelta(hours=self.crawl_interval_hours)
        else:
            # Still update next_crawl_at based on existing scraped_at
            if self.scraped_at:
                self.next_crawl_at = self.scraped_at + timedelta(hours=self.crawl_interval_hours)
        
        # Reset priority to normal after successful crawl (unless it was forced)
        if self.crawl_priority == 'high' and old_rank == 0:
            # Keep high priority for new keywords for a bit
            pass
        elif self.crawl_priority == 'critical':
            # Reset critical priority after force crawl
            self.crawl_priority = 'normal'
        
        # Mark as not processing
        self.processing = False
        
        self.save()
    
    def should_crawl(self):
        """Check if keyword should be crawled based on schedule"""
        now = timezone.now()
        
        # Never crawled - high priority
        if not self.scraped_at:
            return True
        
        # Check if next crawl time has passed
        if self.next_crawl_at and now >= self.next_crawl_at:
            return True
        
        # Check if 24 hours have passed (fallback)
        hours_since_last = (now - self.scraped_at).total_seconds() / 3600
        if hours_since_last >= self.crawl_interval_hours:
            return True
        
        return False
    
    def can_force_crawl(self):
        """Check if force crawl is allowed (once per hour limit)"""
        if not self.last_force_crawl_at:
            return True
        
        now = timezone.now()
        hours_since_last = (now - self.last_force_crawl_at).total_seconds() / 3600
        return hours_since_last >= 1.0
    
    def schedule_next_crawl(self):
        """Schedule the next crawl based on priority and interval"""
        if not self.scraped_at:
            # First time crawl - set to now for immediate crawling
            self.next_crawl_at = timezone.now()
            self.crawl_priority = 'high'  # High priority for first-time keywords
        else:
            # Calculate next crawl time based on interval
            self.next_crawl_at = self.scraped_at + timedelta(hours=self.crawl_interval_hours)
        
        self.save(update_fields=['next_crawl_at', 'crawl_priority'])
    
    def force_crawl(self):
        """Force an immediate crawl if allowed"""
        if not self.can_force_crawl():
            raise ValueError("Force crawl not allowed yet. Please wait 1 hour between force crawls.")
        
        now = timezone.now()
        self.last_force_crawl_at = now
        self.force_crawl_count += 1
        self.next_crawl_at = now  # Set to now for immediate crawling
        self.crawl_priority = 'critical'  # Highest priority for forced crawls
        self.save(update_fields=['last_force_crawl_at', 'force_crawl_count', 'next_crawl_at', 'crawl_priority'])
        
        return True
    
    def get_crawl_priority_value(self):
        """Get numeric priority value for ordering (higher = more important)"""
        priority_values = {
            'critical': 4,
            'high': 3,
            'normal': 2,
            'low': 1,
        }
        return priority_values.get(self.crawl_priority, 2)
    
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
            # Pass from_rank_save=True to prevent circular calls
            self.keyword.update_rank(self.rank, url=url, from_rank_save=True)


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
        # Validate that name is not empty or whitespace only
        if not self.name or not self.name.strip():
            raise ValueError("Tag name cannot be empty")
        
        # Clean the name
        self.name = self.name.strip()
        
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


# Import report models
from .models_reports import KeywordReport, ReportSchedule
