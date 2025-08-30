"""Manager class to coordinate all issue parsers"""

import os
from typing import Dict, List, Any
from .issue_parsers import (
    MetaContentParser,
    ResponseCodeParser,
    ImageParser,
    TechnicalSEOParser,
    ContentQualityParser,
    SecurityParser
)


class IssueParserManager:
    """Manages and coordinates all issue parsers"""
    
    def __init__(self, output_dir: str, site_audit):
        """
        Initialize the parser manager
        
        Args:
            output_dir: Path to Screaming Frog output directory
            site_audit: SiteAudit model instance
        """
        self.output_dir = output_dir
        self.site_audit = site_audit
        self.parsers = {
            'meta_content': MetaContentParser(output_dir, site_audit),
            'response_code': ResponseCodeParser(output_dir, site_audit),
            'image': ImageParser(output_dir, site_audit),
            'technical_seo': TechnicalSEOParser(output_dir, site_audit),
            'content_quality': ContentQualityParser(output_dir, site_audit),
            'security': SecurityParser(output_dir, site_audit)
        }
        self.all_issues = []
        self.issue_counts = {}
        
    def parse_all_issues(self) -> Dict[str, Any]:
        """
        Parse all issues from CSV files using all parsers
        
        Returns:
            Dictionary with parsing results and statistics
        """
        print(f"\n📊 Starting issue parsing from: {self.output_dir}")
        print("=" * 60)
        
        total_issues = 0
        issues_by_category = {}
        issues_by_severity = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0,
            'info': 0
        }
        
        # Process each parser
        for parser_name, parser in self.parsers.items():
            print(f"\n🔍 Running {parser_name.replace('_', ' ').title()} Parser...")
            print("-" * 40)
            
            try:
                issues = parser.parse()
                issue_count = len(issues)
                
                if issue_count > 0:
                    self.all_issues.extend(issues)
                    issues_by_category[parser_name] = issue_count
                    total_issues += issue_count
                    
                    # Count by severity
                    for issue in issues:
                        severity = issue.get('severity', 'info')
                        issues_by_severity[severity] += 1
                    
                    print(f"  ✅ Found {issue_count} issues")
                else:
                    print(f"  ℹ️ No issues found")
                    
            except Exception as e:
                print(f"  ❌ Error: {e}")
                issues_by_category[parser_name] = 0
        
        # Print summary
        print("\n" + "=" * 60)
        print("📈 PARSING SUMMARY")
        print("=" * 60)
        
        print(f"\n📊 Total Issues Found: {total_issues}")
        
        print("\n📂 Issues by Category:")
        for category, count in issues_by_category.items():
            if count > 0:
                print(f"  • {category.replace('_', ' ').title()}: {count}")
        
        print("\n🚨 Issues by Severity:")
        for severity, count in issues_by_severity.items():
            if count > 0:
                emoji = {
                    'critical': '🔴',
                    'high': '🟠',
                    'medium': '🟡',
                    'low': '🔵',
                    'info': 'ℹ️'
                }.get(severity, '•')
                print(f"  {emoji} {severity.capitalize()}: {count}")
        
        return {
            'total_issues': total_issues,
            'issues_by_category': issues_by_category,
            'issues_by_severity': issues_by_severity,
            'all_issues': self.all_issues
        }
    
    def save_all_issues(self) -> int:
        """
        Save all parsed issues to database with lifecycle tracking
        Tracks new, persisting, and resolved issues across audits
        
        Returns:
            Number of issues saved
        """
        from site_audit.models import SiteIssue, SiteAudit
        from django.utils import timezone
        
        if not self.all_issues:
            print("\n⚠️ No issues to save")
            return 0
        
        print(f"\n💾 Processing {len(self.all_issues)} issues with lifecycle tracking...")
        
        # Get the previous audit for this project (if exists)
        previous_audit = SiteAudit.objects.filter(
            project=self.site_audit.project,
            status='completed',
            id__lt=self.site_audit.id  # Audits before this one
        ).order_by('-id').first()
        
        # Get existing issues from previous audit
        previous_issues_map = {}
        if previous_audit:
            print(f"  📊 Found previous audit #{previous_audit.id}")
            previous_issues = SiteIssue.objects.filter(
                site_audit=previous_audit
            ).exclude(status='resolved')  # Don't include already resolved issues
            
            # Create a map of (url, issue_type) -> issue for fast lookup
            for issue in previous_issues:
                key = (issue.url, issue.issue_type)
                previous_issues_map[key] = issue
            print(f"  📋 Found {len(previous_issues_map)} active issues from previous audit")
        else:
            print("  ℹ️ No previous audit found - all issues will be marked as new")
        
        # Process current issues
        issues_to_create = []
        issues_to_update = []
        current_issue_keys = set()
        
        new_count = 0
        persisting_count = 0
        
        for issue_data in self.all_issues:
            url = issue_data.get('url', '')
            issue_type = issue_data.get('issue_type', '')
            key = (url, issue_type)
            current_issue_keys.add(key)
            
            # Check if this issue existed in previous audit
            if key in previous_issues_map:
                # Issue is persisting - create new record linked to current audit
                issue_data['status'] = 'persisting'
                issue_data['first_detected_audit'] = previous_issues_map[key].first_detected_audit or previous_audit
                persisting_count += 1
            else:
                # New issue
                issue_data['status'] = 'new'
                issue_data['first_detected_audit'] = self.site_audit
                new_count += 1
            
            issues_to_create.append(SiteIssue(**issue_data))
        
        # Mark issues from previous audit as resolved if not in current audit
        resolved_count = 0
        if previous_audit and previous_issues_map:
            resolved_issues = []
            for key, prev_issue in previous_issues_map.items():
                if key not in current_issue_keys:
                    # Issue has been resolved - create a resolved record
                    resolved_issue_data = {
                        'site_audit': self.site_audit,
                        'url': prev_issue.url,
                        'issue_type': prev_issue.issue_type,
                        'issue_category': prev_issue.issue_category,
                        'severity': prev_issue.severity,
                        'issue_data': prev_issue.issue_data,
                        'indexability': prev_issue.indexability,
                        'indexability_status': prev_issue.indexability_status,
                        'inlinks_count': prev_issue.inlinks_count,
                        'status': 'resolved',
                        'first_detected_audit': prev_issue.first_detected_audit or previous_audit,
                        'resolved_at': timezone.now()
                    }
                    resolved_issues.append(SiteIssue(**resolved_issue_data))
                    resolved_count += 1
            
            if resolved_issues:
                issues_to_create.extend(resolved_issues)
        
        # Bulk create all issues
        if issues_to_create:
            created_issues = SiteIssue.objects.bulk_create(issues_to_create, batch_size=1000)
            print(f"  ✅ Saved {len(created_issues)} total issue records")
        else:
            created_issues = []
        
        # Print summary
        print(f"\n📊 Issue Lifecycle Summary:")
        print(f"  🆕 New Issues: {new_count}")
        print(f"  🔄 Persisting Issues: {persisting_count}")
        print(f"  ✅ Resolved Issues: {resolved_count}")
        
        # Update site audit statistics
        self._update_site_audit_stats()
        
        return len(created_issues)
    
    def _update_site_audit_stats(self):
        """Update site audit model with issue statistics"""
        from django.db.models import Count
        from site_audit.models import SiteIssue
        import os
        import csv
        
        # Get total issue count
        total_issues = SiteIssue.objects.filter(site_audit=self.site_audit).count()
        
        # Try to get pages crawled from crawl_overview.csv
        crawl_overview_path = os.path.join(os.path.dirname(self.output_dir), 'crawl_overview.csv')
        if os.path.exists(crawl_overview_path):
            try:
                with open(crawl_overview_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if len(row) >= 2 and row[0] == 'Total Internal URLs':
                            self.site_audit.total_pages_crawled = int(row[1])
                            break
            except Exception as e:
                print(f"  ⚠️ Could not read pages crawled: {e}")
        
        # Calculate health score from database issues
        self.site_audit.calculate_overall_score()
        
        # Set audit as completed
        self.site_audit.status = 'completed'
        
        self.site_audit.save()
        
        print(f"\n📊 Site Audit Statistics Updated:")
        print(f"  • Total Issues: {total_issues}")
        print(f"  • Pages Crawled: {self.site_audit.total_pages_crawled}")
        print(f"  • Health Score: {self.site_audit.overall_site_health_score}%")
    
    def get_issue_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all parsed issues
        
        Returns:
            Dictionary with issue summary statistics
        """
        from django.db.models import Count
        from site_audit.models import SiteIssue
        
        # Get issues from database
        issues = SiteIssue.objects.filter(site_audit=self.site_audit)
        
        # Count by category
        category_counts = issues.values('issue_category').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Count by severity
        severity_counts = issues.values('severity').annotate(
            count=Count('id')
        ).order_by('severity')
        
        # Count by type (top 10)
        type_counts = issues.values('issue_type').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Get pages with most issues
        url_counts = issues.values('url').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return {
            'total_issues': issues.count(),
            'by_category': list(category_counts),
            'by_severity': list(severity_counts),
            'top_issue_types': list(type_counts),
            'pages_with_most_issues': list(url_counts)
        }