"""
Core storage module for Cloudflare R2
"""

from .r2_backends import (
    BaseR2Storage,
    R2MediaStorage,
    R2StaticStorage,
    R2PrivateStorage,
    R2SearchResultsStorage,
    R2ReportsStorage,
    R2AuditStorage,
    CloudflareR2Storage,
    SiteAuditStorage,
    BaseAuditStorage,
    get_storage_backend,
)

from services.r2_storage import (
    R2StorageService,
    get_r2_service,
)

__all__ = [
    'BaseR2Storage',
    'R2MediaStorage',
    'R2StaticStorage',
    'R2PrivateStorage',
    'R2SearchResultsStorage',
    'R2ReportsStorage',
    'R2AuditStorage',
    'CloudflareR2Storage',
    'SiteAuditStorage',
    'BaseAuditStorage',
    'get_storage_backend',
    'R2StorageService',
    'get_r2_service',
]