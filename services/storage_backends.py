"""
DEPRECATED: This module has been moved to core.storage
This file exists for backward compatibility only.
Please update your imports to use 'from core.storage import ...'
"""

# Backward compatibility imports
from core.storage import (
    R2MediaStorage,
    R2StaticStorage,
    R2PrivateStorage,
    R2SearchResultsStorage,
)

__all__ = [
    'R2MediaStorage',
    'R2StaticStorage',
    'R2PrivateStorage',
    'R2SearchResultsStorage',
]

import warnings
warnings.warn(
    "services.storage_backends is deprecated. Use core.storage instead.",
    DeprecationWarning,
    stacklevel=2
)