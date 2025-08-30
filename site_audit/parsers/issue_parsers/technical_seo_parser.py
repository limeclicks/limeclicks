"""Parser for technical SEO issues"""

from .base_parser import BaseIssueParser
from typing import List, Dict, Any


class TechnicalSEOParser(BaseIssueParser):
    """Parser for technical SEO related issues"""
    
    # CSV files this parser handles
    CSV_FILES = {
        'canonical_missing.csv': 'missing_canonical',
        'canonical_non_indexable.csv': 'canonical_non_indexable',
        'canonical_outside_head.csv': 'canonical_outside_head',
        'pagination_noindex.csv': 'pagination_noindex',
        'pagination_canonicalised.csv': 'pagination_canonicalised',
        'pagination_missing.csv': 'pagination_missing',
        'pagination_loop.csv': 'pagination_loop',
        'pagination_sequence_error.csv': 'pagination_sequence_error',
        'pagination_multiple.csv': 'pagination_multiple',
        'hreflang_missing.csv': 'missing_hreflang',
        'hreflang_non_200_status_code.csv': 'hreflang_non_200',
        'hreflang_missing_return_links.csv': 'hreflang_missing_return',
        'hreflang_inconsistent_language_region_return_links.csv': 'hreflang_inconsistent',
        'structured_data_missing.csv': 'missing_structured_data',
        'noindex.csv': 'noindex_page'
    }
    
    def parse(self) -> List[Dict[str, Any]]:
        """Parse all technical SEO CSV files"""
        
        for csv_file, issue_type in self.CSV_FILES.items():
            print(f"  📄 Parsing {csv_file}...")
            
            if 'canonical' in csv_file:
                self._parse_canonical_issues(csv_file, issue_type)
            elif 'pagination' in csv_file:
                self._parse_pagination_issues(csv_file, issue_type)
            elif 'hreflang' in csv_file:
                self._parse_hreflang_issues(csv_file, issue_type)
            elif 'structured_data' in csv_file:
                self._parse_structured_data_issues(csv_file, issue_type)
            elif 'noindex' in csv_file:
                self._parse_noindex_issues(csv_file, issue_type)
                
        return self.issues
    
    def _parse_canonical_issues(self, filename: str, issue_type: str):
        """Parse canonical-related issues"""
        rows = self.read_csv(filename)
        
        for row in rows:
            url = row.get('Address', '')
            if not url:
                continue
                
            issue_data = {
                'canonical_url': row.get('Canonical Link Element 1', ''),
                'indexability': row.get('Indexability', ''),
                'indexability_status': row.get('Indexability Status', '')
            }
            
            # Add specific data for canonical issues
            if issue_type == 'canonical_non_indexable':
                issue_data['canonical_indexability'] = row.get('Canonical Link Element 1 Indexability', '')
                issue_data['canonical_status'] = row.get('Canonical Link Element 1 Indexability Status', '')
                
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='technical_seo',
                issue_data=issue_data,
                indexability=row.get('Indexability', ''),
                indexability_status=row.get('Indexability Status', '')
            ))
    
    def _parse_pagination_issues(self, filename: str, issue_type: str):
        """Parse pagination-related issues"""
        rows = self.read_csv(filename)
        
        for row in rows:
            url = row.get('Address', '')
            if not url:
                continue
                
            issue_data = {
                'pagination_prev': row.get('Pagination Prev', ''),
                'pagination_next': row.get('Pagination Next', ''),
                'indexability': row.get('Indexability', ''),
                'indexability_status': row.get('Indexability Status', '')
            }
            
            # Add sequence error details
            if issue_type == 'pagination_sequence_error':
                issue_data['error_type'] = row.get('Error Type', '')
                issue_data['expected_url'] = row.get('Expected URL', '')
                issue_data['actual_url'] = row.get('Actual URL', '')
                
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='technical_seo',
                issue_data=issue_data,
                indexability=row.get('Indexability', ''),
                indexability_status=row.get('Indexability Status', '')
            ))
    
    def _parse_hreflang_issues(self, filename: str, issue_type: str):
        """Parse hreflang-related issues"""
        rows = self.read_csv(filename)
        
        for row in rows:
            url = row.get('Address', '') or row.get('URL', '')
            if not url:
                continue
                
            issue_data = {
                'hreflang_language': row.get('Language', ''),
                'hreflang_url': row.get('Hreflang URL', ''),
                'status_code': int(row.get('Status Code', 0)) if row.get('Status Code') else 0
            }
            
            # Add return link details
            if 'return' in issue_type:
                issue_data['return_link_url'] = row.get('Return Link URL', '')
                issue_data['return_link_language'] = row.get('Return Link Language', '')
                
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='technical_seo',
                issue_data=issue_data,
                indexability=row.get('Indexability', ''),
                indexability_status=row.get('Indexability Status', '')
            ))
    
    def _parse_structured_data_issues(self, filename: str, issue_type: str):
        """Parse structured data issues"""
        rows = self.read_csv(filename)
        
        for row in rows:
            url = row.get('Address', '')
            if not url:
                continue
                
            issue_data = {
                'structured_data_type': row.get('Type', ''),
                'validation_errors': row.get('Validation Errors', ''),
                'validation_warnings': row.get('Validation Warnings', '')
            }
            
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='technical_seo',
                issue_data=issue_data,
                indexability=row.get('Indexability', ''),
                indexability_status=row.get('Indexability Status', '')
            ))
    
    def _parse_noindex_issues(self, filename: str, issue_type: str):
        """Parse noindex pages"""
        rows = self.read_csv(filename)
        
        for row in rows:
            url = row.get('Address', '')
            if not url:
                continue
                
            issue_data = {
                'meta_robots': row.get('Meta Robots 1', ''),
                'x_robots_tag': row.get('X-Robots-Tag 1', ''),
                'inlinks': int(row.get('Inlinks', 0)) if row.get('Inlinks') else 0
            }
            
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='technical_seo',
                issue_data=issue_data,
                indexability='Non-Indexable',
                indexability_status='Noindex',
                inlinks_count=int(row.get('Inlinks', 0)) if row.get('Inlinks') else 0
            ))