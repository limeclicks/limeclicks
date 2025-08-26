#!/usr/bin/env python3

"""
Simple test script for lighthouse improvements
"""

import os
import django
import time
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from project.models import Project
from performance_audit.models import PerformancePage, PerformanceHistory
from performance_audit.tasks import create_audit_for_project
from accounts.models import User

def simple_lighthouse_test():
    """Test lighthouse with a few reliable sites"""
    print("🚀 SIMPLE LIGHTHOUSE IMPROVEMENTS TEST")
    print("="*50)
    print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get or create test user
    user, _ = User.objects.get_or_create(
        email='lighthouse-test@example.com',
        defaults={
            'username': 'lighthouse-test',
            'is_active': True,
            'email_verified': True
        }
    )
    
    # Test sites (reliable ones first)
    test_sites = [
        ('google.com', 'Google'),
        ('github.com', 'GitHub'), 
        ('example.com', 'Example Domain'),
    ]
    
    results = []
    
    for domain, title in test_sites:
        print(f"\n🔍 Testing: {domain}")
        print("-" * 30)
        
        # Clean up existing project
        Project.objects.filter(domain=domain).delete()
        
        # Create project
        project = Project.objects.create(
            user=user,
            domain=domain,
            title=title,
            active=True
        )
        
        start_time = time.time()
        
        try:
            # Trigger audit
            result = create_audit_for_project(project.id, 'test')
            
            if result.get('success'):
                audit_id = result.get('audit_id')
                print(f"✅ Audit queued: {audit_id}")
                
                # Wait for completion
                max_wait = 300  # 5 minutes
                waited = 0
                
                while waited < max_wait:
                    try:
                        history = PerformanceHistory.objects.get(id=audit_id)
                        if history.status == 'completed':
                            duration = time.time() - start_time
                            print(f"✅ Completed in {duration:.1f}s")
                            print(f"   Mobile Performance: {history.mobile_performance_score}")
                            print(f"   Desktop Performance: {history.desktop_performance_score}")
                            
                            results.append({
                                'domain': domain,
                                'success': True,
                                'duration': duration,
                                'mobile_perf': history.mobile_performance_score,
                                'desktop_perf': history.desktop_performance_score
                            })
                            break
                            
                        elif history.status == 'failed':
                            duration = time.time() - start_time
                            print(f"❌ Failed after {duration:.1f}s")
                            print(f"   Error: {history.error_message}")
                            
                            results.append({
                                'domain': domain,
                                'success': False,
                                'duration': duration,
                                'error': history.error_message
                            })
                            break
                        
                        time.sleep(10)
                        waited += 10
                        
                    except PerformanceHistory.DoesNotExist:
                        time.sleep(5)
                        waited += 5
                
                if waited >= max_wait:
                    print(f"⏰ Timed out after {max_wait}s")
                    results.append({
                        'domain': domain,
                        'success': False,
                        'duration': max_wait,
                        'error': 'Timeout'
                    })
            else:
                print(f"❌ Failed to queue: {result.get('error')}")
                results.append({
                    'domain': domain,
                    'success': False,
                    'duration': time.time() - start_time,
                    'error': result.get('error')
                })
                
        except Exception as e:
            duration = time.time() - start_time
            print(f"❌ Exception: {e}")
            results.append({
                'domain': domain,
                'success': False,
                'duration': duration,
                'error': str(e)
            })
    
    # Summary
    print(f"\n{'='*50}")
    print("📊 TEST RESULTS SUMMARY")
    print("="*50)
    
    successful = sum(1 for r in results if r['success'])
    total = len(results)
    
    print(f"Total Tests: {total}")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {total - successful}")
    print(f"Success Rate: {(successful/total*100):.1f}%")
    
    if successful > 0:
        print(f"\n✅ SUCCESSFUL AUDITS:")
        for r in results:
            if r['success']:
                print(f"   {r['domain']}: {r['duration']:.1f}s - Mobile: {r['mobile_perf']}, Desktop: {r['desktop_perf']}")
    
    if successful < total:
        print(f"\n❌ FAILED AUDITS:")
        for r in results:
            if not r['success']:
                print(f"   {r['domain']}: {r['error']}")
    
    if successful >= 2:
        print("\n🎉 LIGHTHOUSE IMPROVEMENTS WORKING!")
        return True
    else:
        print("\n⚠️ Need more improvements")
        return False

if __name__ == "__main__":
    success = simple_lighthouse_test()
    exit(0 if success else 1)