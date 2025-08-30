from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db import models
from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.filters.admin import RangeNumericFilter, RangeDateFilter, ChoicesDropdownFilter
from unfold.decorators import display
from unfold.widgets import UnfoldAdminTextareaWidget, UnfoldAdminSelectWidget
from .models import SiteAudit, SiteIssue
import json


class SiteIssueInline(TabularInline):
    """Inline for Site Issues"""
    model = SiteIssue
    extra = 0
    readonly_fields = ('url', 'issue_type', 'severity', 'issue_category', 'created_at')
    fields = ('url', 'issue_type', 'severity', 'issue_category', 'inlinks_count', 'created_at')
    ordering = ('severity', 'issue_type')
    show_change_link = True
    max_num = 10  # Limit inline display
    
    def has_add_permission(self, request, obj=None):
        return False  # Issues are created automatically


@admin.register(SiteAudit)
class SiteAuditAdmin(ModelAdmin):
    list_display = (
        'project_with_favicon',
        'status_display',
        'audit_score',
        'performance_scores',
        'pages_crawled_display',
        'issues_summary',
        'last_audit_date',
        'audit_actions'
    )
    
    list_filter = (
        'status',
        'is_audit_enabled',
        ('last_audit_date', RangeDateFilter),
        ('created_at', RangeDateFilter),
        ('total_pages_crawled', RangeNumericFilter),
        ('overall_site_health_score', RangeNumericFilter),
        'project__active'
    )
    
    search_fields = (
        'project__domain',
        'project__title',
        'project__user__email',
        'project__user__first_name',
        'project__user__last_name'
    )
    
    readonly_fields = (
        'created_at',
        'updated_at',
        'last_audit_date',
        'total_pages_crawled',
        'crawl_overview_display',
        'issues_overview_display',
        'performance_data_display',
        'audit_statistics'
    )
    
    ordering = ('-last_audit_date', '-created_at')
    list_per_page = 25
    list_select_related = ('project', 'project__user')
    
    fieldsets = (
        ('Audit Information', {
            'fields': (
                'project',
                'status',
                'last_audit_date',
                'is_audit_enabled',
                'temp_audit_dir'
            ),
            'description': 'Basic audit information and current status'
        }),
        ('Audit Settings', {
            'fields': (
                'audit_frequency_days',
                'manual_audit_frequency_days',
                'max_pages_to_crawl',
                'next_scheduled_audit'
            ),
            'classes': ('collapse',),
            'description': 'Audit frequency and scheduling settings'
        }),
        ('Performance Metrics', {
            'fields': (
                'performance_score_mobile',
                'performance_score_desktop',
                'overall_site_health_score',
                'average_page_size_kb',
                'average_load_time_ms'
            ),
            'classes': ('collapse',),
            'description': 'Performance scores and technical metrics'
        }),
        ('Crawl Data', {
            'fields': (
                'total_pages_crawled',
                'crawl_overview_display',
                'issues_overview_display'
            ),
            'classes': ('collapse',),
            'description': 'Detailed crawl results and issues found'
        }),
        ('PageSpeed Insights Data', {
            'fields': ('performance_data_display',),
            'classes': ('collapse',),
            'description': 'Detailed PageSpeed Insights performance data'
        }),
        ('Statistics', {
            'fields': ('audit_statistics',),
            'classes': ('collapse',),
            'description': 'Comprehensive audit statistics'
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'last_automatic_audit',
                'last_manual_audit'
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['trigger_manual_audit', 'enable_audits', 'disable_audits', 'recalculate_scores']
    inlines = [SiteIssueInline]
    
    # Custom widget overrides for better UI
    formfield_overrides = {
        models.TextField: {'widget': UnfoldAdminTextareaWidget},
        models.CharField: {'widget': UnfoldAdminSelectWidget},
    }
    
    @display(description="Project", ordering="project__domain")
    def project_with_favicon(self, obj):
        """Display project with favicon"""
        favicon_url = obj.project.get_cached_favicon_url(size=32)
        project_url = reverse('admin:project_project_change', args=[obj.project.id])
        return format_html(
            '<div style="display: flex; align-items: center; gap: 8px;">'
            '<img src="{}" alt="Favicon" style="width: 16px; height: 16px; border-radius: 2px;"/>'
            '<a href="{}" style="text-decoration: none; color: #3b82f6; font-weight: 500;">{}</a>'
            '</div>',
            favicon_url,
            project_url,
            obj.project.domain
        )
    
    @display(description="Status", ordering="status")
    def status_display(self, obj):
        """Display status with colored badge and icon"""
        status_config = {
            'completed': {'color': '#10b981', 'icon': '✅'},
            'running': {'color': '#f59e0b', 'icon': '🔄'},
            'pending': {'color': '#6b7280', 'icon': '⏳'},
            'failed': {'color': '#ef4444', 'icon': '❌'}
        }
        config = status_config.get(obj.status, {'color': '#6b7280', 'icon': '❓'})
        
        return format_html(
            '<div style="display: flex; align-items: center; gap: 6px;">'
            '<span>{}</span>'
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 500;">{}</span>'
            '</div>',
            config['icon'],
            config['color'],
            obj.status.upper()
        )
    
    @display(description="Health Score", ordering="overall_site_health_score")
    def audit_score(self, obj):
        """Display overall site health score with progress bar"""
        if obj.overall_site_health_score is None:
            return format_html('<span style="color: #9ca3af;">N/A</span>')
        
        score = obj.overall_site_health_score
        if score >= 80:
            color = '#10b981'  # Green
        elif score >= 60:
            color = '#f59e0b'  # Yellow
        else:
            color = '#ef4444'  # Red
        
        return format_html(
            '<div style="display: flex; align-items: center; gap: 8px; min-width: 120px;">'
            '<div style="width: 60px; height: 8px; background: #e5e7eb; border-radius: 4px; overflow: hidden;">'
            '<div style="width: {}%; height: 100%; background: {}; transition: width 0.3s;"></div>'
            '</div>'
            '<strong style="color: {}; font-size: 13px;">{}</strong>'
            '</div>',
            score,
            color,
            color,
            f'{score:.1f}'
        )
    
    @display(description="Performance", ordering="performance_score_mobile")
    def performance_scores(self, obj):
        """Display mobile and desktop performance scores"""
        mobile = obj.performance_score_mobile
        desktop = obj.performance_score_desktop
        
        def score_badge(score, label):
            if score is None:
                return f'<span style="color: #9ca3af; font-size: 11px;">{label}: N/A</span>'
            
            if score >= 90:
                color = '#10b981'
            elif score >= 50:
                color = '#f59e0b'
            else:
                color = '#ef4444'
            
            return f'<span style="background: {color}; color: white; padding: 1px 6px; border-radius: 8px; font-size: 11px; margin-right: 4px;">{label}: {score}</span>'
        
        return format_html(
            '<div style="display: flex; flex-direction: column; gap: 2px;">'
            '{}'
            '{}'
            '</div>',
            score_badge(mobile, '📱'),
            score_badge(desktop, '🖥️')
        )
    
    @display(description="Pages", ordering="total_pages_crawled")
    def pages_crawled_display(self, obj):
        """Display pages crawled with visual indicator"""
        if obj.total_pages_crawled == 0:
            return format_html('<span style="color: #9ca3af;">0 pages</span>')
        
        return format_html(
            '<div style="display: flex; align-items: center; gap: 4px;">'
            '<span style="color: #059669; font-size: 12px;">📄</span>'
            '<strong style="color: #059669;">{:,}</strong>'
            '</div>',
            obj.total_pages_crawled
        )
    
    @display(description="Issues", ordering="issues_overview")
    def issues_summary(self, obj):
        """Display issues summary with priority breakdown"""
        issues_breakdown = obj.get_issues_by_priority()
        total_issues = obj.get_total_issues_count()
        
        if total_issues == 0:
            return format_html('<span style="color: #10b981; font-weight: 500;">✅ No issues</span>')
        
        return format_html(
            '<div style="font-size: 11px;">'
            '<div style="margin-bottom: 2px;"><strong>Total: {}</strong></div>'
            '<div style="display: flex; gap: 4px;">'
            '<span style="background: #ef4444; color: white; padding: 1px 4px; border-radius: 4px;">H: {}</span>'
            '<span style="background: #f59e0b; color: white; padding: 1px 4px; border-radius: 4px;">M: {}</span>'
            '<span style="background: #6b7280; color: white; padding: 1px 4px; border-radius: 4px;">L: {}</span>'
            '</div>'
            '</div>',
            total_issues,
            issues_breakdown['High'],
            issues_breakdown['Medium'],
            issues_breakdown['Low']
        )
    
    @display(description="Actions")
    def audit_actions(self, obj):
        """Display quick action buttons"""
        actions = []
        
        if obj.status in ['completed', 'failed', 'pending']:
            actions.append(
                f'<button onclick="triggerAudit({obj.project.id})" '
                f'style="background: #3b82f6; color: white; border: none; padding: 4px 8px; '
                f'border-radius: 4px; font-size: 11px; cursor: pointer; margin-right: 4px;">'
                f'🔄 Run Audit</button>'
            )
        
        if obj.issues.exists():
            issues_url = reverse('admin:site_audit_siteissue_changelist') + f'?site_audit__id__exact={obj.id}'
            actions.append(
                f'<a href="{issues_url}" style="background: #f59e0b; color: white; text-decoration: none; '
                f'padding: 4px 8px; border-radius: 4px; font-size: 11px; display: inline-block;">'
                f'⚠️ Issues</a>'
            )
        
        return format_html('<div style="display: flex; gap: 4px;">{}</div>', ''.join(actions))
    
    @display(description="Crawl Overview")
    def crawl_overview_display(self, obj):
        """Display formatted crawl overview data"""
        if not obj.crawl_overview:
            return format_html('<p style="color: #9ca3af;">No crawl data available</p>')
        
        data = obj.crawl_overview
        html = ['<div style="font-family: monospace; font-size: 12px;">']
        
        # Basic stats
        html.append('<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 12px;">')
        html.append(f'<div><strong>URLs Encountered:</strong> {data.get("total_urls_encountered", "N/A"):,}</div>')
        html.append(f'<div><strong>URLs Crawled:</strong> {data.get("total_urls_crawled", "N/A"):,}</div>')
        html.append('</div>')
        
        # Top inlinks
        inlinks = data.get('top_20_inlinks', [])
        if inlinks:
            html.append('<div><strong>Top Inlinks:</strong></div>')
            html.append('<ul style="margin: 4px 0 0 16px; padding: 0;">')
            for link in inlinks[:5]:  # Show only first 5
                html.append(f'<li style="margin: 2px 0; color: #3b82f6;">{link}</li>')
            html.append('</ul>')
            if len(inlinks) > 5:
                html.append(f'<p style="margin: 4px 0; color: #6b7280; font-style: italic;">... and {len(inlinks) - 5} more</p>')
        
        html.append('</div>')
        return format_html(''.join(html))
    
    @display(description="Issues Overview")
    def issues_overview_display(self, obj):
        """Display formatted issues overview"""
        if not obj.issues_overview:
            return format_html('<p style="color: #9ca3af;">No issues data available</p>')
        
        data = obj.issues_overview
        html = ['<div style="font-family: monospace; font-size: 12px;">']
        
        # Issues by priority
        issues_by_priority = data.get('issues_by_priority', {})
        if issues_by_priority:
            html.append('<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 12px;">')
            for priority, count in issues_by_priority.items():
                color = {'High': '#ef4444', 'Medium': '#f59e0b', 'Low': '#6b7280'}.get(priority, '#9ca3af')
                html.append(f'<div style="color: {color};"><strong>{priority}:</strong> {count}</div>')
            html.append('</div>')
        
        # Issues by type (top 5)
        issues_by_type = data.get('issues_by_type', {})
        if issues_by_type:
            html.append('<div><strong>Top Issue Types:</strong></div>')
            html.append('<ul style="margin: 4px 0 0 16px; padding: 0;">')
            sorted_issues = sorted(issues_by_type.items(), key=lambda x: x[1], reverse=True)
            for issue_type, count in sorted_issues[:5]:
                html.append(f'<li style="margin: 2px 0;">{issue_type}: <strong>{count}</strong></li>')
            html.append('</ul>')
        
        html.append('</div>')
        return format_html(''.join(html))
    
    @display(description="Performance Data")
    def performance_data_display(self, obj):
        """Display formatted PageSpeed Insights data"""
        html = ['<div style="font-size: 12px;">']
        
        # Mobile performance
        if obj.mobile_performance:
            html.append('<h4 style="color: #3b82f6; margin: 0 0 8px 0;">📱 Mobile Performance</h4>')
            mobile_data = obj.mobile_performance
            
            # Scores
            scores = mobile_data.get('scores', {})
            html.append('<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 8px;">')
            for score_type, score in scores.items():
                if isinstance(score, dict):  # Skip PWA which is dict
                    continue
                color = '#10b981' if score >= 90 else '#f59e0b' if score >= 50 else '#ef4444'
                html.append(f'<div style="color: {color};"><strong>{score_type.title()}:</strong> {score}</div>')
            html.append('</div>')
            
            # Core Web Vitals
            lab_metrics = mobile_data.get('lab_metrics', {})
            if lab_metrics:
                html.append('<div><strong>Core Web Vitals:</strong></div>')
                html.append('<ul style="margin: 4px 0 0 16px; padding: 0; font-family: monospace;">')
                for metric, data_dict in lab_metrics.items():
                    if isinstance(data_dict, dict) and 'display_value' in data_dict:
                        html.append(f'<li>{metric.upper()}: {data_dict["display_value"]}</li>')
                html.append('</ul>')
        
        # Desktop performance
        if obj.desktop_performance:
            html.append('<h4 style="color: #3b82f6; margin: 16px 0 8px 0;">🖥️ Desktop Performance</h4>')
            desktop_data = obj.desktop_performance
            
            # Scores
            scores = desktop_data.get('scores', {})
            html.append('<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 8px;">')
            for score_type, score in scores.items():
                if isinstance(score, dict):  # Skip PWA which is dict
                    continue
                color = '#10b981' if score >= 90 else '#f59e0b' if score >= 50 else '#ef4444'
                html.append(f'<div style="color: {color};"><strong>{score_type.title()}:</strong> {score}</div>')
            html.append('</div>')
            
            # Core Web Vitals
            lab_metrics = desktop_data.get('lab_metrics', {})
            if lab_metrics:
                html.append('<div><strong>Core Web Vitals:</strong></div>')
                html.append('<ul style="margin: 4px 0 0 16px; padding: 0; font-family: monospace;">')
                for metric, data_dict in lab_metrics.items():
                    if isinstance(data_dict, dict) and 'display_value' in data_dict:
                        html.append(f'<li>{metric.upper()}: {data_dict["display_value"]}</li>')
                html.append('</ul>')
        
        if not obj.mobile_performance and not obj.desktop_performance:
            html.append('<p style="color: #9ca3af; font-style: italic;">No PageSpeed Insights data available</p>')
        
        html.append('</div>')
        return format_html(''.join(html))
    
    @display(description="Audit Statistics")
    def audit_statistics(self, obj):
        """Display comprehensive audit statistics"""
        html = ['<div style="font-size: 12px; font-family: monospace;">']
        
        # Basic stats
        html.append('<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 16px;">')
        html.append(f'<div><strong>Total Pages:</strong> {obj.total_pages_crawled:,}</div>')
        html.append(f'<div><strong>Total Issues:</strong> {obj.get_total_issues_count():,}</div>')
        html.append(f'<div><strong>Health Score:</strong> {obj.overall_site_health_score:.1f if obj.overall_site_health_score else "N/A"}</div>')
        html.append('</div>')
        
        # Performance metrics
        if obj.average_page_size_kb or obj.average_load_time_ms:
            html.append('<div style="margin-bottom: 16px;">')
            html.append('<strong>Technical Metrics:</strong>')
            html.append('<ul style="margin: 4px 0 0 16px;">')
            if obj.average_page_size_kb:
                html.append(f'<li>Avg Page Size: {obj.average_page_size_kb:.1f} KB</li>')
            if obj.average_load_time_ms:
                html.append(f'<li>Avg Load Time: {obj.average_load_time_ms:.0f} ms</li>')
            html.append('</ul>')
            html.append('</div>')
        
        # Audit frequency info
        html.append('<div>')
        html.append('<strong>Audit Schedule:</strong>')
        html.append('<ul style="margin: 4px 0 0 16px;">')
        html.append(f'<li>Auto Frequency: {obj.audit_frequency_days} days</li>')
        html.append(f'<li>Manual Frequency: {obj.manual_audit_frequency_days} days</li>')
        html.append(f'<li>Max Pages: {obj.max_pages_to_crawl:,}</li>')
        html.append(f'<li>Auto Audits: {"Enabled" if obj.is_audit_enabled else "Disabled"}</li>')
        html.append('</ul>')
        html.append('</div>')
        
        html.append('</div>')
        return format_html(''.join(html))
    
    def trigger_manual_audit(self, request, queryset):
        """Trigger manual audits for selected site audits"""
        from .tasks import trigger_manual_site_audit
        
        triggered_count = 0
        for site_audit in queryset:
            try:
                trigger_manual_site_audit.apply_async(args=[site_audit.project.id])
                triggered_count += 1
            except Exception as e:
                self.message_user(request, f'Failed to trigger audit for {site_audit.project.domain}: {e}', level='ERROR')
        
        if triggered_count > 0:
            self.message_user(request, f'{triggered_count} audit(s) triggered successfully.')
        else:
            self.message_user(request, 'No audits were triggered.', level='WARNING')
    trigger_manual_audit.short_description = "🔄 Trigger manual audits"
    
    def enable_audits(self, request, queryset):
        """Enable automatic audits for selected site audits"""
        count = queryset.update(is_audit_enabled=True)
        self.message_user(request, f'{count} audit(s) enabled successfully.')
    enable_audits.short_description = "✅ Enable automatic audits"
    
    def disable_audits(self, request, queryset):
        """Disable automatic audits for selected site audits"""
        count = queryset.update(is_audit_enabled=False)
        self.message_user(request, f'{count} audit(s) disabled successfully.')
    disable_audits.short_description = "❌ Disable automatic audits"
    
    def recalculate_scores(self, request, queryset):
        """Recalculate overall scores for selected audits"""
        updated_count = 0
        for audit in queryset:
            audit.calculate_overall_score()
            audit.save(update_fields=['overall_site_health_score'])
            updated_count += 1
        
        self.message_user(request, f'{updated_count} score(s) recalculated successfully.')
    recalculate_scores.short_description = "🔢 Recalculate overall scores"


@admin.register(SiteIssue)
class SiteIssueAdmin(ModelAdmin):
    list_display = (
        'url_display',
        'issue_type_display',
        'severity_badge',
        'issue_category',
        'site_audit_link',
        'inlinks_count',
        'created_at'
    )
    
    list_filter = (
        ('severity', ChoicesDropdownFilter),
        ('issue_category', ChoicesDropdownFilter),
        ('created_at', RangeDateFilter),
        ('inlinks_count', RangeNumericFilter),
        'site_audit__status',
        'site_audit__project__active'
    )
    
    search_fields = (
        'url',
        'issue_type',
        'site_audit__project__domain',
        'site_audit__project__title'
    )
    
    readonly_fields = ('created_at', 'updated_at', 'issue_data_display')
    ordering = ('severity', '-inlinks_count', 'issue_type')
    list_per_page = 50
    list_select_related = ('site_audit', 'site_audit__project')
    
    fieldsets = (
        ('Issue Information', {
            'fields': ('site_audit', 'url', 'issue_type', 'issue_category', 'severity'),
            'description': 'Basic issue identification and classification'
        }),
        ('SEO Metadata', {
            'fields': ('indexability', 'indexability_status', 'inlinks_count'),
            'classes': ('collapse',),
            'description': 'Search engine optimization related data'
        }),
        ('Issue Details', {
            'fields': ('issue_data_display',),
            'classes': ('collapse',),
            'description': 'Detailed issue data and context'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_resolved', 'export_issues']
    
    @display(description="URL", ordering="url")
    def url_display(self, obj):
        """Display URL with truncation and external link"""
        url = obj.url
        display_url = url if len(url) <= 50 else url[:47] + '...'
        return format_html(
            '<div style="display: flex; align-items: center; gap: 6px;">'
            '<a href="{}" target="_blank" style="color: #3b82f6; text-decoration: none;" title="{}">{}</a>'
            '<span style="font-size: 10px; color: #9ca3af;">🔗</span>'
            '</div>',
            url,
            url,
            display_url
        )
    
    @display(description="Issue Type", ordering="issue_type")
    def issue_type_display(self, obj):
        """Display issue type with formatting"""
        return format_html(
            '<span style="font-family: monospace; background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 11px;">{}</span>',
            obj.issue_type
        )
    
    @display(description="Severity", ordering="severity")
    def severity_badge(self, obj):
        """Display severity with colored badge"""
        severity_colors = {
            'critical': '#dc2626',
            'high': '#ef4444',
            'medium': '#f59e0b',
            'low': '#6b7280',
            'info': '#3b82f6'
        }
        color = severity_colors.get(obj.severity, '#9ca3af')
        
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 500;">{}</span>',
            color,
            obj.get_severity_display()
        )
    
    @display(description="Site Audit")
    def site_audit_link(self, obj):
        """Display link to related site audit"""
        audit_url = reverse('admin:site_audit_siteaudit_change', args=[obj.site_audit.id])
        return format_html(
            '<a href="{}" style="color: #3b82f6; text-decoration: none; font-size: 12px;">Audit #{} - {}</a>',
            audit_url,
            obj.site_audit.id,
            obj.site_audit.project.domain
        )
    
    @display(description="Issue Data")
    def issue_data_display(self, obj):
        """Display formatted issue data"""
        if not obj.issue_data:
            return format_html('<p style="color: #9ca3af;">No additional data</p>')
        
        html = ['<div style="font-family: monospace; font-size: 12px;">']
        html.append('<pre style="background: #f8f9fa; padding: 12px; border-radius: 6px; overflow-x: auto; margin: 0;">')
        html.append(json.dumps(obj.issue_data, indent=2))
        html.append('</pre>')
        html.append('</div>')
        
        return format_html(''.join(html))
    
    def mark_as_resolved(self, request, queryset):
        """Mark selected issues as resolved (for future enhancement)"""
        # This is a placeholder action - you can implement resolution tracking
        self.message_user(request, f'{queryset.count()} issues marked for review.')
    mark_as_resolved.short_description = "✅ Mark as reviewed"
    
    def export_issues(self, request, queryset):
        """Export selected issues (placeholder for CSV export)"""
        # Placeholder for CSV export functionality
        self.message_user(request, f'Export functionality coming soon for {queryset.count()} issues.')
    export_issues.short_description = "📄 Export issues"