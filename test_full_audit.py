#!/usr/bin/env python
"""
Test script to run a complete site audit with PageSpeed Insights
for seo-test.limeclicks.com
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

from django.contrib.auth import get_user_model
from project.models import Project
from site_audit.models import SiteAudit, SiteIssue
from site_audit.tasks import run_site_audit, collect_pagespeed_insights

User = get_user_model()

def test_full_audit():
    """Run a complete audit test for seo-test.limeclicks.com"""
    
    print("=" * 80)
    print(f"FULL SITE AUDIT TEST - {datetime.now()}")
    print("=" * 80)
    
    # Test domain
    test_domain = "seo-test.limeclicks.com"
    
    # Get or create admin user
    admin_user, created = User.objects.get_or_create(
        username='admin',
        defaults={
            'email': 'tomuaaz@gmail.com',
            'is_staff': True,
            'is_superuser': True
        }
    )
    if created:
        admin_user.set_password('Vf123456$')
        admin_user.save()
        print(f"✅ Created admin user")
    else:
        print(f"✅ Using existing admin user")
    
    # Get or create project
    project, created = Project.objects.get_or_create(
        domain=test_domain,
        user=admin_user,
        defaults={
            'title': 'SEO Test Site',
            'active': True
        }
    )
    print(f"✅ {'Created' if created else 'Using existing'} project: {project.domain}")
    
    # Create a new site audit
    site_audit = SiteAudit.objects.create(
        project=project,
        audit_frequency_days=30,
        manual_audit_frequency_days=1,
        is_audit_enabled=True,
        status='pending'
    )
    print(f"✅ Created SiteAudit ID: {site_audit.id}")
    
    print("\n" + "=" * 80)
    print("PHASE 1: RUNNING SITE AUDIT (Screaming Frog)")
    print("=" * 80)
    
    # Run the site audit synchronously
    try:
        result = run_site_audit(site_audit.id)
        print(f"✅ Site audit completed: {result.get('status')}")
        
        # Refresh the audit object
        site_audit.refresh_from_db()
        
        # Display audit results
        print(f"\n📊 SITE AUDIT RESULTS:")
        print(f"   Status: {site_audit.status}")
        print(f"   Pages Crawled: {site_audit.total_pages_crawled}")
        print(f"   Issues Found: {site_audit.get_total_issues_count()}")
        print(f"   Health Score: {site_audit.overall_site_health_score}%")
        
        # Show issue breakdown
        issues = SiteIssue.objects.filter(site_audit=site_audit)
        issue_categories = {}
        for issue in issues:
            if issue.issue_category not in issue_categories:
                issue_categories[issue.issue_category] = 0
            issue_categories[issue.issue_category] += 1
        
        if issue_categories:
            print(f"\n   Issue Breakdown:")
            for category, count in sorted(issue_categories.items(), key=lambda x: x[1], reverse=True):
                print(f"     - {category}: {count}")
        
    except Exception as e:
        print(f"❌ Site audit failed: {e}")
        return
    
    print("\n" + "=" * 80)
    print("PHASE 2: COLLECTING PAGESPEED INSIGHTS")
    print("=" * 80)
    
    # Run PageSpeed Insights collection
    try:
        psi_result = collect_pagespeed_insights(site_audit.id)
        print(f"✅ PageSpeed Insights collection: {psi_result.get('status')}")
        
        # Refresh to get updated data
        site_audit.refresh_from_db()
        
        # Display PageSpeed results
        print(f"\n📊 PAGESPEED INSIGHTS RESULTS:")
        
        # Mobile scores
        print(f"\n   📱 MOBILE:")
        if site_audit.performance_score_mobile is not None:
            print(f"      Performance Score: {site_audit.performance_score_mobile}/100")
        else:
            print(f"      Performance Score: Not collected")
            
        if site_audit.mobile_performance:
            scores = site_audit.mobile_performance.get('scores', {})
            print(f"      Accessibility: {scores.get('accessibility', 'N/A')}")
            print(f"      Best Practices: {scores.get('best_practices', 'N/A')}")
            print(f"      SEO: {scores.get('seo', 'N/A')}")
            
            # Core Web Vitals (Lab)
            lab = site_audit.mobile_performance.get('lab_metrics', {})
            if lab:
                print(f"\n      Core Web Vitals (Lab):")
                if 'lcp' in lab:
                    print(f"        LCP: {lab['lcp'].get('display_value', 'N/A')}")
                if 'cls' in lab:
                    print(f"        CLS: {lab['cls'].get('display_value', 'N/A')}")
                if 'fcp' in lab:
                    print(f"        FCP: {lab['fcp'].get('display_value', 'N/A')}")
        
        # Desktop scores
        print(f"\n   💻 DESKTOP:")
        if site_audit.performance_score_desktop is not None:
            print(f"      Performance Score: {site_audit.performance_score_desktop}/100")
        else:
            print(f"      Performance Score: Not collected")
            
        if site_audit.desktop_performance:
            scores = site_audit.desktop_performance.get('scores', {})
            print(f"      Accessibility: {scores.get('accessibility', 'N/A')}")
            print(f"      Best Practices: {scores.get('best_practices', 'N/A')}")
            print(f"      SEO: {scores.get('seo', 'N/A')}")
            
            # Core Web Vitals (Lab)
            lab = site_audit.desktop_performance.get('lab_metrics', {})
            if lab:
                print(f"\n      Core Web Vitals (Lab):")
                if 'lcp' in lab:
                    print(f"        LCP: {lab['lcp'].get('display_value', 'N/A')}")
                if 'cls' in lab:
                    print(f"        CLS: {lab['cls'].get('display_value', 'N/A')}")
                if 'fcp' in lab:
                    print(f"        FCP: {lab['fcp'].get('display_value', 'N/A')}")
        
    except Exception as e:
        print(f"❌ PageSpeed Insights collection failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("PHASE 3: FINAL DATA VERIFICATION")
    print("=" * 80)
    
    # Final verification
    site_audit.refresh_from_db()
    
    print(f"\n✅ AUDIT COMPLETE!")
    print(f"   Audit ID: {site_audit.id}")
    print(f"   Status: {site_audit.status}")
    print(f"   Overall Health Score: {site_audit.overall_site_health_score}%")
    print(f"   Total Pages: {site_audit.total_pages_crawled}")
    print(f"   Total Issues: {site_audit.get_total_issues_count()}")
    print(f"   Mobile Performance: {site_audit.performance_score_mobile}/100" if site_audit.performance_score_mobile else "   Mobile Performance: Not collected")
    print(f"   Desktop Performance: {site_audit.performance_score_desktop}/100" if site_audit.performance_score_desktop else "   Desktop Performance: Not collected")
    
    # Check what data fields are populated
    print(f"\n📋 DATA FIELDS STATUS:")
    fields_to_check = [
        'crawl_data',
        'mobile_performance', 
        'desktop_performance',
        'performance_score_mobile',
        'performance_score_desktop',
        'overall_site_health_score',
        'total_pages_crawled',
        'temp_audit_dir'
    ]
    
    for field in fields_to_check:
        value = getattr(site_audit, field, None)
        if value:
            if isinstance(value, dict):
                print(f"   ✅ {field}: {len(value)} keys")
            elif isinstance(value, (int, float)):
                print(f"   ✅ {field}: {value}")
            else:
                print(f"   ✅ {field}: Set")
        else:
            print(f"   ❌ {field}: Empty/None")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE!")
    print("=" * 80)
    
    return site_audit

if __name__ == "__main__":
    audit = test_full_audit()