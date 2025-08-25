from django.db import models
from django.utils import timezone
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
    
    # Ranking fields
    rank = models.IntegerField(default=0, db_index=True)
    on_map = models.BooleanField(default=False)
    rank_status = models.CharField(max_length=20, choices=RANK_STATUS_CHOICES, default='no_change')
    rank_diff_from_last_time = models.IntegerField(default=0)
    rank_url = models.URLField(max_length=500, blank=True, null=True)
    number_of_results = models.BigIntegerField(default=0)
    initial_rank = models.IntegerField(default=0)
    highest_rank = models.IntegerField(default=0)
    
    # Scraping fields
    scraped_at = models.DateTimeField(null=True, blank=True, db_index=True)
    scrape_do_files = models.JSONField(default=list, blank=True)
    scrape_do_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default='')
    success_api_hit_count = models.IntegerField(default=0)
    failed_api_hit_count = models.IntegerField(default=0)
    
    # Management fields
    impact = models.CharField(max_length=20, choices=IMPACT_CHOICES, default='no')
    tags = models.JSONField(default=list, blank=True)
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
    
    def update_rank(self, new_rank):
        """Update rank and calculate differences"""
        if self.rank > 0:
            self.rank_diff_from_last_time = self.rank - new_rank
            if new_rank < self.rank:
                self.rank_status = 'up'
            elif new_rank > self.rank:
                self.rank_status = 'down'
            else:
                self.rank_status = 'no_change'
        else:
            self.rank_status = 'new'
            self.initial_rank = new_rank
        
        self.rank = new_rank
        
        # Update highest rank
        if self.highest_rank == 0 or new_rank < self.highest_rank:
            self.highest_rank = new_rank
        
        self.scraped_at = timezone.now()
        self.save()


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
    search_results_file = models.CharField(max_length=255, blank=True, null=True)
    number_of_results = models.BigIntegerField(default=0)
    
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
            self.keyword.update_rank(self.rank)
