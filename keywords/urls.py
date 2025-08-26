from django.urls import path
from . import views

app_name = 'keywords'

urlpatterns = [
    # Tag views
    path('tags/', views.user_tags, name='user_tags'),
    path('tags/<slug:tag_slug>/', views.keywords_by_tag, name='keywords_by_tag'),
    
    # API endpoints
    path('api/tags/', views.api_user_tags, name='api_user_tags'),
    path('api/tags/create/', views.api_create_tag, name='api_create_tag'),
    path('api/tags/keyword/', views.api_tag_keyword, name='api_tag_keyword'),
    path('api/tags/keyword/<int:keyword_id>/<int:tag_id>/', views.api_untag_keyword, name='api_untag_keyword'),
    
    # Crawl management endpoints
    path('api/keyword/<int:keyword_id>/force-crawl/', views.api_force_crawl, name='api_force_crawl'),
    path('api/keyword/<int:keyword_id>/crawl-status/', views.api_crawl_status, name='api_crawl_status'),
    path('api/crawl-queue/', views.api_crawl_queue, name='api_crawl_queue'),
]