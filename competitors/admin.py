from django.contrib import admin
from .models import Target, TargetKeywordRank


@admin.register(Target)
class TargetAdmin(admin.ModelAdmin):
    list_display = ['domain', 'name', 'project', 'created_by', 'created_at']
    list_filter = ['created_at', 'project']
    search_fields = ['domain', 'name', 'project__domain']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['project', 'created_by']


@admin.register(TargetKeywordRank)
class TargetKeywordRankAdmin(admin.ModelAdmin):
    list_display = ['target', 'keyword', 'rank', 'scraped_at']
    list_filter = ['scraped_at', 'rank']
    search_fields = ['target__domain', 'keyword__keyword']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['target', 'keyword']