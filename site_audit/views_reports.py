from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.utils import timezone
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
from django.conf import settings
import logging

from project.models import Project
from project.permissions import user_can_view_project
from .models import SiteAudit, AuditFile
from limeclicks.storage_backends import CloudflareR2Storage

logger = logging.getLogger(__name__)


@login_required
def site_audit_reports_list(request):
    """List all available site audit reports for user's projects"""
    # Get all projects user has access to
    user_projects = Project.objects.filter(
        Q(user=request.user) | Q(members=request.user)
    ).distinct().order_by('domain')
    
    # Get selected project
    selected_project_id = request.GET.get('project')
    selected_project = None
    audit_files = []
    
    if selected_project_id:
        try:
            selected_project = get_object_or_404(Project, id=selected_project_id)
            if not user_can_view_project(request.user, selected_project):
                raise Http404("Project not found")
            
            # Get the latest site audit for this project
            latest_audit = SiteAudit.objects.filter(
                project=selected_project,
                status='completed'
            ).order_by('-last_audit_date').first()
            
            if latest_audit:
                # Get all audit files for the latest audit
                audit_files = AuditFile.objects.filter(
                    site_audit=latest_audit
                ).order_by('file_type')
            else:
                # If no last_audit_date, try ordering by created_at
                latest_audit = SiteAudit.objects.filter(
                    project=selected_project,
                    status='completed'
                ).order_by('-created_at').first()
                
                if latest_audit:
                    audit_files = AuditFile.objects.filter(
                        site_audit=latest_audit
                    ).order_by('file_type')
        except (ValueError, Project.DoesNotExist):
            pass
    
    context = {
        'projects': user_projects,
        'selected_project': selected_project,
        'selected_project_id': selected_project_id,
        'audit_files': audit_files,
        'has_audit': bool(audit_files)
    }
    
    return render(request, 'site_audit/reports_list.html', context)


@login_required
@require_http_methods(['GET'])
def get_project_audit_files(request, project_id):
    """Get audit files for a specific project via AJAX"""
    project = get_object_or_404(Project, id=project_id)
    
    if not user_can_view_project(request.user, project):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Get the latest completed audit
    latest_audit = SiteAudit.objects.filter(
        project=project,
        status='completed'
    ).order_by('-last_audit_date').first()
    
    if not latest_audit:
        return JsonResponse({
            'success': False,
            'message': 'No completed audit found for this project',
            'files': []
        })
    
    # Get all files for this audit with human-friendly names
    files_data = []
    for audit_file in latest_audit.audit_files.all():
        files_data.append({
            'id': audit_file.id,
            'type': audit_file.file_type,
            'display_name': get_human_friendly_name(audit_file),
            'original_filename': audit_file.original_filename,
            'size': format_file_size(audit_file.file_size),
            'uploaded_at': audit_file.uploaded_at.strftime('%Y-%m-%d %H:%M'),
            'download_url': f'/site-audit/reports/download/{audit_file.id}/'
        })
    
    return JsonResponse({
        'success': True,
        'audit_date': latest_audit.last_audit_date.strftime('%Y-%m-%d %H:%M') if latest_audit.last_audit_date else 'Unknown',
        'total_pages_crawled': latest_audit.total_pages_crawled,
        'health_score': latest_audit.overall_site_health_score,
        'files': files_data
    })


@login_required
def download_audit_file(request, file_id):
    """Download a specific audit file from R2"""
    audit_file = get_object_or_404(AuditFile, id=file_id)
    
    # Check permissions
    if not user_can_view_project(request.user, audit_file.site_audit.project):
        raise Http404("File not found")
    
    try:
        # Initialize R2 client
        s3_client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name='auto'
        )
        
        # Get the file from R2
        response = s3_client.get_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=audit_file.r2_path
        )
        
        # Prepare the response with human-friendly filename
        file_content = response['Body'].read()
        human_friendly_name = get_download_filename(audit_file)
        
        http_response = HttpResponse(
            file_content,
            content_type=audit_file.mime_type or 'text/csv'
        )
        http_response['Content-Disposition'] = f'attachment; filename="{human_friendly_name}"'
        http_response['Content-Length'] = len(file_content)
        
        return http_response
        
    except ClientError as e:
        logger.error(f"Error downloading file from R2: {e}")
        if e.response['Error']['Code'] == 'NoSuchKey':
            raise Http404("File not found in storage")
        raise Http404("Error downloading file")
    except Exception as e:
        logger.error(f"Unexpected error downloading file: {e}")
        raise Http404("Error downloading file")


@login_required
@require_http_methods(['POST'])
def download_all_audit_files(request, project_id):
    """Generate a ZIP file with all audit files for a project"""
    import zipfile
    import io
    
    project = get_object_or_404(Project, id=project_id)
    
    if not user_can_view_project(request.user, project):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Get the latest completed audit
    latest_audit = SiteAudit.objects.filter(
        project=project,
        status='completed'
    ).order_by('-last_audit_date').first()
    
    if not latest_audit:
        return JsonResponse({'error': 'No completed audit found'}, status=404)
    
    try:
        # Initialize R2 client
        s3_client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name='auto'
        )
        
        # Create ZIP file in memory
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for audit_file in latest_audit.audit_files.all():
                try:
                    # Get file from R2
                    response = s3_client.get_object(
                        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                        Key=audit_file.r2_path
                    )
                    
                    file_content = response['Body'].read()
                    filename = get_download_filename(audit_file)
                    
                    # Add to ZIP
                    zip_file.writestr(filename, file_content)
                    
                except Exception as e:
                    logger.error(f"Error adding file to ZIP: {e}")
                    continue
        
        # Prepare response
        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer.read(), content_type='application/zip')
        
        # Create filename with domain and date
        audit_date = latest_audit.last_audit_date.strftime('%Y-%m-%d') if latest_audit.last_audit_date else 'latest'
        zip_filename = f"{project.domain}_site_audit_{audit_date}.zip"
        
        response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
        
        return response
        
    except Exception as e:
        logger.error(f"Error creating ZIP file: {e}")
        return JsonResponse({'error': 'Error creating download'}, status=500)


def get_human_friendly_name(audit_file):
    """Generate human-friendly display name for audit file"""
    # Check if it's an Excel file (consolidated report)
    if audit_file.original_filename.endswith('.xlsx'):
        # Use the filename without extension as display name
        display_name = audit_file.original_filename.replace('.xlsx', '').replace('_', ' ')
        return display_name
    
    # For CSV files, use the mapping
    name_mapping = {
        'crawl_overview': 'Crawl Overview Report',
        'issues_overview': 'Issues Summary Report',
        'internal_all': 'All Internal URLs',
        'external_all': 'All External URLs',
        'response_codes': 'Response Codes (4xx, 5xx, etc.)',
        'page_titles': 'Page Titles Analysis',
        'meta_descriptions': 'Meta Descriptions Analysis',
        'h1': 'H1 Tags Analysis',
        'h2': 'H2 Tags Analysis',
        'images': 'Images Analysis',
        'canonicals': 'Canonical URLs',
        'directives': 'Robots & Meta Directives',
        'hreflang': 'Hreflang Tags',
        'structured_data': 'Structured Data (Schema)',
        'links': 'Links Analysis',
        'javascript': 'JavaScript Files',
        'validation': 'HTML Validation',
        # New Excel report types
        'technical_seo_audit': 'Technical SEO Audit (Complete)',
        'content_optimization': 'Content Optimization Report',
        'technical_config': 'Technical Configuration',
        'media_analysis': 'Media & Resources Analysis',
        'link_analysis': 'Link Analysis Report',
        'page_performance': 'Page Performance Report',
        'security': 'Security & HTTPS Report',
        'audit_summary': 'Audit Summary Overview',
    }
    
    return name_mapping.get(audit_file.file_type, audit_file.get_file_type_display())


def get_download_filename(audit_file):
    """Generate human-friendly filename for download"""
    # Get project domain
    domain = audit_file.site_audit.project.domain.replace('.', '_')
    
    # Get audit date
    audit_date = audit_file.site_audit.last_audit_date.strftime('%Y%m%d') if audit_file.site_audit.last_audit_date else 'latest'
    
    # Map file types to friendly names
    filename_mapping = {
        'crawl_overview': 'crawl_overview',
        'issues_overview': 'issues_summary',
        'internal_all': 'internal_urls',
        'external_all': 'external_urls',
        'response_codes': 'response_codes',
        'page_titles': 'page_titles',
        'meta_descriptions': 'meta_descriptions',
        'h1': 'h1_tags',
        'h2': 'h2_tags',
        'images': 'images',
        'canonicals': 'canonical_urls',
        'directives': 'robots_directives',
        'hreflang': 'hreflang',
        'structured_data': 'structured_data',
        'links': 'links',
        'javascript': 'javascript',
        'validation': 'html_validation',
    }
    
    file_type = filename_mapping.get(audit_file.file_type, audit_file.file_type)
    
    return f"{domain}_{file_type}_{audit_date}.csv"


def format_file_size(size_bytes):
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"