"""
Django Email Backend for Brevo (formerly Sendinblue)
Supports both template-based and regular emails
"""

import os
import logging
from typing import List, Dict, Any, Optional

from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail import EmailMessage
from django.conf import settings

try:
    import brevo_python
    from brevo_python.rest import ApiException
    HAS_BREVO_SDK = True
except ImportError:
    HAS_BREVO_SDK = False

logger = logging.getLogger(__name__)


class BrevoTemplateEmailMessage(EmailMessage):
    """
    Custom EmailMessage class for Brevo template emails
    """
    def __init__(self, template_id: int, template_params: Dict[str, Any], 
                 to: List[str] = None, from_email: str = None, **kwargs):
        super().__init__(to=to, from_email=from_email, **kwargs)
        self.template_id = template_id
        self.template_params = template_params


class BrevoEmailBackend(BaseEmailBackend):
    """
    Django email backend for Brevo API integration
    Supports both SDK and HTTP methods for flexibility
    """
    
    def __init__(self, fail_silently: bool = False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        
        # Get API key from settings or environment
        self.api_key = (
            getattr(settings, 'BREVO_API_KEY', None) or 
            os.getenv('BREVO_API_KEY')
        )
        
        if not self.api_key:
            logger.warning("Brevo API key not configured")
        
        # Default sender email
        self.default_from_email = (
            getattr(settings, 'DEFAULT_FROM_EMAIL', None) or
            "noreply@limeclicks.com"
        )
        
        # Initialize SDK client if available
        self.api_instance = None
        if HAS_BREVO_SDK and self.api_key:
            try:
                configuration = brevo_python.Configuration()
                configuration.api_key['api-key'] = self.api_key
                self.api_instance = brevo_python.TransactionalEmailsApi(
                    brevo_python.ApiClient(configuration)
                )
            except Exception as e:
                logger.error(f"Failed to initialize Brevo SDK: {e}")
    
    def send_messages(self, email_messages: List[EmailMessage]) -> int:
        """
        Send email messages using Brevo API
        
        Args:
            email_messages: List of EmailMessage objects
            
        Returns:
            Number of successfully sent emails
        """
        if not email_messages:
            return 0
        
        if not self.api_key:
            if not self.fail_silently:
                raise ValueError("Brevo API key not configured")
            return 0
        
        sent_count = 0
        
        for message in email_messages:
            try:
                # Check if this is a template email
                template_id = getattr(message, 'template_id', None)
                template_params = getattr(message, 'template_params', {})
                
                if template_id:
                    # Send template email
                    success = self._send_template_email(
                        to_emails=message.to,
                        template_id=template_id,
                        template_params=template_params,
                        from_email=message.from_email,
                        cc=getattr(message, 'cc', None),
                        bcc=getattr(message, 'bcc', None),
                        reply_to=getattr(message, 'reply_to', None)
                    )
                else:
                    # Send regular email
                    success = self._send_regular_email(
                        to_emails=message.to,
                        subject=message.subject,
                        body=message.body,
                        from_email=message.from_email,
                        cc=getattr(message, 'cc', None),
                        bcc=getattr(message, 'bcc', None),
                        reply_to=getattr(message, 'reply_to', None),
                        html_content=getattr(message, 'html_content', None)
                    )
                
                if success:
                    sent_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to send email: {e}")
                if not self.fail_silently:
                    raise e
        
        return sent_count
    
    def _send_template_email(self, to_emails: List[str], template_id: int,
                            template_params: Dict[str, Any],
                            from_email: str = None,
                            cc: List[str] = None,
                            bcc: List[str] = None,
                            reply_to: str = None) -> bool:
        """
        Send template-based email using Brevo API
        """
        if HAS_BREVO_SDK and self.api_instance:
            # Use SDK method
            try:
                send_smtp_email = brevo_python.SendSmtpEmail(
                    to=[{"email": email} for email in to_emails],
                    template_id=template_id,
                    params=template_params,
                    sender={"email": from_email or self.default_from_email}
                )
                
                # Add optional fields
                if cc:
                    send_smtp_email.cc = [{"email": email} for email in cc]
                if bcc:
                    send_smtp_email.bcc = [{"email": email} for email in bcc]
                if reply_to:
                    send_smtp_email.reply_to = {"email": reply_to}
                
                self.api_instance.send_transac_email(send_smtp_email)
                logger.info(f"Successfully sent template email {template_id} to {to_emails}")
                return True
                
            except (ApiException, Exception) as e:
                logger.error(f"Failed to send template email via SDK: {e}")
                if not self.fail_silently:
                    raise e
                return False
        else:
            # Use HTTP fallback method
            return self._send_via_http(
                to_emails=to_emails,
                template_id=template_id,
                template_params=template_params,
                from_email=from_email,
                cc=cc,
                bcc=bcc,
                reply_to=reply_to
            )
    
    def _send_regular_email(self, to_emails: List[str], subject: str,
                           body: str, from_email: str = None,
                           cc: List[str] = None, bcc: List[str] = None,
                           reply_to: str = None,
                           html_content: str = None) -> bool:
        """
        Send regular (non-template) email
        """
        if HAS_BREVO_SDK and self.api_instance:
            # Use SDK method
            try:
                send_smtp_email = brevo_python.SendSmtpEmail(
                    to=[{"email": email} for email in to_emails],
                    subject=subject,
                    sender={"email": from_email or self.default_from_email}
                )
                
                # Set content
                if html_content:
                    send_smtp_email.html_content = html_content
                else:
                    send_smtp_email.text_content = body
                
                # Add optional fields
                if cc:
                    send_smtp_email.cc = [{"email": email} for email in cc]
                if bcc:
                    send_smtp_email.bcc = [{"email": email} for email in bcc]
                if reply_to:
                    send_smtp_email.reply_to = {"email": reply_to}
                
                self.api_instance.send_transac_email(send_smtp_email)
                logger.info(f"Successfully sent email to {to_emails}")
                return True
                
            except (ApiException, Exception) as e:
                logger.error(f"Failed to send regular email via SDK: {e}")
                if not self.fail_silently:
                    raise e
                return False
        else:
            # Use HTTP fallback
            return self._send_via_http(
                to_emails=to_emails,
                subject=subject,
                body=body,
                html_content=html_content,
                from_email=from_email,
                cc=cc,
                bcc=bcc,
                reply_to=reply_to
            )
    
    def _send_via_http(self, to_emails: List[str], template_id: int = None,
                      template_params: Dict = None, subject: str = None,
                      body: str = None, html_content: str = None,
                      from_email: str = None, cc: List[str] = None,
                      bcc: List[str] = None, reply_to: str = None) -> bool:
        """
        Fallback HTTP method for sending emails via Brevo API
        """
        try:
            import requests
            
            url = "https://api.brevo.com/v3/smtp/email"
            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "api-key": self.api_key
            }
            
            # Build payload
            payload = {
                "to": [{"email": email} for email in to_emails],
                "sender": {"email": from_email or self.default_from_email}
            }
            
            # Add template or content
            if template_id:
                payload["templateId"] = template_id
                if template_params:
                    payload["params"] = template_params
            else:
                if subject:
                    payload["subject"] = subject
                if html_content:
                    payload["htmlContent"] = html_content
                elif body:
                    payload["textContent"] = body
            
            # Add optional fields
            if cc:
                payload["cc"] = [{"email": email} for email in cc]
            if bcc:
                payload["bcc"] = [{"email": email} for email in bcc]
            if reply_to:
                payload["replyTo"] = {"email": reply_to}
            
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 201:
                logger.info(f"Successfully sent email via HTTP to {to_emails}")
                return True
            else:
                logger.error(f"HTTP email send failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send email via HTTP: {e}")
            if not self.fail_silently:
                raise e
            return False
    
    # Convenience method for direct template email sending
    def send_template_email(self, to_emails: List[str], template_id: int,
                          template_params: Dict[str, Any],
                          from_email: str = None, **kwargs) -> bool:
        """
        Direct method to send template email without creating EmailMessage
        
        Args:
            to_emails: List of recipient email addresses
            template_id: Brevo template ID
            template_params: Template parameters
            from_email: Sender email (optional)
            **kwargs: Additional email options (cc, bcc, reply_to)
            
        Returns:
            True if email sent successfully
        """
        return self._send_template_email(
            to_emails=to_emails,
            template_id=template_id,
            template_params=template_params,
            from_email=from_email,
            **kwargs
        )