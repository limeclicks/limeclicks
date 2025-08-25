from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_control
from django.core.cache import cache
import json
import requests
import hashlib
from .models import Project
from .forms import ProjectForm


@login_required
def project_list(request):
    """List user's projects with search functionality"""
    search_query = request.GET.get('search', '').strip()
    projects = Project.objects.filter(user=request.user)
    
    if search_query:
        projects = projects.filter(
            Q(domain__icontains=search_query) | 
            Q(title__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(projects, 10)  # 10 projects per page
    page_number = request.GET.get('page')
    projects_page = paginator.get_page(page_number)
    
    return render(request, 'project/project_list.html', {
        'projects': projects_page,
        'search_query': search_query,
        'total_projects': Project.objects.filter(user=request.user).count()
    })


@login_required
@require_http_methods(["POST"])
def project_create(request):
    """Create a new project via AJAX"""
    try:
        data = json.loads(request.body)
        form = ProjectForm(data)
        
        if form.is_valid():
            project = form.save(commit=False)
            project.user = request.user
            project.save()  # This will trigger the signal to auto-queue audits
            
            return JsonResponse({
                'success': True,
                'message': 'Project created successfully!',
                'project': {
                    'id': project.id,
                    'domain': project.domain,
                    'title': project.title or 'Untitled',
                    'active': project.active,
                    'created_at': project.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'errors': {'__all__': ['Invalid JSON data']}
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'errors': {'__all__': [str(e)]}
        })


@login_required
@require_http_methods(["POST"])
def project_delete(request, project_id):
    """Delete a project via AJAX"""
    try:
        project = get_object_or_404(Project, id=project_id, user=request.user)
        domain = project.domain
        project.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Project {domain} deleted successfully!'
        })
    except Project.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Project not found or you do not have permission to delete it.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })




@login_required
@require_http_methods(["POST"])
def project_toggle_active(request, project_id):
    """Toggle project active status via AJAX"""
    try:
        project = get_object_or_404(Project, id=project_id, user=request.user)
        project.active = not project.active
        project.save()
        
        return JsonResponse({
            'success': True,
            'active': project.active,
            'message': f'Project {project.domain} {"activated" if project.active else "deactivated"}!'
        })
    except Project.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Project not found or you do not have permission to modify it.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


