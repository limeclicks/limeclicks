from django.core.exceptions import PermissionDenied
from .models import ProjectMember, ProjectRole


class ProjectPermission:
    VIEW_PROJECT = 'view_project'
    EDIT_PROJECT_SETTINGS = 'edit_project_settings'
    MANAGE_KEYWORDS = 'manage_keywords'
    MANAGE_TEAM = 'manage_team'
    DELETE_PROJECT = 'delete_project'
    
    ROLE_PERMISSIONS = {
        ProjectRole.OWNER: [
            VIEW_PROJECT,
            EDIT_PROJECT_SETTINGS,
            MANAGE_KEYWORDS,
            MANAGE_TEAM,
            DELETE_PROJECT,
        ],
        ProjectRole.MEMBER: [
            VIEW_PROJECT,
            MANAGE_KEYWORDS,
            # Can view site audit and other project features
            # Cannot edit project settings, manage team, or delete project
        ],
    }
    
    @classmethod
    def get_user_role(cls, user, project):
        if project.user == user:
            return ProjectRole.OWNER
        
        try:
            membership = ProjectMember.objects.get(project=project, user=user)
            return membership.role
        except ProjectMember.DoesNotExist:
            return None
    
    @classmethod
    def has_permission(cls, user, project, permission):
        if not user.is_authenticated:
            return False
        
        if user.is_superuser:
            return True
        
        role = cls.get_user_role(user, project)
        if not role:
            return False
        
        return permission in cls.ROLE_PERMISSIONS.get(role, [])
    
    @classmethod
    def require_permission(cls, user, project, permission):
        if not cls.has_permission(user, project, permission):
            raise PermissionDenied(f"User does not have {permission} permission for this project")


def user_can_view_project(user, project):
    return ProjectPermission.has_permission(user, project, ProjectPermission.VIEW_PROJECT)


def user_can_edit_project(user, project):
    return ProjectPermission.has_permission(user, project, ProjectPermission.EDIT_PROJECT_SETTINGS)


def user_can_manage_keywords(user, project):
    return ProjectPermission.has_permission(user, project, ProjectPermission.MANAGE_KEYWORDS)


def user_can_manage_team(user, project):
    return ProjectPermission.has_permission(user, project, ProjectPermission.MANAGE_TEAM)


def user_can_delete_project(user, project):
    return ProjectPermission.has_permission(user, project, ProjectPermission.DELETE_PROJECT)