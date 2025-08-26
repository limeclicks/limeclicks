import logging
from typing import Type, Optional, Dict, Any
from celery import shared_task, Task
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.db import models

logger = logging.getLogger(__name__)


class BaseAuditTask(Task):
    """Base class for audit tasks with common error handling and retry logic"""
    
    def __init__(self):
        super().__init__()
        self.model_class: Optional[Type[models.Model]] = None
        self.max_retries = 3
        self.default_retry_delay = 60
    
    def execute_audit(self, audit_id: str, audit_function, **kwargs) -> Dict[str, Any]:
        """
        Execute an audit with standard error handling and status updates
        
        Args:
            audit_id: The ID of the audit record
            audit_function: The function to execute for the audit
            **kwargs: Additional arguments to pass to audit_function
        """
        if not self.model_class:
            raise ValueError("model_class must be set")
        
        try:
            # Get the audit record
            audit = self.model_class.objects.get(id=audit_id)
            
            # Mark as running
            if hasattr(audit, 'mark_running'):
                audit.mark_running()
            else:
                audit.status = 'running'
                audit.started_at = timezone.now()
                audit.save(update_fields=['status', 'started_at'])
            
            # Execute the audit function
            result = audit_function(audit, **kwargs)
            
            # Mark as completed
            if hasattr(audit, 'mark_completed'):
                audit.mark_completed()
            else:
                audit.status = 'completed'
                audit.completed_at = timezone.now()
                audit.save(update_fields=['status', 'completed_at'])
            
            logger.info(f"Audit {audit_id} completed successfully")
            return {
                'success': True,
                'audit_id': str(audit_id),
                'result': result
            }
            
        except ObjectDoesNotExist:
            logger.error(f"Audit {audit_id} not found for {self.model_class.__name__}")
            return {
                'success': False,
                'error': f'Audit {audit_id} not found'
            }
            
        except Exception as e:
            logger.error(f"Error executing audit {audit_id}: {str(e)}", exc_info=True)
            
            # Try to update the audit status
            try:
                audit = self.model_class.objects.get(id=audit_id)
                if hasattr(audit, 'mark_failed'):
                    audit.mark_failed(str(e))
                else:
                    audit.status = 'failed'
                    audit.error_message = str(e)[:5000]
                    audit.retry_count = getattr(audit, 'retry_count', 0) + 1
                    audit.save(update_fields=['status', 'error_message', 'retry_count'])
            except:
                pass
            
            # Retry if applicable
            if hasattr(self, 'request') and self.request.retries < self.max_retries:
                raise self.retry(exc=e, countdown=self.default_retry_delay * (self.request.retries + 1))
            
            return {
                'success': False,
                'error': str(e)
            }


def create_base_audit_task(model_class: Type[models.Model], 
                          max_retries: int = 3,
                          default_retry_delay: int = 60):
    """
    Factory function to create a base audit task for a specific model
    
    Args:
        model_class: The Django model class for the audit
        max_retries: Maximum number of retry attempts
        default_retry_delay: Delay between retries in seconds
    """
    @shared_task(bind=True, base=BaseAuditTask, max_retries=max_retries)
    def audit_task(self, audit_id: str, audit_function, **kwargs):
        self.model_class = model_class
        self.max_retries = max_retries
        self.default_retry_delay = default_retry_delay
        return self.execute_audit(audit_id, audit_function, **kwargs)
    
    return audit_task


@shared_task
def cleanup_old_records(model_class_path: str, days_to_keep: int = 90) -> Dict[str, Any]:
    """
    Generic task to cleanup old records from any model
    
    Args:
        model_class_path: Full path to the model class (e.g., 'app.models.ModelName')
        days_to_keep: Number of days to keep records
    """
    from datetime import timedelta
    from django.apps import apps
    
    try:
        # Parse the model class path
        app_label, model_name = model_class_path.rsplit('.', 1)
        app_label = app_label.split('.')[-2]  # Get app name from path
        
        # Get the model class
        model_class = apps.get_model(app_label, model_name)
        
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        # Get the date field to filter on
        date_field = 'created_at'
        if hasattr(model_class, 'completed_at'):
            date_field = 'completed_at'
        
        # Delete old records
        filter_kwargs = {f'{date_field}__lt': cutoff_date}
        deleted_count, _ = model_class.objects.filter(**filter_kwargs).delete()
        
        logger.info(f"Deleted {deleted_count} old {model_name} records older than {days_to_keep} days")
        
        return {
            'success': True,
            'deleted_count': deleted_count,
            'model': model_class_path,
            'days_kept': days_to_keep
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up {model_class_path}: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }