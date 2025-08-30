"""Parser for image-related issues"""

from .base_parser import BaseIssueParser
from typing import List, Dict, Any


class ImageParser(BaseIssueParser):
    """Parser for image related issues"""
    
    # CSV files this parser handles
    CSV_FILES = {
        'images_missing_alt_text.csv': 'missing_alt_text',
        'images_missing_alt_attribute.csv': 'missing_alt_attribute', 
        'images_over_100_kb.csv': 'large_image',
        'images_with_nofollow.csv': 'image_with_nofollow',
        'images_internal_missing.csv': 'missing_image'
    }
    
    def parse(self) -> List[Dict[str, Any]]:
        """Parse all image CSV files"""
        
        for csv_file, issue_type in self.CSV_FILES.items():
            print(f"  📄 Parsing {csv_file}...")
            self._parse_image_issues(csv_file, issue_type)
                
        return self.issues
    
    def _parse_image_issues(self, filename: str, issue_type: str):
        """Parse image issues"""
        rows = self.read_csv(filename)
        
        for row in rows:
            # Different CSV files have different URL columns
            url = row.get('Address', '') or row.get('Source', '') or row.get('Destination', '')
            if not url:
                continue
                
            issue_data = {}
            
            # Parse based on issue type
            if issue_type in ['missing_alt_text', 'missing_alt_attribute']:
                issue_data = {
                    'image_url': row.get('Destination', ''),
                    'source_page': row.get('Source', ''),
                    'alt_text': row.get('Alt Text', ''),
                    'occurrences': int(row.get('Occurrences', 1)) if row.get('Occurrences') else 1
                }
                
            elif issue_type == 'large_image':
                issue_data = {
                    'image_url': url,
                    'size_bytes': int(row.get('Size (Bytes)', 0)) if row.get('Size (Bytes)') else 0,
                    'size_kb': float(row.get('Size', 0)) if row.get('Size') else 0,
                    'type': row.get('Type', ''),
                    'inlinks': int(row.get('Inlinks', 0)) if row.get('Inlinks') else 0
                }
                
            elif issue_type == 'image_with_nofollow':
                issue_data = {
                    'image_url': row.get('Destination', ''),
                    'source_page': row.get('Source', ''),
                    'link_path': row.get('Link Path', ''),
                    'anchor': row.get('Anchor', ''),
                    'status_code': int(row.get('Status Code', 0)) if row.get('Status Code') else 0
                }
                
            elif issue_type == 'missing_image':
                issue_data = {
                    'image_url': url,
                    'status_code': int(row.get('Status Code', 404)) if row.get('Status Code') else 404,
                    'status': row.get('Status', 'Not Found'),
                    'inlinks': int(row.get('Inlinks', 0)) if row.get('Inlinks') else 0,
                    'source_pages': row.get('From', '').split('|') if row.get('From') else []
                }
                
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='image',
                issue_data=issue_data,
                indexability=row.get('Indexability', ''),
                indexability_status=row.get('Indexability Status', ''),
                inlinks_count=int(row.get('Inlinks', 0)) if row.get('Inlinks') else 0
            ))