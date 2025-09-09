#!/usr/bin/env python
"""
Comprehensive diagnostic and permanent fix for keyword crawling issues
This script will:
1. Diagnose crawling issues across ALL projects
2. Identify root causes
3. Apply immediate fixes
4. Suggest permanent code changes
"""

import os
import sys
import django
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Count, Min, Max
from django.db import connection, transaction

# Setup Django environment
os.environ['DATABASE_URL'] = 'postgresql://postgres:LimeClicksPwd007@localhost:5432/lime'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from keywords.models import Keyword
from project.models import Project

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f" {title} ")
    print("=" * 80)

def diagnose_all_projects():
    """Comprehensive diagnosis of ALL projects with keyword crawling issues"""
    
    print_section("SYSTEM-WIDE KEYWORD CRAWLING DIAGNOSIS")
    print(f"Current Time: {timezone.now()}")
    print(f"24 hours ago: {timezone.now() - timedelta(hours=24)}")
    
    # Get overall statistics
    total_keywords = Keyword.objects.filter(archive=False).count()
    total_projects = Project.objects.filter(active=True).count()
    
    print(f"\n📊 OVERALL STATISTICS:")
    print(f"  - Total active projects: {total_projects}")
    print(f"  - Total active keywords: {total_keywords}")
    
    # Check stuck processing flags across all projects
    stuck_processing = Keyword.objects.filter(processing=True, archive=False)
    stuck_count = stuck_processing.count()
    
    print_section("STUCK KEYWORDS (processing=True)")
    print(f"Total stuck keywords: {stuck_count}")
    
    if stuck_count > 0:
        # Group by project
        stuck_by_project = stuck_processing.values('project__domain').annotate(
            count=Count('id'),
            oldest_stuck=Min('updated_at'),
            newest_stuck=Max('updated_at')
        ).order_by('-count')[:10]
        
        print(f"\nTop projects with stuck keywords:")
        for proj in stuck_by_project:
            oldest_time = timezone.now() - proj['oldest_stuck'] if proj['oldest_stuck'] else "Unknown"
            print(f"  - {proj['project__domain']}: {proj['count']} stuck (oldest: {oldest_time})")
    
    # Check keywords needing crawl
    one_day_ago = timezone.now() - timedelta(hours=24)
    needs_crawl = Keyword.objects.filter(
        Q(scraped_at__isnull=True) | Q(scraped_at__lt=one_day_ago),
        processing=False,
        archive=False,
        project__active=True
    )
    needs_crawl_count = needs_crawl.count()
    
    print_section("KEYWORDS NEEDING CRAWL")
    print(f"Total keywords needing crawl (24+ hours old): {needs_crawl_count}")
    
    if needs_crawl_count > 0:
        # Group by age
        never_crawled = needs_crawl.filter(scraped_at__isnull=True).count()
        one_day_old = needs_crawl.filter(scraped_at__lt=one_day_ago, scraped_at__gte=timezone.now() - timedelta(days=2)).count()
        two_days_old = needs_crawl.filter(scraped_at__lt=timezone.now() - timedelta(days=2), scraped_at__gte=timezone.now() - timedelta(days=7)).count()
        week_old = needs_crawl.filter(scraped_at__lt=timezone.now() - timedelta(days=7)).count()
        
        print(f"\nAge distribution:")
        print(f"  - Never crawled: {never_crawled}")
        print(f"  - 24-48 hours old: {one_day_old}")
        print(f"  - 2-7 days old: {two_days_old}")
        print(f"  - Over 1 week old: {week_old}")
        
        # Top projects needing crawls
        needs_by_project = needs_crawl.values('project__id', 'project__domain').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        print(f"\nTop projects needing crawls:")
        for proj in needs_by_project:
            print(f"  - Project {proj['project__id']} ({proj['project__domain']}): {proj['count']} keywords")
    
    # Check next_crawl_at issues
    print_section("NEXT_CRAWL_AT FIELD ISSUES")
    
    null_next_crawl = Keyword.objects.filter(next_crawl_at__isnull=True, archive=False).count()
    past_due = Keyword.objects.filter(next_crawl_at__lt=timezone.now(), processing=False, archive=False).count()
    
    print(f"  - Keywords with NULL next_crawl_at: {null_next_crawl}")
    print(f"  - Keywords past due (next_crawl_at < now): {past_due}")
    
    # Check for specific Project 7
    print_section("PROJECT 7 SPECIFIC DIAGNOSIS")
    
    try:
        project_7 = Project.objects.get(id=7)
        p7_keywords = Keyword.objects.filter(project_id=7, archive=False)
        p7_total = p7_keywords.count()
        p7_stuck = p7_keywords.filter(processing=True).count()
        p7_needs_crawl = p7_keywords.filter(
            Q(scraped_at__isnull=True) | Q(scraped_at__lt=one_day_ago)
        ).exclude(processing=True).count()
        
        print(f"Domain: {project_7.domain}")
        print(f"  - Total keywords: {p7_total}")
        print(f"  - Stuck processing: {p7_stuck}")
        print(f"  - Needs crawl: {p7_needs_crawl}")
        
        # Sample keywords
        sample_keywords = p7_keywords.order_by('scraped_at')[:5]
        print(f"\nSample keywords (oldest scraped first):")
        for kw in sample_keywords:
            age = timezone.now() - kw.scraped_at if kw.scraped_at else "Never crawled"
            print(f"  - {kw.keyword}: last scraped {age}, processing={kw.processing}")
    except Project.DoesNotExist:
        print("Project 7 not found")
    
    # Identify root causes
    print_section("ROOT CAUSE ANALYSIS")
    
    causes = []
    
    if stuck_count > 0:
        causes.append(f"1. {stuck_count} keywords stuck with processing=True flag")
    
    if null_next_crawl > 0:
        causes.append(f"2. {null_next_crawl} keywords have NULL next_crawl_at")
    
    if needs_crawl_count > 1000:
        causes.append(f"3. Large backlog of {needs_crawl_count} keywords needs processing")
    
    # Check if cleanup tasks are working
    two_hours_ago = timezone.now() - timedelta(hours=2)
    very_stuck = Keyword.objects.filter(
        processing=True,
        updated_at__lt=two_hours_ago,
        archive=False
    ).count()
    
    if very_stuck > 0:
        causes.append(f"4. Cleanup task not working: {very_stuck} keywords stuck for 2+ hours")
    
    if causes:
        print("Identified issues:")
        for cause in causes:
            print(f"  {cause}")
    else:
        print("No obvious issues found")
    
    return {
        'stuck_count': stuck_count,
        'needs_crawl_count': needs_crawl_count,
        'null_next_crawl': null_next_crawl,
        'past_due': past_due,
        'very_stuck': very_stuck
    }

def apply_immediate_fixes(dry_run=True):
    """Apply immediate fixes to get crawling working again"""
    
    print_section("APPLYING IMMEDIATE FIXES")
    
    fixes_applied = []
    
    # Fix 1: Reset all stuck processing flags
    stuck_keywords = Keyword.objects.filter(processing=True, archive=False)
    stuck_count = stuck_keywords.count()
    
    if stuck_count > 0:
        print(f"\n🔧 Fix 1: Resetting {stuck_count} stuck processing flags...")
        if not dry_run:
            with transaction.atomic():
                updated = stuck_keywords.update(processing=False, updated_at=timezone.now())
                fixes_applied.append(f"Reset {updated} processing flags")
                print(f"  ✓ Reset {updated} keywords")
        else:
            print(f"  [DRY RUN] Would reset {stuck_count} keywords")
    
    # Fix 2: Set next_crawl_at for keywords with NULL
    null_next = Keyword.objects.filter(next_crawl_at__isnull=True, archive=False)
    null_count = null_next.count()
    
    if null_count > 0:
        print(f"\n🔧 Fix 2: Setting next_crawl_at for {null_count} keywords...")
        if not dry_run:
            with transaction.atomic():
                updated = null_next.update(next_crawl_at=timezone.now())
                fixes_applied.append(f"Set next_crawl_at for {updated} keywords")
                print(f"  ✓ Updated {updated} keywords")
        else:
            print(f"  [DRY RUN] Would update {null_count} keywords")
    
    # Fix 3: Force keywords that haven't been crawled in 24+ hours to be eligible
    one_day_ago = timezone.now() - timedelta(hours=24)
    old_keywords = Keyword.objects.filter(
        scraped_at__lt=one_day_ago,
        processing=True,  # Only reset if stuck
        archive=False
    )
    old_count = old_keywords.count()
    
    if old_count > 0:
        print(f"\n🔧 Fix 3: Resetting {old_count} old stuck keywords...")
        if not dry_run:
            with transaction.atomic():
                updated = old_keywords.update(
                    processing=False,
                    next_crawl_at=timezone.now()
                )
                fixes_applied.append(f"Reset {old_count} old stuck keywords")
                print(f"  ✓ Reset {old_count} keywords")
        else:
            print(f"  [DRY RUN] Would reset {old_count} keywords")
    
    # Fix 4: Specifically fix Project 7
    p7_keywords = Keyword.objects.filter(project_id=7, archive=False)
    p7_stuck = p7_keywords.filter(processing=True).count()
    
    if p7_stuck > 0:
        print(f"\n🔧 Fix 4: Specifically fixing Project 7 ({p7_stuck} stuck)...")
        if not dry_run:
            with transaction.atomic():
                updated = p7_keywords.filter(processing=True).update(
                    processing=False,
                    next_crawl_at=timezone.now()
                )
                fixes_applied.append(f"Fixed {updated} Project 7 keywords")
                print(f"  ✓ Fixed {updated} Project 7 keywords")
        else:
            print(f"  [DRY RUN] Would fix {p7_stuck} Project 7 keywords")
    
    return fixes_applied

def create_permanent_fix():
    """Generate the permanent fix code"""
    
    print_section("PERMANENT FIX RECOMMENDATIONS")
    
    print("""
The permanent fix requires updating the following files:

1. **keywords/tasks.py** - Update the fetch_keyword_serp_html task:
   - Add timeout handling
   - Ensure processing flag is ALWAYS reset on failure
   - Add transaction safety

2. **keywords/tasks.py** - Update cleanup_stuck_keywords:
   - Make it more aggressive (run every 5 minutes)
   - Reset keywords stuck for just 1 hour (not 2)
   - Add logging for visibility

3. **keywords/models.py** - Update Keyword model:
   - Add auto-reset of processing flag after save
   - Add validation to prevent permanent stuck state

4. **celery.py** - Update task configuration:
   - Add task time limits
   - Add task soft time limits
   - Increase cleanup frequency

Here's the permanent fix code to implement:
""")
    
    # Write the permanent fix file
    fix_content = '''
# ========== PERMANENT FIX FOR KEYWORD CRAWLING ==========
# Add this to keywords/tasks.py

from celery.exceptions import SoftTimeLimitExceeded
from django.db import transaction

@shared_task(
    bind=True,
    time_limit=300,  # Hard limit: 5 minutes
    soft_time_limit=240,  # Soft limit: 4 minutes
    max_retries=3,
    default_retry_delay=60
)
def fetch_keyword_serp_html_fixed(self, keyword_id):
    """Enhanced version with proper error handling and timeout management"""
    keyword = None
    try:
        with transaction.atomic():
            keyword = Keyword.objects.select_for_update().get(id=keyword_id)
            
            # Double-check not already processing (race condition prevention)
            if keyword.processing:
                logger.warning(f"Keyword {keyword_id} already processing, skipping")
                return
            
            keyword.processing = True
            keyword.save(update_fields=['processing'])
        
        # Your existing crawl logic here
        # ... perform the actual crawl ...
        
    except SoftTimeLimitExceeded:
        logger.error(f"Task timeout for keyword {keyword_id}")
        if keyword:
            keyword.processing = False
            keyword.save(update_fields=['processing'])
        raise
        
    except Exception as e:
        logger.error(f"Error crawling keyword {keyword_id}: {e}")
        if keyword:
            keyword.processing = False
            keyword.save(update_fields=['processing'])
        raise self.retry(exc=e)
        
    finally:
        # ALWAYS reset processing flag
        if keyword:
            try:
                keyword.processing = False
                keyword.save(update_fields=['processing'])
            except:
                pass  # Even if save fails, don't block

# Update cleanup task to be more aggressive
@shared_task
def cleanup_stuck_keywords_enhanced():
    """More aggressive cleanup - run every 5 minutes"""
    from datetime import timedelta
    from django.utils import timezone
    
    # Reset keywords stuck for just 1 hour (not 2)
    one_hour_ago = timezone.now() - timedelta(hours=1)
    
    stuck = Keyword.objects.filter(
        processing=True,
        updated_at__lt=one_hour_ago
    )
    
    count = stuck.count()
    if count > 0:
        logger.warning(f"Resetting {count} stuck keywords (1+ hour old)")
        stuck.update(processing=False, updated_at=timezone.now())
        
        # Log which projects are affected
        affected_projects = stuck.values('project__domain').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        for proj in affected_projects:
            logger.info(f"  - {proj['project__domain']}: {proj['count']} keywords reset")
    
    # Also check for keywords with next_crawl_at issues
    null_next = Keyword.objects.filter(
        next_crawl_at__isnull=True,
        archive=False
    ).update(next_crawl_at=timezone.now())
    
    if null_next > 0:
        logger.info(f"Set next_crawl_at for {null_next} keywords")
    
    return {'reset': count, 'fixed_next_crawl': null_next}

# Update celery.py beat schedule
'cleanup-stuck-keywords': {
    'task': 'keywords.tasks.cleanup_stuck_keywords_enhanced',
    'schedule': crontab(minute='*/5'),  # Every 5 minutes instead of 15
    'options': {'queue': 'celery', 'priority': 10}  # High priority
},
'''
    
    print(fix_content)
    
    # Save the fix to a file
    with open('/home/muaaz/enterprise/limeclicks/permanent_fix_crawling.py', 'w') as f:
        f.write(fix_content)
    
    print("\nPermanent fix code saved to: permanent_fix_crawling.py")

def main():
    """Main execution"""
    import sys
    
    print("\n" + "🔍" * 40)
    print(" KEYWORD CRAWLING DIAGNOSTIC & FIX TOOL")
    print("🔍" * 40)
    
    # Run diagnosis
    issues = diagnose_all_projects()
    
    # Check if fixes are needed
    total_issues = sum([
        issues['stuck_count'],
        issues['null_next_crawl'],
        issues['very_stuck']
    ])
    
    if total_issues > 0:
        print_section("FIXES NEEDED")
        print(f"Found {total_issues} total issues that need fixing")
        
        # Ask for confirmation
        print("\nDo you want to apply immediate fixes?")
        print("1. Dry run (show what would be fixed)")
        print("2. Apply fixes now")
        print("3. Skip fixes")
        
        try:
            choice = input("\nEnter choice (1-3): ").strip()
        except:
            choice = "1"  # Default to dry run if running non-interactively
        
        if choice == "1":
            apply_immediate_fixes(dry_run=True)
        elif choice == "2":
            fixes = apply_immediate_fixes(dry_run=False)
            print(f"\n✅ Applied {len(fixes)} fixes:")
            for fix in fixes:
                print(f"  - {fix}")
        else:
            print("Skipping immediate fixes")
    else:
        print("\n✅ No immediate issues found!")
    
    # Always show permanent fix recommendations
    create_permanent_fix()
    
    print_section("NEXT STEPS")
    print("""
1. Run this script on the production server:
   python diagnose_and_fix_crawling.py

2. Apply immediate fixes if needed (option 2)

3. Implement the permanent fix code in:
   - keywords/tasks.py
   - celery.py

4. Deploy the permanent fix

5. Monitor for 24 hours to ensure issues don't recur
""")

if __name__ == "__main__":
    main()