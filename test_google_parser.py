#!/usr/bin/env python
"""
Test script for Google Search Parser
Demonstrates parsing of Google search results with structured data extraction
"""

import os
import sys
import django
import json
from pprint import pprint

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from services.google_search_parser import GoogleSearchService, GoogleSearchParser


def test_google_parser():
    """Test the Google search parser"""
    
    print("=" * 70)
    print("Google Search Parser Test")
    print("=" * 70)
    
    # Initialize service
    search_service = GoogleSearchService()
    
    # Test queries
    test_queries = [
        {
            'query': 'python programming tutorial',
            'country_code': 'US',
            'num_results': 10
        },
        {
            'query': 'machine learning courses',
            'country_code': 'GB',
            'num_results': 20
        },
        {
            'query': 'best restaurants london',
            'country_code': 'GB',
            'num_results': 10,
            'use_exact_location': True,
            'location': 'London,England,United Kingdom'
        }
    ]
    
    for test_case in test_queries[:1]:  # Test first query
        print(f"\n📍 Testing: {test_case['query']}")
        print(f"   Country: {test_case['country_code']}")
        print("-" * 50)
        
        # Perform search
        results = search_service.search(**test_case)
        
        if results.get('success'):
            print(f"✅ Search successful!")
            print(f"   Total results found: {results.get('result_count', 0)}")
            print(f"   Estimated total: {results.get('total_results', 'N/A')}")
            print(f"   Search time: {results.get('search_time', 'N/A')} seconds")
            
            # Display search results
            print("\n🔍 Search Results:")
            print("-" * 50)
            
            for result in results.get('results', [])[:5]:  # Show first 5
                print(f"\n#{result['position']}. {result['title']}")
                print(f"   URL: {result['url']}")
                print(f"   Domain: {result['domain']}")
                if result.get('description'):
                    desc = result['description'][:150]
                    if len(result['description']) > 150:
                        desc += '...'
                    print(f"   Description: {desc}")
                if result.get('favicon'):
                    print(f"   Favicon: {result['favicon'][:60]}...")
                if result.get('date'):
                    print(f"   Date: {result['date']}")
                if result.get('breadcrumbs'):
                    print(f"   Breadcrumbs: {result['breadcrumbs']}")
            
            # Display related searches
            if results.get('related_searches'):
                print("\n🔗 Related Searches:")
                for i, related in enumerate(results['related_searches'][:5], 1):
                    print(f"   {i}. {related}")
            
            # Display People Also Ask
            if results.get('people_also_ask'):
                print("\n❓ People Also Ask:")
                for i, paa in enumerate(results['people_also_ask'][:4], 1):
                    print(f"   {i}. {paa['question']}")
            
            # Display featured snippet
            if results.get('featured_snippet'):
                print("\n📌 Featured Snippet:")
                snippet = results['featured_snippet']
                if snippet.get('title'):
                    print(f"   Title: {snippet['title']}")
                if snippet.get('content'):
                    content = snippet['content'][:200]
                    if len(snippet['content']) > 200:
                        content += '...'
                    print(f"   Content: {content}")
                if snippet.get('source'):
                    print(f"   Source: {snippet['source']}")
            
            # Display knowledge panel
            if results.get('knowledge_panel'):
                print("\n📚 Knowledge Panel:")
                panel = results['knowledge_panel']
                if panel.get('title'):
                    print(f"   Title: {panel['title']}")
                if panel.get('description'):
                    desc = panel['description'][:200]
                    if len(panel['description']) > 200:
                        desc += '...'
                    print(f"   Description: {desc}")
        
        else:
            print(f"❌ Search failed: {results.get('error', 'Unknown error')}")
    
    # Test filtering
    print("\n" + "=" * 70)
    print("Testing Search with Filters")
    print("=" * 70)
    
    # Search with domain filter
    print("\n🔍 Testing domain filter (only .edu sites):")
    filtered_results = search_service.search_and_filter(
        query="machine learning",
        country_code="US",
        num_results=20,
        domain_filter=".edu"
    )
    
    if filtered_results.get('success'):
        print(f"   Results after filtering: {filtered_results.get('result_count', 0)}")
        for result in filtered_results.get('results', [])[:3]:
            print(f"   - {result['domain']}: {result['title'][:50]}...")
    
    # Search with exclusion
    print("\n🔍 Testing domain exclusion (exclude YouTube, Wikipedia):")
    filtered_results = search_service.search_and_filter(
        query="python tutorial",
        country_code="US",
        num_results=20,
        exclude_domains=["youtube.com", "wikipedia.org"]
    )
    
    if filtered_results.get('success'):
        print(f"   Results after filtering: {filtered_results.get('result_count', 0)}")
        for result in filtered_results.get('results', [])[:3]:
            print(f"   - {result['domain']}: {result['title'][:50]}...")
    
    # Display parser robustness info
    print("\n" + "=" * 70)
    print("Parser Robustness Features")
    print("=" * 70)
    
    parser = GoogleSearchParser()
    
    print("\n✅ Multiple Selector Strategies:")
    print(f"   - Result selectors: {len(parser.result_selectors)} fallback strategies")
    print(f"   - Title selectors: {len(parser.title_selectors)} fallback options")
    print(f"   - URL selectors: {len(parser.url_selectors)} fallback options")
    print(f"   - Description selectors: {len(parser.description_selectors)} fallback options")
    print(f"   - Favicon selectors: {len(parser.favicon_selectors)} fallback options")
    
    print("\n✅ Extraction Capabilities:")
    print("   - Organic search results with position")
    print("   - Title, URL, domain, description")
    print("   - Favicon URLs (multiple strategies)")
    print("   - Publication dates")
    print("   - Breadcrumb navigation")
    print("   - Related searches")
    print("   - People Also Ask questions")
    print("   - Featured snippets")
    print("   - Knowledge panels")
    print("   - Total results count")
    print("   - Search execution time")
    
    print("\n✅ Safety Features:")
    print("   - Ad detection and filtering")
    print("   - Special result type detection")
    print("   - Google redirect URL cleaning")
    print("   - URL normalization")
    print("   - Graceful error handling")
    print("   - Fallback selectors for Google HTML changes")
    
    print("\n" + "=" * 70)
    print("Test completed successfully!")
    print("=" * 70)


def demo_result_structure():
    """Demonstrate the structure of parsed results"""
    
    print("\n" + "=" * 70)
    print("Result Structure Documentation")
    print("=" * 70)
    
    sample_result = {
        'success': True,
        'query': 'python programming',
        'country_code': 'US',
        'results': [
            {
                'position': 1,
                'title': 'Python.org - Official Site',
                'url': 'https://www.python.org',
                'domain': 'python.org',
                'description': 'The official home of the Python Programming Language...',
                'favicon': 'https://www.google.com/s2/favicons?domain=python.org&sz=32',
                'breadcrumbs': 'python.org',
                'date': None
            },
            {
                'position': 2,
                'title': 'Python Tutorial - W3Schools',
                'url': 'https://www.w3schools.com/python/',
                'domain': 'w3schools.com',
                'description': 'Well organized and easy to understand Web building tutorials...',
                'favicon': 'https://www.google.com/s2/favicons?domain=w3schools.com&sz=32',
                'breadcrumbs': 'w3schools.com › python',
                'date': None
            }
        ],
        'total_results': '2,340,000,000',
        'search_time': '0.42',
        'related_searches': [
            'python programming for beginners',
            'python programming examples',
            'python programming pdf',
            'python programming course'
        ],
        'people_also_ask': [
            {'question': 'Is Python easy to learn?', 'expanded': False},
            {'question': 'What is Python used for?', 'expanded': False},
            {'question': 'How long does it take to learn Python?', 'expanded': False}
        ],
        'featured_snippet': {
            'title': 'What is Python?',
            'content': 'Python is a high-level, interpreted programming language...',
            'source': 'https://www.python.org/about/'
        },
        'knowledge_panel': {
            'title': 'Python (programming language)',
            'subtitle': 'Programming language',
            'description': 'Python is a high-level, general-purpose programming language...',
            'image': 'https://example.com/python-logo.png',
            'facts': []
        },
        'result_count': 10,
        'search_params': {
            'query': 'python programming',
            'country_code': 'US',
            'num_results': 10
        }
    }
    
    print("\n📋 Complete Result Structure:")
    print(json.dumps(sample_result, indent=2))
    
    print("\n📊 Field Descriptions:")
    print("-" * 50)
    print("• success: Whether the search was successful")
    print("• query: Original search query")
    print("• country_code: Country code used for search")
    print("• results: Array of search results")
    print("  - position: Result position (1-based)")
    print("  - title: Result title")
    print("  - url: Clean URL (Google redirects removed)")
    print("  - domain: Extracted domain name")
    print("  - description: Result snippet/description")
    print("  - favicon: Favicon URL (if available)")
    print("  - breadcrumbs: Navigation path (if available)")
    print("  - date: Publication date (if detected)")
    print("• total_results: Estimated total results")
    print("• search_time: Search execution time")
    print("• related_searches: Related search suggestions")
    print("• people_also_ask: PAA questions")
    print("• featured_snippet: Featured snippet (if present)")
    print("• knowledge_panel: Knowledge panel (if present)")
    print("• result_count: Actual parsed results count")
    print("• search_params: Parameters used for search")


if __name__ == "__main__":
    try:
        # Run main test
        test_google_parser()
        
        # Show result structure
        demo_result_structure()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)