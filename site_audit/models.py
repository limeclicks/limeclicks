from django.db import models
from django.utils import timezone
from limeclicks.storage_backends import CloudflareR2Storage
import uuid
from datetime import timedelta
import json
import csv
import os


class SiteAudit(models.Model):
    """Simplified site audit model - stores Screaming Frog crawl results"""
    
    project = models.ForeignKey(
        'project.Project',
        on_delete=models.CASCADE,
        related_name='site_audits'
    )
    
    # Audit settings
    audit_frequency_days = models.IntegerField(
        default=30,
        help_text="Days between automatic audits (minimum 30)"
    )
    manual_audit_frequency_days = models.IntegerField(
        default=1,
        help_text="Days between manual audits (minimum 1)"
    )
    is_audit_enabled = models.BooleanField(
        default=True,
        help_text="Enable/disable automatic audits"
    )
    max_pages_to_crawl = models.IntegerField(
        default=5000,
        help_text="Maximum pages to crawl per audit (subscription-based limit)"
    )
    
    # Rate limiting
    last_automatic_audit = models.DateTimeField(null=True, blank=True)
    last_manual_audit = models.DateTimeField(null=True, blank=True)
    next_scheduled_audit = models.DateTimeField(null=True, blank=True)
    
    # Latest audit summary
    last_audit_date = models.DateTimeField(null=True, blank=True)
    
    # Issues overview from CSV (sorted by priority)
    issues_overview = models.JSONField(
        default=dict,
        blank=True,
        help_text="Issues overview from issues_overview_report.csv sorted by priority"
    )
    
    # Audit status tracking
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending',
        help_text="Current audit status"
    )
    
    # Temporary audit directory path for accessing crawl results
    temp_audit_dir = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Path to temporary directory containing latest crawl results"
    )
    
    # Crawl overview data from crawl_overview.csv
    crawl_overview = models.JSONField(
        default=dict,
        blank=True,
        help_text="Crawl overview data including URLs encountered, crawled, and top inlinks"
    )
    
    # Performance metrics
    average_page_size_kb = models.FloatField(null=True, blank=True)
    average_load_time_ms = models.FloatField(null=True, blank=True)
    total_pages_crawled = models.IntegerField(default=0)
    
    # Total pages crawled from crawl overview (alias for compatibility)
    @property
    def pages_crawled(self):
        """Alias for total_pages_crawled field"""
        return self.total_pages_crawled
    
    # PageSpeed Insights Performance Data
    desktop_performance = models.JSONField(
        default=dict,
        blank=True,
        help_text="Desktop PageSpeed Insights data including scores, core web vitals, and lab metrics"
    )
    mobile_performance = models.JSONField(
        default=dict,
        blank=True,
        help_text="Mobile PageSpeed Insights data including scores, core web vitals, and lab metrics"
    )
    
    # Combined scores
    performance_score_mobile = models.IntegerField(
        null=True, blank=True,
        help_text="Latest mobile performance score from PageSpeed Insights"
    )
    performance_score_desktop = models.IntegerField(
        null=True, blank=True,
        help_text="Latest desktop performance score from PageSpeed Insights"
    )
    overall_site_health_score = models.FloatField(
        null=True, blank=True,
        help_text="Technical SEO health score based on issue density (100% technical)"
    )
    
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
        
    def update_from_audit_results(self, crawl_results):
        """Update summary from latest audit results - updated for overview JSON"""
        if crawl_results:
            self.last_audit_date = timezone.now()
            
            # Update performance metrics
            summary = crawl_results.get('summary', {})
            if summary:
                self.average_page_size_kb = summary.get('average_page_size_kb')
                self.average_load_time_ms = summary.get('average_load_time_ms')
                self.total_pages_crawled = summary.get('total_pages_crawled', 0)
            
            # Don't calculate score here - it will be done after issues are parsed
            # self.calculate_overall_score()
            self.save()
    
    @classmethod
    def cleanup_old_audits(cls, project, keep_count=3):
        """Keep only the last N audits for a project"""
        audits = cls.objects.filter(project=project).order_by('-last_audit_date')
        if audits.count() > keep_count:
            # Delete older audits
            for audit in audits[keep_count:]:
                audit.delete()
    
    def calculate_overall_score(self):
        """Calculate overall site health score based on database issues"""
        from site_audit.models import SiteIssue
        from django.db.models import Count
        
        # Get issues from database
        issues = SiteIssue.objects.filter(site_audit=self)
        
        if not issues.exists():
            self.overall_site_health_score = 100
            return
        
        # Count issues by severity from database
        severity_counts = issues.values('severity').annotate(
            count=Count('id')
        )
        
        critical_issues = 0
        high_issues = 0
        medium_issues = 0
        low_issues = 0
        
        for item in severity_counts:
            if item['severity'] == 'critical':
                critical_issues = item['count']
            elif item['severity'] == 'high':
                high_issues = item['count']
            elif item['severity'] == 'medium':
                medium_issues = item['count']
            elif item['severity'] == 'low':
                low_issues = item['count']
        
        # Calculate weighted issue score with stronger penalties
        # Critical = 10 points, High = 5 points, Medium = 2 points, Low = 1 point
        weighted_issues = (critical_issues * 10) + (high_issues * 5) + (medium_issues * 2) + (low_issues * 1)
        
        # Calculate health score based on weighted issues
        if self.total_pages_crawled and self.total_pages_crawled > 0:
            # Normalize by pages crawled
            issues_per_page = weighted_issues / self.total_pages_crawled
            
            # More aggressive deduction: each weighted issue point per page reduces score by 20 points
            deduction = issues_per_page * 20
            self.overall_site_health_score = max(0, min(100, 100 - deduction))
        else:
            # If no pages crawled, base on absolute issues
            if weighted_issues == 0:
                self.overall_site_health_score = 100
            elif weighted_issues <= 5:
                self.overall_site_health_score = 90
            elif weighted_issues <= 10:
                self.overall_site_health_score = 75
            elif weighted_issues <= 20:
                self.overall_site_health_score = 60
            else:
                self.overall_site_health_score = max(0, 100 - (weighted_issues * 2))
        
        # Special handling: If there are high priority issues, cap the score
        if high_issues > 0:
            if high_issues >= 5:
                # 5+ high issues = critical (max 40%)
                self.overall_site_health_score = min(self.overall_site_health_score, 40)
            elif high_issues >= 2:
                # 2-4 high issues = needs attention (max 60%)  
                self.overall_site_health_score = min(self.overall_site_health_score, 60)
            else:
                # 1 high issue = slight penalty (max 75%)
                self.overall_site_health_score = min(self.overall_site_health_score, 75)
        
        # Round to 1 decimal place
        self.overall_site_health_score = round(self.overall_site_health_score, 1)
    
    def get_total_issues_count(self):
        """Get total issues count from database only"""
        from site_audit.models import SiteIssue
        return SiteIssue.objects.filter(site_audit=self).count()
    
    def get_issues_by_priority(self):
        """Get breakdown of issues by severity from database only"""
        from site_audit.models import SiteIssue
        from django.db.models import Count
        
        # Get from database only
        issues = SiteIssue.objects.filter(site_audit=self)
        severity_counts = issues.values('severity').annotate(
            count=Count('id')
        )
        
        breakdown = {'Critical': 0, 'High': 0, 'Medium': 0, 'Low': 0}
        for item in severity_counts:
            severity = item['severity'].capitalize()
            if severity in breakdown:
                breakdown[severity] = item['count']
        return breakdown
    
    def process_results(self):
        """
        Process crawl results from temp_audit_dir and update audit.
        
        Returns:
            dict: Processing results with status and metrics
        """
        from .parsers.crawl_overview import CrawlOverviewParser
        from .parsers.issues_overview import IssuesOverviewParser
        from .parsers.issue_parser_manager import IssueParserManager
        
        # Print the output directory path from temp_audit_dir
        if self.temp_audit_dir:
            print(f"🔍 Processing results from: {self.temp_audit_dir}")
        else:
            print("❌ No temp_audit_dir found - cannot process results")
            return {"status": "error", "message": "No temp_audit_dir available"}
        
        try:
            # Parse crawl overview data with saving logic inside parser
            parser = CrawlOverviewParser(self.temp_audit_dir, self)
            crawl_data = parser.parse()
            
            # Parse issues overview data
            issues_parser = IssuesOverviewParser(self.temp_audit_dir, self)
            issues_data = issues_parser.parse()
            
            # Parse and save individual issues to database
            print("\n📊 Parsing individual issues...")
            issue_manager = IssueParserManager(self.temp_audit_dir, self)
            detailed_issues = issue_manager.parse_all_issues()
            issues_saved = issue_manager.save_all_issues()
            print(f"✅ Saved {issues_saved} issues to database")
            
            # Prepare response data
            response = {
                "status": "success",
                "message": "Audit data processed successfully"
            }
            
            if crawl_data:
                response.update({
                    "pages_crawled": self.total_pages_crawled,
                    "urls_encountered": crawl_data.get('total_urls_encountered', 0),
                    "top_inlinks_count": len(crawl_data.get('top_20_inlinks', []))
                })
            
            if issues_data:
                response.update({
                    "total_issues": issues_data.get('total_issues', 0),
                    "high_priority_issues": issues_data.get('issues_by_priority', {}).get('High', 0),
                    "medium_priority_issues": issues_data.get('issues_by_priority', {}).get('Medium', 0),
                    "low_priority_issues": issues_data.get('issues_by_priority', {}).get('Low', 0)
                })
            
            # Add detailed issues info
            if detailed_issues:
                response.update({
                    "detailed_issues_saved": issues_saved,
                    "detailed_issues_by_category": detailed_issues.get('issues_by_category', {}),
                    "detailed_issues_by_severity": detailed_issues.get('issues_by_severity', {})
                })
            
            # Mark as completed if we have any data
            if crawl_data or issues_data:
                self.status = 'completed'
                self.last_audit_date = timezone.now()
                # Don't save here - let the parsers save with the correct health score
                # The IssuesOverviewParser already saves with the health score
            elif not crawl_data and not issues_data:
                print("⚠️ No overview data parsed")
                # Still mark as completed even if no overview data
                self.status = 'completed'
                self.last_audit_date = timezone.now()
                self.save()
                
                response = {
                    "status": "partial_success",
                    "message": "Audit completed but no overview data found"
                }
            
            return response
                
        except Exception as e:
            print(f"❌ Error processing crawl results: {e}")
            self.status = 'failed'
            self.save()
            return {"status": "error", "message": f"Failed to process results: {str(e)}"}


class SiteIssue(models.Model):
    """Model to store individual SEO issues found during site audit"""
    
    # Severity choices
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
        ('info', 'Info'),
    ]
    
    # Issue category choices
    CATEGORY_CHOICES = [
        ('meta_content', 'Meta Content'),
        ('response_code', 'Response Code'),
        ('image', 'Image'),
        ('technical_seo', 'Technical SEO'),
        ('content_quality', 'Content Quality'),
        ('security', 'Security'),
    ]
    
    # Issue status choices
    STATUS_CHOICES = [
        ('new', 'New'),
        ('persisting', 'Persisting'),
        ('resolved', 'Resolved'),
    ]
    
    # Core relationships
    site_audit = models.ForeignKey(
        SiteAudit, 
        on_delete=models.CASCADE, 
        related_name='issues'
    )
    
    # Issue identification
    url = models.URLField(max_length=2048)
    issue_type = models.CharField(max_length=100, db_index=True)
    issue_category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, db_index=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, db_index=True)
    
    # Issue details
    issue_data = models.JSONField(default=dict)
    """
    Dynamic storage for parser-specific data. Examples:
    
    MetaContent: {
        'content': 'actual title/meta/h1 text',
        'length': 45,
        'pixel_width': 320,
        'occurrences': 1,
        'duplicates': ['url1', 'url2']
    }
    
    ResponseCode: {
        'status_code': 404,
        'status_text': 'Not Found',
        'response_time': 0.234,
        'redirect_url': 'https://...',
        'redirect_type': 'HTTP Redirect'
    }
    """
    
    # SEO metadata
    indexability = models.CharField(max_length=50, blank=True)
    indexability_status = models.CharField(max_length=100, blank=True)
    inlinks_count = models.IntegerField(default=0)
    
    # Issue lifecycle tracking
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='new',
        db_index=True,
        help_text="Track if issue is new, persisting, or resolved"
    )
    first_detected_audit = models.ForeignKey(
        SiteAudit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='first_detected_issues',
        help_text="The audit where this issue was first detected"
    )
    resolved_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When the issue was resolved"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['severity', 'issue_type', 'url']
        indexes = [
            models.Index(fields=['site_audit', 'severity']),
            models.Index(fields=['site_audit', 'issue_category']),
            models.Index(fields=['site_audit', 'issue_type']),
        ]
    
    def __str__(self):
        return f"{self.get_severity_display()} - {self.issue_type} - {self.url[:50]}"
    
    @classmethod
    def get_severity_for_issue_type(cls, issue_type):
        """Map issue types to severity levels"""
        severity_mapping = {
            # Critical
            'missing_title': 'critical',
            'internal_client_error_4xx': 'critical',
            'internal_server_error_5xx': 'critical',
            'mixed_content': 'critical',
            'missing_hsts_header': 'critical',
            
            # High
            'duplicate_title': 'high',
            'missing_meta_description': 'high',
            'duplicate_meta_description': 'high',
            'missing_h1': 'high',
            'internal_redirection_3xx': 'high',
            'missing_canonical': 'high',
            
            # Medium
            'title_too_long': 'medium',
            'title_too_short': 'medium',
            'meta_too_long': 'medium',
            'meta_too_short': 'medium',
            'low_content_pages': 'medium',
            'missing_alt_text': 'medium',
            'url_underscores': 'medium',
            'url_uppercase': 'medium',
            
            # Low
            'missing_h2': 'low',
            'duplicate_h2': 'low',
            'readability_difficult': 'low',
            'pagination_sequence_error': 'low',
            
            # Info
            'noindex': 'info',
            'url_parameters': 'info',
        }
        
        # Try exact match first
        if issue_type in severity_mapping:
            return severity_mapping[issue_type]
        
        # Try partial matches
        for key, severity in severity_mapping.items():
            if key in issue_type.lower():
                return severity
        
        return 'medium'  # Default severity
