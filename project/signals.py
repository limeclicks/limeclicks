from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

from .models import Project

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Project)
def auto_queue_audits_on_project_creation(sender, instance, created, **kwargs):
    """
    Automatically queue HIGH PRIORITY site and PageSpeed audits when a new project is created
    from any source (admin, API, views, etc.)
    
    Both audits are triggered simultaneously for parallel execution.
    """
    if created:
        try:
            # Import the task that handles both audits
            from site_audit.tasks import create_site_audit_for_new_project
            
            # This task now triggers both site audit and PageSpeed audit simultaneously
            onpage_result = create_site_audit_for_new_project.apply_async(
                args=[instance.id],
                queue='audit_high_priority'
            )
            logger.info(f"Auto-queued HIGH PRIORITY site and PageSpeed audits for new project {instance.domain}: Task ID={onpage_result.id}")
            
            logger.info(f"Successfully auto-queued HIGH PRIORITY audits for new project: {instance.domain}")
            
        except Exception as e:
            # Don't fail project creation if audit queuing fails
            logger.error(f"Failed to auto-queue HIGH PRIORITY audits for new project {instance.domain}: {str(e)}")