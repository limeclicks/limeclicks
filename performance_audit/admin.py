from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from .models import PerformancePage, PerformanceHistory, PerformanceSchedule
from .tasks import run_manual_audit, check_scheduled_audits
from common.admin import (
    AuditHistoryAdminMixin,
    OptimizedQuerysetMixin,
    TimestampedAdminMixin,
    LinksMixin
)


@admin.register(PerformancePage)
class PerformancePageAdmin(admin.ModelAdmin):
    list_display = [
        'project_domain', 
        'page_url_display',
        'last_audit_date', 
        'next_scheduled_audit',
        'score_badges',
        'is_audit_enabled',
        'audit_actions'
    ]
    list_filter = ['is_audit_enabled', 'last_audit_date', 'next_scheduled_audit']
    search_fields = ['project__domain', 'page_url']
    readonly_fields = [
        'project', 
        'last_audit_date',
        'performance_score',
        'accessibility_score',
        'best_practices_score',
        'seo_score',
        'pwa_score',
        'created_at',
        'updated_at'
    ]
    
    fieldsets = (
        ('Project Information', {
            'fields': ('project', 'page_url')
        }),
        ('Latest Audit Scores', {
            'fields': (
                'last_audit_date',
                'performance_score',
                'accessibility_score',
                'best_practices_score',
                'seo_score',
                'pwa_score'
            )
        }),
        ('Audit Settings', {
            'fields': (
                'is_audit_enabled',
                'audit_frequency_days',
                'next_scheduled_audit',
                'last_manual_audit'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def project_domain(self, obj):
        return obj.project.domain
    project_domain.short_description = 'Project Domain'
    project_domain.admin_order_field = 'project__domain'
    
    def page_url_display(self, obj):
        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            obj.page_url,
            obj.page_url[:50] + '...' if len(obj.page_url) > 50 else obj.page_url
        )
    page_url_display.short_description = 'Page URL'
    
    def score_badges(self, obj):
        def get_score_color(score):
            if score is None:
                return '#999'
            elif score >= 90:
                return '#0cce6b'
            elif score >= 50:
                return '#ffa400'
            else:
                return '#ff4e42'
        
        badges = []
        scores = [
            ('P', obj.performance_score),
            ('A', obj.accessibility_score),
            ('BP', obj.best_practices_score),
            ('SEO', obj.seo_score)
        ]
        
        for label, score in scores:
            if score is not None:
                color = get_score_color(score)
                badges.append(
                    f'<span style="background:{color};color:white;padding:2px 6px;'
                    f'border-radius:3px;margin-right:4px;font-size:11px;">'
                    f'{label}:{score}</span>'
                )
        
        return format_html(''.join(badges)) if badges else '-'
    score_badges.short_description = 'Scores'
    
    def audit_actions(self, obj):
        return format_html(
            '<a class="button" href="{}">View History</a>&nbsp;'
            '<a class="button" href="{}">Run Manual</a>',
            reverse('admin:performance_audit_performancehistory_changelist') + f'?performance_page__id__exact={obj.id}',
            reverse('admin:performance_audit_performancepage_run_manual', args=[obj.pk])
        )
    audit_actions.short_description = 'Actions'
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:pk>/run-manual/',
                self.admin_site.admin_view(self.run_manual_audit_view),
                name='performance_audit_performancepage_run_manual'
            ),
        ]
        return custom_urls + urls
    
    def run_manual_audit_view(self, request, pk):
        from django.shortcuts import redirect
        performance_page = self.get_object(request, pk)
        
        if performance_page:
            result = run_manual_audit.delay(performance_page.id)
            if result:
                messages.success(request, f'Manual audit started for {performance_page.project.domain}')
            else:
                messages.error(request, 'Failed to start manual audit')
        
        return redirect('admin:performance_audit_performancepage_changelist')


@admin.register(PerformanceHistory)
class PerformanceHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'audit_id_short',
        'project_domain',
        'trigger_type',
        'status_badge',
        'mobile_score_summary',
        'desktop_score_summary',
        'created_at',
        'duration',
        'view_reports'
    ]
    list_filter = [
        'status',
        'trigger_type',
        'created_at',
        'performance_page__project'
    ]
    search_fields = [
        'id',
        'performance_page__project__domain',
        'performance_page__page_url',
        'error_message'
    ]
    readonly_fields = [
        'id',
        'performance_page',
        'status',
        'trigger_type',
        'created_at',
        'started_at',
        'completed_at',
        # Mobile scores
        'mobile_performance_score',
        'mobile_accessibility_score',
        'mobile_best_practices_score',
        'mobile_seo_score',
        'mobile_pwa_score',
        'mobile_overall_score',
        # Desktop scores
        'desktop_performance_score',
        'desktop_accessibility_score',
        'desktop_best_practices_score',
        'desktop_seo_score',
        'desktop_pwa_score',
        'desktop_overall_score',
        # Mobile metrics
        'mobile_first_contentful_paint',
        'mobile_largest_contentful_paint',
        'mobile_time_to_interactive',
        'mobile_speed_index',
        'mobile_total_blocking_time',
        'mobile_cumulative_layout_shift',
        # Desktop metrics
        'desktop_first_contentful_paint',
        'desktop_largest_contentful_paint',
        'desktop_time_to_interactive',
        'desktop_speed_index',
        'desktop_total_blocking_time',
        'desktop_cumulative_layout_shift',
        'error_message',
        'retry_count'
    ]
    
    fieldsets = (
        ('Audit Information', {
            'fields': (
                'id',
                'performance_page',
                'status',
                'trigger_type'
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'started_at',
                'completed_at'
            )
        }),
        ('Mobile Scores', {
            'fields': (
                'mobile_performance_score',
                'mobile_accessibility_score',
                'mobile_best_practices_score',
                'mobile_seo_score',
                'mobile_pwa_score',
                'mobile_overall_score'
            )
        }),
        ('Desktop Scores', {
            'fields': (
                'desktop_performance_score',
                'desktop_accessibility_score',
                'desktop_best_practices_score',
                'desktop_seo_score',
                'desktop_pwa_score',
                'desktop_overall_score'
            )
        }),
        ('Mobile Performance Metrics', {
            'fields': (
                'mobile_first_contentful_paint',
                'mobile_largest_contentful_paint',
                'mobile_time_to_interactive',
                'mobile_speed_index',
                'mobile_total_blocking_time',
                'mobile_cumulative_layout_shift'
            ),
            'classes': ('collapse',)
        }),
        ('Desktop Performance Metrics', {
            'fields': (
                'desktop_first_contentful_paint',
                'desktop_largest_contentful_paint',
                'desktop_time_to_interactive',
                'desktop_speed_index',
                'desktop_total_blocking_time',
                'desktop_cumulative_layout_shift'
            ),
            'classes': ('collapse',)
        }),
        ('Reports', {
            'fields': ('mobile_json_report', 'mobile_html_report', 'desktop_json_report', 'desktop_html_report', 'consolidated_error_report')
        }),
        ('Error Information', {
            'fields': ('error_message', 'retry_count'),
            'classes': ('collapse',)
        })
    )
    
    def audit_id_short(self, obj):
        return str(obj.id)[:8]
    audit_id_short.short_description = 'Audit ID'
    
    def project_domain(self, obj):
        return obj.performance_page.project.domain
    project_domain.short_description = 'Project'
    project_domain.admin_order_field = 'performance_page__project__domain'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#ffa500',
            'running': '#007bff',
            'completed': '#28a745',
            'failed': '#dc3545'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{};color:white;padding:3px 8px;'
            'border-radius:3px;font-size:11px;font-weight:bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def mobile_score_summary(self, obj):
        if obj.status != 'completed':
            return '-'
        
        scores = [
            obj.mobile_performance_score,
            obj.mobile_accessibility_score,
            obj.mobile_best_practices_score,
            obj.mobile_seo_score
        ]
        
        # Calculate average
        valid_scores = [s for s in scores if s is not None]
        if not valid_scores:
            return '-'
        
        avg = sum(valid_scores) / len(valid_scores)
        
        # Determine color based on average
        if avg >= 90:
            color = '#0cce6b'
        elif avg >= 50:
            color = '#ffa400'
        else:
            color = '#ff4e42'
        
        return format_html(
            '<span style="color:{};">P:{} A:{} BP:{} SEO:{}</span>',
            color,
            obj.mobile_performance_score or '-',
            obj.mobile_accessibility_score or '-',
            obj.mobile_best_practices_score or '-',
            obj.mobile_seo_score or '-'
        )
    mobile_score_summary.short_description = 'Mobile Scores'
    
    def desktop_score_summary(self, obj):
        if obj.status != 'completed':
            return '-'
        
        scores = [
            obj.desktop_performance_score,
            obj.desktop_accessibility_score,
            obj.desktop_best_practices_score,
            obj.desktop_seo_score
        ]
        
        # Calculate average
        valid_scores = [s for s in scores if s is not None]
        if not valid_scores:
            return '-'
        
        avg = sum(valid_scores) / len(valid_scores)
        
        # Determine color based on average
        if avg >= 90:
            color = '#0cce6b'
        elif avg >= 50:
            color = '#ffa400'
        else:
            color = '#ff4e42'
        
        return format_html(
            '<span style="color:{};">P:{} A:{} BP:{} SEO:{}</span>',
            color,
            obj.desktop_performance_score or '-',
            obj.desktop_accessibility_score or '-',
            obj.desktop_best_practices_score or '-',
            obj.desktop_seo_score or '-'
        )
    desktop_score_summary.short_description = 'Desktop Scores'
    
    def duration(self, obj):
        if obj.started_at and obj.completed_at:
            delta = obj.completed_at - obj.started_at
            minutes = int(delta.total_seconds() / 60)
            seconds = int(delta.total_seconds() % 60)
            return f'{minutes}m {seconds}s'
        return '-'
    duration.short_description = 'Duration'
    
    def view_reports(self, obj):
        buttons = []
        
        # Mobile reports
        if obj.mobile_json_report:
            buttons.append(
                format_html(
                    '<a class="button" href="{}" target="_blank" style="margin-right:5px;">📱 JSON</a>',
                    obj.mobile_json_report.url
                )
            )
        
        if obj.mobile_html_report:
            buttons.append(
                format_html(
                    '<a class="button" href="{}" target="_blank" style="margin-right:5px;">📱 HTML</a>',
                    obj.mobile_html_report.url
                )
            )
        
        # Desktop reports
        if obj.desktop_json_report:
            buttons.append(
                format_html(
                    '<a class="button" href="{}" target="_blank" style="margin-right:5px;">💻 JSON</a>',
                    obj.desktop_json_report.url
                )
            )
        
        if obj.desktop_html_report:
            buttons.append(
                format_html(
                    '<a class="button" href="{}" target="_blank" style="margin-right:5px;">💻 HTML</a>',
                    obj.desktop_html_report.url
                )
            )
        
        return format_html(' '.join(buttons)) if buttons else '-'
    view_reports.short_description = 'Reports'
    
    def has_add_permission(self, request):
        # Prevent manual creation of audit history
        return False


@admin.register(PerformanceSchedule)
class PerformanceScheduleAdmin(admin.ModelAdmin):
    list_display = [
        'performance_page_domain',
        'scheduled_for',
        'is_processed',
        'processed_at',
        'task_id'
    ]
    list_filter = ['is_processed', 'scheduled_for', 'processed_at']
    search_fields = ['performance_page__project__domain', 'task_id']
    readonly_fields = ['performance_page', 'scheduled_for', 'task_id', 'is_processed', 'processed_at']
    
    def performance_page_domain(self, obj):
        return obj.performance_page.project.domain
    performance_page_domain.short_description = 'Project'
    performance_page_domain.admin_order_field = 'performance_page__project__domain'
    
    def has_add_permission(self, request):
        # Prevent manual creation of schedules
        return False
    
    actions = ['run_scheduled_audits_check']
    
    def run_scheduled_audits_check(self, request, queryset):
        """Admin action to manually trigger scheduled audits check"""
        result = check_scheduled_audits.delay()
        if result:
            messages.success(request, 'Scheduled audits check has been triggered.')
        else:
            messages.error(request, 'Failed to trigger scheduled audits check.')
    run_scheduled_audits_check.short_description = 'Run scheduled audits check'
