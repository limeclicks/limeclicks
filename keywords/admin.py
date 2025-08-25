from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Keyword, Rank


@admin.register(Keyword)
class KeywordAdmin(ModelAdmin):
    list_display = ['keyword', 'project', 'country', 'rank', 'rank_status', 'processing', 'archive', 'created_at']
    list_filter = ['rank_status', 'country', 'processing', 'archive', 'impact', 'created_at']
    search_fields = ['keyword', 'project__domain', 'rank_url']
    readonly_fields = ['created_at', 'updated_at', 'scraped_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('project', 'keyword', 'country')
        }),
        ('Ranking Data', {
            'fields': ('rank', 'rank_status', 'rank_diff_from_last_time', 'rank_url', 
                      'on_map', 'initial_rank', 'highest_rank', 'number_of_results')
        }),
        ('Scraping Information', {
            'fields': ('scraped_at', 'scrape_do_at', 'scrape_do_files', 'error',
                      'success_api_hit_count', 'failed_api_hit_count')
        }),
        ('Management', {
            'fields': ('impact', 'tags', 'processing', 'archive')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('project')


@admin.register(Rank)
class RankAdmin(ModelAdmin):
    list_display = ['get_keyword', 'rank', 'is_organic', 'has_map_result', 
                   'has_video_result', 'has_image_result', 'created_at']
    list_filter = ['is_organic', 'has_map_result', 'has_video_result', 
                  'has_image_result', 'created_at']
    search_fields = ['keyword__keyword', 'keyword__project__domain']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Keyword', {
            'fields': ('keyword',)
        }),
        ('Ranking Information', {
            'fields': ('rank', 'is_organic', 'number_of_results')
        }),
        ('Special Results', {
            'fields': ('has_map_result', 'has_video_result', 'has_image_result')
        }),
        ('Files', {
            'fields': ('search_results_file',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
    
    def get_keyword(self, obj):
        return f"{obj.keyword.keyword} - {obj.keyword.project.domain}"
    get_keyword.short_description = 'Keyword'
    get_keyword.admin_order_field = 'keyword__keyword'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('keyword', 'keyword__project')
