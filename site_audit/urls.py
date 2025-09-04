"""
URL patterns for site audit app
"""
from django.urls import path
from . import views
from . import views_reports

app_name = 'site_audit'

urlpatterns = [
    path('', views.site_audit_list, name='list'),
    path('add-project-modal/', views.add_project_modal, name='add_project_modal'),
    path('add-project/', views.add_project, name='add_project'),
    path('trigger/<int:project_id>/', views.trigger_audit, name='trigger_audit'),
    path('status-stream/', views.audit_status_stream, name='status_stream'),
    path('card/<int:project_id>/', views.get_audit_card, name='get_card'),
    
    # Reports management
    path('reports/', views_reports.site_audit_reports_list, name='reports_list'),
    path('reports/project/<int:project_id>/files/', views_reports.get_project_audit_files, name='project_audit_files'),
    path('reports/download/<int:file_id>/', views_reports.download_audit_file, name='download_file'),
    path('reports/project/<int:project_id>/download-all/', views_reports.download_all_audit_files, name='download_all'),
    
    path('<int:audit_id>/', views.audit_detail, name='detail'),
]