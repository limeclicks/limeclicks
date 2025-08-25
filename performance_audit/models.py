from django.db import models
from django.contrib.postgres.fields import JSONField
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from limeclicks.storage_backends import AuditJSONStorage, AuditHTMLStorage
import uuid
from datetime import timedelta


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
        """Update summary scores from latest audit"""
        if performance_history and performance_history.status == 'completed':
            self.last_audit_date = performance_history.completed_at
            self.performance_score = performance_history.performance_score
            self.accessibility_score = performance_history.accessibility_score
            self.best_practices_score = performance_history.best_practices_score
            self.seo_score = performance_history.seo_score
            self.pwa_score = performance_history.pwa_score
            self.save()


class PerformanceHistory(models.Model):
    """History of all audits for tracking and comparison"""
    
    AUDIT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    AUDIT_TRIGGER_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('manual', 'Manual'),
        ('project_created', 'Project Created'),
    ]
    
    DEVICE_CHOICES = [
        ('desktop', 'Desktop'),
        ('mobile', 'Mobile'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    performance_page = models.ForeignKey(
        PerformancePage,
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
        choices=AUDIT_TRIGGER_CHOICES,
        default='manual'
    )
    device_type = models.CharField(
        max_length=20,
        choices=DEVICE_CHOICES,
        default='desktop'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Scores (0-100)
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
    
    # Key metrics
    first_contentful_paint = models.FloatField(null=True, blank=True, help_text="FCP in seconds")
    largest_contentful_paint = models.FloatField(null=True, blank=True, help_text="LCP in seconds")
    time_to_interactive = models.FloatField(null=True, blank=True, help_text="TTI in seconds")
    speed_index = models.FloatField(null=True, blank=True, help_text="Speed Index in seconds")
    total_blocking_time = models.FloatField(null=True, blank=True, help_text="TBT in milliseconds")
    cumulative_layout_shift = models.FloatField(null=True, blank=True, help_text="CLS score")
    
    # Storage
    json_report = models.FileField(
        upload_to='',  # Will be handled by storage backend
        storage=AuditJSONStorage(),
        null=True,
        blank=True,
        help_text="Full Lighthouse JSON report"
    )
    html_report = models.FileField(
        upload_to='',  # Will be handled by storage backend
        storage=AuditHTMLStorage(),
        null=True,
        blank=True,
        help_text="HTML report for viewing"
    )
    
    # Error handling
    error_message = models.TextField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'performance_history'
        verbose_name = 'Audit History'
        verbose_name_plural = 'Audit Histories'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['performance_page', '-created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['device_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"Audit {self.id} - {self.performance_page.project.domain} ({self.device_type}) - {self.created_at}"
    
    def get_score_comparison(self, previous_audit=None):
        """Get score changes compared to previous audit"""
        if not previous_audit:
            # Get the previous completed audit
            previous_audit = PerformanceHistory.objects.filter(
                performance_page=self.performance_page,
                status='completed',
                device_type=self.device_type,
                created_at__lt=self.created_at
            ).first()
        
        if not previous_audit:
            return None
        
        return {
            'performance': {
                'current': self.performance_score,
                'previous': previous_audit.performance_score,
                'change': (self.performance_score or 0) - (previous_audit.performance_score or 0)
            },
            'accessibility': {
                'current': self.accessibility_score,
                'previous': previous_audit.accessibility_score,
                'change': (self.accessibility_score or 0) - (previous_audit.accessibility_score or 0)
            },
            'best_practices': {
                'current': self.best_practices_score,
                'previous': previous_audit.best_practices_score,
                'change': (self.best_practices_score or 0) - (previous_audit.best_practices_score or 0)
            },
            'seo': {
                'current': self.seo_score,
                'previous': previous_audit.seo_score,
                'change': (self.seo_score or 0) - (previous_audit.seo_score or 0)
            },
            'pwa': {
                'current': self.pwa_score,
                'previous': previous_audit.pwa_score,
                'change': (self.pwa_score or 0) - (previous_audit.pwa_score or 0)
            }
        }


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
