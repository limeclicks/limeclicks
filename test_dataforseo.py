#!/usr/bin/env python
"""
Test script for DataForSEO integration
"""
import os
import json
import time
from datetime import datetime

# Set environment variables
os.environ['DATA_FOR_SEO_USERNAME'] = 'dev@limeclicks.com'
os.environ['DATA_FOR_SEO_PASSWORD'] = '278ebdbee3eae3a7'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')

import django
django.setup()

from project.models import Project
from services.dataforseo_client import get_dataforseo_client
from services.r2_storage import R2StorageService
from django.utils import timezone

project_id = 56

try:
    # Get the project
    project = Project.objects.get(id=project_id)
    print(f"Testing DataForSEO for project {project_id}: {project.domain}")
    
    # Initialize clients
    dataforseo = get_dataforseo_client()
    r2_service = R2StorageService()
    
    # Step 1: Create task
    print(f"Creating DataForSEO task for domain: {project.domain}")
    response = dataforseo.create_keywords_for_site_task(
        target=project.domain,
        location_code=2840,
        language_code="en",
        sort_by="search_volume",
        date_from="2024-01-01"
    )
    
    if not response or "tasks" not in response:
        raise ValueError(f"Invalid response: {response}")
    
    task = response["tasks"][0]
    task_id = task.get("id")
    print(f"Task created with ID: {task_id}")
    
    # Step 2: Wait and check if ready
    print("Waiting 60 seconds for task to complete...")
    time.sleep(60)
    
    # Check if task is ready
    ready_response = dataforseo.check_tasks_ready()
    ready_tasks = ready_response.get("tasks", [{}])[0].get("result", [])
    
    task_ready = any(t.get("id") == task_id for t in ready_tasks)
    
    if task_ready:
        print(f"Task {task_id} is ready, fetching results...")
        
        # Get results
        result_response = dataforseo.get_task_result(task_id)
        task_data = result_response["tasks"][0]
        
        if task_data.get("status_code") == 20000:
            result = task_data.get("result", [{}])[0]
            keywords = result.get("items", [])
            total_count = result.get("items_count", len(keywords))
            
            print(f"Retrieved {total_count} keywords")
            
            # Prepare data for storage
            keywords_data = {
                "domain": project.domain,
                "total_count": total_count,
                "keywords": keywords,
                "location_code": result.get("location_code"),
                "language_code": result.get("language_code"),
                "fetched_at": datetime.now().isoformat(),
                "dataforseo_task_id": task_id
            }
            
            # Store in R2
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            r2_path = f"dataforseo/domains/{project.domain}/keywords_{timestamp}.json"
            
            json_data = json.dumps(keywords_data, indent=2)
            r2_service.upload_file(
                file_obj=json_data.encode('utf-8'),
                key=r2_path,
                metadata={
                    'project_id': str(project_id),
                    'domain': project.domain,
                    'keywords_count': str(total_count)
                }
            )
            
            print(f"Successfully stored keywords data in R2 at: {r2_path}")
            
            # Update project
            project.dataforseo_keywords_path = r2_path
            project.dataforseo_keywords_updated_at = timezone.now()
            project.save(update_fields=['dataforseo_keywords_path', 'dataforseo_keywords_updated_at'])
            
            print(f"Updated project {project_id} with R2 path: {r2_path}")
            print("SUCCESS!")
        else:
            print(f"Task failed with status: {task_data.get('status_message')}")
    else:
        print(f"Task {task_id} not ready after 60 seconds")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()