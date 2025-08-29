from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

from .models import Project

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Project)
def auto_queue_audits_on_project_creation(sender, instance, created, **kwargs):
    """
    Automatically queue HIGH PRIORITY OnPage audits when a new project is created
    from any source (admin, API, views, etc.)
    
    These tasks will be sent to the high priority queue for immediate processing.
    """
    if created:
        try:
            # Import the HIGH PRIORITY task for new domains
            from site_audit.tasks import create_site_audit_for_new_project
            
            # Queue HIGH PRIORITY OnPage audit for new domain  
            onpage_result = create_site_audit_for_new_project.delay(instance.id)
            logger.info(f"Auto-queued HIGH PRIORITY OnPage audit for new project {instance.domain}: Task ID={onpage_result.id}")
            
            logger.info(f"Successfully auto-queued HIGH PRIORITY audit for new project: {instance.domain}")
            
        except Exception as e:
            # Don't fail project creation if audit queuing fails
            logger.error(f"Failed to auto-queue HIGH PRIORITY audit for new project {instance.domain}: {str(e)}")