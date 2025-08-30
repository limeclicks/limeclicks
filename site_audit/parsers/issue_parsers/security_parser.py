"""Parser for security-related issues"""

from .base_parser import BaseIssueParser
from typing import List, Dict, Any


class SecurityParser(BaseIssueParser):
    """Parser for security related issues"""
    
    # CSV files this parser handles
    CSV_FILES = {
        'security_mixed_content.csv': 'mixed_content',
        'security_insecure_forms.csv': 'insecure_form',
        'security_http_urls.csv': 'http_url',
        'security_missing_hsts.csv': 'missing_hsts',
        'security_missing_x_content_type_options.csv': 'missing_x_content_type',
        'security_missing_x_frame_options.csv': 'missing_x_frame',
        'security_missing_csp.csv': 'missing_csp'
    }
    
    def parse(self) -> List[Dict[str, Any]]:
        """Parse all security CSV files"""
        
        for csv_file, issue_type in self.CSV_FILES.items():
            print(f"  📄 Parsing {csv_file}...")
            
            if 'mixed_content' in csv_file:
                self._parse_mixed_content_issues(csv_file, issue_type)
            elif 'insecure_forms' in csv_file:
                self._parse_insecure_form_issues(csv_file, issue_type)
            elif 'http_urls' in csv_file:
                self._parse_http_url_issues(csv_file, issue_type)
            else:
                self._parse_security_header_issues(csv_file, issue_type)
                
        return self.issues
    
    def _parse_mixed_content_issues(self, filename: str, issue_type: str):
        """Parse mixed content issues (HTTPS pages loading HTTP resources)"""
        rows = self.read_csv(filename)
        
        for row in rows:
            url = row.get('Address', '') or row.get('Source', '')
            if not url:
                continue
                
            issue_data = {
                'resource_url': row.get('Resource URL', '') or row.get('Destination', ''),
                'resource_type': row.get('Resource Type', ''),
                'source_protocol': row.get('Source Protocol', 'https'),
                'resource_protocol': row.get('Resource Protocol', 'http'),
                'link_path': row.get('Link Path', ''),
                'status_code': int(row.get('Status Code', 0)) if row.get('Status Code') else 0
            }
            
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='security',
                issue_data=issue_data,
                indexability=row.get('Indexability', ''),
                indexability_status=row.get('Indexability Status', ''),
                inlinks_count=int(row.get('Inlinks', 0)) if row.get('Inlinks') else 0
            ))
    
    def _parse_insecure_form_issues(self, filename: str, issue_type: str):
        """Parse insecure form issues (forms submitted over HTTP)"""
        rows = self.read_csv(filename)
        
        for row in rows:
            url = row.get('Address', '')
            if not url:
                continue
                
            issue_data = {
                'form_action': row.get('Form Action', ''),
                'form_method': row.get('Form Method', 'POST'),
                'form_protocol': row.get('Form Protocol', 'http'),
                'page_protocol': row.get('Page Protocol', ''),
                'form_count': int(row.get('Form Count', 1)) if row.get('Form Count') else 1,
                'has_password_field': row.get('Has Password Field', '').lower() == 'true' if row.get('Has Password Field') else False
            }
            
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='security',
                issue_data=issue_data,
                indexability=row.get('Indexability', ''),
                indexability_status=row.get('Indexability Status', ''),
                inlinks_count=int(row.get('Inlinks', 0)) if row.get('Inlinks') else 0
            ))
    
    def _parse_http_url_issues(self, filename: str, issue_type: str):
        """Parse HTTP URL issues (non-secure URLs)"""
        rows = self.read_csv(filename)
        
        for row in rows:
            url = row.get('Address', '')
            if not url:
                continue
                
            issue_data = {
                'protocol': 'http',
                'status_code': int(row.get('Status Code', 0)) if row.get('Status Code') else 0,
                'redirect_url': row.get('Redirect URL', ''),
                'content_type': row.get('Content Type', ''),
                'has_forms': row.get('Has Forms', '').lower() == 'true' if row.get('Has Forms') else False,
                'has_sensitive_data': row.get('Has Sensitive Data', '').lower() == 'true' if row.get('Has Sensitive Data') else False
            }
            
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='security',
                issue_data=issue_data,
                indexability=row.get('Indexability', ''),
                indexability_status=row.get('Indexability Status', ''),
                inlinks_count=int(row.get('Inlinks', 0)) if row.get('Inlinks') else 0
            ))
    
    def _parse_security_header_issues(self, filename: str, issue_type: str):
        """Parse missing security header issues"""
        rows = self.read_csv(filename)
        
        for row in rows:
            url = row.get('Address', '')
            if not url:
                continue
                
            issue_data = {
                'status_code': int(row.get('Status Code', 0)) if row.get('Status Code') else 0,
                'content_type': row.get('Content Type', ''),
                'missing_header': self._get_header_name(issue_type)
            }
            
            # Add specific header details based on issue type
            if issue_type == 'missing_hsts':
                issue_data['header_name'] = 'Strict-Transport-Security'
                issue_data['recommended_value'] = 'max-age=31536000; includeSubDomains'
            elif issue_type == 'missing_x_content_type':
                issue_data['header_name'] = 'X-Content-Type-Options'
                issue_data['recommended_value'] = 'nosniff'
            elif issue_type == 'missing_x_frame':
                issue_data['header_name'] = 'X-Frame-Options'
                issue_data['recommended_value'] = 'SAMEORIGIN'
            elif issue_type == 'missing_csp':
                issue_data['header_name'] = 'Content-Security-Policy'
                issue_data['recommended_value'] = "default-src 'self'"
                
            # Check if any security headers are present
            security_headers = []
            for header in ['Strict-Transport-Security', 'X-Content-Type-Options', 'X-Frame-Options', 'Content-Security-Policy']:
                if row.get(header):
                    security_headers.append({
                        'name': header,
                        'value': row.get(header, '')
                    })
            issue_data['existing_security_headers'] = security_headers
                
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='security',
                issue_data=issue_data,
                indexability=row.get('Indexability', ''),
                indexability_status=row.get('Indexability Status', ''),
                inlinks_count=int(row.get('Inlinks', 0)) if row.get('Inlinks') else 0
            ))
    
    def _get_header_name(self, issue_type: str) -> str:
        """Get the actual header name from issue type"""
        header_map = {
            'missing_hsts': 'Strict-Transport-Security',
            'missing_x_content_type': 'X-Content-Type-Options',
            'missing_x_frame': 'X-Frame-Options',
            'missing_csp': 'Content-Security-Policy'
        }
        return header_map.get(issue_type, '')