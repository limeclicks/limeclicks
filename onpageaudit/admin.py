from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from datetime import timedelta
from .models import ScreamingFrogLicense, OnPageAudit, OnPageAuditHistory, OnPageIssue
from .tasks import run_manual_onpage_audit, validate_screaming_frog_license, check_scheduled_onpage_audits


@admin.register(ScreamingFrogLicense)
class ScreamingFrogLicenseAdmin(admin.ModelAdmin):
    list_display = [
        'license_status_display',
        'license_type_display', 
        'expiry_status',
        'max_urls',
        'last_validated',
        'actions_display'
    ]
    
    readonly_fields = [
        'license_status',
        'license_type',
        'expiry_date',
        'last_validated',
        'max_urls',
        'license_holder',
        'license_email',
        'created_at',
        'updated_at',
        'license_info_display'
    ]
    
    fieldsets = (
        ('License Configuration', {
            'fields': ('license_key',),
            'description': 'Enter your Screaming Frog license key from environment variable SCREAMING_FROG_LICENSE'
        }),
        ('License Information', {
            'fields': (
                'license_info_display',
                'license_status',
                'license_type',
                'max_urls',
                'expiry_date',
                'last_validated'
            )
        }),
        ('License Holder', {
            'fields': ('license_holder', 'license_email'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def has_add_permission(self, request):
        # Only allow one license record
        return not ScreamingFrogLicense.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def license_status_display(self, obj):
        if obj.license_status == 'valid':
            color = 'green'
            icon = '✅'
        elif obj.license_status == 'expired':
            color = 'red'
            icon = '❌'
        else:
            color = 'orange'
            icon = '⚠️'
        
        return format_html(
            '<span style="color: {};">{} {}</span>',
            color,
            icon,
            obj.get_license_status_display()
        )
    license_status_display.short_description = 'Status'
    
    def license_type_display(self, obj):
        if obj.license_type == 'paid':
            return format_html('<span style="color: green;">💎 Paid (Unlimited)</span>')
        else:
            return format_html('<span style="color: gray;">🆓 Free (500 URLs)</span>')
    license_type_display.short_description = 'Type'
    
    def expiry_status(self, obj):
        if not obj.expiry_date:
            return 'No expiry date'
        
        days_until = obj.days_until_expiry()
        if days_until is None:
            return 'No expiry date'
        elif days_until < 0:
            return format_html(
                '<span style="color: red;">Expired {} days ago</span>',
                abs(days_until)
            )
        elif days_until <= 7:
            return format_html(
                '<span style="color: red;">⚠️ Expires in {} days</span>',
                days_until
            )
        elif days_until <= 30:
            return format_html(
                '<span style="color: orange;">Expires in {} days</span>',
                days_until
            )
        else:
            return format_html(
                '<span style="color: green;">Valid for {} days</span>',
                days_until
            )
    expiry_status.short_description = 'Expiry Status'
    
    def license_info_display(self, obj):
        info_html = f"""
        <div style="background: #f0f0f0; padding: 10px; border-radius: 5px;">
            <h4 style="margin-top: 0;">License Overview</h4>
            <p><strong>Status:</strong> {obj.get_license_status_display()}</p>
            <p><strong>Type:</strong> {obj.get_license_type_display()}</p>
            <p><strong>Max URLs:</strong> {obj.max_urls}</p>
            <p><strong>Expiry Date:</strong> {obj.expiry_date or 'N/A'}</p>
            <p><strong>Days Until Expiry:</strong> {obj.days_until_expiry() or 'N/A'}</p>
            <p><strong>Last Validated:</strong> {obj.last_validated or 'Never'}</p>
        </div>
        """
        return format_html(info_html)
    license_info_display.short_description = 'License Overview'
    
    def actions_display(self, obj):
        return format_html(
            '<a class="button" href="{}">Validate Now</a>',
            reverse('admin:onpageaudit_screamingfroglicense_validate', args=[obj.pk])
        )
    actions_display.short_description = 'Actions'
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:pk>/validate/',
                self.admin_site.admin_view(self.validate_license_view),
                name='onpageaudit_screamingfroglicense_validate'
            ),
        ]
        return custom_urls + urls
    
    def validate_license_view(self, request, pk):
        from django.shortcuts import redirect
        license_obj = self.get_object(request, pk)
        
        if license_obj:
            result = validate_screaming_frog_license.delay()
            if result:
                messages.success(request, 'License validation started')
            else:
                messages.error(request, 'Failed to start license validation')
        
        return redirect('admin:onpageaudit_screamingfroglicense_changelist')


@admin.register(OnPageAudit)
class OnPageAuditAdmin(admin.ModelAdmin):
    list_display = [
        'project_domain',
        'issues_badge',
        'last_audit_date',
        'next_scheduled_audit',
        'rate_limit_status',
        'is_audit_enabled',
        'audit_actions'
    ]
    
    list_filter = ['is_audit_enabled', 'last_audit_date']
    search_fields = ['project__domain']
    
    readonly_fields = [
        'project',
        'last_audit_date',
        'last_automatic_audit',
        'last_manual_audit',
        'broken_links_count',
        'redirect_chains_count',
        'missing_titles_count',
        'duplicate_titles_count',
        'missing_meta_descriptions_count',
        'duplicate_meta_descriptions_count',
        'blocked_by_robots_count',
        'missing_hreflang_count',
        'duplicate_content_count',
        'spelling_errors_count',
        'total_issues_count',
        'average_page_size_kb',
        'average_load_time_ms',
        'total_pages_crawled',
        'created_at',
        'updated_at',
        'issue_summary_display'
    ]
    
    fieldsets = (
        ('Project Information', {
            'fields': ('project',)
        }),
        ('Audit Configuration', {
            'fields': (
                'is_audit_enabled',
                'audit_frequency_days',
                'manual_audit_frequency_days',
                'max_pages_to_crawl',
                'next_scheduled_audit'
            )
        }),
        ('Rate Limiting', {
            'fields': (
                'last_automatic_audit',
                'last_manual_audit'
            )
        }),
        ('Latest Audit Summary', {
            'fields': (
                'last_audit_date',
                'total_pages_crawled',
                'issue_summary_display'
            )
        }),
        ('Issue Counts', {
            'fields': (
                'total_issues_count',
                'broken_links_count',
                'redirect_chains_count',
                'missing_titles_count',
                'duplicate_titles_count',
                'missing_meta_descriptions_count',
                'duplicate_meta_descriptions_count',
                'blocked_by_robots_count',
                'missing_hreflang_count',
                'duplicate_content_count',
                'spelling_errors_count'
            ),
            'classes': ('collapse',)
        }),
        ('Performance Metrics', {
            'fields': (
                'average_page_size_kb',
                'average_load_time_ms'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def project_domain(self, obj):
        return obj.project.domain
    project_domain.short_description = 'Project'
    project_domain.admin_order_field = 'project__domain'
    
    def issues_badge(self, obj):
        if obj.total_issues_count == 0:
            color = 'green'
            text = '✅ No issues'
        elif obj.total_issues_count < 10:
            color = 'orange'
            text = f'⚠️ {obj.total_issues_count} issues'
        else:
            color = 'red'
            text = f'❌ {obj.total_issues_count} issues'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            text
        )
    issues_badge.short_description = 'Issues'
    
    def rate_limit_status(self, obj):
        items = []
        
        # Automatic audit status
        if obj.can_run_automatic_audit():
            items.append(format_html('<span style="color: green;">✅ Auto ready</span>'))
        else:
            days_until = (obj.last_automatic_audit + timedelta(days=obj.audit_frequency_days) - timezone.now()).days
            items.append(format_html('<span style="color: gray;">Auto in {} days</span>', days_until))
        
        # Manual audit status
        if obj.can_run_manual_audit():
            items.append(format_html('<span style="color: green;">✅ Manual ready</span>'))
        else:
            days_until = (obj.last_manual_audit + timedelta(days=obj.manual_audit_frequency_days) - timezone.now()).days
            items.append(format_html('<span style="color: gray;">Manual in {} days</span>', days_until))
        
        return format_html('<br>'.join(items))
    rate_limit_status.short_description = 'Rate Limits'
    
    def issue_summary_display(self, obj):
        if obj.total_issues_count == 0:
            return format_html('<p style="color: green;">No issues found in last audit</p>')
        
        html = f"""
        <div style="background: #f9f9f9; padding: 10px; border-radius: 5px;">
            <h4 style="margin-top: 0;">Issue Summary ({obj.total_issues_count} total)</h4>
            <table style="width: 100%;">
                <tr>
                    <td>🔗 Broken Links:</td><td style="text-align: right;"><strong>{obj.broken_links_count}</strong></td>
                    <td style="padding-left: 20px;">📝 Missing Titles:</td><td style="text-align: right;"><strong>{obj.missing_titles_count}</strong></td>
                </tr>
                <tr>
                    <td>↪️ Redirect Chains:</td><td style="text-align: right;"><strong>{obj.redirect_chains_count}</strong></td>
                    <td style="padding-left: 20px;">📋 Duplicate Titles:</td><td style="text-align: right;"><strong>{obj.duplicate_titles_count}</strong></td>
                </tr>
                <tr>
                    <td>📄 Missing Meta Desc:</td><td style="text-align: right;"><strong>{obj.missing_meta_descriptions_count}</strong></td>
                    <td style="padding-left: 20px;">📋 Duplicate Meta Desc:</td><td style="text-align: right;"><strong>{obj.duplicate_meta_descriptions_count}</strong></td>
                </tr>
                <tr>
                    <td>🚫 Blocked by Robots:</td><td style="text-align: right;"><strong>{obj.blocked_by_robots_count}</strong></td>
                    <td style="padding-left: 20px;">🌐 Missing Hreflang:</td><td style="text-align: right;"><strong>{obj.missing_hreflang_count}</strong></td>
                </tr>
                <tr>
                    <td>📑 Duplicate Content:</td><td style="text-align: right;"><strong>{obj.duplicate_content_count}</strong></td>
                    <td style="padding-left: 20px;">✏️ Spelling Errors:</td><td style="text-align: right;"><strong>{obj.spelling_errors_count}</strong></td>
                </tr>
            </table>
            <p style="margin-top: 10px;"><strong>Pages Crawled:</strong> {obj.total_pages_crawled}</p>
            <p><strong>Avg Page Size:</strong> {obj.average_page_size_kb or 'N/A'} KB</p>
            <p><strong>Avg Load Time:</strong> {obj.average_load_time_ms or 'N/A'} ms</p>
        </div>
        """
        return format_html(html)
    issue_summary_display.short_description = 'Issue Details'
    
    def audit_actions(self, obj):
        buttons = []
        
        # View History button
        buttons.append(format_html(
            '<a class="button" href="{}">View History</a>',
            reverse('admin:onpageaudit_onpageaudithistory_changelist') + f'?audit__id__exact={obj.id}'
        ))
        
        # Run Manual button (if allowed)
        if obj.can_run_manual_audit():
            buttons.append(format_html(
                '<a class="button" href="{}">Run Manual</a>',
                reverse('admin:onpageaudit_onpageaudit_run_manual', args=[obj.pk])
            ))
        
        return format_html(' '.join(buttons))
    audit_actions.short_description = 'Actions'
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:pk>/run-manual/',
                self.admin_site.admin_view(self.run_manual_audit_view),
                name='onpageaudit_onpageaudit_run_manual'
            ),
        ]
        return custom_urls + urls
    
    def run_manual_audit_view(self, request, pk):
        from django.shortcuts import redirect
        audit = self.get_object(request, pk)
        
        if audit:
            result = run_manual_onpage_audit.delay(audit.id)
            if result:
                messages.success(request, f'Manual on-page audit started for {audit.project.domain}')
            else:
                messages.error(request, 'Failed to start manual audit')
        
        return redirect('admin:onpageaudit_onpageaudit_changelist')


@admin.register(OnPageAuditHistory)
class OnPageAuditHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'audit_id_short',
        'project_domain',
        'trigger_type',
        'status_badge',
        'issues_summary',
        'comparison_badge',
        'created_at',
        'duration',
        'view_reports'
    ]
    
    list_filter = ['status', 'trigger_type', 'created_at']
    search_fields = ['id', 'audit__project__domain']
    date_hierarchy = 'created_at'
    
    readonly_fields = [
        'id',
        'audit',
        'status',
        'trigger_type',
        'created_at',
        'started_at',
        'completed_at',
        'pages_crawled',
        'max_pages_limit',
        'crawl_depth',
        'summary_data',
        'issues_summary',
        'issues_fixed',
        'issues_introduced',
        'total_issues',
        'error_message',
        'retry_count',
        'comparison_display'
    ]
    
    fieldsets = (
        ('Audit Information', {
            'fields': (
                'id',
                'audit',
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
        ('Crawl Details', {
            'fields': (
                'pages_crawled',
                'max_pages_limit',
                'crawl_depth'
            )
        }),
        ('Results', {
            'fields': (
                'total_issues',
                'issues_fixed',
                'issues_introduced',
                'summary_data',
                'issues_summary',
                'comparison_display'
            )
        }),
        ('Reports', {
            'fields': (
                'full_report_json',
                'crawl_report_csv',
                'issues_report_json'
            )
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
        return obj.audit.project.domain
    project_domain.short_description = 'Project'
    
    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'running': 'blue',
            'completed': 'green',
            'failed': 'red'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def issues_summary(self, obj):
        if obj.status != 'completed':
            return '-'
        
        return format_html(
            '<span title="{} pages crawled">{} issues</span>',
            obj.pages_crawled,
            obj.total_issues
        )
    issues_summary.short_description = 'Issues'
    
    def comparison_badge(self, obj):
        if obj.status != 'completed':
            return '-'
        
        if obj.issues_fixed == 0 and obj.issues_introduced == 0:
            return format_html('<span style="color: gray;">No change</span>')
        
        badges = []
        if obj.issues_fixed > 0:
            badges.append(format_html(
                '<span style="color: green;">✅ {} fixed</span>',
                obj.issues_fixed
            ))
        if obj.issues_introduced > 0:
            badges.append(format_html(
                '<span style="color: red;">❌ {} new</span>',
                obj.issues_introduced
            ))
        
        return format_html('<br>'.join(badges))
    comparison_badge.short_description = 'Changes'
    
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
        
        if obj.full_report_json:
            buttons.append(format_html(
                '<a class="button" href="{}" target="_blank">JSON</a>',
                obj.full_report_json.url
            ))
        
        if obj.issues_report_json:
            buttons.append(format_html(
                '<a class="button" href="{}" target="_blank">Issues</a>',
                obj.issues_report_json.url
            ))
        
        # View issues link
        buttons.append(format_html(
            '<a class="button" href="{}">View Issues</a>',
            reverse('admin:onpageaudit_onpageissue_changelist') + f'?audit_history__id__exact={obj.id}'
        ))
        
        return format_html(' '.join(buttons)) if buttons else '-'
    view_reports.short_description = 'Reports'
    
    def comparison_display(self, obj):
        comparison = obj.compare_with_previous()
        if not comparison:
            return 'No previous audit to compare'
        
        html = f"""
        <div style="background: #f9f9f9; padding: 10px; border-radius: 5px;">
            <h4>Comparison with Previous Audit</h4>
            <p><strong>Previous:</strong> {comparison['previous_date']}</p>
            <p><strong>Current:</strong> {comparison['current_date']}</p>
            
            <h5>Fixed Issues ({len(comparison['fixed_issues'])})</h5>
            <ul>
        """
        
        for item in comparison['fixed_issues']:
            html += f"<li>{item['type']}: {item['fixed']} fixed</li>"
        
        html += f"""
            </ul>
            
            <h5>New Issues ({len(comparison['new_issues'])})</h5>
            <ul>
        """
        
        for item in comparison['new_issues']:
            html += f"<li>{item['type']}: {item['new']} new</li>"
        
        html += """
            </ul>
        </div>
        """
        
        return format_html(html)
    comparison_display.short_description = 'Comparison with Previous'
    
    def has_add_permission(self, request):
        return False


@admin.register(OnPageIssue)
class OnPageIssueAdmin(admin.ModelAdmin):
    list_display = [
        'issue_type',
        'severity_badge',
        'page_url_short',
        'audit_project',
        'created_at'
    ]
    
    list_filter = ['issue_type', 'severity', 'created_at']
    search_fields = ['page_url', 'description', 'audit_history__audit__project__domain']
    
    readonly_fields = [
        'audit_history',
        'issue_type',
        'severity',
        'page_url',
        'page_title',
        'description',
        'recommendation',
        'status_code',
        'response_time_ms',
        'page_size_bytes',
        'duplicate_urls',
        'similarity_score',
        'source_url',
        'anchor_text',
        'created_at'
    ]
    
    def severity_badge(self, obj):
        colors = {
            'critical': 'red',
            'high': 'orange',
            'medium': 'yellow',
            'low': 'gray',
            'info': 'blue'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.severity, 'gray'),
            obj.get_severity_display()
        )
    severity_badge.short_description = 'Severity'
    
    def page_url_short(self, obj):
        url = obj.page_url
        if len(url) > 50:
            url = url[:50] + '...'
        return format_html(
            '<a href="{}" target="_blank" title="{}">{}</a>',
            obj.page_url,
            obj.page_url,
            url
        )
    page_url_short.short_description = 'Page URL'
    
    def audit_project(self, obj):
        return obj.audit_history.audit.project.domain
    audit_project.short_description = 'Project'
    
    def has_add_permission(self, request):
        return False
