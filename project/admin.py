from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import RangeNumericFilter, RangeDateFilter
from unfold.decorators import display
from .models import Project


@admin.register(Project)
class ProjectAdmin(ModelAdmin):
    list_display = (
        'domain_with_favicon', 
        'title', 
        'user', 
        'active_status', 
        'dataforseo_status',
        'audit_count',
        'latest_audit_status',
        'created_at'
    )
    list_filter = (
        'active', 
        ('created_at', RangeDateFilter),
        'user'
    )
    search_fields = ('domain', 'title', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at', 'audit_summary', 
                       'dataforseo_task_id', 'dataforseo_keywords_path', 'dataforseo_keywords_updated_at')
    ordering = ('-created_at',)
    list_per_page = 20
    list_select_related = ('user',)
    
    fieldsets = (
        ('Project Information', {
            'fields': ('user', 'domain', 'title', 'active'),
            'description': 'Basic project details and ownership'
        }),
        ('DataForSEO Keywords', {
            'fields': ('dataforseo_task_id', 'dataforseo_keywords_path', 'dataforseo_keywords_updated_at'),
            'classes': ('collapse',),
            'description': 'DataForSEO keyword research data and task reference'
        }),
        ('Audit Summary', {
            'fields': ('audit_summary',),
            'classes': ('collapse',),
            'description': 'Overview of site audits for this project'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_projects', 'deactivate_projects', 'trigger_audits']
    
    @display(description="Domain", ordering="domain")
    def domain_with_favicon(self, obj):
        """Display domain with favicon"""
        favicon_url = obj.get_cached_favicon_url(size=32)
        return format_html(
            '<div style="display: flex; align-items: center; gap: 8px;">'
            '<img src="{}" alt="Favicon" style="width: 16px; height: 16px; border-radius: 2px;"/>'
            '<strong>{}</strong>'
            '</div>',
            favicon_url,
            obj.domain
        )
    
    @display(description="Status", ordering="active")
    def active_status(self, obj):
        """Display active status with colored badge"""
        if obj.active:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 500;">Active</span>'
            )
        else:
            return format_html(
                '<span style="background: #ef4444; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 500;">Inactive</span>'
            )
    
    @display(description="Keywords", ordering="dataforseo_keywords_path")
    def dataforseo_status(self, obj):
        """Display DataForSEO keywords status"""
        if obj.dataforseo_keywords_path:
            # Calculate how old the data is
            if obj.dataforseo_keywords_updated_at:
                from django.utils import timezone
                days_old = (timezone.now() - obj.dataforseo_keywords_updated_at).days
                if days_old == 0:
                    age_text = "Today"
                elif days_old == 1:
                    age_text = "1 day ago"
                else:
                    age_text = f"{days_old} days ago"
                    
                return format_html(
                    '<span style="background: #10b981; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 500;" title="Updated: {}">✓ {}</span>',
                    age_text,
                    age_text
                )
            else:
                return format_html(
                    '<span style="background: #10b981; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 500;">✓ Available</span>'
                )
        elif obj.dataforseo_task_id and not obj.dataforseo_keywords_path:
            return format_html(
                '<span style="background: #f59e0b; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 500;">⏳ Processing</span>'
            )
        else:
            return format_html('<span style="color: #9ca3af; font-size: 11px;">—</span>')
    
    @display(description="Audits")
    def audit_count(self, obj):
        """Display count of site audits"""
        count = obj.site_audits.count()
        if count > 0:
            url = reverse('admin:site_audit_siteaudit_changelist') + f'?project__id__exact={obj.id}'
            return format_html('<a href="{}" style="color: #3b82f6; text-decoration: none;">{} audits</a>', url, count)
        return '0 audits'
    
    @display(description="Latest Audit")
    def latest_audit_status(self, obj):
        """Display latest audit status"""
        latest_audit = obj.site_audits.order_by('-created_at').first()
        if latest_audit:
            status_colors = {
                'completed': '#10b981',
                'running': '#f59e0b', 
                'pending': '#6b7280',
                'failed': '#ef4444'
            }
            color = status_colors.get(latest_audit.status, '#6b7280')
            return format_html(
                '<span style="background: {}; color: white; padding: 2px 6px; border-radius: 8px; font-size: 10px;">{}</span>',
                color,
                latest_audit.status.upper()
            )
        return format_html('<span style="color: #9ca3af;">No audits</span>')
    
    @display(description="Audit Summary")
    def audit_summary(self, obj):
        """Display comprehensive audit summary"""
        audits = obj.site_audits.order_by('-created_at')[:5]
        if not audits:
            return format_html('<p style="color: #9ca3af; font-style: italic;">No audits performed yet.</p>')
        
        html = ['<div style="font-family: monospace;">']
        
        for audit in audits:
            status_icon = {
                'completed': '✅',
                'running': '🔄', 
                'pending': '⏳',
                'failed': '❌'
            }.get(audit.status, '❓')
            
            audit_url = reverse('admin:site_audit_siteaudit_change', args=[audit.id])
            date_str = audit.created_at.strftime('%Y-%m-%d %H:%M')
            
            html.append(f'''
                <div style="border: 1px solid #e5e7eb; border-radius: 4px; padding: 8px; margin: 4px 0; background: #f9fafb;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <a href="{audit_url}" style="text-decoration: none; color: #3b82f6; font-weight: 500;">
                            {status_icon} Audit #{audit.id}
                        </a>
                        <span style="color: #6b7280; font-size: 12px;">{date_str}</span>
                    </div>
                    <div style="margin-top: 4px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; font-size: 12px;">
                        <div>Pages: <strong>{audit.total_pages_crawled}</strong></div>
                        <div>Issues: <strong>{audit.get_total_issues_count()}</strong></div>
                        <div>Score: <strong>{f"{audit.overall_site_health_score:.1f}" if audit.overall_site_health_score is not None else "N/A"}</strong></div>
                    </div>
                </div>
            ''')
        
        html.append('</div>')
        return format_html(''.join(html))
    
    def activate_projects(self, request, queryset):
        """Activate selected projects"""
        count = queryset.update(active=True)
        self.message_user(request, f'{count} projects activated successfully.')
    activate_projects.short_description = "Activate selected projects"
    
    def deactivate_projects(self, request, queryset):
        """Deactivate selected projects"""
        count = queryset.update(active=False)
        self.message_user(request, f'{count} projects deactivated successfully.')
    deactivate_projects.short_description = "Deactivate selected projects"
    
    def trigger_audits(self, request, queryset):
        """Trigger manual audits for selected projects"""
        from site_audit.tasks import trigger_manual_site_audit
        
        triggered_count = 0
        for project in queryset:
            if project.active:
                try:
                    trigger_manual_site_audit.apply_async(args=[project.id])
                    triggered_count += 1
                except Exception as e:
                    self.message_user(request, f'Failed to trigger audit for {project.domain}: {e}', level='ERROR')
        
        if triggered_count > 0:
            self.message_user(request, f'{triggered_count} audit(s) triggered successfully.')
        else:
            self.message_user(request, 'No audits were triggered.', level='WARNING')
    trigger_audits.short_description = "Trigger manual audits for selected projects"