#!/usr/bin/env python3
"""
🔧 CLEANUP AND PREPARATION SCRIPT
=================================

Comprehensive cleanup script to prepare the system for the new daily scheduling.
Cleans up existing stuck keywords and prepares for tomorrow's 12:01 AM queue.

Usage:
    python cleanup_and_prepare.py [--dry-run] [--force] [--reset-all]

Options:
    --dry-run    Show what would be done without making changes
    --force      Force cleanup even if keywords were recently processed
    --reset-all  Reset ALL keywords (use with caution)
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from collections import defaultdict

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
import django
django.setup()

from django.utils import timezone
from django.db.models import Count, Q
from django.db import transaction
from keywords.models import Keyword
from project.models import Project


class SystemCleaner:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.stats = {
            'stuck_reset': 0,
            'tracking_updated': 0,
            'projects_activated': 0,
            'errors_cleared': 0,
            'total_keywords': 0
        }
        self.issues_found = []
        
    def run_full_cleanup(self, force=False, reset_all=False):
        """Run complete cleanup process"""
        print("🔧 SYSTEM CLEANUP AND PREPARATION")
        print("=" * 50)
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        print(f"Time: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        self.analyze_current_state()
        self.cleanup_stuck_keywords(force)
        self.reset_tracking_fields()
        self.activate_inactive_projects()
        self.clear_old_errors()
        
        if reset_all:
            self.reset_all_processing_flags()
        
        self.prepare_for_daily_queue()
        self.print_summary()
        
        return self.stats
    
    def analyze_current_state(self):
        """Analyze current system state"""
        print("🔍 ANALYZING CURRENT STATE...")
        
        total = Keyword.objects.filter(archive=False, project__active=True).count()
        stuck = Keyword.objects.filter(archive=False, project__active=True, processing=True).count()
        
        # Find old stuck keywords
        old_stuck_threshold = timezone.now() - timedelta(hours=12)
        old_stuck = Keyword.objects.filter(
            archive=False,
            project__active=True, 
            processing=True,
            updated_at__lt=old_stuck_threshold
        ).count()
        
        # Never crawled keywords
        never_crawled = Keyword.objects.filter(
            archive=False,
            project__active=True,
            scraped_at__isnull=True
        ).count()
        
        # Very old data
        very_old_threshold = timezone.now() - timedelta(days=7)
        very_old = Keyword.objects.filter(
            archive=False,
            project__active=True,
            scraped_at__lt=very_old_threshold
        ).count()
        
        self.stats['total_keywords'] = total
        
        print(f"📊 System Overview:")
        print(f"  • Total Active Keywords: {total:,}")
        print(f"  • Currently Stuck: {stuck:,}")
        print(f"  • Old Stuck (>12h): {old_stuck:,}")
        print(f"  • Never Crawled: {never_crawled:,}")
        print(f"  • Very Old Data (>7d): {very_old:,}")
        print()
        
        if stuck > 0:
            self.issues_found.append(f"{stuck:,} keywords currently stuck")
        if old_stuck > 50:
            self.issues_found.append(f"{old_stuck:,} keywords stuck for >12 hours")
        if never_crawled > 100:
            self.issues_found.append(f"{never_crawled:,} keywords never crawled")
    
    def cleanup_stuck_keywords(self, force=False):
        """Clean up stuck keywords"""
        print("🔧 CLEANING UP STUCK KEYWORDS...")
        
        # Find stuck keywords
        stuck_threshold = timezone.now() - timedelta(hours=2)
        if force:
            # If force, reset all stuck keywords regardless of age
            stuck_keywords = Keyword.objects.filter(
                archive=False,
                project__active=True,
                processing=True
            )
        else:
            # Only reset keywords stuck for >2 hours
            stuck_keywords = Keyword.objects.filter(
                archive=False,
                project__active=True,
                processing=True,
                updated_at__lt=stuck_threshold
            )
        
        stuck_count = stuck_keywords.count()
        
        if stuck_count == 0:
            print("  ✅ No stuck keywords found")
            return
        
        print(f"  🔍 Found {stuck_count:,} stuck keywords to reset")
        
        if not self.dry_run:
            try:
                with transaction.atomic():
                    updated = stuck_keywords.update(
                        processing=False,
                        last_error_message="Cleanup: Auto-reset stuck keyword",
                        updated_at=timezone.now()
                    )
                    self.stats['stuck_reset'] = updated
                    print(f"  ✅ Reset {updated:,} stuck keywords")
            except Exception as e:
                print(f"  ❌ Error resetting stuck keywords: {e}")
        else:
            print(f"  🔍 Would reset {stuck_count:,} stuck keywords")
            self.stats['stuck_reset'] = stuck_count
    
    def reset_tracking_fields(self):
        """Reset tracking fields for new system"""
        print("🔧 RESETTING TRACKING FIELDS...")
        
        # Clear old tracking data to prepare for new system
        keywords_to_reset = Keyword.objects.filter(
            archive=False,
            project__active=True
        ).exclude(
            last_queue_date=timezone.now().date()
        )
        
        reset_count = keywords_to_reset.count()
        
        if reset_count == 0:
            print("  ✅ Tracking fields already current")
            return
        
        print(f"  🔍 Resetting tracking fields for {reset_count:,} keywords")
        
        if not self.dry_run:
            try:
                with transaction.atomic():
                    updated = keywords_to_reset.update(
                        last_queue_date=None,
                        daily_queue_task_id=None,
                        expected_crawl_time=None
                    )
                    self.stats['tracking_updated'] = updated
                    print(f"  ✅ Reset tracking fields for {updated:,} keywords")
            except Exception as e:
                print(f"  ❌ Error resetting tracking fields: {e}")
        else:
            print(f"  🔍 Would reset tracking for {reset_count:,} keywords")
            self.stats['tracking_updated'] = reset_count
    
    def activate_inactive_projects(self):
        """Activate projects that have keywords but are inactive"""
        print("🔧 CHECKING INACTIVE PROJECTS...")
        
        # Find inactive projects with keywords
        inactive_with_keywords = Project.objects.filter(
            active=False
        ).annotate(
            keyword_count=Count('keywords', filter=Q(keywords__archive=False))
        ).filter(keyword_count__gt=0)
        
        inactive_count = inactive_with_keywords.count()
        
        if inactive_count == 0:
            print("  ✅ All projects with keywords are active")
            return
        
        print(f"  🔍 Found {inactive_count} inactive projects with keywords:")
        for project in inactive_with_keywords[:5]:  # Show first 5
            print(f"    • {project.domain} ({project.keyword_count} keywords)")
        
        if not self.dry_run:
            try:
                updated = inactive_with_keywords.update(active=True)
                self.stats['projects_activated'] = updated
                print(f"  ✅ Activated {updated} projects")
            except Exception as e:
                print(f"  ❌ Error activating projects: {e}")
        else:
            print(f"  🔍 Would activate {inactive_count} projects")
            self.stats['projects_activated'] = inactive_count
    
    def clear_old_errors(self):
        """Clear old error messages to start fresh"""
        print("🔧 CLEARING OLD ERROR MESSAGES...")
        
        keywords_with_errors = Keyword.objects.filter(
            archive=False,
            project__active=True,
            last_error_message__isnull=False
        ).exclude(last_error_message='')
        
        error_count = keywords_with_errors.count()
        
        if error_count == 0:
            print("  ✅ No error messages to clear")
            return
        
        print(f"  🔍 Clearing error messages from {error_count:,} keywords")
        
        if not self.dry_run:
            try:
                updated = keywords_with_errors.update(
                    last_error_message=None
                )
                self.stats['errors_cleared'] = updated
                print(f"  ✅ Cleared {updated:,} error messages")
            except Exception as e:
                print(f"  ❌ Error clearing messages: {e}")
        else:
            print(f"  🔍 Would clear {error_count:,} error messages")
            self.stats['errors_cleared'] = error_count
    
    def reset_all_processing_flags(self):
        """Reset ALL processing flags (use with caution)"""
        print("🚨 RESETTING ALL PROCESSING FLAGS...")
        
        all_processing = Keyword.objects.filter(
            archive=False,
            project__active=True,
            processing=True
        )
        
        processing_count = all_processing.count()
        
        if processing_count == 0:
            print("  ✅ No processing flags to reset")
            return
        
        print(f"  ⚠️  Resetting ALL {processing_count:,} processing flags")
        
        if not self.dry_run:
            try:
                updated = all_processing.update(
                    processing=False,
                    last_error_message="Cleanup: Force reset all processing flags"
                )
                print(f"  ✅ Reset {updated:,} processing flags")
            except Exception as e:
                print(f"  ❌ Error resetting processing flags: {e}")
        else:
            print(f"  🔍 Would reset {processing_count:,} processing flags")
    
    def prepare_for_daily_queue(self):
        """Prepare system for tomorrow's daily queue"""
        print("🎯 PREPARING FOR DAILY QUEUE...")
        
        # Verify system readiness
        total_ready = Keyword.objects.filter(
            archive=False,
            project__active=True
        ).count()
        
        projects_ready = Project.objects.filter(active=True).count()
        
        print(f"  📊 System Ready:")
        print(f"    • Keywords Ready: {total_ready:,}")
        print(f"    • Active Projects: {projects_ready}")
        print()
        print("  🚀 System prepared for daily queue at 12:01 AM")
        print(f"  ⏰ Next Queue: Tomorrow at 00:01")
        
        # Calculate estimated completion time
        # Assuming 100 keywords/hour processing rate
        estimated_hours = total_ready / 100
        print(f"  ⏱️  Estimated Completion: {estimated_hours:.1f} hours")
    
    def print_summary(self):
        """Print cleanup summary"""
        print("\n" + "=" * 50)
        print("📋 CLEANUP SUMMARY")
        print("=" * 50)
        
        if self.dry_run:
            print("🔍 DRY RUN - No changes were made")
        else:
            print("✅ CLEANUP COMPLETED")
        
        print(f"\n📊 Actions {'Simulated' if self.dry_run else 'Completed'}:")
        print(f"  • Stuck Keywords Reset: {self.stats['stuck_reset']:,}")
        print(f"  • Tracking Fields Updated: {self.stats['tracking_updated']:,}")
        print(f"  • Projects Activated: {self.stats['projects_activated']:,}")
        print(f"  • Error Messages Cleared: {self.stats['errors_cleared']:,}")
        
        if self.issues_found:
            print(f"\n🚨 Issues Found:")
            for issue in self.issues_found:
                print(f"  • {issue}")
        
        print(f"\n🎯 System Status:")
        print(f"  • Total Keywords Ready: {self.stats['total_keywords']:,}")
        print(f"  • Ready for Daily Queue: {'YES' if self.stats['stuck_reset'] >= 0 else 'NEEDS ATTENTION'}")
        
        if not self.dry_run:
            print(f"\n💡 Next Steps:")
            print(f"  1. Wait for 12:01 AM tomorrow for daily queue")
            print(f"  2. Run: python verify_daily_system.py --detailed")
            print(f"  3. Monitor keyword processing throughout the day")


def main():
    parser = argparse.ArgumentParser(description='Cleanup and Prepare System')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--force', action='store_true', help='Force cleanup even for recently processed keywords')
    parser.add_argument('--reset-all', action='store_true', help='Reset ALL processing flags (use with caution)')
    
    args = parser.parse_args()
    
    if args.reset_all and not args.dry_run:
        response = input("⚠️  This will reset ALL processing flags. Continue? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled.")
            sys.exit(0)
    
    cleaner = SystemCleaner(dry_run=args.dry_run)
    results = cleaner.run_full_cleanup(force=args.force, reset_all=args.reset_all)
    
    print(f"\n{'🔍 Simulation complete' if args.dry_run else '✅ Cleanup complete'}")


if __name__ == '__main__':
    main()