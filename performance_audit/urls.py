from django.urls import path
from . import views

app_name = 'performance_audit'

urlpatterns = [
    path('project/<int:project_id>/performance_audit/', views.audit_dashboard, name='dashboard'),
    path('project/<int:project_id>/performance_audit/trigger/', views.trigger_manual_audit, name='trigger_manual'),
]