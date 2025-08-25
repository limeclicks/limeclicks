"""
Screaming Frog SEO Spider CLI integration
Handles crawling, data extraction, and issue analysis
"""

import subprocess
import os
import json
import csv
import tempfile
import logging
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
import requests
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class ScreamingFrogCLI:
    """Interface for Screaming Frog SEO Spider CLI"""
    
    def __init__(self):
        self.sf_path = self._find_screaming_frog()
        self.license_key = os.getenv('SCREAMING_FROG_LICENSE', settings.SCREAMING_FROG_LICENSE if hasattr(settings, 'SCREAMING_FROG_LICENSE') else None)
        self.temp_dir = None
    
    def _find_screaming_frog(self) -> str:
        """Find Screaming Frog executable"""
        # Common installation paths
        paths = [
            '/opt/screamingfrog/ScreamingFrogSEOSpider',  # Linux
            '/usr/bin/screamingfrogseospider',  # Linux alternative
            'C:\\Program Files\\Screaming Frog SEO Spider\\ScreamingFrogSEOSpider.exe',  # Windows
            '/Applications/Screaming Frog SEO Spider.app/Contents/MacOS/ScreamingFrogSEOSpider',  # macOS
            'screamingfrogseospider',  # In PATH
        ]
        
        for path in paths:
            if os.path.exists(path):
                return path
        
        # Try to find in PATH
        try:
            result = subprocess.run(['which', 'screamingfrogseospider'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        
        # Default fallback
        return 'screamingfrogseospider'
    
    def validate_license(self) -> Dict:
        """Validate Screaming Frog license"""
        if not self.license_key:
            return {
                'valid': False,
                'type': 'free',
                'max_urls': 500,
                'message': 'No license key provided, using free version (500 URL limit)'
            }
        
        # For now, we'll assume the license is valid if provided
        # The actual validation will happen when we try to crawl
        # This avoids the --check-licence error
        return {
            'valid': True,
            'type': 'paid',
            'max_urls': None,  # Unlimited for paid
            'message': 'License key configured (validation will occur during crawl)',
            'expiry_date': None  # We'll track this manually in admin
        }
    
    def crawl_website(self, url: str, max_pages: int = 500, config: Optional[Dict] = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Crawl a website using Screaming Frog CLI
        
        Args:
            url: Website URL to crawl
            max_pages: Maximum pages to crawl
            config: Optional configuration dict
        
        Returns:
            Tuple of (success, output_dir, error_message)
        """
        
        # Create temporary directory for output
        self.temp_dir = tempfile.mkdtemp(prefix='sf_crawl_')
        
        try:
            # Build command for fully headless operation
            cmd = [
                self.sf_path,
                '--headless',  # MUST be first after executable for true headless mode
                '--crawl', url,
                '--output-folder', self.temp_dir,
                '--save-crawl',  # Save crawl data
                '--no-gui',  # Ensure no GUI elements
                '--export-tabs', 'Internal:All,External:All,Response Codes:All,Page Titles:All,Meta Description:All,H1:All,H2:All,Images:All,Directives:All,Hreflang:All,Canonical:All,Pagination:All,Structured Data:All',
                '--max-uri', str(max_pages),
                '--max-page-size', '10',  # 10MB max page size
                '--max-html-size', '5',  # 5MB max HTML size
                '--respect-robots-txt',
                '--user-agent', 'Mozilla/5.0 (compatible; ScreamingFrog/18.0)',
            ]
            
            # Add license if available
            if self.license_key:
                cmd.extend(['--licence', self.license_key])
            
            # Add custom configuration
            if config:
                if config.get('follow_redirects', True):
                    cmd.append('--follow-redirects')
                if config.get('crawl_subdomains', False):
                    cmd.append('--crawl-subdomains')
                if config.get('check_spelling', True):
                    cmd.append('--spell-check')
                if config.get('crawl_depth'):
                    cmd.extend(['--max-depth', str(config['crawl_depth'])])
            
            logger.info(f"Starting Screaming Frog crawl for {url}")
            
            # Run the crawl
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minute timeout
            )
            
            if result.returncode == 0:
                logger.info(f"Crawl completed successfully for {url}")
                return True, self.temp_dir, None
            else:
                error_msg = f"Crawl failed: {result.stderr}"
                logger.error(error_msg)
                return False, None, error_msg
                
        except subprocess.TimeoutExpired:
            error_msg = "Crawl timed out after 30 minutes"
            logger.error(error_msg)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"Error during crawl: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
    
    def parse_crawl_results(self, output_dir: str) -> Dict:
        """Parse Screaming Frog crawl results from exported files"""
        
        results = {
            'pages_crawled': 0,
            'issues': {},
            'summary': {},
            'details': {
                # Critical SEO Issues
                'broken_links': [],
                'redirect_chains': [],
                'blocked_by_robots': [],
                'non_indexable': [],
                
                # Title Issues
                'missing_titles': [],
                'duplicate_titles': [],
                'title_too_long': [],
                'title_too_short': [],
                
                # Meta Description Issues
                'missing_meta_descriptions': [],
                'duplicate_meta_descriptions': [],
                'meta_description_too_long': [],
                'meta_description_too_short': [],
                
                # Heading Issues
                'missing_h1': [],
                'duplicate_h1': [],
                'multiple_h1': [],
                'missing_h2': [],
                
                # Content Issues
                'thin_content': [],
                'duplicate_content': [],
                'spelling_errors': [],
                
                # Technical SEO
                'missing_canonical': [],
                'duplicate_canonical': [],
                'missing_hreflang': [],
                'orphan_pages': [],
                
                # Image Issues
                'missing_alt_text': [],
                'large_images': [],
                
                # Performance Issues
                'slow_pages': [],
                'large_pages': [],
                'performance_issues': []
            }
        }
        
        # Parse Internal URLs
        internal_file = os.path.join(output_dir, 'internal_all.csv')
        if os.path.exists(internal_file):
            results['details']['internal_urls'] = self._parse_internal_urls(internal_file)
            results['pages_crawled'] = len(results['details']['internal_urls'])
        
        # Parse Response Codes (for broken links and redirects)
        response_file = os.path.join(output_dir, 'response_codes_all.csv')
        if os.path.exists(response_file):
            self._parse_response_codes(response_file, results)
        
        # Parse Page Titles
        titles_file = os.path.join(output_dir, 'page_titles_all.csv')
        if os.path.exists(titles_file):
            self._parse_page_titles(titles_file, results)
        
        # Parse Meta Descriptions
        meta_file = os.path.join(output_dir, 'meta_description_all.csv')
        if os.path.exists(meta_file):
            self._parse_meta_descriptions(meta_file, results)
        
        # Parse Directives (robots, canonical, etc.)
        directives_file = os.path.join(output_dir, 'directives_all.csv')
        if os.path.exists(directives_file):
            self._parse_directives(directives_file, results)
        
        # Parse Hreflang
        hreflang_file = os.path.join(output_dir, 'hreflang_all.csv')
        if os.path.exists(hreflang_file):
            self._parse_hreflang(hreflang_file, results)
        
        # Parse H1 tags
        h1_file = os.path.join(output_dir, 'h1_all.csv')
        if os.path.exists(h1_file):
            self._parse_h1_tags(h1_file, results)
        
        # Parse H2 tags
        h2_file = os.path.join(output_dir, 'h2_all.csv')
        if os.path.exists(h2_file):
            self._parse_h2_tags(h2_file, results)
        
        # Parse Images
        images_file = os.path.join(output_dir, 'images_all.csv')
        if os.path.exists(images_file):
            self._parse_images(images_file, results)
        
        # Parse Canonical URLs
        canonical_file = os.path.join(output_dir, 'canonical_all.csv')
        if os.path.exists(canonical_file):
            self._parse_canonical(canonical_file, results)
        
        # Analyze content and performance from internal URLs
        if results['details'].get('internal_urls'):
            self._analyze_content_issues(results)
            self._analyze_performance_issues(results)
        
        # Calculate summary statistics
        self._calculate_summary(results)
        
        return results
    
    def _parse_internal_urls(self, file_path: str) -> List[Dict]:
        """Parse internal URLs from CSV"""
        urls = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url_data = {
                        'url': row.get('Address', ''),
                        'status_code': int(row.get('Status Code', 0)),
                        'title': row.get('Title 1', ''),
                        'meta_description': row.get('Meta Description 1', ''),
                        'h1': row.get('H1-1', ''),
                        'word_count': int(row.get('Word Count', 0)),
                        'page_size': int(row.get('Size (Bytes)', 0)),
                        'response_time': int(row.get('Response Time', 0)),
                        'crawl_depth': int(row.get('Crawl Depth', 0)),
                    }
                    urls.append(url_data)
        except Exception as e:
            logger.error(f"Error parsing internal URLs: {e}")
        return urls
    
    def _parse_response_codes(self, file_path: str, results: Dict):
        """Parse response codes to find broken links and redirects"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    status_code = int(row.get('Status Code', 0))
                    url = row.get('Address', '')
                    
                    # Broken links (4xx, 5xx)
                    if 400 <= status_code < 600:
                        results['details']['broken_links'].append({
                            'url': url,
                            'status_code': status_code,
                            'source': row.get('From', ''),
                            'anchor_text': row.get('Anchor', '')
                        })
                    
                    # Redirect chains (3xx)
                    elif 300 <= status_code < 400:
                        results['details']['redirect_chains'].append({
                            'url': url,
                            'status_code': status_code,
                            'redirect_to': row.get('Redirect URL', ''),
                            'chain_length': int(row.get('Redirect Chain', 1))
                        })
        except Exception as e:
            logger.error(f"Error parsing response codes: {e}")
    
    def _parse_page_titles(self, file_path: str, results: Dict):
        """Parse page titles to find issues"""
        try:
            titles_seen = {}
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get('Address', '')
                    title = row.get('Title 1', '')
                    title_length = int(row.get('Title 1 Length', 0))
                    
                    # Missing titles
                    if not title:
                        results['details']['missing_titles'].append({
                            'url': url
                        })
                    
                    # Duplicate titles
                    elif title in titles_seen:
                        if title not in [t['title'] for t in results['details']['duplicate_titles']]:
                            results['details']['duplicate_titles'].append({
                                'title': title,
                                'urls': [titles_seen[title], url]
                            })
                        else:
                            # Add to existing duplicate entry
                            for item in results['details']['duplicate_titles']:
                                if item['title'] == title:
                                    item['urls'].append(url)
                    else:
                        titles_seen[title] = url
                    
                    # Title length issues
                    if title_length > 60:
                        if 'title_too_long' not in results['details']:
                            results['details']['title_too_long'] = []
                        results['details']['title_too_long'].append({
                            'url': url,
                            'title': title,
                            'length': title_length
                        })
                    elif 0 < title_length < 30:
                        if 'title_too_short' not in results['details']:
                            results['details']['title_too_short'] = []
                        results['details']['title_too_short'].append({
                            'url': url,
                            'title': title,
                            'length': title_length
                        })
        except Exception as e:
            logger.error(f"Error parsing page titles: {e}")
    
    def _parse_meta_descriptions(self, file_path: str, results: Dict):
        """Parse meta descriptions to find issues"""
        try:
            descriptions_seen = {}
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get('Address', '')
                    description = row.get('Meta Description 1', '')
                    desc_length = int(row.get('Meta Description 1 Length', 0))
                    
                    # Missing meta descriptions
                    if not description:
                        results['details']['missing_meta_descriptions'].append({
                            'url': url
                        })
                    
                    # Duplicate meta descriptions
                    elif description in descriptions_seen:
                        if description not in [d['description'] for d in results['details']['duplicate_meta_descriptions']]:
                            results['details']['duplicate_meta_descriptions'].append({
                                'description': description[:100],
                                'urls': [descriptions_seen[description], url]
                            })
                        else:
                            for item in results['details']['duplicate_meta_descriptions']:
                                if item['description'] == description[:100]:
                                    item['urls'].append(url)
                    else:
                        descriptions_seen[description] = url
                    
                    # Description length issues
                    if desc_length > 160:
                        if 'meta_description_too_long' not in results['details']:
                            results['details']['meta_description_too_long'] = []
                        results['details']['meta_description_too_long'].append({
                            'url': url,
                            'description': description[:100],
                            'length': desc_length
                        })
                    elif 0 < desc_length < 50:
                        if 'meta_description_too_short' not in results['details']:
                            results['details']['meta_description_too_short'] = []
                        results['details']['meta_description_too_short'].append({
                            'url': url,
                            'description': description,
                            'length': desc_length
                        })
        except Exception as e:
            logger.error(f"Error parsing meta descriptions: {e}")
    
    def _parse_directives(self, file_path: str, results: Dict):
        """Parse directives (robots, canonical, etc.)"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get('Address', '')
                    meta_robots = row.get('Meta Robots 1', '')
                    
                    # Blocked by robots
                    if 'noindex' in meta_robots.lower() or 'nofollow' in meta_robots.lower():
                        results['details']['blocked_by_robots'].append({
                            'url': url,
                            'directive': meta_robots
                        })
        except Exception as e:
            logger.error(f"Error parsing directives: {e}")
    
    def _parse_hreflang(self, file_path: str, results: Dict):
        """Parse hreflang attributes"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get('Address', '')
                    hreflang = row.get('Hreflang', '')
                    
                    # Missing or invalid hreflang
                    if not hreflang or hreflang == 'Missing':
                        results['details']['missing_hreflang'].append({
                            'url': url
                        })
        except Exception as e:
            logger.error(f"Error parsing hreflang: {e}")
    
    def _calculate_summary(self, results: Dict):
        """Calculate summary statistics"""
        results['summary'] = {
            'total_pages_crawled': results['pages_crawled'],
            
            # Critical Issues
            'broken_links': len(results['details']['broken_links']),
            'redirect_chains': len(results['details']['redirect_chains']),
            'blocked_by_robots': len(results['details']['blocked_by_robots']),
            'non_indexable': len(results['details'].get('non_indexable', [])),
            
            # Title Issues
            'missing_titles': len(results['details']['missing_titles']),
            'duplicate_titles': len(results['details']['duplicate_titles']),
            'title_too_long': len(results['details'].get('title_too_long', [])),
            'title_too_short': len(results['details'].get('title_too_short', [])),
            
            # Meta Description Issues
            'missing_meta_descriptions': len(results['details']['missing_meta_descriptions']),
            'duplicate_meta_descriptions': len(results['details']['duplicate_meta_descriptions']),
            'meta_description_too_long': len(results['details'].get('meta_description_too_long', [])),
            'meta_description_too_short': len(results['details'].get('meta_description_too_short', [])),
            
            # Heading Issues
            'missing_h1': len(results['details'].get('missing_h1', [])),
            'duplicate_h1': len(results['details'].get('duplicate_h1', [])),
            'multiple_h1': len(results['details'].get('multiple_h1', [])),
            
            # Content Issues
            'thin_content': len(results['details'].get('thin_content', [])),
            'duplicate_content': len(results['details'].get('duplicate_content', [])),
            
            # Technical SEO
            'missing_canonical': len(results['details'].get('missing_canonical', [])),
            'missing_hreflang': len(results['details']['missing_hreflang']),
            'orphan_pages': len(results['details'].get('orphan_pages', [])),
            
            # Images
            'missing_alt_text': len(results['details'].get('missing_alt_text', [])),
            'large_images': len(results['details'].get('large_images', [])),
            
            # Performance
            'slow_pages': len(results['details'].get('slow_pages', [])),
            'large_pages': len(results['details'].get('large_pages', [])),
            
            'total_issues': 0
        }
        
        # Calculate total issues - include all issue types
        results['summary']['total_issues'] = sum([
            value for key, value in results['summary'].items() 
            if key not in ['total_pages_crawled', 'total_issues', 'average_page_size_kb', 'average_load_time_ms']
        ])
        
        # Calculate average metrics
        if results['details'].get('internal_urls'):
            urls = results['details']['internal_urls']
            if urls:
                avg_size = sum(u['page_size'] for u in urls) / len(urls)
                avg_time = sum(u['response_time'] for u in urls) / len(urls)
                results['summary']['average_page_size_kb'] = round(avg_size / 1024, 2)
                results['summary']['average_load_time_ms'] = round(avg_time, 2)
    
    def cleanup(self):
        """Clean up temporary files"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                import shutil
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
            except Exception as e:
                logger.error(f"Error cleaning up temp directory: {e}")
    
    def _parse_h1_tags(self, file_path: str, results: Dict):
        """Parse H1 tags to find issues"""
        try:
            h1_seen = {}
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get('Address', '')
                    h1_1 = row.get('H1-1', '')
                    h1_2 = row.get('H1-2', '')  # Check for multiple H1s
                    
                    # Missing H1
                    if not h1_1:
                        results['details']['missing_h1'].append({
                            'url': url
                        })
                    
                    # Multiple H1s
                    elif h1_2:
                        results['details']['multiple_h1'].append({
                            'url': url,
                            'h1_count': 2 if h1_2 else 1
                        })
                    
                    # Duplicate H1s
                    elif h1_1 in h1_seen:
                        if h1_1 not in [h['h1'] for h in results['details']['duplicate_h1']]:
                            results['details']['duplicate_h1'].append({
                                'h1': h1_1,
                                'urls': [h1_seen[h1_1], url]
                            })
                        else:
                            for item in results['details']['duplicate_h1']:
                                if item['h1'] == h1_1:
                                    item['urls'].append(url)
                    else:
                        h1_seen[h1_1] = url
        except Exception as e:
            logger.error(f"Error parsing H1 tags: {e}")
    
    def _parse_h2_tags(self, file_path: str, results: Dict):
        """Parse H2 tags to find missing H2s"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get('Address', '')
                    h2 = row.get('H2-1', '')
                    
                    # Missing H2
                    if not h2:
                        results['details']['missing_h2'].append({
                            'url': url
                        })
        except Exception as e:
            logger.error(f"Error parsing H2 tags: {e}")
    
    def _parse_images(self, file_path: str, results: Dict):
        """Parse images to find alt text and size issues"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get('Address', '')
                    alt_text = row.get('Alt Text', '')
                    size = int(row.get('Size (Bytes)', 0))
                    
                    # Missing alt text
                    if not alt_text or alt_text.strip() == '':
                        results['details']['missing_alt_text'].append({
                            'url': url,
                            'image_url': row.get('Destination', '')
                        })
                    
                    # Large images (over 200KB)
                    if size > 200000:
                        results['details']['large_images'].append({
                            'url': url,
                            'image_url': row.get('Destination', ''),
                            'size_kb': round(size / 1024, 2)
                        })
        except Exception as e:
            logger.error(f"Error parsing images: {e}")
    
    def _parse_canonical(self, file_path: str, results: Dict):
        """Parse canonical URLs to find issues"""
        try:
            canonical_seen = {}
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get('Address', '')
                    canonical = row.get('Canonical Link Element 1', '')
                    
                    # Missing canonical
                    if not canonical:
                        results['details']['missing_canonical'].append({
                            'url': url
                        })
                    
                    # Duplicate canonical (multiple pages pointing to same canonical)
                    elif canonical in canonical_seen and canonical != url:
                        if canonical not in [c['canonical'] for c in results['details']['duplicate_canonical']]:
                            results['details']['duplicate_canonical'].append({
                                'canonical': canonical,
                                'urls': [canonical_seen[canonical], url]
                            })
                        else:
                            for item in results['details']['duplicate_canonical']:
                                if item['canonical'] == canonical:
                                    item['urls'].append(url)
                    else:
                        canonical_seen[canonical] = url
        except Exception as e:
            logger.error(f"Error parsing canonical URLs: {e}")
    
    def _analyze_content_issues(self, results: Dict):
        """Analyze content issues from internal URLs"""
        try:
            for url_data in results['details']['internal_urls']:
                url = url_data['url']
                word_count = url_data.get('word_count', 0)
                
                # Thin content (less than 300 words)
                if word_count < 300 and word_count > 0:
                    results['details']['thin_content'].append({
                        'url': url,
                        'word_count': word_count
                    })
                
                # Check for orphan pages (crawl depth > 3)
                if url_data.get('crawl_depth', 0) > 3:
                    results['details']['orphan_pages'].append({
                        'url': url,
                        'crawl_depth': url_data['crawl_depth']
                    })
        except Exception as e:
            logger.error(f"Error analyzing content issues: {e}")
    
    def _analyze_performance_issues(self, results: Dict):
        """Analyze performance issues from internal URLs"""
        try:
            for url_data in results['details']['internal_urls']:
                url = url_data['url']
                response_time = url_data.get('response_time', 0)
                page_size = url_data.get('page_size', 0)
                
                # Slow pages (response time > 3000ms)
                if response_time > 3000:
                    results['details']['slow_pages'].append({
                        'url': url,
                        'response_time_ms': response_time
                    })
                
                # Large pages (size > 3MB)
                if page_size > 3145728:  # 3MB in bytes
                    results['details']['large_pages'].append({
                        'url': url,
                        'size_mb': round(page_size / 1048576, 2)
                    })
        except Exception as e:
            logger.error(f"Error analyzing performance issues: {e}")


class ScreamingFrogService:
    """High-level service for Screaming Frog operations"""
    
    @staticmethod
    def check_installation() -> bool:
        """Check if Screaming Frog is installed"""
        cli = ScreamingFrogCLI()
        try:
            # Try to run with version flag
            result = subprocess.run(
                [cli.sf_path, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    @staticmethod
    def validate_and_save_license():
        """Validate license and save to database"""
        from .models import ScreamingFrogLicense
        
        cli = ScreamingFrogCLI()
        license_info = cli.validate_license()
        
        # Update or create license record
        license_obj, created = ScreamingFrogLicense.objects.get_or_create(
            defaults={'license_key': cli.license_key or ''}
        )
        
        license_obj.license_key = cli.license_key or ''
        license_obj.license_status = 'valid' if license_info['valid'] else 'invalid'
        license_obj.license_type = license_info['type']
        license_obj.max_urls = license_info.get('max_urls', 500)
        license_obj.last_validated = timezone.now()
        
        if license_info.get('expiry_date'):
            license_obj.expiry_date = license_info['expiry_date']
        
        license_obj.save()
        
        return license_obj, license_info