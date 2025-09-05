"""
Unified Permission System for LimeClicks
Centralizes all permission checks and provides decorators for views
"""

from .decorators import (
    require_project_access,
    require_project_owner,
    require_project_member,
    project_permission_required,
)

from .mixins import (
    ProjectAccessMixin,
    ProjectOwnerMixin,
    ProjectMemberMixin,
)

from .utils import (
    check_project_access,
    check_project_owner,
    get_user_project_role,
    get_accessible_projects,
)

__all__ = [
    # Decorators
    'require_project_access',
    'require_project_owner',
    'require_project_member',
    'project_permission_required',
    
    # Mixins
    'ProjectAccessMixin',
    'ProjectOwnerMixin',
    'ProjectMemberMixin',
    
    # Utils
    'check_project_access',
    'check_project_owner',
    'get_user_project_role',
    'get_accessible_projects',
]