"""Parser for content quality issues"""

from .base_parser import BaseIssueParser
from typing import List, Dict, Any


class ContentQualityParser(BaseIssueParser):
    """Parser for content quality related issues"""
    
    # CSV files this parser handles
    CSV_FILES = {
        'content_low_word_count.csv': 'low_word_count',
        'content_duplicate.csv': 'duplicate_content',
        'content_near_duplicate.csv': 'near_duplicate_content',
        'content_soft_404_pages.csv': 'soft_404',
        'content_readability_difficult.csv': 'readability_difficult',
        'spelling_errors.csv': 'spelling_errors',
        'grammar_errors.csv': 'grammar_errors'
    }
    
    def parse(self) -> List[Dict[str, Any]]:
        """Parse all content quality CSV files"""
        
        for csv_file, issue_type in self.CSV_FILES.items():
            print(f"  📄 Parsing {csv_file}...")
            
            if 'word_count' in csv_file:
                self._parse_word_count_issues(csv_file, issue_type)
            elif 'duplicate' in csv_file:
                self._parse_duplicate_content_issues(csv_file, issue_type)
            elif 'soft_404' in csv_file:
                self._parse_soft_404_issues(csv_file, issue_type)
            elif 'readability' in csv_file:
                self._parse_readability_issues(csv_file, issue_type)
            elif 'spelling' in csv_file or 'grammar' in csv_file:
                self._parse_language_issues(csv_file, issue_type)
                
        return self.issues
    
    def _parse_word_count_issues(self, filename: str, issue_type: str):
        """Parse low word count issues"""
        rows = self.read_csv(filename)
        
        for row in rows:
            url = row.get('Address', '')
            if not url:
                continue
                
            issue_data = {
                'word_count': int(row.get('Word Count', 0)) if row.get('Word Count') else 0,
                'size_bytes': int(row.get('Size (Bytes)', 0)) if row.get('Size (Bytes)') else 0,
                'content_type': row.get('Content Type', ''),
                'status_code': int(row.get('Status Code', 0)) if row.get('Status Code') else 0
            }
            
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='content_quality',
                issue_data=issue_data,
                indexability=row.get('Indexability', ''),
                indexability_status=row.get('Indexability Status', ''),
                inlinks_count=int(row.get('Inlinks', 0)) if row.get('Inlinks') else 0
            ))
    
    def _parse_duplicate_content_issues(self, filename: str, issue_type: str):
        """Parse duplicate and near-duplicate content issues"""
        rows = self.read_csv(filename)
        
        for row in rows:
            url = row.get('Address', '')
            if not url:
                continue
                
            issue_data = {
                'hash': row.get('Hash', ''),
                'similarity': float(row.get('Similarity', 0)) if row.get('Similarity') else 0,
                'word_count': int(row.get('Word Count', 0)) if row.get('Word Count') else 0,
                'duplicate_count': int(row.get('Duplicate Count', 1)) if row.get('Duplicate Count') else 1
            }
            
            # Add duplicate URLs if present
            if row.get('Duplicate Addresses'):
                issue_data['duplicate_urls'] = row.get('Duplicate Addresses', '').split('|')
            elif row.get('Near Duplicate Addresses'):
                issue_data['near_duplicate_urls'] = row.get('Near Duplicate Addresses', '').split('|')
                
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='content_quality',
                issue_data=issue_data,
                indexability=row.get('Indexability', ''),
                indexability_status=row.get('Indexability Status', ''),
                inlinks_count=int(row.get('Inlinks', 0)) if row.get('Inlinks') else 0
            ))
    
    def _parse_soft_404_issues(self, filename: str, issue_type: str):
        """Parse soft 404 issues"""
        rows = self.read_csv(filename)
        
        for row in rows:
            url = row.get('Address', '')
            if not url:
                continue
                
            issue_data = {
                'status_code': int(row.get('Status Code', 200)) if row.get('Status Code') else 200,
                'word_count': int(row.get('Word Count', 0)) if row.get('Word Count') else 0,
                'soft_404_detection': row.get('Soft 404 Detection', ''),
                'content_type': row.get('Content Type', ''),
                'size_bytes': int(row.get('Size (Bytes)', 0)) if row.get('Size (Bytes)') else 0
            }
            
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='content_quality',
                issue_data=issue_data,
                indexability=row.get('Indexability', ''),
                indexability_status=row.get('Indexability Status', ''),
                inlinks_count=int(row.get('Inlinks', 0)) if row.get('Inlinks') else 0
            ))
    
    def _parse_readability_issues(self, filename: str, issue_type: str):
        """Parse readability issues"""
        rows = self.read_csv(filename)
        
        for row in rows:
            url = row.get('Address', '')
            if not url:
                continue
                
            issue_data = {
                'readability_score': float(row.get('Readability Score', 0)) if row.get('Readability Score') else 0,
                'flesch_reading_ease': float(row.get('Flesch Reading Ease', 0)) if row.get('Flesch Reading Ease') else 0,
                'flesch_kincaid_grade': float(row.get('Flesch Kincaid Grade Level', 0)) if row.get('Flesch Kincaid Grade Level') else 0,
                'word_count': int(row.get('Word Count', 0)) if row.get('Word Count') else 0,
                'sentence_count': int(row.get('Sentence Count', 0)) if row.get('Sentence Count') else 0,
                'average_words_per_sentence': float(row.get('Average Words Per Sentence', 0)) if row.get('Average Words Per Sentence') else 0
            }
            
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='content_quality',
                issue_data=issue_data,
                indexability=row.get('Indexability', ''),
                indexability_status=row.get('Indexability Status', ''),
                inlinks_count=int(row.get('Inlinks', 0)) if row.get('Inlinks') else 0
            ))
    
    def _parse_language_issues(self, filename: str, issue_type: str):
        """Parse spelling and grammar issues"""
        rows = self.read_csv(filename)
        
        for row in rows:
            url = row.get('Address', '')
            if not url:
                continue
                
            issue_data = {
                'error_count': int(row.get('Error Count', 0)) if row.get('Error Count') else 0,
                'errors': row.get('Errors', '').split('|') if row.get('Errors') else [],
                'word_count': int(row.get('Word Count', 0)) if row.get('Word Count') else 0,
                'language': row.get('Language', 'en')
            }
            
            # Add specific error details
            if issue_type == 'spelling_errors':
                issue_data['misspelled_words'] = row.get('Misspelled Words', '').split('|') if row.get('Misspelled Words') else []
            elif issue_type == 'grammar_errors':
                issue_data['grammar_issues'] = row.get('Grammar Issues', '').split('|') if row.get('Grammar Issues') else []
                
            self.issues.append(self.create_issue(
                url=url,
                issue_type=issue_type,
                issue_category='content_quality',
                issue_data=issue_data,
                indexability=row.get('Indexability', ''),
                indexability_status=row.get('Indexability Status', ''),
                inlinks_count=int(row.get('Inlinks', 0)) if row.get('Inlinks') else 0
            ))