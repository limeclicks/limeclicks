from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from limeclicks.storage_backends import CloudflareR2Storage
import uuid
from datetime import timedelta
import json


class ScreamingFrogLicense(models.Model):
    """Singleton model to store Screaming Frog license information"""
    
    license_key = models.CharField(max_length=255, help_text="Screaming Frog license key")
    license_type = models.CharField(
        max_length=50,
        choices=[
            ('free', 'Free (500 URLs)'),
            ('paid', 'Paid (Unlimited)'),
        ],
        default='free'
    )
    license_status = models.CharField(
        max_length=20,
        choices=[
            ('valid', 'Valid'),
            ('expired', 'Expired'),
            ('invalid', 'Invalid'),
        ],
        default='valid'
    )
    expiry_date = models.DateField(null=True, blank=True)
    last_validated = models.DateTimeField(null=True, blank=True)
    last_reminder_sent = models.DateTimeField(null=True, blank=True, help_text="Last time expiry reminder was sent")
    max_urls = models.IntegerField(default=500, help_text="Maximum URLs allowed by license")
    
    # License holder information
    license_holder = models.CharField(max_length=255, null=True, blank=True)
    license_email = models.EmailField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'screaming_frog_license'
        verbose_name = 'Screaming Frog License'
        verbose_name_plural = 'Screaming Frog License'
    
    def save(self, *args, **kwargs):
        # Ensure only one license record exists
        if not self.pk and ScreamingFrogLicense.objects.exists():
            # Update existing record instead of creating new one
            existing = ScreamingFrogLicense.objects.first()
            self.pk = existing.pk
        super().save(*args, **kwargs)
    
    def is_expired(self):
        """Check if license is expired"""
        if not self.expiry_date:
            return False
        return timezone.now().date() > self.expiry_date
    
    def days_until_expiry(self):
        """Get days until license expires"""
        if not self.expiry_date:
            return None
        delta = self.expiry_date - timezone.now().date()
        return delta.days
    
    def should_revalidate(self):
        """Check if license should be revalidated (once per week)"""
        if not self.last_validated:
            return True
        return timezone.now() - self.last_validated > timedelta(days=7)
    
    def __str__(self):
        return f"Screaming Frog License ({self.license_status})"


class SiteAudit(models.Model):
    """Main model for on-page SEO audits"""
    
    project = models.OneToOneField(
        'project.Project',
        on_delete=models.CASCADE,
        related_name='site_audit'
    )
    
    # Audit settings
    audit_frequency_days = models.IntegerField(
        default=30,
        help_text="Days between automatic audits (minimum 30)"
    )
    manual_audit_frequency_days = models.IntegerField(
        default=3,
        help_text="Days between manual audits (minimum 3)"
    )
    is_audit_enabled = models.BooleanField(
        default=True,
        help_text="Enable/disable automatic audits"
    )
    max_pages_to_crawl = models.IntegerField(
        default=500,
        help_text="Maximum pages to crawl per audit"
    )
    
    # Rate limiting
    last_automatic_audit = models.DateTimeField(null=True, blank=True)
    last_manual_audit = models.DateTimeField(null=True, blank=True)
    next_scheduled_audit = models.DateTimeField(null=True, blank=True)
    
    # Latest audit summary
    last_audit_date = models.DateTimeField(null=True, blank=True)
    
    # Issue counts (latest)
    broken_links_count = models.IntegerField(default=0)
    redirect_chains_count = models.IntegerField(default=0)
    missing_titles_count = models.IntegerField(default=0)
    duplicate_titles_count = models.IntegerField(default=0)
    missing_meta_descriptions_count = models.IntegerField(default=0)
    duplicate_meta_descriptions_count = models.IntegerField(default=0)
    blocked_by_robots_count = models.IntegerField(default=0)
    missing_hreflang_count = models.IntegerField(default=0)
    duplicate_content_count = models.IntegerField(default=0)
    spelling_errors_count = models.IntegerField(default=0)
    total_issues_count = models.IntegerField(default=0)
    
    # Performance metrics
    average_page_size_kb = models.FloatField(null=True, blank=True)
    average_load_time_ms = models.FloatField(null=True, blank=True)
    total_pages_crawled = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'site_audits'
        verbose_name = 'On-Page Audit'
        verbose_name_plural = 'On-Page Audits'
        indexes = [
            models.Index(fields=['next_scheduled_audit']),
            models.Index(fields=['is_audit_enabled', 'next_scheduled_audit']),
        ]
    
    def __str__(self):
        return f"On-Page Audit for {self.project.domain}"
    
    def can_run_automatic_audit(self):
        """Check if automatic audit can be run (30 day limit)"""
        if not self.last_automatic_audit:
            return True
        time_since_last = timezone.now() - self.last_automatic_audit
        return time_since_last >= timedelta(days=self.audit_frequency_days)
    
    def can_run_manual_audit(self):
        """Check if manual audit can be run (3 day limit)"""
        if not self.last_manual_audit:
            return True
        time_since_last = timezone.now() - self.last_manual_audit
        return time_since_last >= timedelta(days=self.manual_audit_frequency_days)
    
    def schedule_next_audit(self):
        """Schedule the next automatic audit"""
        if self.is_audit_enabled:
            self.next_scheduled_audit = timezone.now() + timedelta(days=self.audit_frequency_days)
            self.save(update_fields=['next_scheduled_audit'])
    
    def update_from_audit_results(self, performance_history):
        """Update summary from latest audit"""
        if performance_history and performance_history.status == 'completed':
            self.last_audit_date = performance_history.completed_at
            
            # Update issue counts
            summary = performance_history.get_summary_data()
            if summary:
                self.broken_links_count = summary.get('broken_links', 0)
                self.redirect_chains_count = summary.get('redirect_chains', 0)
                self.missing_titles_count = summary.get('missing_titles', 0)
                self.duplicate_titles_count = summary.get('duplicate_titles', 0)
                self.missing_meta_descriptions_count = summary.get('missing_meta_descriptions', 0)
                self.duplicate_meta_descriptions_count = summary.get('duplicate_meta_descriptions', 0)
                self.blocked_by_robots_count = summary.get('blocked_by_robots', 0)
                self.missing_hreflang_count = summary.get('missing_hreflang', 0)
                self.duplicate_content_count = summary.get('duplicate_content', 0)
                self.spelling_errors_count = summary.get('spelling_errors', 0)
                self.total_issues_count = summary.get('total_issues', 0)
                
                # Update performance metrics
                self.average_page_size_kb = summary.get('average_page_size_kb')
                self.average_load_time_ms = summary.get('average_load_time_ms')
                self.total_pages_crawled = summary.get('total_pages_crawled', 0)
            
            self.save()


class OnPagePerformanceHistory(models.Model):
    """History of all on-page audits"""
    
    AUDIT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    TRIGGER_TYPE_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('manual', 'Manual'),
        ('project_created', 'Project Created'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    audit = models.ForeignKey(
        SiteAudit,
        on_delete=models.CASCADE,
        related_name='performance_history'
    )
    
    # Audit metadata
    status = models.CharField(
        max_length=20,
        choices=AUDIT_STATUS_CHOICES,
        default='pending'
    )
    trigger_type = models.CharField(
        max_length=20,
        choices=TRIGGER_TYPE_CHOICES,
        default='manual'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Crawl settings used
    pages_crawled = models.IntegerField(default=0)
    max_pages_limit = models.IntegerField(default=500)
    crawl_depth = models.IntegerField(default=10)
    
    # Summary data (stored in DB for quick access)
    summary_data = models.JSONField(null=True, blank=True)
    
    # Issue details (detailed data stored in R2)
    issues_summary = models.JSONField(null=True, blank=True)
    
    # Comparison with previous audit
    issues_fixed = models.IntegerField(default=0)
    issues_introduced = models.IntegerField(default=0)
    total_issues = models.IntegerField(default=0)
    
    # Storage in R2
    full_report_json = models.FileField(
        upload_to='onpage/',
        storage=CloudflareR2Storage(),
        null=True,
        blank=True,
        help_text="Full Screaming Frog JSON report"
    )
    
    crawl_report_csv = models.FileField(
        upload_to='onpage/',
        storage=CloudflareR2Storage(),
        null=True,
        blank=True,
        help_text="Screaming Frog CSV export"
    )
    
    issues_report_json = models.FileField(
        upload_to='onpage/',
        storage=CloudflareR2Storage(),
        null=True,
        blank=True,
        help_text="Processed issues report"
    )
    
    # Error handling
    error_message = models.TextField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'onpage_performance_history'
        verbose_name = 'On-Page Audit History'
        verbose_name_plural = 'On-Page Audit Histories'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['audit', '-created_at']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"On-Page Audit {self.id} - {self.audit.project.domain} - {self.created_at}"
    
    def get_summary_data(self):
        """Get summary data as dict"""
        if isinstance(self.summary_data, str):
            return json.loads(self.summary_data)
        return self.summary_data or {}
    
    def get_issues_summary(self):
        """Get issues summary as dict"""
        if isinstance(self.issues_summary, str):
            return json.loads(self.issues_summary)
        return self.issues_summary or {}
    
    def compare_with_previous(self):
        """Compare with previous audit to find fixed/new issues"""
        previous = OnPagePerformanceHistory.objects.filter(
            audit=self.audit,
            status='completed',
            created_at__lt=self.created_at
        ).first()
        
        if not previous:
            return None
        
        current_issues = self.get_issues_summary()
        previous_issues = previous.get_issues_summary()
        
        comparison = {
            'previous_date': previous.created_at,
            'current_date': self.created_at,
            'fixed_issues': [],
            'new_issues': [],
            'recurring_issues': [],
            'metrics_change': {}
        }
        
        # Compare issue counts
        for issue_type in ['broken_links', 'missing_titles', 'duplicate_titles', 
                          'missing_meta_descriptions', 'duplicate_meta_descriptions',
                          'blocked_by_robots', 'duplicate_content', 'spelling_errors']:
            
            current_count = current_issues.get(issue_type, 0)
            previous_count = previous_issues.get(issue_type, 0)
            
            if current_count < previous_count:
                comparison['fixed_issues'].append({
                    'type': issue_type,
                    'fixed': previous_count - current_count
                })
            elif current_count > previous_count:
                comparison['new_issues'].append({
                    'type': issue_type,
                    'new': current_count - previous_count
                })
            elif current_count > 0:
                comparison['recurring_issues'].append({
                    'type': issue_type,
                    'count': current_count
                })
            
            comparison['metrics_change'][issue_type] = {
                'previous': previous_count,
                'current': current_count,
                'change': current_count - previous_count
            }
        
        return comparison


class SiteIssue(models.Model):
    """Individual issues found during on-page audit"""
    
    ISSUE_TYPE_CHOICES = [
        ('broken_link', 'Broken Link (4xx/5xx)'),
        ('redirect_chain', 'Redirect Chain'),
        ('missing_title', 'Missing Title'),
        ('duplicate_title', 'Duplicate Title'),
        ('title_too_long', 'Title Too Long'),
        ('title_too_short', 'Title Too Short'),
        ('missing_meta_description', 'Missing Meta Description'),
        ('duplicate_meta_description', 'Duplicate Meta Description'),
        ('meta_description_too_long', 'Meta Description Too Long'),
        ('meta_description_too_short', 'Meta Description Too Short'),
        ('blocked_by_robots', 'Blocked by Robots'),
        ('noindex_page', 'Noindex Page'),
        ('missing_hreflang', 'Missing Hreflang'),
        ('invalid_hreflang', 'Invalid Hreflang'),
        ('duplicate_content', 'Duplicate Content'),
        ('near_duplicate', 'Near Duplicate Content'),
        ('spelling_error', 'Spelling/Grammar Error'),
        ('missing_h1', 'Missing H1'),
        ('multiple_h1', 'Multiple H1 Tags'),
        ('missing_alt_text', 'Missing Alt Text'),
        ('page_too_large', 'Page Too Large'),
        ('slow_page', 'Slow Loading Page'),
        ('orphan_page', 'Orphan Page'),
    ]
    
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
        ('info', 'Info'),
    ]
    
    performance_history = models.ForeignKey(
        OnPagePerformanceHistory,
        on_delete=models.CASCADE,
        related_name='issues'
    )
    
    issue_type = models.CharField(max_length=50, choices=ISSUE_TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    
    page_url = models.URLField(max_length=2000)
    page_title = models.CharField(max_length=500, null=True, blank=True)
    
    # Issue details
    description = models.TextField()
    recommendation = models.TextField(null=True, blank=True)
    
    # Additional metadata
    status_code = models.IntegerField(null=True, blank=True)
    response_time_ms = models.IntegerField(null=True, blank=True)
    page_size_bytes = models.IntegerField(null=True, blank=True)
    
    # For duplicate content
    duplicate_urls = models.JSONField(null=True, blank=True)
    similarity_score = models.FloatField(null=True, blank=True)
    
    # For broken links
    source_url = models.URLField(max_length=2000, null=True, blank=True)
    anchor_text = models.CharField(max_length=500, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'onpage_issues'
        verbose_name = 'On-Page Issue'
        verbose_name_plural = 'On-Page Issues'
        indexes = [
            models.Index(fields=['performance_history', 'issue_type']),
            models.Index(fields=['severity']),
            models.Index(fields=['page_url']),
        ]
    
    def __str__(self):
        return f"{self.get_issue_type_display()} - {self.page_url[:50]}"
