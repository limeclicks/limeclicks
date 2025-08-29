from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Project


@admin.register(Project)
class ProjectAdmin(ModelAdmin):
    list_display = ('domain', 'title', 'user', 'active', 'created_at')
    list_filter = ('active', 'created_at')
    search_fields = ('domain', 'title', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Project Information', {
            'fields': ('user', 'domain', 'title', 'active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )