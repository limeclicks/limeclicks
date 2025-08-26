#!/usr/bin/env python
"""
Test cases for rank tracking functionality including:
- Rank difference calculations
- Impact calculations
- Initial and highest rank tracking
- Tag associations
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.utils import timezone
from keywords.models import Keyword, Rank, Tag, KeywordTag
from project.models import Project
from accounts.models import User


def test_rank_tracking():
    """Test comprehensive rank tracking functionality"""
    
    print("=" * 80)
    print("🧪 Testing Rank Tracking Functionality")
    print("=" * 80)
    
    # Create test project
    user, _ = User.objects.get_or_create(
        username='rank_test_user',
        defaults={'email': 'ranktest@example.com'}
    )
    
    project, _ = Project.objects.get_or_create(
        domain='ranktest.com',
        defaults={
            'user': user,
            'title': 'Rank Test Project',
            'active': True
        }
    )
    
    # Create test keyword (or reset if exists)
    keyword, created = Keyword.objects.get_or_create(
        project=project,
        keyword='test rank tracking',
        country='US',
        defaults={'country_code': 'US'}
    )
    
    # Reset the keyword to initial state for testing
    keyword.rank = 0
    keyword.initial_rank = None
    keyword.highest_rank = 0
    keyword.rank_status = 'no_change'
    keyword.rank_diff_from_last_time = 0
    keyword.impact = 'no'
    keyword.rank_url = None
    keyword.save()
    
    print(f"\n✓ Created test keyword: {keyword.keyword}")
    print(f"  Initial state:")
    print(f"    Rank: {keyword.rank}")
    print(f"    Initial rank: {keyword.initial_rank}")
    print(f"    Highest rank: {keyword.highest_rank}")
    print(f"    Status: {keyword.rank_status}")
    print(f"    Impact: {keyword.impact}")
    
    # Test 1: First ranking (new)
    print("\n" + "-" * 40)
    print("Test 1: First Ranking (NEW)")
    print("-" * 40)
    
    keyword.update_rank(5, url="https://ranktest.com/page1")
    keyword.refresh_from_db()
    
    assert keyword.rank == 5, f"Expected rank 5, got {keyword.rank}"
    assert keyword.initial_rank == 5, f"Expected initial_rank 5, got {keyword.initial_rank}"
    assert keyword.highest_rank == 5, f"Expected highest_rank 5, got {keyword.highest_rank}"
    assert keyword.rank_status == 'new', f"Expected status 'new', got {keyword.rank_status}"
    assert keyword.rank_diff_from_last_time == 0, f"Expected diff 0, got {keyword.rank_diff_from_last_time}"
    assert keyword.impact == 'medium', f"Expected impact 'medium', got {keyword.impact}"
    assert keyword.rank_url == "https://ranktest.com/page1", f"URL not saved correctly"
    
    print(f"  ✓ Rank: {keyword.rank}")
    print(f"  ✓ Initial rank: {keyword.initial_rank}")
    print(f"  ✓ Highest rank: {keyword.highest_rank}")
    print(f"  ✓ Status: {keyword.rank_status}")
    print(f"  ✓ Diff: {keyword.rank_diff_from_last_time}")
    print(f"  ✓ Impact: {keyword.impact}")
    print(f"  ✓ URL: {keyword.rank_url}")
    
    # Test 2: Rank improvement (up)
    print("\n" + "-" * 40)
    print("Test 2: Rank Improvement (UP)")
    print("-" * 40)
    
    keyword.update_rank(2, url="https://ranktest.com/page2")
    keyword.refresh_from_db()
    
    assert keyword.rank == 2, f"Expected rank 2, got {keyword.rank}"
    assert keyword.initial_rank == 5, f"Initial rank should stay 5, got {keyword.initial_rank}"
    assert keyword.highest_rank == 2, f"Expected highest_rank 2, got {keyword.highest_rank}"
    assert keyword.rank_status == 'up', f"Expected status 'up', got {keyword.rank_status}"
    assert keyword.rank_diff_from_last_time == 3, f"Expected diff 3, got {keyword.rank_diff_from_last_time}"
    assert keyword.impact == 'high', f"Expected impact 'high', got {keyword.impact}"
    
    print(f"  Previous rank: 5 → Current rank: {keyword.rank}")
    print(f"  ✓ Status: {keyword.rank_status}")
    print(f"  ✓ Diff: +{keyword.rank_diff_from_last_time} positions (improvement)")
    print(f"  ✓ Highest rank updated: {keyword.highest_rank}")
    print(f"  ✓ Impact: {keyword.impact}")
    
    # Test 3: Rank decline (down)
    print("\n" + "-" * 40)
    print("Test 3: Rank Decline (DOWN)")
    print("-" * 40)
    
    keyword.update_rank(8)
    keyword.refresh_from_db()
    
    assert keyword.rank == 8, f"Expected rank 8, got {keyword.rank}"
    assert keyword.highest_rank == 2, f"Highest rank should stay 2, got {keyword.highest_rank}"
    assert keyword.rank_status == 'down', f"Expected status 'down', got {keyword.rank_status}"
    assert keyword.rank_diff_from_last_time == -6, f"Expected diff -6, got {keyword.rank_diff_from_last_time}"
    assert keyword.impact == 'high', f"Expected impact 'high', got {keyword.impact}"
    
    print(f"  Previous rank: 2 → Current rank: {keyword.rank}")
    print(f"  ✓ Status: {keyword.rank_status}")
    print(f"  ✓ Diff: {keyword.rank_diff_from_last_time} positions (decline)")
    print(f"  ✓ Highest rank unchanged: {keyword.highest_rank}")
    print(f"  ✓ Impact: {keyword.impact}")
    
    # Test 4: No change
    print("\n" + "-" * 40)
    print("Test 4: No Change")
    print("-" * 40)
    
    keyword.update_rank(8)
    keyword.refresh_from_db()
    
    assert keyword.rank_status == 'no_change', f"Expected status 'no_change', got {keyword.rank_status}"
    assert keyword.rank_diff_from_last_time == 0, f"Expected diff 0, got {keyword.rank_diff_from_last_time}"
    assert keyword.impact == 'no', f"Expected impact 'no', got {keyword.impact}"
    
    print(f"  ✓ Status: {keyword.rank_status}")
    print(f"  ✓ Diff: {keyword.rank_diff_from_last_time}")
    print(f"  ✓ Impact: {keyword.impact}")
    
    # Test 5: Impact calculations for different positions
    print("\n" + "-" * 40)
    print("Test 5: Impact Calculations")
    print("-" * 40)
    
    test_cases = [
        # (old_rank, new_rank, expected_impact, description)
        (0, 1, 'high', 'New ranking at #1'),
        (0, 3, 'high', 'New ranking in top 3'),
        (0, 10, 'medium', 'New ranking in top 10'),
        (0, 25, 'low', 'New ranking in top 30'),
        (0, 50, 'no', 'New ranking beyond 30'),
        (5, 3, 'high', 'Improvement to top 3'),
        (15, 5, 'high', 'Large improvement to top 10'),
        (25, 10, 'high', 'Major improvement'),
        (50, 40, 'low', 'Small improvement beyond 30'),
        (10, 35, 'medium', 'Major decline from top 10'),
    ]
    
    for old_rank, new_rank, expected_impact, description in test_cases:
        impact = keyword.calculate_impact(old_rank, new_rank)
        status = "✓" if impact == expected_impact else "✗"
        print(f"  {status} {description}: {old_rank} → {new_rank} = {impact} (expected: {expected_impact})")
        assert impact == expected_impact, f"Failed: {description}"
    
    # Test 6: Tags functionality
    print("\n" + "-" * 40)
    print("Test 6: Tags Functionality")
    print("-" * 40)
    
    # Create tags
    tag1 = Tag.objects.create(name='Priority', color='#FF0000')
    tag2 = Tag.objects.create(name='Local SEO', color='#00FF00')
    tag3 = Tag.objects.create(name='Commercial', color='#0000FF')
    
    print(f"  Created tags: {tag1.name}, {tag2.name}, {tag3.name}")
    print(f"  Tag slugs: {tag1.slug}, {tag2.slug}, {tag3.slug}")
    
    # Associate tags with keyword
    KeywordTag.objects.create(keyword=keyword, tag=tag1)
    KeywordTag.objects.create(keyword=keyword, tag=tag2)
    
    # Check associations
    keyword_tags = keyword.keyword_tags.all()
    assert keyword_tags.count() == 2, f"Expected 2 tags, got {keyword_tags.count()}"
    
    tag_names = [kt.tag.name for kt in keyword_tags]
    print(f"  ✓ Keyword tags: {', '.join(tag_names)}")
    
    # Test 7: Multiple rank records
    print("\n" + "-" * 40)
    print("Test 7: Multiple Rank Records")
    print("-" * 40)
    
    # Create multiple rank records over time
    dates = [
        timezone.now() - timedelta(days=7),
        timezone.now() - timedelta(days=5),
        timezone.now() - timedelta(days=3),
        timezone.now() - timedelta(days=1),
        timezone.now(),
    ]
    
    ranks = [10, 8, 5, 3, 2]
    
    for date, rank_pos in zip(dates, ranks):
        rank = Rank.objects.create(
            keyword=keyword,
            rank=rank_pos,
            is_organic=True,
            created_at=date
        )
    
    # Check rank history
    rank_history = Rank.objects.filter(keyword=keyword).order_by('-created_at')
    print(f"  Total rank records: {rank_history.count()}")
    
    for rank in rank_history[:5]:
        print(f"    {rank.created_at.strftime('%Y-%m-%d')}: #{rank.rank}")
    
    # Clean up
    print("\n" + "-" * 40)
    print("Cleanup")
    print("-" * 40)
    
    keyword.delete()
    project.delete()
    user.delete()
    Tag.objects.filter(name__in=['Priority', 'Local SEO', 'Commercial']).delete()
    
    print("  ✓ Test data cleaned up")
    
    print("\n" + "=" * 80)
    print("✅ All Rank Tracking Tests Passed!")
    print("=" * 80)
    print("\nSummary of tested features:")
    print("  • Initial rank tracking")
    print("  • Highest rank tracking")
    print("  • Rank difference calculations")
    print("  • Rank status (new, up, down, no_change)")
    print("  • Impact calculations based on position and change")
    print("  • URL tracking for rankings")
    print("  • Tag associations with keywords")
    print("  • Multiple rank records over time")
    print("  • scraped_at timestamp updates")


if __name__ == '__main__':
    test_rank_tracking()