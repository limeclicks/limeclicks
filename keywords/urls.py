from django.urls import path, include
from . import views
from . import views_reports_list

app_name = 'keywords'

urlpatterns = [
    # Main list view
    path('', views.keywords_list, name='list'),
    
    # Reports main view
    path('reports/', views_reports_list.reports_main_list, name='reports_main'),
    path('project/<int:project_id>/', views.project_keywords, name='project_keywords'),
    path('keyword/<int:keyword_id>/', views.keyword_detail, name='keyword_detail'),
    path('add-modal/', views.add_keyword_modal, name='add_keyword_modal'),
    path('add/', views.add_keywords, name='add_keywords'),
    
    # Tag views
    path('tags/', views.user_tags, name='user_tags'),
    path('tags/<slug:tag_slug>/', views.keywords_by_tag, name='keywords_by_tag'),
    
    # API endpoints
    path('api/tags/', views.api_tags, name='api_tags'),  # Simple tags list for autocomplete
    path('api/user-tags/', views.api_user_tags, name='api_user_tags'),  # Full tags data
    path('api/tags/create/', views.api_create_tag, name='api_create_tag'),
    path('api/tags/keyword/', views.api_tag_keyword, name='api_tag_keyword'),
    path('api/tags/keyword/<int:keyword_id>/<int:tag_id>/', views.api_untag_keyword, name='api_untag_keyword'),
    
    # Crawl management endpoints
    path('api/keyword/<int:keyword_id>/force-crawl/', views.api_force_crawl, name='api_force_crawl'),
    path('api/keyword/<int:keyword_id>/status/', views.api_keyword_status, name='api_keyword_status'),
    path('api/keyword/<int:keyword_id>/crawl-status/', views.api_crawl_status, name='api_crawl_status'),
    path('api/keyword/<int:keyword_id>/delete/', views.api_delete_keyword, name='api_delete_keyword'),
    path('api/crawl-queue/', views.api_crawl_queue, name='api_crawl_queue'),
    path('api/project/<int:project_id>/updates-sse/', views.keyword_updates_sse, name='keyword_updates_sse'),
    
    # Historical SERP data
    path('api/rank/<int:rank_id>/serp/', views.api_rank_serp, name='api_rank_serp'),
    
    # Project-specific Reports URLs
    path('project/', include('keywords.urls_reports')),
]