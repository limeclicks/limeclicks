from django.urls import path
from . import views, team_views
from .favicon_utils import favicon_proxy

app_name = 'project'

urlpatterns = [
    path('', views.project_list, name='project_list'),
    path('create/', views.project_create, name='create'),
    path('<int:project_id>/delete/', views.project_delete, name='delete'),
    path('<int:project_id>/toggle-active/', views.project_toggle_active, name='toggle_active'),
    path('favicon/<str:domain>/', favicon_proxy, name='favicon_proxy'),
    
    # Team management routes
    path('team/', team_views.team_projects_list, name='team_projects_list'),
    path('<int:project_id>/team/', team_views.team_management, name='team_management'),
    path('<int:project_id>/team/invite/', team_views.invite_users, name='invite_users'),
    path('<int:project_id>/team/member/<int:member_id>/remove/', team_views.remove_member, name='remove_member'),
    path('<int:project_id>/team/invitation/<int:invitation_id>/resend/', team_views.resend_invitation, name='resend_invitation'),
    path('<int:project_id>/team/invitation/<int:invitation_id>/revoke/', team_views.revoke_invitation, name='revoke_invitation'),
    path('invitation/<uuid:token>/accept/', team_views.accept_invitation, name='accept_invitation'),
]