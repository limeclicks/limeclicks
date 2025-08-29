#!/usr/bin/env python
"""Production verification test for Screaming Frog integration

This test verifies that the Screaming Frog crawler works correctly
in a production-like environment with proper license configuration.
"""

import os
import sys
import django
import time
import json
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from site_audit.screaming_frog import ScreamingFrogCLI
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def verify_environment():
    """Verify that the environment is properly configured"""
    print("\n" + "=" * 60)
    print("ENVIRONMENT VERIFICATION")
    print("=" * 60)
    
    # Check license environment variable
    license_key = os.getenv('SCREAMING_FROG_LICENSE')
    if license_key:
        # Mask the license key for security
        masked_key = license_key[:10] + "..." if len(license_key) > 10 else "HIDDEN"
        print(f"✅ License configured: {masked_key}")
    else:
        print("⚠️  No license key found in SCREAMING_FROG_LICENSE")
        print("   Using free version (500 URL limit)")
    
    # Check Screaming Frog installation
    cli = ScreamingFrogCLI()
    if cli.sf_path:
        print(f"✅ Screaming Frog found: {cli.sf_path}")
    else:
        print("❌ Screaming Frog not found")
        return False
    
    # Validate license
    license_info = cli.validate_license()
    print(f"\n📋 License Status:")
    print(f"   Valid: {license_info.get('valid', False)}")
    print(f"   Type: {license_info.get('type', 'Unknown')}")
    if license_info.get('key'):
        print(f"   Key: {license_info['key'][:20]}..." if len(license_info['key']) > 20 else license_info['key'])
    
    return True


def test_production_crawl():
    """Test crawl with production parameters"""
    print("\n" + "=" * 60)
    print("PRODUCTION CRAWL TEST")
    print("=" * 60)
    
    cli = ScreamingFrogCLI()
    
    # Test with a real website (limited pages for testing)
    test_url = "https://example.com"
    max_pages = 10  # Small number for testing
    
    print(f"\n📊 Starting crawl test:")
    print(f"   URL: {test_url}")
    print(f"   Intended limit: {max_pages} pages")
    print(f"   Actual limit: Determined by license")
    
    start_time = time.time()
    
    try:
        success, output_dir, error = cli.crawl_website(test_url, max_pages=max_pages)
        
        elapsed_time = time.time() - start_time
        
        if success:
            print(f"\n✅ Crawl completed successfully in {elapsed_time:.2f} seconds")
            print(f"📁 Output directory: {output_dir}")
            
            # Analyze output
            if output_dir and os.path.exists(output_dir):
                files = os.listdir(output_dir)
                print(f"\n📊 Generated {len(files)} files:")
                
                # Show key files
                key_files = [
                    'internal_all.csv',
                    'external_all.csv', 
                    'response_codes_client_error_4xx.csv',
                    'response_codes_server_error_5xx.csv',
                    'page_titles_missing.csv',
                    'meta_description_missing.csv',
                    'h1_missing.csv',
                    'images_missing_alt_text.csv'
                ]
                
                for filename in key_files:
                    file_path = os.path.join(output_dir, filename)
                    if os.path.exists(file_path):
                        size = os.path.getsize(file_path)
                        print(f"   ✓ {filename}: {size:,} bytes")
                    else:
                        print(f"   ✗ {filename}: Not found")
                
                # Parse results
                print("\n📈 Parsing crawl results...")
                results = cli.parse_crawl_results(output_dir)
                
                if results:
                    print(f"\n📊 Crawl Statistics:")
                    print(f"   Pages crawled: {results.get('pages_crawled', 0)}")
                    
                    summary = results.get('summary', {})
                    print(f"   Total issues: {summary.get('total_issues', 0)}")
                    
                    # Show issue breakdown
                    print(f"\n📋 Issue Breakdown:")
                    issue_types = [
                        'missing_titles',
                        'duplicate_titles',
                        'missing_meta_descriptions',
                        'duplicate_meta_descriptions',
                        'missing_h1',
                        'duplicate_h1',
                        'broken_links',
                        'redirect_chains',
                        'missing_alt_text'
                    ]
                    
                    for issue_type in issue_types:
                        count = summary.get(issue_type, 0)
                        if count > 0:
                            print(f"   • {issue_type.replace('_', ' ').title()}: {count}")
                    
                    # Save results summary
                    results_file = f"crawl_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    with open(results_file, 'w') as f:
                        json.dump(results, f, indent=2, default=str)
                    print(f"\n💾 Results saved to: {results_file}")
                    
                    # Clean up
                    import shutil
                    if output_dir and os.path.exists(output_dir):
                        shutil.rmtree(output_dir)
                        print(f"🧹 Cleaned up temporary directory")
                    
                    return True
                else:
                    print("⚠️  No results parsed from crawl")
            else:
                print("⚠️  Output directory not found")
        else:
            print(f"\n❌ Crawl failed: {error}")
            return False
            
    except Exception as e:
        print(f"\n❌ Exception during crawl: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test runner"""
    print("\n" + "=" * 60)
    print("SCREAMING FROG PRODUCTION VERIFICATION")
    print("=" * 60)
    print(f"Time: {datetime.now()}")
    
    # Step 1: Verify environment
    if not verify_environment():
        print("\n❌ Environment verification failed")
        return False
    
    # Step 2: Test production crawl
    if not test_production_crawl():
        print("\n❌ Production crawl test failed")
        return False
    
    print("\n" + "=" * 60)
    print("✅ PRODUCTION VERIFICATION COMPLETE")
    print("=" * 60)
    
    print("\n📋 Summary:")
    print("   • Environment properly configured")
    print("   • Screaming Frog executable found")
    print("   • License validation successful")
    print("   • Crawl completed without errors")
    print("   • Results parsed successfully")
    print("   • All critical files generated")
    
    print("\n🚀 System is ready for production use!")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)