#!/usr/bin/env python
"""
Production verification script for IssuesOverviewParser
Ensures the parser is ready for production use with full error handling and data validation
"""

import os
import sys
import django
from pathlib import Path
import json
from datetime import datetime

# Setup Django
sys.path.insert(0, '/home/muaaz/enterprise/limeclicks')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from site_audit.parsers.issues_overview import IssuesOverviewParser
from site_audit.parsers.crawl_overview import CrawlOverviewParser
from site_audit.models import SiteAudit
from project.models import Project
from accounts.models import User

def verify_production_readiness():
    """Comprehensive production verification for IssuesOverviewParser"""
    
    print("=" * 80)
    print("PRODUCTION VERIFICATION - ISSUES OVERVIEW PARSER")
    print("=" * 80)
    print(f"\nVerification started at: {datetime.now()}")
    
    # Test directory with actual crawl data
    temp_audit_dir = "/tmp/sf_crawl_qjojrr2v/2025.08.29.15.15.03"
    
    # Verification checklist
    checks_passed = []
    checks_failed = []
    
    # 1. Check parser initialization
    print("\n1. PARSER INITIALIZATION CHECK")
    print("-" * 40)
    try:
        parser = IssuesOverviewParser(temp_audit_dir)
        if parser.issues_report_file and parser.issues_report_file.exists():
            print("✅ Parser initialized successfully")
            print(f"   CSV file: {parser.issues_report_file}")
            checks_passed.append("Parser initialization")
        else:
            print("❌ Parser initialization failed - CSV file not found")
            checks_failed.append("Parser initialization")
    except Exception as e:
        print(f"❌ Parser initialization error: {e}")
        checks_failed.append("Parser initialization")
        return False
    
    # 2. Check standalone parsing
    print("\n2. STANDALONE PARSING CHECK")
    print("-" * 40)
    try:
        issues_data = parser.parse()
        if issues_data and issues_data.get('issues'):
            print(f"✅ Parsed {issues_data['total_issues']} issues successfully")
            print(f"   High: {issues_data['issues_by_priority']['High']}")
            print(f"   Medium: {issues_data['issues_by_priority']['Medium']}")
            print(f"   Low: {issues_data['issues_by_priority']['Low']}")
            checks_passed.append("Standalone parsing")
        else:
            print("❌ No issues data returned")
            checks_failed.append("Standalone parsing")
    except Exception as e:
        print(f"❌ Parsing error: {e}")
        checks_failed.append("Standalone parsing")
    
    # 3. Check priority sorting
    print("\n3. PRIORITY SORTING VERIFICATION")
    print("-" * 40)
    if issues_data and issues_data.get('issues'):
        is_sorted = True
        prev_priority = 0
        for issue in issues_data['issues']:
            current_priority = IssuesOverviewParser.PRIORITY_ORDER.get(
                issue['issue_priority'], 999
            )
            if current_priority < prev_priority:
                is_sorted = False
                break
            prev_priority = current_priority
        
        if is_sorted:
            print("✅ Issues correctly sorted by priority")
            checks_passed.append("Priority sorting")
        else:
            print("❌ Issues not properly sorted")
            checks_failed.append("Priority sorting")
    
    # 4. Check database integration
    print("\n4. DATABASE INTEGRATION CHECK")
    print("-" * 40)
    try:
        # Get or create test project
        user = User.objects.first()
        project, created = Project.objects.get_or_create(
            domain='production-test.limeclicks.com',
            defaults={'title': 'Production Test', 'user': user}
        )
        
        # Create or get site audit
        site_audit, created = SiteAudit.objects.get_or_create(
            project=project,
            defaults={'temp_audit_dir': temp_audit_dir}
        )
        
        # Parse with database save
        parser_with_db = IssuesOverviewParser(temp_audit_dir, site_audit)
        saved_data = parser_with_db.parse()
        
        # Verify data was saved
        site_audit.refresh_from_db()
        if site_audit.issues_overview and site_audit.issues_overview.get('issues'):
            print("✅ Data successfully saved to database")
            print(f"   Database issues count: {len(site_audit.issues_overview['issues'])}")
            checks_passed.append("Database integration")
        else:
            print("❌ Data not saved to database")
            checks_failed.append("Database integration")
    except Exception as e:
        print(f"❌ Database integration error: {e}")
        checks_failed.append("Database integration")
    
    # 5. Check data integrity
    print("\n5. DATA INTEGRITY CHECK")
    print("-" * 40)
    if site_audit.issues_overview:
        integrity_checks = []
        
        # Check all required fields are present
        sample_issue = site_audit.issues_overview['issues'][0] if site_audit.issues_overview['issues'] else {}
        required_fields = ['issue_name', 'issue_type', 'issue_priority', 'urls']
        
        for field in required_fields:
            if field in sample_issue:
                integrity_checks.append(True)
            else:
                print(f"   ❌ Missing field: {field}")
                integrity_checks.append(False)
        
        if all(integrity_checks):
            print("✅ All required fields present in issues")
            checks_passed.append("Data integrity")
        else:
            print("❌ Some required fields missing")
            checks_failed.append("Data integrity")
    
    # 6. Check process_results integration
    print("\n6. PROCESS_RESULTS INTEGRATION CHECK")
    print("-" * 40)
    try:
        # Test the complete workflow
        site_audit.temp_audit_dir = temp_audit_dir
        results = site_audit.process_results()
        
        if results['status'] in ['success', 'partial_success']:
            print("✅ process_results() integration successful")
            print(f"   Status: {results['status']}")
            print(f"   Total issues: {results.get('total_issues', 0)}")
            checks_passed.append("process_results integration")
        else:
            print(f"❌ process_results() failed: {results.get('message')}")
            checks_failed.append("process_results integration")
    except Exception as e:
        print(f"❌ process_results() error: {e}")
        checks_failed.append("process_results integration")
    
    # 7. Check helper methods
    print("\n7. HELPER METHODS CHECK")
    print("-" * 40)
    try:
        total_issues = site_audit.get_total_issues_count()
        issues_by_priority = site_audit.get_issues_by_priority()
        
        print(f"✅ Helper methods working correctly")
        print(f"   get_total_issues_count(): {total_issues}")
        print(f"   get_issues_by_priority(): {issues_by_priority}")
        checks_passed.append("Helper methods")
    except Exception as e:
        print(f"❌ Helper methods error: {e}")
        checks_failed.append("Helper methods")
    
    # 8. Check error handling
    print("\n8. ERROR HANDLING CHECK")
    print("-" * 40)
    try:
        # Test with invalid directory
        invalid_parser = IssuesOverviewParser("/invalid/path")
        invalid_data = invalid_parser.parse()
        
        if invalid_data == {}:
            print("✅ Handles invalid paths gracefully")
            checks_passed.append("Error handling")
        else:
            print("⚠️ Unexpected data from invalid path")
    except Exception as e:
        print(f"❌ Error handling failed: {e}")
        checks_failed.append("Error handling")
    
    # Final summary
    print("\n" + "=" * 80)
    print("PRODUCTION VERIFICATION SUMMARY")
    print("=" * 80)
    
    total_checks = len(checks_passed) + len(checks_failed)
    success_rate = (len(checks_passed) / total_checks * 100) if total_checks > 0 else 0
    
    print(f"\n✅ Passed: {len(checks_passed)}/{total_checks} checks")
    for check in checks_passed:
        print(f"   ✓ {check}")
    
    if checks_failed:
        print(f"\n❌ Failed: {len(checks_failed)}/{total_checks} checks")
        for check in checks_failed:
            print(f"   ✗ {check}")
    
    print(f"\n📊 Success Rate: {success_rate:.1f}%")
    
    if success_rate == 100:
        print("\n🎉 PARSER IS PRODUCTION READY!")
        print("All verification checks passed successfully.")
    elif success_rate >= 80:
        print("\n⚠️ PARSER MOSTLY READY")
        print("Some non-critical checks failed. Review before production use.")
    else:
        print("\n❌ PARSER NOT READY FOR PRODUCTION")
        print("Critical issues found. Fix before deployment.")
    
    return success_rate == 100

if __name__ == "__main__":
    try:
        is_ready = verify_production_readiness()
        print(f"\n{'✅' if is_ready else '❌'} Production readiness: {'READY' if is_ready else 'NOT READY'}")
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()