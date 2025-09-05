"""
DEPRECATED: This module has been moved to core.email
This file exists for backward compatibility only.
Please update your imports to use 'from core.email import ...'
"""

import warnings

# Import from new location  
from core.email.backend import (
    BrevoEmailBackend as _BrevoEmailBackend,
    BrevoTemplateEmailMessage as _BrevoTemplateEmailMessage
)


class BrevoTemplateEmailMessage(_BrevoTemplateEmailMessage):
    """
    DEPRECATED: Use core.email.BrevoTemplateEmailMessage instead
    """
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "accounts.email_backend.BrevoTemplateEmailMessage is deprecated. "
            "Use core.email.BrevoTemplateEmailMessage instead.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(*args, **kwargs)


class BrevoEmailBackend(_BrevoEmailBackend):
    """
    DEPRECATED: Use core.email.BrevoEmailBackend instead
    """
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "accounts.email_backend.BrevoEmailBackend is deprecated. "
            "Use core.email.BrevoEmailBackend instead.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(*args, **kwargs)