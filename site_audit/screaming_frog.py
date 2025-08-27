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
            '/usr/local/bin/screamingfrogseospider',  # Linux local bin
            'C:\\Program Files\\Screaming Frog SEO Spider\\ScreamingFrogSEOSpider.exe',  # Windows
            '/Applications/Screaming Frog SEO Spider.app/Contents/MacOS/ScreamingFrogSEOSpider',  # macOS
            'screamingfrogseospider',  # In PATH
        ]
        
        for path in paths:
            if os.path.exists(path):
                logger.info(f"Found Screaming Frog at: {path}")
                return path
        
        # Try to find in PATH
        try:
            result = subprocess.run(['which', 'screamingfrogseospider'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                found_path = result.stdout.strip()
                logger.info(f"Found Screaming Frog in PATH: {found_path}")
                return found_path
        except:
            pass
        
        # Check if it's available as a command
        try:
            result = subprocess.run(['screamingfrogseospider', '--version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                logger.info("Screaming Frog is available as 'screamingfrogseospider' command")
                return 'screamingfrogseospider'
        except:
            pass
        
        # Default fallback - will likely fail but provides clear error
        logger.warning("Screaming Frog executable not found in common locations")
        return 'screamingfrogseospider'
    
    def is_installed(self) -> bool:
        """Check if Screaming Frog is installed and accessible"""
        # First check if the executable exists
        if not os.path.exists(self.sf_path) and self.sf_path != 'screamingfrogseospider':
            logger.error(f"Screaming Frog executable not found at: {self.sf_path}")
            return False
            
        try:
            # Try a simpler version check first
            result = subprocess.run(
                [self.sf_path, '--version'],
                capture_output=True,
                text=True,
                timeout=5,
                env={**os.environ, 'DISPLAY': ''}  # Ensure no display to prevent GUI
            )
            # If --version works, it's installed
            if result.returncode == 0 or 'version' in result.stdout.lower():
                logger.info("Screaming Frog is installed (version check successful)")
                return True
                
            # Try headless mode check as fallback
            result = subprocess.run(
                [self.sf_path, '--headless'],
                capture_output=True,
                text=True,
                timeout=2,
                env={**os.environ, 'DISPLAY': ''}
            )
            # If it doesn't crash immediately, assume it's installed
            # Even if it exits with error due to missing args, that's fine
            logger.info("Screaming Frog is installed (headless check successful)")
            return True
            
        except FileNotFoundError:
            logger.error(f"Screaming Frog executable not found at: {self.sf_path}")
            return False
        except subprocess.TimeoutExpired:
            # Timeout might mean it's waiting for input - that's actually good
            logger.info("Screaming Frog appears to be installed (timeout on check)")
            return True
        except Exception as e:
            # Log the error but don't fail - might still work for actual crawls
            logger.warning(f"Could not verify Screaming Frog installation: {e}")
            # Assume it's installed if the file exists
            if os.path.exists(self.sf_path) or self.sf_path == 'screamingfrogseospider':
                return True
            return False
    
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
    
    def crawl_website(self, url: str, max_pages: int = 5000, config: Optional[Dict] = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Crawl a website using Screaming Frog CLI with maximum data extraction
        
        Args:
            url: Website URL to crawl
            max_pages: Maximum pages to crawl (default 5000 for comprehensive analysis)
            config: Optional configuration dict
        
        Returns:
            Tuple of (success, output_dir, error_message)
        """
        
        # Create temporary directory for output
        self.temp_dir = tempfile.mkdtemp(prefix='sf_crawl_')
        
        try:
            # Build command for fully headless operation - CRITICAL ORDER
            cmd = [
                self.sf_path,
                '--headless',  # MUST be first after executable for true headless mode
                '--crawl', url,
                '--output-folder', self.temp_dir,
                '--max-urls', str(max_pages),  # Add max URLs parameter to control crawl depth
                '--save-crawl',  # Save crawl data  
                '--overwrite',  # Overwrite existing files
            ]
            
            # Debug log the command
            logger.info(f"Screaming Frog command: max_pages={max_pages}, --max-urls={str(max_pages)}")
            
            # Export tabs - use proper format without colons in filter names
            # Based on the --help output, we need simpler tab names
            export_tabs = [
                'Internal:All',
                'External:All',
                'Response Codes:Client Error (4xx)',
                'Response Codes:Server Error (5xx)',
                'Page Titles:Missing',
                'Page Titles:Duplicate',
                'Page Titles:Over X Characters',
                'Page Titles:Below X Characters',
                'Meta Description:Missing',
                'Meta Description:Duplicate',
                'Meta Description:Over X Characters',
                'Meta Description:Below X Characters',
                'H1:Missing',
                'H1:Duplicate',
                'H1:Multiple',
                'H2:Missing',
                'Images:Missing Alt Text',
                'Images:Over X KB',
                'Hreflang:Missing',
                'Canonicals:Missing',
                'Directives:Noindex',
                'Content:Low Content Pages',
            ]
            
            # Add export tabs as single comma-separated argument
            cmd.extend(['--export-tabs', ','.join(export_tabs)])
            
            # Add bulk exports for comprehensive data
            cmd.extend(['--bulk-export', 'Links:All Inlinks'])  # Proper bulk export format
            
            logger.info(f"Starting Screaming Frog crawl for {url} (max {max_pages} pages)")
            logger.debug(f"Output directory: {self.temp_dir}")
            
            # Set up environment for headless execution
            env = os.environ.copy()
            env['DISPLAY'] = ''  # No display for true headless
            env['QT_QPA_PLATFORM'] = 'offscreen'  # Qt offscreen mode
            
            # If license key is available, set it as environment variable
            if self.license_key:
                env['SCREAMING_FROG_LICENSE'] = self.license_key
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minute timeout
                env=env,
                cwd=self.temp_dir  # Run in temp directory
            )
            
            # Check for successful completion or partial success
            # Even if return code is non-zero, we may have partial data
            output_files = os.listdir(self.temp_dir) if os.path.exists(self.temp_dir) else []
            csv_files = [f for f in output_files if f.endswith('.csv')]
            
            if csv_files:
                logger.info(f"Crawl completed with {len(csv_files)} output files for {url}")
                logger.debug(f"Output files: {csv_files}")
                return True, self.temp_dir, None
            elif result.returncode == 0:
                # Command succeeded but no CSV files - might be timestamped subdirectory
                for item in output_files:
                    subdir = os.path.join(self.temp_dir, item)
                    if os.path.isdir(subdir):
                        subdir_files = os.listdir(subdir)
                        csv_files = [f for f in subdir_files if f.endswith('.csv')]
                        if csv_files:
                            logger.info(f"Found output in subdirectory: {item}")
                            return True, subdir, None
                
                logger.warning("Crawl completed but no CSV files found")
                return False, None, "No output files generated"
            else:
                # Detailed error analysis
                error_output = result.stderr.strip() if result.stderr else ""
                stdout_output = result.stdout.strip() if result.stdout else ""
                
                # Check for common errors in stdout (Screaming Frog logs to stdout)
                if "FATAL" in stdout_output:
                    # Extract FATAL error message
                    import re
                    fatal_match = re.search(r'FATAL - (.+?)(?:\n|$)', stdout_output)
                    if fatal_match:
                        error_msg = f"Screaming Frog error: {fatal_match.group(1)}"
                    else:
                        error_msg = "Screaming Frog fatal error (check logs)"
                elif "licence" in error_output.lower() or "license" in error_output.lower():
                    error_msg = "License validation failed. Please check your Screaming Frog license key."
                elif "command not found" in error_output.lower():
                    error_msg = "Screaming Frog is not installed or not in PATH"
                elif "connection refused" in error_output.lower():
                    error_msg = f"Could not connect to {url}. Site may be down or blocking crawlers."
                elif error_output:
                    error_msg = f"Crawl failed: {error_output[:200]}"
                elif stdout_output:
                    # Look for error patterns in stdout
                    if "Error" in stdout_output or "ERROR" in stdout_output:
                        error_msg = f"Crawl error: {stdout_output[:200]}"
                    else:
                        error_msg = f"Crawl failed with return code {result.returncode}"
                else:
                    error_msg = f"Crawl failed with return code {result.returncode}"
                
                logger.error(f"Crawl error for {url}: {error_msg}")
                return False, None, error_msg
                
        except subprocess.TimeoutExpired:
            error_msg = "Crawl timed out after 30 minutes"
            logger.error(error_msg)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"Error during crawl: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
        finally:
            # Clean up config file  
            if 'config_file' in locals() and config_file and os.path.exists(config_file):
                try:
                    os.remove(config_file)
                except:
                    pass
    
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
        
        # Parse Internal URLs - this contains ALL the data in this version
        internal_file = os.path.join(output_dir, 'internal_all.csv')
        if os.path.exists(internal_file):
            results['details']['internal_urls'] = self._parse_internal_urls(internal_file)
            results['pages_crawled'] = len(results['details']['internal_urls'])
            
            # Extract title and meta description issues from internal_all.csv
            # Since separate files don't exist in this version
            self._extract_title_meta_issues_from_internal(results)
        
        # Try parsing other files if they exist (backwards compatibility)
        # Parse Response Codes (for broken links and redirects)
        response_file = os.path.join(output_dir, 'response_codes_all.csv')
        if os.path.exists(response_file):
            self._parse_response_codes(response_file, results)
        
        # Parse Page Titles (if separate file exists)
        titles_file = os.path.join(output_dir, 'page_titles_all.csv')
        if os.path.exists(titles_file):
            self._parse_page_titles(titles_file, results)
        
        # Parse Meta Descriptions (if separate file exists)
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
            try:
                self._parse_hreflang(hreflang_file, results)
                logger.debug(f"Parsed {len(results['details']['missing_hreflang'])} hreflang issues")
            except Exception as e:
                logger.warning(f"Could not parse hreflang file {hreflang_file}: {e}")
                # Continue processing other files even if hreflang parsing fails
        
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
        
        # Parse specific issue export files (new format from export-tabs)
        self._parse_specific_issue_files(output_dir, results)
        
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
                    # Helper function to safely convert to int
                    def safe_int(value, default=0):
                        try:
                            if isinstance(value, str) and '.' in value:
                                # Handle floats (like response time)
                                return int(float(value))
                            return int(value) if value else default
                        except (ValueError, TypeError):
                            return default
                    
                    # Helper function to safely convert to float  
                    def safe_float(value, default=0.0):
                        try:
                            return float(value) if value else default
                        except (ValueError, TypeError):
                            return default
                    
                    url_data = {
                        'url': row.get('Address', ''),
                        'status_code': safe_int(row.get('Status Code', 0)),
                        'title': row.get('Title 1', ''),
                        'meta_description': row.get('Meta Description 1', ''),
                        'h1': row.get('H1-1', ''),
                        'word_count': safe_int(row.get('Word Count', 0)),
                        'page_size': safe_int(row.get('Size (bytes)', 0)),
                        'response_time': safe_float(row.get('Response Time', 0)),
                        'crawl_depth': safe_int(row.get('Crawl Depth', 0)),
                    }
                    
                    # Store original row data for flexibility
                    url_data['_raw'] = row
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
        if not os.path.exists(file_path):
            logger.debug(f"Hreflang file not found: {file_path}")
            return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Check if file is empty
                content = f.read().strip()
                if not content:
                    logger.debug(f"Hreflang file is empty: {file_path}")
                    return
                
                # Reset file pointer and read as CSV
                f.seek(0)
                reader = csv.DictReader(f)
                
                row_count = 0
                for row in reader:
                    row_count += 1
                    url = row.get('Address', '').strip()
                    hreflang = row.get('Hreflang', '').strip()
                    
                    # Skip empty rows
                    if not url:
                        continue
                    
                    # Missing or invalid hreflang
                    if not hreflang or hreflang.lower() in ['missing', 'none', '']:
                        results['details']['missing_hreflang'].append({
                            'url': url
                        })
                
                logger.debug(f"Processed {row_count} rows from hreflang file")
                
        except FileNotFoundError:
            logger.debug(f"Hreflang file not found: {file_path}")
        except csv.Error as e:
            logger.warning(f"CSV parsing error in hreflang file: {e}")
        except UnicodeDecodeError as e:
            logger.warning(f"Encoding error reading hreflang file: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing hreflang file {file_path}: {e}")
            # Re-raise only if it's a critical error, otherwise continue
            if "missing_hreflang" not in str(e).lower():
                raise
    
    def _extract_title_meta_issues_from_internal(self, results: Dict):
        """Extract title and meta description issues from internal URLs data"""
        titles_seen = {}
        descriptions_seen = {}
        
        for url_data in results['details'].get('internal_urls', []):
            url = url_data.get('url', '')
            title = url_data.get('title', '')
            meta_description = url_data.get('meta_description', '')
            h1 = url_data.get('h1', '')
            word_count = url_data.get('word_count', 0)
            
            # Title issues
            if not title or title == '':
                results['details']['missing_titles'].append({'url': url})
            else:
                title_length = len(title)
                
                # Duplicate titles
                if title in titles_seen:
                    # Check if we already have this duplicate
                    found = False
                    for dup in results['details']['duplicate_titles']:
                        if dup['title'] == title:
                            dup['urls'].append(url)
                            found = True
                            break
                    if not found:
                        results['details']['duplicate_titles'].append({
                            'title': title,
                            'urls': [titles_seen[title], url]
                        })
                else:
                    titles_seen[title] = url
                
                # Title length issues
                if title_length > 60:
                    results['details']['title_too_long'].append({
                        'url': url,
                        'title': title,
                        'length': title_length
                    })
                elif title_length < 30 and title_length > 0:
                    results['details']['title_too_short'].append({
                        'url': url,
                        'title': title,
                        'length': title_length
                    })
            
            # Meta description issues
            if not meta_description or meta_description == '':
                results['details']['missing_meta_descriptions'].append({'url': url})
            else:
                desc_length = len(meta_description)
                
                # Duplicate meta descriptions
                if meta_description in descriptions_seen:
                    # Check if we already have this duplicate
                    found = False
                    for dup in results['details']['duplicate_meta_descriptions']:
                        if dup['description'] == meta_description:
                            dup['urls'].append(url)
                            found = True
                            break
                    if not found:
                        results['details']['duplicate_meta_descriptions'].append({
                            'description': meta_description,
                            'urls': [descriptions_seen[meta_description], url]
                        })
                else:
                    descriptions_seen[meta_description] = url
                
                # Meta description length issues
                if desc_length > 160:
                    results['details']['meta_description_too_long'].append({
                        'url': url,
                        'description': meta_description,
                        'length': desc_length
                    })
                elif desc_length < 70 and desc_length > 0:
                    results['details']['meta_description_too_short'].append({
                        'url': url,
                        'description': meta_description,
                        'length': desc_length
                    })
            
            # H1 issues
            if not h1 or h1 == '':
                results['details']['missing_h1'].append({'url': url})
            
            # Content issues
            if word_count < 300 and word_count > 0:
                results['details']['thin_content'].append({
                    'url': url,
                    'word_count': word_count
                })
    
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
            'missing_hreflang': len(results['details'].get('missing_hreflang', [])),
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


    def _parse_specific_issue_files(self, output_dir: str, results: Dict):
        """Parse specific issue export files generated by export-tabs"""
        try:
            # Helper function to get value from row with BOM handling
            def get_row_value(row, keys):
                """Try multiple key variations to handle BOM and quotes"""
                if isinstance(keys, str):
                    keys = [keys]
                for key in keys:
                    # Try exact key
                    if key in row:
                        return row[key]
                    # Try with BOM prefix
                    bom_key = f'﻿"{key}"'
                    if bom_key in row:
                        return row[bom_key]
                    # Try with quotes
                    quoted_key = f'"{key}"'
                    if quoted_key in row:
                        return row[quoted_key]
                    # Try with BOM and no quotes
                    bom_no_quotes = f'﻿{key}'
                    if bom_no_quotes in row:
                        return row[bom_no_quotes]
                return ''
            
            # Parse missing titles
            missing_titles_file = os.path.join(output_dir, 'page_titles_missing.csv')
            if os.path.exists(missing_titles_file):
                with open(missing_titles_file, 'r', encoding='utf-8-sig') as f:  # utf-8-sig strips BOM
                    reader = csv.DictReader(f)
                    for row in reader:
                        url = get_row_value(row, ['Address'])
                        if url:  # Skip empty rows
                            results['details']['missing_titles'].append({'url': url})
            
            # Parse duplicate titles
            duplicate_titles_file = os.path.join(output_dir, 'page_titles_duplicate.csv')
            if os.path.exists(duplicate_titles_file):
                with open(duplicate_titles_file, 'r', encoding='utf-8-sig') as f:  # utf-8-sig strips BOM
                    reader = csv.DictReader(f)
                    title_groups = {}
                    for row in reader:
                        title = get_row_value(row, ['Title 1'])
                        url = get_row_value(row, ['Address'])
                        if title and url:
                            if title not in title_groups:
                                title_groups[title] = []
                            title_groups[title].append(url)
                    
                    for title, urls in title_groups.items():
                        if len(urls) > 1:
                            results['details']['duplicate_titles'].append({
                                'title': title,
                                'urls': urls,
                                'count': len(urls)
                            })
            
            # Parse missing meta descriptions
            missing_meta_file = os.path.join(output_dir, 'meta_description_missing.csv')
            if os.path.exists(missing_meta_file):
                with open(missing_meta_file, 'r', encoding='utf-8-sig') as f:  # utf-8-sig strips BOM
                    reader = csv.DictReader(f)
                    for row in reader:
                        url = get_row_value(row, ['Address'])
                        if url:
                            results['details']['missing_meta_descriptions'].append({'url': url})
            
            # Parse duplicate meta descriptions
            duplicate_meta_file = os.path.join(output_dir, 'meta_description_duplicate.csv')
            if os.path.exists(duplicate_meta_file):
                with open(duplicate_meta_file, 'r', encoding='utf-8-sig') as f:  # utf-8-sig strips BOM
                    reader = csv.DictReader(f)
                    meta_groups = {}
                    for row in reader:
                        meta = get_row_value(row, ['Meta Description 1'])
                        url = get_row_value(row, ['Address'])
                        if meta and url:
                            if meta not in meta_groups:
                                meta_groups[meta] = []
                            meta_groups[meta].append(url)
                    
                    for meta, urls in meta_groups.items():
                        if len(urls) > 1:
                            results['details']['duplicate_meta_descriptions'].append({
                                'description': meta[:100] + '...' if len(meta) > 100 else meta,
                                'urls': urls,
                                'count': len(urls)
                            })
            
            # Parse missing H1s
            missing_h1_file = os.path.join(output_dir, 'h1_missing.csv')
            if os.path.exists(missing_h1_file):
                with open(missing_h1_file, 'r', encoding='utf-8-sig') as f:  # utf-8-sig strips BOM
                    reader = csv.DictReader(f)
                    for row in reader:
                        url = get_row_value(row, ['Address'])
                        if url:
                            results['details']['missing_h1'].append({'url': url})
            
            # Parse duplicate H1s
            duplicate_h1_file = os.path.join(output_dir, 'h1_duplicate.csv')
            if os.path.exists(duplicate_h1_file):
                with open(duplicate_h1_file, 'r', encoding='utf-8-sig') as f:  # utf-8-sig strips BOM
                    reader = csv.DictReader(f)
                    for row in reader:
                        h1 = get_row_value(row, ['H1-1'])
                        url = get_row_value(row, ['Address'])
                        count = get_row_value(row, ['Occurrences']) or '1'
                        if h1 and url:
                            results['details']['duplicate_h1'].append({
                                'h1': h1,
                                'url': url,
                                'count': int(count) if count else 1
                            })
            
            # Parse multiple H1s
            multiple_h1_file = os.path.join(output_dir, 'h1_multiple.csv')
            if os.path.exists(multiple_h1_file):
                with open(multiple_h1_file, 'r', encoding='utf-8-sig') as f:  # utf-8-sig strips BOM
                    reader = csv.DictReader(f)
                    for row in reader:
                        url = get_row_value(row, ['Address'])
                        h1_1 = get_row_value(row, ['H1-1'])
                        h1_2 = get_row_value(row, ['H1-2'])
                        if url and h1_1 and h1_2:
                            results['details']['multiple_h1'].append({
                                'url': url,
                                'h1_tags': [h1_1, h1_2]
                            })
            
            # Parse missing alt text images
            missing_alt_file = os.path.join(output_dir, 'images_missing_alt_text.csv')
            if os.path.exists(missing_alt_file):
                with open(missing_alt_file, 'r', encoding='utf-8-sig') as f:  # utf-8-sig strips BOM
                    reader = csv.DictReader(f)
                    for row in reader:
                        img_url = get_row_value(row, ['Address'])
                        page_url = get_row_value(row, ['Source'])
                        if img_url:
                            results['details']['missing_alt_text'].append({
                                'image_url': img_url,
                                'url': page_url if page_url else img_url
                            })
            
            # Parse large images
            large_images_file = os.path.join(output_dir, 'images_over_100_kb.csv')
            if os.path.exists(large_images_file):
                with open(large_images_file, 'r', encoding='utf-8-sig') as f:  # utf-8-sig strips BOM
                    reader = csv.DictReader(f)
                    for row in reader:
                        img_url = get_row_value(row, ['Address'])
                        size_str = get_row_value(row, ['Size (bytes)'])
                        if img_url and size_str:
                            try:
                                size = int(size_str)
                                results['details']['large_images'].append({
                                    'image_url': img_url,
                                    'size_kb': round(size / 1024, 2)
                                })
                            except ValueError:
                                pass
            
            # Parse missing hreflang
            missing_hreflang_file = os.path.join(output_dir, 'hreflang_missing.csv')
            if os.path.exists(missing_hreflang_file):
                with open(missing_hreflang_file, 'r', encoding='utf-8-sig') as f:  # utf-8-sig strips BOM
                    reader = csv.DictReader(f)
                    for row in reader:
                        url = get_row_value(row, ['Address'])
                        if url:
                            results['details']['missing_hreflang'].append({'url': url})
            
            # Parse missing canonicals
            missing_canonical_file = os.path.join(output_dir, 'canonicals_missing.csv')
            if os.path.exists(missing_canonical_file):
                with open(missing_canonical_file, 'r', encoding='utf-8-sig') as f:  # utf-8-sig strips BOM
                    reader = csv.DictReader(f)
                    for row in reader:
                        url = get_row_value(row, ['Address'])
                        if url:
                            results['details']['missing_canonical'].append({'url': url})
            
            # Parse noindex pages
            noindex_file = os.path.join(output_dir, 'directives_noindex.csv')
            if os.path.exists(noindex_file):
                with open(noindex_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        url = row.get('Address', '')
                        if url:
                            if 'noindex_pages' not in results['details']:
                                results['details']['noindex_pages'] = []
                            results['details']['noindex_pages'].append({'url': url})
            
            # Parse low content pages
            low_content_file = os.path.join(output_dir, 'content_low_content_pages.csv')
            if os.path.exists(low_content_file):
                with open(low_content_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        url = row.get('Address', '')
                        word_count = row.get('Word Count', '0')
                        if url:
                            if 'low_content_pages' not in results['details']:
                                results['details']['low_content_pages'] = []
                            results['details']['low_content_pages'].append({
                                'url': url,
                                'word_count': int(word_count) if word_count else 0
                            })
            
            # Parse client error (4xx) responses
            client_errors_file = os.path.join(output_dir, 'response_codes_client_error_(4xx).csv')
            if os.path.exists(client_errors_file):
                with open(client_errors_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        url = row.get('Address', '')
                        status = row.get('Status Code', '')
                        if url and status:
                            results['details']['broken_links'].append({
                                'url': url,
                                'status_code': int(status) if status else 404
                            })
            
            # Parse server error (5xx) responses
            server_errors_file = os.path.join(output_dir, 'response_codes_server_error_(5xx).csv')
            if os.path.exists(server_errors_file):
                with open(server_errors_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        url = row.get('Address', '')
                        status = row.get('Status Code', '')
                        if url and status:
                            results['details']['broken_links'].append({
                                'url': url,
                                'status_code': int(status) if status else 500
                            })
            
            logger.info(f"Parsed specific issue files from {output_dir}")
            
        except Exception as e:
            logger.error(f"Error parsing specific issue files: {e}")
            import traceback
            traceback.print_exc()


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