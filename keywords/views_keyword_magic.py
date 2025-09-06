"""
Keyword Magic Tool views for DataForSEO keyword analysis
"""
import json
import gzip
import logging
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
from project.models import Project
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@login_required
def keyword_magic_tool(request):
    """Main view for Keyword Magic Tool"""
    # Get all projects where user is owner or member
    from django.db.models import Q
    
    projects = Project.objects.filter(
        Q(user=request.user) |  # Projects owned by user
        Q(memberships__user=request.user)  # Projects where user is a member
    ).distinct().order_by('domain')
    
    context = {
        'projects': projects,
    }
    
    return render(request, 'keywords/keyword_magic.html', context)


@login_required
@require_http_methods(["GET"])
def load_keyword_data(request, project_id):
    """Generate presigned URL for R2 file so client can fetch and decompress directly"""
    from django.db.models import Q
    from datetime import datetime, timedelta
    
    logger.info(f"Loading keyword data for project {project_id} by user {request.user.username}")
    
    try:
        # Ensure user has access to the project (owner or member)
        project = get_object_or_404(
            Project.objects.filter(
                Q(user=request.user) | Q(memberships__user=request.user)
            ).distinct(),
            id=project_id
        )
        
        logger.info(f"Found project: {project.domain}, path: {project.dataforseo_keywords_path}")
        
        # Check if project has keyword data
        if not project.dataforseo_keywords_path:
            return JsonResponse({
                'success': False,
                'error': 'No keyword data available for this project. Please run keyword analysis first.'
            })
        
        # Initialize S3 client for R2
        s3_client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name='auto'
        )
        
        try:
            # Generate a presigned URL for the R2 file (valid for 1 hour)
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                    'Key': project.dataforseo_keywords_path
                },
                ExpiresIn=3600  # 1 hour
            )
            
            logger.info(f"Generated presigned URL for project {project_id}")
            
            # Return the presigned URL for client-side fetching
            return JsonResponse({
                'success': True,
                'data': {
                    'presigned_url': presigned_url,
                    'domain': project.domain,
                    'updated_at': project.dataforseo_keywords_updated_at.isoformat() if project.dataforseo_keywords_updated_at else None,
                    'file_path': project.dataforseo_keywords_path
                }
            })
            
        except ClientError as e:
            logger.error(f"Error generating presigned URL for R2: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to generate access URL for keyword data.'
            })
            
    except Exception as e:
        logger.error(f"Error loading keyword data: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_http_methods(["POST"])
def refresh_keyword_data(request, project_id):
    """Trigger a refresh of keyword data for a project"""
    from project.tasks import fetch_domain_keywords_from_dataforseo
    from django.db.models import Q
    
    try:
        # Ensure user has access to the project (owner or member)
        project = get_object_or_404(
            Project.objects.filter(
                Q(user=request.user) | Q(memberships__user=request.user)
            ).distinct(),
            id=project_id
        )
        
        # Trigger the Celery task
        task = fetch_domain_keywords_from_dataforseo.delay(project_id)
        
        return JsonResponse({
            'success': True,
            'message': f'Keyword data refresh started for {project.domain}',
            'task_id': task.id
        })
        
    except Exception as e:
        logger.error(f"Error refreshing keyword data: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })