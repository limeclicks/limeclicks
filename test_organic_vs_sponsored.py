#!/usr/bin/env python
"""
Test script for Google Search Parser - Organic vs Sponsored Results
Demonstrates the separation of organic and sponsored search results
"""

import os
import sys
import django
import json

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from services.google_search_parser import GoogleSearchParser


def test_organic_vs_sponsored():
    """Test the separation of organic and sponsored results"""
    
    print("=" * 70)
    print("Google Search Parser - Organic vs Sponsored Results")
    print("=" * 70)
    
    parser = GoogleSearchParser()
    
    # Sample HTML with both organic and sponsored results
    sample_html = """
    <html>
    <body>
        <div id="result-stats">About 5,340,000 results (0.52 seconds)</div>
        
        <!-- Sponsored Result 1 -->
        <div class="g" data-text-ad="1">
            <span class="D1fz0e">Ad</span>
            <div class="yuRUbf">
                <a href="https://www.sponsored-site.com/buy-shoes" data-ved="ad123">
                    <h3>Buy Shoes Online - Best Prices | Sponsored Site</h3>
                </a>
            </div>
            <cite class="iUh30">www.sponsored-site.com</cite>
            <div class="VwiC3b">
                <span>Great deals on shoes. Free shipping on orders over $50. 
                Shop our huge selection of footwear.</span>
            </div>
            <div class="MhgNwc">
                <a href="/mens-shoes">Men's Shoes</a>
                <a href="/womens-shoes">Women's Shoes</a>
                <a href="/sale">Sale Items</a>
            </div>
            <div class="Lu0opc">
                <span>✓ Free Shipping</span>
                <span>✓ 30-Day Returns</span>
                <span>✓ Best Prices</span>
            </div>
        </div>
        
        <!-- Sponsored Result 2 -->
        <div class="g ads-ad">
            <span>Sponsored</span>
            <a href="https://www.adshoes.com/premium">
                <h3>Premium Footwear Collection - AdShoes.com</h3>
            </a>
            <cite>www.adshoes.com</cite>
            <div class="IsZvec">
                Luxury shoes and accessories. Designer brands at competitive prices.
            </div>
        </div>
        
        <!-- Organic Result 1 -->
        <div class="g">
            <div class="yuRUbf">
                <a href="https://www.hushpuppies.com.pk" data-ved="org123">
                    <h3 class="LC20lb">Hush Puppies - Buy Shoes Online in Pakistan</h3>
                </a>
            </div>
            <cite>https://www.hushpuppies.com.pk</cite>
            <div class="VwiC3b">
                <span>Hush Puppies brings footwear for men, women and children for everyday comfort. 
                Shop for formal, casual, sandals, flats, heels & walking shoes in Pakistan.</span>
            </div>
            <img class="XNo5Ab" src="https://www.google.com/s2/favicons?domain=hushpuppies.com.pk&sz=32">
        </div>
        
        <!-- Organic Result 2 -->
        <div class="g">
            <div class="yuRUbf">
                <a href="https://www.trendlad.co">
                    <h3>Trend Lad- Pakistan's No.1 Footwear Brand</h3>
                </a>
            </div>
            <cite>https://www.trendlad.co</cite>
            <div class="IsZvec">
                DISCOVER OUR COLLECTION - Monk Shoes · Formal Lace Ups · Loafers · Driving 
                Loafers · Peshawari Chappal · Sandals & Slippers ...
            </div>
        </div>
        
        <!-- Shopping Ad (Sponsored) -->
        <div class="commercial-unit-desktop-top">
            <div class="uEierd">
                <span>Sponsored</span>
                <div class="pla-unit">
                    <a href="https://shop.example.com/product1">
                        <img src="product1.jpg">
                        <div class="price">$49.99</div>
                        <div>Running Shoes</div>
                    </a>
                </div>
            </div>
        </div>
        
        <!-- Organic Result 3 -->
        <div class="g">
            <a href="https://www.wikipedia.org/wiki/Footwear">
                <h3>Footwear - Wikipedia</h3>
            </a>
            <cite>en.wikipedia.org › wiki › Footwear</cite>
            <div class="VwiC3b">
                Footwear refers to garments worn on the feet, which typically serves the purpose 
                of protection against adversities of the environment...
            </div>
        </div>
    </body>
    </html>
    """
    
    print("\n🔍 Parsing Sample HTML...")
    print("-" * 40)
    
    results = parser.parse(sample_html)
    
    # Display Organic Results
    print("\n✅ ORGANIC RESULTS:")
    print("-" * 40)
    print(f"Total Organic Results: {results.get('organic_count', 0)}")
    
    for result in results.get('organic_results', []):
        print(f"\n#{result['position']}. {result['title']}")
        print(f"   URL: {result['url']}")
        print(f"   Domain: {result['domain']}")
        print(f"   Type: {result.get('result_type', 'organic')}")
        if result.get('description'):
            desc = result['description'][:100]
            if len(result['description']) > 100:
                desc += '...'
            print(f"   Description: {desc}")
        if result.get('favicon'):
            print(f"   Favicon: ✓")
    
    # Display Sponsored Results
    print("\n💰 SPONSORED RESULTS:")
    print("-" * 40)
    print(f"Total Sponsored Results: {results.get('sponsored_count', 0)}")
    
    for result in results.get('sponsored_results', []):
        print(f"\n#{result['position']}. {result['title']}")
        print(f"   URL: {result['url']}")
        print(f"   Domain: {result['domain']}")
        print(f"   Type: {result.get('result_type', 'sponsored')}")
        print(f"   Ad Format: {result.get('ad_format', 'text')}")
        if result.get('ad_label'):
            print(f"   Label: {result['ad_label']}")
        if result.get('advertiser'):
            print(f"   Advertiser: {result['advertiser']}")
        if result.get('description'):
            desc = result['description'][:100]
            if len(result['description']) > 100:
                desc += '...'
            print(f"   Description: {desc}")
        
        # Display ad extensions if present
        if result.get('ad_extensions'):
            extensions = result['ad_extensions']
            if extensions.get('sitelinks'):
                print(f"   Sitelinks:")
                for link in extensions['sitelinks'][:3]:
                    print(f"     • {link['text']}")
            if extensions.get('callouts'):
                print(f"   Callouts: {', '.join(extensions['callouts'][:3])}")
            if extensions.get('price'):
                print(f"   Price: {extensions['price']}")
            if extensions.get('rating'):
                print(f"   Rating: {extensions['rating']}")
            if extensions.get('phone'):
                print(f"   Phone: {extensions['phone']}")
    
    # Summary Statistics
    print("\n📊 SUMMARY:")
    print("-" * 40)
    print(f"Total Results Parsed: {results.get('organic_count', 0) + results.get('sponsored_count', 0)}")
    print(f"  • Organic: {results.get('organic_count', 0)}")
    print(f"  • Sponsored: {results.get('sponsored_count', 0)}")
    if results.get('total_results'):
        print(f"Estimated Total Results: {results['total_results']}")
    if results.get('search_time'):
        print(f"Search Time: {results['search_time']} seconds")
    
    # Show structure of sponsored result
    print("\n" + "=" * 70)
    print("Sponsored Result Data Structure")
    print("=" * 70)
    
    sample_sponsored = {
        'position': 1,
        'title': 'Buy Shoes Online - Best Prices',
        'url': 'https://www.sponsored-site.com/shoes',
        'domain': 'sponsored-site.com',
        'description': 'Great deals on shoes...',
        'favicon': 'https://...',
        'result_type': 'sponsored',
        'is_sponsored': True,
        'ad_format': 'text',  # text, shopping, local, call
        'ad_label': 'Ad',  # or 'Sponsored'
        'advertiser': 'www.sponsored-site.com',
        'ad_extensions': {
            'sitelinks': [
                {'text': "Men's Shoes", 'url': 'https://...'},
                {'text': "Women's Shoes", 'url': 'https://...'}
            ],
            'callouts': ['Free Shipping', '30-Day Returns', 'Best Prices'],
            'structured_snippets': ['Types: Running, Casual, Formal'],
            'price': '$49.99',
            'rating': '4.5 stars',
            'phone': '+1-800-SHOES'
        }
    }
    
    print("\n📋 Sponsored Result Fields:")
    print(json.dumps(sample_sponsored, indent=2))
    
    # Show detection methods
    print("\n" + "=" * 70)
    print("Ad Detection Methods")
    print("=" * 70)
    
    print("\n🔍 How We Identify Sponsored Results:")
    print("-" * 40)
    print("1. Ad Labels:")
    print("   • 'Ad' or 'Sponsored' text labels")
    print("   • aria-label attributes containing 'Ad'")
    print("   • CSS classes: .D1fz0e, .ads-label")
    print("\n2. Data Attributes:")
    print("   • data-text-ad")
    print("   • data-rw (text ads)")
    print("   • aria-label='Advertisement'")
    print("\n3. Container Classes:")
    print("   • .ads-ad")
    print("   • .commercial-unit (shopping ads)")
    print("   • .uEierd (shopping carousel)")
    print("\n4. Ad Formats Detected:")
    print("   • Text ads (standard search ads)")
    print("   • Shopping ads (product listings)")
    print("   • Local ads (with addresses/maps)")
    print("   • Call ads (with phone numbers)")
    
    # Usage example
    print("\n" + "=" * 70)
    print("Usage Example")
    print("=" * 70)
    
    print("""
from services.google_search_parser import GoogleSearchService

# Initialize service
service = GoogleSearchService()

# Perform search
results = service.search(
    query="buy shoes online",
    country_code="US",
    num_results=20
)

# Access organic results only
print(f"Organic Results: {results['organic_count']}")
for result in results['organic_results']:
    print(f"  • {result['title']} - {result['domain']}")

# Access sponsored results
print(f"\\nSponsored Results: {results['sponsored_count']}")
for result in results['sponsored_results']:
    print(f"  • [AD] {result['title']} - {result['domain']}")
    if result.get('ad_extensions', {}).get('sitelinks'):
        print(f"    Sitelinks: {len(result['ad_extensions']['sitelinks'])}")

# Filter to exclude sponsored results
filtered = service.search_and_filter(
    query="python tutorials",
    include_sponsored=False  # Exclude ads
)
print(f"\\nFiltered (Organic Only): {filtered['organic_count']} results")
""")
    
    print("\n" + "=" * 70)
    print("✅ Test completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        test_organic_vs_sponsored()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)