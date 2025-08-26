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
    
    # Combined scores
    performance_score_mobile = models.IntegerField(
        null=True, blank=True,
        help_text="Latest mobile performance score from Lighthouse"
    )
    performance_score_desktop = models.IntegerField(
        null=True, blank=True,
        help_text="Latest desktop performance score from Lighthouse"
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
            
            # Update overall score
            self.calculate_overall_score()
            self.save()
    
    def update_performance_scores(self):
        """Update performance scores from PerformanceHistory"""
        try:
            from performance_audit.models import PerformancePage, PerformanceHistory
            
            performance_page = PerformancePage.objects.filter(project=self.project).first()
            if performance_page:
                # Get latest mobile score
                latest_mobile = PerformanceHistory.objects.filter(
                    performance_page=performance_page,
                    device_type='mobile',
                    status='completed'
                ).order_by('-created_at').first()
                
                if latest_mobile and latest_mobile.performance_score is not None:
                    self.performance_score_mobile = latest_mobile.performance_score
                
                # Get latest desktop score
                latest_desktop = PerformanceHistory.objects.filter(
                    performance_page=performance_page,
                    device_type='desktop',
                    status='completed'
                ).order_by('-created_at').first()
                
                if latest_desktop and latest_desktop.performance_score is not None:
                    self.performance_score_desktop = latest_desktop.performance_score
                
                # Calculate overall score
                self.calculate_overall_score()
                self.save(update_fields=['performance_score_mobile', 'performance_score_desktop', 'overall_site_health_score'])
        except:
            pass
    
    def calculate_overall_score(self):
        """Calculate overall site health score combining technical SEO and performance"""
        # Calculate technical SEO health
        if self.total_pages_crawled and self.total_pages_crawled > 0:
            issues_per_page = self.total_issues_count / self.total_pages_crawled
            technical_health = max(0, min(100, 100 - (issues_per_page * 100)))
        else:
            technical_health = 100 if self.total_issues_count == 0 else 0
        
        # Get average performance score
        performance_scores = []
        if self.performance_score_mobile is not None:
            performance_scores.append(self.performance_score_mobile)
        if self.performance_score_desktop is not None:
            performance_scores.append(self.performance_score_desktop)
        
        avg_performance = sum(performance_scores) / len(performance_scores) if performance_scores else 50
        
        # Calculate combined score (60% technical SEO + 40% performance)
        self.overall_site_health_score = (technical_health * 0.6) + (avg_performance * 0.4)


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
        # Page Titles & Metadata
        ('missing_title', 'Missing Page Title'),
        ('duplicate_title', 'Duplicate Page Title'),
        ('title_too_long', 'Page Title Too Long (>60 chars)'),
        ('title_too_short', 'Page Title Too Short (<30 chars)'),
        ('title_pixel_width', 'Title Pixel Width Too Long (>600px)'),
        ('missing_meta_description', 'Missing Meta Description'),
        ('duplicate_meta_description', 'Duplicate Meta Description'),
        ('meta_description_too_long', 'Meta Description Too Long (>160 chars)'),
        ('meta_description_too_short', 'Meta Description Too Short (<70 chars)'),
        ('meta_pixel_width', 'Meta Description Pixel Width Too Long'),
        
        # Headings
        ('missing_h1', 'Missing H1 Tag'),
        ('multiple_h1', 'Multiple H1 Tags'),
        ('duplicate_h1', 'Duplicate H1 Tag'),
        ('h1_too_long', 'H1 Too Long (>70 chars)'),
        ('h1_too_short', 'H1 Too Short (<20 chars)'),
        ('missing_h2', 'Missing H2 Tags'),
        ('duplicate_h2', 'Duplicate H2 Tags'),
        
        # Content & Duplicate Issues
        ('duplicate_content', 'Exact Duplicate Content'),
        ('near_duplicate', 'Near Duplicate Content'),
        ('thin_content', 'Low Word Count/Thin Content'),
        ('canonical_issue', 'Canonicalization Issue'),
        ('canonical_chain', 'Canonical Chain'),
        ('canonical_loop', 'Canonical Loop'),
        ('noindex_page', 'Noindex Page'),
        ('orphan_page', 'Orphan Page (No Internal Links)'),
        
        # Images
        ('missing_alt_text', 'Missing Alt Text on Images'),
        ('missing_alt_linked', 'Missing Alt Text on Linked Images'),
        ('image_too_large', 'Image Too Large (>100KB)'),
        ('broken_image', 'Missing/Broken Image'),
        
        # Links & Redirects
        ('broken_internal_link', 'Broken Internal Link (404/5xx)'),
        ('broken_external_link', 'Broken External Link'),
        ('redirect_chain', 'Redirect Chain'),
        ('redirect_loop', 'Redirect Loop'),
        ('temporary_redirect', 'Temporary Redirect (302)'),
        ('permanent_redirect', 'Permanent Redirect (301)'),
        ('blocked_by_robots', 'Link Blocked by Robots.txt'),
        ('internal_nofollow', 'Internal Nofollow Link'),
        ('external_nofollow', 'External Nofollow Link'),
        
        # Structured Data & Directives
        ('missing_canonical', 'Missing Canonical Tag'),
        ('conflicting_canonical', 'Conflicting Canonical Tags'),
        ('multiple_canonical', 'Multiple Canonical Tags'),
        ('hreflang_missing_return', 'Hreflang Missing Return Link'),
        ('hreflang_invalid_code', 'Hreflang Invalid Language Code'),
        ('hreflang_no_self', 'Hreflang No Self-Reference'),
        ('meta_robots_issue', 'Meta Robots Tag Issue'),
        ('x_robots_issue', 'X-Robots-Tag Issue'),
        ('amp_error', 'AMP Error'),
        
        # Sitemaps & Crawling
        ('sitemap_mismatch', 'URL in Sitemap Not on Site'),
        ('sitemap_noindex', 'Sitemap Contains Noindex URLs'),
        ('sitemap_missing', 'Page Missing from Sitemap'),
        ('robots_blocked_resource', 'Robots.txt Blocked Resource'),
        ('crawl_depth_issue', 'Excessive Crawl Depth'),
        
        # Performance & Other
        ('slow_page', 'Slow Page Load (>3s)'),
        ('mobile_usability', 'Mobile Usability Issue'),
        ('mixed_content', 'Mixed Content (HTTP on HTTPS)'),
        ('http_https_mismatch', 'HTTP/HTTPS Inconsistency'),
        ('non_200_status', 'Non-200 Status Code'),
        ('missing_structured_data', 'Missing Structured Data'),
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
    
    def get_clean_display_name(self):
        """Get a clean display name for the issue type"""
        display_name = self.get_issue_type_display()
        if not display_name or display_name == self.issue_type:
            # Fallback: convert issue_type to readable format
            return self.issue_type.replace('_', ' ').title()
        return display_name
    
    @classmethod
    def get_issue_severity(cls, issue_type):
        """Get severity level for an issue type"""
        severity_map = {
            # Critical issues
            'broken_internal_link': 'critical',
            'broken_external_link': 'critical',
            'broken_image': 'critical',
            'redirect_loop': 'critical',
            'canonical_loop': 'critical',
            'non_200_status': 'critical',
            
            # High priority issues
            'missing_title': 'high',
            'duplicate_title': 'high',
            'missing_meta_description': 'high',
            'duplicate_content': 'high',
            'missing_h1': 'high',
            'multiple_h1': 'high',
            'noindex_page': 'high',
            'blocked_by_robots': 'high',
            
            # Medium priority issues
            'title_too_long': 'medium',
            'title_too_short': 'medium',
            'meta_description_too_long': 'medium',
            'meta_description_too_short': 'medium',
            'redirect_chain': 'medium',
            'missing_canonical': 'medium',
            'thin_content': 'medium',
            'orphan_page': 'medium',
            'slow_page': 'medium',
            
            # Low priority issues
            'missing_alt_text': 'low',
            'image_too_large': 'low',
            'temporary_redirect': 'low',
            'internal_nofollow': 'low',
            'missing_h2': 'low',
            'duplicate_h2': 'low',
            
            # Info level
            'permanent_redirect': 'info',
            'external_nofollow': 'info',
            'missing_structured_data': 'info',
        }
        return severity_map.get(issue_type, 'medium')
    
    @classmethod
    def get_resolution_suggestion(cls, issue_type):
        """Get resolution suggestion for an issue type"""
        resolutions = {
            # Page Titles & Metadata
            'missing_title': "Add a unique, descriptive title tag to the page. Aim for 50-60 characters that accurately describe the page content and include target keywords.",
            'duplicate_title': "Make each page title unique. Differentiate pages by adding specific identifiers like location, product names, or categories.",
            'title_too_long': "Shorten the title to under 60 characters to prevent truncation in search results. Focus on the most important keywords.",
            'title_too_short': "Expand the title to at least 30 characters to better describe the page content and improve click-through rates.",
            'title_pixel_width': "Reduce title length to fit within 600 pixels. Consider shorter words or removing less important terms.",
            'missing_meta_description': "Add a compelling meta description of 150-160 characters that summarizes the page content and includes a call-to-action.",
            'duplicate_meta_description': "Write unique meta descriptions for each page. Customize them to highlight what makes each page different.",
            'meta_description_too_long': "Trim the meta description to under 160 characters to avoid truncation in search results.",
            'meta_description_too_short': "Expand the meta description to at least 70 characters to provide more context about the page.",
            
            # Headings
            'missing_h1': "Add a single H1 tag that clearly describes the main topic of the page. This helps both users and search engines understand the content.",
            'multiple_h1': "Use only one H1 tag per page. Convert additional H1s to H2 or H3 tags to maintain proper heading hierarchy.",
            'duplicate_h1': "Make H1 tags unique across pages. Each page should have its own distinctive main heading.",
            'h1_too_long': "Shorten the H1 to under 70 characters for better readability and user experience.",
            'h1_too_short': "Expand the H1 to at least 20 characters to better describe the page topic.",
            'missing_h2': "Add H2 tags to break up content into logical sections. This improves readability and content structure.",
            'duplicate_h2': "Vary your H2 tags to cover different aspects of the topic. Each should introduce a unique section.",
            
            # Content & Duplicate Issues
            'duplicate_content': "Rewrite content to be unique, or use canonical tags to point to the original version. Consider consolidating duplicate pages.",
            'near_duplicate': "Differentiate similar pages by adding unique content, or merge them if they serve the same purpose.",
            'thin_content': "Expand content to at least 300 words. Add valuable information, examples, or related topics to provide more value.",
            'canonical_issue': "Fix canonical tag implementation. Ensure it points to the correct preferred version of the page.",
            'canonical_chain': "Point canonical tags directly to the final destination, not through intermediate pages.",
            'canonical_loop': "Break the canonical loop by ensuring tags don't create circular references.",
            'noindex_page': "Remove noindex if the page should be indexed, or ensure it's intentional for pages like admin or duplicate content.",
            'orphan_page': "Add internal links to this page from related content to help users and search engines discover it.",
            
            # Images
            'missing_alt_text': "Add descriptive alt text to images for accessibility and SEO. Describe what the image shows in context.",
            'missing_alt_linked': "Add alt text to linked images to provide context about where the link leads.",
            'image_too_large': "Compress images to under 100KB using tools like TinyPNG or WebP format. Consider lazy loading for better performance.",
            'broken_image': "Fix the image URL or replace the missing image. Check file paths and ensure images are properly uploaded.",
            
            # Links & Redirects
            'broken_internal_link': "Fix or remove broken internal links. Update URLs or redirect old pages to relevant alternatives.",
            'broken_external_link': "Update or remove broken external links. Find alternative resources or archive links if content is important.",
            'redirect_chain': "Simplify redirect chains by pointing directly to the final destination. Update internal links to avoid redirects.",
            'redirect_loop': "Fix redirect configuration to prevent infinite loops. Ensure redirects have a clear final destination.",
            'temporary_redirect': "Use 301 permanent redirects for pages that have permanently moved. Keep 302 only for truly temporary moves.",
            'blocked_by_robots': "Review robots.txt to ensure important pages aren't blocked. Only block admin, duplicate, or low-value pages.",
            'internal_nofollow': "Remove nofollow from internal links unless linking to login/admin pages. Internal PageRank flow is important.",
            
            # Structured Data & Directives
            'missing_canonical': "Add a self-referencing canonical tag to establish the preferred version of this page.",
            'conflicting_canonical': "Ensure all canonical signals (tags, redirects, sitemaps) point to the same URL version.",
            'multiple_canonical': "Use only one canonical tag per page. Remove duplicate canonical declarations.",
            'hreflang_missing_return': "Add reciprocal hreflang tags. Each language version should reference all other versions.",
            'hreflang_invalid_code': "Use valid ISO 639-1 language codes and ISO 3166-1 Alpha 2 country codes in hreflang tags.",
            'meta_robots_issue': "Review meta robots tags. Ensure they don't conflict with robots.txt or unintentionally block indexing.",
            
            # Sitemaps & Crawling
            'sitemap_mismatch': "Remove deleted or redirected URLs from the sitemap. Keep it updated with only live, indexable pages.",
            'sitemap_noindex': "Remove noindex pages from the sitemap. Only include pages you want search engines to index.",
            'sitemap_missing': "Add important pages to the XML sitemap to help search engines discover and crawl them.",
            'crawl_depth_issue': "Improve site architecture. Important pages should be accessible within 3 clicks from the homepage.",
            
            # Performance & Other
            'slow_page': "Optimize page speed: compress images, minify CSS/JS, enable caching, use CDN, reduce server response time.",
            'mobile_usability': "Fix mobile issues: ensure text is readable, buttons are tappable, content fits viewport without horizontal scrolling.",
            'mixed_content': "Update all resources to use HTTPS. Replace http:// links with https:// or use protocol-relative URLs.",
            'missing_structured_data': "Add relevant schema markup (JSON-LD preferred) to help search engines understand your content better.",
        }
        return resolutions.get(issue_type, "Review and fix this issue according to SEO best practices.")
