"""
DEPRECATED: This module has been moved to core.email
This file exists for backward compatibility only.
Please update your imports to use 'from core.email import ...'
"""

import warnings
from typing import Dict, List, Any

# Import from new location
from core.email import EmailService, get_email_service, EmailTemplate

# Create singleton instance for backward compatibility
_service = get_email_service()


def send_brevo_email(email_data: Dict[str, Any]) -> bool:
    """
    DEPRECATED: Use EmailService.send_template_email() instead
    
    Send email via Brevo API using templates
    
    Args:
        email_data: Dictionary containing email parameters
        
    Returns:
        True if email sent successfully
    """
    warnings.warn(
        "send_brevo_email is deprecated. Use EmailService.send_template_email() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    # Extract parameters
    to_emails = email_data.get('to', [])
    template_id = email_data.get('templateId')
    params = email_data.get('params', {})
    
    if not to_emails or not template_id:
        return False
    
    # Convert recipient format
    if isinstance(to_emails[0], dict):
        to_emails = [r.get('email') for r in to_emails if r.get('email')]
    
    # Send using new service
    return _service.send_template_email(
        to_emails=to_emails,
        template_id=template_id,
        template_params=params,
        validate=False  # Don't validate for backward compatibility
    )


def send_report_notification(
    recipient_email: str,
    recipient_name: str,
    report_name: str,
    template_id: int = 6
) -> bool:
    """
    DEPRECATED: Use EmailService.send_report_notification() instead
    
    Send report ready notification
    """
    warnings.warn(
        "This function is deprecated. Use EmailService.send_report_notification() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    return _service.send_report_notification(
        recipient_email=recipient_email,
        recipient_name=recipient_name,
        report_name=report_name
    )


def send_batch_emails(
    recipients: List[Dict[str, str]],
    template_id: int,
    params: Dict[str, Any]
) -> Dict[str, int]:
    """
    DEPRECATED: Use EmailService.send_batch_emails() instead
    
    Send emails to multiple recipients
    """
    warnings.warn(
        "This function is deprecated. Use EmailService.send_batch_emails() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    return _service.send_batch_emails(
        recipients=recipients,
        template_id=template_id,
        params=params,
        validate=False
    )