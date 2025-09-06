import logging
import json
import time
from datetime import datetime
from celery import shared_task
from django.utils import timezone
from services.r2_storage import R2StorageService

logger = logging.getLogger(__name__)


# Favicon-related tasks have been removed as we now use Google's favicon service
# The favicon URL is generated on-demand using Project.get_favicon_url() method


@shared_task(bind=True, max_retries=3)
def fetch_domain_keywords_from_dataforseo(self, project_id):
    """
    Fetch all keywords for a domain from DataForSEO and store in R2
    Uses Keywords Data -> Google Ads -> Keywords for Site endpoint
    Creates task and stores task_id for webhook callback
    
    Args:
        project_id: ID of the project to fetch keywords for
        
    Returns:
        Dict with task status
    """
    from project.models import Project
    from services.dataforseo_client import get_dataforseo_client
    from django.core.cache import cache
    
    try:
        # Get the project
        project = Project.objects.get(id=project_id)
        logger.info(f"Starting DataForSEO keyword fetch for project {project_id}: {project.domain}")
        
        # Initialize clients
        dataforseo = get_dataforseo_client()
        r2_service = R2StorageService()
        
        # Step 1: Create task for Keywords for Site
        logger.info(f"Creating DataForSEO task for domain: {project.domain}")
        
        # Create the task with webhook callback
        response = dataforseo.create_keywords_for_site_task(
            target=project.domain,
            location_code=2826,  # UK location code
            language_code="en",
            sort_by="relevance",  # Use relevance like in the successful response
            include_webhook=True  # Include webhook URL for callback
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
        
        # Update project with DataForSEO task ID
        project.dataforseo_task_id = task_id
        project.save(update_fields=['dataforseo_task_id'])
        logger.info(f"Stored DataForSEO task ID {task_id} for project {project_id}")
        
        # Store task metadata in cache for webhook to use
        cache_key = f"dataforseo_task_{task_id}"
        cache.set(cache_key, {
            "project_id": project_id,
            "domain": project.domain,
            "created_at": datetime.now().isoformat(),
            "celery_task_id": self.request.id
        }, timeout=3600)  # Keep for 1 hour
        
        # Also check with polling as fallback (in case webhook fails)
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
        
        # Store in R2 with gzip compression
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        r2_path = f"dataforseo/domains/{project.domain}/keywords_{timestamp}.json.gz"
        
        # Convert to JSON and compress with gzip
        import gzip
        json_data = json.dumps(keywords_data, indent=2)
        compressed_data = gzip.compress(json_data.encode('utf-8'))
        
        # Log compression stats
        original_size = len(json_data.encode('utf-8'))
        compressed_size = len(compressed_data)
        compression_ratio = (1 - compressed_size/original_size) * 100 if original_size > 0 else 0
        logger.info(f"Compressed DataForSEO data: {original_size:,} bytes -> {compressed_size:,} bytes ({compression_ratio:.1f}% reduction)")
        
        r2_service.upload_file(
            file_obj=compressed_data,
            key=r2_path,
            metadata={
                'project_id': str(project_id),
                'domain': project.domain,
                'keywords_count': str(keywords_data['total_count']),
                'task_id': self.request.id,
                'content_encoding': 'gzip',
                'original_size': str(original_size),
                'compressed_size': str(compressed_size)
            }
        )
        
        logger.info(f"Successfully stored keywords data in R2 at: {r2_path}")
        
        # Update project with the R2 path and mark task as completed
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
    When DataForSEO completes a task, it sends a webhook notification.
    This task fetches the results and stores them in R2.
    
    Args:
        task_id: DataForSEO task ID
        webhook_data: Data received from DataForSEO webhook
        
    Returns:
        Processing status
    """
    from project.models import Project
    from services.dataforseo_client import get_dataforseo_client
    from services.r2_storage import R2StorageService
    import gzip
    
    logger.info(f"Processing DataForSEO webhook for task {task_id}")
    
    try:
        # Find the project by DataForSEO task ID
        try:
            project = Project.objects.get(dataforseo_task_id=task_id)
            logger.info(f"Found project {project.id} ({project.domain}) for task {task_id}")
        except Project.DoesNotExist:
            logger.error(f"No project found with dataforseo_task_id={task_id}")
            return {"status": "error", "message": f"No project found for task {task_id}"}
        
        # Check if keywords were already fetched today
        if project.dataforseo_keywords_path and project.dataforseo_keywords_updated_at:
            from datetime import timedelta
            
            # Check if updated today (within last 24 hours)
            time_since_update = timezone.now() - project.dataforseo_keywords_updated_at
            if time_since_update < timedelta(hours=24):
                hours_ago = time_since_update.total_seconds() / 3600
                logger.info(
                    f"Keywords for project {project.id} ({project.domain}) were already fetched {hours_ago:.1f} hours ago. "
                    f"Skipping duplicate processing for task {task_id}"
                )
                return {
                    "status": "already_processed",
                    "message": f"Keywords already fetched {hours_ago:.1f} hours ago",
                    "project_id": project.id,
                    "r2_path": project.dataforseo_keywords_path,
                    "updated_at": project.dataforseo_keywords_updated_at.isoformat()
                }
        
        # Initialize DataForSEO client
        dataforseo = get_dataforseo_client()
        r2_service = R2StorageService()
        
        # Fetch the task results
        logger.info(f"Fetching results for task {task_id}")
        result_response = dataforseo.get_task_result(task_id)
        
        if result_response and "tasks" in result_response:
            task_data = result_response["tasks"][0]
            
            if task_data.get("status_code") == 20000:
                # Task completed successfully
                result = task_data.get("result", [{}])[0]
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
                    "task_id": task_id,
                    "dataforseo_task_id": task_id
                }
                
                logger.info(f"Retrieved {total_count} keywords for {project.domain}")
                
                # Store in R2 with gzip compression
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                r2_path = f"dataforseo/domains/{project.domain}/keywords_{timestamp}.json.gz"
                
                # Convert to JSON and compress with gzip
                json_data = json.dumps(keywords_data, indent=2)
                compressed_data = gzip.compress(json_data.encode('utf-8'))
                
                # Log compression stats
                original_size = len(json_data.encode('utf-8'))
                compressed_size = len(compressed_data)
                compression_ratio = (1 - compressed_size/original_size) * 100 if original_size > 0 else 0
                logger.info(f"Compressed DataForSEO data: {original_size:,} bytes -> {compressed_size:,} bytes ({compression_ratio:.1f}% reduction)")
                
                r2_service.upload_file(
                    file_obj=compressed_data,
                    key=r2_path,
                    metadata={
                        'project_id': str(project.id),
                        'domain': project.domain,
                        'keywords_count': str(total_count),
                        'task_id': task_id,
                        'content_encoding': 'gzip',
                        'original_size': str(original_size),
                        'compressed_size': str(compressed_size)
                    }
                )
                
                logger.info(f"Successfully stored keywords data in R2 at: {r2_path}")
                
                # Update project with the R2 path and mark task as completed
                project.dataforseo_keywords_path = r2_path
                project.dataforseo_keywords_updated_at = timezone.now()
                project.save(update_fields=['dataforseo_keywords_path', 'dataforseo_keywords_updated_at'])
                
                logger.info(f"Updated project {project.id} with R2 path: {r2_path}")
                
                return {
                    "status": "success",
                    "task_id": task_id,
                    "project_id": project.id,
                    "keywords_count": total_count,
                    "r2_path": r2_path
                }
            else:
                error_msg = task_data.get("status_message", "Unknown error")
                logger.error(f"Task {task_id} failed: {error_msg}")
                # Log the failure - no need to update project status
                return {"status": "error", "message": error_msg}
        else:
            logger.error(f"Invalid response for task {task_id}")
            return {"status": "error", "message": "Invalid response"}
            
    except Exception as e:
        logger.error(f"Error processing webhook for task {task_id}: {str(e)}")
        return {"status": "error", "message": str(e)}