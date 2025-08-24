#!/usr/bin/env python
"""
Quick test for Google search with special characters
"""

import os
import sys
import django
import time

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from services.google_search_parser import GoogleSearchService


def test_special_characters():
    """Test a few queries with special characters"""
    
    print("="*80)
    print("GOOGLE SEARCH - SPECIAL CHARACTERS TEST")
    print("="*80)
    
    google_service = GoogleSearchService()
    
    # Test cases focusing on special characters
    test_queries = [
        ("Simple query", "python tutorial"),
        ("With apostrophe", "McDonald's restaurants"),
        ("With ampersand", "AT&T customer service"),
        ("With quotes", '"machine learning" algorithms'),
        ("With plus", "C++ programming language"),
        ("Complex mix", "O'Reilly's \"Python\" & Data Science books"),
        ("With hashtag", "#python tips"),
        ("With hyphen", "COVID-19 vaccine"),
        ("Mathematical", "2+2*3 calculator"),
        ("URL format", "site:github.com python"),
    ]
    
    print(f"\nTesting {len(test_queries)} queries with special characters...")
    print(f"Timeout set to 30 seconds per query\n")
    
    results_summary = []
    
    for test_name, query in test_queries:
        print(f"\n{'='*60}")
        print(f"Test: {test_name}")
        print(f"Query: {query}")
        print("-"*40)
        
        start_time = time.time()
        
        try:
            # Search with 100 results requested
            results = google_service.search(
                query=query,
                country_code='US',
                num_results=100
            )
            
            elapsed = time.time() - start_time
            
            if results and results.get('success'):
                organic = results.get('organic_count', 0)
                sponsored = results.get('sponsored_count', 0)
                total = organic + sponsored
                
                print(f"✅ Success in {elapsed:.2f}s")
                print(f"   • Organic results: {organic}")
                print(f"   • Sponsored results: {sponsored}")
                print(f"   • Total results: {total}")
                
                # Show first result
                if organic > 0 and results.get('organic_results'):
                    first = results['organic_results'][0]
                    print(f"\n   First result:")
                    print(f"   Title: {first.get('title', 'N/A')[:60]}")
                    print(f"   Domain: {first.get('domain', 'N/A')}")
                
                # Check timeout
                if elapsed > 30:
                    print(f"\n   ⚠️ WARNING: Exceeded 30s timeout ({elapsed:.2f}s)")
                
                results_summary.append({
                    'test': test_name,
                    'query': query,
                    'success': True,
                    'results': total,
                    'time': elapsed
                })
                
            else:
                print(f"❌ Failed: {results.get('error', 'Unknown error')}")
                results_summary.append({
                    'test': test_name,
                    'query': query,
                    'success': False,
                    'results': 0,
                    'time': elapsed
                })
                
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ Exception: {str(e)}")
            results_summary.append({
                'test': test_name,
                'query': query,
                'success': False,
                'results': 0,
                'time': elapsed,
                'error': str(e)
            })
        
        # Small delay between requests
        time.sleep(0.5)
    
    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    successful = sum(1 for r in results_summary if r['success'])
    failed = len(results_summary) - successful
    avg_time = sum(r['time'] for r in results_summary) / len(results_summary)
    avg_results = sum(r['results'] for r in results_summary) / len(results_summary)
    
    print(f"\nTotal tests: {len(results_summary)}")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"\n📊 Statistics:")
    print(f"   • Average response time: {avg_time:.2f}s")
    print(f"   • Average results count: {avg_results:.1f}")
    
    # Check for timeout issues
    slow_queries = [r for r in results_summary if r['time'] > 30]
    if slow_queries:
        print(f"\n⚠️ Queries exceeding 30s timeout:")
        for r in slow_queries:
            print(f"   • {r['test']}: {r['time']:.2f}s")
    else:
        print(f"\n✅ All queries completed within 30s timeout")
    
    # Show any failed queries
    failed_queries = [r for r in results_summary if not r['success']]
    if failed_queries:
        print(f"\n❌ Failed queries:")
        for r in failed_queries:
            print(f"   • {r['test']}: {r.get('error', 'Failed')}")
    
    print("\n" + "="*80)
    if failed == 0:
        print("✅ ALL TESTS PASSED - Special characters handled correctly!")
    else:
        print(f"⚠️ {failed} TESTS FAILED - Check special character encoding")
    print("="*80)
    
    return successful == len(results_summary)


if __name__ == "__main__":
    try:
        success = test_special_characters()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)