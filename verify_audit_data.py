#!/usr/bin/env python
"""
Verify and display detailed audit data for seo-test.limeclicks.com
"""

import os
import sys
import django
import json
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from site_audit.models import SiteAudit, SiteIssue
from project.models import Project

def verify_audit_data():
    """Verify all data collected for seo-test.limeclicks.com"""
    
    print("=" * 80)
    print("VERIFYING AUDIT DATA FOR seo-test.limeclicks.com")
    print("=" * 80)
    
    # Get the latest audit for this domain
    try:
        project = Project.objects.get(domain='seo-test.limeclicks.com')
        site_audit = SiteAudit.objects.filter(project=project).latest('created_at')
    except (Project.DoesNotExist, SiteAudit.DoesNotExist):
        print("❌ No audit found for seo-test.limeclicks.com")
        return
    
    print(f"\n📊 AUDIT SUMMARY:")
    print(f"   Audit ID: {site_audit.id}")
    print(f"   Created: {site_audit.created_at}")
    print(f"   Status: {site_audit.status}")
    print(f"   Overall Health Score: {site_audit.overall_site_health_score}%")
    print(f"   Pages Crawled: {site_audit.total_pages_crawled}")
    
    # Check Issues
    print(f"\n📋 ISSUES BREAKDOWN:")
    issues = SiteIssue.objects.filter(site_audit=site_audit)
    print(f"   Total Issues: {issues.count()}")
    
    # Group by category
    categories = {}
    severities = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
    
    for issue in issues:
        # Category breakdown
        if issue.issue_category not in categories:
            categories[issue.issue_category] = []
        categories[issue.issue_category].append(issue)
        
        # Severity breakdown
        if issue.severity in severities:
            severities[issue.severity] += 1
    
    print(f"\n   By Category:")
    for category, category_issues in sorted(categories.items()):
        print(f"     {category}: {len(category_issues)} issues")
        # Show first 3 issues as examples
        for i, issue in enumerate(category_issues[:3]):
            print(f"       - {issue.issue_type}: {issue.affected_url[:50]}...")
            if i == 2 and len(category_issues) > 3:
                print(f"       ... and {len(category_issues) - 3} more")
    
    print(f"\n   By Severity:")
    for severity, count in severities.items():
        if count > 0:
            print(f"     {severity.upper()}: {count}")
    
    # Check PageSpeed Data
    print(f"\n🚀 PAGESPEED INSIGHTS DATA:")
    
    # Mobile Performance
    print(f"\n   📱 MOBILE PERFORMANCE:")
    if site_audit.performance_score_mobile is not None:
        print(f"      Score: {site_audit.performance_score_mobile}/100")
    
    if site_audit.mobile_performance:
        mobile = site_audit.mobile_performance
        
        # Scores
        scores = mobile.get('scores', {})
        if scores:
            print(f"      Performance: {scores.get('performance', 'N/A')}")
            print(f"      Accessibility: {scores.get('accessibility', 'N/A')}")
            print(f"      Best Practices: {scores.get('best_practices', 'N/A')}")
            print(f"      SEO: {scores.get('seo', 'N/A')}")
        
        # Lab Metrics
        lab = mobile.get('lab_metrics', {})
        if lab:
            print(f"\n      Lab Metrics:")
            for metric, data in lab.items():
                if isinstance(data, dict) and 'display_value' in data:
                    print(f"        {metric.upper()}: {data['display_value']}")
        
        # Field Data (if available)
        field = mobile.get('field_data', {})
        if field and field.get('origin_summary'):
            print(f"\n      Field Data (Real User Metrics):")
            origin = field['origin_summary']
            for metric, data in origin.items():
                if isinstance(data, dict) and 'percentile' in data:
                    print(f"        {metric}: {data['percentile']}ms (P75)")
    else:
        print(f"      No mobile data collected")
    
    # Desktop Performance
    print(f"\n   💻 DESKTOP PERFORMANCE:")
    if site_audit.performance_score_desktop is not None:
        print(f"      Score: {site_audit.performance_score_desktop}/100")
    
    if site_audit.desktop_performance:
        desktop = site_audit.desktop_performance
        
        # Scores
        scores = desktop.get('scores', {})
        if scores:
            print(f"      Performance: {scores.get('performance', 'N/A')}")
            print(f"      Accessibility: {scores.get('accessibility', 'N/A')}")
            print(f"      Best Practices: {scores.get('best_practices', 'N/A')}")
            print(f"      SEO: {scores.get('seo', 'N/A')}")
        
        # Lab Metrics
        lab = desktop.get('lab_metrics', {})
        if lab:
            print(f"\n      Lab Metrics:")
            for metric, data in lab.items():
                if isinstance(data, dict) and 'display_value' in data:
                    print(f"        {metric.upper()}: {data['display_value']}")
    else:
        print(f"      No desktop data collected")
    
    # Check crawl data storage
    print(f"\n📁 DATA STORAGE:")
    print(f"   Temp Audit Directory: {site_audit.temp_audit_dir}")
    # Note: crawl_data field doesn't exist in current model
    
    # Sample of specific issues
    print(f"\n🔍 SAMPLE ISSUES DETAIL:")
    sample_issues = issues[:5]
    for idx, issue in enumerate(sample_issues, 1):
        print(f"\n   Issue #{idx}:")
        print(f"     Type: {issue.issue_type}")
        print(f"     Category: {issue.issue_category}")
        print(f"     Severity: {issue.severity}")
        print(f"     URL: {issue.affected_url}")
        if issue.details:
            print(f"     Details: {issue.details[:100]}...")
    
    print("\n" + "=" * 80)
    print("VERIFICATION COMPLETE!")
    print("=" * 80)
    
    return site_audit

if __name__ == "__main__":
    verify_audit_data()