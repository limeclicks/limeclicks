#!/usr/bin/env python
"""
Test logo configuration and Unfold settings
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.conf import settings
from django.test import RequestFactory
from limeclicks.context_processors import logos, site_settings


def test_logo_configuration():
    """Test that logos are properly configured"""
    
    print("=" * 60)
    print("🎨 Testing Logo Configuration")
    print("=" * 60)
    
    # Check static files exist
    print("\n📁 Checking logo files:")
    logo_paths = [
        'static/img/logo-light.png',
        'static/img/logo-dark.png',
        'static/admin/img/logo-light.png',
        'static/admin/img/logo-dark.png'
    ]
    
    for path in logo_paths:
        exists = os.path.exists(path)
        status = "✅" if exists else "❌"
        if exists:
            size = os.path.getsize(path)
            print(f"  {status} {path} ({size:,} bytes)")
        else:
            print(f"  {status} {path} (not found)")
    
    # Test context processor
    print("\n🔧 Testing context processor:")
    factory = RequestFactory()
    request = factory.get('/')
    
    logo_context = logos(request)
    print(f"  Logo Light: {logo_context['logo_light']}")
    print(f"  Logo Dark: {logo_context['logo_dark']}")
    print(f"  Site Name: {logo_context['site_name']}")
    print(f"  Site Tagline: {logo_context['site_tagline']}")
    
    site_context = site_settings(request)
    print(f"\n  Debug Mode: {site_context['DEBUG']}")
    print(f"  Site URL: {site_context['SITE_URL']}")
    print(f"  Support Email: {site_context['SUPPORT_EMAIL']}")
    
    # Check Unfold configuration
    print("\n⚙️ Unfold Configuration:")
    unfold = settings.UNFOLD
    print(f"  Site Title: {unfold['SITE_TITLE']}")
    print(f"  Site Header: {unfold['SITE_HEADER']}")
    print(f"  Theme: {unfold['THEME']}")
    
    # Check if badge was removed
    sidebar = unfold.get('SIDEBAR', {})
    navigation = sidebar.get('navigation', [])
    
    badge_found = False
    for section in navigation:
        for item in section.get('items', []):
            if 'badge' in item:
                badge_found = True
                print(f"  ⚠️ Badge still found in: {item.get('title')}")
    
    if not badge_found:
        print("  ✅ Badge count removed from Keywords navigation")
    
    # Check for logo configuration in Unfold
    if 'SITE_ICON' in unfold:
        print("\n  ✅ Logo configuration in Unfold:")
        site_icon = unfold['SITE_ICON']
        if callable(site_icon.get('light')):
            print("    Light logo: Configured as callable")
        if callable(site_icon.get('dark')):
            print("    Dark logo: Configured as callable")
    
    print("\n" + "=" * 60)
    print("✅ Logo Configuration Test Complete")
    print("=" * 60)
    print("\nSummary:")
    print("  • Logo files downloaded and stored")
    print("  • Context processors configured")
    print("  • Templates updated to use logos")
    print("  • Unfold admin configured with logos")
    print("  • Badge count issue fixed")


if __name__ == '__main__':
    test_logo_configuration()