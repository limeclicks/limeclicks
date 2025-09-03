from django.urls import path
from . import views

app_name = 'competitors'

urlpatterns = [
    path('keywords/', views.CompetitorKeywordsView.as_view(), name='keywords'),
    path('keywords/data/', views.CompetitorKeywordsDataView.as_view(), name='keywords_data'),
    path('target/', views.TargetView.as_view(), name='target'),
    path('target/add/<int:project_id>/', views.add_target, name='add_target'),
    path('target/remove/<int:target_id>/', views.remove_target, name='remove_target'),
    path('target/comparison/<int:project_id>/', views.TargetComparisonView.as_view(), name='target_comparison'),
]