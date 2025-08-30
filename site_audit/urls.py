"""
URL patterns for site audit app
"""
from django.urls import path
from . import views

app_name = 'site_audit'

urlpatterns = [
    path('', views.site_audit_list, name='list'),
    path('trigger/<int:project_id>/', views.trigger_audit, name='trigger_audit'),
    path('status-stream/', views.audit_status_stream, name='status_stream'),
    path('card/<int:project_id>/', views.get_audit_card, name='get_card'),
    path('<int:audit_id>/', views.audit_detail, name='detail'),
]