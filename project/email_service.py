import logging
from django.conf import settings
from django.urls import reverse
from accounts.email_backend import BrevoEmailBackend

logger = logging.getLogger(__name__)


def send_project_invitation(email, project, inviter, is_existing_user=False, user_name=None, invitation_token=None):
    """
    Send project invitation email using Brevo Templates
    Template 4: New user invitation  
    Template 5: Existing user invitation
    
    Args:
        email: Recipient email address
        project: Project instance
        inviter: User who sent the invitation
        is_existing_user: Whether recipient is an existing user
        user_name: Name of existing user (required if is_existing_user=True)
        invitation_token: Invitation token for new users (required if is_existing_user=False)
    """
    try:
        backend = BrevoEmailBackend()
        
        if is_existing_user:
            # Existing user - send with Template 5
            template_id = 5
            params = {
                "name": user_name or email.split('@')[0]
            }
        else:
            # New user - send with Template 4
            template_id = 4
            if not invitation_token:
                raise ValueError("Invitation token required for new user invitations")
            
            # Build registration link
            base_url = settings.SITE_URL.rstrip('/')
            reg_link = f"{base_url}{reverse('project:accept_invitation', kwargs={'token': invitation_token})}"
            
            params = {
                "project": project.domain,
                "reg_link": reg_link
            }
        
        # Send using existing Brevo backend
        success = backend.send_template_email(
            to_emails=[email],
            template_id=template_id,
            template_params=params
        )
        
        if success:
            logger.info(f"Successfully sent invitation email to {email} for project {project.domain}")
        else:
            logger.error(f"Failed to send invitation email to {email}")
        
        return success
        
    except Exception as e:
        logger.error(f"Failed to send invitation email to {email}: {str(e)}")
        # Don't fail the invitation process if email fails
        return False


def send_invitation_accepted_notification(inviter_email, acceptor_name, project):
    """
    Optional: Send notification to inviter when invitation is accepted
    """
    try:
        api_client = get_brevo_client()
        
        # You may want to create a separate template for this
        # For now, using a simple transactional email
        send_smtp_email = SendSmtpEmail(
            to=[{"email": inviter_email}],
            subject=f"{acceptor_name} joined {project.domain}",
            html_content=f"""
            <p>Good news!</p>
            <p>{acceptor_name} has accepted your invitation and joined the project <strong>{project.domain}</strong>.</p>
            <p>They now have access to manage keywords and project settings.</p>
            """,
            sender={"email": settings.DEFAULT_FROM_EMAIL, "name": "LimeClicks"}
        )
        
        api_response = api_client.send_transac_email(send_smtp_email)
        logger.info(f"Sent acceptance notification to {inviter_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send acceptance notification: {str(e)}")
        return False