#!/usr/bin/env python
"""
Demo script for Google Search Parser
Shows the parser structure and capabilities without making actual requests
"""

import os
import sys
import django
import json

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from services.google_search_parser import GoogleSearchParser


def demonstrate_parser():
    """Demonstrate the parser capabilities"""
    
    print("=" * 70)
    print("Google Search Results Parser - Feature Demonstration")
    print("=" * 70)
    
    parser = GoogleSearchParser()
    
    # Sample HTML snippet (simplified for demo)
    sample_html = """
    <html>
    <body>
        <div id="result-stats">About 2,340,000,000 results (0.42 seconds)</div>
        
        <!-- Sample search result -->
        <div class="g">
            <div class="yuRUbf">
                <a href="https://www.python.org" data-ved="abc123">
                    <h3 class="LC20lb">Python.org - Official Site</h3>
                </a>
            </div>
            <div class="TbwUpd">
                <cite>https://www.python.org</cite>
            </div>
            <div class="VwiC3b">
                <span>The official home of the Python Programming Language. Python is a high-level, 
                interpreted programming language with dynamic semantics...</span>
            </div>
            <img class="XNo5Ab" src="https://www.google.com/s2/favicons?domain=python.org&sz=32">
        </div>
        
        <!-- Another result -->
        <div class="g">
            <div class="yuRUbf">
                <a href="https://www.w3schools.com/python/" ping="/url?sa=t">
                    <h3>Python Tutorial - W3Schools</h3>
                </a>
            </div>
            <cite>www.w3schools.com › python</cite>
            <div class="IsZvec">
                Well organized and easy to understand Web building tutorials with lots of 
                examples of how to use HTML, CSS, JavaScript, SQL, Python...
            </div>
        </div>
        
        <!-- Related searches -->
        <div class="s75CSd">
            <a>python programming for beginners</a>
        </div>
        <div class="s75CSd">
            <a>python programming examples</a>
        </div>
    </body>
    </html>
    """
    
    print("\n📝 Sample HTML Input:")
    print("-" * 40)
    print(sample_html[:300] + "...")
    
    print("\n🔧 Parser Configuration:")
    print("-" * 40)
    print(f"• Result selector strategies: {len(parser.result_selectors)}")
    print(f"• Title selector fallbacks: {len(parser.title_selectors)}")
    print(f"• URL extraction methods: {len(parser.url_selectors)}")
    print(f"• Description selectors: {len(parser.description_selectors)}")
    print(f"• Favicon extraction methods: {len(parser.favicon_selectors)}")
    
    # Parse the sample HTML
    print("\n🔍 Parsing Results:")
    print("-" * 40)
    
    results = parser.parse(sample_html)
    
    print(f"✅ Parsing successful!")
    print(f"• Results found: {results.get('result_count', 0)}")
    print(f"• Total results: {results.get('total_results', 'N/A')}")
    print(f"• Search time: {results.get('search_time', 'N/A')} seconds")
    
    if results.get('results'):
        print("\n📊 Extracted Results:")
        for i, result in enumerate(results['results'], 1):
            print(f"\n  Result #{i}:")
            print(f"  • Title: {result.get('title', 'N/A')}")
            print(f"  • URL: {result.get('url', 'N/A')}")
            print(f"  • Domain: {result.get('domain', 'N/A')}")
            if result.get('description'):
                desc = result['description'][:80]
                if len(result['description']) > 80:
                    desc += '...'
                print(f"  • Description: {desc}")
            if result.get('favicon'):
                print(f"  • Favicon: ✓ Found")
    
    if results.get('related_searches'):
        print(f"\n🔗 Related Searches: {len(results['related_searches'])} found")
        for search in results['related_searches'][:3]:
            print(f"  • {search}")
    
    # Demonstrate selector fallbacks
    print("\n" + "=" * 70)
    print("Selector Fallback System")
    print("=" * 70)
    
    print("\n🛡️ Robustness Features:")
    print("-" * 40)
    
    print("\n1. Result Container Selectors (in priority order):")
    for i, sel in enumerate(parser.result_selectors[:3], 1):
        print(f"   {i}. {sel['selector']} ({sel['type']})")
    
    print("\n2. Title Extraction Fallbacks:")
    for i, sel in enumerate(parser.title_selectors[:3], 1):
        print(f"   {i}. {sel}")
    
    print("\n3. URL Extraction Strategies:")
    print("   • Direct href from anchor tags")
    print("   • Google redirect URL cleaning")
    print("   • Citation text parsing")
    print("   • Data attribute extraction")
    
    print("\n4. Smart Features:")
    print("   • Ad detection and filtering")
    print("   • Special result type detection")
    print("   • Date extraction with multiple patterns")
    print("   • Breadcrumb navigation parsing")
    print("   • Google favicon service fallback")
    
    # Show output structure
    print("\n" + "=" * 70)
    print("Output Data Structure")
    print("=" * 70)
    
    output_structure = {
        'results': [
            {
                'position': 'int - Result position (1-based)',
                'title': 'str - Page title',
                'url': 'str - Clean URL (redirects removed)',
                'domain': 'str - Domain name',
                'description': 'str - Result snippet',
                'favicon': 'str - Favicon URL',
                'breadcrumbs': 'str - Navigation path',
                'date': 'str - Publication date if found'
            }
        ],
        'total_results': 'str - Estimated total results',
        'search_time': 'str - Search execution time',
        'related_searches': ['list', 'of', 'related', 'queries'],
        'people_also_ask': [
            {'question': 'str - Question text', 'expanded': 'bool'}
        ],
        'featured_snippet': {
            'title': 'str - Snippet title',
            'content': 'str - Snippet content',
            'source': 'str - Source URL'
        },
        'knowledge_panel': {
            'title': 'str - Panel title',
            'description': 'str - Panel description',
            'image': 'str - Image URL',
            'facts': ['list', 'of', 'facts']
        },
        'result_count': 'int - Actual parsed results'
    }
    
    print("\n📋 Complete Output Structure:")
    print(json.dumps(output_structure, indent=2, default=str))
    
    # Integration example
    print("\n" + "=" * 70)
    print("Integration Example")
    print("=" * 70)
    
    print("""
from services.google_search_parser import GoogleSearchService

# Initialize service
search_service = GoogleSearchService()

# Perform search with parsing
results = search_service.search(
    query="python programming",
    country_code="US",
    num_results=10
)

# Access parsed results
for result in results['results']:
    print(f"{result['position']}. {result['title']}")
    print(f"   URL: {result['url']}")
    print(f"   Domain: {result['domain']}")
    
# Filter results by domain
edu_results = search_service.search_and_filter(
    query="machine learning",
    country_code="US",
    domain_filter=".edu"
)

# Exclude certain domains
filtered = search_service.search_and_filter(
    query="tutorials",
    exclude_domains=["youtube.com", "facebook.com"]
)
""")
    
    print("\n" + "=" * 70)
    print("✅ Parser demonstration completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        demonstrate_parser()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)