from django.urls import path
from . import views

app_name = 'site_audit'

urlpatterns = [
    path('', views.site_audit_list, name='list'),
    path('<int:audit_id>/', views.site_audit_detail, name='detail'),
    path('<int:audit_id>/issues/', views.site_audit_issues, name='issues'),
    path('<int:audit_id>/run/', views.run_manual_audit, name='run_manual'),
    path('create/', views.create_site_audit, name='create'),
]