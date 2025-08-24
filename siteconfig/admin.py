from django.contrib import admin
from .models import SiteConfiguration


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    list_display = ['key', 'value_display', 'value_type', 'is_sensitive', 'updated_at']
    list_filter = ['value_type', 'is_sensitive', 'created_at', 'updated_at']
    search_fields = ['key', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('key', 'value', 'value_type')
        }),
        ('Additional Information', {
            'fields': ('description', 'is_sensitive')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def value_display(self, obj):
        """Display truncated value for list view"""
        if obj.is_sensitive:
            return "[HIDDEN]"
        if len(obj.value) > 50:
            return f"{obj.value[:50]}..."
        return obj.value
    value_display.short_description = 'Value'
    
    def get_form(self, request, obj=None, **kwargs):
        """Customize form to show/hide sensitive values"""
        form = super().get_form(request, obj, **kwargs)
        if obj and obj.is_sensitive:
            form.base_fields['value'].widget.attrs['placeholder'] = 'Sensitive value - hidden for security'
        return form
    
    actions = ['clear_cache']
    
    def clear_cache(self, request, queryset):
        """Admin action to clear cache for selected configurations"""
        from django.core.cache import cache
        count = 0
        for config in queryset:
            cache_key = f'siteconfig_{config.key}'
            cache.delete(cache_key)
            count += 1
        self.message_user(request, f'Cache cleared for {count} configuration(s)')
    clear_cache.short_description = "Clear cache for selected configurations"
