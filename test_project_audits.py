#!/usr/bin/env python
"""
Test that creating a new project automatically triggers Lighthouse and OnPage audits
"""

import os
import sys
import django
import time
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from project.models import Project
from accounts.models import User
from performance_audit.models import PerformancePage, PerformanceHistory
from site_audit.models import SiteAudit, OnPagePerformanceHistory


def test_project_audit_triggers():
    """Test that project creation triggers both audits"""
    
    print("\n" + "="*60)
    print("TEST: Project Creation Audit Triggers")
    print("="*60)
    
    # Get or create test user
    user, _ = User.objects.get_or_create(
        email='test@example.com',
        defaults={
            'username': 'testuser',
            'is_active': True,
            'email_verified': True
        }
    )
    print(f"\n✓ Using test user: {user.email}")
    
    # Create a test project
    test_domain = f"testdomain-{datetime.now().strftime('%Y%m%d%H%M%S')}.com"
    print(f"\n1. Creating new project: {test_domain}")
    
    project = Project.objects.create(
        user=user,
        domain=test_domain,
        title='Test Project for Audit Triggers',
        active=True
    )
    print(f"   ✓ Project created: ID={project.id}")
    
    # Give signals time to execute
    print("\n2. Waiting for signal handlers to execute...")
    time.sleep(2)
    
    # Check if Lighthouse audit was created
    print("\n3. Checking Lighthouse audit...")
    try:
        performance_page = PerformancePage.objects.get(project=project)
        print(f"   ✓ PerformancePage created for project")
        print(f"   - Page URL: {performance_page.page_url}")
        print(f"   - Homepage only: {'Yes' if performance_page.page_url == f'https://{test_domain}' else 'No'}")
        
        # Check audit history
        audit_histories = PerformanceHistory.objects.filter(performance_page=performance_page)
        print(f"   - Audit histories created: {audit_histories.count()}")
        for ah in audit_histories:
            print(f"     • {ah.device_type}: Status={ah.status}, Trigger={ah.trigger_type}")
    except PerformancePage.DoesNotExist:
        print("   ✗ No PerformancePage created")
    
    # Check if OnPage audit was created
    print("\n4. Checking OnPage audit...")
    try:
        site_audit = SiteAudit.objects.get(project=project)
        print(f"   ✓ SiteAudit created for project")
        print(f"   - Max pages to crawl: {site_audit.max_pages_to_crawl}")
        print(f"   - Is 10,000 pages: {'Yes' if site_audit.max_pages_to_crawl == 10000 else 'No'}")
        print(f"   - Audit enabled: {site_audit.is_audit_enabled}")
        
        # Check audit history
        onpage_histories = OnPagePerformanceHistory.objects.filter(audit=site_audit)
        print(f"   - Audit histories created: {onpage_histories.count()}")
        for oh in onpage_histories:
            print(f"     • Status={oh.status}, Trigger={oh.trigger_type}")
    except SiteAudit.DoesNotExist:
        print("   ✗ No SiteAudit created")
    
    # Check Celery task queue (if Celery is running)
    print("\n5. Checking Celery tasks...")
    try:
        from celery import current_app
        inspect = current_app.control.inspect()
        
        # Get active tasks
        active_tasks = inspect.active()
        if active_tasks:
            for worker, tasks in active_tasks.items():
                print(f"   Worker {worker}:")
                for task in tasks:
                    if 'audit' in task['name'].lower():
                        print(f"     • {task['name']} - Args: {task.get('args', [])[:100]}")
        
        # Get scheduled tasks
        scheduled_tasks = inspect.scheduled()
        if scheduled_tasks:
            for worker, tasks in scheduled_tasks.items():
                print(f"   Scheduled on {worker}:")
                for task in tasks:
                    if 'audit' in task['request']['name'].lower():
                        print(f"     • {task['request']['name']}")
    except Exception as e:
        print(f"   ℹ Could not check Celery tasks: {e}")
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY:")
    print("="*60)
    
    has_lighthouse = PerformancePage.objects.filter(project=project).exists()
    has_onpage = SiteAudit.objects.filter(project=project).exists()
    
    if has_lighthouse:
        performance_page = PerformancePage.objects.get(project=project)
        is_homepage = performance_page.page_url == f'https://{test_domain}'
        print(f"✓ Lighthouse audit: Created (Homepage only: {'Yes' if is_homepage else 'No'})")
    else:
        print("✗ Lighthouse audit: Not created")
    
    if has_onpage:
        site_audit = SiteAudit.objects.get(project=project)
        is_10k = site_audit.max_pages_to_crawl == 10000
        print(f"✓ OnPage audit: Created (10k page limit: {'Yes' if is_10k else 'No'})")
    else:
        print("✗ OnPage audit: Not created")
    
    if has_lighthouse and has_onpage:
        print("\n✅ SUCCESS: Both audits were triggered automatically!")
    else:
        print("\n⚠ WARNING: Not all audits were triggered")
    
    # Cleanup
    print("\n6. Cleaning up test data...")
    project.delete()  # This will cascade delete related audits
    print("   ✓ Test project and related audits deleted")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60 + "\n")


if __name__ == "__main__":
    test_project_audit_triggers()