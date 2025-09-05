"""
Permission mixins for class-based views
Provides mixins for common permission checks
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404

from project.models import Project
from project.permissions import ProjectPermission
from .utils import check_project_access, check_project_owner


class ProjectAccessMixin(LoginRequiredMixin):
    """
    Mixin that ensures user has access to the project (owner or member)
    
    Usage:
        class MyView(ProjectAccessMixin, View):
            project_id_param = 'project_id'  # Optional, defaults to 'project_id'
            
            def get(self, request, project_id):
                # self.project is automatically available
                ...
    """
    
    project_id_param = 'project_id'
    project = None
    
    def dispatch(self, request, *args, **kwargs):
        # Get project ID
        project_id = kwargs.get(self.project_id_param)
        if not project_id:
            project_id = self.kwargs.get(self.project_id_param)
        
        if not project_id:
            raise Http404("Project not found")
        
        # Get and check project
        self.project = get_object_or_404(Project, id=project_id)
        
        # Check access
        if not check_project_access(request.user, self.project, raise_exception=False):
            raise PermissionDenied("You don't have access to this project")
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """Add project to context automatically"""
        context = super().get_context_data(**kwargs)
        context['project'] = self.project
        return context


class ProjectOwnerMixin(LoginRequiredMixin):
    """
    Mixin that ensures user is the project owner
    
    Usage:
        class MyView(ProjectOwnerMixin, View):
            def get(self, request, project_id):
                # Only owners can access this view
                ...
    """
    
    project_id_param = 'project_id'
    project = None
    
    def dispatch(self, request, *args, **kwargs):
        # Get project ID
        project_id = kwargs.get(self.project_id_param)
        if not project_id:
            project_id = self.kwargs.get(self.project_id_param)
        
        if not project_id:
            raise Http404("Project not found")
        
        # Get and check project
        self.project = get_object_or_404(Project, id=project_id)
        
        # Check ownership
        if not check_project_owner(request.user, self.project, raise_exception=False):
            raise PermissionDenied("Only project owner can perform this action")
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """Add project to context automatically"""
        context = super().get_context_data(**kwargs)
        context['project'] = self.project
        return context


class ProjectMemberMixin(LoginRequiredMixin):
    """
    Mixin that ensures user is a project member
    
    Usage:
        class MyView(ProjectMemberMixin, View):
            allow_owner = True  # Optional, defaults to True
            
            def get(self, request, project_id):
                # Members (and optionally owners) can access
                ...
    """
    
    project_id_param = 'project_id'
    allow_owner = True
    project = None
    
    def dispatch(self, request, *args, **kwargs):
        # Get project ID
        project_id = kwargs.get(self.project_id_param)
        if not project_id:
            project_id = self.kwargs.get(self.project_id_param)
        
        if not project_id:
            raise Http404("Project not found")
        
        # Get and check project
        self.project = get_object_or_404(Project, id=project_id)
        
        # Check membership
        is_owner = self.project.user == request.user
        is_member = self.project.members.filter(id=request.user.id).exists()
        
        if not ((self.allow_owner and is_owner) or is_member):
            raise PermissionDenied("You must be a project member to access this")
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """Add project to context automatically"""
        context = super().get_context_data(**kwargs)
        context['project'] = self.project
        return context


class ProjectPermissionMixin(LoginRequiredMixin):
    """
    Mixin that checks for specific project permissions
    
    Usage:
        class MyView(ProjectPermissionMixin, View):
            required_permission = ProjectPermission.MANAGE_KEYWORDS
            
            def get(self, request, project_id):
                # Only users with MANAGE_KEYWORDS permission can access
                ...
    """
    
    project_id_param = 'project_id'
    required_permission = None
    project = None
    
    def dispatch(self, request, *args, **kwargs):
        if not self.required_permission:
            raise ValueError("required_permission must be set")
        
        # Get project ID
        project_id = kwargs.get(self.project_id_param)
        if not project_id:
            project_id = self.kwargs.get(self.project_id_param)
        
        if not project_id:
            raise Http404("Project not found")
        
        # Get and check project
        self.project = get_object_or_404(Project, id=project_id)
        
        # Check permission
        if not ProjectPermission.has_permission(
            request.user, self.project, self.required_permission
        ):
            raise PermissionDenied(
                f"You don't have permission to {self.required_permission.replace('_', ' ')}"
            )
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """Add project to context automatically"""
        context = super().get_context_data(**kwargs)
        context['project'] = self.project
        return context