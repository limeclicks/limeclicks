from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
import re


class Project(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    domain = models.CharField(max_length=255)
    title = models.CharField(max_length=255, blank=True, null=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_favicon_url(self, size=64):
        """Get Google favicon URL for this domain"""
        return f"https://www.google.com/s2/favicons?domain={self.domain}&sz={size}"
    
    def get_cached_favicon_url(self, size=64):
        """Get cached favicon URL using our proxy (reduces Google API calls)"""
        from django.urls import reverse
        return reverse('project:favicon_proxy', kwargs={'domain': self.domain}) + f'?size={size}'

    def __str__(self):
        return f"{self.domain} - {self.title or 'Untitled'}"

    class Meta:
        ordering = ['-created_at']
