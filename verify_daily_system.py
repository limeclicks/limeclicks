#!/usr/bin/env python3
"""
🎯 DAILY SYSTEM VERIFICATION SCRIPT
==================================

Comprehensive verification script to check if the new daily keyword scheduling system 
is working correctly. Run this after 12:01 AM to verify the system.

Usage:
    python verify_daily_system.py [--quick] [--detailed] [--json]

Options:
    --quick     Quick health check only
    --detailed  Detailed analysis with keyword breakdowns
    --json      Output in JSON format for automation
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from collections import defaultdict

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
import django
django.setup()

from django.utils import timezone
from django.db.models import Count, Q, Avg
from keywords.models import Keyword
from project.models import Project
from celery import current_app


class SystemVerifier:
    def __init__(self):
        self.results = {
            'timestamp': timezone.now().isoformat(),
            'date_checked': timezone.now().date().isoformat(),
            'overall_status': 'UNKNOWN',
            'checks': {},
            'stats': {},
            'issues': [],
            'recommendations': []
        }
    
    def run_all_checks(self, detailed=False):
        """Run all verification checks"""
        print("🔍 DAILY SYSTEM VERIFICATION STARTING...")
        print(f"📅 Date: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # Core system checks
        self.check_daily_queue_execution()
        self.check_keyword_processing_status()
        self.check_celery_services()
        self.check_database_tracking()
        self.check_user_priority_system()
        
        if detailed:
            self.detailed_keyword_analysis()
            self.check_project_health()
            self.check_system_performance()
        
        self.calculate_overall_status()
        return self.results
    
    def check_daily_queue_execution(self):
        """Verify daily queue was executed at 12:01 AM"""
        today = timezone.now().date()
        
        # Check if keywords were queued today
        queued_today = Keyword.objects.filter(
            last_queue_date=today,
            archive=False,
            project__active=True
        ).count()
        
        total_active = Keyword.objects.filter(
            archive=False,
            project__active=True
        ).count()
        
        queue_percentage = (queued_today / total_active * 100) if total_active > 0 else 0
        
        status = "PASS" if queue_percentage >= 95 else "FAIL"
        
        self.results['checks']['daily_queue'] = {
            'status': status,
            'queued_today': queued_today,
            'total_active': total_active,
            'queue_percentage': round(queue_percentage, 1),
            'message': f"{queued_today}/{total_active} keywords queued today ({queue_percentage:.1f}%)"
        }
        
        if status == "FAIL":
            self.results['issues'].append(
                f"Daily queue incomplete: Only {queue_percentage:.1f}% of keywords queued"
            )
        
        print(f"✅ Daily Queue: {status} - {queued_today}/{total_active} keywords queued ({queue_percentage:.1f}%)")
    
    def check_keyword_processing_status(self):
        """Check keyword processing progress"""
        today = timezone.now().date()
        now = timezone.now()
        
        # Processing statistics
        total_keywords = Keyword.objects.filter(archive=False, project__active=True).count()
        processed_today = Keyword.objects.filter(
            archive=False,
            project__active=True,
            scraped_at__date=today
        ).count()
        
        stuck_keywords = Keyword.objects.filter(
            archive=False,
            project__active=True,
            processing=True
        ).count()
        
        # Calculate processing rate
        processing_rate = (processed_today / total_keywords * 100) if total_keywords > 0 else 0
        
        # Time since midnight
        midnight = timezone.now().replace(hour=0, minute=1, second=0, microsecond=0)
        hours_since_queue = (now - midnight).total_seconds() / 3600
        
        expected_processed = min(total_keywords, hours_since_queue * 100)  # Assume 100/hour capacity
        
        status = "PASS"
        if stuck_keywords > 50:
            status = "WARN"
        if processing_rate < 10 and hours_since_queue > 2:
            status = "FAIL"
        
        self.results['checks']['processing'] = {
            'status': status,
            'total_keywords': total_keywords,
            'processed_today': processed_today,
            'stuck_keywords': stuck_keywords,
            'processing_rate': round(processing_rate, 1),
            'hours_since_queue': round(hours_since_queue, 1),
            'message': f"{processed_today}/{total_keywords} processed ({processing_rate:.1f}%), {stuck_keywords} stuck"
        }
        
        if status == "FAIL":
            self.results['issues'].append(
                f"Processing too slow: {processing_rate:.1f}% after {hours_since_queue:.1f} hours"
            )
        elif status == "WARN":
            self.results['issues'].append(f"High stuck keywords: {stuck_keywords}")
        
        print(f"✅ Processing: {status} - {processed_today}/{total_keywords} done ({processing_rate:.1f}%), {stuck_keywords} stuck")
    
    def check_celery_services(self):
        """Check Celery worker and beat status"""
        try:
            # Check active workers
            i = current_app.control.inspect()
            stats = i.stats()
            active = i.active()
            
            worker_count = len(stats) if stats else 0
            active_tasks = sum(len(tasks) for tasks in active.values()) if active else 0
            
            status = "PASS" if worker_count > 0 else "FAIL"
            
            self.results['checks']['celery'] = {
                'status': status,
                'worker_count': worker_count,
                'active_tasks': active_tasks,
                'message': f"{worker_count} workers running, {active_tasks} active tasks"
            }
            
            if status == "FAIL":
                self.results['issues'].append("No Celery workers detected")
            
            print(f"✅ Celery: {status} - {worker_count} workers, {active_tasks} active tasks")
            
        except Exception as e:
            self.results['checks']['celery'] = {
                'status': 'FAIL',
                'error': str(e),
                'message': f"Celery check failed: {e}"
            }
            self.results['issues'].append(f"Celery error: {e}")
            print(f"❌ Celery: FAIL - {e}")
    
    def check_database_tracking(self):
        """Verify database tracking fields are working"""
        today = timezone.now().date()
        
        # Check tracking field usage
        with_task_id = Keyword.objects.filter(
            archive=False,
            project__active=True,
            last_queue_date=today,
            daily_queue_task_id__isnull=False
        ).count()
        
        with_expected_time = Keyword.objects.filter(
            archive=False,
            project__active=True,
            last_queue_date=today,
            expected_crawl_time__isnull=False
        ).count()
        
        queued_today = Keyword.objects.filter(
            archive=False,
            project__active=True,
            last_queue_date=today
        ).count()
        
        tracking_percentage = (with_task_id / queued_today * 100) if queued_today > 0 else 0
        
        status = "PASS" if tracking_percentage >= 90 else "FAIL"
        
        self.results['checks']['tracking'] = {
            'status': status,
            'with_task_id': with_task_id,
            'with_expected_time': with_expected_time,
            'queued_today': queued_today,
            'tracking_percentage': round(tracking_percentage, 1),
            'message': f"{with_task_id}/{queued_today} have tracking data ({tracking_percentage:.1f}%)"
        }
        
        if status == "FAIL":
            self.results['issues'].append(
                f"Poor tracking data: {tracking_percentage:.1f}% completion"
            )
        
        print(f"✅ Tracking: {status} - {with_task_id}/{queued_today} tracked ({tracking_percentage:.1f}%)")
    
    def check_user_priority_system(self):
        """Check if user priority system is ready"""
        # This is more of a readiness check since we can't test without user action
        
        # Check if the new task exists
        try:
            from keywords.tasks import user_recheck_keyword_rank
            task_available = True
        except ImportError:
            task_available = False
        
        # Check recent force crawls (high priority usage)
        recent_force = Keyword.objects.filter(
            last_force_crawl_at__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        status = "PASS" if task_available else "FAIL"
        
        self.results['checks']['priority_system'] = {
            'status': status,
            'task_available': task_available,
            'recent_force_crawls': recent_force,
            'message': f"Priority system {'ready' if task_available else 'NOT available'}, {recent_force} recent force crawls"
        }
        
        if status == "FAIL":
            self.results['issues'].append("User priority system not available")
        
        print(f"✅ Priority System: {status} - {'Ready' if task_available else 'Not available'}")
    
    def detailed_keyword_analysis(self):
        """Detailed breakdown by project and status"""
        today = timezone.now().date()
        
        projects = Project.objects.filter(active=True).annotate(
            total_keywords=Count('keywords', filter=Q(keywords__archive=False)),
            processed_today=Count('keywords', filter=Q(
                keywords__archive=False,
                keywords__scraped_at__date=today
            )),
            stuck_keywords=Count('keywords', filter=Q(
                keywords__archive=False,
                keywords__processing=True
            ))
        ).order_by('-total_keywords')
        
        project_details = []
        for project in projects[:10]:  # Top 10 projects
            completion_rate = (project.processed_today / project.total_keywords * 100) if project.total_keywords > 0 else 0
            project_details.append({
                'domain': project.domain,
                'total': project.total_keywords,
                'processed': project.processed_today,
                'stuck': project.stuck_keywords,
                'completion_rate': round(completion_rate, 1)
            })
        
        self.results['stats']['project_breakdown'] = project_details
        
        print(f"\n📊 TOP PROJECT ANALYSIS:")
        print(f"{'Domain':<25} {'Total':<8} {'Done':<8} {'Stuck':<8} {'Rate':<8}")
        print("-" * 60)
        for proj in project_details:
            print(f"{proj['domain']:<25} {proj['total']:<8} {proj['processed']:<8} {proj['stuck']:<8} {proj['completion_rate']:.1f}%")
    
    def check_project_health(self):
        """Check individual project health"""
        today = timezone.now().date()
        
        unhealthy_projects = Project.objects.filter(active=True).annotate(
            total_keywords=Count('keywords', filter=Q(keywords__archive=False)),
            processed_today=Count('keywords', filter=Q(
                keywords__archive=False,
                keywords__scraped_at__date=today
            ))
        ).filter(total_keywords__gt=10).exclude(
            processed_today__gt=0
        )
        
        self.results['stats']['unhealthy_projects'] = unhealthy_projects.count()
        
        if unhealthy_projects.exists():
            self.results['issues'].append(
                f"{unhealthy_projects.count()} projects with no keywords processed today"
            )
    
    def check_system_performance(self):
        """Check system performance metrics"""
        today = timezone.now().date()
        
        # Processing speed analysis
        midnight = timezone.now().replace(hour=0, minute=1, second=0, microsecond=0)
        hours_running = (timezone.now() - midnight).total_seconds() / 3600
        
        processed_today = Keyword.objects.filter(
            archive=False,
            project__active=True,
            scraped_at__date=today
        ).count()
        
        processing_speed = processed_today / hours_running if hours_running > 0 else 0
        
        self.results['stats']['performance'] = {
            'hours_running': round(hours_running, 1),
            'processed_today': processed_today,
            'processing_speed': round(processing_speed, 1),
            'estimated_completion': round((2132 - processed_today) / processing_speed, 1) if processing_speed > 0 else 'Unknown'
        }
    
    def calculate_overall_status(self):
        """Calculate overall system status"""
        statuses = [check['status'] for check in self.results['checks'].values()]
        
        if 'FAIL' in statuses:
            self.results['overall_status'] = 'FAIL'
        elif 'WARN' in statuses:
            self.results['overall_status'] = 'WARN'
        else:
            self.results['overall_status'] = 'PASS'
    
    def generate_recommendations(self):
        """Generate actionable recommendations"""
        if self.results['overall_status'] == 'FAIL':
            self.results['recommendations'].append(
                "❌ System has critical issues - immediate attention required"
            )
        elif self.results['overall_status'] == 'WARN':
            self.results['recommendations'].append(
                "⚠️ System has minor issues - monitor closely"
            )
        else:
            self.results['recommendations'].append(
                "✅ System operating normally - continue monitoring"
            )
        
        # Specific recommendations based on issues
        for issue in self.results['issues']:
            if 'stuck' in issue.lower():
                self.results['recommendations'].append(
                    "🔧 Run: python manage.py shell -c \"from keywords.tasks import cleanup_stuck_keywords; cleanup_stuck_keywords()\""
                )
            elif 'queue' in issue.lower():
                self.results['recommendations'].append(
                    "🔧 Check if daily_queue_all_keywords task ran at 12:01 AM"
                )
    
    def print_summary(self):
        """Print verification summary"""
        print("\n" + "=" * 60)
        print("📋 VERIFICATION SUMMARY")
        print("=" * 60)
        
        status_emoji = {
            'PASS': '✅',
            'WARN': '⚠️',
            'FAIL': '❌'
        }
        
        print(f"Overall Status: {status_emoji[self.results['overall_status']]} {self.results['overall_status']}")
        
        if self.results['issues']:
            print(f"\n🚨 Issues Found ({len(self.results['issues'])}):")
            for issue in self.results['issues']:
                print(f"  • {issue}")
        
        self.generate_recommendations()
        
        if self.results['recommendations']:
            print(f"\n💡 Recommendations:")
            for rec in self.results['recommendations']:
                print(f"  {rec}")
        
        print(f"\n📊 Quick Stats:")
        if 'daily_queue' in self.results['checks']:
            dq = self.results['checks']['daily_queue']
            print(f"  • Queued Today: {dq['queued_today']}/{dq['total_active']} ({dq['queue_percentage']}%)")
        
        if 'processing' in self.results['checks']:
            proc = self.results['checks']['processing']
            print(f"  • Processed Today: {proc['processed_today']}/{proc['total_keywords']} ({proc['processing_rate']}%)")
            print(f"  • Stuck Keywords: {proc['stuck_keywords']}")


def main():
    parser = argparse.ArgumentParser(description='Daily System Verification')
    parser.add_argument('--quick', action='store_true', help='Quick check only')
    parser.add_argument('--detailed', action='store_true', help='Detailed analysis')
    parser.add_argument('--json', action='store_true', help='JSON output')
    
    args = parser.parse_args()
    
    verifier = SystemVerifier()
    results = verifier.run_all_checks(detailed=args.detailed)
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        verifier.print_summary()
    
    # Exit with appropriate code
    exit_code = {
        'PASS': 0,
        'WARN': 1,
        'FAIL': 2
    }.get(results['overall_status'], 2)
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()