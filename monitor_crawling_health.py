#!/usr/bin/env python
"""
MONITORING SCRIPT - Run after 24 hours to verify fixes are working
This script tracks keyword crawling health over time

Usage:
    python monitor_crawling_health.py          # Run once
    python monitor_crawling_health.py --watch  # Continuous monitoring
    python monitor_crawling_health.py --report # Generate detailed report
"""

import os
import sys
import django
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min
import time
import json

# Setup Django
os.environ['DATABASE_URL'] = 'postgresql://postgres:LimeClicksPwd007@localhost:5432/lime'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from keywords.models import Keyword, Rank
from project.models import Project
from django_celery_beat.models import PeriodicTask


class CrawlingHealthMonitor:
    """Monitor crawling system health"""
    
    def __init__(self):
        self.start_time = timezone.now()
        self.issues_found = []
        self.metrics = {}
    
    def check_stuck_keywords(self):
        """Check for keywords stuck in processing state"""
        stuck = Keyword.objects.filter(processing=True)
        count = stuck.count()
        
        if count > 0:
            # Check how long they've been stuck
            oldest_stuck = stuck.order_by('updated_at').first()
            if oldest_stuck:
                stuck_duration = timezone.now() - oldest_stuck.updated_at
                
                self.metrics['stuck_keywords'] = count
                self.metrics['oldest_stuck_duration'] = str(stuck_duration)
                
                if stuck_duration > timedelta(hours=2):
                    self.issues_found.append(
                        f"CRITICAL: {count} keywords stuck for {stuck_duration}"
                    )
                elif stuck_duration > timedelta(hours=1):
                    self.issues_found.append(
                        f"WARNING: {count} keywords stuck for {stuck_duration}"
                    )
        else:
            self.metrics['stuck_keywords'] = 0
        
        return count
    
    def check_crawl_freshness(self):
        """Check if keywords are being crawled regularly"""
        now = timezone.now()
        one_day_ago = now - timedelta(hours=24)
        two_days_ago = now - timedelta(hours=48)
        
        # Count keywords by last crawl time
        never_crawled = Keyword.objects.filter(
            scraped_at__isnull=True,
            archive=False
        ).count()
        
        overdue_24h = Keyword.objects.filter(
            scraped_at__lt=one_day_ago,
            scraped_at__gte=two_days_ago,
            archive=False,
            project__active=True
        ).count()
        
        overdue_48h = Keyword.objects.filter(
            scraped_at__lt=two_days_ago,
            archive=False,
            project__active=True
        ).count()
        
        recently_crawled = Keyword.objects.filter(
            scraped_at__gte=one_day_ago,
            archive=False
        ).count()
        
        self.metrics['never_crawled'] = never_crawled
        self.metrics['overdue_24h'] = overdue_24h
        self.metrics['overdue_48h'] = overdue_48h
        self.metrics['recently_crawled'] = recently_crawled
        
        # Check if backlog is growing
        total_active = Keyword.objects.filter(archive=False, project__active=True).count()
        if total_active > 0:
            overdue_percentage = (overdue_24h + overdue_48h) * 100 / total_active
            
            if overdue_percentage > 50:
                self.issues_found.append(
                    f"CRITICAL: {overdue_percentage:.1f}% keywords overdue for crawl"
                )
            elif overdue_percentage > 20:
                self.issues_found.append(
                    f"WARNING: {overdue_percentage:.1f}% keywords overdue for crawl"
                )
    
    def check_project_7_specifically(self):
        """Check Project 7 health specifically"""
        try:
            project = Project.objects.get(id=7)
            keywords = Keyword.objects.filter(project_id=7, archive=False)
            total = keywords.count()
            
            if total == 0:
                return
            
            stuck = keywords.filter(processing=True).count()
            
            one_day_ago = timezone.now() - timedelta(hours=24)
            needs_crawl = keywords.filter(
                Q(scraped_at__isnull=True) | Q(scraped_at__lt=one_day_ago)
            ).count()
            
            recently_crawled = keywords.filter(scraped_at__gte=one_day_ago).count()
            
            self.metrics['project_7'] = {
                'total': total,
                'stuck': stuck,
                'needs_crawl': needs_crawl,
                'recently_crawled': recently_crawled,
                'health_percentage': (recently_crawled * 100 / total) if total > 0 else 0
            }
            
            if stuck > 10:
                self.issues_found.append(f"Project 7: {stuck} keywords stuck")
            
            if needs_crawl > total * 0.5:
                self.issues_found.append(
                    f"Project 7: {needs_crawl}/{total} keywords need crawl"
                )
                
        except Project.DoesNotExist:
            pass
    
    def check_celery_tasks(self):
        """Check if Celery tasks are running properly"""
        try:
            # Check periodic tasks
            tasks = PeriodicTask.objects.filter(enabled=True)
            
            # Check critical tasks
            critical_tasks = [
                'enqueue_keyword_scrapes_batch',
                'cleanup_stuck_keywords',
                'worker_health_check'
            ]
            
            for task_name in critical_tasks:
                task = tasks.filter(task__icontains=task_name).first()
                if task:
                    if task.last_run_at:
                        time_since = timezone.now() - task.last_run_at
                        
                        self.metrics[f'task_{task_name}'] = {
                            'last_run': str(task.last_run_at),
                            'time_since': str(time_since)
                        }
                        
                        # Check if task is running regularly
                        if 'enqueue' in task_name and time_since > timedelta(minutes=10):
                            self.issues_found.append(
                                f"Task {task_name} hasn't run in {time_since}"
                            )
                        elif 'cleanup' in task_name and time_since > timedelta(minutes=30):
                            self.issues_found.append(
                                f"Cleanup task hasn't run in {time_since}"
                            )
                else:
                    self.issues_found.append(f"CRITICAL: Task {task_name} not found!")
                    
        except Exception as e:
            self.issues_found.append(f"Error checking Celery tasks: {e}")
    
    def check_crawl_velocity(self):
        """Check how many keywords are being crawled per hour"""
        one_hour_ago = timezone.now() - timedelta(hours=1)
        six_hours_ago = timezone.now() - timedelta(hours=6)
        one_day_ago = timezone.now() - timedelta(hours=24)
        
        # Count successful crawls
        crawls_1h = Keyword.objects.filter(
            scraped_at__gte=one_hour_ago
        ).count()
        
        crawls_6h = Keyword.objects.filter(
            scraped_at__gte=six_hours_ago
        ).count()
        
        crawls_24h = Keyword.objects.filter(
            scraped_at__gte=one_day_ago
        ).count()
        
        self.metrics['crawl_velocity'] = {
            'last_hour': crawls_1h,
            'last_6_hours': crawls_6h,
            'last_24_hours': crawls_24h,
            'per_hour_avg': crawls_24h / 24 if crawls_24h > 0 else 0
        }
        
        # Check if crawling has stopped
        if crawls_1h == 0:
            self.issues_found.append("CRITICAL: No keywords crawled in last hour!")
        elif crawls_1h < 10:
            self.issues_found.append(f"WARNING: Only {crawls_1h} keywords crawled in last hour")
    
    def check_error_rates(self):
        """Check for high error rates"""
        # Keywords with recent errors
        recent_errors = Keyword.objects.filter(
            last_error_message__isnull=False,
            updated_at__gte=timezone.now() - timedelta(hours=24)
        )
        
        error_count = recent_errors.count()
        
        if error_count > 0:
            # Group errors by message
            error_types = recent_errors.values('last_error_message').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            self.metrics['error_count'] = error_count
            self.metrics['top_errors'] = list(error_types)
            
            if error_count > 100:
                self.issues_found.append(f"High error rate: {error_count} errors in 24h")
    
    def generate_health_score(self):
        """Generate overall health score (0-100)"""
        score = 100
        
        # Deduct points for issues
        if self.metrics.get('stuck_keywords', 0) > 0:
            score -= min(30, self.metrics['stuck_keywords'])
        
        if self.metrics.get('overdue_48h', 0) > 100:
            score -= 20
        elif self.metrics.get('overdue_24h', 0) > 100:
            score -= 10
        
        if self.metrics.get('crawl_velocity', {}).get('last_hour', 0) == 0:
            score -= 40
        elif self.metrics.get('crawl_velocity', {}).get('last_hour', 0) < 10:
            score -= 20
        
        if self.metrics.get('error_count', 0) > 100:
            score -= 15
        
        # Project 7 specific
        p7_health = self.metrics.get('project_7', {}).get('health_percentage', 100)
        if p7_health < 50:
            score -= 20
        
        return max(0, score)
    
    def run_full_check(self):
        """Run all health checks"""
        print("\n" + "=" * 80)
        print(" CRAWLING HEALTH CHECK REPORT ")
        print("=" * 80)
        print(f"Time: {timezone.now()}")
        print("=" * 80)
        
        # Run all checks
        print("\n🔍 Running health checks...")
        
        self.check_stuck_keywords()
        self.check_crawl_freshness()
        self.check_project_7_specifically()
        self.check_celery_tasks()
        self.check_crawl_velocity()
        self.check_error_rates()
        
        # Calculate health score
        health_score = self.generate_health_score()
        
        # Display results
        print("\n📊 METRICS:")
        print("-" * 40)
        
        # Stuck keywords
        stuck = self.metrics.get('stuck_keywords', 0)
        print(f"Stuck Keywords: {stuck}")
        if stuck > 0:
            print(f"  Oldest stuck: {self.metrics.get('oldest_stuck_duration', 'Unknown')}")
        
        # Crawl freshness
        print(f"\nCrawl Freshness:")
        print(f"  Never crawled: {self.metrics.get('never_crawled', 0)}")
        print(f"  Overdue 24h+: {self.metrics.get('overdue_24h', 0)}")
        print(f"  Overdue 48h+: {self.metrics.get('overdue_48h', 0)}")
        print(f"  Recently crawled: {self.metrics.get('recently_crawled', 0)}")
        
        # Crawl velocity
        velocity = self.metrics.get('crawl_velocity', {})
        print(f"\nCrawl Velocity:")
        print(f"  Last hour: {velocity.get('last_hour', 0)}")
        print(f"  Last 6 hours: {velocity.get('last_6_hours', 0)}")
        print(f"  Last 24 hours: {velocity.get('last_24_hours', 0)}")
        print(f"  Average per hour: {velocity.get('per_hour_avg', 0):.1f}")
        
        # Project 7
        p7 = self.metrics.get('project_7', {})
        if p7:
            print(f"\nProject 7 Status:")
            print(f"  Total: {p7.get('total', 0)}")
            print(f"  Stuck: {p7.get('stuck', 0)}")
            print(f"  Needs crawl: {p7.get('needs_crawl', 0)}")
            print(f"  Recently crawled: {p7.get('recently_crawled', 0)}")
            print(f"  Health: {p7.get('health_percentage', 0):.1f}%")
        
        # Errors
        if self.metrics.get('error_count', 0) > 0:
            print(f"\nErrors (last 24h): {self.metrics['error_count']}")
            for error in self.metrics.get('top_errors', [])[:3]:
                print(f"  - {error['last_error_message'][:50]}: {error['count']}")
        
        # Issues found
        if self.issues_found:
            print("\n⚠️  ISSUES FOUND:")
            print("-" * 40)
            for issue in self.issues_found:
                print(f"  • {issue}")
        else:
            print("\n✅ No issues found!")
        
        # Health score
        print("\n" + "=" * 80)
        if health_score >= 80:
            status = "✅ HEALTHY"
            emoji = "🟢"
        elif health_score >= 60:
            status = "⚠️  DEGRADED"
            emoji = "🟡"
        else:
            status = "🚨 CRITICAL"
            emoji = "🔴"
        
        print(f"{emoji} OVERALL HEALTH SCORE: {health_score}/100 - {status}")
        print("=" * 80)
        
        return health_score
    
    def continuous_monitor(self, interval=300):
        """Run continuous monitoring every N seconds"""
        print("Starting continuous monitoring (Ctrl+C to stop)...")
        print(f"Checking every {interval} seconds")
        
        try:
            while True:
                score = self.run_full_check()
                
                # Save to log file
                log_entry = {
                    'timestamp': timezone.now().isoformat(),
                    'health_score': score,
                    'metrics': self.metrics,
                    'issues': self.issues_found
                }
                
                with open('crawling_health_log.jsonl', 'a') as f:
                    f.write(json.dumps(log_entry) + '\n')
                
                # Reset for next run
                self.issues_found = []
                self.metrics = {}
                
                print(f"\nNext check in {interval} seconds...")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped")
    
    def generate_detailed_report(self):
        """Generate detailed health report"""
        print("\n" + "📋" * 40)
        print(" DETAILED CRAWLING HEALTH REPORT ")
        print("📋" * 40)
        
        # Run checks
        self.run_full_check()
        
        # Additional detailed checks
        print("\n📈 DETAILED ANALYSIS:")
        print("=" * 80)
        
        # Project-by-project health
        print("\nProject Health Summary:")
        projects = Project.objects.filter(active=True)
        
        for project in projects[:10]:
            keywords = Keyword.objects.filter(project=project, archive=False)
            total = keywords.count()
            if total == 0:
                continue
            
            stuck = keywords.filter(processing=True).count()
            one_day_ago = timezone.now() - timedelta(hours=24)
            fresh = keywords.filter(scraped_at__gte=one_day_ago).count()
            
            health = (fresh * 100 / total) if total > 0 else 0
            status = "✅" if health > 70 else "⚠️" if health > 40 else "❌"
            
            print(f"  {status} {project.domain[:30]:30} - {fresh}/{total} fresh ({health:.1f}%)")
            if stuck > 0:
                print(f"      ⚠️  {stuck} stuck keywords")
        
        # Recommendations
        print("\n💡 RECOMMENDATIONS:")
        print("=" * 80)
        
        if self.metrics.get('stuck_keywords', 0) > 0:
            print("• Run immediate_recovery.py to reset stuck keywords")
        
        if self.metrics.get('overdue_48h', 0) > 100:
            print("• Increase worker concurrency to handle backlog")
        
        if self.metrics.get('crawl_velocity', {}).get('last_hour', 0) < 10:
            print("• Check if Celery workers are running")
            print("• Verify Redis is operational")
        
        if self.metrics.get('error_count', 0) > 50:
            print("• Review error logs for API issues")
            print("• Check Scrape.do API quota")
        
        print("\n" + "=" * 80)
        print("Report generated at:", timezone.now())


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor keyword crawling health')
    parser.add_argument('--watch', action='store_true', help='Continuous monitoring mode')
    parser.add_argument('--report', action='store_true', help='Generate detailed report')
    parser.add_argument('--interval', type=int, default=300, help='Check interval in seconds')
    
    args = parser.parse_args()
    
    monitor = CrawlingHealthMonitor()
    
    if args.watch:
        monitor.continuous_monitor(args.interval)
    elif args.report:
        monitor.generate_detailed_report()
    else:
        monitor.run_full_check()


if __name__ == "__main__":
    main()