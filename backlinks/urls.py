from django.urls import path
from . import views

app_name = 'backlinks'

urlpatterns = [
    # Main backlinks listing page
    path('', views.backlinks_list, name='list'),
    
    # HTMX endpoints
    path('htmx/projects/', views.htmx_backlinks_projects, name='htmx_projects'),
    path('htmx/stats/', views.htmx_backlinks_stats, name='htmx_stats'),
    
    # Project specific backlinks detail
    path('project/<int:project_id>/', views.backlinks_detail, name='detail'),
    
    # Actions
    path('project/<int:project_id>/fetch/', views.fetch_backlinks, name='fetch'),
    path('project/<int:project_id>/fetch-detailed/', views.fetch_detailed_backlinks, name='fetch_detailed'),
]