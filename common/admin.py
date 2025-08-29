from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse


class AuditHistoryAdminMixin:
    """Mixin for admin classes that display audit history records"""
    
    def status_badge(self, obj):
        """Display a colored badge based on status"""
        colors = {
            'pending': '#ffa500',
            'running': '#007bff',
            'completed': '#28a745',
            'failed': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 0.9em;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def duration_display(self, obj):
        """Display the duration of the audit"""
        duration = obj.duration
        if duration:
            if duration < 60:
                return f"{duration:.1f}s"
            elif duration < 3600:
                return f"{duration/60:.1f}m"
            else:
                return f"{duration/3600:.1f}h"
        return '-'
    duration_display.short_description = 'Duration'
    
    def id_short(self, obj):
        """Display shortened UUID"""
        return str(obj.id)[:8]
    id_short.short_description = 'ID'
    
    def error_truncated(self, obj):
        """Display truncated error message"""
        if obj.error_message:
            return obj.error_message[:100] + ('...' if len(obj.error_message) > 100 else '')
        return '-'
    error_truncated.short_description = 'Error'
    
    def retry_badge(self, obj):
        """Display retry count as a badge"""
        if obj.retry_count > 0:
            color = '#dc3545' if obj.retry_count >= 3 else '#ffa500'
            return format_html(
                '<span style="background-color: {}; color: white; padding: 2px 8px; '
                'border-radius: 3px; font-size: 0.85em;">{}</span>',
                color, obj.retry_count
            )
        return '-'
    retry_badge.short_description = 'Retries'


class ReadOnlyAdminMixin:
    """Mixin to make admin interface read-only"""
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


class BulkActionsMixin:
    """Mixin for common bulk actions"""
    
    def mark_as_pending(self, request, queryset):
        updated = queryset.update(status='pending')
        self.message_user(request, f'{updated} items marked as pending.')
    mark_as_pending.short_description = 'Mark selected as pending'
    
    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, f'{updated} items marked as completed.')
    mark_as_completed.short_description = 'Mark selected as completed'
    
    def retry_failed(self, request, queryset):
        failed_items = queryset.filter(status='failed')
        for item in failed_items:
            item.status = 'pending'
            item.retry_count = 0
            item.error_message = None
            item.save()
        self.message_user(request, f'{failed_items.count()} failed items queued for retry.')
    retry_failed.short_description = 'Retry failed items'


class OptimizedQuerysetMixin:
    """Mixin to optimize database queries in admin"""
    
    def get_queryset(self, request):
        """Override to add select_related and prefetch_related"""
        qs = super().get_queryset(request)
        
        # Automatically detect and optimize foreign key relationships
        model = qs.model
        select_related_fields = []
        prefetch_related_fields = []
        
        for field in model._meta.get_fields():
            if field.many_to_one or field.one_to_one:
                # Foreign key or OneToOne field
                select_related_fields.append(field.name)
            elif field.many_to_many or field.one_to_many:
                # ManyToMany or reverse foreign key
                prefetch_related_fields.append(field.name)
        
        if select_related_fields:
            qs = qs.select_related(*select_related_fields)
        if prefetch_related_fields:
            qs = qs.prefetch_related(*prefetch_related_fields)
        
        return qs


class TimestampedAdminMixin:
    """Mixin for models with created_at and updated_at fields"""
    
    def created_date(self, obj):
        """Format created_at date"""
        if obj.created_at:
            return obj.created_at.strftime('%Y-%m-%d %H:%M')
        return '-'
    created_date.short_description = 'Created'
    created_date.admin_order_field = 'created_at'
    
    def updated_date(self, obj):
        """Format updated_at date"""
        if obj.updated_at:
            return obj.updated_at.strftime('%Y-%m-%d %H:%M')
        return '-'
    updated_date.short_description = 'Updated'
    updated_date.admin_order_field = 'updated_at'
    
    def time_since_created(self, obj):
        """Show time elapsed since creation"""
        if obj.created_at:
            delta = timezone.now() - obj.created_at
            days = delta.days
            if days == 0:
                hours = delta.seconds // 3600
                if hours == 0:
                    minutes = delta.seconds // 60
                    return f"{minutes}m ago"
                return f"{hours}h ago"
            elif days == 1:
                return "Yesterday"
            elif days < 7:
                return f"{days}d ago"
            elif days < 30:
                weeks = days // 7
                return f"{weeks}w ago"
            else:
                months = days // 30
                return f"{months}mo ago"
        return '-'
    time_since_created.short_description = 'Age'


class LinksMixin:
    """Mixin to add common link helpers"""
    
    def admin_link(self, obj, model_name=None, app_label=None):
        """Create a link to another admin page"""
        if not obj:
            return '-'
        
        if not model_name:
            model_name = obj.__class__.__name__.lower()
        if not app_label:
            app_label = obj.__class__._meta.app_label
        
        url = reverse(f'admin:{app_label}_{model_name}_change', args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, str(obj))
    
    def external_link(self, url, text=None, new_window=True):
        """Create an external link"""
        if not url:
            return '-'
        
        if not text:
            text = url
        
        target = ' target="_blank"' if new_window else ''
        return format_html('<a href="{}"{}>{}</a>', url, target, text)