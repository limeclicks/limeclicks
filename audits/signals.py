from django.db.models.signals import post_save
from django.dispatch import receiver
from project.models import Project
from .tasks import create_audit_for_project
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Project)
def trigger_audit_on_project_creation(sender, instance, created, **kwargs):
    """
    Trigger a Lighthouse audit when a new project is created
    """
    if created:
        logger.info(f"New project created: {instance.domain}, triggering initial audit")
        
        # Queue the audit task
        create_audit_for_project.delay(instance.id, trigger_type='project_created')