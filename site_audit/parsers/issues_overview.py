"""
Parser for Screaming Frog's issues_overview_report.csv file.
Extracts Issue Name, Issue Type, Issue Priority, and URLs from the report.
"""
import csv
import os
from pathlib import Path
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class IssuesOverviewParser:
    """Parser for Screaming Frog's issues overview report."""
    
    # Priority order mapping for sorting (lower number = higher priority)
    # Only includes Issue Priority values (High, Medium, Low)
    # Issue Type values (Issue, Opportunity, Warning) are separate and not used for sorting
    PRIORITY_ORDER = {
        'High': 1,
        'Medium': 2,
        'Low': 3
    }
    
    def __init__(self, temp_audit_dir, site_audit=None):
        """
        Initialize the parser with the temp audit directory.
        
        Args:
            temp_audit_dir: Path to the Screaming Frog output directory
            site_audit: Optional SiteAudit instance to save data to
        """
        self.temp_audit_dir = temp_audit_dir
        self.site_audit = site_audit
        self.issues_report_file = None
        
        # Find the issues_overview_report.csv file
        if temp_audit_dir:
            issues_reports_dir = Path(temp_audit_dir) / 'issues_reports'
            issues_file = issues_reports_dir / 'issues_overview_report.csv'
            
            if issues_file.exists():
                self.issues_report_file = issues_file
                logger.info(f"Found issues_overview_report.csv at {issues_file}")
            else:
                logger.warning(f"issues_overview_report.csv not found at {issues_file}")
    
    def parse(self):
        """
        Parse issues_overview_report.csv and extract required fields.
        Sorts issues from High to Low priority.
        If site_audit is provided, also saves the data to the model.
        
        Returns:
            dict: Parsed and sorted issues data
        """
        if not self.issues_report_file:
            logger.warning("No issues_overview_report.csv file to parse")
            return {}
        
        issues_data = {
            'issues': [],
            'total_issues': 0,
            'issues_by_priority': {
                'High': 0,
                'Medium': 0,
                'Low': 0
            },
            'issues_by_type': {
                'Issue': 0,
                'Opportunity': 0,
                'Warning': 0
            }
        }
        
        try:
            with open(self.issues_report_file, 'r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                
                issues_list = []
                for row in reader:
                    issue = {
                        'issue_name': row.get('Issue Name', '').strip(),
                        'issue_type': row.get('Issue Type', '').strip(),
                        'issue_priority': row.get('Issue Priority', '').strip(),
                        'urls': int(row.get('URLs', 0)) if row.get('URLs', '').isdigit() else 0,
                        'percentage': row.get('% of Total', '').strip(),
                        'description': row.get('Description', '').strip(),
                        'how_to_fix': row.get('How To Fix', '').strip()
                    }
                    
                    # Skip empty rows
                    if issue['issue_name']:
                        issues_list.append(issue)
                        
                        # Count issues by priority
                        priority = issue['issue_priority']
                        if priority in issues_data['issues_by_priority']:
                            issues_data['issues_by_priority'][priority] += 1
                        
                        # Count issues by type
                        issue_type = issue['issue_type']
                        if issue_type in issues_data['issues_by_type']:
                            issues_data['issues_by_type'][issue_type] += 1
                
                # Sort issues by priority (High to Low)
                sorted_issues = sorted(
                    issues_list,
                    key=lambda x: (
                        self.PRIORITY_ORDER.get(x['issue_priority'], 999),
                        -x['urls']  # Secondary sort by URL count (descending)
                    )
                )
                
                issues_data['issues'] = sorted_issues
                issues_data['total_issues'] = len(sorted_issues)
                
                logger.info(f"Parsed {len(sorted_issues)} issues from issues_overview_report.csv")
                logger.info(f"Issues by priority: {issues_data['issues_by_priority']}")
                
        except Exception as e:
            logger.error(f"Error parsing issues_overview_report.csv: {e}")
            return issues_data
        
        # Save to site_audit if provided
        if self.site_audit and issues_data:
            try:
                self.site_audit.issues_overview = issues_data
                print(f"📊 Issues overview set: {issues_data.get('issues_by_priority', {})}")
                
                # Calculate the overall health score immediately after parsing issues
                print(f"📊 Calculating health score...")
                self.site_audit.calculate_overall_score()
                print(f"📊 Health score calculated: {self.site_audit.overall_site_health_score}")
                
                # Need to update status too since it needs to be completed
                self.site_audit.status = 'completed'
                
                # Explicitly save all fields including the health score and status
                self.site_audit.save(update_fields=['issues_overview', 'overall_site_health_score', 'status'])
                print(f"📊 Saved to DB with health score: {self.site_audit.overall_site_health_score} and status: {self.site_audit.status}")
                logger.info(f"Saved issues overview data to SiteAudit {self.site_audit.id} with health score: {self.site_audit.overall_site_health_score}")
                
            except Exception as e:
                logger.error(f"Error saving issues overview to SiteAudit: {e}")
                print(f"❌ Error in issues_overview parser: {e}")
                import traceback
                traceback.print_exc()
        
        return issues_data