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
    
    # Get only the LATEST backlink profile for each project
    latest_profiles = []
    for project in user_projects:
        latest_profile = BacklinkProfile.objects.filter(
            project=project
        ).order_by('-created_at').first()
        if latest_profile:
            latest_profiles.append(latest_profile)
    
    # Calculate stats
    total_projects = user_projects.count()
    projects_with_backlinks = len(latest_profiles)
    total_backlinks = sum(profile.backlinks for profile in latest_profiles)
    avg_spam_scores = [p.backlinks_spam_score for p in latest_profiles if p.backlinks_spam_score is not None]
    avg_spam_score = sum(avg_spam_scores) / len(avg_spam_scores) if avg_spam_scores else 0
    
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
        can_fetch = True
        days_until_next_fetch = 0
        next_fetch_date = None
        is_locked = project.is_backlinks_locked()
        lockdown_days_remaining = project.get_backlinks_lockdown_days_remaining()
        
        # Check if domain is locked first
        if is_locked:
            can_fetch = False
            days_until_next_fetch = lockdown_days_remaining
        elif latest_profile:
            previous_profile = BacklinkProfile.objects.filter(
                project=project,
                created_at__lt=latest_profile.created_at
            ).order_by('-created_at').first()
            
            if previous_profile:
                loss_links = max(0, previous_profile.backlinks - latest_profile.backlinks)
            
            # Calculate if 30 days have passed
            days_since_fetch = (timezone.now() - latest_profile.created_at).days
            if days_since_fetch < 30:
                can_fetch = False
                days_until_next_fetch = 30 - days_since_fetch
                next_fetch_date = latest_profile.created_at + timedelta(days=30)
        
        # Format backlinks for display
        backlinks_formatted = format_backlinks(latest_profile.backlinks) if latest_profile else "0"
        
        project_data.append({
            'project': project,
            'profile': latest_profile,
            'loss_links': loss_links,
            'backlinks_formatted': backlinks_formatted,
            'can_fetch': can_fetch,
            'days_until_next_fetch': days_until_next_fetch,
            'next_fetch_date': next_fetch_date,
            'is_locked': is_locked,
            'lockdown_days_remaining': lockdown_days_remaining,
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
    
    # Calculate if refresh is allowed (30 days check)
    can_refresh = True
    days_until_refresh = 0
    next_refresh_date = None
    
    # Check if domain is locked due to no data
    is_locked = project.is_backlinks_locked()
    lockdown_days_remaining = project.get_backlinks_lockdown_days_remaining()
    
    if is_locked:
        can_refresh = False
        days_until_refresh = lockdown_days_remaining
    elif latest_profile:
        days_since_fetch = (timezone.now() - latest_profile.created_at).days
        if days_since_fetch < 30:
            can_refresh = False
            days_until_refresh = 30 - days_since_fetch
            next_refresh_date = (latest_profile.created_at + timedelta(days=30)).isoformat()
    
    context = {
        'project': project,
        'latest_profile': latest_profile,
        'profiles': profiles[:5],  # Show last 5 profiles
        'can_refresh': can_refresh,
        'days_until_refresh': days_until_refresh,
        'next_refresh_date': next_refresh_date,
        'is_locked': is_locked,
        'lockdown_days_remaining': lockdown_days_remaining,
    }
    
    return render(request, 'backlinks/detail.html', context)


@login_required
def fetch_backlinks(request, project_id):
    """
    Trigger backlink summary fetch for a project
    Enforces 30-day minimum interval between fetches
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    project = get_object_or_404(Project, id=project_id)
    
    # Check user has access
    if not (project.user == request.user or 
            project.memberships.filter(user=request.user).exists()):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Check if there's an existing profile and if 30 days have passed
    latest_profile = BacklinkProfile.objects.filter(
        project=project
    ).order_by('-created_at').first()
    
    if latest_profile:
        days_since_last_fetch = (timezone.now() - latest_profile.created_at).days
        
        if days_since_last_fetch < 30:
            days_remaining = 30 - days_since_last_fetch
            return JsonResponse({
                'error': f'Backlink data was fetched {days_since_last_fetch} days ago. Please wait {days_remaining} more days before fetching again.',
                'days_remaining': days_remaining,
                'last_fetch_date': latest_profile.created_at.isoformat(),
                'next_available_date': (latest_profile.created_at + timedelta(days=30)).isoformat()
            }, status=429)  # 429 Too Many Requests
    
    try:
        # Queue the task
        task = fetch_backlink_summary_from_dataforseo.delay(project_id, force=True)
        
        messages.success(request, f'Starting backlink data collection for {project.domain}. This will take 1-2 minutes.')
        
        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'message': f'Collecting backlink data for {project.domain}. Please wait 1-2 minutes and refresh the page.',
            'status': 'processing',
            'domain': project.domain
        })
    
    except Exception as e:
        messages.error(request, f'Error starting backlink collection: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': f'Failed to start backlink collection: {str(e)}'
        }, status=500)


@login_required
def fetch_detailed_backlinks(request, project_id):
    """
    Trigger detailed backlinks fetch for a project's latest profile
    Enforces 30-day minimum interval between fetches
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
    
    # Check if detailed backlinks were already collected and if 30 days have passed
    if latest_profile.backlinks_collected_at:
        days_since_last_fetch = (timezone.now() - latest_profile.backlinks_collected_at).days
        
        if days_since_last_fetch < 30:
            days_remaining = 30 - days_since_last_fetch
            return JsonResponse({
                'error': f'Detailed backlinks were fetched {days_since_last_fetch} days ago. Please wait {days_remaining} more days before fetching again.',
                'days_remaining': days_remaining,
                'last_fetch_date': latest_profile.backlinks_collected_at.isoformat(),
                'next_available_date': (latest_profile.backlinks_collected_at + timedelta(days=30)).isoformat()
            }, status=429)
    
    try:
        # Queue the detailed fetch task
        task = fetch_detailed_backlinks_from_dataforseo.delay(latest_profile.id)
        
        messages.success(request, f'Collecting detailed backlinks for {project.domain}. This process will take 3-5 minutes.')
        
        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'message': f'Collecting detailed backlinks for {project.domain}. This will take 3-5 minutes. The page will refresh automatically when complete.',
            'status': 'processing',
            'domain': project.domain,
            'estimated_time': '3-5 minutes'
        })
    
    except Exception as e:
        messages.error(request, f'Error starting detailed backlink collection: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': f'Failed to start detailed backlink collection: {str(e)}'
        }, status=500)


@login_required
def backlink_audit(request):
    """
    Backlink Audit interface for reviewing and filtering backlinks
    """
    # Get user's projects with backlink data
    user_projects = Project.objects.filter(
        Q(user=request.user) | Q(memberships__user=request.user),
        active=True
    ).distinct()
    
    # Get projects that have backlink data (both summary and detailed)
    projects_with_backlinks = []
    projects_for_audit = []  # Projects specifically with detailed backlink files
    
    for project in user_projects:
        # Get the most recent profile (any profile)
        latest_profile = BacklinkProfile.objects.filter(
            project=project
        ).order_by('-created_at').first()
        
        if latest_profile:
            # Calculate time since last data fetch
            time_since_update = timezone.now() - latest_profile.created_at
            if time_since_update.days > 0:
                time_display = f"{time_since_update.days} day{'s' if time_since_update.days > 1 else ''} ago"
            else:
                hours = time_since_update.seconds // 3600
                if hours > 0:
                    time_display = f"{hours} hour{'s' if hours > 1 else ''} ago"
                else:
                    minutes = (time_since_update.seconds % 3600) // 60
                    time_display = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            
            project_data = {
                'id': project.id,
                'domain': project.domain,
                'title': project.title,
                'profile_id': latest_profile.id,
                'backlinks_count': latest_profile.backlinks or 0,
                'referring_domains': latest_profile.referring_domains or 0,
                'referring_pages': latest_profile.referring_pages or 0,
                'domain_rank': latest_profile.rank or 0,
                'spam_score': latest_profile.backlinks_spam_score or 0,
                'collected_at': latest_profile.created_at,
                'time_since_update': time_display,
                'has_detailed_data': bool(latest_profile.backlinks_file_path and latest_profile.backlinks_file_path != ''),
                'is_locked': project.is_backlinks_locked(),
                'lockdown_days_remaining': project.get_backlinks_lockdown_days_remaining()
            }
            
            projects_with_backlinks.append(project_data)
            
            # Only add to audit list if it has detailed file
            if project_data['has_detailed_data']:
                projects_for_audit.append({
                    'id': project.id,
                    'domain': project.domain,
                    'title': project.title,
                    'profile_id': latest_profile.id,
                    'backlinks_count': latest_profile.backlinks_count_collected or 0,
                    'collected_at': latest_profile.backlinks_collected_at
                })
    
    import json
    
    context = {
        'projects': projects_for_audit,  # For dropdown - only with detailed files
        'all_projects': projects_with_backlinks,  # For project cards - all with any backlink data
        'projects_json': json.dumps(projects_for_audit, default=str),
    }
    
    return render(request, 'backlinks/audit.html', context)


@login_required
def get_backlinks_presigned_url(request, profile_id):
    """
    Generate a presigned URL for direct R2 access to backlinks file
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'GET method required'}, status=405)
    
    # Get the backlink profile
    profile = get_object_or_404(BacklinkProfile, id=profile_id)
    
    # Check user has access to this project
    if not (profile.project.user == request.user or 
            profile.project.memberships.filter(user=request.user).exists()):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    if not profile.backlinks_file_path:
        return JsonResponse({'error': 'No backlinks file available'}, status=404)
    
    try:
        # Import R2 service
        from services.r2_storage import R2StorageService
        
        r2_service = R2StorageService()
        
        # Generate presigned URL (valid for 1 hour)
        presigned_url = r2_service.get_presigned_url(
            key=profile.backlinks_file_path,
            expires_in=3600  # 1 hour
        )
        
        return JsonResponse({
            'success': True,
            'url': presigned_url,
            'expires_in': 3600,
            'profile': {
                'id': profile.id,
                'domain': profile.project.domain,
                'backlinks_count': profile.backlinks_count_collected or 0,
                'spam_score': profile.backlinks_spam_score or 0,
                'collected_at': profile.backlinks_collected_at.isoformat() if profile.backlinks_collected_at else None
            }
        })
    
    except Exception as e:
        return JsonResponse({'error': f'Error generating presigned URL: {str(e)}'}, status=500)
