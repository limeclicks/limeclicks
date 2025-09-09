#!/usr/bin/env python
"""
IMMEDIATE RECOVERY SCRIPT FOR PRODUCTION
Run this NOW on production to fix stuck keywords and restore crawling

Usage:
    python immediate_recovery.py --dry-run    # Test mode (no changes)
    python immediate_recovery.py --apply       # Apply fixes
    python immediate_recovery.py --project 7   # Fix specific project
"""

import os
import sys
import django
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction, connection

# Setup Django
os.environ['DATABASE_URL'] = 'postgresql://postgres:LimeClicksPwd007@localhost:5432/lime'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from keywords.models import Keyword
from project.models import Project
from django.db.models import Q, Count


def print_header(title):
    """Print formatted header"""
    print("\n" + "=" * 80)
    print(f" {title} ")
    print("=" * 80)


def reset_all_stuck_keywords(dry_run=True):
    """Reset ALL keywords with processing=True flag"""
    print_header("RESETTING STUCK PROCESSING FLAGS")
    
    stuck_keywords = Keyword.objects.filter(processing=True)
    count = stuck_keywords.count()
    
    if count == 0:
        print("✓ No stuck keywords found")
        return 0
    
    print(f"Found {count} keywords with processing=True")
    
    # Show breakdown by project
    by_project = stuck_keywords.values('project__id', 'project__domain').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    print("\nTop affected projects:")
    for proj in by_project:
        print(f"  - Project {proj['project__id']} ({proj['project__domain']}): {proj['count']} keywords")
    
    if not dry_run:
        with transaction.atomic():
            reset_count = stuck_keywords.update(
                processing=False,
                updated_at=timezone.now()
            )
            print(f"\n✓ Reset {reset_count} keywords")
    else:
        print(f"\n[DRY RUN] Would reset {count} keywords")
    
    return count


def fix_null_next_crawl_at(dry_run=True):
    """Fix keywords with NULL next_crawl_at"""
    print_header("FIXING NULL NEXT_CRAWL_AT")
    
    null_keywords = Keyword.objects.filter(
        next_crawl_at__isnull=True,
        archive=False
    )
    count = null_keywords.count()
    
    if count == 0:
        print("✓ No keywords with NULL next_crawl_at")
        return 0
    
    print(f"Found {count} keywords with NULL next_crawl_at")
    
    if not dry_run:
        with transaction.atomic():
            fixed_count = null_keywords.update(
                next_crawl_at=timezone.now(),
                updated_at=timezone.now()
            )
            print(f"✓ Fixed {fixed_count} keywords")
    else:
        print(f"[DRY RUN] Would fix {count} keywords")
    
    return count


def reset_old_stuck_keywords(dry_run=True):
    """Reset keywords that have been stuck for >24 hours"""
    print_header("RESETTING OLD STUCK KEYWORDS")
    
    one_day_ago = timezone.now() - timedelta(hours=24)
    
    old_stuck = Keyword.objects.filter(
        processing=True,
        scraped_at__lt=one_day_ago
    )
    count = old_stuck.count()
    
    if count == 0:
        print("✓ No old stuck keywords found")
        return 0
    
    print(f"Found {count} keywords stuck for >24 hours")
    
    if not dry_run:
        with transaction.atomic():
            reset_count = old_stuck.update(
                processing=False,
                next_crawl_at=timezone.now(),
                updated_at=timezone.now()
            )
            print(f"✓ Reset {reset_count} old stuck keywords")
    else:
        print(f"[DRY RUN] Would reset {count} keywords")
    
    return count


def fix_specific_project(project_id, dry_run=True):
    """Fix all issues for a specific project"""
    print_header(f"FIXING PROJECT {project_id}")
    
    try:
        project = Project.objects.get(id=project_id)
        print(f"Project: {project.domain}")
        
        # Ensure project is active
        if not project.active:
            if not dry_run:
                project.active = True
                project.save()
                print("✓ Activated project")
            else:
                print("[DRY RUN] Would activate project")
        
        # Get all keywords
        keywords = Keyword.objects.filter(project_id=project_id, archive=False)
        total = keywords.count()
        print(f"Total active keywords: {total}")
        
        # Reset processing flags
        stuck = keywords.filter(processing=True).count()
        if stuck > 0:
            if not dry_run:
                reset = keywords.filter(processing=True).update(
                    processing=False,
                    updated_at=timezone.now()
                )
                print(f"✓ Reset {reset} stuck keywords")
            else:
                print(f"[DRY RUN] Would reset {stuck} stuck keywords")
        
        # Fix NULL next_crawl_at
        null_next = keywords.filter(next_crawl_at__isnull=True).count()
        if null_next > 0:
            if not dry_run:
                fixed = keywords.filter(next_crawl_at__isnull=True).update(
                    next_crawl_at=timezone.now(),
                    updated_at=timezone.now()
                )
                print(f"✓ Fixed {fixed} NULL next_crawl_at")
            else:
                print(f"[DRY RUN] Would fix {null_next} NULL next_crawl_at")
        
        # Force immediate crawl for overdue keywords
        one_day_ago = timezone.now() - timedelta(hours=24)
        overdue = keywords.filter(
            Q(scraped_at__isnull=True) | Q(scraped_at__lt=one_day_ago)
        ).count()
        
        if overdue > 0:
            if not dry_run:
                # Mark first 50 for immediate crawl
                immediate = keywords.filter(
                    Q(scraped_at__isnull=True) | Q(scraped_at__lt=one_day_ago)
                )[:50]
                
                for kw in immediate:
                    kw.processing = True
                    kw.crawl_priority = 'high'
                    kw.save()
                
                print(f"✓ Marked {len(immediate)} keywords for immediate crawl")
                
                # Import and queue tasks
                from keywords.tasks import fetch_keyword_serp_html
                
                for kw in immediate:
                    fetch_keyword_serp_html.apply_async(
                        args=[kw.id],
                        queue='serp_high',
                        priority=10
                    )
                
                print(f"✓ Queued {len(immediate)} tasks")
            else:
                print(f"[DRY RUN] Would queue {min(50, overdue)} overdue keywords")
        
        print(f"\n✓ Project {project_id} recovery complete")
        
    except Project.DoesNotExist:
        print(f"✗ Project {project_id} not found")
        return False
    
    return True


def activate_all_projects(dry_run=True):
    """Activate all inactive projects with keywords"""
    print_header("ACTIVATING INACTIVE PROJECTS")
    
    inactive = Project.objects.filter(
        active=False,
        keyword__isnull=False
    ).distinct()
    
    count = inactive.count()
    
    if count == 0:
        print("✓ No inactive projects with keywords")
        return 0
    
    print(f"Found {count} inactive projects with keywords")
    
    for proj in inactive[:10]:
        keyword_count = Keyword.objects.filter(project=proj, archive=False).count()
        print(f"  - {proj.domain}: {keyword_count} keywords")
    
    if not dry_run:
        activated = inactive.update(active=True)
        print(f"\n✓ Activated {activated} projects")
    else:
        print(f"\n[DRY RUN] Would activate {count} projects")
    
    return count


def queue_overdue_keywords(limit=100, dry_run=True):
    """Queue overdue keywords for immediate crawling"""
    print_header("QUEUEING OVERDUE KEYWORDS")
    
    one_day_ago = timezone.now() - timedelta(hours=24)
    
    overdue = Keyword.objects.filter(
        Q(scraped_at__isnull=True) | Q(scraped_at__lt=one_day_ago),
        processing=False,
        archive=False,
        project__active=True
    )[:limit]
    
    count = len(overdue)
    
    if count == 0:
        print("✓ No overdue keywords to queue")
        return 0
    
    print(f"Found {count} overdue keywords to queue")
    
    if not dry_run:
        from keywords.tasks import fetch_keyword_serp_html
        
        queued = 0
        for keyword in overdue:
            keyword.processing = True
            keyword.save(update_fields=['processing'])
            
            fetch_keyword_serp_html.apply_async(
                args=[keyword.id],
                queue='serp_high',
                priority=10
            )
            queued += 1
        
        print(f"✓ Queued {queued} keywords for immediate crawl")
    else:
        print(f"[DRY RUN] Would queue {count} keywords")
    
    return count


def show_current_status():
    """Show current system status"""
    print_header("CURRENT SYSTEM STATUS")
    
    total_keywords = Keyword.objects.filter(archive=False).count()
    stuck_count = Keyword.objects.filter(processing=True).count()
    null_next = Keyword.objects.filter(next_crawl_at__isnull=True, archive=False).count()
    
    one_day_ago = timezone.now() - timedelta(hours=24)
    needs_crawl = Keyword.objects.filter(
        Q(scraped_at__isnull=True) | Q(scraped_at__lt=one_day_ago),
        archive=False,
        project__active=True
    ).count()
    
    never_crawled = Keyword.objects.filter(scraped_at__isnull=True, archive=False).count()
    
    print(f"Total active keywords: {total_keywords}")
    print(f"Stuck (processing=True): {stuck_count} ({stuck_count*100/total_keywords:.1f}%)")
    print(f"NULL next_crawl_at: {null_next}")
    print(f"Never crawled: {never_crawled}")
    print(f"Needs crawl (>24h): {needs_crawl}")
    
    # Check Project 7 specifically
    p7_keywords = Keyword.objects.filter(project_id=7, archive=False)
    if p7_keywords.exists():
        p7_total = p7_keywords.count()
        p7_stuck = p7_keywords.filter(processing=True).count()
        p7_needs = p7_keywords.filter(
            Q(scraped_at__isnull=True) | Q(scraped_at__lt=one_day_ago)
        ).count()
        
        print(f"\nProject 7 Status:")
        print(f"  Total: {p7_total}")
        print(f"  Stuck: {p7_stuck}")
        print(f"  Needs crawl: {p7_needs}")


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Immediate recovery for keyword crawling')
    parser.add_argument('--dry-run', action='store_true', help='Test mode - no changes')
    parser.add_argument('--apply', action='store_true', help='Apply all fixes')
    parser.add_argument('--project', type=int, help='Fix specific project')
    parser.add_argument('--status', action='store_true', help='Show status only')
    
    args = parser.parse_args()
    
    print("\n" + "🚨" * 40)
    print(" IMMEDIATE RECOVERY SCRIPT ")
    print("🚨" * 40)
    print(f"Time: {timezone.now()}")
    
    # Default to dry run if no action specified
    if not args.apply and not args.status:
        args.dry_run = True
    
    # Show current status
    show_current_status()
    
    if args.status:
        return
    
    # Determine mode
    dry_run = not args.apply
    mode = "[DRY RUN]" if dry_run else "[APPLYING FIXES]"
    
    print(f"\n{mode}")
    
    # Apply fixes
    fixes_applied = []
    
    # 1. Reset all stuck keywords
    count = reset_all_stuck_keywords(dry_run)
    if count > 0:
        fixes_applied.append(f"Reset {count} stuck keywords")
    
    # 2. Fix NULL next_crawl_at
    count = fix_null_next_crawl_at(dry_run)
    if count > 0:
        fixes_applied.append(f"Fixed {count} NULL next_crawl_at")
    
    # 3. Reset old stuck keywords
    count = reset_old_stuck_keywords(dry_run)
    if count > 0:
        fixes_applied.append(f"Reset {count} old stuck keywords")
    
    # 4. Activate inactive projects
    count = activate_all_projects(dry_run)
    if count > 0:
        fixes_applied.append(f"Activated {count} projects")
    
    # 5. Fix specific project if requested
    if args.project:
        if fix_specific_project(args.project, dry_run):
            fixes_applied.append(f"Fixed Project {args.project}")
    
    # 6. Queue overdue keywords (only if applying)
    if not dry_run:
        count = queue_overdue_keywords(limit=100, dry_run=False)
        if count > 0:
            fixes_applied.append(f"Queued {count} keywords")
    
    # Summary
    print_header("RECOVERY SUMMARY")
    
    if fixes_applied:
        print("Fixes applied:")
        for fix in fixes_applied:
            print(f"  ✓ {fix}")
    else:
        print("No fixes needed or applied")
    
    if dry_run:
        print("\n⚠️  This was a DRY RUN - no changes were made")
        print("Run with --apply to apply fixes")
    else:
        print("\n✅ Recovery complete - monitor for 1 hour to verify")
    
    # Show final status if changes were applied
    if not dry_run:
        print("\n" + "=" * 80)
        show_current_status()


if __name__ == "__main__":
    main()