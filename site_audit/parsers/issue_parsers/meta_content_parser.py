"""Parser for meta content issues (titles, meta descriptions, headers)"""

from .base_parser import BaseIssueParser
from typing import List, Dict, Any


class MetaContentParser(BaseIssueParser):
    """Parser for meta content related issues"""
    
    # CSV files this parser handles (updated to match actual file names)
    CSV_FILES = {
        'page_titles_missing.csv': 'missing_title',
        'page_titles_duplicate.csv': 'duplicate_title',
        'page_titles_over_60_characters.csv': 'title_too_long',
        'page_titles_over_561_pixels.csv': 'title_too_long_pixels',
        'page_titles_below_30_characters.csv': 'title_too_short',
        'page_titles_below_200_pixels.csv': 'title_too_short_pixels',
        'page_titles_same_as_h1.csv': 'title_same_as_h1',
        'meta_description_missing.csv': 'missing_meta_description',
        'meta_description_duplicate.csv': 'duplicate_meta_description',
        'meta_description_over_155_characters.csv': 'meta_too_long',
        'meta_description_over_985_pixels.csv': 'meta_too_long_pixels',
        'meta_description_below_70_characters.csv': 'meta_too_short',
        'meta_description_below_400_pixels.csv': 'meta_too_short_pixels',
        'h1_missing.csv': 'missing_h1',
        'h1_duplicate.csv': 'duplicate_h1',
        'h1_multiple.csv': 'multiple_h1',
        'h2_missing.csv': 'missing_h2',
        'h2_duplicate.csv': 'duplicate_h2',
        'h2_multiple.csv': 'multiple_h2'
    }
    
    def parse(self) -> List[Dict[str, Any]]:
        """Parse all meta content CSV files"""
        
        for csv_file, issue_type in self.CSV_FILES.items():
            print(f"  📄 Parsing {csv_file}...")
            
            if 'title' in csv_file:
                self._parse_title_issues(csv_file, issue_type)
            elif 'meta_description' in csv_file:
                self._parse_meta_description_issues(csv_file, issue_type)
            elif 'h1' in csv_file:
                self._parse_h1_issues(csv_file, issue_type)
            elif 'h2' in csv_file:
                self._parse_h2_issues(csv_file, issue_type)
                
        return self.issues
    
    def _parse_title_issues(self, filename: str, issue_type: str):
        """Parse title-related issues"""
        rows = self.read_csv(filename)
        
        for row in rows:
            url = row.get('Address', '')
            if not url:
                continue
                
            issue_data = {
                'content': row.get('Title 1', ''),
                'length': int(row.get('Title 1 Length', 0)) if row.get('Title 1 Length') else 0,
                'pixel_width': int(row.get('Title 1 Pixel Width', 0)) if row.get('Title 1 Pixel Width') else 0,
                'occurrences': int(row.get('Occurrences', 1)) if row.get('Occurrences') else 1
            }
            
            # For duplicate titles, add duplicate URLs
            if issue_type == 'duplicate_title' and row.get('Duplicate Addresses'):
                issue_data['duplicates'] = row.get('Duplicate Addresses', '').split('|')
                
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='meta_content',
                issue_data=issue_data,
                indexability=row.get('Indexability', ''),
                indexability_status=row.get('Indexability Status', '')
            ))
    
    def _parse_meta_description_issues(self, filename: str, issue_type: str):
        """Parse meta description issues"""
        rows = self.read_csv(filename)
        
        for row in rows:
            url = row.get('Address', '')
            if not url:
                continue
                
            issue_data = {
                'content': row.get('Meta Description 1', ''),
                'length': int(row.get('Meta Description 1 Length', 0)) if row.get('Meta Description 1 Length') else 0,
                'pixel_width': int(row.get('Meta Description 1 Pixel Width', 0)) if row.get('Meta Description 1 Pixel Width') else 0,
                'occurrences': int(row.get('Occurrences', 1)) if row.get('Occurrences') else 1
            }
            
            # For duplicate meta descriptions
            if issue_type == 'duplicate_meta_description' and row.get('Duplicate Addresses'):
                issue_data['duplicates'] = row.get('Duplicate Addresses', '').split('|')
                
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='meta_content',
                issue_data=issue_data,
                indexability=row.get('Indexability', ''),
                indexability_status=row.get('Indexability Status', '')
            ))
    
    def _parse_h1_issues(self, filename: str, issue_type: str):
        """Parse H1 heading issues"""
        rows = self.read_csv(filename)
        
        for row in rows:
            url = row.get('Address', '')
            if not url:
                continue
                
            issue_data = {
                'content': row.get('H1-1', ''),
                'length': int(row.get('H1-1 Length', 0)) if row.get('H1-1 Length') else 0,
                'occurrences': int(row.get('Occurrences', 1)) if row.get('Occurrences') else 1
            }
            
            # For multiple H1s
            if issue_type == 'multiple_h1':
                h1_list = []
                for i in range(1, 10):  # Check up to 9 H1s
                    h1_key = f'H1-{i}'
                    if h1_key in row and row[h1_key]:
                        h1_list.append(row[h1_key])
                issue_data['all_h1s'] = h1_list
                
            # For duplicate H1s
            if issue_type == 'duplicate_h1' and row.get('Duplicate Addresses'):
                issue_data['duplicates'] = row.get('Duplicate Addresses', '').split('|')
                
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='meta_content',
                issue_data=issue_data,
                indexability=row.get('Indexability', ''),
                indexability_status=row.get('Indexability Status', '')
            ))
    
    def _parse_h2_issues(self, filename: str, issue_type: str):
        """Parse H2 heading issues"""
        rows = self.read_csv(filename)
        
        for row in rows:
            url = row.get('Address', '')
            if not url:
                continue
                
            issue_data = {
                'content': row.get('H2-1', ''),
                'length': int(row.get('H2-1 Length', 0)) if row.get('H2-1 Length') else 0,
                'occurrences': int(row.get('Occurrences', 0)) if row.get('Occurrences') else 0
            }
            
            # For duplicate H2s
            if issue_type == 'duplicate_h2' and row.get('Duplicate Addresses'):
                issue_data['duplicates'] = row.get('Duplicate Addresses', '').split('|')
                
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='meta_content',
                issue_data=issue_data,
                indexability=row.get('Indexability', ''),
                indexability_status=row.get('Indexability Status', '')
            ))