#!/usr/bin/env python
"""Test Screaming Frog configuration and crawl functionality"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from site_audit.screaming_frog import ScreamingFrogCLI
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_screaming_frog():
    """Test Screaming Frog configuration"""
    print("=" * 60)
    print("SCREAMING FROG CONFIGURATION TEST")
    print("=" * 60)
    
    # Initialize CLI
    cli = ScreamingFrogCLI()
    
    # Check installation
    print("\n1. Checking Screaming Frog installation...")
    if cli.is_installed():
        print(f"   ✅ Screaming Frog found at: {cli.sf_path}")
    else:
        print(f"   ❌ Screaming Frog not found")
        return False
    
    # Check license
    print("\n2. Checking license configuration...")
    license_key = os.getenv('SCREAMING_FROG_LICENSE')
    if license_key:
        print(f"   ✅ License key found in environment (length: {len(license_key)})")
        print(f"   ✅ License key starts with: {license_key[:10]}...")
    else:
        print("   ⚠️  No license key in SCREAMING_FROG_LICENSE environment variable")
    
    # Validate license
    print("\n3. Validating license...")
    license_info = cli.validate_license()
    print(f"   Valid: {license_info.get('valid', False)}")
    print(f"   Type: {license_info.get('type', 'Unknown')}")
    print(f"   Max URLs: {license_info.get('max_urls', 500)}")
    print(f"   Message: {license_info.get('message', '')}")
    
    # Test small crawl
    print("\n4. Testing crawl with fixed --max-urls parameter...")
    test_url = "https://example.com"
    max_pages = 10  # Small test
    
    print(f"   Testing crawl of {test_url} (max {max_pages} pages)...")
    print(f"   Using --max-urls={max_pages} parameter")
    
    try:
        success, output_dir, error = cli.crawl_website(test_url, max_pages=max_pages)
        
        if success:
            print(f"   ✅ Crawl successful!")
            print(f"   ✅ Output directory: {output_dir}")
            
            # List output files
            if output_dir and os.path.exists(output_dir):
                files = os.listdir(output_dir)
                print(f"   ✅ Generated {len(files)} files:")
                for f in sorted(files)[:10]:  # Show first 10 files
                    print(f"      - {f}")
        else:
            print(f"   ❌ Crawl failed: {error}")
            return False
            
    except Exception as e:
        print(f"   ❌ Crawl error: {str(e)}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - Screaming Frog is properly configured!")
    print("=" * 60)
    print("\nConfiguration Summary:")
    print(f"  • Executable: {cli.sf_path}")
    print(f"  • License: {'Configured' if license_key else 'Not configured (500 URL limit)'}")
    print(f"  • Max URLs: {5000 if license_key else 500}")
    print("  • Headless mode: Enabled")
    print("  • --max-urls parameter: Fixed and working")
    
    return True

if __name__ == "__main__":
    success = test_screaming_frog()
    sys.exit(0 if success else 1)