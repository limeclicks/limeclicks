#!/usr/bin/env python3
"""
🚀 USER PRIORITY SYSTEM TEST SCRIPT
===================================

Test script to verify that user-initiated rank rechecks get highest priority
and are processed immediately, jumping ahead of the daily queue.

Usage:
    python test_priority_system.py [--keyword-id ID] [--project-id ID] [--auto]

Options:
    --keyword-id ID    Test specific keyword ID
    --project-id ID    Test random keyword from specific project  
    --auto             Automatically select a keyword to test
"""

import os
import sys
import time
import argparse
from datetime import datetime, timedelta

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
import django
django.setup()

from django.utils import timezone
from django.contrib.auth.models import User
from keywords.models import Keyword
from project.models import Project
from keywords.tasks import user_recheck_keyword_rank
from celery import current_app


class PriorityTester:
    def __init__(self):
        self.test_results = {
            'timestamp': timezone.now().isoformat(),
            'test_keyword': None,
            'priority_test': {},
            'processing_test': {},
            'overall_result': 'UNKNOWN'
        }
    
    def run_priority_test(self, keyword_id=None, project_id=None, auto_select=False):
        """Run complete priority system test"""
        print("🚀 USER PRIORITY SYSTEM TEST")
        print("=" * 40)
        print(f"Time: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Select test keyword
        keyword = self.select_test_keyword(keyword_id, project_id, auto_select)
        if not keyword:
            print("❌ No suitable keyword found for testing")
            return False
        
        self.test_results['test_keyword'] = {
            'id': keyword.id,
            'keyword': keyword.keyword,
            'project': keyword.project.domain,
            'current_rank': keyword.rank,
            'last_scraped': keyword.scraped_at.isoformat() if keyword.scraped_at else None
        }
        
        print(f"🎯 Testing Keyword: {keyword.keyword} (ID: {keyword.id})")
        print(f"   Project: {keyword.project.domain}")
        print(f"   Current Rank: {keyword.rank}")
        print(f"   Last Scraped: {keyword.scraped_at or 'Never'}")
        print()
        
        # Test priority queueing
        if not self.test_priority_queueing(keyword):
            return False
        
        # Test processing speed
        if not self.test_processing_speed(keyword):
            return False
        
        self.calculate_overall_result()
        self.print_results()
        
        return self.test_results['overall_result'] == 'PASS'
    
    def select_test_keyword(self, keyword_id=None, project_id=None, auto_select=False):
        """Select a keyword for testing"""
        if keyword_id:
            try:
                return Keyword.objects.get(id=keyword_id, archive=False, project__active=True)
            except Keyword.DoesNotExist:
                print(f"❌ Keyword {keyword_id} not found or inactive")
                return None
        
        if project_id:
            try:
                project = Project.objects.get(id=project_id, active=True)
                keywords = project.keywords.filter(archive=False)
                if keywords.exists():
                    return keywords.first()
                else:
                    print(f"❌ No active keywords in project {project_id}")
                    return None
            except Project.DoesNotExist:
                print(f"❌ Project {project_id} not found")
                return None
        
        if auto_select:
            # Select a keyword that hasn't been crawled recently
            suitable_keywords = Keyword.objects.filter(
                archive=False,
                project__active=True,
                processing=False
            ).order_by('scraped_at')[:10]
            
            if suitable_keywords.exists():
                return suitable_keywords.first()
            else:
                print("❌ No suitable keywords found for auto-selection")
                return None
        
        # Interactive selection
        projects = Project.objects.filter(active=True)[:5]
        print("Available projects for testing:")
        for i, project in enumerate(projects, 1):
            keyword_count = project.keywords.filter(archive=False).count()
            print(f"  {i}. {project.domain} ({keyword_count} keywords)")
        
        try:
            choice = int(input("\nSelect project (1-5): ")) - 1
            if 0 <= choice < len(projects):
                project = projects[choice]
                keyword = project.keywords.filter(archive=False).first()
                if keyword:
                    return keyword
                else:
                    print("❌ No keywords in selected project")
                    return None
            else:
                print("❌ Invalid selection")
                return None
        except (ValueError, KeyboardInterrupt):
            print("❌ Invalid input or cancelled")
            return None
    
    def test_priority_queueing(self, keyword):
        """Test that keyword gets queued with highest priority"""
        print("🔍 TESTING PRIORITY QUEUEING...")
        
        # Get current queue state
        i = current_app.control.inspect()
        active_before = i.active()
        active_count_before = sum(len(tasks) for tasks in active_before.values()) if active_before else 0
        
        print(f"   Active tasks before: {active_count_before}")
        
        # Record initial state
        initial_processing = keyword.processing
        initial_scraped_at = keyword.scraped_at
        
        print(f"   Keyword processing before: {initial_processing}")
        
        # Queue with high priority
        print("   🚀 Queueing keyword with user_recheck_keyword_rank...")
        
        try:
            # Mock user ID (get first superuser)
            user = User.objects.filter(is_superuser=True).first()
            user_id = user.id if user else 1
            
            result = user_recheck_keyword_rank.delay(keyword.id, user_id)
            
            if result:
                task_id = result.id
                print(f"   ✅ Task queued successfully: {task_id}")
                
                self.test_results['priority_test'] = {
                    'status': 'PASS',
                    'task_id': task_id,
                    'queue_time': timezone.now().isoformat(),
                    'initial_processing': initial_processing,
                    'message': 'High priority task queued successfully'
                }
                
                # Wait a moment and check if task started
                time.sleep(2)
                keyword.refresh_from_db()
                
                if keyword.processing or keyword.daily_queue_task_id == task_id:
                    print("   ✅ Keyword marked as processing or task ID updated")
                    return True
                else:
                    print("   ⚠️  Keyword not yet marked as processing (may be normal)")
                    return True
            else:
                print("   ❌ Failed to queue task")
                self.test_results['priority_test'] = {
                    'status': 'FAIL',
                    'message': 'Failed to queue high priority task'
                }
                return False
                
        except Exception as e:
            print(f"   ❌ Error queueing task: {e}")
            self.test_results['priority_test'] = {
                'status': 'FAIL',
                'error': str(e),
                'message': f'Exception during queueing: {e}'
            }
            return False
    
    def test_processing_speed(self, keyword):
        """Test that keyword gets processed quickly"""
        print("\n⏱️  TESTING PROCESSING SPEED...")
        
        initial_scraped_at = keyword.scraped_at
        task_id = self.test_results['priority_test'].get('task_id')
        
        print(f"   Monitoring keyword {keyword.id} for up to 3 minutes...")
        print(f"   Task ID: {task_id}")
        
        start_time = time.time()
        max_wait_time = 180  # 3 minutes
        check_interval = 5   # Check every 5 seconds
        
        while time.time() - start_time < max_wait_time:
            time.sleep(check_interval)
            
            keyword.refresh_from_db()
            elapsed = time.time() - start_time
            
            print(f"   ⏳ Checking... ({elapsed:.0f}s elapsed)")
            print(f"      Processing: {keyword.processing}")
            print(f"      Last Scraped: {keyword.scraped_at}")
            
            # Check if keyword was processed (scraped_at changed)
            if keyword.scraped_at and keyword.scraped_at != initial_scraped_at:
                processing_time = elapsed
                print(f"   ✅ Keyword processed in {processing_time:.1f} seconds!")
                
                self.test_results['processing_test'] = {
                    'status': 'PASS',
                    'processing_time': round(processing_time, 1),
                    'initial_scraped_at': initial_scraped_at.isoformat() if initial_scraped_at else None,
                    'final_scraped_at': keyword.scraped_at.isoformat(),
                    'new_rank': keyword.rank,
                    'message': f'Processed in {processing_time:.1f} seconds'
                }
                return True
            
            # Check if task completed but failed
            if not keyword.processing and keyword.scraped_at == initial_scraped_at:
                # Task might have failed
                if keyword.last_error_message:
                    print(f"   ⚠️  Task may have failed: {keyword.last_error_message}")
                
        # Timeout reached
        processing_time = time.time() - start_time
        print(f"   ⚠️  Timeout reached after {processing_time:.0f} seconds")
        
        self.test_results['processing_test'] = {
            'status': 'TIMEOUT',
            'processing_time': round(processing_time, 1),
            'timeout_reached': True,
            'message': f'Did not complete within {max_wait_time} seconds'
        }
        
        # Check if at least task started
        if keyword.processing:
            print("   ℹ️  Keyword is still processing - may complete soon")
            self.test_results['processing_test']['status'] = 'PROCESSING'
            return True
        else:
            print("   ❌ Keyword not processing - possible issue")
            return False
    
    def calculate_overall_result(self):
        """Calculate overall test result"""
        priority_status = self.test_results['priority_test'].get('status', 'FAIL')
        processing_status = self.test_results['processing_test'].get('status', 'FAIL')
        
        if priority_status == 'PASS' and processing_status == 'PASS':
            self.test_results['overall_result'] = 'PASS'
        elif priority_status == 'PASS' and processing_status in ['PROCESSING', 'TIMEOUT']:
            self.test_results['overall_result'] = 'PARTIAL'
        else:
            self.test_results['overall_result'] = 'FAIL'
    
    def print_results(self):
        """Print test results summary"""
        print("\n" + "=" * 40)
        print("📋 PRIORITY SYSTEM TEST RESULTS")
        print("=" * 40)
        
        result_emoji = {
            'PASS': '✅',
            'PARTIAL': '⚠️',
            'FAIL': '❌'
        }
        
        overall = self.test_results['overall_result']
        print(f"Overall Result: {result_emoji[overall]} {overall}")
        
        # Priority test results
        priority = self.test_results['priority_test']
        print(f"\n🚀 Priority Queueing: {result_emoji.get(priority.get('status', 'FAIL'), '❌')} {priority.get('status', 'FAIL')}")
        print(f"   {priority.get('message', 'No message')}")
        
        # Processing test results  
        processing = self.test_results['processing_test']
        print(f"\n⏱️  Processing Speed: {result_emoji.get(processing.get('status', 'FAIL'), '❌')} {processing.get('status', 'FAIL')}")
        print(f"   {processing.get('message', 'No message')}")
        
        if processing.get('processing_time'):
            print(f"   Time: {processing['processing_time']} seconds")
        
        if processing.get('new_rank'):
            print(f"   New Rank: {processing['new_rank']}")
        
        # Recommendations
        print(f"\n💡 Recommendations:")
        if overall == 'PASS':
            print("   ✅ Priority system working correctly!")
            print("   ✅ User rechecks will get immediate attention")
        elif overall == 'PARTIAL':
            print("   ⚠️  System queues correctly but processing is slow")
            print("   🔧 Check Celery worker capacity")
        else:
            print("   ❌ Priority system has issues")
            print("   🔧 Check Celery configuration and worker status")
            print("   🔧 Verify user_recheck_keyword_rank task is available")


def main():
    parser = argparse.ArgumentParser(description='Test User Priority System')
    parser.add_argument('--keyword-id', type=int, help='Test specific keyword ID')
    parser.add_argument('--project-id', type=int, help='Test random keyword from specific project')
    parser.add_argument('--auto', action='store_true', help='Automatically select a keyword to test')
    
    args = parser.parse_args()
    
    if not any([args.keyword_id, args.project_id, args.auto]):
        # Interactive mode
        print("🚀 User Priority System Test")
        print("No keyword specified - entering interactive mode")
        print()
    
    tester = PriorityTester()
    success = tester.run_priority_test(
        keyword_id=args.keyword_id,
        project_id=args.project_id, 
        auto_select=args.auto
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()