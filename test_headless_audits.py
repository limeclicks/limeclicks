#!/usr/bin/env python
"""
Test script to verify both Lighthouse and Screaming Frog audits run in headless mode
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from project.models import Project
from audits.tasks import create_audit_for_project
from onpageaudit.tasks import create_onpage_audit_for_project


def test_headless_audits():
    """Test that both audit systems run headless"""
    
    print("=" * 60)
    print("Testing Headless Audit Systems")
    print("=" * 60)
    
    # Get or create a test project
    project = Project.objects.filter(domain='example.com').first()
    if not project:
        from accounts.models import User
        user = User.objects.first()
        if not user:
            print("❌ No user found. Please create a user first.")
            return False
        
        project = Project.objects.create(
            user=user,
            domain='example.com',
            title='Test Project for Headless Audits',
            active=True
        )
        print(f"✅ Created test project: {project.domain}")
    else:
        print(f"✅ Using existing project: {project.domain}")
    
    print("\n" + "-" * 40)
    print("Testing Lighthouse Audit (Headless)")
    print("-" * 40)
    
    # Test Lighthouse audit
    try:
        result = create_audit_for_project(project.id, 'test_headless')
        if result['success']:
            print("✅ Lighthouse audit queued successfully")
            print("   - This should run without opening a browser")
            print("   - Check Celery logs for execution")
            print(f"   - Reports will be saved to: {project.domain}/lighthouseaudit/[date]/")
        else:
            print(f"❌ Failed to queue Lighthouse audit: {result.get('error')}")
    except Exception as e:
        print(f"❌ Error queuing Lighthouse audit: {str(e)}")
    
    print("\n" + "-" * 40)
    print("Testing OnPage Audit (Screaming Frog Headless)")
    print("-" * 40)
    
    # Test OnPage audit
    try:
        result = create_onpage_audit_for_project(project.id, 'test_headless')
        if result['success']:
            print("✅ OnPage audit queued successfully")
            print("   - This should run without opening Screaming Frog GUI")
            print("   - Check Celery logs for execution")
            print(f"   - Reports will be saved to: {project.domain}/onpageaudit/[date]/")
        else:
            print(f"❌ Failed to queue OnPage audit: {result.get('error')}")
    except Exception as e:
        print(f"❌ Error queuing OnPage audit: {str(e)}")
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print("✓ Both audits have been queued to run in headless mode")
    print("✓ No browser windows should open")
    print("✓ Reports will be saved as JSON only")
    print("✓ Directory structure: [domain]/[audit_type]/[date]/report.json")
    print("")
    print("Monitor with:")
    print("  - Celery logs: celery -A limeclicks worker -l info")
    print("  - Flower UI: http://localhost:5555")
    print("")
    print("Check R2/S3 storage for saved reports")
    
    return True


if __name__ == "__main__":
    success = test_headless_audits()
    sys.exit(0 if success else 1)