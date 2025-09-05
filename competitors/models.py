from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from project.models import Project
from keywords.models import Keyword


class Target(models.Model):
    """Competitor target domain for tracking rankings"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='targets')
    domain = models.CharField(max_length=255, help_text="Competitor domain to track (e.g., example.com)")
    name = models.CharField(max_length=255, blank=True, help_text="Optional name for this competitor")
    is_manual = models.BooleanField(default=True, help_text="True if manually added by user")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        unique_together = ['project', 'domain']
        ordering = ['domain']
    
    @staticmethod
    def clean_domain_string(domain):
        """Clean a domain string - remove protocol, www, path, etc."""
        from core.utils import clean_domain_string
        return clean_domain_string(domain)
    
    def clean(self):
        # Clean domain using the static method
        if self.domain:
            self.domain = self.clean_domain_string(self.domain)
            
            # Validate domain has at least one dot
            if '.' not in self.domain:
                raise ValidationError("Please enter a valid domain name (e.g., example.com)")
            
            # Check target limit (max 3 manual targets per project)
            if self.is_manual and not self.pk:  # Only check for new manual targets
                existing_count = Target.objects.filter(
                    project=self.project,
                    is_manual=True
                ).count()
                if existing_count >= 3:
                    raise ValidationError("Maximum 3 targets allowed per project")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name or self.domain} (Target for {self.project.domain})"


class TargetKeywordRank(models.Model):
    """Store ranking data for target domains on specific keywords"""
    target = models.ForeignKey(Target, on_delete=models.CASCADE, related_name='keyword_ranks')
    keyword = models.ForeignKey(Keyword, on_delete=models.CASCADE, related_name='target_ranks')
    rank = models.IntegerField(default=0, help_text="0 means not ranking")
    rank_url = models.URLField(max_length=500, blank=True, null=True)
    scraped_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['target', 'keyword']
        ordering = ['-scraped_at']
        indexes = [
            models.Index(fields=['target', 'keyword']),
            models.Index(fields=['keyword', 'rank']),
        ]
    
    def __str__(self):
        return f"{self.target.domain} - {self.keyword.keyword}: Rank {self.rank}"