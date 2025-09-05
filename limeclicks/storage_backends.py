"""
DEPRECATED: This module has been moved to core.storage
This file exists for backward compatibility only.
Please update your imports to use 'from core.storage import ...'
"""

# Backward compatibility imports
from core.storage import (
    CloudflareR2Storage,
    BaseAuditStorage,
    SiteAuditStorage,
    BaseR2Storage,
)

__all__ = [
    'CloudflareR2Storage',
    'BaseAuditStorage', 
    'SiteAuditStorage',
    'BaseR2Storage',
]

import warnings
warnings.warn(
    "limeclicks.storage_backends is deprecated. Use core.storage instead.",
    DeprecationWarning,
    stacklevel=2
)