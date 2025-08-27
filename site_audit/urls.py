from django.urls import path
from . import views

app_name = 'site_audit'

urlpatterns = [
    path('', views.site_audit_list, name='list'),
    path('<int:audit_id>/', views.site_audit_detail, name='detail'),
    path('<int:audit_id>/issues/', views.site_audit_issues, name='issues'),
    path('<int:audit_id>/issues/load-more/', views.load_more_issues, name='load_more_issues'),
    path('<int:audit_id>/run/', views.run_manual_audit, name='run_manual'),
    path('<int:audit_id>/status-stream/', views.audit_status_stream, name='status_stream'),
    path('create/', views.create_site_audit, name='create'),
]