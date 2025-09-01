#!/usr/bin/env python
"""Quick test of Screaming Frog URL limit"""

import os
import sys
import csv
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from site_audit.screaming_frog import ScreamingFrogCLI

def test_simple():
    """Test with a simple site"""
    print("Testing URL limit with example.com (5 pages max)")
    
    cli = ScreamingFrogCLI()
    
    # Very simple test
    success, output_dir, error = cli.crawl_website("https://example.com", max_pages=5)
    
    if success:
        print(f"✅ Crawl successful")
        print(f"📁 Output: {output_dir}")
        
        # Check internal_all.csv
        internal_file = os.path.join(output_dir, 'internal_all.csv')
        if os.path.exists(internal_file):
            with open(internal_file, 'r') as f:
                lines = len(f.readlines()) - 1  # Subtract header
            print(f"📊 URLs in internal_all.csv: {lines}")
            
            # Show file sizes
            files = os.listdir(output_dir)
            print(f"\n📁 Generated {len(files)} files:")
            for f in sorted(files)[:10]:
                path = os.path.join(output_dir, f)
                size = os.path.getsize(path)
                print(f"   {f}: {size} bytes")
        
        # Parse results
        results = cli.parse_crawl_results(output_dir)
        if results:
            print(f"\n📈 Pages crawled (from parser): {results.get('pages_crawled', 0)}")
            print(f"📈 Total issues: {results.get('summary', {}).get('total_issues', 0)}")
        
        # Clean up
        import shutil
        shutil.rmtree(output_dir)
    else:
        print(f"❌ Crawl failed: {error}")

if __name__ == "__main__":
    test_simple()