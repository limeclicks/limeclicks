from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

from .models import Project

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Project)
def auto_queue_audits_on_project_creation(sender, instance, created, **kwargs):
    """
    Automatically queue HIGH PRIORITY OnPage audit when a new project is created
    from any source (admin, API, views, etc.)
    
    The task will be sent to the high priority queue for immediate processing.
    PageSpeed audit will be triggered automatically after site audit completes.
    """
    if created:
        try:
            # Import the HIGH PRIORITY task for new domains
            from site_audit.tasks import create_site_audit_for_new_project
            
            # Queue HIGH PRIORITY OnPage audit for new domain
            onpage_result = create_site_audit_for_new_project.apply_async(
                args=[instance.id],
                queue='audit_high_priority'
            )
            logger.info(f"Auto-queued HIGH PRIORITY OnPage audit for new project {instance.domain}: Task ID={onpage_result.id}")
            
            logger.info(f"Successfully auto-queued HIGH PRIORITY audit for new project: {instance.domain}")
            
        except Exception as e:
            # Don't fail project creation if audit queuing fails
            logger.error(f"Failed to auto-queue HIGH PRIORITY audits for new project {instance.domain}: {str(e)}")
        
        # Create DataForSEO task with webhook callback
        try:
            task_id = instance.create_dataforseo_task()
            if task_id:
                logger.info(f"Created DataForSEO task {task_id} for project {instance.domain} with webhook callback")
            else:
                logger.warning(f"Failed to create DataForSEO task for project {instance.domain}")
        except Exception as e:
            # Don't fail project creation if DataForSEO fails
            logger.error(f"Failed to create DataForSEO task for new project {instance.domain}: {str(e)}")
        
        # Fetch backlink summary for the new project
        try:
            from backlinks.tasks import fetch_backlink_summary_from_dataforseo
            
            # Queue backlink summary fetch
            backlink_result = fetch_backlink_summary_from_dataforseo.delay(instance.id)
            logger.info(f"Auto-queued backlink summary fetch for new project {instance.domain}: Task ID={backlink_result.id}")
            
        except Exception as e:
            # Don't fail project creation if backlink fetch fails
            logger.error(f"Failed to queue backlink summary for new project {instance.domain}: {str(e)}")