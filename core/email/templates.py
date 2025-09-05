"""
Email Template Configuration
Centralized definition of all Brevo email templates
"""

from enum import IntEnum
from typing import Dict, Any, Optional


class EmailTemplate(IntEnum):
    """
    Enum of all Brevo email template IDs
    Centralizes template configuration
    """
    # User/Auth templates
    NEW_USER_INVITATION = 4  # New user project invitation
    EXISTING_USER_INVITATION = 5  # Existing user project invitation
    
    # Report templates
    REPORT_READY = 6  # Report generation complete notification
    
    # Add more templates as needed
    # WELCOME_EMAIL = 1
    # PASSWORD_RESET = 2
    # etc.


class TemplateConfig:
    """
    Template configuration and parameter validation
    """
    
    # Define required parameters for each template
    TEMPLATE_PARAMS = {
        EmailTemplate.NEW_USER_INVITATION: {
            'required': ['project', 'reg_link'],
            'optional': ['inviter_name']
        },
        EmailTemplate.EXISTING_USER_INVITATION: {
            'required': ['name'],
            'optional': ['project', 'inviter_name']
        },
        EmailTemplate.REPORT_READY: {
            'required': ['report_name'],
            'optional': ['report_url', 'report_type']
        }
    }
    
    @classmethod
    def validate_params(cls, template_id: EmailTemplate, 
                       params: Dict[str, Any]) -> bool:
        """
        Validate that required parameters are present for a template
        
        Args:
            template_id: Template ID from EmailTemplate enum
            params: Parameters dict to validate
            
        Returns:
            True if all required params present
            
        Raises:
            ValueError: If required parameters are missing
        """
        if template_id not in cls.TEMPLATE_PARAMS:
            # Template not configured, allow any params
            return True
        
        config = cls.TEMPLATE_PARAMS[template_id]
        required = config.get('required', [])
        
        missing = [p for p in required if p not in params]
        if missing:
            raise ValueError(
                f"Template {template_id} missing required parameters: {missing}"
            )
        
        return True
    
    @classmethod
    def get_template_info(cls, template_id: EmailTemplate) -> Dict[str, Any]:
        """
        Get information about a template
        
        Args:
            template_id: Template ID
            
        Returns:
            Dict with template information
        """
        config = cls.TEMPLATE_PARAMS.get(template_id, {})
        
        return {
            'id': int(template_id),
            'name': template_id.name,
            'required_params': config.get('required', []),
            'optional_params': config.get('optional', [])
        }