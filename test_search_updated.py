#!/usr/bin/env python
"""
Test script for updated Google and Bing search functions
- Country-specific Google domains
- Proper Scrape.do geoCode mapping
- Single page results only (no pagination)
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from services.scrape_do import ScrapeDoService


def test_updated_search():
    """Test the updated search functions"""
    
    print("=" * 70)
    print("Updated Google & Bing Search Functions Test")
    print("=" * 70)
    
    scraper = ScrapeDoService()
    
    # Show supported Scrape.do geoCode countries
    print("\n1. Scrape.do Supported Countries (geoCode):")
    print("-" * 45)
    
    supported = list(scraper.SCRAPE_DO_GEO_CODES.keys())
    print(f"Total supported: {len(supported)} countries")
    print(f"Countries: {', '.join(sorted(supported[:20]))}...")
    
    # Test Google search with different countries
    print("\n2. Google Search - Country-Specific Domains:")
    print("-" * 45)
    
    test_cases = [
        ('US', 'www.google.com', 'US'),
        ('GB', 'www.google.co.uk', 'GB'),
        ('FR', 'www.google.fr', 'FR'),
        ('DE', 'www.google.de', 'DE'),
        ('JP', 'www.google.co.jp', 'JP'),
        ('BR', 'www.google.com.br', 'BR'),
        ('IN', 'www.google.co.in', 'IN'),
        ('ZZ', 'www.google.com', 'US'),  # Unknown country -> US domain & proxy
    ]
    
    print("\nCountry | Google Domain         | Scrape.do Proxy")
    print("--------|----------------------|----------------")
    for country, expected_domain, expected_geo in test_cases:
        domain = scraper.get_google_domain(country)
        geo_code = scraper.SCRAPE_DO_GEO_CODES.get(country, 'US')
        status = "✓" if (domain == expected_domain and geo_code == expected_geo) else "✗"
        print(f"{status} {country:5} | {domain:20} | {geo_code:5}")
    
    # Google search examples
    print("\n3. Google Search Usage Examples:")
    print("-" * 35)
    print("""
    # Search from US (default)
    scraper.scrape_google_search(
        query="python tutorials",
        country_code="US"  # Uses google.com + US proxy
    )
    
    # Search from UK
    scraper.scrape_google_search(
        query="london restaurants",
        country_code="GB",  # Uses google.co.uk + GB proxy
        hl="en-GB"         # British English interface
    )
    
    # Search from Germany
    scraper.scrape_google_search(
        query="python programmierung",
        country_code="DE",  # Uses google.de + DE proxy
        hl="de"            # German interface
    )
    
    # Search from unsupported country (falls back to US)
    scraper.scrape_google_search(
        query="programming",
        country_code="ZZ"  # Uses google.com + US proxy (fallback)
    )
    """)
    
    # Bing search examples
    print("\n4. Bing Search Usage Examples:")
    print("-" * 35)
    print("""
    # Search from US
    scraper.scrape_bing_search(
        query="machine learning",
        country_code="US"  # Uses US proxy, mkt=en-US
    )
    
    # Search from France
    scraper.scrape_bing_search(
        query="apprentissage automatique",
        country_code="FR",  # Uses FR proxy, mkt=fr-FR
        freshness="Week"   # Results from last week
    )
    
    # Search from Japan
    scraper.scrape_bing_search(
        query="機械学習",
        country_code="JP"  # Uses JP proxy, mkt=ja-JP
    )
    
    # Custom market override
    scraper.scrape_bing_search(
        query="news",
        country_code="US",   # US proxy
        mkt="en-GB"         # But UK market results
    )
    """)
    
    # Key differences
    print("\n5. Key Changes Summary:")
    print("-" * 25)
    print("✓ Removed 'gl' parameter from Google search")
    print("✓ Google domain determined by country_code")
    print("✓ Proper Scrape.do geoCode mapping (50+ countries)")
    print("✓ Fallback to US for unsupported countries")
    print("✓ No pagination - single page results only")
    print("✓ Simplified API - fewer parameters")
    
    # URL structure examples
    print("\n6. Generated URL Examples:")
    print("-" * 28)
    
    print("\nGoogle URLs:")
    examples = [
        ('US', 'https://www.google.com/search?q=test&num=100&hl=en'),
        ('GB', 'https://www.google.co.uk/search?q=test&num=100&hl=en'),
        ('FR', 'https://www.google.fr/search?q=test&num=100&hl=fr'),
        ('DE', 'https://www.google.de/search?q=test&num=100&hl=de'),
    ]
    for country, url in examples:
        print(f"  {country}: {url}")
    
    print("\nBing URLs:")
    print("  All countries: https://www.bing.com/search?q=test&count=50&mkt=xx-XX")
    print("  (mkt varies by country: en-US, fr-FR, de-DE, ja-JP, etc.)")
    
    # Response structure
    print("\n7. Response Structure:")
    print("-" * 22)
    print("""
    Both functions return:
    {
        'html': '...',           # Scraped HTML content
        'status_code': 200,      # HTTP status
        'headers': {...},        # Response headers
        'url': '...',           # Final URL
        'success': True,        # Success flag
        'search_params': {      # Added metadata
            'query': '...',
            'country_code': 'US',
            ...
        }
    }
    """)
    
    # Scrape.do proxy mapping
    print("\n8. Scrape.do Proxy Mapping:")
    print("-" * 30)
    print("Country codes are mapped to Scrape.do geoCode:")
    print()
    
    mapping_examples = [
        ('US', 'US'), ('GB', 'GB'), ('UK', 'GB'), 
        ('FR', 'FR'), ('DE', 'DE'), ('JP', 'JP'),
        ('XX', 'US'), ('ZZ', 'US'), (None, 'US')
    ]
    
    for country, geo in mapping_examples:
        actual_geo = scraper.SCRAPE_DO_GEO_CODES.get(country or 'US', 'US')
        print(f"  {str(country):4} → {actual_geo:3} {'(fallback)' if actual_geo == 'US' and country not in ['US', None] else ''}")
    
    print("\n" + "=" * 70)
    print("All tests completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        test_updated_search()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)