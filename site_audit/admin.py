from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db import models
from django.db.models import Count, Q
from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.filters.admin import RangeNumericFilter, RangeDateFilter, ChoicesDropdownFilter
from unfold.decorators import display
from .models import SiteAudit, SiteIssue, AuditFile
import json


class IssuesFromJSONInline(TabularInline):
    """Display issues from JSON field as inline (read-only)"""
    model = SiteIssue
    fk_name = 'site_audit'  # Specify the foreign key to use
    extra = 0
    max_num = 0
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    # Override to show JSON issues if no DB issues exist
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if qs.count() == 0:
            # Return empty queryset but we'll show JSON data in the template
            return qs
        return qs


class AuditFileInline(TabularInline):
    """Display uploaded audit files as inline"""
    model = AuditFile
    extra = 0
    can_delete = False
    fields = ('file_type', 'original_filename', 'file_size_display', 'uploaded_at', 'download_link')
    readonly_fields = ('file_type', 'original_filename', 'file_size_display', 'uploaded_at', 'download_link')
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    @display(description="Size")
    def file_size_display(self, obj):
        """Display file size in human readable format"""
        if obj.file_size < 1024:
            return f"{obj.file_size} B"
        elif obj.file_size < 1024 * 1024:
            return f"{obj.file_size / 1024:.2f} KB"
        else:
            return f"{obj.file_size / 1024 / 1024:.2f} MB"
    
    @display(description="Download")
    def download_link(self, obj):
        """Generate download link for the file"""
        if not obj.r2_path:
            return "-"
        return format_html(
            '<a href="#" onclick="alert(\'R2 path: {}\')" style="color: #3b82f6;">View Path</a>',
            obj.r2_path
        )


@admin.register(SiteAudit)
class SiteAuditAdmin(ModelAdmin):
    list_display = (
        'id',
        'project_display',
        'status_badge',
        'health_score_display',
        'pages_display',
        'issues_display',
        'performance_display',
        'last_audit_display',
        'view_details_link'
    )
    
    list_filter = (
        'status',
        'is_audit_enabled',
        ('overall_site_health_score', RangeNumericFilter),
        ('total_pages_crawled', RangeNumericFilter),
        ('last_audit_date', RangeDateFilter),
    )
    
    search_fields = ('project__domain', 'project__title')
    ordering = ('-last_audit_date',)
    list_per_page = 25
    
    readonly_fields = (
        'project',
        'status',
        'overall_site_health_score',
        'total_pages_crawled',
        'performance_score_mobile',
        'performance_score_desktop',
        'last_audit_date',
        'issues_overview_display',
        'crawl_overview_display',
    )
    
    fieldsets = (
        ('Project Information', {
            'fields': ('project', 'status', 'last_audit_date')
        }),
        ('Audit Configuration', {
            'fields': (
                'is_audit_enabled',
                'audit_frequency_days',
                'manual_audit_frequency_days',
                'max_pages_to_crawl'
            )
        }),
        ('Audit Results', {
            'fields': (
                'overall_site_health_score',
                'total_pages_crawled',
                'performance_score_mobile',
                'performance_score_desktop',
            )
        }),
        ('Issues Overview', {
            'fields': ('issues_overview_display',),
            'classes': ('wide',)
        }),
        ('Crawl Overview', {
            'fields': ('crawl_overview_display',),
            'classes': ('wide',)
        }),
    )
    
    inlines = [AuditFileInline, IssuesFromJSONInline]
    
    @display(description="Project")
    def project_display(self, obj):
        """Display project with favicon"""
        if not obj.project:
            return "-"
        
        favicon_url = obj.project.get_cached_favicon_url(size=32)
        return format_html(
            '<div style="display: flex; align-items: center; gap: 8px;">'
            '<img src="{}" style="width: 20px; height: 20px; border-radius: 4px;">'
            '<div>'
            '<strong>{}</strong><br>'
            '<small style="color: #6b7280;">{}</small>'
            '</div>'
            '</div>',
            favicon_url,
            obj.project.domain,
            obj.project.title or 'No title'
        )
    
    @display(description="Status")
    def status_badge(self, obj):
        """Display status as badge"""
        colors = {
            'completed': '#10b981',
            'running': '#f59e0b',
            'pending': '#3b82f6',
            'failed': '#ef4444'
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 8px; '
            'border-radius: 4px; font-size: 12px; font-weight: 500;">{}</span>',
            color,
            obj.status.upper()
        )
    
    @display(description="Health Score", ordering="overall_site_health_score")
    def health_score_display(self, obj):
        """Display health score with color coding"""
        score = obj.overall_site_health_score
        if score is None:
            return "-"
        
        if score >= 80:
            color = '#10b981'
            icon = '✅'
        elif score >= 60:
            color = '#f59e0b'
            icon = '⚠️'
        else:
            color = '#ef4444'
            icon = '❌'
        
        return format_html(
            '<div style="display: flex; align-items: center; gap: 4px;">'
            '<span>{}</span>'
            '<strong style="color: {}; font-size: 16px;">{}</strong>'
            '</div>',
            icon, color, int(score)
        )
    
    @display(description="Pages", ordering="total_pages_crawled")
    def pages_display(self, obj):
        """Display pages crawled"""
        if obj.total_pages_crawled == 0:
            return format_html('<span style="color: #9ca3af;">0</span>')
        
        formatted_number = f"{obj.total_pages_crawled:,}"
        return format_html(
            '<strong style="color: #059669;">{}</strong>',
            formatted_number
        )
    
    @display(description="Issues")
    def issues_display(self, obj):
        """Display issues summary from JSON"""
        issues_by_priority = obj.get_issues_by_priority()
        total = obj.get_total_issues_count()
        
        if total == 0:
            return format_html('<span style="color: #10b981;">✅ No issues</span>')
        
        badges = []
        if issues_by_priority.get('High', 0) > 0:
            badges.append(format_html(
                '<span style="background: #fee2e2; color: #dc2626; padding: 2px 6px; '
                'border-radius: 3px; font-size: 11px; margin-right: 4px;">'
                '{} High</span>',
                issues_by_priority['High']
            ))
        if issues_by_priority.get('Medium', 0) > 0:
            badges.append(format_html(
                '<span style="background: #fef3c7; color: #d97706; padding: 2px 6px; '
                'border-radius: 3px; font-size: 11px; margin-right: 4px;">'
                '{} Med</span>',
                issues_by_priority['Medium']
            ))
        if issues_by_priority.get('Low', 0) > 0:
            badges.append(format_html(
                '<span style="background: #dbeafe; color: #2563eb; padding: 2px 6px; '
                'border-radius: 3px; font-size: 11px;">'
                '{} Low</span>',
                issues_by_priority['Low']
            ))
        
        return format_html(
            '<div style="display: flex; flex-direction: column; gap: 4px;">'
            '<strong>Total: {}</strong>'
            '<div>{}</div>'
            '</div>',
            total,
            ''.join(badges)
        )
    
    @display(description="Performance")
    def performance_display(self, obj):
        """Display performance scores"""
        mobile = obj.performance_score_mobile or 0
        desktop = obj.performance_score_desktop or 0
        
        def get_color(score):
            if score >= 90:
                return '#10b981'
            elif score >= 50:
                return '#f59e0b'
            else:
                return '#ef4444'
        
        return format_html(
            '<div style="display: flex; gap: 8px;">'
            '<span style="color: {};">📱 {}</span>'
            '<span style="color: {};">💻 {}</span>'
            '</div>',
            get_color(mobile), mobile,
            get_color(desktop), desktop
        )
    
    @display(description="Last Audit")
    def last_audit_display(self, obj):
        """Display last audit date"""
        if not obj.last_audit_date:
            return "-"
        
        from django.utils import timezone
        from django.utils.timesince import timesince
        
        time_ago = timesince(obj.last_audit_date, timezone.now())
        return format_html(
            '<span title="{}">{} ago</span>',
            obj.last_audit_date.strftime('%Y-%m-%d %H:%M'),
            time_ago
        )
    
    @display(description="Actions")
    def view_details_link(self, obj):
        """Link to view audit details"""
        detail_url = reverse('site_audit:detail', args=[obj.id])
        issues_url = reverse('admin:site_audit_siteissue_changelist') + f'?site_audit__id__exact={obj.id}'
        
        return format_html(
            '<a href="{}" target="_blank" style="color: #3b82f6; text-decoration: none; '
            'padding: 4px 8px; background: #eff6ff; border-radius: 4px; '
            'display: inline-block; margin-right: 4px;">View Report</a>'
            '<a href="{}" style="color: #7c3aed; text-decoration: none; '
            'padding: 4px 8px; background: #f3f4f6; border-radius: 4px; '
            'display: inline-block;">Issues ({})</a>',
            detail_url,
            issues_url,
            obj.get_total_issues_count()
        )
    
    @display(description="Issues Overview (from JSON)")
    def issues_overview_display(self, obj):
        """Display issues from JSON in a formatted way"""
        if not obj.issues_overview:
            return "No issues data"
        
        issues_list = obj.issues_overview.get('issues', [])
        if not issues_list:
            return "No issues found"
        
        # Group issues by priority
        by_priority = {'High': [], 'Medium': [], 'Low': []}
        for issue in issues_list[:20]:  # Show first 20
            priority = issue.get('issue_priority', 'Low')
            by_priority[priority].append(issue)
        
        html_parts = ['<div style="max-height: 400px; overflow-y: auto;">']
        
        for priority, priority_issues in by_priority.items():
            if not priority_issues:
                continue
            
            color = {'High': '#dc2626', 'Medium': '#d97706', 'Low': '#2563eb'}[priority]
            html_parts.append(f'<h4 style="color: {color}; margin: 10px 0;">{priority} Priority ({len(priority_issues)})</h4>')
            html_parts.append('<ul style="margin: 0; padding-left: 20px;">')
            
            for issue in priority_issues:
                html_parts.append(format_html(
                    '<li style="margin: 5px 0;">'
                    '<strong>{}</strong> - {} URLs affected<br>'
                    '<small style="color: #6b7280;">{}</small>'
                    '</li>',
                    issue.get('issue_name', 'Unknown'),
                    issue.get('urls', 0),
                    issue.get('description', '')[:100] + '...' if issue.get('description') else ''
                ))
            
            html_parts.append('</ul>')
        
        html_parts.append('</div>')
        return mark_safe(''.join(html_parts))
    
    @display(description="Crawl Overview")
    def crawl_overview_display(self, obj):
        """Display crawl overview data"""
        if not obj.crawl_overview:
            return "No crawl data"
        
        return format_html(
            '<pre style="background: #f9fafb; padding: 10px; border-radius: 4px; '
            'overflow-x: auto; max-width: 600px;">{}</pre>',
            json.dumps(obj.crawl_overview, indent=2)[:1000] + '...' if len(json.dumps(obj.crawl_overview)) > 1000 else json.dumps(obj.crawl_overview, indent=2)
        )


@admin.register(SiteIssue)
class SiteIssueAdmin(ModelAdmin):
    list_display = (
        'id',
        'site_audit_link',
        'severity_badge',
        'issue_type_display',
        'url_display',
        'issue_category',
        'inlinks_count',
        'created_at'
    )
    
    list_filter = (
        'severity',
        'issue_category',
        'issue_type',
        ('created_at', RangeDateFilter),
        ('inlinks_count', RangeNumericFilter),
    )
    
    search_fields = ('url', 'issue_type', 'description')
    ordering = ('severity', '-created_at')
    list_per_page = 50
    
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Issue Information', {
            'fields': ('site_audit', 'url', 'severity', 'issue_type', 'issue_category')
        }),
        ('Issue Details', {
            'fields': ('description', 'recommendation', 'inlinks_count'),
            'classes': ('wide',)
        }),
        ('Technical Details', {
            'fields': ('technical_details', 'indexability', 'indexability_status'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    @display(description="Audit")
    def site_audit_link(self, obj):
        """Link to parent audit"""
        if not obj.site_audit:
            return "-"
        
        audit_url = reverse('admin:site_audit_siteaudit_change', args=[obj.site_audit.id])
        return format_html(
            '<a href="{}" style="color: #3b82f6;">{}</a>',
            audit_url,
            obj.site_audit.project.domain if obj.site_audit.project else f'Audit #{obj.site_audit.id}'
        )
    
    @display(description="Severity", ordering="severity")
    def severity_badge(self, obj):
        """Display severity as colored badge"""
        colors = {
            'critical': '#dc2626',
            'high': '#ef4444',
            'medium': '#f59e0b',
            'low': '#3b82f6',
            'info': '#6b7280'
        }
        
        display_names = {
            'critical': 'CRITICAL',
            'high': 'HIGH',
            'medium': 'MEDIUM',
            'low': 'LOW',
            'info': 'INFO'
        }
        
        color = colors.get(obj.severity, '#6b7280')
        name = display_names.get(obj.severity, obj.severity.upper())
        
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px; font-weight: 600;">{}</span>',
            color, name
        )
    
    @display(description="Issue Type")
    def issue_type_display(self, obj):
        """Display issue type with formatting"""
        return format_html(
            '<strong>{}</strong>',
            obj.issue_type.replace('_', ' ').title()
        )
    
    @display(description="URL")
    def url_display(self, obj):
        """Display URL with truncation"""
        if not obj.url:
            return "-"
        
        truncated = obj.url[:50] + '...' if len(obj.url) > 50 else obj.url
        return format_html(
            '<a href="{}" target="_blank" style="color: #6b7280;">{}</a>',
            obj.url if obj.url.startswith('http') else f'http://{obj.url}',
            truncated
        )
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('site_audit', 'site_audit__project')
    
    class Media:
        css = {
            'all': ('admin/css/site_audit_admin.css',)
        }


@admin.register(AuditFile)
class AuditFileAdmin(ModelAdmin):
    """Admin for viewing audit files uploaded to R2"""
    list_display = (
        'id',
        'site_audit_link',
        'file_type',
        'original_filename',
        'file_size_display',
        'uploaded_at',
        'r2_path_display'
    )
    
    list_filter = (
        'file_type',
        ('uploaded_at', RangeDateFilter),
        ('file_size', RangeNumericFilter),
    )
    
    search_fields = (
        'original_filename',
        'r2_path',
        'site_audit__project__domain'
    )
    
    ordering = ('-uploaded_at',)
    list_per_page = 50
    
    readonly_fields = (
        'site_audit',
        'file_type',
        'original_filename',
        'r2_path',
        'file_size',
        'mime_type',
        'checksum',
        'uploaded_at'
    )
    
    fieldsets = (
        ('Audit Information', {
            'fields': ('site_audit',)
        }),
        ('File Information', {
            'fields': (
                'file_type',
                'original_filename',
                'r2_path',
                'file_size',
                'mime_type'
            )
        }),
        ('Metadata', {
            'fields': ('checksum', 'uploaded_at'),
            'classes': ('collapse',)
        }),
    )
    
    @display(description="Site Audit")
    def site_audit_link(self, obj):
        """Link to parent audit"""
        if not obj.site_audit:
            return "-"
        
        audit_url = reverse('admin:site_audit_siteaudit_change', args=[obj.site_audit.id])
        return format_html(
            '<a href="{}" style="color: #3b82f6;">{}</a>',
            audit_url,
            obj.site_audit.project.domain if obj.site_audit.project else f'Audit #{obj.site_audit.id}'
        )
    
    @display(description="Size", ordering="file_size")
    def file_size_display(self, obj):
        """Display file size in human readable format"""
        if obj.file_size < 1024:
            return f"{obj.file_size} B"
        elif obj.file_size < 1024 * 1024:
            return f"{obj.file_size / 1024:.2f} KB"
        else:
            return f"{obj.file_size / 1024 / 1024:.2f} MB"
    
    @display(description="R2 Path")
    def r2_path_display(self, obj):
        """Display truncated R2 path"""
        if not obj.r2_path:
            return "-"
        
        # Show only the last part of the path
        parts = obj.r2_path.split('/')
        if len(parts) > 2:
            return f".../{'/'.join(parts[-2:])}"
        return obj.r2_path