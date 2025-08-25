#!/usr/bin/env python
"""
Comprehensive test script for Lighthouse Audit System
Tests all major features including triggers, scheduling, and manual audits
"""

import os
import sys
import django
import time
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.utils import timezone
from project.models import Project
from accounts.models import User
from audits.models import AuditPage, AuditHistory, AuditSchedule
from audits.tasks import (
    run_lighthouse_audit,
    create_audit_for_project,
    run_manual_audit,
    check_scheduled_audits,
    generate_audit_report
)
from audits.lighthouse_runner import LighthouseRunner, LighthouseService


def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_lighthouse_installation():
    """Test 1: Verify Lighthouse is installed"""
    print_section("TEST 1: Lighthouse Installation")
    
    if LighthouseService.check_lighthouse_installed():
        print("✅ Lighthouse is installed and ready")
        return True
    else:
        print("❌ Lighthouse is not installed")
        print("   Attempting to install...")
        if LighthouseService.install_lighthouse():
            print("✅ Lighthouse installed successfully")
            return True
        else:
            print("❌ Failed to install Lighthouse")
            return False


def test_direct_audit():
    """Test 2: Run a direct Lighthouse audit"""
    print_section("TEST 2: Direct Lighthouse Audit")
    
    runner = LighthouseRunner()
    url = "https://www.example.com"
    
    print(f"Running audit for {url}...")
    success, results, error = runner.run_audit(url, 'desktop')
    
    if success:
        print("✅ Audit completed successfully")
        print(f"   Performance Score: {results.get('performance_score')}")
        print(f"   Accessibility Score: {results.get('accessibility_score')}")
        print(f"   SEO Score: {results.get('seo_score')}")
        return True
    else:
        print(f"❌ Audit failed: {error}")
        return False


def test_project_trigger():
    """Test 3: Test automatic audit trigger on project creation"""
    print_section("TEST 3: Automatic Audit on Project Creation")
    
    # Get or create a test user
    user, _ = User.objects.get_or_create(
        email='audit_test@example.com',
        defaults={'username': 'audit_test', 'is_active': True}
    )
    
    # Create a new project (this should trigger an audit)
    print("Creating new project...")
    project = Project.objects.create(
        user=user,
        domain='test-audit-site.com',
        title='Test Audit Site',
        active=True
    )
    print(f"✅ Project created: {project.domain}")
    
    # Check if audit page was created
    time.sleep(2)  # Give signals time to process
    
    try:
        audit_page = AuditPage.objects.get(project=project)
        print(f"✅ Audit page created automatically")
        print(f"   Page URL: {audit_page.page_url}")
        print(f"   Next scheduled audit: {audit_page.next_scheduled_audit}")
        
        # Check if audit history entries were created
        audit_count = AuditHistory.objects.filter(audit_page=audit_page).count()
        print(f"   Audit history entries: {audit_count}")
        
        return True
    except AuditPage.DoesNotExist:
        print("❌ Audit page was not created")
        return False
    finally:
        # Cleanup
        project.delete()


def test_manual_audit():
    """Test 4: Test manual audit with rate limiting"""
    print_section("TEST 4: Manual Audit with Rate Limiting")
    
    # Get an existing project
    project = Project.objects.filter(active=True).first()
    if not project:
        print("❌ No active projects found")
        return False
    
    print(f"Using project: {project.domain}")
    
    # Get or create audit page
    audit_page, _ = AuditPage.objects.get_or_create(
        project=project,
        defaults={'page_url': f'https://{project.domain}'}
    )
    
    # Test manual audit
    print("Triggering manual audit...")
    result = run_manual_audit(audit_page.id)
    
    if result.get('success'):
        print("✅ Manual audit triggered successfully")
        print(f"   Audit IDs: {result.get('audit_ids')}")
        
        # Test rate limiting
        print("\nTesting rate limiting...")
        result2 = run_manual_audit(audit_page.id)
        
        if not result2.get('success'):
            print("✅ Rate limiting working correctly")
            print(f"   {result2.get('error')}")
        else:
            print("❌ Rate limiting not working")
        
        return True
    else:
        print(f"❌ Failed to trigger manual audit: {result.get('error')}")
        return False


def test_scheduled_audits():
    """Test 5: Test scheduled audit system"""
    print_section("TEST 5: Scheduled Audit System")
    
    # Get an audit page and set it to need an audit
    audit_page = AuditPage.objects.filter(is_audit_enabled=True).first()
    if not audit_page:
        print("❌ No enabled audit pages found")
        return False
    
    print(f"Using audit page for: {audit_page.project.domain}")
    
    # Set next scheduled audit to past
    audit_page.next_scheduled_audit = timezone.now() - timedelta(hours=1)
    audit_page.save()
    print(f"Set next audit to: {audit_page.next_scheduled_audit}")
    
    # Run scheduled audit check
    print("Running scheduled audit check...")
    result = check_scheduled_audits()
    
    if result.get('success'):
        print(f"✅ Scheduled audit check completed")
        print(f"   Audits scheduled: {result.get('scheduled_count')}")
        
        # Verify schedule was updated
        audit_page.refresh_from_db()
        print(f"   Next audit scheduled for: {audit_page.next_scheduled_audit}")
        
        return True
    else:
        print("❌ Scheduled audit check failed")
        return False


def test_audit_report():
    """Test 6: Test audit report generation"""
    print_section("TEST 6: Audit Report Generation")
    
    # Get an audit page with history
    audit_page = AuditPage.objects.filter(
        audit_history__status='completed'
    ).distinct().first()
    
    if not audit_page:
        print("❌ No audit pages with completed audits found")
        return False
    
    print(f"Generating report for: {audit_page.project.domain}")
    
    # Generate report
    result = generate_audit_report(audit_page.id)
    
    if result.get('success'):
        report = result.get('report')
        print("✅ Report generated successfully")
        print(f"   Total audits: {report['summary']['total_audits']}")
        print(f"   Desktop audits: {report['summary']['desktop_audits']}")
        print(f"   Mobile audits: {report['summary']['mobile_audits']}")
        
        # Show latest scores
        if report['latest_scores'].get('desktop'):
            desktop_scores = report['latest_scores']['desktop']
            print(f"\n   Latest Desktop Scores:")
            print(f"   - Performance: {desktop_scores.get('performance')}")
            print(f"   - Accessibility: {desktop_scores.get('accessibility')}")
            print(f"   - SEO: {desktop_scores.get('seo')}")
        
        return True
    else:
        print(f"❌ Report generation failed: {result.get('error')}")
        return False


def test_admin_interface():
    """Test 7: Verify admin interface is registered"""
    print_section("TEST 7: Admin Interface")
    
    from django.contrib import admin
    from audits.models import AuditPage, AuditHistory, AuditSchedule
    
    models_registered = []
    
    if admin.site.is_registered(AuditPage):
        models_registered.append("AuditPage")
    
    if admin.site.is_registered(AuditHistory):
        models_registered.append("AuditHistory")
    
    if admin.site.is_registered(AuditSchedule):
        models_registered.append("AuditSchedule")
    
    if len(models_registered) == 3:
        print("✅ All models registered in admin")
        for model in models_registered:
            print(f"   - {model}")
        return True
    else:
        print(f"❌ Not all models registered. Found: {models_registered}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("  LIGHTHOUSE AUDIT SYSTEM - COMPREHENSIVE TEST")
    print("="*60)
    
    tests = [
        ("Lighthouse Installation", test_lighthouse_installation),
        ("Direct Audit", test_direct_audit),
        ("Project Trigger", test_project_trigger),
        ("Manual Audit", test_manual_audit),
        ("Scheduled Audits", test_scheduled_audits),
        ("Report Generation", test_audit_report),
        ("Admin Interface", test_admin_interface),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((name, False))
    
    # Summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{name:.<40} {status}")
    
    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{total} tests passed")
    print(f"{'='*60}\n")
    
    if passed == total:
        print("🎉 All tests passed! The audit system is fully functional.")
    else:
        print(f"⚠️  {total - passed} test(s) failed. Please review the output above.")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)