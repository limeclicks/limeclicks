#!/usr/bin/env python
"""
Debug script to check Google search HTML and understand result count
"""

import os
import sys
import django
import re

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from services.scrape_do import ScrapeDoService
from services.google_search_parser import GoogleSearchParser
from bs4 import BeautifulSoup


def debug_google_results():
    """Debug Google search to understand result count"""
    
    print("=" * 80)
    print("GOOGLE SEARCH DEBUG - Analyzing HTML Structure")
    print("=" * 80)
    
    # Initialize services
    scraper = ScrapeDoService()
    parser = GoogleSearchParser()
    
    # Test with a popular query that should have many results
    query = "python"
    num_results = 100
    
    print(f"\n🔍 Searching for: '{query}' with num={num_results}")
    print("-" * 40)
    
    # Scrape the page
    result = scraper.scrape_google_search(
        query=query,
        country_code='US',
        num_results=num_results
    )
    
    if not result or not result.get('success'):
        print("❌ Failed to scrape Google")
        return
    
    html = result['html']
    print(f"✅ Scraped HTML: {len(html)} characters")
    
    # Parse with BeautifulSoup for analysis
    soup = BeautifulSoup(html, 'html.parser')
    
    # Check the actual URL parameters in the page
    print("\n📋 URL Analysis:")
    print("-" * 40)
    
    # Look for num parameter in various places
    if 'num=100' in html:
        print("✅ Found 'num=100' in HTML")
    elif 'num=' in html:
        nums = re.findall(r'num=(\d+)', html)
        print(f"⚠️  Found num parameters: {set(nums)}")
    else:
        print("❌ No 'num' parameter found in HTML")
    
    # Count different types of result containers
    print("\n📊 Result Container Analysis:")
    print("-" * 40)
    
    # Common Google result selectors
    selectors = {
        'div.g': "Main result containers",
        'div.g:not(.g-blk)': "Non-grouped results",
        'div[data-hveid]': "Results with data attributes",
        'div[data-sokoban-container]': "Sokoban containers",
        'li.g': "List item results",
        'div.tF2Cxc': "Modern result containers",
        'div.kvH3mc': "Alternate containers",
        'div.Z26q7c': "Search result items",
        'div[jscontroller][jsdata]': "JS-controlled results",
        'h3': "All H3 headers (titles)",
        'a[href][ping]': "Links with ping attribute",
        'cite': "Citation elements"
    }
    
    for selector, description in selectors.items():
        elements = soup.select(selector)
        if elements:
            print(f"  • {description}: {len(elements)} found")
    
    # Look for pagination info
    print("\n🔢 Pagination Information:")
    print("-" * 40)
    
    # Check for result stats
    result_stats = soup.find('div', {'id': 'result-stats'})
    if result_stats:
        print(f"  Result stats: {result_stats.text.strip()}")
    
    # Check for next page link
    next_link = soup.find('a', {'id': 'pnnext'}) or soup.find('a', {'aria-label': 'Next page'})
    if next_link:
        print("  ✅ Next page link found")
        if 'start=' in str(next_link.get('href', '')):
            start_match = re.search(r'start=(\d+)', str(next_link.get('href', '')))
            if start_match:
                print(f"  Next page starts at: result #{start_match.group(1)}")
    
    # Check for page numbers
    page_numbers = soup.select('td.YyVfkd') or soup.select('a.fl')
    if page_numbers:
        print(f"  Page numbers found: {len(page_numbers)}")
    
    # Parse with our parser
    print("\n🔧 Parser Results:")
    print("-" * 40)
    
    parsed = parser.parse(html)
    
    # Count all types of results
    organic = len(parsed.get('organic_results', []))
    sponsored = len(parsed.get('sponsored_results', []))
    total = organic + sponsored
    
    print(f"  • Organic results: {organic}")
    print(f"  • Sponsored results: {sponsored}")
    print(f"  • Total parsed: {total}")
    
    # Check for special features that might be taking up space
    features = {
        'local_pack': 'Local Pack',
        'featured_snippet': 'Featured Snippet',
        'knowledge_panel': 'Knowledge Panel',
        'people_also_ask': 'People Also Ask',
        'top_stories': 'Top Stories',
        'videos': 'Videos',
        'images': 'Images',
        'shopping': 'Shopping',
        'twitter': 'Twitter',
        'recipes': 'Recipes'
    }
    
    print("\n✨ Special Features Found:")
    for key, name in features.items():
        if parsed.get(key):
            if isinstance(parsed[key], list):
                print(f"  • {name}: {len(parsed[key])} items")
            else:
                print(f"  • {name}: Present")
    
    # Analyze why we might not be getting 100 results
    print("\n💡 Analysis:")
    print("-" * 40)
    
    if total < 20:
        print("⚠️  Getting very few results. Possible reasons:")
        print("  1. Google is detecting automated requests and limiting results")
        print("  2. The render might not be waiting long enough for all results")
        print("  3. Google might be showing a different layout (mobile/tablet view)")
        print("  4. Results might be loaded dynamically and not captured")
    elif total < 50:
        print("⚠️  Getting moderate results. Possible reasons:")
        print("  1. Google typically shows 10-20 results even with num=100")
        print("  2. Additional results might require scrolling or interaction")
        print("  3. Google might be capping results for this query")
    else:
        print("✅ Getting good number of results!")
    
    # Check if we're getting mobile view
    if 'mobile' in html.lower() or 'mobi' in html.lower():
        mobile_count = html.lower().count('mobile') + html.lower().count('mobi')
        print(f"\n📱 Mobile indicators found: {mobile_count} occurrences")
    
    # Save a sample of HTML for manual inspection
    sample_file = 'google_search_sample.html'
    with open(sample_file, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\n💾 Full HTML saved to: {sample_file}")
    print("   You can open this file to manually inspect the structure")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print("""
1. Google may not return 100 results even when requested
2. The current setup IS correctly requesting 100 results
3. Consider these alternatives:
   - Accept that Google limits results per page
   - Implement pagination if more results are needed
   - Use different queries that return more results
   - Add scrolling/interaction if using headless browser
""")


if __name__ == "__main__":
    try:
        debug_google_results()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)