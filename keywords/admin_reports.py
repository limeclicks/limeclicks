"""
Django Admin configuration for Keyword Reports
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import redirect
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone

from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.filters.admin import RangeNumericFilter, RangeDateFilter, ChoicesDropdownFilter
from unfold.decorators import display

from .models_reports import KeywordReport, ReportSchedule
from .tasks_reports import generate_keyword_report


class KeywordInline(TabularInline):
    """Inline for displaying keywords in report"""
    model = KeywordReport.keywords.through
    extra = 0
    can_delete = True
    verbose_name = "Included Keyword"
    verbose_name_plural = "Included Keywords"
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "keyword" and hasattr(request, '_obj_'):
            kwargs["queryset"] = db_field.related_model.objects.filter(
                project=request._obj_.project
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(KeywordReport)
class KeywordReportAdmin(ModelAdmin):
    """Admin for Keyword Reports"""
    
    list_display = (
        'id',
        'project_link',
        'name',
        'date_range_display',
        'status_badge',
        'format_display',
        'file_sizes_display',
        'created_by_display',
        'created_at',
        'actions_display'
    )
    
    list_filter = (
        ('status', ChoicesDropdownFilter),
        ('report_format', ChoicesDropdownFilter),
        ('created_at', RangeDateFilter),
        ('start_date', RangeDateFilter),
        ('end_date', RangeDateFilter),
        'send_email_notification',
        'email_sent',
    )
    
    search_fields = (
        'name',
        'project__domain',
        'created_by__username',
        'created_by__email',
    )
    
    readonly_fields = (
        'project',
        'status',
        'processing_started_at',
        'processing_completed_at',
        'processing_duration_seconds',
        'duration_display',
        'csv_file_path',
        'pdf_file_path',
        'csv_file_size',
        'pdf_file_size',
        'email_sent',
        'email_sent_at',
        'download_count',
        'last_downloaded_at',
        'created_at',
        'updated_at',
        'error_message',
    )
    
    fieldsets = (
        ('Report Configuration', {
            'fields': (
                'project',
                'name',
                ('start_date', 'end_date'),
                'report_format',
            )
        }),
        ('Report Settings', {
            'fields': (
                'fill_missing_ranks',
                'include_competitors',
                'include_graphs',
                ('include_tags', 'exclude_tags'),
            )
        }),
        ('Status', {
            'fields': (
                'status',
                'error_message',
                ('processing_started_at', 'processing_completed_at'),
                'duration_display',
            )
        }),
        ('Files', {
            'fields': (
                ('csv_file_path', 'csv_file_size'),
                ('pdf_file_path', 'pdf_file_size'),
            ),
            'classes': ('collapse',)
        }),
        ('Email Notification', {
            'fields': (
                'send_email_notification',
                ('email_sent', 'email_sent_at'),
            )
        }),
        ('Tracking', {
            'fields': (
                'created_by',
                ('download_count', 'last_downloaded_at'),
                ('created_at', 'updated_at'),
            )
        }),
    )
    
    inlines = [KeywordInline]
    
    ordering = ['-created_at']
    list_per_page = 25
    
    def get_form(self, request, obj=None, **kwargs):
        # Store obj on request for inline
        request._obj_ = obj
        return super().get_form(request, obj, **kwargs)
    
    @display(description="Project")
    def project_link(self, obj):
        """Link to project"""
        if not obj.project:
            return "-"
        
        url = reverse('admin:project_project_change', args=[obj.project.id])
        return format_html(
            '<a href="{}" style="color: #3b82f6;">{}</a>',
            url, obj.project.domain
        )
    
    @display(description="Date Range")
    def date_range_display(self, obj):
        """Display date range"""
        return format_html(
            '{} → {}',
            obj.start_date.strftime('%b %d'),
            obj.end_date.strftime('%b %d, %Y')
        )
    
    @display(description="Status")
    def status_badge(self, obj):
        """Display status as badge"""
        color_map = {
            'pending': '#fbbf24',  # yellow
            'processing': '#3b82f6',  # blue
            'completed': '#10b981',  # green
            'failed': '#ef4444',  # red
        }
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px; font-weight: 500;">{}</span>',
            color_map.get(obj.status, '#6b7280'),
            obj.get_status_display().upper()
        )
    
    @display(description="Format")
    def format_display(self, obj):
        """Display report format"""
        icons = {
            'csv': '📊',
            'pdf': '📄',
            'both': '📊📄'
        }
        return format_html(
            '{} {}',
            icons.get(obj.report_format, ''),
            obj.get_report_format_display()
        )
    
    @display(description="File Sizes")
    def file_sizes_display(self, obj):
        """Display file sizes"""
        sizes = []
        
        if obj.csv_file_size > 0:
            sizes.append(f"CSV: {obj.get_file_size_display('csv')}")
        
        if obj.pdf_file_size > 0:
            sizes.append(f"PDF: {obj.get_file_size_display('pdf')}")
        
        if sizes:
            return format_html('<br>'.join(sizes))
        return "-"
    
    @display(description="Created By")
    def created_by_display(self, obj):
        """Display creator"""
        if not obj.created_by:
            return "-"
        
        return format_html(
            '{}',
            obj.created_by.get_full_name() or obj.created_by.username
        )
    
    @display(description="Duration")
    def duration_display(self, obj):
        """Display processing duration"""
        return obj.get_duration_display()
    
    @display(description="Actions")
    def actions_display(self, obj):
        """Display action buttons"""
        actions = []
        
        if obj.status == 'completed':
            # Download links
            if obj.csv_file_path:
                actions.append(
                    f'<a href="#" onclick="alert(\'CSV: {obj.csv_file_path}\'); return false;" '
                    f'style="color: #3b82f6; margin-right: 10px;">📥 CSV</a>'
                )
            
            if obj.pdf_file_path:
                actions.append(
                    f'<a href="#" onclick="alert(\'PDF: {obj.pdf_file_path}\'); return false;" '
                    f'style="color: #3b82f6; margin-right: 10px;">📥 PDF</a>'
                )
        
        elif obj.status == 'failed':
            # Regenerate button
            regenerate_url = reverse('admin:keywords_keywordreport_regenerate', args=[obj.id])
            actions.append(
                f'<a href="{regenerate_url}" style="color: #ef4444;">🔄 Retry</a>'
            )
        
        elif obj.status == 'pending':
            # Generate button
            generate_url = reverse('admin:keywords_keywordreport_generate', args=[obj.id])
            actions.append(
                f'<a href="{generate_url}" style="color: #10b981;">▶️ Generate</a>'
            )
        
        if actions:
            return format_html(' '.join(actions))
        return "-"
    
    def get_urls(self):
        """Add custom URLs"""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:report_id>/generate/',
                self.admin_site.admin_view(self.generate_report_view),
                name='keywords_keywordreport_generate'
            ),
            path(
                '<int:report_id>/regenerate/',
                self.admin_site.admin_view(self.regenerate_report_view),
                name='keywords_keywordreport_regenerate'
            ),
        ]
        return custom_urls + urls
    
    def generate_report_view(self, request, report_id):
        """Generate report manually"""
        try:
            report = KeywordReport.objects.get(id=report_id)
            
            if report.status not in ['pending', 'failed']:
                messages.warning(request, f"Report is already {report.get_status_display()}")
            else:
                # Queue generation task
                generate_keyword_report.delay(report.id)
                messages.success(request, f"Report generation started for '{report.name}'")
            
        except KeywordReport.DoesNotExist:
            messages.error(request, "Report not found")
        except Exception as e:
            messages.error(request, f"Error starting generation: {e}")
        
        return redirect('admin:keywords_keywordreport_changelist')
    
    def regenerate_report_view(self, request, report_id):
        """Regenerate failed report"""
        try:
            report = KeywordReport.objects.get(id=report_id)
            
            # Reset status
            report.status = 'pending'
            report.error_message = None
            report.processing_started_at = None
            report.processing_completed_at = None
            report.save()
            
            # Queue generation task
            generate_keyword_report.delay(report.id)
            messages.success(request, f"Report regeneration started for '{report.name}'")
            
        except KeywordReport.DoesNotExist:
            messages.error(request, "Report not found")
        except Exception as e:
            messages.error(request, f"Error starting regeneration: {e}")
        
        return redirect('admin:keywords_keywordreport_changelist')
    
    def has_add_permission(self, request):
        """Disable add in admin (use views instead)"""
        return False


@admin.register(ReportSchedule)
class ReportScheduleAdmin(ModelAdmin):
    """Admin for Report Schedules"""
    
    list_display = (
        'id',
        'project_link',
        'name',
        'frequency_display',
        'schedule_display',
        'active_badge',
        'last_run_display',
        'next_run_display',
        'created_by_display',
    )
    
    list_filter = (
        'is_active',
        ('frequency', ChoicesDropdownFilter),
        ('created_at', RangeDateFilter),
        ('next_run_at', RangeDateFilter),
    )
    
    search_fields = (
        'name',
        'project__domain',
        'created_by__username',
        'created_by__email',
    )
    
    readonly_fields = (
        'last_run_at',
        'next_run_at',
        'last_report',
        'created_at',
        'updated_at',
    )
    
    fieldsets = (
        ('Schedule Configuration', {
            'fields': (
                'project',
                'name',
                'is_active',
            )
        }),
        ('Schedule Timing', {
            'fields': (
                'frequency',
                'day_of_week',
                'day_of_month',
                'time_of_day',
                'report_period_days',
            )
        }),
        ('Report Settings', {
            'fields': (
                'report_format',
                'fill_missing_ranks',
                'include_competitors',
                'include_graphs',
                ('include_tags', 'exclude_tags'),
            )
        }),
        ('Email Configuration', {
            'fields': (
                'email_recipients',
            )
        }),
        ('Execution Info', {
            'fields': (
                ('last_run_at', 'next_run_at'),
                'last_report',
                'created_by',
                ('created_at', 'updated_at'),
            ),
            'classes': ('collapse',)
        }),
    )
    
    ordering = ['-created_at']
    list_per_page = 25
    
    @display(description="Project")
    def project_link(self, obj):
        """Link to project"""
        if not obj.project:
            return "-"
        
        url = reverse('admin:project_project_change', args=[obj.project.id])
        return format_html(
            '<a href="{}" style="color: #3b82f6;">{}</a>',
            url, obj.project.domain
        )
    
    @display(description="Frequency")
    def frequency_display(self, obj):
        """Display frequency with icon"""
        icons = {
            'daily': '📅',
            'weekly': '📆',
            'biweekly': '📆',
            'monthly': '🗓️'
        }
        return format_html(
            '{} {}',
            icons.get(obj.frequency, ''),
            obj.get_frequency_display()
        )
    
    @display(description="Schedule")
    def schedule_display(self, obj):
        """Display schedule details"""
        time_str = obj.time_of_day.strftime('%I:%M %p')
        
        if obj.frequency == 'daily':
            return f"Daily at {time_str}"
        elif obj.frequency in ['weekly', 'biweekly']:
            day_name = dict(ReportSchedule.DAY_OF_WEEK_CHOICES).get(obj.day_of_week, 'Unknown')
            prefix = "Every" if obj.frequency == 'weekly' else "Every other"
            return f"{prefix} {day_name} at {time_str}"
        elif obj.frequency == 'monthly':
            day = obj.day_of_month or 1
            suffix = 'st' if day == 1 else 'nd' if day == 2 else 'rd' if day == 3 else 'th'
            return f"Monthly on {day}{suffix} at {time_str}"
        
        return "-"
    
    @display(description="Active")
    def active_badge(self, obj):
        """Display active status as badge"""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #10b981; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px; font-weight: 500;">ACTIVE</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #6b7280; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px; font-weight: 500;">INACTIVE</span>'
            )
    
    @display(description="Last Run")
    def last_run_display(self, obj):
        """Display last run time"""
        if not obj.last_run_at:
            return "-"
        
        # Calculate time ago
        delta = timezone.now() - obj.last_run_at
        
        if delta.days > 0:
            return f"{delta.days}d ago"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours}h ago"
        else:
            minutes = delta.seconds // 60
            return f"{minutes}m ago"
    
    @display(description="Next Run")
    def next_run_display(self, obj):
        """Display next run time"""
        if not obj.next_run_at:
            return "-"
        
        if not obj.is_active:
            return format_html('<span style="color: #6b7280;">Inactive</span>')
        
        # Calculate time until
        delta = obj.next_run_at - timezone.now()
        
        if delta.total_seconds() < 0:
            return format_html('<span style="color: #ef4444;">Overdue</span>')
        elif delta.days > 0:
            return f"In {delta.days}d"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"In {hours}h"
        else:
            minutes = delta.seconds // 60
            return f"In {minutes}m"
    
    @display(description="Created By")
    def created_by_display(self, obj):
        """Display creator"""
        if not obj.created_by:
            return "-"
        
        return obj.created_by.get_full_name() or obj.created_by.username
    
    def save_model(self, request, obj, form, change):
        """Calculate next run on save"""
        if not change:  # New object
            obj.created_by = request.user
        
        super().save_model(request, obj, form, change)
        
        # Calculate next run time
        if obj.is_active and not obj.next_run_at:
            obj.calculate_next_run()
            obj.save(update_fields=['next_run_at'])