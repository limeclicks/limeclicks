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
    overview = models.JSONField(
        default=list,
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
    
    def update_from_csv_overview(self, csv_file_path):
        """Update overview from issues_overview_report.csv"""
        overview_data = []
        
        if os.path.exists(csv_file_path):
            try:
                with open(csv_file_path, 'r', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    
                    for row in reader:
                        # Extract required fields
                        issue_data = {
                            'issue_name': row.get('Issue Name', '').strip(),
                            'issue_type': row.get('Issue Type', '').strip(),
                            'issue_priority': row.get('Issue Priority', '').strip(),
                            'urls': row.get('URLs', '').strip()
                        }
                        
                        # Only add if we have valid data
                        if issue_data['issue_name'] and issue_data['issue_priority']:
                            overview_data.append(issue_data)
                
                # Sort by priority: High, Medium, Low
                priority_order = {'High': 1, 'Medium': 2, 'Low': 3}
                overview_data.sort(key=lambda x: priority_order.get(x['issue_priority'], 4))
                
                # Update the overview field
                self.overview = overview_data
                self.last_audit_date = timezone.now()
                self.status = 'completed'
                self.save()
                
                return len(overview_data)
                
            except Exception as e:
                self.status = 'failed'
                self.save()
                raise e
        
        return 0
    
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
            
            # Update overall score based on overview data
            self.calculate_overall_score()
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
        """Calculate overall site health score based on overview issues"""
        if not self.overview or not self.total_pages_crawled:
            self.overall_site_health_score = 100
            return
        
        # Count issues by priority
        high_issues = len([i for i in self.overview if i.get('issue_priority') == 'High'])
        medium_issues = len([i for i in self.overview if i.get('issue_priority') == 'Medium'])
        low_issues = len([i for i in self.overview if i.get('issue_priority') == 'Low'])
        
        # Calculate weighted issue score (High=3, Medium=2, Low=1)
        weighted_issues = (high_issues * 3) + (medium_issues * 2) + (low_issues * 1)
        
        # Calculate technical health based on issues per page
        if self.total_pages_crawled > 0:
            issues_per_page = weighted_issues / self.total_pages_crawled
            technical_health = max(0, min(100, 100 - (issues_per_page * 10)))
        else:
            technical_health = 100 if weighted_issues == 0 else 0
        
        # Get average performance score
        performance_scores = []
        if self.performance_score_mobile is not None:
            performance_scores.append(self.performance_score_mobile)
        if self.performance_score_desktop is not None:
            performance_scores.append(self.performance_score_desktop)
        
        avg_performance = sum(performance_scores) / len(performance_scores) if performance_scores else 50
        
        # Calculate combined score (60% technical SEO + 40% performance)
        self.overall_site_health_score = (technical_health * 0.6) + (avg_performance * 0.4)
    
    def get_total_issues_count(self):
        """Get total number of issues from overview"""
        return len(self.overview) if self.overview else 0
    
    def get_issues_by_priority(self):
        """Get breakdown of issues by priority"""
        if not self.overview:
            return {'High': 0, 'Medium': 0, 'Low': 0}
        
        breakdown = {'High': 0, 'Medium': 0, 'Low': 0}
        for issue in self.overview:
            priority = issue.get('issue_priority', '')
            if priority in breakdown:
                breakdown[priority] += 1
        
        return breakdown