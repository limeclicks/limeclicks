#!/usr/bin/env python3

"""
Test script for improved Lighthouse audit system
Tests different types of sites and validates data quality
"""

import os
import django
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from project.models import Project
from performance_audit.models import PerformancePage, PerformanceHistory
from performance_audit.tasks import create_audit_for_project, run_lighthouse_audit
from accounts.models import User

def cleanup_existing_audits():
    """Clean up existing audits for fresh testing"""
    print("🧹 Cleaning up existing audits for fresh testing...")
    
    # Delete existing performance pages to start fresh
    PerformancePage.objects.all().delete()
    print("✅ Cleaned up existing performance pages")

def create_test_projects():
    """Create test projects with different website types"""
    print("🏗️ Creating test projects...")
    
    # Get or create test user
    user, _ = User.objects.get_or_create(
        email='lighthouse-test@example.com',
        defaults={
            'username': 'lighthouse-test',
            'is_active': True,
            'email_verified': True
        }
    )
    
    test_sites = [
        # High-quality sites (should succeed)
        ('google.com', 'Google - Fast Loading'),
        ('github.com', 'GitHub - Developer Platform'),
        ('cloudflare.com', 'Cloudflare - CDN Provider'),
        
        # Medium-quality sites
        ('wikipedia.org', 'Wikipedia - Knowledge Base'),
        ('stackoverflow.com', 'Stack Overflow - Q&A'),
        
        # Potentially problematic sites
        ('example.com', 'Example Domain'),
        ('httpbin.org', 'HTTP Testing Service'),
        
        # Sites with SSL issues (will test our improvements)
        ('badexample.com', 'Bad Example - SSL Issues'),
    ]
    
    projects = []
    for domain, title in test_sites:
        # Delete existing project if it exists
        Project.objects.filter(domain=domain).delete()
        
        project = Project.objects.create(
            user=user,
            domain=domain,
            title=title,
            active=True
        )
        projects.append(project)
        print(f"✅ Created project: {domain}")
    
    return projects

def run_lighthouse_tests(projects, max_concurrent=1):
    """Run lighthouse audits on test projects"""
    print(f"\n🚀 Running Lighthouse audits on {len(projects)} projects...")
    print(f"📊 Max concurrent audits: {max_concurrent}")
    print("="*60)
    
    results = []
    start_time = time.time()
    
    # Run audits one by one to test the locking mechanism
    for i, project in enumerate(projects, 1):
        print(f"\n🔍 Test {i}/{len(projects)}: {project.domain}")
        print(f"⏰ Started at: {datetime.now().strftime('%H:%M:%S')}")
        
        audit_start = time.time()
        
        try:
            # Trigger audit
            result = create_audit_for_project(project.id, 'test_trigger')
            
            if result.get('success'):
                audit_id = result.get('audit_id')
                print(f"✅ Audit queued successfully: {audit_id}")
                
                # Wait for completion (check every 10 seconds)
                max_wait = 600  # 10 minutes
                waited = 0
                
                while waited < max_wait:
                    try:
                        history = PerformanceHistory.objects.get(id=audit_id)
                        if history.status == 'completed':
                            audit_duration = time.time() - audit_start
                            print(f"✅ Audit completed in {audit_duration:.1f}s")
                            
                            # Collect results
                            result_data = {
                                'domain': project.domain,
                                'success': True,
                                'duration': audit_duration,
                                'mobile_performance': history.mobile_performance_score,
                                'desktop_performance': history.desktop_performance_score,
                                'mobile_seo': history.mobile_seo_score,
                                'desktop_seo': history.desktop_seo_score,
                                'mobile_accessibility': history.mobile_accessibility_score,
                                'desktop_accessibility': history.desktop_accessibility_score,
                                'status': 'completed'
                            }
                            results.append(result_data)
                            break
                            
                        elif history.status == 'failed':
                            audit_duration = time.time() - audit_start
                            print(f"❌ Audit failed after {audit_duration:.1f}s")
                            print(f"   Error: {history.error_message}")
                            
                            result_data = {
                                'domain': project.domain,
                                'success': False,
                                'duration': audit_duration,
                                'error': history.error_message,
                                'retry_count': history.retry_count,
                                'status': 'failed'
                            }
                            results.append(result_data)
                            break
                            
                        elif history.status == 'running':
                            print(f"🔄 Still running... ({waited}s elapsed)")
                        
                        time.sleep(10)
                        waited += 10
                        
                    except PerformanceHistory.DoesNotExist:
                        print(f"⏳ Waiting for audit to start... ({waited}s)")
                        time.sleep(10)
                        waited += 10
                
                if waited >= max_wait:
                    print(f"⏰ Audit timed out after {max_wait}s")
                    results.append({
                        'domain': project.domain,
                        'success': False,
                        'duration': max_wait,
                        'error': 'Timeout',
                        'status': 'timeout'
                    })
            else:
                print(f"❌ Failed to queue audit: {result.get('error')}")
                results.append({
                    'domain': project.domain,
                    'success': False,
                    'duration': 0,
                    'error': result.get('error'),
                    'status': 'queue_failed'
                })
                
        except Exception as e:
            print(f"❌ Exception during audit: {e}")
            results.append({
                'domain': project.domain,
                'success': False,
                'duration': time.time() - audit_start,
                'error': str(e),
                'status': 'exception'
            })
    
    total_duration = time.time() - start_time
    
    print(f"\n{'='*60}")
    print(f"🏁 ALL TESTS COMPLETED")
    print(f"⏱️ Total time: {total_duration:.1f}s")
    print(f"{'='*60}")
    
    return results

def analyze_results(results):
    """Analyze and report on test results"""
    print(f"\n📊 LIGHTHOUSE AUDIT RESULTS ANALYSIS")
    print(f"="*60)
    
    total_tests = len(results)
    successful_tests = sum(1 for r in results if r['success'])
    failed_tests = total_tests - successful_tests
    
    print(f"Total Tests: {total_tests}")
    print(f"✅ Successful: {successful_tests}")
    print(f"❌ Failed: {failed_tests}")
    print(f"Success Rate: {(successful_tests/total_tests*100):.1f}%")
    
    if successful_tests > 0:
        print(f"\n🎯 SUCCESSFUL AUDITS:")
        print(f"-"*40)
        
        mobile_scores = []
        desktop_scores = []
        
        for result in results:
            if result['success']:
                domain = result['domain']
                duration = result['duration']
                mobile_perf = result.get('mobile_performance', 0)
                desktop_perf = result.get('desktop_performance', 0)
                mobile_seo = result.get('mobile_seo', 0)
                desktop_seo = result.get('desktop_seo', 0)
                
                print(f"📈 {domain}:")
                print(f"   ⏱️ Duration: {duration:.1f}s")
                print(f"   📱 Mobile - Perf: {mobile_perf}, SEO: {mobile_seo}")
                print(f"   🖥️ Desktop - Perf: {desktop_perf}, SEO: {desktop_seo}")
                
                if mobile_perf: mobile_scores.append(mobile_perf)
                if desktop_perf: desktop_scores.append(desktop_perf)
        
        if mobile_scores:
            avg_mobile = sum(mobile_scores) / len(mobile_scores)
            print(f"\n📱 Average Mobile Performance: {avg_mobile:.1f}")
        
        if desktop_scores:
            avg_desktop = sum(desktop_scores) / len(desktop_scores)
            print(f"🖥️ Average Desktop Performance: {avg_desktop:.1f}")
    
    if failed_tests > 0:
        print(f"\n❌ FAILED AUDITS:")
        print(f"-"*40)
        
        error_counts = {}
        for result in results:
            if not result['success']:
                domain = result['domain']
                error = result.get('error', 'Unknown error')
                status = result.get('status', 'failed')
                retry_count = result.get('retry_count', 0)
                
                print(f"💥 {domain}:")
                print(f"   Status: {status}")
                print(f"   Error: {error[:100]}...")
                print(f"   Retries: {retry_count}")
                
                # Count error types
                if 'SSL' in error or 'CERT' in error:
                    error_type = 'SSL/Certificate Issues'
                elif 'timeout' in error.lower():
                    error_type = 'Timeout'
                elif 'not found' in error.lower():
                    error_type = 'Site Not Found'
                else:
                    error_type = 'Other'
                
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        print(f"\n📊 Error Type Breakdown:")
        for error_type, count in error_counts.items():
            print(f"   {error_type}: {count}")
    
    # Data Quality Assessment
    print(f"\n🔍 DATA QUALITY ASSESSMENT:")
    print(f"-"*40)
    
    if successful_tests >= 5:
        print("✅ EXCELLENT: 5+ successful audits - Production ready!")
    elif successful_tests >= 3:
        print("✅ GOOD: 3+ successful audits - Mostly reliable")
    elif successful_tests >= 1:
        print("⚠️ FAIR: Some successful audits - Needs improvement")
    else:
        print("❌ POOR: No successful audits - Major issues need fixing")
    
    return {
        'total': total_tests,
        'successful': successful_tests,
        'failed': failed_tests,
        'success_rate': successful_tests/total_tests*100
    }

def main():
    """Main test function"""
    print("🚀 LIGHTHOUSE AUDIT IMPROVEMENTS TEST")
    print("="*60)
    print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Step 1: Cleanup
        cleanup_existing_audits()
        
        # Step 2: Create test projects
        projects = create_test_projects()
        
        # Step 3: Run tests
        results = run_lighthouse_tests(projects, max_concurrent=1)
        
        # Step 4: Analyze results
        summary = analyze_results(results)
        
        print(f"\n🎉 TEST SUMMARY:")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        
        if summary['success_rate'] >= 75:
            print("🚀 LIGHTHOUSE IMPROVEMENTS ARE ROCK SOLID!")
            return True
        else:
            print("⚠️ Lighthouse needs more improvements")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)