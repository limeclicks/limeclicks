from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings


class CloudflareR2Storage(S3Boto3Storage):
    """Custom storage backend for Cloudflare R2"""
    
    def __init__(self, *args, **kwargs):
        # Use AWS settings which are configured for R2
        kwargs['region_name'] = 'auto'
        kwargs['signature_version'] = 's3v4'
        kwargs['object_parameters'] = {
            'CacheControl': 'max-age=86400',
        }
        kwargs['file_overwrite'] = False
        kwargs['default_acl'] = None  # R2 doesn't support ACLs
        super().__init__(*args, **kwargs)


class LighthouseAuditStorage(CloudflareR2Storage):
    """Storage specifically for Lighthouse audit JSON files with proper directory structure"""
    file_overwrite = False
    
    def get_valid_name(self, name):
        """Ensure the file has a .json extension"""
        if not name.endswith('.json'):
            name += '.json'
        return super().get_valid_name(name)


class OnPageAuditStorage(CloudflareR2Storage):
    """Storage specifically for OnPage audit JSON files with proper directory structure"""
    file_overwrite = False
    
    def get_valid_name(self, name):
        """Ensure the file has a .json extension"""
        if not name.endswith('.json'):
            name += '.json'
        return super().get_valid_name(name)


# Legacy storage classes for backward compatibility
class AuditJSONStorage(LighthouseAuditStorage):
    """Legacy storage class - use LighthouseAuditStorage instead"""
    pass


class AuditHTMLStorage(CloudflareR2Storage):
    """Legacy storage class - no longer used, keeping for compatibility"""
    location = 'audits/html'
    file_overwrite = False