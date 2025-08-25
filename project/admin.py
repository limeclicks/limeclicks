from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from django import forms
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.urls import path, reverse
from django.utils.html import format_html
from .models import Project

User = get_user_model()


class ProjectAdminForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = '__all__'
    
    def clean_domain(self):
        domain = self.cleaned_data.get('domain')
        if domain:
            # Remove http:// or https:// if present
            import re
            domain = domain.lower()
            domain = re.sub(r'^https?://', '', domain)
            
            # Remove trailing slash if present
            domain = domain.rstrip('/')
            
            # Remove www. prefix if present
            domain = re.sub(r'^www\.', '', domain)
            
            # Validate domain format - must have at least one dot for proper domain/subdomain
            # Reject localhost and single words
            if '.' not in domain:
                raise forms.ValidationError('Please enter a valid domain or subdomain name (must contain at least one dot).')
            
            # Check for invalid characters
            if not re.match(r'^[a-zA-Z0-9.-]+$', domain):
                raise forms.ValidationError('Domain name contains invalid characters. Only letters, numbers, dots, and hyphens are allowed.')
            
            # Validate proper domain format
            domain_pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
            if not re.match(domain_pattern, domain):
                raise forms.ValidationError('Please enter a valid domain or subdomain name.')
            
            # Additional validations
            if domain.startswith('.') or domain.endswith('.'):
                raise forms.ValidationError('Domain cannot start or end with a dot.')
            
            if '..' in domain:
                raise forms.ValidationError('Domain cannot contain consecutive dots.')
            
            if domain.startswith('-') or domain.endswith('-'):
                raise forms.ValidationError('Domain cannot start or end with a hyphen.')
            
            return domain
        return domain


# Inline admin for Lighthouse Audits
class PerformancePageInline(TabularInline):
    from performance_audit.models import PerformancePage
    model = PerformancePage
    extra = 0
    readonly_fields = ('page_url', 'last_audit_date', 'score_display', 'audit_actions')
    fields = ('page_url', 'last_audit_date', 'score_display', 'is_audit_enabled', 'audit_actions')
    can_delete = False
    
    def score_display(self, obj):
        if not obj.last_audit_date:
            return '-'
        
        def get_score_color(score):
            if score is None:
                return '#999'
            elif score >= 90:
                return '#0cce6b'
            elif score >= 50:
                return '#ffa400'
            else:
                return '#ff4e42'
        
        scores = []
        if obj.performance_score is not None:
            color = get_score_color(obj.performance_score)
            scores.append(f'<span style="background:{color};color:white;padding:2px 6px;'
                         f'border-radius:3px;margin-right:4px;">P:{obj.performance_score}</span>')
        if obj.seo_score is not None:
            color = get_score_color(obj.seo_score)
            scores.append(f'<span style="background:{color};color:white;padding:2px 6px;'
                         f'border-radius:3px;margin-right:4px;">SEO:{obj.seo_score}</span>')
        if obj.accessibility_score is not None:
            color = get_score_color(obj.accessibility_score)
            scores.append(f'<span style="background:{color};color:white;padding:2px 6px;'
                         f'border-radius:3px;">A:{obj.accessibility_score}</span>')
        
        return format_html(''.join(scores)) if scores else '-'
    score_display.short_description = 'Latest Scores'
    
    def audit_actions(self, obj):
        if not obj.id:
            return '-'
        return format_html(
            '<a class="button" href="{}" style="padding:5px 10px;background:#007bff;color:white;'
            'text-decoration:none;border-radius:3px;">View History</a>',
            reverse('admin:performance_audit_audithistory_changelist') + f'?performance_page__id__exact={obj.id}'
        )
    audit_actions.short_description = 'Actions'
    
    def has_add_permission(self, request, obj=None):
        return False


# Inline admin for OnPage Audits
class SiteAuditInline(TabularInline):
    from site_audit.models import SiteAudit
    model = SiteAudit
    extra = 0
    readonly_fields = ('last_audit_date', 'total_issues_count', 'issues_display', 'audit_actions')
    fields = ('last_audit_date', 'max_pages_to_crawl', 'total_issues_count', 'issues_display', 
              'is_audit_enabled', 'audit_actions')
    can_delete = False
    
    def issues_display(self, obj):
        if obj.total_issues_count == 0:
            color = 'green'
            text = 'No issues'
        elif obj.total_issues_count <= 10:
            color = 'orange'
            text = f'{obj.total_issues_count} issues'
        else:
            color = 'red'
            text = f'{obj.total_issues_count} issues'
        
        details = []
        if obj.broken_links_count > 0:
            details.append(f'{obj.broken_links_count} broken links')
        if obj.missing_titles_count > 0:
            details.append(f'{obj.missing_titles_count} missing titles')
        if obj.duplicate_titles_count > 0:
            details.append(f'{obj.duplicate_titles_count} duplicate titles')
        
        html = f'<span style="color:{color};font-weight:bold;">{text}</span>'
        if details:
            html += f'<br><small style="color:#666;">({", ".join(details[:2])})</small>'
        
        return format_html(html)
    issues_display.short_description = 'Issues Summary'
    
    def audit_actions(self, obj):
        if not obj.id:
            return '-'
        return format_html(
            '<a class="button" href="{}" style="padding:5px 10px;background:#28a745;color:white;'
            'text-decoration:none;border-radius:3px;">View History</a>',
            reverse('admin:site_audit_site_audithistory_changelist') + f'?audit__id__exact={obj.id}'
        )
    audit_actions.short_description = 'Actions'
    
    def has_add_permission(self, request, obj=None):
        return False


class EmailFilter(admin.SimpleListFilter):
    title = 'User Email'
    parameter_name = 'user_email'

    def lookups(self, request, model_admin):
        emails = Project.objects.values_list('user__email', flat=True).distinct().order_by('user__email')
        return [(email, email) for email in emails if email]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(user__email=self.value())
        return queryset


@admin.register(Project)
class ProjectAdmin(ModelAdmin):
    form = ProjectAdminForm
    list_display = ('domain', 'title', 'user_email', 'active', 'audit_status', 'favicon_url_display', 'created_at', 'updated_at')
    list_filter = ('active', EmailFilter, 'created_at', 'updated_at')
    search_fields = ('domain', 'title', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at', 'favicon_url_display', 'audit_summary')
    list_per_page = 25
    ordering = ('-created_at',)
    autocomplete_fields = ('user',)
    inlines = [PerformancePageInline, SiteAuditInline]
    
    fieldsets = (
        ('Project Information', {
            'fields': ('user', 'domain', 'title', 'active')
        }),
        ('Audit Overview', {
            'fields': ('audit_summary',),
            'description': 'Summary of all audits for this project'
        }),
        ('Favicon', {
            'fields': ('favicon_url_display',),
            'classes': ('collapse',),
            'description': 'Favicons are now served via Google\'s favicon service'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'
    
    def favicon_url_display(self, obj):
        google_url = obj.get_favicon_url()
        cached_url = obj.get_cached_favicon_url()
        return (f'<strong>Cached:</strong> <a href="{cached_url}" target="_blank">View</a><br>'
                f'<strong>Google:</strong> <a href="{google_url}" target="_blank">Direct</a>')
    favicon_url_display.short_description = 'Favicon URLs'
    favicon_url_display.allow_tags = True
    
    def audit_status(self, obj):
        """Display audit status badges in list view"""
        from performance_audit.models import PerformancePage
        from site_audit.models import SiteAudit
        
        badges = []
        
        # Lighthouse audit status
        try:
            performance_page = PerformancePage.objects.get(project=obj)
            if performance_page.last_audit_date:
                badges.append(format_html(
                    '<span style="background:#007bff;color:white;padding:2px 6px;'
                    'border-radius:3px;margin-right:4px;font-size:11px;">🔍 Lighthouse</span>'
                ))
            else:
                badges.append(format_html(
                    '<span style="background:#6c757d;color:white;padding:2px 6px;'
                    'border-radius:3px;margin-right:4px;font-size:11px;">🔍 No Lighthouse</span>'
                ))
        except PerformancePage.DoesNotExist:
            badges.append(format_html(
                '<span style="background:#dc3545;color:white;padding:2px 6px;'
                'border-radius:3px;margin-right:4px;font-size:11px;">❌ Lighthouse</span>'
            ))
        
        # OnPage audit status
        try:
            site_audit = SiteAudit.objects.get(project=obj)
            if site_audit.last_audit_date:
                badges.append(format_html(
                    '<span style="background:#28a745;color:white;padding:2px 6px;'
                    'border-radius:3px;font-size:11px;">📊 OnPage</span>'
                ))
            else:
                badges.append(format_html(
                    '<span style="background:#6c757d;color:white;padding:2px 6px;'
                    'border-radius:3px;font-size:11px;">📊 No OnPage</span>'
                ))
        except SiteAudit.DoesNotExist:
            badges.append(format_html(
                '<span style="background:#dc3545;color:white;padding:2px 6px;'
                'border-radius:3px;font-size:11px;">❌ OnPage</span>'
            ))
        
        return format_html(''.join(badges))
    audit_status.short_description = 'Audits'
    
    def audit_summary(self, obj):
        """Display detailed audit summary in change form"""
        from performance_audit.models import PerformancePage, PerformanceHistory
        from site_audit.models import SiteAudit, OnPagePerformanceHistory
        
        summary = []
        
        # Lighthouse Audit Summary
        try:
            performance_page = PerformancePage.objects.get(project=obj)
            history_count = PerformanceHistory.objects.filter(performance_page=performance_page).count()
            latest = PerformanceHistory.objects.filter(
                performance_page=performance_page,
                status='completed'
            ).order_by('-created_at').first()
            
            summary.append('<div style="margin-bottom:20px;">')
            summary.append('<h4 style="margin:0 0 10px 0;">🔍 Lighthouse Audits</h4>')
            summary.append(f'<p>Total audits run: <strong>{history_count}</strong></p>')
            
            if latest:
                summary.append(f'<p>Last audit: <strong>{latest.created_at.strftime("%Y-%m-%d %H:%M")}</strong></p>')
                summary.append(f'<p>Latest scores: ')
                if latest.performance_score:
                    summary.append(f'Performance: <strong>{latest.performance_score}</strong>, ')
                if latest.seo_score:
                    summary.append(f'SEO: <strong>{latest.seo_score}</strong>, ')
                if latest.accessibility_score:
                    summary.append(f'Accessibility: <strong>{latest.accessibility_score}</strong>')
                summary.append('</p>')
            
            summary.append(f'<a href="{reverse("admin:performance_audit_audithistory_changelist")}?performance_page__id__exact={performance_page.id}" '
                          f'class="button" style="padding:5px 10px;background:#007bff;color:white;'
                          f'text-decoration:none;border-radius:3px;">View Lighthouse History</a>')
            summary.append('</div>')
        except PerformancePage.DoesNotExist:
            summary.append('<div style="margin-bottom:20px;">')
            summary.append('<h4 style="margin:0 0 10px 0;">🔍 Lighthouse Audits</h4>')
            summary.append('<p style="color:#dc3545;">No Lighthouse audits configured yet.</p>')
            summary.append('</div>')
        
        # OnPage Audit Summary
        try:
            site_audit = SiteAudit.objects.get(project=obj)
            history_count = OnPagePerformanceHistory.objects.filter(audit=site_audit).count()
            latest = OnPagePerformanceHistory.objects.filter(
                audit=site_audit,
                status='completed'
            ).order_by('-created_at').first()
            
            summary.append('<div>')
            summary.append('<h4 style="margin:0 0 10px 0;">📊 OnPage Audits (Screaming Frog)</h4>')
            summary.append(f'<p>Max pages to crawl: <strong>{site_audit.max_pages_to_crawl}</strong></p>')
            summary.append(f'<p>Total audits run: <strong>{history_count}</strong></p>')
            
            if latest:
                summary.append(f'<p>Last audit: <strong>{latest.created_at.strftime("%Y-%m-%d %H:%M")}</strong></p>')
                summary.append(f'<p>Pages crawled: <strong>{latest.pages_crawled}</strong></p>')
                summary.append(f'<p>Total issues found: <strong>{latest.total_issues or 0}</strong></p>')
            
            summary.append(f'<a href="{reverse("admin:site_audit_site_audithistory_changelist")}?audit__id__exact={site_audit.id}" '
                          f'class="button" style="padding:5px 10px;background:#28a745;color:white;'
                          f'text-decoration:none;border-radius:3px;">View OnPage History</a>')
            summary.append('</div>')
        except SiteAudit.DoesNotExist:
            summary.append('<div>')
            summary.append('<h4 style="margin:0 0 10px 0;">📊 OnPage Audits</h4>')
            summary.append('<p style="color:#dc3545;">No OnPage audits configured yet.</p>')
            summary.append('</div>')
        
        return format_html(''.join(summary))
    audit_summary.short_description = 'Audit Summary'
