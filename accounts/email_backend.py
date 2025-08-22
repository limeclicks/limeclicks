import os
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail import EmailMessage
import brevo_python
from brevo_python.rest import ApiException


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
                # Prepare email data for Brevo
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