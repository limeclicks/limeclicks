"""
Issue Manager for Site Audit

Handles the creation, update, and management of site issues
with proper deletion of old issues and creation of new ones.
"""

from django.db import transaction
from .models import SiteIssue, OnPagePerformanceHistory
from .issue_templates import get_issue_template
import logging

logger = logging.getLogger(__name__)


class IssueManager:
    """Manages site audit issues with proper lifecycle"""
    
    def __init__(self, performance_history: OnPagePerformanceHistory):
        self.performance_history = performance_history
        self.audit = performance_history.audit
        self.project = self.audit.project
    
    @transaction.atomic
    def update_issues(self, new_issues_data: list):
        """
        Replace old issues with new ones for this audit.
        This ensures we always have fresh, accurate data.
        
        Args:
            new_issues_data: List of dicts with issue information
        """
        # Delete all existing issues for this performance history
        deleted_count = SiteIssue.objects.filter(
            performance_history=self.performance_history
        ).delete()[0]
        
        logger.info(f"Deleted {deleted_count} old issues for {self.project.domain}")
        
        # Create new issues
        created_issues = []
        issue_counts = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0,
            'info': 0
        }
        
        for issue_data in new_issues_data:
            issue = self._create_issue(issue_data)
            if issue:
                created_issues.append(issue)
                issue_counts[issue.severity] += 1
        
        # Bulk create all issues
        if created_issues:
            SiteIssue.objects.bulk_create(created_issues, batch_size=100)
            logger.info(f"Created {len(created_issues)} new issues for {self.project.domain}")
        
        # Update audit summary counts
        self._update_audit_counts(issue_counts, len(created_issues))
        
        return created_issues
    
    def _create_issue(self, issue_data: dict) -> SiteIssue:
        """Create a single issue from data"""
        issue_type = issue_data.get('type')
        if not issue_type:
            return None
        
        # Get template for this issue type
        template = get_issue_template(issue_type)
        
        # Create issue object (don't save yet)
        issue = SiteIssue(
            performance_history=self.performance_history,
            issue_type=issue_type,
            severity=template.get('severity', 'medium'),
            page_url=issue_data.get('url', ''),
            page_title=issue_data.get('title', ''),
            description=template.get('description', issue_data.get('description', '')),
            recommendation=template.get('resolution', ''),
            status_code=issue_data.get('status_code'),
            response_time_ms=issue_data.get('response_time'),
            page_size_bytes=issue_data.get('page_size'),
            duplicate_urls=issue_data.get('duplicate_urls'),
            similarity_score=issue_data.get('similarity_score'),
            source_url=issue_data.get('source_url'),
            anchor_text=issue_data.get('anchor_text')
        )
        
        return issue
    
    def _update_audit_counts(self, issue_counts: dict, total_issues: int):
        """Update audit model with issue counts"""
        # Count specific issue types from the created issues
        all_issues = SiteIssue.objects.filter(
            performance_history=self.performance_history
        )
        
        self.audit.total_issues_count = total_issues
        self.audit.broken_links_count = all_issues.filter(
            issue_type__in=['broken_internal_link', 'broken_external_link', 'broken_image']
        ).count()
        self.audit.missing_titles_count = all_issues.filter(
            issue_type='missing_title'
        ).count()
        self.audit.duplicate_titles_count = all_issues.filter(
            issue_type='duplicate_title'
        ).count()
        self.audit.missing_meta_descriptions_count = all_issues.filter(
            issue_type='missing_meta_description'
        ).count()
        self.audit.duplicate_meta_descriptions_count = all_issues.filter(
            issue_type='duplicate_meta_description'
        ).count()
        self.audit.redirect_chains_count = all_issues.filter(
            issue_type__in=['redirect_chain', 'redirect_loop']
        ).count()
        
        # Update overall health score based on issues
        if self.audit.total_pages_crawled > 0:
            issues_per_page = total_issues / self.audit.total_pages_crawled
            # More issues = lower health score
            health_score = max(0, min(100, 100 - (issues_per_page * 20)))
            self.audit.overall_site_health_score = int(health_score)
        else:
            self.audit.overall_site_health_score = 100 if total_issues == 0 else 50
        
        self.audit.save()
        logger.info(f"Updated audit counts for {self.project.domain}: {total_issues} total issues, health: {self.audit.overall_site_health_score}%")
    
    @classmethod
    def create_test_issues(cls, performance_history: OnPagePerformanceHistory):
        """Create comprehensive test issues for development/testing"""
        test_issues = [
            # Critical Issues
            {'type': 'missing_title', 'url': f'https://{performance_history.audit.project.domain}/page1'},
            {'type': 'missing_title', 'url': f'https://{performance_history.audit.project.domain}/page2'},
            {'type': 'duplicate_title', 'url': f'https://{performance_history.audit.project.domain}/page3'},
            {'type': 'missing_meta_description', 'url': f'https://{performance_history.audit.project.domain}/page4'},
            {'type': 'broken_internal_link', 'url': f'https://{performance_history.audit.project.domain}/page5', 'source_url': '/blog/post1'},
            
            # High Priority Issues
            {'type': 'title_too_long', 'url': f'https://{performance_history.audit.project.domain}/page6'},
            {'type': 'meta_description_too_long', 'url': f'https://{performance_history.audit.project.domain}/page7'},
            {'type': 'missing_h1', 'url': f'https://{performance_history.audit.project.domain}/page8'},
            {'type': 'duplicate_h1', 'url': f'https://{performance_history.audit.project.domain}/page9'},
            {'type': 'missing_canonical', 'url': f'https://{performance_history.audit.project.domain}/page10'},
            
            # Medium Priority Issues
            {'type': 'thin_content', 'url': f'https://{performance_history.audit.project.domain}/blog/post1'},
            {'type': 'missing_alt_text', 'url': f'https://{performance_history.audit.project.domain}/gallery'},
            {'type': 'redirect_chain', 'url': f'https://{performance_history.audit.project.domain}/old-page'},
            
            # Low Priority Issues
            {'type': 'missing_structured_data', 'url': f'https://{performance_history.audit.project.domain}/products'},
            
            # Info Issues
            {'type': 'external_nofollow', 'url': f'https://{performance_history.audit.project.domain}/links'},
        ]
        
        manager = cls(performance_history)
        return manager.update_issues(test_issues)