"""
Email service for sending emails via Brevo (formerly Sendinblue)
"""

import logging
import os
from typing import Dict, List, Optional, Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def send_brevo_email(email_data: Dict[str, Any]) -> bool:
    """
    Send email via Brevo API using templates
    
    Args:
        email_data: Dictionary containing:
            - to: List of recipient dicts with 'email' and optional 'name'
            - templateId: Brevo template ID
            - params: Template parameters dict
            - subject (optional): Override template subject
            
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Get API key from settings or environment
        api_key = getattr(settings, 'BREVO_API_KEY', None) or os.getenv('BREVO_API_KEY')
        
        if not api_key:
            logger.error("Brevo API key not configured")
            return False
        
        # Brevo API endpoint
        url = "https://api.brevo.com/v3/smtp/email"
        
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": api_key
        }
        
        # Prepare payload
        payload = {
            "to": email_data.get('to', []),
            "templateId": email_data.get('templateId'),
            "params": email_data.get('params', {})
        }
        
        # Add optional fields
        if 'subject' in email_data:
            payload['subject'] = email_data['subject']
        
        if 'replyTo' in email_data:
            payload['replyTo'] = email_data['replyTo']
        
        # Send request
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 201:
            logger.info(f"Email sent successfully via Brevo template {email_data.get('templateId')}")
            return True
        else:
            logger.error(f"Failed to send email via Brevo: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending Brevo email: {e}", exc_info=True)
        return False


def send_report_notification(
    recipient_email: str,
    recipient_name: str,
    report_name: str,
    template_id: int = 6
) -> bool:
    """
    Send report ready notification using Brevo template 6
    
    Args:
        recipient_email: Email address to send to
        recipient_name: Name of recipient
        report_name: Name of the report
        template_id: Brevo template ID (default: 6)
        
    Returns:
        True if sent successfully
    """
    email_data = {
        'to': [{'email': recipient_email, 'name': recipient_name}],
        'templateId': template_id,
        'params': {
            'report_name': report_name
        }
    }
    
    return send_brevo_email(email_data)


def send_batch_emails(
    recipients: List[Dict[str, str]],
    template_id: int,
    params: Dict[str, Any]
) -> Dict[str, int]:
    """
    Send emails to multiple recipients using the same template
    
    Args:
        recipients: List of dicts with 'email' and optional 'name'
        template_id: Brevo template ID
        params: Template parameters
        
    Returns:
        Dict with 'sent' and 'failed' counts
    """
    sent = 0
    failed = 0
    
    for recipient in recipients:
        email_data = {
            'to': [recipient],
            'templateId': template_id,
            'params': params
        }
        
        if send_brevo_email(email_data):
            sent += 1
        else:
            failed += 1
    
    logger.info(f"Batch email results: {sent} sent, {failed} failed")
    
    return {
        'sent': sent,
        'failed': failed
    }