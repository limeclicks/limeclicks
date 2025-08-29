"""
Simplified Screaming Frog CLI wrapper for site audits
"""

import os
import subprocess
import tempfile
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ScreamingFrogCLI:
    """Simplified Screaming Frog CLI wrapper"""
    
    def __init__(self):
        self.sf_path = '/usr/bin/screamingfrogseospider'
        
    def crawl_website(self, url):
        """
        Run Screaming Frog crawl and save all reports
        
        Args:
            url: The URL to crawl
            max_pages: Maximum number of pages to crawl
            
        Returns:
            tuple: (success, output_dir, error_message)
        """
        # Create temporary directory for output
        temp_dir = tempfile.mkdtemp(prefix='sf_crawl_')
        
        try:
            # Build the command with all reports and exports
            cmd = [
                self.sf_path,
                '--headless',
                '--crawl', url,
                '--save-crawl',
                '--timestamped-output',
                '--output-folder', temp_dir,
                '--export-tabs', 'Internal:All,External:All,Response Codes:All,URL:All,Canonicals:All,Directives:All,Page Titles:All,Meta Description:All,H1:All,H2:All,Images:All,Hreflang:All,Structured Data:All,Links:All,JavaScript:All,Validation:All',
                '--save-report', 'Crawl Overview',
                '--save-report', 'Issues Overview',
                '--save-report', 'Redirects:All Redirects',
                '--save-report', 'Redirects:Redirect Chains',
                '--save-report', 'Redirects:Redirect & Canonical Chains',
                '--save-report', 'Canonicals:Canonical Chains',
                '--save-report', 'Canonicals:Non-Indexable Canonicals',
                '--save-report', 'Pagination:Non-200 Pagination URLs',
                '--save-report', 'Pagination:Unlinked Pagination URLs',
                '--save-report', 'Hreflang:All hreflang URLs',
                '--save-report', 'Hreflang:Non-200 hreflang URLs',
                '--save-report', 'Hreflang:Unlinked hreflang URLs',
                '--save-report', 'Hreflang:Missing Return Links',
                '--save-report', 'Hreflang:Inconsistent Language & Region Return Links',
                '--save-report', 'HTTP Header:HTTP Headers Summary',
                '--save-report', 'Cookies:Cookie Summary',
                '--save-report', 'Structured Data:Validation Errors & Warnings',
                '--bulk-export', 'Issues:All,Response Codes:Internal & External:Client Error (4xx) Inlinks,Response Codes:Internal & External:Server Error (5xx) Inlinks,Response Codes:Internal:Internal Redirect Chain Inlinks,Response Codes:Internal:Internal Redirect Loop Inlinks,Images:Images Missing Alt Text Inlinks,Images:Images Over X KB Inlinks'
            ]
            
            # Print the command for debugging
            print("=" * 80)
            print("SCREAMING FROG COMMAND:")
            print(" ".join(cmd))
            print(f"Output directory: {temp_dir}")
            print("=" * 80)
            
            # Set environment for headless execution
            env = os.environ.copy()
            env['DISPLAY'] = ''
            env['QT_QPA_PLATFORM'] = 'offscreen'
            
            # Execute the command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=900,  # 15 minute timeout
                env=env
            )
            
            # Log the output
            if result.stdout:
                logger.info(f"Screaming Frog stdout: {result.stdout}")
            if result.stderr:
                logger.warning(f"Screaming Frog stderr: {result.stderr}")
            
            # Check if any files were generated
            output_files = list(Path(temp_dir).glob('*'))
            if output_files:
                print(f"✅ Crawl completed. Generated {len(output_files)} files:")
                for file in output_files[:10]:  # Show first 10 files
                    print(f"  - {file.name}")
                return True, temp_dir, None
            else:
                error_msg = f"No output files generated. stderr: {result.stderr}"
                logger.error(error_msg)
                return False, temp_dir, error_msg
                
        except subprocess.TimeoutExpired:
            error_msg = "Crawl timed out after 15 minutes"
            logger.error(error_msg)
            return False, temp_dir, error_msg
            
        except Exception as e:
            error_msg = f"Error during crawl: {str(e)}"
            logger.error(error_msg)
            return False, temp_dir, error_msg
    
    def parse_crawl_results(self, output_dir):
        """
        Parse the crawl results from output directory
        
        For now, just return the list of files generated
        Actual parsing can be implemented later based on the report formats
        """
        output_files = list(Path(output_dir).glob('*'))
        
        result = {
            'pages_crawled': 0,
            'files_generated': len(output_files),
            'output_dir': output_dir,
            'files': [f.name for f in output_files],
            'summary': {
                'total_issues': 0  # Will be parsed from reports later
            },
            'details': {}
        }
        
        # Try to find and parse the Issues Overview report
        issues_file = Path(output_dir) / 'issues_overview.xlsx'
        if not issues_file.exists():
            # Try other possible names
            for file in output_files:
                if 'issues' in file.name.lower() and 'overview' in file.name.lower():
                    issues_file = file
                    break
        
        if issues_file.exists():
            print(f"Found issues overview file: {issues_file.name}")
            # Parsing can be implemented here when needed
        
        return result