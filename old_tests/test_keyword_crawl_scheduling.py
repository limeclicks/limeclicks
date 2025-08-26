#!/usr/bin/env python
"""
Test script for keyword crawl scheduling functionality
"""
import os
import sys
import django
from datetime import timedelta

os.environ['DJANGO_SETTINGS_MODULE'] = 'limeclicks.settings'
django.setup()

from django.utils import timezone
from keywords.models import Keyword
from project.models import Project
from accounts.models import User
from keywords.crawl_scheduler import CrawlScheduler

print("\n" + "="*80)
print("KEYWORD CRAWL SCHEDULING TEST")
print("="*80)

# Test user and project setup
try:
    user = User.objects.first()
    if not user:
        print("❌ No user found. Creating test user...")
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    print(f"✅ Using user: {user.email}")
    
    # Get or create test project
    project = Project.objects.filter(user=user).first()
    if not project:
        project = Project.objects.create(
            user=user,
            domain='testsite.com',
            title='Test Site'
        )
    print(f"✅ Using project: {project.domain}")
    
except Exception as e:
    print(f"❌ Setup error: {e}")
    sys.exit(1)

# Test 1: Create keywords with different scenarios
print("\n📝 TEST 1: Creating test keywords with different states...")

test_keywords = []

# Keyword 1: Never crawled (should be high priority)
kw1, created = Keyword.objects.get_or_create(
    project=project,
    keyword='test keyword new',
    country='US',
    defaults={'rank': 0}
)
if created:
    print(f"  Created new keyword: {kw1.keyword}")
test_keywords.append(kw1)

# Keyword 2: Crawled 25 hours ago (should need crawl)
kw2, created = Keyword.objects.get_or_create(
    project=project,
    keyword='test keyword old',
    country='US',
    defaults={'rank': 5}
)
kw2.scraped_at = timezone.now() - timedelta(hours=25)
kw2.next_crawl_at = timezone.now() - timedelta(hours=1)
kw2.save()
print(f"  Set keyword '{kw2.keyword}' as crawled 25 hours ago")
test_keywords.append(kw2)

# Keyword 3: Recently crawled (should not need crawl)
kw3, created = Keyword.objects.get_or_create(
    project=project,
    keyword='test keyword recent',
    country='US',
    defaults={'rank': 10}
)
kw3.scraped_at = timezone.now() - timedelta(hours=5)
kw3.next_crawl_at = timezone.now() + timedelta(hours=19)
kw3.save()
print(f"  Set keyword '{kw3.keyword}' as crawled 5 hours ago")
test_keywords.append(kw3)

# Test 2: Check should_crawl logic
print("\n🔍 TEST 2: Testing should_crawl() method...")
for kw in test_keywords:
    should_crawl = kw.should_crawl()
    print(f"  {kw.keyword}: should_crawl = {should_crawl}")
    if kw.scraped_at:
        hours_since = (timezone.now() - kw.scraped_at).total_seconds() / 3600
        print(f"    Last crawled: {hours_since:.1f} hours ago")

# Test 3: Test priority assignment
print("\n🎯 TEST 3: Testing priority assignment...")

# Set priority for never-crawled keyword
if not kw1.scraped_at:
    kw1.schedule_next_crawl()
    print(f"  {kw1.keyword}: Priority = {kw1.crawl_priority} (expected: high)")

# Check priority values
for kw in test_keywords:
    priority_value = kw.get_crawl_priority_value()
    print(f"  {kw.keyword}: Priority = {kw.crawl_priority} (value: {priority_value})")

# Test 4: Force crawl functionality
print("\n💪 TEST 4: Testing force crawl...")

# First force crawl should work
try:
    can_force = kw2.can_force_crawl()
    print(f"  Can force crawl '{kw2.keyword}': {can_force}")
    
    if can_force:
        result = kw2.force_crawl()
        print(f"  ✅ Force crawl successful! Priority: {kw2.crawl_priority}")
        print(f"     Force crawl count: {kw2.force_crawl_count}")
except Exception as e:
    print(f"  ❌ Force crawl error: {e}")

# Second force crawl should fail (within 1 hour)
try:
    can_force = kw2.can_force_crawl()
    print(f"  Can force crawl again: {can_force} (expected: False)")
    
    if not can_force:
        print("  ✅ Rate limiting working correctly!")
except Exception as e:
    print(f"  ❌ Error: {e}")

# Test 5: Crawl scheduler
print("\n📅 TEST 5: Testing CrawlScheduler...")

scheduler = CrawlScheduler()

# Get keywords to crawl
keywords_to_crawl = scheduler.get_keywords_to_crawl(limit=10)
print(f"  Keywords ready for crawl: {len(keywords_to_crawl)}")

for kw in keywords_to_crawl[:5]:  # Show first 5
    print(f"    - {kw.keyword} (Priority: {kw.crawl_priority})")

# Test 6: Update rank and scheduling
print("\n📊 TEST 6: Testing rank update and scheduling...")

# Update rank for a keyword
old_rank = kw2.rank
kw2.update_rank(3, url='https://example.com/page')
print(f"  Updated '{kw2.keyword}' rank: {old_rank} -> {kw2.rank}")
print(f"  Next crawl scheduled at: {kw2.next_crawl_at}")
print(f"  Priority after update: {kw2.crawl_priority}")

# Test 7: Verify database fields
print("\n🗄️ TEST 7: Verifying database fields...")

from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'keywords_keyword' 
        AND column_name IN ('next_crawl_at', 'crawl_priority', 'force_crawl_count', 
                           'last_force_crawl_at', 'crawl_interval_hours')
    """)
    columns = [row[0] for row in cursor.fetchall()]
    
    expected = ['next_crawl_at', 'crawl_priority', 'force_crawl_count', 
                'last_force_crawl_at', 'crawl_interval_hours']
    
    for col in expected:
        if col in columns:
            print(f"  ✅ Column '{col}' exists")
        else:
            print(f"  ❌ Column '{col}' missing")

# Test Summary
print("\n" + "="*80)
print("TEST SUMMARY")
print("="*80)

# Count keywords by state
never_crawled = Keyword.objects.filter(scraped_at__isnull=True).count()
needs_crawl = Keyword.objects.filter(
    scraped_at__lt=timezone.now() - timedelta(hours=24)
).count()
recently_crawled = Keyword.objects.filter(
    scraped_at__gte=timezone.now() - timedelta(hours=24)
).count()

print(f"Never crawled: {never_crawled}")
print(f"Needs crawl (>24h): {needs_crawl}")
print(f"Recently crawled (<24h): {recently_crawled}")

print("\n✅ All tests completed!")
print("\nKey Features Implemented:")
print("  • High priority for first-time keywords")
print("  • 24-hour interval for regular crawls")
print("  • Force crawl with 1-hour rate limiting")
print("  • Priority-based crawl scheduling")
print("  • API endpoints for force crawl and status")
print("  • Periodic tasks for automated scheduling")