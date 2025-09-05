"""
Permission utility functions
Core functions for checking project permissions
"""

from typing import Optional, List
from django.contrib.auth.models import User
from django.db.models import Q, QuerySet
from django.core.exceptions import PermissionDenied
from django.http import Http404

from project.models import Project, ProjectMember, ProjectRole
from project.permissions import ProjectPermission


def check_project_access(user: User, project: Project, 
                         raise_exception: bool = True) -> bool:
    """
    Check if user has any access to the project (owner or member)
    
    Args:
        user: The user to check
        project: The project to check access for
        raise_exception: If True, raise PermissionDenied if no access
        
    Returns:
        True if user has access, False otherwise
        
    Raises:
        PermissionDenied: If raise_exception=True and user has no access
    """
    if not user.is_authenticated:
        if raise_exception:
            raise PermissionDenied("Authentication required")
        return False
    
    # Superusers always have access
    if user.is_superuser:
        return True
    
    # Check if user is owner or member
    has_access = (
        project.user == user or 
        project.members.filter(id=user.id).exists()
    )
    
    if not has_access and raise_exception:
        raise PermissionDenied("You don't have access to this project")
    
    return has_access


def check_project_owner(user: User, project: Project,
                       raise_exception: bool = True) -> bool:
    """
    Check if user is the project owner
    
    Args:
        user: The user to check
        project: The project to check ownership for
        raise_exception: If True, raise PermissionDenied if not owner
        
    Returns:
        True if user is owner, False otherwise
        
    Raises:
        PermissionDenied: If raise_exception=True and user is not owner
    """
    if not user.is_authenticated:
        if raise_exception:
            raise PermissionDenied("Authentication required")
        return False
    
    # Superusers are treated as owners
    if user.is_superuser:
        return True
    
    is_owner = project.user == user
    
    if not is_owner and raise_exception:
        raise PermissionDenied("Only project owner can perform this action")
    
    return is_owner


def get_user_project_role(user: User, project: Project) -> Optional[str]:
    """
    Get the user's role in a project
    
    Args:
        user: The user to check
        project: The project to check
        
    Returns:
        'owner', 'member', or None
    """
    if not user.is_authenticated:
        return None
    
    if user.is_superuser:
        return ProjectRole.OWNER
    
    if project.user == user:
        return ProjectRole.OWNER
    
    try:
        membership = ProjectMember.objects.get(project=project, user=user)
        return membership.role
    except ProjectMember.DoesNotExist:
        return None


def get_accessible_projects(user: User) -> QuerySet:
    """
    Get all projects that a user can access (as owner or member)
    
    Args:
        user: The user to get projects for
        
    Returns:
        QuerySet of accessible projects
    """
    if not user.is_authenticated:
        return Project.objects.none()
    
    if user.is_superuser:
        return Project.objects.all()
    
    # Get projects where user is owner or member
    return Project.objects.filter(
        Q(user=user) | Q(members=user)
    ).distinct()


def has_project_permission(user: User, project: Project, 
                          permission: str) -> bool:
    """
    Check if user has a specific permission for a project
    Uses the existing ProjectPermission class
    
    Args:
        user: The user to check
        project: The project
        permission: Permission string from ProjectPermission
        
    Returns:
        True if user has the permission
    """
    return ProjectPermission.has_permission(user, project, permission)


def require_project_permission(user: User, project: Project,
                              permission: str) -> None:
    """
    Require that user has a specific permission for a project
    
    Args:
        user: The user to check
        project: The project
        permission: Permission string from ProjectPermission
        
    Raises:
        PermissionDenied: If user doesn't have the permission
    """
    ProjectPermission.require_permission(user, project, permission)


def get_project_or_404(project_id: int, user: User = None,
                       check_access: bool = True) -> Project:
    """
    Get a project by ID and optionally check user access
    
    Args:
        project_id: The project ID
        user: The user to check access for (optional)
        check_access: Whether to check user access
        
    Returns:
        Project instance
        
    Raises:
        Http404: If project doesn't exist
        PermissionDenied: If check_access=True and user has no access
    """
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        raise Http404("Project not found")
    
    if check_access and user:
        check_project_access(user, project, raise_exception=True)
    
    return project