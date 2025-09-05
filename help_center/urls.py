from django.urls import path
from . import views

app_name = 'help_center'

urlpatterns = [
    path('', views.help_center_view, name='index'),
]