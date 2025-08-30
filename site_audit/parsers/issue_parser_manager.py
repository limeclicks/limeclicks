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
        Save all parsed issues to database with duplicate prevention
        Ensures same issue_type + URL combination is stored only once
        
        Returns:
            Number of issues saved
        """
        from site_audit.models import SiteIssue
        
        if not self.all_issues:
            print("\n⚠️ No issues to save")
            return 0
        
        print(f"\n💾 Saving {len(self.all_issues)} issues to database...")
        
        # Get existing issues for this audit to check for duplicates
        existing_issues = SiteIssue.objects.filter(site_audit=self.site_audit)
        existing_combinations = set()
        
        if existing_issues.exists():
            # Build set of existing (url, issue_type) combinations for fast lookup
            existing_combinations = set(
                existing_issues.values_list('url', 'issue_type')
            )
            print(f"  📋 Found {len(existing_combinations)} existing issue combinations")
        
        # Filter out duplicates from new issues
        unique_issues = []
        duplicate_count = 0
        seen_combinations = set()
        
        for issue_data in self.all_issues:
            url = issue_data.get('url', '')
            issue_type = issue_data.get('issue_type', '')
            combination = (url, issue_type)
            
            # Skip if already exists in database or already seen in this batch
            if combination in existing_combinations or combination in seen_combinations:
                duplicate_count += 1
                continue
            
            unique_issues.append(issue_data)
            seen_combinations.add(combination)
        
        if duplicate_count > 0:
            print(f"  🔍 Skipped {duplicate_count} duplicate issues")
        
        if not unique_issues:
            print("  ℹ️ No new unique issues to save")
            return 0
        
        print(f"  💾 Saving {len(unique_issues)} unique issues...")
        
        # Create SiteIssue objects for unique issues only
        issue_objects = []
        for issue_data in unique_issues:
            issue_objects.append(SiteIssue(**issue_data))
        
        # Bulk create for efficiency
        created_issues = SiteIssue.objects.bulk_create(issue_objects, batch_size=1000)
        
        print(f"  ✅ Successfully saved {len(created_issues)} new issues")
        if duplicate_count > 0:
            print(f"  🔄 Prevented {duplicate_count} duplicates")
        
        # Update site audit statistics
        self._update_site_audit_stats()
        
        return len(created_issues)
    
    def _update_site_audit_stats(self):
        """Update site audit model with issue statistics"""
        from django.db.models import Count
        from site_audit.models import SiteIssue
        
        # Get total issue count
        total_issues = SiteIssue.objects.filter(site_audit=self.site_audit).count()
        
        # Don't calculate health score here - it's calculated from issues_overview.csv
        # The overview-based calculation considers issue priority (High/Medium/Low)
        # which is more accurate than just counting individual issue instances
        
        # Set audit as completed
        self.site_audit.status = 'completed'
        
        self.site_audit.save()
        
        print(f"\n📊 Site Audit Statistics Updated:")
        print(f"  • Total Issues: {total_issues}")
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