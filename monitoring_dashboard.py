#!/usr/bin/env python3
"""
📊 REAL-TIME MONITORING DASHBOARD
================================

Live monitoring dashboard for the daily keyword scheduling system.
Shows real-time progress, statistics, and system health.

Usage:
    python monitoring_dashboard.py [--refresh SECONDS] [--compact]

Options:
    --refresh SECONDS    Refresh interval (default: 30 seconds)
    --compact           Compact display mode
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
from django.db.models import Count, Q, Avg
from keywords.models import Keyword
from project.models import Project
from celery import current_app


class MonitoringDashboard:
    def __init__(self, refresh_interval=30, compact=False):
        self.refresh_interval = refresh_interval
        self.compact = compact
        self.start_time = timezone.now()
    
    def run_dashboard(self):
        """Run the live monitoring dashboard"""
        try:
            while True:
                self.clear_screen()
                self.display_header()
                self.display_system_overview()
                
                if not self.compact:
                    self.display_processing_progress()
                    self.display_project_breakdown()
                    self.display_celery_status()
                    self.display_recent_activity()
                
                self.display_footer()
                
                # Wait for refresh or allow keyboard interrupt
                try:
                    time.sleep(self.refresh_interval)
                except KeyboardInterrupt:
                    print("\n\n👋 Monitoring stopped by user")
                    break
                    
        except Exception as e:
            print(f"\n❌ Dashboard error: {e}")
            sys.exit(1)
    
    def clear_screen(self):
        """Clear the terminal screen"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def display_header(self):
        """Display dashboard header"""
        now = timezone.now()
        uptime = now - self.start_time
        
        print("📊 LIMECLICKS KEYWORD MONITORING DASHBOARD")
        print("=" * 60)
        print(f"Time: {now.strftime('%Y-%m-%d %H:%M:%S')} | Uptime: {self.format_duration(uptime)}")
        print(f"Refresh: {self.refresh_interval}s | Mode: {'Compact' if self.compact else 'Full'}")
        print()
    
    def display_system_overview(self):
        """Display high-level system statistics"""
        today = timezone.now().date()
        now = timezone.now()
        
        # Core statistics
        total_keywords = Keyword.objects.filter(archive=False, project__active=True).count()
        queued_today = Keyword.objects.filter(
            archive=False,
            project__active=True,
            last_queue_date=today
        ).count()
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
        
        # Calculate rates
        queue_rate = (queued_today / total_keywords * 100) if total_keywords > 0 else 0
        processing_rate = (processed_today / total_keywords * 100) if total_keywords > 0 else 0
        
        # Time calculations
        midnight = now.replace(hour=0, minute=1, second=0, microsecond=0)
        if now >= midnight:
            hours_since_queue = (now - midnight).total_seconds() / 3600
        else:
            # Before midnight - show time until next queue
            next_midnight = midnight + timedelta(days=1)
            hours_until_queue = (next_midnight - now).total_seconds() / 3600
            hours_since_queue = 0
        
        print("🎯 SYSTEM OVERVIEW")
        print("-" * 30)
        print(f"Total Keywords: {total_keywords:,}")
        print(f"Queued Today:   {queued_today:,} ({queue_rate:.1f}%)")
        print(f"Processed:      {processed_today:,} ({processing_rate:.1f}%)")
        print(f"Stuck:          {stuck_keywords:,}")
        
        if hours_since_queue > 0:
            processing_speed = processed_today / hours_since_queue if hours_since_queue > 0 else 0
            remaining = total_keywords - processed_today
            eta_hours = remaining / processing_speed if processing_speed > 0 else 0
            
            print(f"Speed:          {processing_speed:.1f} keywords/hour")
            if eta_hours > 0 and eta_hours < 24:
                print(f"ETA Complete:   {eta_hours:.1f} hours")
        else:
            print(f"Next Queue:     {hours_until_queue:.1f} hours")
        
        # Status indicator
        status = self.get_system_status(queue_rate, processing_rate, stuck_keywords)
        status_emoji = {'HEALTHY': '✅', 'WARNING': '⚠️', 'CRITICAL': '❌'}
        print(f"Status:         {status_emoji[status]} {status}")
        print()
    
    def display_processing_progress(self):
        """Display detailed processing progress"""
        today = timezone.now().date()
        
        # Hourly breakdown
        hourly_stats = []
        for hour in range(24):
            hour_start = timezone.now().replace(hour=hour, minute=0, second=0, microsecond=0)
            hour_end = hour_start + timedelta(hours=1)
            
            if hour_start.date() == today:
                processed_hour = Keyword.objects.filter(
                    archive=False,
                    project__active=True,
                    scraped_at__range=(hour_start, hour_end)
                ).count()
                hourly_stats.append(processed_hour)
            else:
                hourly_stats.append(0)
        
        current_hour = timezone.now().hour
        
        print("⏰ HOURLY PROCESSING BREAKDOWN")
        print("-" * 30)
        
        # Show bars for last 12 hours and next 12 hours
        start_hour = max(0, current_hour - 6)
        end_hour = min(24, current_hour + 6)
        
        for hour in range(start_hour, end_hour):
            count = hourly_stats[hour]
            bar_length = min(20, count // 5) if count > 0 else 0
            bar = "█" * bar_length + "░" * (20 - bar_length)
            
            marker = " ←" if hour == current_hour else ""
            print(f"{hour:2d}:00 [{bar}] {count:3d}{marker}")
        
        print()
    
    def display_project_breakdown(self):
        """Display per-project statistics"""
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
        ).order_by('-total_keywords')[:8]  # Top 8 projects
        
        print("📈 PROJECT BREAKDOWN (Top 8)")
        print("-" * 50)
        print(f"{'Project':<20} {'Total':<8} {'Done':<8} {'Rate':<8} {'Stuck':<6}")
        print("-" * 50)
        
        for project in projects:
            rate = (project.processed_today / project.total_keywords * 100) if project.total_keywords > 0 else 0
            status = "✅" if rate > 50 else "⚠️" if rate > 10 else "❌"
            
            domain = project.domain[:18] + ".." if len(project.domain) > 20 else project.domain
            print(f"{domain:<20} {project.total_keywords:<8} {project.processed_today:<8} {rate:5.1f}%  {project.stuck_keywords:<6} {status}")
        
        print()
    
    def display_celery_status(self):
        """Display Celery worker status"""
        try:
            i = current_app.control.inspect()
            stats = i.stats()
            active = i.active()
            reserved = i.reserved()
            
            if not stats:
                print("❌ CELERY STATUS: No workers detected")
                print()
                return
            
            total_workers = len(stats)
            total_active = sum(len(tasks) for tasks in active.values()) if active else 0
            total_reserved = sum(len(tasks) for tasks in reserved.values()) if reserved else 0
            
            print("⚙️ CELERY WORKER STATUS")
            print("-" * 30)
            print(f"Workers:        {total_workers}")
            print(f"Active Tasks:   {total_active}")
            print(f"Reserved:       {total_reserved}")
            
            # Show individual workers
            for worker_name, worker_stats in stats.items():
                worker_active = len(active.get(worker_name, []))
                worker_reserved = len(reserved.get(worker_name, []))
                
                print(f"  {worker_name}: {worker_active} active, {worker_reserved} reserved")
            
            print()
            
        except Exception as e:
            print(f"❌ CELERY STATUS: Error - {e}")
            print()
    
    def display_recent_activity(self):
        """Display recent processing activity"""
        # Recent successes (last 10 minutes)
        recent_threshold = timezone.now() - timedelta(minutes=10)
        recent_processed = Keyword.objects.filter(
            archive=False,
            project__active=True,
            scraped_at__gte=recent_threshold
        ).order_by('-scraped_at')[:5]
        
        print("🔄 RECENT ACTIVITY (Last 10 minutes)")
        print("-" * 40)
        
        if recent_processed.exists():
            for keyword in recent_processed:
                time_ago = timezone.now() - keyword.scraped_at
                minutes_ago = int(time_ago.total_seconds() / 60)
                
                rank_display = f"#{keyword.rank}" if keyword.rank and keyword.rank <= 100 else "NR"
                project_short = keyword.project.domain[:15]
                keyword_short = keyword.keyword[:20]
                
                print(f"  {minutes_ago:2d}m ago: {keyword_short:<20} {project_short:<15} {rank_display}")
        else:
            print("  No recent activity")
        
        print()
    
    def display_footer(self):
        """Display dashboard footer"""
        print("-" * 60)
        print("Commands: Ctrl+C to exit | Auto-refresh every", f"{self.refresh_interval}s")
    
    def get_system_status(self, queue_rate, processing_rate, stuck_count):
        """Determine overall system status"""
        if stuck_count > 100:
            return 'CRITICAL'
        elif processing_rate > 80 or (queue_rate > 95 and processing_rate > 20):
            return 'HEALTHY'
        elif processing_rate > 10 or queue_rate > 50:
            return 'WARNING'
        else:
            return 'CRITICAL'
    
    def format_duration(self, duration):
        """Format duration as human readable"""
        total_seconds = int(duration.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"


class SimpleMonitor:
    """Simplified one-shot monitor for quick checks"""
    
    @staticmethod
    def quick_status():
        """Display quick system status"""
        today = timezone.now().date()
        
        total = Keyword.objects.filter(archive=False, project__active=True).count()
        processed = Keyword.objects.filter(
            archive=False,
            project__active=True,
            scraped_at__date=today
        ).count()
        stuck = Keyword.objects.filter(
            archive=False,
            project__active=True,
            processing=True
        ).count()
        
        rate = (processed / total * 100) if total > 0 else 0
        
        print(f"📊 Quick Status: {processed:,}/{total:,} processed ({rate:.1f}%), {stuck:,} stuck")
        
        if rate > 80:
            print("✅ System healthy")
        elif rate > 20:
            print("⚠️ System progressing")  
        else:
            print("❌ System needs attention")


def main():
    parser = argparse.ArgumentParser(description='Keyword Processing Monitor')
    parser.add_argument('--refresh', type=int, default=30, help='Refresh interval in seconds')
    parser.add_argument('--compact', action='store_true', help='Compact display mode')
    parser.add_argument('--quick', action='store_true', help='Quick status check only')
    
    args = parser.parse_args()
    
    if args.quick:
        SimpleMonitor.quick_status()
    else:
        dashboard = MonitoringDashboard(
            refresh_interval=args.refresh,
            compact=args.compact
        )
        dashboard.run_dashboard()


if __name__ == '__main__':
    main()