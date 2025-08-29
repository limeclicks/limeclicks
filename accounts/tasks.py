from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import get_connection
from .email_backend import BrevoTemplateEmailMessage
from django.conf import settings
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(bind=True, max_retries=3)
def send_verification_email_async(self, user_id, verification_url):
    """
    Send email verification asynchronously
    """
    try:
        user = User.objects.get(id=user_id)
        
        template_params = {
            'name': user.first_name or user.username,
            'url': verification_url
        }
        
        # Create template email message
        email_message = BrevoTemplateEmailMessage(
            template_id=2,
            template_params=template_params,
            to=[user.email],
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        
        # Send the email
        connection = get_connection()
        connection.send_messages([email_message])
        
        logger.info(f"Verification email sent successfully to {user.email}")
        return f"Email sent to {user.email}"
        
    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} does not exist")
        return f"User {user_id} not found"
    except Exception as exc:
        logger.error(f"Failed to send verification email: {exc}")
        # Retry the task
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_password_reset_email_async(self, user_id, reset_url):
    """
    Send password reset email asynchronously
    """
    try:
        user = User.objects.get(id=user_id)
        
        template_params = {
            'name': user.first_name or user.username,
            'url': reset_url
        }
        
        # Create template email message
        email_message = BrevoTemplateEmailMessage(
            template_id=1,  # Password reset template
            template_params=template_params,
            to=[user.email],
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        
        # Send the email
        connection = get_connection()
        connection.send_messages([email_message])
        
        logger.info(f"Password reset email sent successfully to {user.email}")
        return f"Password reset email sent to {user.email}"
        
    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} does not exist")
        return f"User {user_id} not found"
    except Exception as exc:
        logger.error(f"Failed to send password reset email: {exc}")
        # Retry the task
        raise self.retry(exc=exc, countdown=60)


@shared_task
def cleanup_expired_tokens():
    """
    Clean up expired verification tokens (older than 24 hours)
    """
    try:
        expired_time = timezone.now() - timezone.timedelta(hours=24)
        
        # Find users with expired tokens
        expired_users = User.objects.filter(
            email_verified=False,
            verification_token_created__lt=expired_time
        )
        
        count = expired_users.count()
        
        # You could either delete the users or regenerate their tokens
        # For now, let's just log them
        for user in expired_users:
            logger.info(f"User {user.email} has an expired verification token")
        
        logger.info(f"Found {count} users with expired verification tokens")
        return f"Found {count} expired tokens"
        
    except Exception as exc:
        logger.error(f"Failed to cleanup expired tokens: {exc}")
        raise exc


@shared_task(bind=True, max_retries=3)
def send_welcome_email_async(self, user_id):
    """
    Send welcome email after email verification using Brevo template ID 3
    """
    try:
        user = User.objects.get(id=user_id)
        
        if not user.email_verified:
            logger.warning(f"Attempted to send welcome email to unverified user: {user.email}")
            return "User email not verified"
        
        template_params = {
            'name': user.first_name or user.username
        }
        
        # Create template email message using template ID 3
        email_message = BrevoTemplateEmailMessage(
            template_id=3,  # Welcome email template
            template_params=template_params,
            to=[user.email],
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        
        # Send the email
        connection = get_connection()
        connection.send_messages([email_message])
        
        logger.info(f"Welcome email sent successfully to {user.email}")
        return f"Welcome email sent to {user.email}"
        
    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} does not exist")
        return f"User {user_id} not found"
    except Exception as exc:
        logger.error(f"Failed to send welcome email: {exc}")
        # Retry the task
        raise self.retry(exc=exc, countdown=60)