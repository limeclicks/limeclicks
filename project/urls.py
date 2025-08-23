from django.urls import path
from . import views
from .favicon_utils import favicon_proxy

app_name = 'project'

urlpatterns = [
    path('', views.project_list, name='list'),
    path('create/', views.project_create, name='create'),
    path('<int:project_id>/delete/', views.project_delete, name='delete'),
    path('<int:project_id>/toggle-active/', views.project_toggle_active, name='toggle_active'),
    path('favicon/<str:domain>/', favicon_proxy, name='favicon_proxy'),
]