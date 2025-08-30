"""Base parser class for all issue parsers"""

import csv
import os
from typing import List, Dict, Any


class BaseIssueParser:
    """Base class for all issue parsers"""
    
    def __init__(self, output_dir: str, site_audit):
        """
        Initialize parser with output directory and site audit instance
        
        Args:
            output_dir: Path to Screaming Frog output directory
            site_audit: SiteAudit model instance
        """
        self.output_dir = output_dir
        self.site_audit = site_audit
        self.issues = []
        
    def parse(self) -> List[Dict[str, Any]]:
        """
        Parse CSV files and return list of issues
        
        Returns:
            List of issue dictionaries
        """
        raise NotImplementedError("Subclasses must implement parse()")
    
    def read_csv(self, filename: str) -> List[Dict[str, Any]]:
        """
        Read CSV file and return rows as list of dictionaries
        
        Args:
            filename: Name of CSV file to read
            
        Returns:
            List of dictionaries representing CSV rows
        """
        # Try multiple locations for the file
        possible_paths = [
            os.path.join(self.output_dir, 'issues_reports', filename),  # New location
            os.path.join(self.output_dir, filename)  # Original location
        ]
        
        file_path = None
        for path in possible_paths:
            if os.path.exists(path):
                file_path = path
                break
        
        if not file_path:
            print(f"  ⚠️ File not found: {filename}")
            return []
            
        rows = []
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Skip empty rows
                    if any(row.values()):
                        rows.append(row)
        except Exception as e:
            print(f"  ❌ Error reading {filename}: {e}")
            
        return rows
    
    def create_issue(self, 
                    url: str,
                    issue_type: str,
                    issue_category: str,
                    issue_data: Dict[str, Any],
                    indexability: str = '',
                    indexability_status: str = '',
                    inlinks_count: int = 0) -> Dict[str, Any]:
        """
        Create issue dictionary for database insertion
        
        Args:
            url: URL with the issue
            issue_type: Type of issue (e.g., 'missing_title')
            issue_category: Category of issue
            issue_data: Additional data specific to issue type
            indexability: Indexability status
            indexability_status: Indexability status details
            inlinks_count: Number of inlinks
            
        Returns:
            Dictionary representing the issue
        """
        from site_audit.models import SiteIssue
        
        return {
            'site_audit': self.site_audit,
            'url': url,
            'issue_type': issue_type,
            'issue_category': issue_category,
            'severity': SiteIssue.get_severity_for_issue_type(issue_type),
            'issue_data': issue_data,
            'indexability': indexability or '',
            'indexability_status': indexability_status or '',
            'inlinks_count': inlinks_count
        }
    
    def save_issues(self) -> int:
        """
        Save parsed issues to database
        
        Returns:
            Number of issues saved
        """
        from site_audit.models import SiteIssue
        
        if not self.issues:
            return 0
            
        # Create SiteIssue objects
        issue_objects = []
        for issue_data in self.issues:
            issue_objects.append(SiteIssue(**issue_data))
            
        # Bulk create for efficiency
        SiteIssue.objects.bulk_create(issue_objects, batch_size=1000)
        
        return len(issue_objects)