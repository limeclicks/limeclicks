from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from core.utils import simple_paginate
from django.db.models import Q, Count, Prefetch, Max
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model
import json
from .models import Project, ProjectMember, ProjectRole, ProjectInvitation
from .forms import ProjectForm
from .permissions import ProjectPermission, user_can_view_project, user_can_delete_project, user_can_edit_project
from .email_service import send_project_invitation
from common.utils import create_ajax_response, get_logger

User = get_user_model()

logger = get_logger(__name__)


@login_required
def project_list(request):
    """List user's projects with search functionality"""
    search_query = request.GET.get('search', '').strip()
    
    # Get projects where user is owner or member with related data
    projects = Project.objects.filter(
        Q(user=request.user) | Q(memberships__user=request.user)
    ).distinct().prefetch_related(
        Prefetch('site_audits'),
        Prefetch('keywords'),
        Prefetch('memberships')
    ).annotate(
        keyword_count=Count('keywords', distinct=True),
        member_count=Count('memberships', distinct=True)
    )
    
    if search_query:
        projects = projects.filter(
            Q(domain__icontains=search_query) | 
            Q(title__icontains=search_query)
        )
    
    # Order by creation date
    projects = projects.order_by('-created_at')
    
    # Pagination using centralized utility
    pagination_context = simple_paginate(request, projects, 12)
    projects_page = pagination_context['page_obj']
    
    # Add role and additional information to each project
    projects_with_info = []
    for project in projects_page:
        role = ProjectPermission.get_user_role(request.user, project)
        
        # Get latest site audit
        latest_audit = project.site_audits.order_by('-created_at').first()
        audit_score = None
        audit_status = None
        audit_id = None
        if latest_audit:
            audit_status = latest_audit.status
            audit_id = latest_audit.id
            # Use overall_site_health_score field - handle 0 scores properly
            if latest_audit.overall_site_health_score is not None:
                audit_score = int(latest_audit.overall_site_health_score)
            else:
                # If score is None but audit is completed, set to 0
                if audit_status == 'completed':
                    audit_score = 0
        
        # Get keyword statistics
        keywords = project.keywords.all()
        keywords_in_top_10 = keywords.filter(rank__lte=10, rank__gt=0).count()
        keywords_tracked = keywords.filter(rank__gt=0).count()
        
        # Get domain rank from latest backlink profile
        domain_rank = None
        try:
            from backlinks.models import BacklinkProfile
            latest_backlink_profile = BacklinkProfile.objects.filter(
                project=project
            ).order_by('-created_at').first()
            if latest_backlink_profile and latest_backlink_profile.rank:
                domain_rank = latest_backlink_profile.rank
        except:
            pass
        
        projects_with_info.append({
            'project': project,
            'role': role,
            'is_owner': role == ProjectRole.OWNER,
            'can_delete': user_can_delete_project(request.user, project),
            'can_edit': user_can_edit_project(request.user, project),
            'audit_score': audit_score,
            'audit_status': audit_status,
            'audit_id': audit_id,
            'keyword_count': project.keyword_count,
            'keywords_in_top_10': keywords_in_top_10,
            'keywords_tracked': keywords_tracked,
            'member_count': project.member_count,
            'domain_rank': domain_rank,
        })
    
    # Check if it's an HTMX request for partial updates
    if request.headers.get('HX-Request'):
        template = 'project/partials/project_cards_clean.html'
    else:
        template = 'project/project_list.html'
    
    return render(request, template, {
        'projects': projects_page,
        'projects_with_info': projects_with_info,
        'search_query': search_query,
        'total_projects': projects.count(),
        'page_obj': projects_page
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
            
            # Create owner membership
            ProjectMember.objects.create(
                project=project,
                user=request.user,
                role=ProjectRole.OWNER
            )
            
            # Handle sharing if emails provided
            share_emails = data.get('share_emails', '').strip()
            if share_emails:
                email_list = [email.strip().lower() for email in share_emails.split(',')]
                for email in email_list:
                    if not email:
                        continue
                    
                    try:
                        # Check if user exists
                        try:
                            existing_user = User.objects.get(email__iexact=email)
                            # Add existing user as member
                            ProjectMember.objects.create(
                                project=project,
                                user=existing_user,
                                role=ProjectRole.MEMBER
                            )
                            # Send notification email
                            send_project_invitation(
                                email=email,
                                project=project,
                                inviter=request.user,
                                is_existing_user=True,
                                user_name=existing_user.get_full_name() or existing_user.username
                            )
                        except User.DoesNotExist:
                            # Create invitation for new user
                            invitation = ProjectInvitation.objects.create(
                                project=project,
                                email=email,
                                role=ProjectRole.MEMBER,
                                invited_by=request.user
                            )
                            # Send invitation email
                            send_project_invitation(
                                email=email,
                                project=project,
                                inviter=request.user,
                                is_existing_user=False,
                                invitation_token=invitation.token
                            )
                    except Exception as e:
                        logger.error(f"Error inviting {email} during project creation: {str(e)}")
            
            return create_ajax_response(
                success=True,
                message='Project created successfully!',
                data={
                    'project': {
                        'id': project.id,
                        'domain': project.domain,
                        'title': project.title or 'Untitled',
                        'active': project.active,
                        'created_at': project.created_at.strftime('%Y-%m-%d %H:%M:%S')
                    }
                }
            )
        else:
            return create_ajax_response(
                success=False,
                message='Validation failed',
                data={'errors': form.errors}
            )
    
    except json.JSONDecodeError:
        logger.error("Invalid JSON data in project_create")
        return create_ajax_response(
            success=False,
            message='Invalid JSON data'
        )
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}")
        return create_ajax_response(
            success=False,
            message=str(e)
        )


@login_required
@require_http_methods(["POST"])
def project_delete(request, project_id):
    """Delete a project via AJAX"""
    try:
        project = get_object_or_404(Project, id=project_id)
        
        # Check if user has permission to delete
        if not user_can_delete_project(request.user, project):
            return create_ajax_response(
                success=False,
                message='You do not have permission to delete this project.'
            )
        domain = project.domain
        project.delete()
        
        return create_ajax_response(
            success=True,
            message=f'Project {domain} deleted successfully!'
        )
    except Project.DoesNotExist:
        return create_ajax_response(
            success=False,
            message='Project not found or you do not have permission to delete it.'
        )
    except Exception as e:
        return create_ajax_response(
            success=False,
            message=str(e)
        )




@login_required
@require_http_methods(["POST"])
def project_toggle_active(request, project_id):
    """Toggle project active status via AJAX"""
    try:
        project = get_object_or_404(Project, id=project_id)
        
        # Check if user has permission to edit
        if not user_can_edit_project(request.user, project):
            return JsonResponse({
                'success': False,
                'message': 'You do not have permission to modify this project.'
            })
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
        return create_ajax_response(
            success=False,
            message=str(e)
        )


