from django.db import models
from django.core.cache import cache
from django.core.exceptions import ValidationError


class SiteConfiguration(models.Model):
    """
    Model for storing system-wide configuration as key-value pairs.
    Values are stored as text and can be cast to appropriate types when retrieved.
    """
    
    VALUE_TYPE_CHOICES = [
        ('str', 'String'),
        ('int', 'Integer'),
        ('float', 'Float'),
        ('bool', 'Boolean'),
        ('json', 'JSON'),
        ('text', 'Long Text'),
    ]
    
    key = models.CharField(
        max_length=255, 
        unique=True, 
        db_index=True,
        help_text="Unique configuration key (e.g., 'site_name', 'maintenance_mode')"
    )
    value = models.TextField(
        help_text="Configuration value stored as text"
    )
    value_type = models.CharField(
        max_length=10,
        choices=VALUE_TYPE_CHOICES,
        default='str',
        help_text="Data type of the value for proper casting"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of what this configuration does"
    )
    is_sensitive = models.BooleanField(
        default=False,
        help_text="Mark if this contains sensitive data (will be hidden in logs)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Site Configuration'
        verbose_name_plural = 'Site Configurations'
        ordering = ['key']
    
    def __str__(self):
        if self.is_sensitive:
            return f"{self.key} = [HIDDEN]"
        return f"{self.key} = {self.value[:50]}..." if len(self.value) > 50 else f"{self.key} = {self.value}"
    
    def clean(self):
        """Validate value based on value_type"""
        if self.value_type == 'int':
            try:
                int(self.value)
            except ValueError:
                raise ValidationError({'value': 'Value must be a valid integer'})
        elif self.value_type == 'float':
            try:
                float(self.value)
            except ValueError:
                raise ValidationError({'value': 'Value must be a valid float'})
        elif self.value_type == 'bool':
            if self.value.lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                raise ValidationError({'value': 'Value must be a valid boolean (true/false, 1/0, yes/no)'})
        elif self.value_type == 'json':
            import json
            try:
                json.loads(self.value)
            except json.JSONDecodeError:
                raise ValidationError({'value': 'Value must be valid JSON'})
    
    def save(self, *args, **kwargs):
        self.full_clean()
        # Clear cache when configuration changes
        cache_key = f'siteconfig_{self.key}'
        cache.delete(cache_key)
        super().save(*args, **kwargs)
    
    def get_value(self):
        """Get the value cast to the appropriate type"""
        if self.value_type == 'int':
            return int(self.value)
        elif self.value_type == 'float':
            return float(self.value)
        elif self.value_type == 'bool':
            return self.value.lower() in ['true', '1', 'yes']
        elif self.value_type == 'json':
            import json
            return json.loads(self.value)
        return self.value
    
    @classmethod
    def get_config(cls, key, default=None, use_cache=True):
        """
        Get configuration value by key with optional caching.
        
        Args:
            key: Configuration key
            default: Default value if key doesn't exist
            use_cache: Whether to use caching (default: True)
        
        Returns:
            Configuration value cast to appropriate type, or default if not found
        """
        if use_cache:
            cache_key = f'siteconfig_{key}'
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
        
        try:
            config = cls.objects.get(key=key)
            value = config.get_value()
            if use_cache:
                # Cache for 1 hour
                cache.set(f'siteconfig_{key}', value, 3600)
            return value
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_config(cls, key, value, value_type='str', description=''):
        """
        Set or update a configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value (will be converted to string)
            value_type: Type of the value ('str', 'int', 'float', 'bool', 'json', 'text')
            description: Optional description
        
        Returns:
            The created or updated SiteConfiguration instance
        """
        if value_type == 'json':
            import json
            value = json.dumps(value) if not isinstance(value, str) else value
        else:
            value = str(value)
        
        config, created = cls.objects.update_or_create(
            key=key,
            defaults={
                'value': value,
                'value_type': value_type,
                'description': description
            }
        )
        return config
    
    @classmethod
    def bulk_get(cls, keys, use_cache=True):
        """
        Get multiple configuration values at once.
        
        Args:
            keys: List of configuration keys
            use_cache: Whether to use caching
        
        Returns:
            Dictionary of key-value pairs
        """
        result = {}
        for key in keys:
            result[key] = cls.get_config(key, use_cache=use_cache)
        return result
