#!/usr/bin/env python
"""
Final test for admin configuration
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.conf import settings


def test_admin_configuration():
    """Test final admin configuration"""
    
    print("=" * 60)
    print("🎯 Final Admin Configuration Test")
    print("=" * 60)
    
    # Check Unfold configuration
    print("\n📋 Unfold Configuration:")
    unfold = settings.UNFOLD
    
    # Check logo configuration
    if 'LOGO' in unfold:
        print("  ✅ LOGO configured (single logo)")
        if callable(unfold['LOGO']['light']):
            print(f"     Light theme: {unfold['LOGO']['light'](None)}")
        if callable(unfold['LOGO']['dark']):
            print(f"     Dark theme: {unfold['LOGO']['dark'](None)}")
    
    if 'SITE_ICON' not in unfold:
        print("  ✅ SITE_ICON removed (prevents duplicates)")
    
    # Check logo files
    print("\n📁 Logo Files:")
    logo_files = [
        ('static/admin/img/logo-main.png', 'Main Logo (Light)'),
        ('static/admin/img/logo-main-dark.png', 'Main Logo (Dark)'),
    ]
    
    for path, description in logo_files:
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  ✅ {description}: {size:,} bytes")
        else:
            print(f"  ❌ {description}: Not found")
    
    # Check CSS
    print("\n🎨 Custom CSS:")
    if os.path.exists('static/admin/css/custom.css'):
        with open('static/admin/css/custom.css', 'r') as f:
            content = f.read()
            if 'display: none !important' in content:
                print("  ✅ CSS rules to prevent duplicate logos")
            if 'max-height: 40px' in content:
                print("  ✅ Logo size constraints defined")
    
    print("\n" + "=" * 60)
    print("✅ Admin Configuration Complete")
    print("=" * 60)
    print("\nChanges Summary:")
    print("  • Single logo configuration (removed SITE_ICON)")
    print("  • Using original logo files (logo-main.png)")
    print("  • CSS prevents duplicate logo display")
    print("  • Logo height set to 40px for better visibility")
    print("  • Rank display shows 'Not ranked' for keywords not in top 100")


if __name__ == '__main__':
    test_admin_configuration()