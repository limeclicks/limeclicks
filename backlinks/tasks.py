import logging
import json
import gzip
import time
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone
from services.dataforseo_client import get_dataforseo_client
from services.r2_storage import R2StorageService
from backlinks.models import BacklinkProfile
from project.models import Project

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def fetch_backlink_summary_from_dataforseo(self, project_id, target_domain=None, force=False):
    """
    Fetch backlink summary for a project's domain from DataForSEO
    Uses Backlinks -> Summary -> Live endpoint
    Creates BacklinkProfile record with the summary data
    
    Args:
        project_id: ID of the project to fetch backlinks for
        target_domain: Optional domain override (uses project.domain if not provided)
        force: If True, bypass the 30-day interval check (for manual runs)
        
    Returns:
        Dict with task status and created BacklinkProfile ID
    """
    from django.db import connection
    
    try:
        # Get the project
        project = Project.objects.get(id=project_id)
        domain = target_domain or project.domain
        logger.info(f"Starting DataForSEO backlink summary fetch for project {project_id}: {domain}")
        
        # Check if domain is locked due to no data found previously
        if project.is_backlinks_locked() and not force:
            days_remaining = project.get_backlinks_lockdown_days_remaining()
            logger.info(f"Backlinks fetch blocked for {domain}: lockdown active for {days_remaining} more days")
            return {
                "status": "locked",
                "project_id": project_id,
                "domain": domain,
                "days_remaining": days_remaining,
                "lockdown_until": project.backlinks_no_data_until.isoformat(),
                "message": f"Backlinks fetch blocked - no data was found previously. Please wait {days_remaining} more days."
            }
        
        # Check 30-day interval unless forced
        if not force:
            latest_profile = BacklinkProfile.objects.filter(
                project=project, 
                target=domain
            ).order_by('-created_at').first()
            
            if latest_profile:
                time_since_last = timezone.now() - latest_profile.created_at
                if time_since_last < timedelta(days=30):
                    days_remaining = 30 - time_since_last.days
                    logger.info(f"Skipping fetch for {domain}: last fetch was {time_since_last.days} days ago, {days_remaining} days remaining")
                    return {
                        "status": "skipped",
                        "project_id": project_id,
                        "domain": domain,
                        "days_since_last_fetch": time_since_last.days,
                        "days_remaining": days_remaining,
                        "message": f"Fetch skipped - must wait {days_remaining} more days (30-day minimum interval)"
                    }
        
        # Initialize DataForSEO client
        dataforseo = get_dataforseo_client()
        
        # Make live call to backlinks summary endpoint
        logger.info(f"Calling DataForSEO backlinks summary for domain: {domain}")
        
        # Prepare request data for backlinks summary live endpoint
        post_data = [{
            "target": domain,
            "backlinks_status_type": "live",
            "internal_list_limit": 10,
            "include_subdomains": True,
            "exclude_internal_backlinks": True,
            "include_indirect_links": True,
            "rank_scale": "one_hundred"
        }]
        
        # Make the API call
        response = dataforseo._make_request("POST", "/backlinks/summary/live", post_data)
        
        # Check if request was successful
        if not response or "tasks" not in response or not response["tasks"]:
            raise ValueError(f"Invalid response from DataForSEO: {response}")
            
        task = response["tasks"][0]
        
        # Check for successful response - status_code 20000 means "Ok"
        if task.get("status_code") != 20000:
            error_message = task.get("status_message", "Unknown error")
            raise ValueError(f"DataForSEO API error: {error_message}")
            
        # Check if we have results
        if not task.get("result") or not task["result"]:
            logger.warning(f"No backlink data found for domain: {domain}")
            
            # Set 30-day lockdown for this domain
            lockdown_until = timezone.now() + timedelta(days=30)
            project.backlinks_no_data_until = lockdown_until
            project.save(update_fields=['backlinks_no_data_until'])
            logger.info(f"Set backlinks lockdown for {domain} until {lockdown_until}")
            
            return {
                "status": "no_data",
                "project_id": project_id,
                "domain": domain,
                "message": "No backlink data found for this domain",
                "lockdown_until": lockdown_until.isoformat(),
                "lockdown_days": 30
            }
            
        # Extract the backlink summary data from the first result
        result_data = task["result"][0]
        
        logger.info(f"DataForSEO returned backlink summary for {domain}: {result_data.get('backlinks', 0)} backlinks")
        
        # Always create a new BacklinkProfile record
        backlink_profile = BacklinkProfile.objects.create(
            project=project,
            target=domain,
            rank=result_data.get('rank'),
            backlinks=result_data.get('backlinks', 0),
            backlinks_spam_score=result_data.get('backlinks_spam_score', 0),
            internal_links_count=result_data.get('internal_links_count', 0),
            external_links_count=result_data.get('external_links_count', 0),
            broken_backlinks=result_data.get('broken_backlinks', 0),
            broken_pages=result_data.get('broken_pages', 0),
            referring_domains=result_data.get('referring_domains', 0),
            referring_domains_nofollow=result_data.get('referring_domains_nofollow', 0),
            referring_main_domains=result_data.get('referring_main_domains', 0),
            referring_main_domains_nofollow=result_data.get('referring_main_domains_nofollow', 0),
            referring_ips=result_data.get('referring_ips', 0),
            referring_subnets=result_data.get('referring_subnets', 0),
            referring_pages=result_data.get('referring_pages', 0),
            referring_pages_nofollow=result_data.get('referring_pages_nofollow', 0),
            referring_links_tld=result_data.get('referring_links_tld', {}),
            referring_links_types=result_data.get('referring_links_types', {}),
            referring_links_attributes=result_data.get('referring_links_attributes', {}),
            referring_links_platform_types=result_data.get('referring_links_platform_types', {}),
            referring_links_semantic_locations=result_data.get('referring_links_semantic_locations', {}),
            referring_links_countries=result_data.get('referring_links_countries', {}),
        )
        
        logger.info(f"Created new BacklinkProfile record for {domain} (ID: {backlink_profile.id})")
        
        # Implement retention policy: keep only 3 most recent profiles
        all_profiles = BacklinkProfile.objects.filter(
            project=project, 
            target=domain
        ).order_by('-created_at')
        
        if all_profiles.count() > 3:
            # Get IDs of profiles to keep (3 most recent)
            keep_ids = list(all_profiles.values_list('id', flat=True)[:3])
            
            # Delete profiles not in the keep list
            profiles_to_delete = BacklinkProfile.objects.filter(
                project=project,
                target=domain
            ).exclude(id__in=keep_ids)
            
            deleted_count = profiles_to_delete.count()
            profiles_to_delete.delete()
            logger.info(f"Deleted {deleted_count} old BacklinkProfile records for {domain} (retention policy: keep 3 most recent)")
        
        # Use the newly created profile
        latest_profile = backlink_profile
        
        logger.info(f"Successfully stored backlink summary for {domain}: {latest_profile.backlinks} backlinks, {latest_profile.referring_domains} referring domains")
        
        # Note: Detailed backlinks collection must be manually triggered by user
        logger.info(f"Backlink summary completed for {domain}. Detailed collection requires manual trigger.")
        
        return {
            "status": "success",
            "project_id": project_id,
            "domain": domain,
            "backlink_profile_id": latest_profile.id,
            "backlinks_count": latest_profile.backlinks,
            "referring_domains": latest_profile.referring_domains,
            "rank": latest_profile.rank,
            "message": f"Successfully fetched and stored backlink summary for {domain}"
        }
        
    except Project.DoesNotExist:
        logger.error(f"Project with ID {project_id} not found")
        raise
        
    except Exception as e:
        logger.error(f"Error fetching backlinks for project {project_id}: {str(e)}")
        # Close connection before retry
        connection.close()
        # Retry the task with exponential backoff
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
    finally:
        # Always close database connection to prevent leaks
        try:
            connection.close()
        except:
            pass


@shared_task(bind=True, max_retries=3)
def fetch_backlinks_for_all_projects(self, force=False):
    """
    Background task to fetch backlink summaries for all active projects
    Respects 30-day interval unless force=True
    
    Args:
        force: If True, bypass the 30-day interval check for all projects
    
    Returns:
        Dict with processing summary
    """
    from django.db import connection
    
    try:
        logger.info("Starting backlink summary fetch for all active projects")
        
        # Get all active projects
        active_projects = Project.objects.filter(active=True)
        total_projects = active_projects.count()
        
        logger.info(f"Found {total_projects} active projects to process")
        
        success_count = 0
        error_count = 0
        
        for project in active_projects:
            try:
                logger.info(f"Processing project {project.id}: {project.domain}")
                
                # Call the individual fetch task with force parameter
                result = fetch_backlink_summary_from_dataforseo.delay(project.id, force=force)
                
                # You could wait for result if needed, but for background processing
                # it's better to let tasks run async
                success_count += 1
                logger.info(f"Queued backlink fetch for project {project.id}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error queuing backlink fetch for project {project.id}: {str(e)}")
                continue
        
        logger.info(f"Finished queuing backlink fetches: {success_count} successful, {error_count} errors")
        
        return {
            "status": "completed",
            "total_projects": total_projects,
            "success_count": success_count,
            "error_count": error_count,
            "message": f"Queued backlink fetches for {success_count}/{total_projects} projects"
        }
        
    except Exception as e:
        logger.error(f"Error in bulk backlink fetch task: {str(e)}")
        connection.close()
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
    finally:
        # Always close database connection
        try:
            connection.close()
        except:
            pass


@shared_task(bind=True, max_retries=3)
def fetch_detailed_backlinks_from_dataforseo(self, backlink_profile_id, max_links=5000):
    """
    Fetch detailed backlinks for a BacklinkProfile from DataForSEO
    Uses pagination to collect up to max_links backlinks and stores them in R2
    
    Args:
        backlink_profile_id: ID of the BacklinkProfile to collect detailed backlinks for
        max_links: Maximum number of backlinks to collect (default: 5000)
        
    Returns:
        Dict with collection status and file path
    """
    
    try:
        # Get the BacklinkProfile
        backlink_profile = BacklinkProfile.objects.get(id=backlink_profile_id)
        project = backlink_profile.project
        domain = backlink_profile.target
        
        logger.info(f"Starting detailed backlinks collection for profile {backlink_profile_id}: {domain}")
        
        # Get the total number of backlinks from the profile
        total_available = backlink_profile.backlinks
        if total_available == 0:
            logger.warning(f"No backlinks available for domain: {domain}")
            return {
                "status": "no_data",
                "backlink_profile_id": backlink_profile_id,
                "domain": domain,
                "message": "No backlinks available for collection"
            }
        
        # Determine how many to collect (min of available, max_links, and API limit)
        links_to_collect = min(total_available, max_links, 20000)  # API offset limit is 20,000
        logger.info(f"Planning to collect {links_to_collect} backlinks out of {total_available} available for {domain}")
        
        # Initialize DataForSEO client and R2 service
        dataforseo = get_dataforseo_client()
        r2_service = R2StorageService()
        
        # Store previous summary before updating
        previous_summary_data = {
            "rank": backlink_profile.rank,
            "backlinks": backlink_profile.backlinks,
            "backlinks_spam_score": backlink_profile.backlinks_spam_score,
            "referring_domains": backlink_profile.referring_domains,
            "referring_pages": backlink_profile.referring_pages,
            "collected_at": backlink_profile.updated_at.isoformat() if backlink_profile.updated_at else None,
            "referring_links_tld": backlink_profile.referring_links_tld,
            "referring_links_types": backlink_profile.referring_links_types,
            "referring_links_countries": backlink_profile.referring_links_countries
        }
        
        # Collection variables
        all_backlinks = []
        offset = 0
        batch_size = 1000  # Max per API call
        
        # Collect backlinks in batches
        while offset < links_to_collect:
            remaining = links_to_collect - offset
            current_batch_size = min(batch_size, remaining)
            
            logger.info(f"Fetching batch: offset={offset}, limit={current_batch_size} for {domain}")
            
            # Make API call for this batch
            response = dataforseo.get_backlinks_detailed(
                target=domain,
                limit=current_batch_size,
                offset=offset
            )
            
            # Check if request was successful
            if not response or "tasks" not in response or not response["tasks"]:
                raise ValueError(f"Invalid response from DataForSEO: {response}")
                
            task = response["tasks"][0]
            
            # Check for successful response
            if task.get("status_code") != 20000:
                error_message = task.get("status_message", "Unknown error")
                raise ValueError(f"DataForSEO API error: {error_message}")
                
            # Extract and merge results from this batch
            if task.get("result") and task["result"]:
                # DataForSEO returns result as array with items inside
                for result in task["result"]:
                    if result.get("items"):
                        batch_backlinks = result["items"]
                        all_backlinks.extend(batch_backlinks)
                        logger.info(f"Collected {len(batch_backlinks)} backlinks in this batch (total: {len(all_backlinks)})")
            else:
                logger.info(f"No more backlinks returned at offset {offset}")
                break
            
            # Move to next batch
            offset += current_batch_size
            
            # Small delay to avoid rate limits
            time.sleep(0.1)
        
        logger.info(f"Finished collecting {len(all_backlinks)} detailed backlinks for {domain}")
        
        # Prepare merged backlinks data for upload
        backlinks_data = {
            "domain": domain,
            "project_id": project.id,
            "backlink_profile_id": backlink_profile_id,
            "total_available": total_available,
            "collected_count": len(all_backlinks),
            "collected_at": datetime.now().isoformat(),
            "previous_summary": previous_summary_data,
            "backlinks": all_backlinks
        }
        
        # Upload merged results to R2 as gzip
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        r2_path = f"backlinks/detailed/{domain}/backlinks_{timestamp}.json.gz"
        
        # Convert to JSON and compress
        json_data = json.dumps(backlinks_data, indent=2)
        compressed_data = gzip.compress(json_data.encode('utf-8'))
        
        # Log compression stats
        original_size = len(json_data.encode('utf-8'))
        compressed_size = len(compressed_data)
        compression_ratio = (1 - compressed_size/original_size) * 100 if original_size > 0 else 0
        logger.info(f"Compressed merged backlinks: {original_size:,} bytes -> {compressed_size:,} bytes ({compression_ratio:.1f}% reduction)")
        
        # Upload to R2 as private file (default behavior)
        r2_service.upload_file(
            file_obj=compressed_data,
            key=r2_path,
            metadata={
                'project_id': str(project.id),
                'domain': domain,
                'backlinks_count': str(len(all_backlinks)),
                'total_available': str(total_available),
                'task_id': str(getattr(self.request, 'id', 'manual')),
                'content_encoding': 'gzip'
            },
            content_type='application/json',
            public=False  # Ensure file is private
        )
        
        logger.info(f"Successfully stored merged backlinks in R2 at: {r2_path}")
        
        # Update BacklinkProfile
        backlink_profile.previous_summary = previous_summary_data
        backlink_profile.backlinks_file_path = r2_path
        backlink_profile.backlinks_collected_at = timezone.now()
        backlink_profile.backlinks_count_collected = len(all_backlinks)
        backlink_profile.save(update_fields=[
            'previous_summary', 'backlinks_file_path', 
            'backlinks_collected_at', 'backlinks_count_collected'
        ])
        
        return {
            "status": "success",
            "backlink_profile_id": backlink_profile_id,
            "domain": domain,
            "collected_count": len(all_backlinks),
            "r2_path": r2_path,
            "message": f"Successfully collected and stored {len(all_backlinks)} backlinks for {domain}"
        }
        
    except BacklinkProfile.DoesNotExist:
        logger.error(f"BacklinkProfile with ID {backlink_profile_id} not found")
        raise
        
    except Exception as e:
        logger.error(f"Error collecting detailed backlinks for profile {backlink_profile_id}: {str(e)}")
        from django.db import connection
        connection.close()
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
    finally:
        # Always close database connection
        from django.db import connection
        try:
            connection.close()
        except:
            pass