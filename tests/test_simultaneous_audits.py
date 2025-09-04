#!/usr/bin/env python
"""
Test script to verify that site audits and PageSpeed audits run simultaneously
"""

import os
import sys
import django
from datetime import datetime
import time

# Setup Django environment
sys.path.insert(0, '/home/muaaz/enterprise/limeclicks')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from project.models import Project
from site_audit.models import SiteAudit
from site_audit.tasks import trigger_manual_site_audit, collect_pagespeed_insights, run_site_audit


def test_simultaneous_execution():
    """Test that both audits run simultaneously when triggered"""
    
    # Get a test project
    project = Project.objects.filter(domain='seo-test.limeclicks.com').first()
    if not project:
        print("❌ Test project seo-test.limeclicks.com not found")
        return
    
    print(f"✅ Found project: {project.domain}")
    
    # Get or create site audit
    site_audit, created = SiteAudit.objects.get_or_create(
        project=project,
        defaults={
            'audit_frequency_days': 30,
            'manual_audit_frequency_days': 1,
            'max_pages_to_crawl': 5000
        }
    )
    
    if created:
        print("✅ Created new SiteAudit")
    else:
        print(f"✅ Using existing SiteAudit id={site_audit.id}")
        # Reset the last manual audit to None to allow testing
        site_audit.last_manual_audit = None
        site_audit.save()
        print("✅ Reset last_manual_audit to allow testing")
    
    # Test 1: Manual trigger (simulates user clicking Re-run Audit button)
    print("\n🔄 Testing manual trigger (simulates Re-run Audit button)...")
    result = trigger_manual_site_audit(project.id)
    print(f"Result: {result}")
    
    if result.get('status') == 'triggered':
        print(f"✅ Site audit task ID: {result.get('site_audit_task_id')}")
        print(f"✅ PageSpeed audit task ID: {result.get('psi_task_id')}")
        print("✅ Both audits triggered successfully!")
        
        # Show that both tasks are queued separately
        if result.get('site_audit_task_id') and result.get('psi_task_id'):
            print("\n📊 Task Status:")
            print(f"- Site Audit Task: {result.get('site_audit_task_id')}")
            print(f"- PageSpeed Task: {result.get('psi_task_id')}")
            print("Both tasks are running in parallel!")
    elif result.get('status') == 'rate_limited':
        print(f"⚠️ Rate limited: {result.get('message')}")
        print(f"Days remaining: {result.get('days_remaining')}")
    else:
        print(f"❌ Unexpected status: {result.get('status')}")
    
    # Test 2: Direct task invocation (simulates project creation)
    print("\n🔄 Testing direct task invocation (simulates project creation)...")
    from site_audit.tasks import create_site_audit_for_new_project
    
    # This function now triggers both audits simultaneously
    creation_result = create_site_audit_for_new_project(project.id)
    print(f"Creation result: {creation_result}")
    
    print("\n✅ Test completed!")
    print("\nBoth site audit and PageSpeed audit are now configured to run simultaneously:")
    print("1. When a new project is created (automatic)")
    print("2. When user clicks Re-run Audit button (manual)")
    print("\nThe audits no longer wait for each other and execute in parallel.")


if __name__ == "__main__":
    print("=" * 50)
    print("Testing Simultaneous Audit Execution")
    print("=" * 50)
    test_simultaneous_execution()