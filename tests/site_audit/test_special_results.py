#!/usr/bin/env python
"""
Test script to verify special results handling in SERP parser
"""

import os
import sys
import django
from pathlib import Path

# Setup Django environment
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from services.google_search_parser import GoogleSearchParser
from keywords.models import Keyword

def test_parser_with_sample_html():
    """Test the parser with a sample HTML that contains special results"""
    
    parser = GoogleSearchParser()
    
    # Simple test HTML with a special result (no URL) and regular results
    test_html = """
    <html>
    <body>
        <!-- Special Result without URL -->
        <div class="g">
            <div class="kp-blk">
                <h3>Special Knowledge Panel</h3>
                <div class="description">This is a special result without a URL</div>
            </div>
        </div>
        
        <!-- Regular Organic Result -->
        <div class="g">
            <h3><a href="https://example.com/page1">Regular Result 1</a></h3>
            <div class="VwiC3b">This is a regular organic result with URL</div>
            <cite>example.com</cite>
        </div>
        
        <!-- Another Special Result -->
        <div class="g xpdopen">
            <h3>Answer Box Result</h3>
            <div class="hgKElc">This is an answer box without URL</div>
        </div>
        
        <!-- Another Regular Result -->
        <div class="g">
            <h3><a href="https://test.com/page2">Regular Result 2</a></h3>
            <div class="VwiC3b">Another regular result</div>
            <cite>test.com</cite>
        </div>
    </body>
    </html>
    """
    
    # Parse the HTML
    results = parser.parse(test_html)
    
    print("=" * 60)
    print("PARSER TEST RESULTS")
    print("=" * 60)
    
    # Check organic results
    organic = results.get('organic_results', [])
    print(f"\nOrganic Results: {len(organic)}")
    for i, result in enumerate(organic, 1):
        print(f"  {i}. Position: {result.get('position')}")
        print(f"     Title: {result.get('title')}")
        print(f"     URL: {result.get('url')}")
        print(f"     Type: {result.get('result_type')}")
        print()
    
    print("\nExpected: Only results with valid URLs should be in organic results")
    print("Result: ", end="")
    
    # Verify only results with valid URLs are included
    all_have_urls = all(r.get('url') and r['url'] != '#' for r in organic)
    if all_have_urls:
        print("✓ PASS - All organic results have valid URLs")
    else:
        print("✗ FAIL - Some organic results don't have valid URLs")
        for r in organic:
            if not r.get('url') or r['url'] == '#':
                print(f"  - Result at position {r.get('position')} has no valid URL")
    
    return all_have_urls


def test_with_real_keyword():
    """Test with a real keyword from the database"""
    
    print("\n" + "=" * 60)
    print("TESTING WITH REAL KEYWORD DATA")
    print("=" * 60)
    
    # Try to find a keyword with "Shreveport LA" 
    try:
        keyword = Keyword.objects.filter(keyword__icontains="shreveport").first()
        if keyword:
            print(f"\nFound keyword: {keyword.keyword}")
            print(f"Project: {keyword.project.domain}")
            
            # Check if we have stored SERP HTML
            if keyword.scrape_do_file_path:
                from pathlib import Path
                import django.conf
                
                storage_root = Path(django.conf.settings.SCRAPE_DO_STORAGE_ROOT)
                file_path = storage_root / keyword.scrape_do_file_path
                
                if file_path.exists():
                    print(f"Found SERP HTML file: {file_path}")
                    
                    # Read and parse the HTML
                    html_content = file_path.read_text(encoding='utf-8')
                    parser = GoogleSearchParser()
                    results = parser.parse(html_content)
                    
                    organic = results.get('organic_results', [])
                    print(f"\nParsed {len(organic)} organic results")
                    
                    # Check first few results
                    print("\nFirst 5 results:")
                    for i, result in enumerate(organic[:5], 1):
                        url = result.get('url', 'NO URL')
                        title = result.get('title', 'NO TITLE')[:50]
                        print(f"  {i}. {title}...")
                        print(f"     URL: {url[:60]}..." if len(url) > 60 else f"     URL: {url}")
                    
                    # Check for any results without URLs
                    no_url_results = [r for r in organic if not r.get('url') or r['url'] == '#']
                    if no_url_results:
                        print(f"\n⚠️  Found {len(no_url_results)} results without valid URLs")
                    else:
                        print("\n✓ All organic results have valid URLs")
                else:
                    print("SERP HTML file not found")
            else:
                print("No SERP HTML file path stored")
        else:
            print("No keyword found with 'shreveport' in it")
    except Exception as e:
        print(f"Error testing with real keyword: {e}")


if __name__ == "__main__":
    # Run tests
    print("Testing SERP Parser Special Results Handling")
    print("=" * 60)
    
    # Test with sample HTML
    test_passed = test_parser_with_sample_html()
    
    # Test with real data if available
    test_with_real_keyword()
    
    print("\n" + "=" * 60)
    if test_passed:
        print("✓ Parser test PASSED - Special results are properly filtered")
    else:
        print("✗ Parser test FAILED - Special results not properly handled")
    print("=" * 60)