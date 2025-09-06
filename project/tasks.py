import logging
import json
from datetime import datetime
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# Favicon-related tasks have been removed as we now use Google's favicon service
# The favicon URL is generated on-demand using Project.get_favicon_url() method


@shared_task(bind=True, max_retries=3)
def fetch_domain_keywords_from_dataforseo(self, project_id):
    """
    Fetch all keywords for a domain from DataForSEO and store in R2
    Uses Keywords Data -> Google Ads -> Keywords for Site endpoint with long polling
    
    Args:
        project_id: ID of the project to fetch keywords for
        
    Returns:
        Dict with task status and R2 path
    """
    from project.models import Project
    from services.dataforseo_client import get_dataforseo_client
    from services.r2_storage import R2StorageService
    import time
    
    try:
        # Get the project
        project = Project.objects.get(id=project_id)
        logger.info(f"Starting DataForSEO keyword fetch for project {project_id}: {project.domain}")
        
        # Initialize clients
        dataforseo = get_dataforseo_client()
        r2_service = R2StorageService()
        
        # Step 1: Create task for Keywords for Site
        logger.info(f"Creating DataForSEO task for domain: {project.domain}")
        
        # Create the task using simplified client
        response = dataforseo.create_keywords_for_site_task(
            target=project.domain,
            location_code=2840,  # USA location code
            language_code="en",
            sort_by="search_volume",
            date_from="2024-01-01"  # Get data from last year
        )
        
        # Check if request was successful
        if not response or "tasks" not in response or not response["tasks"]:
            raise ValueError(f"Invalid response from DataForSEO: {response}")
            
        task = response["tasks"][0]
        
        # Check for task creation - status_code 20100 means "Task Created"
        if task.get("status_code") not in [20000, 20100]:
            error_message = task.get("status_message", "Unknown error")
            raise ValueError(f"DataForSEO API error: {error_message}")
            
        # Get the task ID
        task_id = task.get("id")
        logger.info(f"DataForSEO task created with ID: {task_id}")
        
        # Step 2: Long polling - check every minute for up to 10 minutes
        max_attempts = 10  # 10 attempts = 10 minutes max
        wait_interval = 60  # Check every 60 seconds (1 minute)
        
        for attempt in range(max_attempts):
            # Wait before checking (except on first attempt)
            if attempt > 0:
                logger.info(f"Waiting {wait_interval} seconds before checking task status (attempt {attempt + 1}/{max_attempts})")
                time.sleep(wait_interval)
            
            # Check if task is ready
            ready_response = dataforseo.check_tasks_ready()
            
            if ready_response and "tasks" in ready_response:
                ready_tasks = ready_response.get("tasks", [])
                
                # Check if our task is ready
                task_ready = False
                for ready_task in ready_tasks:
                    if ready_task.get("id") == task_id:
                        task_ready = True
                        break
                
                if task_ready:
                    logger.info(f"Task {task_id} is ready, fetching results")
                    
                    # Get the task results
                    task_result = dataforseo.get_task_result(task_id)
                    
                    if task_result and "tasks" in task_result and task_result["tasks"]:
                        task_data = task_result["tasks"][0]
                        
                        if task_data.get("status_code") == 20000:
                            # Task completed successfully
                            result = task_data.get("result", [{}])[0]
                            
                            if result and result.get("items"):
                                # Process the keywords data
                                keywords = result.get("items", [])
                                total_count = result.get("items_count", len(keywords))
                                
                                # Structure the data for storage
                                keywords_data = {
                                    "domain": project.domain,
                                    "total_count": total_count,
                                    "keywords": keywords,
                                    "location_code": result.get("location_code"),
                                    "language_code": result.get("language_code"),
                                    "fetched_at": datetime.now().isoformat(),
                                    "task_id": self.request.id,
                                    "dataforseo_task_id": task_id
                                }
                                
                                logger.info(f"Retrieved {total_count} keywords for {project.domain}")
                                break
                            else:
                                logger.warning(f"No keyword data found for domain: {project.domain}")
                                keywords_data = {
                                    "domain": project.domain,
                                    "total_count": 0,
                                    "keywords": [],
                                    "fetched_at": datetime.now().isoformat(),
                                    "task_id": self.request.id,
                                    "dataforseo_task_id": task_id
                                }
                                break
                        else:
                            error_msg = task_data.get("status_message", "Unknown error")
                            logger.error(f"Task {task_id} failed: {error_msg}")
                            raise ValueError(f"DataForSEO task failed: {error_msg}")
                else:
                    logger.info(f"Task {task_id} not ready yet (attempt {attempt + 1}/{max_attempts})")
        else:
            # Max attempts reached
            logger.warning(f"DataForSEO task {task_id} timed out after {max_attempts} attempts")
            keywords_data = {
                "domain": project.domain,
                "total_count": 0,
                "keywords": [],
                "error": "Task timed out after 10 minutes",
                "fetched_at": datetime.now().isoformat(),
                "task_id": self.request.id,
                "dataforseo_task_id": task_id
            }
            
        logger.info(f"Processed {keywords_data.get('total_count', 0)} keywords for {project.domain}")
        
        # Store in R2
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        r2_path = f"dataforseo/domains/{project.domain}/keywords_{timestamp}.json"
        
        # Convert to JSON and upload
        json_data = json.dumps(keywords_data, indent=2)
        
        r2_service.upload_file(
            file_obj=json_data.encode('utf-8'),
            key=r2_path,
            metadata={
                'project_id': str(project_id),
                'domain': project.domain,
                'keywords_count': str(keywords_data['total_count']),
                'task_id': self.request.id
            }
        )
        
        logger.info(f"Successfully stored keywords data in R2 at: {r2_path}")
        
        # Update project with the R2 path
        project.dataforseo_keywords_path = r2_path
        project.dataforseo_keywords_updated_at = timezone.now()
        project.save(update_fields=['dataforseo_keywords_path', 'dataforseo_keywords_updated_at'])
        
        logger.info(f"Updated project {project_id} with R2 path: {r2_path}")
        
        return {
            "status": "success",
            "project_id": project_id,
            "domain": project.domain,
            "keywords_count": keywords_data['total_count'],
            "r2_path": r2_path,
            "message": f"Successfully fetched and stored {keywords_data['total_count']} keywords"
        }
        
    except Project.DoesNotExist:
        logger.error(f"Project with ID {project_id} not found")
        raise
        
    except Exception as e:
        logger.error(f"Error fetching keywords for project {project_id}: {str(e)}")
        # Retry the task with exponential backoff
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@shared_task
def process_dataforseo_webhook(task_id, webhook_data):
    """
    Process webhook callback from DataForSEO
    NOTE: This is kept for backward compatibility but not used with long polling
    
    Args:
        task_id: Original task ID
        webhook_data: Data received from DataForSEO webhook
        
    Returns:
        Processing status
    """
    logger.info(f"Processing DataForSEO webhook for task {task_id}")
    
    try:
        # Log the webhook data for debugging
        logger.debug(f"Webhook data: {json.dumps(webhook_data, indent=2)}")
        
        # Extract status and results
        status = webhook_data.get("status")
        
        if status == "success":
            logger.info(f"DataForSEO task {task_id} completed successfully")
        else:
            logger.warning(f"DataForSEO task {task_id} failed with status: {status}")
            
        return {
            "status": "processed",
            "task_id": task_id,
            "dataforseo_status": status
        }
        
    except Exception as e:
        logger.error(f"Error processing webhook for task {task_id}: {str(e)}")
        raise