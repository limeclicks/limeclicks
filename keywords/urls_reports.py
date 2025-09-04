"""
URL patterns for keyword reports
"""

from django.urls import path
from . import views_reports

app_name = 'keyword_reports'

urlpatterns = [
    # Report management
    path('<int:project_id>/reports/', views_reports.report_list_view, name='report_list'),
    path('<int:project_id>/reports/create/', views_reports.create_report_view, name='create_report'),
    path('<int:project_id>/reports/<int:report_id>/', views_reports.report_detail_view, name='report_detail'),
    path('<int:project_id>/reports/<int:report_id>/download/', views_reports.download_report_view, name='download_report'),
    path('<int:project_id>/reports/<int:report_id>/delete/', views_reports.delete_report_view, name='delete_report'),
    
    # Schedule management
    path('<int:project_id>/schedules/', views_reports.schedule_list_view, name='schedule_list'),
    path('<int:project_id>/schedules/create/', views_reports.create_schedule_view, name='create_schedule'),
    path('<int:project_id>/schedules/<int:schedule_id>/toggle/', views_reports.toggle_schedule_view, name='toggle_schedule'),
    path('<int:project_id>/schedules/<int:schedule_id>/delete/', views_reports.delete_schedule_view, name='delete_schedule'),
]