from django.urls import path
from . import views

app_name = 'audits'

urlpatterns = [
    path('project/<int:project_id>/audits/', views.audit_dashboard, name='dashboard'),
    path('project/<int:project_id>/audits/trigger/', views.trigger_manual_audit, name='trigger_manual'),
]