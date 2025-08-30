"""Parser for response code issues (redirects, errors, etc.)"""

from .base_parser import BaseIssueParser
from typing import List, Dict, Any


class ResponseCodeParser(BaseIssueParser):
    """Parser for response code related issues"""
    
    # CSV files this parser handles
    CSV_FILES = {
        'response_codes_internal_redirection_(3xx).csv': 'internal_redirection_3xx',
        'response_codes_internal_client_error_(4xx).csv': 'internal_client_error_4xx',
        'response_codes_internal_server_error_(5xx).csv': 'internal_server_error_5xx',
        'response_codes_external_redirection_(3xx).csv': 'external_redirection_3xx',
        'response_codes_external_client_error_(4xx).csv': 'external_client_error_4xx',
        'response_codes_external_server_error_(5xx).csv': 'external_server_error_5xx',
        'response_codes_external_no_response.csv': 'external_no_response',
        'response_codes_internal_blocked_by_robots_txt.csv': 'internal_blocked_robots'
    }
    
    def parse(self) -> List[Dict[str, Any]]:
        """Parse all response code CSV files"""
        
        for csv_file, issue_type in self.CSV_FILES.items():
            print(f"  📄 Parsing {csv_file}...")
            self._parse_response_code_issues(csv_file, issue_type)
                
        return self.issues
    
    def _parse_response_code_issues(self, filename: str, issue_type: str):
        """Parse response code issues"""
        rows = self.read_csv(filename)
        
        for row in rows:
            url = row.get('Address', '')
            if not url:
                continue
                
            issue_data = {
                'status_code': int(row.get('Status Code', 0)) if row.get('Status Code') else 0,
                'status_text': row.get('Status', ''),
                'content_type': row.get('Content Type', ''),
                'response_time': float(row.get('Response Time', 0)) if row.get('Response Time') else 0,
                'size_bytes': int(row.get('Size (Bytes)', 0)) if row.get('Size (Bytes)') else 0
            }
            
            # Add redirect information if present
            if '3xx' in issue_type:
                issue_data['redirect_url'] = row.get('Redirect URL', '')
                issue_data['redirect_type'] = row.get('Redirect Type', '')
                
            # Add inlinks information
            if row.get('Inlinks'):
                issue_data['inlinks'] = int(row.get('Inlinks', 0))
                
            # Add source URL for external issues
            if 'external' in issue_type and row.get('Source'):
                issue_data['source_url'] = row.get('Source', '')
                
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='response_code',
                issue_data=issue_data,
                indexability=row.get('Indexability', ''),
                indexability_status=row.get('Indexability Status', ''),
                inlinks_count=int(row.get('Inlinks', 0)) if row.get('Inlinks') else 0
            ))