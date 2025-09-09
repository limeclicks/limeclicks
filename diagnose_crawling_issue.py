#!/usr/bin/env python
"""
Pure diagnostic script for keyword crawling issues
This will ONLY diagnose and report - NO changes will be made
Run this on the production server to understand the exact problem
"""

import os
import sys
import django
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Count, Min, Max, Avg
from django.db import connection
from collections import defaultdict

# Setup Django for production database
os.environ['DATABASE_URL'] = 'postgresql://postgres:LimeClicksPwd007@localhost:5432/lime'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from keywords.models import Keyword
from project.models import Project
from django_celery_beat.models import PeriodicTask, IntervalSchedule

def print_section(title, symbol="="):
    """Print a formatted section header"""
    print(f"\n{symbol * 80}")
    print(f" {title} ")
    print(f"{symbol * 80}")

def analyze_project_7_specifically():
    """Deep dive into Project 7 issues"""
    print_section("PROJECT 7 DEEP ANALYSIS", "▶")
    
    try:
        project = Project.objects.get(id=7)
        print(f"Project: {project.domain}")
        print(f"Active: {project.active}")
        print(f"Created: {project.created_at}")
        
        keywords = Keyword.objects.filter(project_id=7)
        total = keywords.count()
        
        if total == 0:
            print("❌ No keywords found for Project 7!")
            return None
            
        print(f"\n📊 Keyword Statistics:")
        print(f"  Total keywords: {total}")
        print(f"  Archived: {keywords.filter(archive=True).count()}")
        print(f"  Active: {keywords.filter(archive=False).count()}")
        
        # Analyze scraped_at distribution
        print(f"\n⏰ Last Scraped Distribution:")
        now = timezone.now()
        
        ranges = [
            ("Never", keywords.filter(scraped_at__isnull=True)),
            ("< 1 hour", keywords.filter(scraped_at__gte=now - timedelta(hours=1))),
            ("1-6 hours", keywords.filter(scraped_at__lt=now - timedelta(hours=1), scraped_at__gte=now - timedelta(hours=6))),
            ("6-24 hours", keywords.filter(scraped_at__lt=now - timedelta(hours=6), scraped_at__gte=now - timedelta(hours=24))),
            ("24-48 hours", keywords.filter(scraped_at__lt=now - timedelta(hours=24), scraped_at__gte=now - timedelta(hours=48))),
            ("2-7 days", keywords.filter(scraped_at__lt=now - timedelta(days=2), scraped_at__gte=now - timedelta(days=7))),
            ("> 7 days", keywords.filter(scraped_at__lt=now - timedelta(days=7)))
        ]
        
        for label, queryset in ranges:
            count = queryset.count()
            if count > 0:
                print(f"  {label:15} : {count:5} keywords ({count*100/total:.1f}%)")
        
        # Analyze processing flags
        print(f"\n🔄 Processing Status:")
        processing_true = keywords.filter(processing=True)
        processing_count = processing_true.count()
        print(f"  Processing=True: {processing_count}")
        
        if processing_count > 0:
            # Check how long they've been stuck
            stuck_times = []
            for kw in processing_true[:10]:  # Sample first 10
                if kw.updated_at:
                    stuck_duration = now - kw.updated_at
                    stuck_times.append(stuck_duration)
                    print(f"    - {kw.keyword[:30]:30} stuck for {stuck_duration}")
            
            if stuck_times:
                avg_stuck = sum(stuck_times, timedelta()) / len(stuck_times)
                print(f"  Average stuck time: {avg_stuck}")
        
        # Analyze next_crawl_at
        print(f"\n📅 Next Crawl Scheduling:")
        null_next = keywords.filter(next_crawl_at__isnull=True).count()
        future_next = keywords.filter(next_crawl_at__gt=now).count()
        past_next = keywords.filter(next_crawl_at__lte=now).count()
        
        print(f"  NULL next_crawl_at: {null_next}")
        print(f"  Future (not yet due): {future_next}")
        print(f"  Past (overdue): {past_next}")
        
        # Sample overdue keywords
        if past_next > 0:
            overdue = keywords.filter(next_crawl_at__lte=now, processing=False).order_by('next_crawl_at')[:5]
            print(f"\n  Sample overdue keywords:")
            for kw in overdue:
                overdue_by = now - kw.next_crawl_at if kw.next_crawl_at else "N/A"
                print(f"    - {kw.keyword[:30]:30} overdue by {overdue_by}")
        
        # Check what the batch query would select
        print(f"\n🔍 Batch Query Simulation:")
        one_day_ago = now - timedelta(hours=24)
        
        # Exact query from enqueue_keyword_scrapes_batch
        would_select = keywords.filter(
            Q(scraped_at__isnull=True) | Q(scraped_at__lt=one_day_ago),
            processing=False,
            archive=False,
            project__active=True
        )
        
        would_select_count = would_select.count()
        print(f"  Keywords that WOULD be selected by batch: {would_select_count}")
        
        if would_select_count == 0:
            print(f"\n  ⚠️ WARNING: No keywords would be selected!")
            print(f"  Checking why...")
            
            # Break down each condition
            never_or_old = keywords.filter(Q(scraped_at__isnull=True) | Q(scraped_at__lt=one_day_ago)).count()
            not_processing = keywords.filter(processing=False).count()
            not_archived = keywords.filter(archive=False).count()
            project_active = keywords.filter(project__active=True).count()
            
            print(f"    - Meet time criteria (never or >24h): {never_or_old}/{total}")
            print(f"    - Not processing: {not_processing}/{total}")
            print(f"    - Not archived: {not_archived}/{total}")
            print(f"    - Project active: {project_active}/{total}")
            
            # Find the blocking condition
            if never_or_old == 0:
                print(f"    ❌ BLOCKER: All keywords crawled within 24 hours")
            elif not_processing == 0:
                print(f"    ❌ BLOCKER: All keywords have processing=True")
            elif not_archived == 0:
                print(f"    ❌ BLOCKER: All keywords are archived")
            elif project_active == 0:
                print(f"    ❌ BLOCKER: Project is not active")
        else:
            print(f"\n  Sample keywords that would be selected:")
            for kw in would_select[:5]:
                last_scraped = f"{(now - kw.scraped_at).total_seconds()/3600:.1f}h ago" if kw.scraped_at else "Never"
                print(f"    - {kw.keyword[:30]:30} (scraped: {last_scraped})")
        
        return {
            'total': total,
            'processing_stuck': processing_count,
            'would_be_selected': would_select_count,
            'overdue': past_next
        }
        
    except Project.DoesNotExist:
        print("❌ Project 7 does not exist!")
        return None

def analyze_celery_health():
    """Check if Celery Beat and tasks are configured correctly"""
    print_section("CELERY CONFIGURATION ANALYSIS", "🔧")
    
    try:
        # Check periodic tasks
        tasks = PeriodicTask.objects.filter(enabled=True)
        print(f"\n📋 Enabled Periodic Tasks: {tasks.count()}")
        
        # Look for our specific task
        keyword_tasks = tasks.filter(task__icontains='keyword')
        print(f"\n🔎 Keyword-related tasks:")
        for task in keyword_tasks:
            print(f"  - {task.name}")
            print(f"    Task: {task.task}")
            print(f"    Schedule: {task.interval or task.crontab}")
            print(f"    Last run: {task.last_run_at}")
            if task.last_run_at:
                time_since = timezone.now() - task.last_run_at
                print(f"    Time since last run: {time_since}")
        
        # Check for the specific batch task
        batch_task = tasks.filter(task='keywords.tasks.enqueue_keyword_scrapes_batch').first()
        if batch_task:
            print(f"\n✅ Batch task found: {batch_task.name}")
            print(f"  Enabled: {batch_task.enabled}")
            print(f"  Last run: {batch_task.last_run_at}")
            if batch_task.last_run_at:
                time_since = timezone.now() - batch_task.last_run_at
                if time_since > timedelta(minutes=10):
                    print(f"  ⚠️ WARNING: Task hasn't run in {time_since}")
        else:
            print(f"\n❌ CRITICAL: enqueue_keyword_scrapes_batch task NOT FOUND in schedule!")
        
        # Check cleanup task
        cleanup_task = tasks.filter(task='keywords.tasks.cleanup_stuck_keywords').first()
        if cleanup_task:
            print(f"\n✅ Cleanup task found: {cleanup_task.name}")
            print(f"  Last run: {cleanup_task.last_run_at}")
        else:
            print(f"\n⚠️ WARNING: cleanup_stuck_keywords task not found")
            
    except Exception as e:
        print(f"❌ Error checking Celery tasks: {e}")

def analyze_system_wide_patterns():
    """Look for patterns across all projects"""
    print_section("SYSTEM-WIDE PATTERN ANALYSIS", "📈")
    
    # Overall statistics
    total_keywords = Keyword.objects.filter(archive=False).count()
    total_projects = Project.objects.filter(active=True).count()
    
    print(f"\n📊 Overall Statistics:")
    print(f"  Total active projects: {total_projects}")
    print(f"  Total active keywords: {total_keywords}")
    
    # Processing flag analysis
    stuck_processing = Keyword.objects.filter(processing=True, archive=False)
    stuck_count = stuck_processing.count()
    
    print(f"\n🔄 Processing Flags:")
    print(f"  Stuck (processing=True): {stuck_count} ({stuck_count*100/total_keywords:.1f}%)")
    
    if stuck_count > 0:
        # Find patterns in stuck keywords
        stuck_by_project = stuck_processing.values('project__id', 'project__domain').annotate(
            count=Count('id'),
            avg_stuck_time=Avg('updated_at')
        ).order_by('-count')[:10]
        
        print(f"\n  Projects with most stuck keywords:")
        for proj in stuck_by_project:
            percentage = proj['count'] * 100 / stuck_count
            print(f"    Project {proj['project__id']:3} ({proj['project__domain'][:30]:30}): {proj['count']:5} stuck ({percentage:.1f}%)")
    
    # Time-based analysis
    now = timezone.now()
    one_day_ago = now - timedelta(hours=24)
    
    print(f"\n⏰ Crawl Timing Analysis:")
    never_crawled = Keyword.objects.filter(scraped_at__isnull=True, archive=False).count()
    needs_crawl = Keyword.objects.filter(scraped_at__lt=one_day_ago, archive=False).count()
    recently_crawled = Keyword.objects.filter(scraped_at__gte=one_day_ago, archive=False).count()
    
    print(f"  Never crawled: {never_crawled}")
    print(f"  Needs crawl (>24h): {needs_crawl}")
    print(f"  Recently crawled (<24h): {recently_crawled}")
    
    # Check distribution by age
    age_distribution = []
    for days in [1, 2, 3, 7, 14, 30]:
        cutoff = now - timedelta(days=days)
        count = Keyword.objects.filter(scraped_at__lt=cutoff, archive=False).count()
        age_distribution.append((days, count))
        print(f"  Not crawled in {days:2} days: {count:6} keywords")
    
    # Identify if it's a systemic issue or project-specific
    projects_affected = Keyword.objects.filter(
        scraped_at__lt=one_day_ago,
        archive=False
    ).values('project_id').distinct().count()
    
    print(f"\n🎯 Issue Scope:")
    print(f"  Projects affected: {projects_affected}/{total_projects}")
    if projects_affected > total_projects * 0.8:
        print(f"  ⚠️ SYSTEMIC ISSUE: Affects {projects_affected*100/total_projects:.1f}% of projects")
    else:
        print(f"  📍 ISOLATED ISSUE: Affects only {projects_affected*100/total_projects:.1f}% of projects")

def check_database_query_performance():
    """Test the actual queries being used"""
    print_section("DATABASE QUERY ANALYSIS", "🗄️")
    
    now = timezone.now()
    one_day_ago = now - timedelta(hours=24)
    
    # Test the batch query
    print("\n🔍 Testing Batch Query Performance:")
    
    with connection.cursor() as cursor:
        # Get query execution plan
        query = """
        EXPLAIN ANALYZE
        SELECT COUNT(*) FROM keywords_keyword k
        JOIN project_project p ON k.project_id = p.id
        WHERE (k.scraped_at IS NULL OR k.scraped_at < %s)
        AND k.processing = false
        AND k.archive = false
        AND p.active = true
        """
        
        cursor.execute(query, [one_day_ago])
        result = cursor.fetchall()
        
        print("Query execution plan:")
        for row in result:
            print(f"  {row[0]}")
    
    # Check for index usage
    print("\n📊 Index Usage Check:")
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename = 'keywords_keyword'
        """)
        indexes = cursor.fetchall()
        
        print("Indexes on keywords_keyword table:")
        for idx_name, idx_def in indexes:
            print(f"  - {idx_name}")
            if 'processing' in idx_def.lower():
                print(f"    ✅ Has index on processing")
            if 'scraped_at' in idx_def.lower():
                print(f"    ✅ Has index on scraped_at")

def generate_diagnosis_summary():
    """Generate a comprehensive summary and recommendations"""
    print_section("DIAGNOSIS SUMMARY", "📋")
    
    findings = []
    critical_issues = []
    
    # Run all analyses
    p7_results = analyze_project_7_specifically()
    
    if p7_results:
        if p7_results['processing_stuck'] > 0:
            critical_issues.append(f"Project 7 has {p7_results['processing_stuck']} stuck keywords")
        if p7_results['would_be_selected'] == 0:
            critical_issues.append(f"Project 7 keywords won't be selected by batch query")
    
    # Check for common patterns
    stuck_total = Keyword.objects.filter(processing=True, archive=False).count()
    if stuck_total > 100:
        critical_issues.append(f"System-wide: {stuck_total} keywords stuck with processing=True")
    
    never_crawled = Keyword.objects.filter(scraped_at__isnull=True, archive=False).count()
    if never_crawled > 0:
        findings.append(f"{never_crawled} keywords have never been crawled")
    
    # Output summary
    print("\n🔴 CRITICAL ISSUES:")
    if critical_issues:
        for issue in critical_issues:
            print(f"  - {issue}")
    else:
        print("  None found")
    
    print("\n🟡 FINDINGS:")
    if findings:
        for finding in findings:
            print(f"  - {finding}")
    else:
        print("  None")
    
    print("\n💡 ROOT CAUSE HYPOTHESIS:")
    if stuck_total > 0:
        print("  1. PRIMARY: Processing flags getting stuck when tasks fail")
        print("     - Tasks crash without resetting the flag")
        print("     - Cleanup task not aggressive enough")
    
    if p7_results and p7_results['would_be_selected'] == 0:
        print("  2. SECONDARY: Batch query not selecting eligible keywords")
        print("     - Possibly due to stuck processing flags")
        print("     - Or all keywords recently crawled")
    
    print("\n🔧 RECOMMENDED SOLUTION APPROACH:")
    print("  1. Implement atomic processing flag management")
    print("  2. Add task timeouts and proper error handling")
    print("  3. Make cleanup more aggressive (every 5 min, 1 hour threshold)")
    print("  4. Add monitoring/alerting for stuck keywords")
    print("  5. Consider using database-level locks instead of flags")

def main():
    """Run complete diagnosis"""
    print("\n" + "="*80)
    print(" KEYWORD CRAWLING ISSUE DIAGNOSIS - PRODUCTION ")
    print("="*80)
    print(f"Started at: {timezone.now()}")
    
    # Run all diagnostic functions
    analyze_project_7_specifically()
    analyze_celery_health()
    analyze_system_wide_patterns()
    check_database_query_performance()
    generate_diagnosis_summary()
    
    print("\n" + "="*80)
    print(" END OF DIAGNOSIS ")
    print("="*80)
    
    print("\n📝 NEXT STEPS:")
    print("  1. Run this script on the production server")
    print("  2. Review the diagnosis results")
    print("  3. Based on findings, implement targeted fixes")
    print("  4. Test fixes in staging first")
    print("  5. Deploy to production with monitoring")

if __name__ == "__main__":
    main()