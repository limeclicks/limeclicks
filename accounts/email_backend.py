import os
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail import EmailMessage
import brevo_python
from brevo_python.rest import ApiException


class BrevoTemplateEmailMessage(EmailMessage):
    """
    Custom EmailMessage class for Brevo template emails
    """
    def __init__(self, template_id, template_params, to=None, from_email=None, **kwargs):
        super().__init__(to=to, from_email=from_email, **kwargs)
        self.template_id = template_id
        self.template_params = template_params


class BrevoEmailBackend(BaseEmailBackend):
    """
    Custom email backend for Brevo API integration
    """
    
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        
        # Initialize Brevo API client
        configuration = brevo_python.Configuration()
        configuration.api_key['api-key'] = os.getenv('BREVO_API_KEY')
        self.api_instance = brevo_python.TransactionalEmailsApi(
            brevo_python.ApiClient(configuration)
        )
    
    def send_messages(self, email_messages):
        """
        Send email messages using Brevo API
        """
        if not email_messages:
            return 0
        
        sent_count = 0
        
        for message in email_messages:
            try:
                # Check if this is a template email
                template_id = getattr(message, 'template_id', None)
                template_params = getattr(message, 'template_params', {})
                
                if template_id:
                    # Send using Brevo template
                    send_smtp_email = brevo_python.SendSmtpEmail(
                        to=[{"email": recipient} for recipient in message.to],
                        template_id=template_id,
                        params=template_params,
                        sender={"email": message.from_email or "noreply@limeclicks.com"}
                    )
                else:
                    # Send regular email
                    send_smtp_email = brevo_python.SendSmtpEmail(
                        to=[{"email": recipient} for recipient in message.to],
                        subject=message.subject,
                        text_content=message.body,
                        sender={"email": message.from_email or "noreply@limeclicks.com"}
                    )
                
                # Add CC if present
                if hasattr(message, 'cc') and message.cc:
                    send_smtp_email.cc = [{"email": cc} for cc in message.cc]
                
                # Add BCC if present
                if hasattr(message, 'bcc') and message.bcc:
                    send_smtp_email.bcc = [{"email": bcc} for bcc in message.bcc]
                
                # Send email
                api_response = self.api_instance.send_transac_email(send_smtp_email)
                sent_count += 1
                
            except ApiException as e:
                if not self.fail_silently:
                    raise e
            except Exception as e:
                if not self.fail_silently:
                    raise e
        
        return sent_count
    
    def send_template_email(self, to_emails, template_id, template_params, from_email=None):
        """
        Send template-based email using Brevo API
        """
        try:
            send_smtp_email = brevo_python.SendSmtpEmail(
                to=[{"email": email} for email in to_emails],
                template_id=template_id,
                params=template_params,
                sender={"email": from_email or "noreply@limeclicks.com"}
            )
            
            api_response = self.api_instance.send_transac_email(send_smtp_email)
            return True
            
        except (ApiException, Exception) as e:
            if not self.fail_silently:
                raise e
            return False