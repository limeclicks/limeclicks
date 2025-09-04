"""
Keyword Reporting Models
Handles report generation, scheduling, and storage
"""

from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import timedelta
from project.models import Project


class KeywordReport(models.Model):
    """Track generated keyword reports"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    REPORT_FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('pdf', 'PDF'),
        ('both', 'Both CSV and PDF'),
    ]
    
    # Core fields
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='keyword_reports'
    )
    
    # Report configuration
    name = models.CharField(
        max_length=255,
        help_text="Report name or title"
    )
    
    start_date = models.DateField(
        help_text="Report start date"
    )
    
    end_date = models.DateField(
        help_text="Report end date"
    )
    
    report_format = models.CharField(
        max_length=10,
        choices=REPORT_FORMAT_CHOICES,
        default='both'
    )
    
    # Keywords configuration
    keywords = models.ManyToManyField(
        'Keyword',
        blank=True,
        help_text="Specific keywords to include. Leave empty for all project keywords"
    )
    
    include_tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Include keywords with these tags"
    )
    
    exclude_tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Exclude keywords with these tags"
    )
    
    # Report settings
    fill_missing_ranks = models.BooleanField(
        default=True,
        help_text="Use previous day's rank when data is missing"
    )
    
    include_competitors = models.BooleanField(
        default=False,
        help_text="Include competitor tracking data if available"
    )
    
    include_graphs = models.BooleanField(
        default=True,
        help_text="Include graphs in PDF report"
    )
    
    # Status fields
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    
    error_message = models.TextField(
        blank=True,
        null=True
    )
    
    # File storage (R2)
    csv_file_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="R2 path to CSV file"
    )
    
    pdf_file_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="R2 path to PDF file"
    )
    
    csv_file_size = models.BigIntegerField(
        default=0,
        help_text="CSV file size in bytes"
    )
    
    pdf_file_size = models.BigIntegerField(
        default=0,
        help_text="PDF file size in bytes"
    )
    
    # Processing information
    processing_started_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    processing_completed_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    processing_duration_seconds = models.IntegerField(
        default=0
    )
    
    # User tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_reports'
    )
    
    # Email notification
    send_email_notification = models.BooleanField(
        default=True,
        help_text="Send email when report is ready"
    )
    
    email_sent = models.BooleanField(
        default=False
    )
    
    email_sent_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Download tracking
    download_count = models.IntegerField(
        default=0
    )
    
    last_downloaded_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'keyword_reports'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', '-created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['created_by', '-created_at']),
        ]
        
    def __str__(self):
        return f"{self.name} - {self.project.domain} ({self.start_date} to {self.end_date})"
    
    def clean(self):
        """Validate report configuration"""
        from django.core.exceptions import ValidationError
        
        # Validate date range
        if self.end_date and self.start_date:
            date_diff = (self.end_date - self.start_date).days
            if date_diff < 0:
                raise ValidationError("End date must be after start date")
            if date_diff > 60:
                raise ValidationError("Report period cannot exceed 60 days")
    
    def get_duration_display(self):
        """Get human-readable processing duration"""
        if self.processing_duration_seconds == 0:
            return "N/A"
        
        minutes, seconds = divmod(self.processing_duration_seconds, 60)
        if minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"
    
    def get_file_size_display(self, file_type='csv'):
        """Get human-readable file size"""
        size = self.csv_file_size if file_type == 'csv' else self.pdf_file_size
        
        if size == 0:
            return "N/A"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        
        return f"{size:.2f} TB"
    
    def mark_as_processing(self):
        """Mark report as processing"""
        self.status = 'processing'
        self.processing_started_at = timezone.now()
        self.save(update_fields=['status', 'processing_started_at', 'updated_at'])
    
    def mark_as_completed(self):
        """Mark report as completed"""
        self.status = 'completed'
        self.processing_completed_at = timezone.now()
        
        if self.processing_started_at:
            duration = (self.processing_completed_at - self.processing_started_at).total_seconds()
            self.processing_duration_seconds = int(duration)
        
        self.save(update_fields=[
            'status', 'processing_completed_at', 
            'processing_duration_seconds', 'updated_at'
        ])
    
    def mark_as_failed(self, error_message):
        """Mark report as failed"""
        self.status = 'failed'
        self.error_message = error_message
        self.processing_completed_at = timezone.now()
        
        if self.processing_started_at:
            duration = (self.processing_completed_at - self.processing_started_at).total_seconds()
            self.processing_duration_seconds = int(duration)
        
        self.save(update_fields=[
            'status', 'error_message', 'processing_completed_at',
            'processing_duration_seconds', 'updated_at'
        ])


class ReportSchedule(models.Model):
    """Schedule recurring report generation"""
    
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-Weekly'),
        ('monthly', 'Monthly'),
    ]
    
    DAY_OF_WEEK_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    # Core fields
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='report_schedules'
    )
    
    name = models.CharField(
        max_length=255,
        help_text="Schedule name"
    )
    
    # Schedule configuration
    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default='weekly'
    )
    
    day_of_week = models.IntegerField(
        choices=DAY_OF_WEEK_CHOICES,
        null=True,
        blank=True,
        help_text="For weekly reports"
    )
    
    day_of_month = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        null=True,
        blank=True,
        help_text="For monthly reports (1-31)"
    )
    
    time_of_day = models.TimeField(
        default="09:00",
        help_text="Time to generate report (UTC)"
    )
    
    # Report configuration (same as KeywordReport)
    report_period_days = models.IntegerField(
        default=7,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
        help_text="Number of days to include in each report"
    )
    
    report_format = models.CharField(
        max_length=10,
        choices=KeywordReport.REPORT_FORMAT_CHOICES,
        default='both'
    )
    
    keywords = models.ManyToManyField(
        'Keyword',
        blank=True,
        help_text="Specific keywords to include. Leave empty for all project keywords"
    )
    
    include_tags = models.JSONField(
        default=list,
        blank=True
    )
    
    exclude_tags = models.JSONField(
        default=list,
        blank=True
    )
    
    fill_missing_ranks = models.BooleanField(
        default=True
    )
    
    include_competitors = models.BooleanField(
        default=False
    )
    
    include_graphs = models.BooleanField(
        default=True
    )
    
    # Email configuration
    email_recipients = models.JSONField(
        default=list,
        help_text="List of email addresses to send reports to"
    )
    
    # Status fields
    is_active = models.BooleanField(
        default=True,
        db_index=True
    )
    
    last_run_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    last_report = models.ForeignKey(
        KeywordReport,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )
    
    next_run_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True
    )
    
    # User tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'report_schedules'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', 'is_active']),
            models.Index(fields=['is_active', 'next_run_at']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.get_frequency_display()} for {self.project.domain}"
    
    def calculate_next_run(self):
        """Calculate the next run time based on frequency"""
        from datetime import datetime, time
        
        now = timezone.now()
        
        # Combine date with time_of_day
        def combine_datetime(date, time_val):
            return timezone.make_aware(
                datetime.combine(date, time_val),
                timezone.get_current_timezone()
            )
        
        if self.frequency == 'daily':
            # Next occurrence of time_of_day
            next_run = combine_datetime(now.date(), self.time_of_day)
            if next_run <= now:
                next_run += timedelta(days=1)
                
        elif self.frequency == 'weekly':
            # Next occurrence of day_of_week at time_of_day
            days_ahead = self.day_of_week - now.weekday()
            if days_ahead < 0:  # Day already happened this week
                days_ahead += 7
            elif days_ahead == 0:  # Same day
                next_run = combine_datetime(now.date(), self.time_of_day)
                if next_run <= now:
                    days_ahead = 7
            
            next_date = now.date() + timedelta(days=days_ahead)
            next_run = combine_datetime(next_date, self.time_of_day)
            
        elif self.frequency == 'biweekly':
            # Every two weeks on day_of_week
            days_ahead = self.day_of_week - now.weekday()
            if days_ahead < 0:
                days_ahead += 14
            elif days_ahead == 0:
                next_run = combine_datetime(now.date(), self.time_of_day)
                if next_run <= now:
                    days_ahead = 14
            else:
                # Check if this week or next week
                days_ahead += 7  # Default to next occurrence (2 weeks)
            
            next_date = now.date() + timedelta(days=days_ahead)
            next_run = combine_datetime(next_date, self.time_of_day)
            
        elif self.frequency == 'monthly':
            # Next occurrence of day_of_month
            from datetime import date
            from dateutil.relativedelta import relativedelta
            
            current_month_date = date(now.year, now.month, min(self.day_of_month, 28))
            next_run = combine_datetime(current_month_date, self.time_of_day)
            
            if next_run <= now:
                # Move to next month
                next_month = now.date() + relativedelta(months=1)
                next_date = date(next_month.year, next_month.month, min(self.day_of_month, 28))
                next_run = combine_datetime(next_date, self.time_of_day)
        
        self.next_run_at = next_run
        return next_run
    
    def should_run_now(self):
        """Check if this schedule should run now"""
        if not self.is_active:
            return False
        
        if not self.next_run_at:
            self.calculate_next_run()
            self.save(update_fields=['next_run_at'])
        
        return timezone.now() >= self.next_run_at