"""
Permission decorators for views
Provides easy-to-use decorators for common permission checks
"""

from functools import wraps
from typing import Callable, Optional

from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from project.models import Project
from project.permissions import ProjectPermission
from .utils import check_project_access, check_project_owner


def require_project_access(view_func: Callable = None, 
                          project_id_param: str = 'project_id',
                          redirect_url: Optional[str] = None) -> Callable:
    """
    Decorator that ensures user has access to the project (owner or member)
    
    Args:
        view_func: The view function to wrap
        project_id_param: Name of the parameter containing project ID
        redirect_url: URL to redirect to if access denied (None = raise error)
        
    Usage:
        @require_project_access
        def my_view(request, project_id):
            ...
            
        @require_project_access(project_id_param='pk')
        def my_view(request, pk):
            ...
    """
    def decorator(func):
        @wraps(func)
        @login_required
        def wrapper(request, *args, **kwargs):
            # Get project ID from kwargs or args
            project_id = kwargs.get(project_id_param)
            if project_id is None and args:
                # Try to get from positional args (assumes first arg after request)
                project_id = args[0] if len(args) > 0 else None
            
            if project_id is None:
                raise ValueError(f"No project ID found in parameter '{project_id_param}'")
            
            # Get the project
            try:
                project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                raise Http404("Project not found")
            
            # Check access
            try:
                check_project_access(request.user, project, raise_exception=True)
            except PermissionDenied as e:
                if redirect_url:
                    messages.error(request, str(e))
                    return redirect(redirect_url)
                raise
            
            # Add project to kwargs for convenience
            kwargs['project'] = project
            
            return func(request, *args, **kwargs)
        
        return wrapper
    
    # Handle both @decorator and @decorator() syntax
    if view_func is not None:
        return decorator(view_func)
    return decorator


def require_project_owner(view_func: Callable = None,
                         project_id_param: str = 'project_id',
                         redirect_url: Optional[str] = None) -> Callable:
    """
    Decorator that ensures user is the project owner
    
    Args:
        view_func: The view function to wrap
        project_id_param: Name of the parameter containing project ID
        redirect_url: URL to redirect to if not owner (None = raise error)
        
    Usage:
        @require_project_owner
        def my_view(request, project_id):
            ...
    """
    def decorator(func):
        @wraps(func)
        @login_required
        def wrapper(request, *args, **kwargs):
            # Get project ID
            project_id = kwargs.get(project_id_param)
            if project_id is None and args:
                project_id = args[0] if len(args) > 0 else None
            
            if project_id is None:
                raise ValueError(f"No project ID found in parameter '{project_id_param}'")
            
            # Get the project
            try:
                project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                raise Http404("Project not found")
            
            # Check ownership
            try:
                check_project_owner(request.user, project, raise_exception=True)
            except PermissionDenied as e:
                if redirect_url:
                    messages.error(request, str(e))
                    return redirect(redirect_url)
                raise
            
            # Add project to kwargs
            kwargs['project'] = project
            
            return func(request, *args, **kwargs)
        
        return wrapper
    
    if view_func is not None:
        return decorator(view_func)
    return decorator


def require_project_member(view_func: Callable = None,
                          project_id_param: str = 'project_id',
                          allow_owner: bool = True,
                          redirect_url: Optional[str] = None) -> Callable:
    """
    Decorator that ensures user is a project member (and optionally owner)
    
    Args:
        view_func: The view function to wrap
        project_id_param: Name of the parameter containing project ID
        allow_owner: Whether to also allow project owner (default: True)
        redirect_url: URL to redirect to if not member (None = raise error)
        
    Usage:
        @require_project_member
        def my_view(request, project_id):
            ...
    """
    def decorator(func):
        @wraps(func)
        @login_required
        def wrapper(request, *args, **kwargs):
            # Get project ID
            project_id = kwargs.get(project_id_param)
            if project_id is None and args:
                project_id = args[0] if len(args) > 0 else None
            
            if project_id is None:
                raise ValueError(f"No project ID found in parameter '{project_id_param}'")
            
            # Get the project
            try:
                project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                raise Http404("Project not found")
            
            # Check membership
            is_owner = project.user == request.user
            is_member = project.members.filter(id=request.user.id).exists()
            
            if not ((allow_owner and is_owner) or is_member):
                error_msg = "You must be a project member to access this"
                if redirect_url:
                    messages.error(request, error_msg)
                    return redirect(redirect_url)
                raise PermissionDenied(error_msg)
            
            # Add project to kwargs
            kwargs['project'] = project
            
            return func(request, *args, **kwargs)
        
        return wrapper
    
    if view_func is not None:
        return decorator(view_func)
    return decorator


def project_permission_required(permission: str,
                               project_id_param: str = 'project_id',
                               redirect_url: Optional[str] = None) -> Callable:
    """
    Decorator that checks for a specific project permission
    
    Args:
        permission: Permission string from ProjectPermission class
        project_id_param: Name of the parameter containing project ID
        redirect_url: URL to redirect to if permission denied
        
    Usage:
        @project_permission_required(ProjectPermission.MANAGE_KEYWORDS)
        def my_view(request, project_id):
            ...
    """
    def decorator(func):
        @wraps(func)
        @login_required
        def wrapper(request, *args, **kwargs):
            # Get project ID
            project_id = kwargs.get(project_id_param)
            if project_id is None and args:
                project_id = args[0] if len(args) > 0 else None
            
            if project_id is None:
                raise ValueError(f"No project ID found in parameter '{project_id_param}'")
            
            # Get the project
            try:
                project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                raise Http404("Project not found")
            
            # Check permission
            if not ProjectPermission.has_permission(request.user, project, permission):
                error_msg = f"You don't have permission to {permission.replace('_', ' ')}"
                if redirect_url:
                    messages.error(request, error_msg)
                    return redirect(redirect_url)
                raise PermissionDenied(error_msg)
            
            # Add project to kwargs
            kwargs['project'] = project
            
            return func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator