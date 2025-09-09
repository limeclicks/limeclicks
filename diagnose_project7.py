#!/usr/bin/env python
"""
Diagnostic script for Project 7 keyword crawling issues
Run this on the production server to check keyword states
"""

import os
import sys
import django
from datetime import datetime, timedelta
from django.utils import timezone

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from keywords.models import Keyword
from project.models import Project
from django.db.models import Q

def diagnose_project_7():
    """Comprehensive diagnosis of Project 7 keyword crawling issues"""
    
    print("=" * 80)
    print("PROJECT 7 KEYWORD CRAWLING DIAGNOSIS")
    print("=" * 80)
    print(f"Current Time: {timezone.now()}")
    print(f"24 hours ago: {timezone.now() - timedelta(hours=24)}")
    print("=" * 80)
    
    # Check if project exists
    try:
        project = Project.objects.get(id=7)
        print(f"\n✓ Project 7 found: {project.domain}")
        print(f"  - Active: {project.active}")
        print(f"  - Created: {project.created_at}")
    except Project.DoesNotExist:
        print("\n✗ Project 7 not found!")
        return
    
    # Get all keywords for project 7
    all_keywords = Keyword.objects.filter(project_id=7)
    total_count = all_keywords.count()
    
    print(f"\n📊 KEYWORD STATISTICS FOR PROJECT 7:")
    print(f"  - Total keywords: {total_count}")
    
    if total_count == 0:
        print("  ✗ No keywords found for this project!")
        return
    
    # Check processing flags
    processing_stuck = all_keywords.filter(processing=True)
    processing_count = processing_stuck.count()
    
    print(f"\n🔄 PROCESSING STATUS:")
    print(f"  - Keywords with processing=True: {processing_count}")
    if processing_count > 0:
        print(f"    ⚠️  {processing_count} keywords are stuck in processing state!")
        # Show first 5 stuck keywords
        for kw in processing_stuck[:5]:
            time_stuck = timezone.now() - kw.updated_at if kw.updated_at else "Unknown"
            print(f"      - {kw.keyword}: stuck for {time_stuck}")
    
    # Check archived keywords
    archived_count = all_keywords.filter(archive=True).count()
    print(f"\n📦 ARCHIVED STATUS:")
    print(f"  - Archived keywords: {archived_count}")
    
    # Check never scraped keywords
    never_scraped = all_keywords.filter(scraped_at__isnull=True)
    never_scraped_count = never_scraped.count()
    
    print(f"\n🆕 NEVER SCRAPED:")
    print(f"  - Keywords never scraped: {never_scraped_count}")
    if never_scraped_count > 0:
        for kw in never_scraped[:5]:
            print(f"      - {kw.keyword} (created: {kw.created_at})")
    
    # Check keywords needing crawl (24+ hours old)
    one_day_ago = timezone.now() - timedelta(hours=24)
    needs_crawl = all_keywords.filter(
        Q(scraped_at__isnull=True) | Q(scraped_at__lt=one_day_ago)
    ).exclude(processing=True).exclude(archive=True)
    needs_crawl_count = needs_crawl.count()
    
    print(f"\n⏰ KEYWORDS NEEDING CRAWL (24+ hours):")
    print(f"  - Count: {needs_crawl_count}")
    if needs_crawl_count > 0:
        for kw in needs_crawl[:5]:
            last_scraped = kw.scraped_at if kw.scraped_at else "Never"
            if kw.scraped_at:
                time_since = timezone.now() - kw.scraped_at
                hours_ago = time_since.total_seconds() / 3600
                last_scraped = f"{hours_ago:.1f} hours ago"
            print(f"      - {kw.keyword}: last scraped {last_scraped}")
    
    # Check next_crawl_at field
    print(f"\n📅 NEXT CRAWL SCHEDULING:")
    
    # Keywords with next_crawl_at in the past
    past_due = all_keywords.filter(next_crawl_at__lt=timezone.now()).exclude(processing=True)
    past_due_count = past_due.count()
    print(f"  - Keywords past due (next_crawl_at < now): {past_due_count}")
    
    # Keywords with NULL next_crawl_at
    null_next_crawl = all_keywords.filter(next_crawl_at__isnull=True)
    null_count = null_next_crawl.count()
    print(f"  - Keywords with NULL next_crawl_at: {null_count}")
    
    # Show sample of past due keywords
    if past_due_count > 0:
        print(f"\n  Past due examples:")
        for kw in past_due[:5]:
            overdue_by = timezone.now() - kw.next_crawl_at if kw.next_crawl_at else "N/A"
            print(f"      - {kw.keyword}: overdue by {overdue_by}")
    
    # Check crawl priorities
    print(f"\n🎯 CRAWL PRIORITIES:")
    for priority in ['critical', 'high', 'normal', 'low']:
        count = all_keywords.filter(crawl_priority=priority).count()
        print(f"  - {priority}: {count} keywords")
    
    # Recent crawl activity
    print(f"\n📈 RECENT CRAWL ACTIVITY:")
    for hours in [1, 6, 12, 24, 48]:
        time_threshold = timezone.now() - timedelta(hours=hours)
        recent_count = all_keywords.filter(scraped_at__gte=time_threshold).count()
        print(f"  - Crawled in last {hours} hours: {recent_count}")
    
    # Check what the batch query would return
    print(f"\n🔍 SIMULATING BATCH QUERY:")
    
    # This mimics the exact query from enqueue_keyword_scrapes_batch
    batch_keywords = Keyword.objects.filter(
        Q(scraped_at__isnull=True) | Q(scraped_at__lt=one_day_ago),
        processing=False,
        archive=False,
        project__active=True,
        project_id=7  # Just for project 7
    ).order_by('scraped_at', 'created_at')[:10]
    
    batch_count = batch_keywords.count()
    print(f"  - Keywords that SHOULD be picked up by batch: {batch_count}")
    
    if batch_count > 0:
        print(f"\n  First 10 that should be processed:")
        for kw in batch_keywords:
            print(f"      - {kw.keyword}")
            print(f"        scraped_at: {kw.scraped_at}")
            print(f"        processing: {kw.processing}")
            print(f"        next_crawl: {kw.next_crawl_at}")
    else:
        print(f"  ⚠️  NO KEYWORDS WOULD BE PICKED UP BY BATCH QUERY!")
        print(f"\n  Investigating why...")
        
        # Check each condition separately
        not_processing = all_keywords.filter(processing=False).count()
        not_archived = all_keywords.filter(archive=False).count()
        project_active = all_keywords.filter(project__active=True).count()
        
        print(f"    - Keywords with processing=False: {not_processing}/{total_count}")
        print(f"    - Keywords with archive=False: {not_archived}/{total_count}")
        print(f"    - Keywords with active project: {project_active}/{total_count}")
        
        # If all conditions pass individually but not together
        if not_processing > 0 and not_archived > 0 and needs_crawl_count > 0:
            print(f"\n  🔴 CRITICAL: Conditions pass individually but not together!")
            print(f"     This suggests a complex interaction between conditions.")
    
    print("\n" + "=" * 80)
    print("DIAGNOSIS COMPLETE")
    print("=" * 80)
    
    # Recommendations
    print("\n📋 RECOMMENDATIONS:")
    
    if processing_count > 0:
        print(f"  1. Reset {processing_count} stuck processing flags:")
        print(f"     Keyword.objects.filter(project_id=7, processing=True).update(processing=False)")
    
    if null_count > 0:
        print(f"  2. Set next_crawl_at for {null_count} keywords:")
        print(f"     Keyword.objects.filter(project_id=7, next_crawl_at__isnull=True).update(next_crawl_at=timezone.now())")
    
    if needs_crawl_count > 0 and batch_count == 0:
        print(f"  3. Force reset all keywords to trigger crawl:")
        print(f"     Keyword.objects.filter(project_id=7).update(processing=False, next_crawl_at=timezone.now())")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    diagnose_project_7()