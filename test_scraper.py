#!/usr/bin/env python
"""
Quick test script to verify Scrape.do service is working
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from services.scrape_do import get_scraper

def test_scraper():
    """Test the Scrape.do service with a simple example"""
    
    print("Testing Scrape.do Service")
    print("=" * 50)
    
    # Get the scraper instance
    scraper = get_scraper()
    print(f"✓ Scraper initialized with API key: {scraper.api_key[:10]}...")
    
    # Test 1: Simple scraping (using httpbin for testing)
    print("\n1. Testing basic scraping...")
    test_url = "https://httpbin.org/html"
    result = scraper.scrape(test_url, use_cache=False)
    
    if result and result.get('success'):
        print(f"   ✓ Successfully scraped {test_url}")
        print(f"   - Status code: {result['status_code']}")
        print(f"   - Content length: {len(result['html'])} characters")
        print(f"   - Contains 'Herman Melville': {'Herman Melville' in result['html']}")
    else:
        print(f"   ✗ Failed to scrape: {result.get('error', 'Unknown error')}")
    
    # Test 2: URL with special characters
    print("\n2. Testing URL with special characters...")
    search_url = "https://httpbin.org/get?search=hello world&filter=price>100&name=café"
    result = scraper.scrape(search_url, use_cache=False)
    
    if result and result.get('success'):
        print(f"   ✓ Successfully handled special characters")
        print(f"   - Status code: {result['status_code']}")
        # Check if parameters are preserved in the response
        if 'hello world' in result['html'] or 'hello%20world' in result['html']:
            print(f"   - Query parameters preserved correctly")
    else:
        print(f"   ✗ Failed: {result.get('error', 'Unknown error')}")
    
    # Test 3: Caching
    print("\n3. Testing caching...")
    cache_url = "https://httpbin.org/uuid"
    
    # First request (no cache)
    result1 = scraper.scrape(cache_url, use_cache=True)
    uuid1 = result1['html'] if result1.get('success') else None
    
    # Second request (should use cache)
    result2 = scraper.scrape(cache_url, use_cache=True)
    uuid2 = result2['html'] if result2.get('success') else None
    
    if uuid1 and uuid2:
        if uuid1 == uuid2:
            print(f"   ✓ Caching works - same content returned")
        else:
            print(f"   ✗ Cache not working - different content")
    
    # Third request without cache
    result3 = scraper.scrape(cache_url, use_cache=False)
    uuid3 = result3['html'] if result3.get('success') else None
    
    if uuid1 and uuid3 and uuid1 != uuid3:
        print(f"   ✓ Cache bypass works - new content fetched")
    
    # Test 4: Country-specific scraping
    print("\n4. Testing geo-location scraping...")
    geo_url = "https://httpbin.org/headers"
    
    for country in ['us', 'uk', 'de']:
        result = scraper.scrape(geo_url, country_code=country, use_cache=False)
        if result and result.get('success'):
            print(f"   ✓ Successfully scraped with country code: {country}")
        else:
            print(f"   ✗ Failed for country: {country}")
    
    print("\n" + "=" * 50)
    print("Testing complete!")
    
    # Optional: Show API usage if available
    usage = scraper.get_usage()
    if usage:
        print(f"\nAPI Usage: {usage}")

if __name__ == "__main__":
    try:
        test_scraper()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)