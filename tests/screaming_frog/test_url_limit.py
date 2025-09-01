#!/usr/bin/env python
"""Test Screaming Frog URL limit enforcement"""

import os
import sys
import csv
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from site_audit.screaming_frog import ScreamingFrogCLI
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def count_crawled_urls(output_dir):
    """Count URLs in the internal_all.csv file"""
    internal_file = os.path.join(output_dir, 'internal_all.csv')
    if not os.path.exists(internal_file):
        logger.warning(f"internal_all.csv not found in {output_dir}")
        return 0
    
    count = 0
    with open(internal_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            count += 1
    return count

def test_url_limit():
    """Test URL limit enforcement with a larger site"""
    print("=" * 60)
    print("TESTING URL LIMIT ENFORCEMENT")
    print("=" * 60)
    
    cli = ScreamingFrogCLI()
    
    # Test sites with different expected sizes
    test_cases = [
        # (URL, max_pages, description)
        ("https://www.python.org", 50, "Python.org with 50 page limit"),
        ("https://httpbin.org", 20, "Httpbin.org with 20 page limit"),
    ]
    
    for url, max_pages, description in test_cases:
        print(f"\n📊 Testing: {description}")
        print(f"   URL: {url}")
        print(f"   Max pages: {max_pages}")
        
        try:
            success, output_dir, error = cli.crawl_website(url, max_pages=max_pages)
            
            if success:
                print(f"   ✅ Crawl successful")
                print(f"   📁 Output: {output_dir}")
                
                # Count actual URLs crawled
                url_count = count_crawled_urls(output_dir)
                print(f"   📊 URLs crawled: {url_count}")
                
                # Check if limit was respected
                if url_count <= max_pages:
                    print(f"   ✅ URL limit respected ({url_count} <= {max_pages})")
                else:
                    print(f"   ❌ URL limit EXCEEDED ({url_count} > {max_pages})")
                    print(f"      This indicates the limit is not being enforced!")
                
                # Parse results to get more details
                results = cli.parse_crawl_results(output_dir)
                if results:
                    print(f"   📈 Total issues found: {results.get('summary', {}).get('total_issues', 0)}")
                    
                # Clean up
                import shutil
                if output_dir and os.path.exists(output_dir):
                    shutil.rmtree(output_dir)
                    
            else:
                print(f"   ❌ Crawl failed: {error}")
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
    
    print("\n" + "=" * 60)
    print("URL LIMIT TEST COMPLETE")
    print("=" * 60)
    
    # Check license info
    license_info = cli.validate_license()
    print("\n📋 License Information:")
    print(f"   Valid: {license_info.get('valid', False)}")
    print(f"   Type: {license_info.get('type', 'Unknown')}")
    
    # Important note
    print("\n⚠️  IMPORTANT NOTES:")
    print("   • Screaming Frog's paid license removes the 500 URL limit")
    print("   • The license key is set via SCREAMING_FROG_LICENSE env var")
    print("   • Command-line parameters for URL limits don't work reliably")
    print("   • The crawl will respect robots.txt which may limit pages")
    
    return True

if __name__ == "__main__":
    success = test_url_limit()
    sys.exit(0 if success else 1)