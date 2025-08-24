#!/usr/bin/env python
"""
Demo script for enhanced Google search functionality with Scrape.do
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from services.scrape_do import get_scraper


def demonstrate_google_search():
    """Demonstrate the enhanced Google search capabilities"""
    
    print("=" * 70)
    print("Enhanced Google Search with Scrape.do Service")
    print("=" * 70)
    
    scraper = get_scraper()
    
    # Example 1: Basic search with 100 results
    print("\n1. Basic Google Search (100 results):")
    print("-" * 40)
    print("""
    scraper.scrape_google_search(
        query='python web scraping',
        num_results=100,  # Get 100 results
        gl='us',          # USA results
        hl='en'           # English interface
    )
    """)
    
    # Example 2: Location-based search with UULE
    print("\n2. Location-based Search with UULE:")
    print("-" * 40)
    
    location = "New York,New York,United States"
    uule = scraper.encode_uule(location)
    print(f"Location: {location}")
    print(f"UULE Encoded: {uule}")
    print("""
    scraper.scrape_google_search(
        query='restaurants',
        location='New York,New York,United States',
        use_exact_location=True,
        gl='us',
        hl='en'
    )
    """)
    
    # Example 3: Multi-language search
    print("\n3. Multi-language Search (German):")
    print("-" * 40)
    print("""
    scraper.scrape_google_search(
        query='python programmierung',
        gl='de',           # German results
        hl='de',           # German interface
        country_code='de', # German proxy
        num_results=100
    )
    """)
    
    # Example 4: Paginated search
    print("\n4. Paginated Search Results:")
    print("-" * 40)
    print("""
    # Page 1 (results 1-100)
    page1 = scraper.scrape_google_search(
        query='machine learning jobs',
        start=0,
        num_results=100
    )
    
    # Page 2 (results 101-200)
    page2 = scraper.scrape_google_search(
        query='machine learning jobs',
        start=100,
        num_results=100
    )
    
    # Page 3 (results 201-300)
    page3 = scraper.scrape_google_search(
        query='machine learning jobs',
        start=200,
        num_results=100
    )
    """)
    
    # Example 5: Multiple pages at once
    print("\n5. Scrape Multiple Pages at Once:")
    print("-" * 40)
    print("""
    all_results = scraper.scrape_google_search_pages(
        query='data science tutorials',
        pages=3,               # Get 3 pages
        results_per_page=100,  # 100 results per page
        gl='us',
        hl='en'
    )
    # Returns list with 3 result sets (300 results total)
    """)
    
    # Example 6: Safe search
    print("\n6. Safe Search Settings:")
    print("-" * 40)
    print("""
    # Strict safe search
    safe_results = scraper.scrape_google_search(
        query='adult content filter test',
        safe='active',     # Strict filtering
        num_results=50
    )
    
    # Moderate safe search (default)
    moderate_results = scraper.scrape_google_search(
        query='content filter test',
        safe='moderate'
    )
    
    # No safe search
    unfiltered_results = scraper.scrape_google_search(
        query='unfiltered search',
        safe='off'
    )
    """)
    
    # Show different location UULE examples
    print("\n7. UULE Examples for Different Locations:")
    print("-" * 40)
    
    locations = [
        "London,England,United Kingdom",
        "Tokyo,Japan",
        "Paris,France",
        "Sydney,New South Wales,Australia",
        "Toronto,Ontario,Canada"
    ]
    
    for loc in locations:
        uule = scraper.encode_uule(loc)
        print(f"  {loc}")
        print(f"  → {uule[:50]}...")
    
    # URL Building Example
    print("\n8. Complete URL Example:")
    print("-" * 40)
    print("""
    Final Google URL structure:
    https://www.google.com/search?
        q=python+django              # Search query
        &num=100                     # Number of results
        &gl=us                       # Country for results
        &hl=en                       # Interface language
        &uule=w+CAIQICI...          # Exact location (optional)
        &safe=moderate              # Safe search (optional)
        &start=0                    # Starting position (optional)
    
    This URL is then passed to Scrape.do with:
    - timeout=60000 (60 seconds)
    - render=true (JavaScript rendering)
    - wait_for=3000 (3 seconds wait)
    - geoCode=us (proxy location)
    """)
    
    print("\n" + "=" * 70)
    print("Key Features:")
    print("-" * 15)
    print("✓ Support for up to 100 results per request (num=100)")
    print("✓ UULE encoding for precise location targeting")
    print("✓ gl parameter for country-specific results")
    print("✓ hl parameter for interface language")
    print("✓ 60-second timeout for large result sets")
    print("✓ Pagination support for getting more results")
    print("✓ Multi-page scraping helper function")
    print("✓ Safe search control")
    print("✓ Proper URL encoding for special characters")
    print("=" * 70)


if __name__ == "__main__":
    try:
        demonstrate_google_search()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)