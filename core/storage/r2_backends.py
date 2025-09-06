"""
Unified Cloudflare R2 Storage Backends for Django
Consolidates all R2 storage implementations into a single module
"""

from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings
import re


class BaseR2Storage(S3Boto3Storage):
    """
    Base storage class for Cloudflare R2
    All R2 storage backends should inherit from this
    """
    
    # R2 common settings
    endpoint_url = None
    region_name = 'auto'  # R2 uses 'auto' for region
    signature_version = 's3v4'
    object_parameters = {'CacheControl': 'max-age=86400'}
    
    def __init__(self, *args, **kwargs):
        # Set R2 credentials from settings
        self.bucket_name = getattr(settings, 'R2_BUCKET_NAME', None)
        self.endpoint_url = getattr(settings, 'R2_ENDPOINT_URL', None) or getattr(settings, 'AWS_S3_ENDPOINT_URL', None)
        
        # Set bucket_name in kwargs for parent class
        if 'bucket_name' not in kwargs and self.bucket_name:
            kwargs['bucket_name'] = self.bucket_name
        
        # Set endpoint_url in kwargs for parent class
        if 'endpoint_url' not in kwargs and self.endpoint_url:
            kwargs['endpoint_url'] = self.endpoint_url
        
        # Set credentials
        kwargs['access_key'] = kwargs.get('access_key') or getattr(settings, 'R2_ACCESS_KEY_ID', None) or getattr(settings, 'AWS_ACCESS_KEY_ID', None)
        kwargs['secret_key'] = kwargs.get('secret_key') or getattr(settings, 'R2_SECRET_ACCESS_KEY', None) or getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        
        # Apply R2-specific settings
        kwargs['region_name'] = self.region_name
        kwargs['signature_version'] = self.signature_version
        kwargs['object_parameters'] = self.object_parameters
        
        # R2 doesn't support ACLs like S3
        if 'default_acl' not in kwargs:
            kwargs['default_acl'] = None
            
        super().__init__(*args, **kwargs)
    
    def get_valid_name(self, name):
        """
        Return a valid file name for R2
        Sanitizes the filename to be R2-compatible
        """
        # Handle None case
        if name is None:
            import logging
            logging.error("get_valid_name received None as input")
            return ""
        
        name = super().get_valid_name(name)
        
        # Handle None from parent
        if name is None:
            import logging
            logging.error("Parent get_valid_name returned None")
            return ""
        
        # Keep only alphanumeric, dash, underscore, forward slash, and dots
        name = re.sub(r'[^a-zA-Z0-9\-_./]', '_', name)
        return name


class R2MediaStorage(BaseR2Storage):
    """
    Storage backend for media files in R2
    Used for user-uploaded content like images, documents, etc.
    """
    location = 'media'
    file_overwrite = False
    default_acl = None  # Private by default
    custom_domain = False
    querystring_auth = True  # Generate signed URLs for private media
    querystring_expire = 3600  # 1 hour expiration


class R2StaticStorage(BaseR2Storage):
    """
    Storage backend for static files in R2
    Used for CSS, JS, and other static assets
    """
    location = 'static'
    file_overwrite = True  # Static files can be overwritten
    default_acl = 'public-read'  # Static files are public
    custom_domain = True  # Use custom domain if configured


class R2PrivateStorage(BaseR2Storage):
    """
    Storage backend for private files in R2
    Requires authentication to access
    """
    location = 'private'
    file_overwrite = False
    default_acl = None  # Always private
    custom_domain = False  # Don't use custom domain for private files
    querystring_auth = True  # Always generate signed URLs
    querystring_expire = 3600  # 1 hour expiration for signed URLs


class R2SearchResultsStorage(BaseR2Storage):
    """
    Storage backend for search results and scraped data
    Used for storing SERP data, crawl results, etc.
    """
    location = 'search-results'
    file_overwrite = False
    default_acl = None  # Private
    custom_domain = False
    querystring_auth = True
    querystring_expire = 86400  # 24 hours expiration


class R2ReportsStorage(BaseR2Storage):
    """
    Storage backend for generated reports
    Used for PDF, CSV, and other report files
    """
    location = 'reports'
    file_overwrite = False
    default_acl = None  # Private
    custom_domain = False
    querystring_auth = True
    querystring_expire = 7200  # 2 hours expiration


class R2AuditStorage(BaseR2Storage):
    """
    Storage backend for site audit files
    Used for storing audit JSON data and results
    """
    location = 'audits'
    file_overwrite = False
    default_acl = None  # Private
    custom_domain = False
    querystring_auth = True
    querystring_expire = 3600  # 1 hour expiration
    file_extension = '.json'
    
    def get_valid_name(self, name):
        """Ensure the file has the correct extension for audit files"""
        name = super().get_valid_name(name)
        if self.file_extension and not name.endswith(self.file_extension):
            name += self.file_extension
        return name


# Aliases for backward compatibility
CloudflareR2Storage = BaseR2Storage  # Main alias for existing code
SiteAuditStorage = R2AuditStorage  # Specific alias for site audit
BaseAuditStorage = R2AuditStorage  # Legacy alias


# Helper function to get storage instance
def get_storage_backend(storage_type='media'):
    """
    Get appropriate storage backend instance
    
    Args:
        storage_type: Type of storage needed ('media', 'static', 'private', 'search', 'reports', 'audit')
    
    Returns:
        Storage backend instance
    """
    storage_map = {
        'media': R2MediaStorage,
        'static': R2StaticStorage,
        'private': R2PrivateStorage,
        'search': R2SearchResultsStorage,
        'reports': R2ReportsStorage,
        'audit': R2AuditStorage,
    }
    
    storage_class = storage_map.get(storage_type, R2MediaStorage)
    return storage_class()