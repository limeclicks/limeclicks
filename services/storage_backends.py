"""
Django Storage Backends for Cloudflare R2
"""

from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings


class R2MediaStorage(S3Boto3Storage):
    """
    Storage backend for media files in R2
    """
    bucket_name = settings.R2_BUCKET_NAME
    endpoint_url = settings.R2_ENDPOINT_URL
    region_name = 'auto'
    signature_version = 's3v4'
    file_overwrite = False
    default_acl = None
    location = 'media'
    
    def __init__(self, *args, **kwargs):
        kwargs['access_key'] = settings.R2_ACCESS_KEY_ID
        kwargs['secret_key'] = settings.R2_SECRET_ACCESS_KEY
        super().__init__(*args, **kwargs)


class R2StaticStorage(S3Boto3Storage):
    """
    Storage backend for static files in R2
    """
    bucket_name = settings.R2_BUCKET_NAME
    endpoint_url = settings.R2_ENDPOINT_URL
    region_name = 'auto'
    signature_version = 's3v4'
    file_overwrite = True
    default_acl = 'public-read'
    location = 'static'
    
    def __init__(self, *args, **kwargs):
        kwargs['access_key'] = settings.R2_ACCESS_KEY_ID
        kwargs['secret_key'] = settings.R2_SECRET_ACCESS_KEY
        super().__init__(*args, **kwargs)


class R2PrivateStorage(S3Boto3Storage):
    """
    Storage backend for private files in R2 (requires authentication)
    """
    bucket_name = settings.R2_BUCKET_NAME
    endpoint_url = settings.R2_ENDPOINT_URL
    region_name = 'auto'
    signature_version = 's3v4'
    file_overwrite = False
    default_acl = 'private'
    location = 'private'
    custom_domain = False  # Don't use custom domain for private files
    querystring_auth = True  # Generate signed URLs
    querystring_expire = 3600  # 1 hour expiration for signed URLs
    
    def __init__(self, *args, **kwargs):
        kwargs['access_key'] = settings.R2_ACCESS_KEY_ID
        kwargs['secret_key'] = settings.R2_SECRET_ACCESS_KEY
        super().__init__(*args, **kwargs)


class R2SearchResultsStorage(S3Boto3Storage):
    """
    Storage backend specifically for search results and scraped data
    """
    bucket_name = settings.R2_BUCKET_NAME
    endpoint_url = settings.R2_ENDPOINT_URL
    region_name = 'auto'
    signature_version = 's3v4'
    file_overwrite = False
    default_acl = 'private'
    location = 'search-results'
    custom_domain = False
    querystring_auth = True
    querystring_expire = 86400  # 24 hours expiration
    
    def __init__(self, *args, **kwargs):
        kwargs['access_key'] = settings.R2_ACCESS_KEY_ID
        kwargs['secret_key'] = settings.R2_SECRET_ACCESS_KEY
        super().__init__(*args, **kwargs)
    
    def get_valid_name(self, name):
        """
        Return a valid file name for R2
        """
        # Replace spaces with underscores and remove special characters
        import re
        name = super().get_valid_name(name)
        # Keep only alphanumeric, dash, underscore, and dots
        name = re.sub(r'[^a-zA-Z0-9\-_./]', '_', name)
        return name