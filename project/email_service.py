"""
DEPRECATED: This module has been moved to core.email
This file exists for backward compatibility only.
Please update your imports to use 'from core.email import ...'
"""

import warnings
import logging

# Import from new location
from core.email import get_email_service

logger = logging.getLogger(__name__)

# Create singleton instance
_service = get_email_service()


def send_project_invitation(email, project, inviter, is_existing_user=False, user_name=None, invitation_token=None):
    """
    DEPRECATED: Use EmailService.send_project_invitation() instead
    
    Send project invitation email
    """
    warnings.warn(
        "This function is deprecated. Use EmailService.send_project_invitation() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    return _service.send_project_invitation(
        email=email,
        project=project,
        inviter=inviter,
        is_existing_user=is_existing_user,
        user_name=user_name,
        invitation_token=invitation_token
    )


def send_invitation_accepted_notification(inviter_email, acceptor_name, project):
    """
    DEPRECATED: This function is not yet implemented in the unified service
    
    Send notification when invitation is accepted
    """
    warnings.warn(
        "send_invitation_accepted_notification is deprecated and will be removed.",
        DeprecationWarning,
        stacklevel=2
    )
    
    # For now, just log it
    logger.info(
        f"Invitation acceptance notification would be sent to {inviter_email} "
        f"for {acceptor_name} joining {project.domain}"
    )
    return True