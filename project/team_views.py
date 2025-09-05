from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.template.loader import render_to_string
from django.db.models import Count, Q, Prefetch
from core.utils import simple_paginate
import json
from .models import Project, ProjectMember, ProjectInvitation, ProjectRole, InvitationStatus
from .permissions import ProjectPermission, user_can_manage_team
from common.utils import create_ajax_response, get_logger
from .email_service import send_project_invitation

logger = get_logger(__name__)
User = get_user_model()


@login_required
def team_projects_list(request):
    """List all projects with team information"""
    # Get all projects the user has access to
    user_projects = Project.objects.filter(
        Q(user=request.user) |  # Owner (original creator)
        Q(memberships__user=request.user)  # Member (through ProjectMember)
    ).distinct().prefetch_related(
        Prefetch('memberships', queryset=ProjectMember.objects.select_related('user')),
        Prefetch('invitations', queryset=ProjectInvitation.objects.filter(status=InvitationStatus.PENDING))
    ).annotate(
        member_count=Count('memberships', distinct=True),
        pending_invitations=Count('invitations', filter=Q(invitations__status=InvitationStatus.PENDING), distinct=True)
    ).order_by('-created_at')
    
    # Add user role for each project
    projects_with_info = []
    for project in user_projects:
        user_role = ProjectPermission.get_user_role(request.user, project)
        is_owner = user_role == ProjectRole.OWNER
        
        # Get team member names (first 3)
        member_names = list(project.memberships.values_list('user__first_name', 'user__last_name')[:3])
        member_display = []
        for first, last in member_names:
            if first or last:
                name = f"{first or ''} {last or ''}".strip()
            else:
                name = "Team Member"
            member_display.append(name)
        
        # Check if there are more members
        total_members = project.member_count
        if total_members > 3:
            member_display.append(f"+{total_members - 3} more")
        
        projects_with_info.append({
            'project': project,
            'user_role': user_role,
            'is_owner': is_owner,
            'member_count': total_members,
            'pending_invitations': project.pending_invitations,
            'member_display': ', '.join(member_display) if member_display else 'No team members yet',
            'total_team_size': total_members + project.pending_invitations
        })
    
    # Pagination using centralized utility
    pagination_context = simple_paginate(request, projects_with_info, 12)
    page_obj = pagination_context['page_obj']
    
    # Check if it's an HTMX request for partial updates
    if request.headers.get('HX-Request'):
        template = 'project/partials/team_project_cards.html'
    else:
        template = 'project/team_projects_list.html'
    
    context = {
        'page_obj': page_obj,
        'projects_with_info': page_obj.object_list,
        'has_projects': len(user_projects) > 0,
        'total_projects': len(user_projects),
    }
    
    return render(request, template, context)


@login_required
def team_management(request, project_id):
    """Team management page with HTMX"""
    project = get_object_or_404(Project, id=project_id)
    
    if not ProjectPermission.has_permission(request.user, project, ProjectPermission.VIEW_PROJECT):
        raise PermissionDenied("You don't have permission to view this project")
    
    can_manage = user_can_manage_team(request.user, project)
    user_role = ProjectPermission.get_user_role(request.user, project)
    
    members = project.memberships.select_related('user')
    invitations = ProjectInvitation.objects.filter(
        project=project, 
        status=InvitationStatus.PENDING
    ).select_related('invited_by')
    
    context = {
        'project': project,
        'members': members,
        'invitations': invitations,
        'can_manage': can_manage,
        'user_role': user_role,
        'ProjectRole': ProjectRole,
    }
    
    return render(request, 'project/team_management.html', context)


@login_required
@require_http_methods(["POST"])
def invite_users(request, project_id):
    """HTMX endpoint to invite users to project"""
    project = get_object_or_404(Project, id=project_id)
    
    if not user_can_manage_team(request.user, project):
        return HttpResponse(
            '<div class="alert alert-danger">You don\'t have permission to manage this team</div>',
            status=403
        )
    
    emails = request.POST.get('emails', '').strip()
    role = ProjectRole.MEMBER  # All invited users are members
    
    if not emails:
        return HttpResponse(
            '<div class="alert alert-danger">Please provide at least one email address</div>',
            status=400
        )
    
    email_list = [email.strip().lower() for email in emails.split(',')]
    results = {'invited': [], 'already_member': [], 'errors': []}
    
    with transaction.atomic():
        for email in email_list:
            if not email:
                continue
                
            try:
                # Check if user is already a member
                existing_member = ProjectMember.objects.filter(
                    project=project,
                    user__email__iexact=email
                ).first()
                
                if existing_member:
                    results['already_member'].append(email)
                    continue
                
                # Check if user exists
                try:
                    user = User.objects.get(email__iexact=email)
                    # Add existing user as member
                    ProjectMember.objects.create(
                        project=project,
                        user=user,
                        role=role
                    )
                    # Send notification email
                    send_project_invitation(
                        email=email,
                        project=project,
                        inviter=request.user,
                        is_existing_user=True,
                        user_name=user.get_full_name() or user.username
                    )
                    results['invited'].append(email)
                    
                except User.DoesNotExist:
                    # Create invitation for new user
                    invitation, created = ProjectInvitation.objects.get_or_create(
                        project=project,
                        email=email,
                        status=InvitationStatus.PENDING,
                        defaults={
                            'role': role,
                            'invited_by': request.user
                        }
                    )
                    
                    if created:
                        # Send invitation email
                        send_project_invitation(
                            email=email,
                            project=project,
                            inviter=request.user,
                            is_existing_user=False,
                            invitation_token=invitation.token
                        )
                        results['invited'].append(email)
                    else:
                        # Resend invitation if it already exists
                        invitation.regenerate_token()
                        send_project_invitation(
                            email=email,
                            project=project,
                            inviter=request.user,
                            is_existing_user=False,
                            invitation_token=invitation.token
                        )
                        results['invited'].append(email)
                        
            except Exception as e:
                logger.error(f"Error inviting {email}: {str(e)}")
                results['errors'].append(f"{email}: {str(e)}")
    
    # Refresh member and invitation lists
    members = ProjectMember.objects.filter(project=project).select_related('user')
    invitations = ProjectInvitation.objects.filter(
        project=project,
        status=InvitationStatus.PENDING
    ).select_related('invited_by')
    
    context = {
        'project': project,
        'members': members,
        'invitations': invitations,
        'can_manage': True,
        'ProjectRole': ProjectRole,
        'results': results,
    }
    
    return render(request, 'project/partials/team_members_list.html', context)


@login_required
@require_http_methods(["DELETE"])
def remove_member(request, project_id, member_id):
    """HTMX endpoint to remove a team member"""
    project = get_object_or_404(Project, id=project_id)
    
    if not user_can_manage_team(request.user, project):
        return HttpResponse(
            '<div class="alert alert-danger">You don\'t have permission to manage this team</div>',
            status=403
        )
    
    member = get_object_or_404(ProjectMember, id=member_id, project=project)
    
    # Prevent removing the owner
    if member.role == ProjectRole.OWNER:
        return HttpResponse(
            '<div class="alert alert-danger">Cannot remove the project owner</div>',
            status=400
        )
    
    # Prevent removing yourself if you're the only owner
    if member.user == request.user:
        owner_count = ProjectMember.objects.filter(
            project=project,
            role=ProjectRole.OWNER
        ).count()
        if owner_count == 1:
            return HttpResponse(
                '<div class="alert alert-danger">Cannot remove yourself as the only owner</div>',
                status=400
            )
    
    member.delete()
    
    # Return updated member list
    members = ProjectMember.objects.filter(project=project).select_related('user')
    invitations = ProjectInvitation.objects.filter(
        project=project,
        status=InvitationStatus.PENDING
    ).select_related('invited_by')
    
    context = {
        'project': project,
        'members': members,
        'invitations': invitations,
        'can_manage': True,
        'ProjectRole': ProjectRole,
        'message': f'Successfully removed {member.user.email} from the project',
    }
    
    return render(request, 'project/partials/team_members_list.html', context)


# Role update removed - all non-owners are members with same permissions


@login_required
@require_http_methods(["POST"])
def resend_invitation(request, project_id, invitation_id):
    """HTMX endpoint to resend an invitation"""
    project = get_object_or_404(Project, id=project_id)
    
    if not user_can_manage_team(request.user, project):
        return HttpResponse(
            '<div class="alert alert-danger">You don\'t have permission to manage this team</div>',
            status=403
        )
    
    invitation = get_object_or_404(ProjectInvitation, id=invitation_id, project=project)
    
    if invitation.status != InvitationStatus.PENDING:
        return HttpResponse(
            '<div class="alert alert-danger">Can only resend pending invitations</div>',
            status=400
        )
    
    # Regenerate token and resend
    invitation.regenerate_token()
    send_project_invitation(
        email=invitation.email,
        project=project,
        inviter=request.user,
        is_existing_user=False,
        invitation_token=invitation.token
    )
    
    # Return updated invitation row
    context = {
        'invitation': invitation,
        'project': project,
        'can_manage': True,
    }
    
    return render(request, 'project/partials/invitation_row.html', context)


@login_required
@require_http_methods(["DELETE"])
def revoke_invitation(request, project_id, invitation_id):
    """HTMX endpoint to revoke an invitation"""
    project = get_object_or_404(Project, id=project_id)
    
    if not user_can_manage_team(request.user, project):
        return HttpResponse(
            '<div class="alert alert-danger">You don\'t have permission to manage this team</div>',
            status=403
        )
    
    invitation = get_object_or_404(ProjectInvitation, id=invitation_id, project=project)
    
    if invitation.status != InvitationStatus.PENDING:
        return HttpResponse(
            '<div class="alert alert-danger">Can only revoke pending invitations</div>',
            status=400
        )
    
    invitation.revoke()
    
    # Return empty response to remove the row
    return HttpResponse('')


def accept_invitation(request, token):
    """Accept an invitation to join a project"""
    invitation = get_object_or_404(ProjectInvitation, token=token)
    
    if not invitation.is_valid():
        context = {
            'error': 'This invitation is no longer valid',
            'invitation': invitation
        }
        return render(request, 'project/invitation_error.html', context)
    
    if not request.user.is_authenticated:
        # Store invitation token in session and redirect to registration
        request.session['invitation_token'] = str(token)
        return redirect('accounts:register')
    
    # Accept invitation for logged-in user
    try:
        invitation.accept(request.user)
        return redirect('project:team_management', project_id=invitation.project.id)
    except ValueError as e:
        context = {
            'error': str(e),
            'invitation': invitation
        }
        return render(request, 'project/invitation_error.html', context)