"""
Unified Email Service Module for LimeClicks
Consolidates all email functionality into a single, consistent interface
"""

from .service import EmailService, get_email_service
from .backend import BrevoEmailBackend, BrevoTemplateEmailMessage
from .templates import EmailTemplate

__all__ = [
    'EmailService',
    'get_email_service',
    'BrevoEmailBackend',
    'BrevoTemplateEmailMessage',
    'EmailTemplate',
]