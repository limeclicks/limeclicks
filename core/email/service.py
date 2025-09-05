"""
Unified Email Service for LimeClicks
Provides a single interface for all email operations
"""

import logging
from typing import Dict, List, Optional, Any
from django.conf import settings
from django.urls import reverse

from .backend import BrevoEmailBackend
from .templates import EmailTemplate, TemplateConfig

logger = logging.getLogger(__name__)


class EmailService:
    """
    Unified email service that consolidates all email functionality
    """
    
    def __init__(self, backend: Optional[BrevoEmailBackend] = None):
        """
        Initialize email service
        
        Args:
            backend: Email backend to use (defaults to BrevoEmailBackend)
        """
        self.backend = backend or BrevoEmailBackend()
        self.site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')
    
    def send_template_email(self, to_emails: List[str], template_id: EmailTemplate,
                          template_params: Dict[str, Any],
                          from_email: Optional[str] = None,
                          validate: bool = True, **kwargs) -> bool:
        """
        Send email using a Brevo template
        
        Args:
            to_emails: List of recipient email addresses
            template_id: EmailTemplate enum value
            template_params: Template parameters
            from_email: Sender email (optional)
            validate: Whether to validate template parameters
            **kwargs: Additional options (cc, bcc, reply_to)
            
        Returns:
            True if email sent successfully
        """
        try:
            # Validate parameters if requested
            if validate:
                TemplateConfig.validate_params(template_id, template_params)
            
            # Convert single email to list
            if isinstance(to_emails, str):
                to_emails = [to_emails]
            
            # Send via backend
            success = self.backend.send_template_email(
                to_emails=to_emails,
                template_id=int(template_id),
                template_params=template_params,
                from_email=from_email,
                **kwargs
            )
            
            if success:
                logger.info(
                    f"Sent template email {template_id.name} to {to_emails}"
                )
            else:
                logger.error(
                    f"Failed to send template email {template_id.name} to {to_emails}"
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending template email: {e}", exc_info=True)
            return False
    
    def send_report_notification(self, recipient_email: str, recipient_name: str,
                                report_name: str, report_url: Optional[str] = None,
                                report_type: Optional[str] = None) -> bool:
        """
        Send report ready notification
        
        Args:
            recipient_email: Email address to send to
            recipient_name: Name of recipient
            report_name: Name of the report
            report_url: Optional URL to view the report
            report_type: Optional type of report
            
        Returns:
            True if sent successfully
        """
        params = {
            'report_name': report_name,
            'recipient_name': recipient_name
        }
        
        if report_url:
            params['report_url'] = report_url
        if report_type:
            params['report_type'] = report_type
        
        return self.send_template_email(
            to_emails=[recipient_email],
            template_id=EmailTemplate.REPORT_READY,
            template_params=params
        )
    
    def send_project_invitation(self, email: str, project: Any, inviter: Any,
                               is_existing_user: bool = False,
                               user_name: Optional[str] = None,
                               invitation_token: Optional[str] = None) -> bool:
        """
        Send project invitation email
        
        Args:
            email: Recipient email address
            project: Project instance
            inviter: User who sent the invitation
            is_existing_user: Whether recipient is an existing user
            user_name: Name of existing user
            invitation_token: Invitation token for new users
            
        Returns:
            True if sent successfully
        """
        try:
            if is_existing_user:
                # Existing user invitation
                template_id = EmailTemplate.EXISTING_USER_INVITATION
                params = {
                    'name': user_name or email.split('@')[0],
                    'project': project.domain,
                    'inviter_name': inviter.get_full_name() or inviter.username
                }
            else:
                # New user invitation
                if not invitation_token:
                    raise ValueError("Invitation token required for new user invitations")
                
                template_id = EmailTemplate.NEW_USER_INVITATION
                
                # Build registration link
                reg_link = f"{self.site_url}{reverse('project:accept_invitation', kwargs={'token': invitation_token})}"
                
                params = {
                    'project': project.domain,
                    'reg_link': reg_link,
                    'inviter_name': inviter.get_full_name() or inviter.username
                }
            
            success = self.send_template_email(
                to_emails=[email],
                template_id=template_id,
                template_params=params
            )
            
            if success:
                logger.info(
                    f"Sent invitation to {email} for project {project.domain}"
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send invitation to {email}: {e}")
            return False
    
    def send_batch_emails(self, recipients: List[Dict[str, str]],
                        template_id: EmailTemplate,
                        params: Dict[str, Any],
                        validate: bool = True) -> Dict[str, int]:
        """
        Send emails to multiple recipients using the same template
        
        Args:
            recipients: List of dicts with 'email' and optional 'name'
            template_id: EmailTemplate enum value
            params: Template parameters
            validate: Whether to validate template parameters
            
        Returns:
            Dict with 'sent' and 'failed' counts
        """
        sent = 0
        failed = 0
        
        # Validate once for all emails
        if validate:
            try:
                TemplateConfig.validate_params(template_id, params)
            except ValueError as e:
                logger.error(f"Invalid template parameters: {e}")
                return {'sent': 0, 'failed': len(recipients)}
        
        for recipient in recipients:
            email = recipient.get('email')
            if not email:
                failed += 1
                continue
            
            # Personalize params if recipient has a name
            personalized_params = params.copy()
            if 'name' in recipient:
                personalized_params['recipient_name'] = recipient['name']
            
            if self.send_template_email(
                to_emails=[email],
                template_id=template_id,
                template_params=personalized_params,
                validate=False  # Already validated
            ):
                sent += 1
            else:
                failed += 1
        
        logger.info(f"Batch email results: {sent} sent, {failed} failed")
        
        return {
            'sent': sent,
            'failed': failed,
            'total': len(recipients)
        }
    
    def send_regular_email(self, to_emails: List[str], subject: str,
                         body: str, html_body: Optional[str] = None,
                         from_email: Optional[str] = None,
                         **kwargs) -> bool:
        """
        Send a regular (non-template) email
        
        Args:
            to_emails: List of recipient emails
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
            from_email: Sender email
            **kwargs: Additional options (cc, bcc, reply_to)
            
        Returns:
            True if sent successfully
        """
        try:
            # Convert single email to list
            if isinstance(to_emails, str):
                to_emails = [to_emails]
            
            # Use backend's regular email method
            success = self.backend._send_regular_email(
                to_emails=to_emails,
                subject=subject,
                body=body,
                html_content=html_body,
                from_email=from_email,
                **kwargs
            )
            
            if success:
                logger.info(f"Sent regular email to {to_emails}")
            else:
                logger.error(f"Failed to send regular email to {to_emails}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending regular email: {e}", exc_info=True)
            return False


# Singleton instance
_email_service = None


def get_email_service() -> EmailService:
    """
    Get singleton instance of EmailService
    
    Returns:
        EmailService instance
    """
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service