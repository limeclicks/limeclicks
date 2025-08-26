from django.db import models
from django.contrib.postgres.fields import JSONField
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from limeclicks.storage_backends import AuditJSONStorage, AuditHTMLStorage
import uuid
from datetime import timedelta
from common.models import BaseAuditHistory, BaseAuditModel


class PerformancePage(models.Model):
    """Main model for audit pages associated with projects"""
    
    project = models.OneToOneField(
        'project.Project',
        on_delete=models.CASCADE,
        related_name='performance_page'
    )
    
    page_url = models.URLField(
        max_length=500,
        help_text="URL of the page to audit (defaults to project domain home page)"
    )
    
    # Latest audit summary data
    last_audit_date = models.DateTimeField(null=True, blank=True)
    next_scheduled_audit = models.DateTimeField(null=True, blank=True)
    
    # Latest scores (0-100)
    performance_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    accessibility_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    best_practices_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    seo_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    pwa_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Audit settings
    audit_frequency_days = models.IntegerField(
        default=30,
        help_text="Days between automatic audits"
    )
    is_audit_enabled = models.BooleanField(
        default=True,
        help_text="Enable/disable automatic audits for this page"
    )
    
    # Rate limiting
    last_manual_audit = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'performance_pages'
        verbose_name = 'Audit Page'
        verbose_name_plural = 'Audit Pages'
        indexes = [
            models.Index(fields=['next_scheduled_audit']),
            models.Index(fields=['is_audit_enabled', 'next_scheduled_audit']),
        ]
    
    def __str__(self):
        return f"Audit Page for {self.project.domain}"
    
    def save(self, *args, **kwargs):
        # Set default page URL if not provided
        if not self.page_url and self.project:
            # Ensure domain has protocol
            domain = self.project.domain
            if not domain.startswith(('http://', 'https://')):
                domain = f'https://{domain}'
            self.page_url = domain
        
        # Schedule next audit if this is the first save
        if not self.pk and self.is_audit_enabled:
            self.next_scheduled_audit = timezone.now()
        
        super().save(*args, **kwargs)
    
    def can_run_manual_audit(self):
        """Check if manual audit can be run (rate limited to once per day)"""
        if not self.last_manual_audit:
            return True
        time_since_last = timezone.now() - self.last_manual_audit
        return time_since_last >= timedelta(days=1)
    
    def schedule_next_audit(self):
        """Schedule the next automatic audit"""
        if self.is_audit_enabled:
            self.next_scheduled_audit = timezone.now() + timedelta(days=self.audit_frequency_days)
            self.save(update_fields=['next_scheduled_audit'])
    
    def update_from_audit_results(self, performance_history):
        """Update summary scores from latest audit - uses mobile scores as primary"""
        if performance_history and performance_history.status == 'completed':
            self.last_audit_date = performance_history.completed_at
            # Use mobile scores as the primary display scores (mobile-first approach)
            self.performance_score = performance_history.mobile_performance_score
            self.accessibility_score = performance_history.mobile_accessibility_score
            self.best_practices_score = performance_history.mobile_best_practices_score
            self.seo_score = performance_history.mobile_seo_score
            self.pwa_score = performance_history.mobile_pwa_score
            self.save()


class PerformanceHistory(BaseAuditHistory):
    """History of all audits for tracking and comparison - stores both mobile and desktop results"""
    
    performance_page = models.ForeignKey(
        PerformancePage,
        on_delete=models.CASCADE,
        related_name='performance_history'
    )
    
    # Mobile Scores (0-100)
    mobile_performance_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    mobile_accessibility_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    mobile_best_practices_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    mobile_seo_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    mobile_pwa_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Desktop Scores (0-100)
    desktop_performance_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    desktop_accessibility_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    desktop_best_practices_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    desktop_seo_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    desktop_pwa_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Mobile Key metrics
    mobile_first_contentful_paint = models.FloatField(null=True, blank=True, help_text="FCP in seconds")
    mobile_largest_contentful_paint = models.FloatField(null=True, blank=True, help_text="LCP in seconds")
    mobile_time_to_interactive = models.FloatField(null=True, blank=True, help_text="TTI in seconds")
    mobile_speed_index = models.FloatField(null=True, blank=True, help_text="Speed Index in seconds")
    mobile_total_blocking_time = models.FloatField(null=True, blank=True, help_text="TBT in milliseconds")
    mobile_cumulative_layout_shift = models.FloatField(null=True, blank=True, help_text="CLS score")
    
    # Desktop Key metrics
    desktop_first_contentful_paint = models.FloatField(null=True, blank=True, help_text="FCP in seconds")
    desktop_largest_contentful_paint = models.FloatField(null=True, blank=True, help_text="LCP in seconds")
    desktop_time_to_interactive = models.FloatField(null=True, blank=True, help_text="TTI in seconds")
    desktop_speed_index = models.FloatField(null=True, blank=True, help_text="Speed Index in seconds")
    desktop_total_blocking_time = models.FloatField(null=True, blank=True, help_text="TBT in milliseconds")
    desktop_cumulative_layout_shift = models.FloatField(null=True, blank=True, help_text="CLS score")
    
    # Mobile Additional Web Vitals
    mobile_interaction_to_next_paint = models.FloatField(null=True, blank=True, help_text="INP in milliseconds")
    mobile_first_input_delay = models.FloatField(null=True, blank=True, help_text="FID in milliseconds")
    mobile_time_to_first_byte = models.FloatField(null=True, blank=True, help_text="TTFB in milliseconds")
    
    # Desktop Additional Web Vitals
    desktop_interaction_to_next_paint = models.FloatField(null=True, blank=True, help_text="INP in milliseconds")
    desktop_first_input_delay = models.FloatField(null=True, blank=True, help_text="FID in milliseconds")
    desktop_time_to_first_byte = models.FloatField(null=True, blank=True, help_text="TTFB in milliseconds")
    
    # Overall scores (average of all scores per device)
    mobile_overall_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Average of all mobile category scores"
    )
    desktop_overall_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Average of all desktop category scores"
    )
    
    # Mobile Error tracking
    mobile_js_errors = models.JSONField(default=list, blank=True, help_text="JavaScript errors found on mobile")
    mobile_css_errors = models.JSONField(default=list, blank=True, help_text="CSS errors found on mobile")
    mobile_console_errors = models.JSONField(default=list, blank=True, help_text="Console errors found on mobile")
    mobile_network_errors = models.JSONField(default=list, blank=True, help_text="Network/resource errors found on mobile")
    
    # Desktop Error tracking
    desktop_js_errors = models.JSONField(default=list, blank=True, help_text="JavaScript errors found on desktop")
    desktop_css_errors = models.JSONField(default=list, blank=True, help_text="CSS errors found on desktop")
    desktop_console_errors = models.JSONField(default=list, blank=True, help_text="Console errors found on desktop")
    desktop_network_errors = models.JSONField(default=list, blank=True, help_text="Network/resource errors found on desktop")
    
    # Storage - separate files for mobile and desktop
    mobile_json_report = models.FileField(
        upload_to='',  # Will be handled by storage backend
        storage=AuditJSONStorage(),
        null=True,
        blank=True,
        help_text="Mobile Lighthouse JSON report"
    )
    mobile_html_report = models.FileField(
        upload_to='',  # Will be handled by storage backend
        storage=AuditHTMLStorage(),
        null=True,
        blank=True,
        help_text="Mobile HTML report for viewing"
    )
    desktop_json_report = models.FileField(
        upload_to='',  # Will be handled by storage backend
        storage=AuditJSONStorage(),
        null=True,
        blank=True,
        help_text="Desktop Lighthouse JSON report"
    )
    desktop_html_report = models.FileField(
        upload_to='',  # Will be handled by storage backend
        storage=AuditHTMLStorage(),
        null=True,
        blank=True,
        help_text="Desktop HTML report for viewing"
    )
    consolidated_error_report = models.FileField(
        upload_to='',  # Will be handled by storage backend
        storage=AuditJSONStorage(),
        null=True,
        blank=True,
        help_text="Consolidated error report JSON for both devices"
    )
    
    
    class Meta:
        db_table = 'performance_history'
        verbose_name = 'Audit History'
        verbose_name_plural = 'Audit Histories'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['performance_page', '-created_at']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"Audit {self.id} - {self.performance_page.project.domain} - {self.created_at}"
    
    def get_score_comparison(self, previous_audit=None, device='both'):
        """Get score changes compared to previous audit for specified device"""
        if not previous_audit:
            # Get the previous completed audit
            previous_audit = PerformanceHistory.objects.filter(
                performance_page=self.performance_page,
                status='completed',
                created_at__lt=self.created_at
            ).first()
        
        if not previous_audit:
            return None
        
        result = {}
        
        if device in ['mobile', 'both']:
            result['mobile'] = {
                'performance': {
                    'current': self.mobile_performance_score,
                    'previous': previous_audit.mobile_performance_score,
                    'change': (self.mobile_performance_score or 0) - (previous_audit.mobile_performance_score or 0)
                },
                'accessibility': {
                    'current': self.mobile_accessibility_score,
                    'previous': previous_audit.mobile_accessibility_score,
                    'change': (self.mobile_accessibility_score or 0) - (previous_audit.mobile_accessibility_score or 0)
                },
                'best_practices': {
                    'current': self.mobile_best_practices_score,
                    'previous': previous_audit.mobile_best_practices_score,
                    'change': (self.mobile_best_practices_score or 0) - (previous_audit.mobile_best_practices_score or 0)
                },
                'seo': {
                    'current': self.mobile_seo_score,
                    'previous': previous_audit.mobile_seo_score,
                    'change': (self.mobile_seo_score or 0) - (previous_audit.mobile_seo_score or 0)
                },
                'pwa': {
                    'current': self.mobile_pwa_score,
                    'previous': previous_audit.mobile_pwa_score,
                    'change': (self.mobile_pwa_score or 0) - (previous_audit.mobile_pwa_score or 0)
                }
            }
        
        if device in ['desktop', 'both']:
            result['desktop'] = {
                'performance': {
                    'current': self.desktop_performance_score,
                    'previous': previous_audit.desktop_performance_score,
                    'change': (self.desktop_performance_score or 0) - (previous_audit.desktop_performance_score or 0)
                },
                'accessibility': {
                    'current': self.desktop_accessibility_score,
                    'previous': previous_audit.desktop_accessibility_score,
                    'change': (self.desktop_accessibility_score or 0) - (previous_audit.desktop_accessibility_score or 0)
                },
                'best_practices': {
                    'current': self.desktop_best_practices_score,
                    'previous': previous_audit.desktop_best_practices_score,
                    'change': (self.desktop_best_practices_score or 0) - (previous_audit.desktop_best_practices_score or 0)
                },
                'seo': {
                    'current': self.desktop_seo_score,
                    'previous': previous_audit.desktop_seo_score,
                    'change': (self.desktop_seo_score or 0) - (previous_audit.desktop_seo_score or 0)
                },
                'pwa': {
                    'current': self.desktop_pwa_score,
                    'previous': previous_audit.desktop_pwa_score,
                    'change': (self.desktop_pwa_score or 0) - (previous_audit.desktop_pwa_score or 0)
                }
            }
        
        return result


class ConsolidatedErrors(models.Model):
    """Consolidated error tracking across all audits for a project"""
    
    performance_page = models.OneToOneField(
        PerformancePage,
        on_delete=models.CASCADE,
        related_name='consolidated_errors'
    )
    
    # Unique errors across all audits
    all_js_errors = models.JSONField(default=list, blank=True, help_text="All unique JS errors")
    all_css_errors = models.JSONField(default=list, blank=True, help_text="All unique CSS errors")
    all_console_errors = models.JSONField(default=list, blank=True, help_text="All unique console errors")
    all_network_errors = models.JSONField(default=list, blank=True, help_text="All unique network errors")
    
    # Error report file
    consolidated_error_report = models.FileField(
        upload_to='',
        storage=AuditJSONStorage(),
        null=True,
        blank=True,
        help_text="Consolidated error report across mobile and desktop"
    )
    
    # Statistics
    total_unique_errors = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'performance_consolidated_errors'
        verbose_name = 'Consolidated Error Report'
        verbose_name_plural = 'Consolidated Error Reports'
    
    def __str__(self):
        return f"Consolidated errors for {self.performance_page.project.domain}"


class PerformanceSchedule(models.Model):
    """Track scheduled audit runs to prevent duplicates"""
    
    performance_page = models.ForeignKey(
        PerformancePage,
        on_delete=models.CASCADE,
        related_name='schedules'
    )
    
    scheduled_for = models.DateTimeField()
    task_id = models.CharField(max_length=255, null=True, blank=True)
    is_processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'performance_schedules'
        unique_together = ['performance_page', 'scheduled_for']
        indexes = [
            models.Index(fields=['scheduled_for', 'is_processed']),
        ]
    
    def __str__(self):
        return f"Schedule for {self.performance_page} at {self.scheduled_for}"
