from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

from .models import Project

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Project)
def auto_queue_audits_on_project_creation(sender, instance, created, **kwargs):
    """
    Automatically queue Lighthouse and OnPage audits when a new project is created
    from any source (admin, API, views, etc.)
    """
    if created:
        try:
            from audits.tasks import create_audit_for_project
            from onpageaudit.tasks import create_onpage_audit_for_project
            
            # Queue Lighthouse audit
            lighthouse_result = create_audit_for_project.delay(instance.id, 'project_created')
            logger.info(f"Auto-queued Lighthouse audit for new project {instance.domain}: Task ID={lighthouse_result.id}")
            
            # Queue OnPage audit  
            onpage_result = create_onpage_audit_for_project.delay(instance.id, 'project_created')
            logger.info(f"Auto-queued OnPage audit for new project {instance.domain}: Task ID={onpage_result.id}")
            
            logger.info(f"Successfully auto-queued both audits for new project: {instance.domain}")
            
        except Exception as e:
            # Don't fail project creation if audit queuing fails
            logger.error(f"Failed to auto-queue audits for new project {instance.domain}: {str(e)}")