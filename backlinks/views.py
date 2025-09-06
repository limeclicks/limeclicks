from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Avg, Q, Max
from django.utils import timezone
from datetime import timedelta
from project.models import Project, ProjectMember
from .models import BacklinkProfile
from .tasks import fetch_backlink_summary_from_dataforseo, fetch_detailed_backlinks_from_dataforseo


@login_required
def backlinks_list(request):
    """
    Main backlinks listing page with stats cards and project listing
    """
    # Get user's projects
    user_projects = Project.objects.filter(
        Q(user=request.user) | Q(memberships__user=request.user),
        active=True
    ).distinct()
    
    context = {
        'projects': user_projects,
        'total_projects': user_projects.count(),
    }
    
    return render(request, 'backlinks/list.html', context)


@login_required
def htmx_backlinks_stats(request):
    """
    HTMX endpoint for backlinks stats cards
    """
    # Get user's projects
    user_projects = Project.objects.filter(
        Q(user=request.user) | Q(memberships__user=request.user),
        active=True
    ).distinct()
    
    # Get latest backlink profiles for these projects
    latest_profiles = BacklinkProfile.objects.filter(
        project__in=user_projects
    ).select_related('project')
    
    # Calculate stats
    total_projects = user_projects.count()
    projects_with_backlinks = latest_profiles.values('project').distinct().count()
    total_backlinks = sum(profile.backlinks for profile in latest_profiles)
    avg_spam_score = latest_profiles.aggregate(avg_spam=Avg('backlinks_spam_score'))['avg_spam'] or 0
    
    # Format total backlinks for display
    if total_backlinks >= 1000000:
        total_backlinks_formatted = f"{total_backlinks/1000000:.1f}M"
    elif total_backlinks >= 1000:
        total_backlinks_formatted = f"{total_backlinks/1000:.1f}K"
    else:
        total_backlinks_formatted = f"{total_backlinks:,}"
    
    context = {
        'total_projects': total_projects,
        'projects_with_backlinks': projects_with_backlinks,
        'total_backlinks': total_backlinks,
        'total_backlinks_formatted': total_backlinks_formatted,
        'avg_spam_score': round(avg_spam_score, 1),
    }
    
    return render(request, 'backlinks/htmx/stats_cards.html', context)


@login_required
def htmx_backlinks_projects(request):
    """
    HTMX endpoint for projects listing with backlink data
    """
    # Get user's projects
    user_projects = Project.objects.filter(
        Q(user=request.user) | Q(memberships__user=request.user),
        active=True
    ).distinct().select_related('user')
    
    # Helper function to format backlinks
    def format_backlinks(count):
        if count >= 1000000:
            return f"{count/1000000:.1f}M"
        elif count >= 1000:
            return f"{count/1000:.1f}K"
        else:
            return f"{count:,}"
    
    # Get latest backlink profiles for each project
    project_data = []
    for project in user_projects:
        latest_profile = BacklinkProfile.objects.filter(
            project=project
        ).order_by('-created_at').first()
        
        # Calculate loss (difference from previous profile if exists)
        loss_links = 0
        if latest_profile:
            previous_profile = BacklinkProfile.objects.filter(
                project=project,
                created_at__lt=latest_profile.created_at
            ).order_by('-created_at').first()
            
            if previous_profile:
                loss_links = max(0, previous_profile.backlinks - latest_profile.backlinks)
        
        # Format backlinks for display
        backlinks_formatted = format_backlinks(latest_profile.backlinks) if latest_profile else "0"
        
        project_data.append({
            'project': project,
            'profile': latest_profile,
            'loss_links': loss_links,
            'backlinks_formatted': backlinks_formatted,
        })
    
    context = {
        'project_data': project_data,
    }
    
    return render(request, 'backlinks/htmx/projects_list.html', context)


@login_required
def backlinks_detail(request, project_id):
    """
    Detailed view for a specific project's backlinks
    """
    project = get_object_or_404(Project, id=project_id)
    
    # Check user has access to this project
    if not (project.user == request.user or 
            project.memberships.filter(user=request.user).exists()):
        messages.error(request, "You don't have access to this project.")
        return redirect('backlinks:list')
    
    # Get backlink profiles for this project
    profiles = BacklinkProfile.objects.filter(
        project=project
    ).order_by('-created_at')
    
    latest_profile = profiles.first()
    
    context = {
        'project': project,
        'latest_profile': latest_profile,
        'profiles': profiles[:5],  # Show last 5 profiles
    }
    
    return render(request, 'backlinks/detail.html', context)


@login_required
def fetch_backlinks(request, project_id):
    """
    Trigger backlink summary fetch for a project
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    project = get_object_or_404(Project, id=project_id)
    
    # Check user has access
    if not (project.user == request.user or 
            project.memberships.filter(user=request.user).exists()):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    try:
        # Queue the task
        task = fetch_backlink_summary_from_dataforseo.delay(project_id, force=True)
        
        messages.success(request, f'Backlink fetch queued for {project.domain}. This may take a few minutes.')
        
        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'message': f'Backlink fetch queued for {project.domain}'
        })
    
    except Exception as e:
        messages.error(request, f'Error queuing backlink fetch: {str(e)}')
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def fetch_detailed_backlinks(request, project_id):
    """
    Trigger detailed backlinks fetch for a project's latest profile
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    project = get_object_or_404(Project, id=project_id)
    
    # Check user has access
    if not (project.user == request.user or 
            project.memberships.filter(user=request.user).exists()):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Get latest profile
    latest_profile = BacklinkProfile.objects.filter(
        project=project
    ).order_by('-created_at').first()
    
    if not latest_profile:
        messages.error(request, 'No backlink profile found. Please fetch summary first.')
        return JsonResponse({'error': 'No backlink profile found'}, status=400)
    
    try:
        # Queue the detailed fetch task
        task = fetch_detailed_backlinks_from_dataforseo.delay(latest_profile.id)
        
        messages.success(request, f'Detailed backlink fetch queued for {project.domain}. This may take several minutes.')
        
        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'message': f'Detailed backlink fetch queued for {project.domain}'
        })
    
    except Exception as e:
        messages.error(request, f'Error queuing detailed backlink fetch: {str(e)}')
        return JsonResponse({'error': str(e)}, status=500)
