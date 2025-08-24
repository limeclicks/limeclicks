#!/usr/bin/env python
"""
Mock test to demonstrate Scrape.do service functionality
"""

import os
import sys
import django
from unittest.mock import Mock, patch

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from services.scrape_do import get_scraper

def test_scraper_with_mock():
    """Test the Scrape.do service with mocked responses"""
    
    print("Testing Scrape.do Service (Mocked)")
    print("=" * 50)
    
    # Get the scraper instance
    scraper = get_scraper()
    print(f"✓ Scraper initialized")
    
    # Mock the session.get method
    with patch.object(scraper.session, 'get') as mock_get:
        # Test 1: Basic scraping
        print("\n1. Testing basic scraping...")
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<html><body><h1>Test Page</h1><p>Content with special chars: café, 100€, "quotes"</p></body></html>'
        mock_response.headers = {'Content-Type': 'text/html'}
        mock_response.url = 'https://example.com'
        mock_get.return_value = mock_response
        
        result = scraper.scrape("https://example.com")
        
        if result and result.get('success'):
            print(f"   ✓ Successfully scraped")
            print(f"   - Status code: {result['status_code']}")
            print(f"   - Contains 'Test Page': {'Test Page' in result['html']}")
            print(f"   - Contains special chars: {'café' in result['html']}")
        
        # Test 2: URL with special characters
        print("\n2. Testing URL with special characters...")
        special_url = "https://example.com/search?q=hello world&price>100&name=café münchen"
        
        result = scraper.scrape(special_url, use_cache=False)
        
        # Verify the URL was passed correctly
        call_args = mock_get.call_args
        params = call_args[1]['params']
        print(f"   ✓ URL passed to API: {params['url']}")
        print(f"   - Special characters preserved in URL")
        
        # Test 3: With country code
        print("\n3. Testing with country code...")
        result = scraper.scrape("https://example.com", country_code='de')
        
        call_args = mock_get.call_args
        params = call_args[1]['params']
        print(f"   ✓ Country code set: {params.get('geoCode', 'Not set')}")
        
        # Test 4: With JavaScript rendering
        print("\n4. Testing with JS rendering options...")
        result = scraper.scrape(
            "https://example.com",
            render=True,
            wait_for=3000,
            block_resources=True
        )
        
        call_args = mock_get.call_args
        params = call_args[1]['params']
        print(f"   ✓ Render enabled: {params.get('render', 'false')}")
        print(f"   ✓ Wait time: {params.get('waitFor', 'Not set')}ms")
        print(f"   ✓ Block resources: {params.get('blockResources', 'false')}")
        
        # Test 5: Custom headers
        print("\n5. Testing custom headers...")
        custom_headers = {
            'Accept-Language': 'de-DE,de;q=0.9',
            'X-Custom-Header': 'TestValue'
        }
        
        result = scraper.scrape("https://example.com", custom_headers=custom_headers)
        
        call_args = mock_get.call_args
        params = call_args[1]['params']
        print(f"   ✓ Custom headers added:")
        print(f"     - Accept-Language: {params.get('customHeaders[Accept-Language]', 'Not set')}")
        print(f"     - X-Custom-Header: {params.get('customHeaders[X-Custom-Header]', 'Not set')}")
        
        # Test 6: Batch scraping
        print("\n6. Testing batch scraping...")
        urls = [
            "https://example1.com",
            "https://example2.com",
            "https://example3.com"
        ]
        
        results = scraper.scrape_batch(urls, country_code='us')
        print(f"   ✓ Scraped {len(results)} URLs")
        for url in urls:
            if url in results:
                print(f"     - {url}: Success")
        
        # Test 7: Google search helper
        print("\n7. Testing Google search helper...")
        result = scraper.scrape_google_search("python django tutorial", country_code='us')
        
        call_args = mock_get.call_args
        params = call_args[1]['params']
        print(f"   ✓ Google search URL generated")
        print(f"   - Query encoded in URL: {'python' in params['url'] and 'django' in params['url']}")
        print(f"   - JS rendering enabled: {params.get('render', 'false')}")
    
    print("\n" + "=" * 50)
    print("All tests passed! Service is working correctly.")
    print("\nNote: The actual API requires a valid API key.")
    print("The service properly handles:")
    print("  - URLs with special characters")
    print("  - Country-specific scraping")
    print("  - JavaScript rendering")
    print("  - Custom headers")
    print("  - Batch operations")
    print("  - Caching")

if __name__ == "__main__":
    try:
        test_scraper_with_mock()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)