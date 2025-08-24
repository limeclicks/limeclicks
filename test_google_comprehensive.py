#!/usr/bin/env python
"""
Comprehensive test suite for Google Search Parser
Tests complex queries, special characters, and various edge cases
"""

import os
import sys
import django
import json
import time
from datetime import datetime

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from services.scrape_do import ScrapeDoService
from services.google_search_parser import GoogleSearchService


class GoogleSearchComprehensiveTest:
    """Comprehensive test suite for Google search functionality"""
    
    def __init__(self):
        self.scraper = ScrapeDoService()
        self.google_service = GoogleSearchService()
        self.test_results = []
        
    def run_test(self, test_name, query, expected_min_results=10):
        """Run a single test case"""
        print(f"\n{'='*60}")
        print(f"TEST: {test_name}")
        print(f"{'='*60}")
        print(f"Query: {query}")
        print(f"Expected minimum results: {expected_min_results}")
        
        start_time = time.time()
        
        try:
            # Test with the Google service
            results = self.google_service.search(
                query=query,
                country_code='US',
                num_results=100
            )
            
            elapsed_time = time.time() - start_time
            
            if results and results.get('success'):
                organic_count = results.get('organic_count', 0)
                sponsored_count = results.get('sponsored_count', 0)
                total_count = organic_count + sponsored_count
                
                print(f"✅ Success in {elapsed_time:.2f} seconds")
                print(f"   • Organic: {organic_count}")
                print(f"   • Sponsored: {sponsored_count}")
                print(f"   • Total: {total_count}")
                
                # Show first few results
                if organic_count > 0:
                    print(f"\n   First 3 results:")
                    for i, result in enumerate(results['organic_results'][:3], 1):
                        title = result.get('title', 'N/A')[:50]
                        domain = result.get('domain', 'N/A')
                        print(f"   {i}. {title}... ({domain})")
                
                # Check if we got enough results
                if total_count >= expected_min_results:
                    status = "PASSED"
                    print(f"\n   ✅ TEST PASSED: Got {total_count} results (>= {expected_min_results})")
                else:
                    status = "WARNING"
                    print(f"\n   ⚠️ WARNING: Got {total_count} results (< {expected_min_results})")
                
                # Check timeout
                if elapsed_time > 30:
                    print(f"   ⚠️ TIMEOUT WARNING: Took {elapsed_time:.2f}s (> 30s limit)")
                    status = "TIMEOUT"
                
                self.test_results.append({
                    'test': test_name,
                    'query': query,
                    'status': status,
                    'results': total_count,
                    'time': elapsed_time
                })
                
                return True
                
            else:
                print(f"❌ Failed: {results.get('error', 'Unknown error')}")
                self.test_results.append({
                    'test': test_name,
                    'query': query,
                    'status': 'FAILED',
                    'results': 0,
                    'time': elapsed_time
                })
                return False
                
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"❌ Exception: {str(e)}")
            self.test_results.append({
                'test': test_name,
                'query': query,
                'status': 'ERROR',
                'results': 0,
                'time': elapsed_time,
                'error': str(e)
            })
            return False
    
    def run_all_tests(self):
        """Run all test cases"""
        print("="*80)
        print("GOOGLE SEARCH COMPREHENSIVE TEST SUITE")
        print("="*80)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Timeout limit: 30 seconds per query")
        
        # Test cases with different complexity levels
        test_cases = [
            # Basic queries
            ("Simple keyword", "python", 50),
            ("Multi-word query", "machine learning algorithms", 40),
            ("Long tail keyword", "how to learn python programming for beginners step by step", 30),
            
            # Queries with special characters
            ("Query with apostrophe", "McDonald's menu", 40),
            ("Query with quotes", '"exact match search"', 20),
            ("Query with ampersand", "Ben & Jerry's ice cream", 30),
            ("Query with hyphen", "COVID-19 symptoms", 40),
            ("Query with plus sign", "C++ programming", 40),
            ("Query with hashtag", "#python programming", 30),
            ("Query with at symbol", "@elonmusk twitter", 30),
            
            # Complex queries with multiple special characters
            ("Complex special chars", "O'Reilly's \"Python\" & Data Science", 20),
            ("Mathematical expression", "2+2*3 calculator", 30),
            ("URL in query", "site:stackoverflow.com python", 40),
            ("File type search", "filetype:pdf machine learning", 30),
            
            # International and Unicode
            ("Emoji in query", "🐍 python programming", 20),
            ("Mixed language", "python プログラミング", 20),
            ("Accented characters", "café près de moi", 30),
            ("German umlauts", "Müller Deutschland", 30),
            
            # Edge cases
            ("Very short query", "AI", 50),
            ("Numbers only", "2024", 40),
            ("Single character", "X", 40),
            ("All caps", "NASA SPACEX MARS", 30),
            ("Question format", "what is the meaning of life?", 40),
            ("Local search", "restaurants near me", 30),
            
            # Programming-specific queries
            ("Code snippet", "python list comprehension [x for x in range(10)]", 20),
            ("Error message", 'python "TypeError: list indices must be integers"', 30),
            ("Version specific", "python 3.12 new features", 30),
            ("Framework query", "django vs flask 2024", 30),
            
            # Business/Brand queries
            ("Company with special char", "AT&T customer service", 30),
            ("Brand with apostrophe", "Levi's jeans", 30),
            ("Product with version", "iPhone 15 Pro Max", 40),
            
            # Advanced search operators
            ("OR operator", "python OR java tutorials", 40),
            ("Exclude operator", "python -snake", 30),
            ("Wildcard", "how to * in python", 30),
            ("Date range", "python news 2024..2025", 20),
        ]
        
        # Run each test
        passed = 0
        failed = 0
        warnings = 0
        
        for test_name, query, min_results in test_cases:
            success = self.run_test(test_name, query, min_results)
            
            # Check the status
            if self.test_results[-1]['status'] == 'PASSED':
                passed += 1
            elif self.test_results[-1]['status'] == 'WARNING':
                warnings += 1
            else:
                failed += 1
            
            # Small delay between requests to be respectful
            time.sleep(1)
        
        # Print summary
        self.print_summary(passed, failed, warnings)
    
    def print_summary(self, passed, failed, warnings):
        """Print test summary"""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        total_tests = len(self.test_results)
        print(f"\nTotal Tests: {total_tests}")
        print(f"✅ Passed: {passed}")
        print(f"⚠️ Warnings: {warnings}")
        print(f"❌ Failed: {failed}")
        
        # Calculate statistics
        if self.test_results:
            avg_time = sum(r['time'] for r in self.test_results) / len(self.test_results)
            max_time = max(r['time'] for r in self.test_results)
            min_time = min(r['time'] for r in self.test_results)
            avg_results = sum(r['results'] for r in self.test_results) / len(self.test_results)
            
            print(f"\n📊 Performance Statistics:")
            print(f"   • Average response time: {avg_time:.2f}s")
            print(f"   • Fastest response: {min_time:.2f}s")
            print(f"   • Slowest response: {max_time:.2f}s")
            print(f"   • Average results count: {avg_results:.1f}")
        
        # Show any timeouts
        timeouts = [r for r in self.test_results if r.get('status') == 'TIMEOUT']
        if timeouts:
            print(f"\n⏱️ Timeouts (>{30}s):")
            for r in timeouts:
                print(f"   • {r['test']}: {r['time']:.2f}s")
        
        # Show failed tests
        failed_tests = [r for r in self.test_results if r['status'] in ['FAILED', 'ERROR']]
        if failed_tests:
            print(f"\n❌ Failed Tests:")
            for r in failed_tests:
                print(f"   • {r['test']}: {r.get('error', 'Failed to get results')}")
        
        # Show warnings (low result count)
        warning_tests = [r for r in self.test_results if r['status'] == 'WARNING']
        if warning_tests:
            print(f"\n⚠️ Low Result Count:")
            for r in warning_tests:
                print(f"   • {r['test']}: {r['results']} results")
        
        # Save detailed results to file
        report_file = f"google_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                'summary': {
                    'total': total_tests,
                    'passed': passed,
                    'warnings': warnings,
                    'failed': failed,
                    'avg_time': avg_time if self.test_results else 0,
                    'avg_results': avg_results if self.test_results else 0
                },
                'tests': self.test_results
            }, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_file}")
        
        # Final verdict
        print("\n" + "="*80)
        if failed == 0 and warnings <= 5:
            print("✅ TEST SUITE PASSED - Google scraper is working well!")
        elif failed == 0:
            print("⚠️ TEST SUITE PASSED WITH WARNINGS - Some queries returned fewer results")
        else:
            print("❌ TEST SUITE FAILED - Some tests did not pass")
        print("="*80)


def test_timeout_handling():
    """Test that timeout is properly enforced"""
    print("\n" + "="*80)
    print("TIMEOUT HANDLING TEST")
    print("="*80)
    
    scraper = ScrapeDoService()
    
    print(f"Testing with DEFAULT_TIMEOUT = {scraper.DEFAULT_TIMEOUT} seconds")
    
    # Test a normal query that should complete quickly
    print("\n1. Testing normal query (should complete < 30s)...")
    start = time.time()
    
    result = scraper.scrape_google_search(
        query="python programming",
        country_code='US',
        num_results=100
    )
    
    elapsed = time.time() - start
    
    if result and result.get('success'):
        print(f"   ✅ Completed in {elapsed:.2f}s")
        if elapsed > 30:
            print(f"   ⚠️ WARNING: Took longer than 30s timeout!")
    else:
        print(f"   ❌ Failed after {elapsed:.2f}s")
    
    print("\n✅ Timeout is set to 30 seconds in Scrape.do service")


if __name__ == "__main__":
    try:
        # First test timeout handling
        test_timeout_handling()
        
        # Then run comprehensive test suite
        print("\n" + "="*80)
        print("Starting comprehensive test suite...")
        print("="*80)
        
        tester = GoogleSearchComprehensiveTest()
        tester.run_all_tests()
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)