from django.db import models
from django.utils import timezone


class BacklinkProfile(models.Model):
    """Current backlink profile for a project's domain"""
    project = models.ForeignKey('project.Project', on_delete=models.CASCADE, related_name='backlink_profiles')
    target = models.CharField(max_length=255, help_text="Domain being analyzed")
    
    # Core metrics from DataForSEO result
    rank = models.IntegerField(null=True, blank=True)
    backlinks = models.IntegerField(default=0)
    backlinks_spam_score = models.IntegerField(default=0)
    
    # Link counts
    internal_links_count = models.IntegerField(default=0)
    external_links_count = models.IntegerField(default=0)
    broken_backlinks = models.IntegerField(default=0)
    broken_pages = models.IntegerField(default=0)
    
    # Referring domains
    referring_domains = models.IntegerField(default=0)
    referring_domains_nofollow = models.IntegerField(default=0)
    referring_main_domains = models.IntegerField(default=0)
    referring_main_domains_nofollow = models.IntegerField(default=0)
    referring_ips = models.IntegerField(default=0)
    referring_subnets = models.IntegerField(default=0)
    referring_pages = models.IntegerField(default=0)
    referring_pages_nofollow = models.IntegerField(default=0)
    
    # JSON fields for complex data
    referring_links_tld = models.JSONField(default=dict)
    referring_links_types = models.JSONField(default=dict)
    referring_links_attributes = models.JSONField(default=dict)
    referring_links_platform_types = models.JSONField(default=dict)
    referring_links_semantic_locations = models.JSONField(default=dict)
    referring_links_countries = models.JSONField(default=dict)
    
    # Historical data and file storage
    previous_summary = models.JSONField(default=dict, help_text="Previous summary data before update")
    backlinks_file_path = models.CharField(max_length=500, null=True, blank=True, help_text="R2 path for detailed backlinks file")
    backlinks_collected_at = models.DateTimeField(null=True, blank=True, help_text="When detailed backlinks were last collected")
    backlinks_count_collected = models.IntegerField(default=0, help_text="Number of detailed backlinks collected")
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'backlinks_profile'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', 'target']),
            models.Index(fields=['project', 'rank']),
            models.Index(fields=['project', 'backlinks']),
            models.Index(fields=['created_at']),
        ]
    
    def get_backlinks_file_signed_url(self, expiry_hours: int = 24) -> str:
        """
        Generate a signed URL for accessing the backlinks file in R2
        
        Args:
            expiry_hours: URL expiry time in hours (default 24 hours)
            
        Returns:
            Signed URL string or empty string if no file or error
        """
        if not self.backlinks_file_path:
            return ""
        
        try:
            from services.r2_storage import get_r2_service
            
            r2_service = get_r2_service()
            expiry_seconds = expiry_hours * 3600
            
            result = r2_service.generate_presigned_url(
                key=self.backlinks_file_path,
                expiry=expiry_seconds
            )
            
            if result.get('success'):
                return result.get('url', '')
            else:
                return ""
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating signed URL for backlinks file: {str(e)}")
            return ""
    
    def download_backlinks_data(self) -> dict:
        """
        Download and parse the backlinks data from R2
        
        Returns:
            Parsed backlinks data as dictionary or empty dict if error
        """
        if not self.backlinks_file_path:
            return {}
        
        try:
            from services.r2_storage import get_r2_service
            
            r2_service = get_r2_service()
            data = r2_service.download_json(self.backlinks_file_path)
            
            return data or {}
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error downloading backlinks data: {str(e)}")
            return {}
    
    def get_file_info(self) -> dict:
        """
        Get metadata about the backlinks file in R2
        
        Returns:
            File metadata dict or empty dict if error
        """
        if not self.backlinks_file_path:
            return {}
        
        try:
            from services.r2_storage import get_r2_service
            
            r2_service = get_r2_service()
            info = r2_service.get_file_info(self.backlinks_file_path)
            
            return info or {}
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting backlinks file info: {str(e)}")
            return {}

    def __str__(self):
        return f"{self.target} - {self.project.domain} ({self.backlinks} backlinks)"


