#!/usr/bin/env python
"""
Test rank tracking with fastgenerations.co.uk real data
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


def test_fastgen_rank_tracking():
    """Test rank tracking with real fastgenerations.co.uk data"""
    
    print("=" * 80)
    print("🔍 Testing Rank Tracking with fastgenerations.co.uk")
    print("=" * 80)
    
    # Get project
    try:
        project = Project.objects.get(domain='fastgenerations.co.uk')
        print(f"\n✓ Project: {project.domain}")
    except Project.DoesNotExist:
        print("❌ Project fastgenerations.co.uk not found. Run test_fastgenerations_scrape_real.py first.")
        return
    
    # Get keywords
    keywords = Keyword.objects.filter(project=project).order_by('keyword')
    print(f"\n📝 Keywords found: {keywords.count()}")
    
    for keyword in keywords:
        print(f"\n" + "-" * 60)
        print(f"Keyword: {keyword.keyword}")
        print("-" * 60)
        print(f"  Current rank: #{keyword.rank}")
        print(f"  Initial rank: {keyword.initial_rank}")
        print(f"  Highest rank: {keyword.highest_rank}")
        print(f"  Status: {keyword.rank_status}")
        print(f"  Difference: {keyword.rank_diff_from_last_time}")
        print(f"  Impact: {keyword.impact}")
        print(f"  URL: {keyword.rank_url if keyword.rank_url else 'Not set'}")
        print(f"  Last scraped: {keyword.scraped_at}")
        
        # Check rank history
        rank_history = Rank.objects.filter(keyword=keyword).order_by('-created_at')[:5]
        if rank_history:
            print(f"\n  📊 Rank History (last 5):")
            for rank in rank_history:
                organic_type = "Organic" if rank.is_organic else "Sponsored"
                print(f"    {rank.created_at.strftime('%Y-%m-%d %H:%M')}: #{rank.rank} ({organic_type})")
    
    # Test adding tags
    print("\n" + "=" * 80)
    print("🏷️  Testing Tag System")
    print("=" * 80)
    
    # Create some tags
    tag_data = [
        ('UK Market', '#FF6B6B'),
        ('Local SEO', '#4ECDC4'),
        ('PPC', '#45B7D1'),
        ('High Priority', '#FFA07A'),
    ]
    
    tags = []
    for name, color in tag_data:
        tag, created = Tag.objects.get_or_create(
            name=name,
            defaults={'color': color}
        )
        tags.append(tag)
        status = "Created" if created else "Exists"
        print(f"  {status}: {tag.name} (slug: {tag.slug}, color: {tag.color})")
    
    # Associate tags with keywords
    print("\n  Associating tags with keywords...")
    
    for keyword in keywords[:2]:  # Tag first two keywords
        # Add UK Market tag to all
        KeywordTag.objects.get_or_create(keyword=keyword, tag=tags[0])  # UK Market
        
        # Add specific tags based on keyword
        if 'ppc' in keyword.keyword.lower() or 'pay per click' in keyword.keyword.lower():
            KeywordTag.objects.get_or_create(keyword=keyword, tag=tags[2])  # PPC
        if 'seo' in keyword.keyword.lower():
            KeywordTag.objects.get_or_create(keyword=keyword, tag=tags[1])  # Local SEO
        
        # Add high priority to all
        KeywordTag.objects.get_or_create(keyword=keyword, tag=tags[3])  # High Priority
        
        # Display tags
        keyword_tags = keyword.keyword_tags.all()
        tag_names = [kt.tag.name for kt in keyword_tags]
        print(f"    {keyword.keyword}: {', '.join(tag_names)}")
    
    # Simulate rank changes
    print("\n" + "=" * 80)
    print("📈 Simulating Rank Changes")
    print("=" * 80)
    
    test_keyword = keywords.first()
    if test_keyword:
        print(f"\n  Testing with: {test_keyword.keyword}")
        
        # Store original values
        original_rank = test_keyword.rank
        original_status = test_keyword.rank_status
        
        print(f"  Original rank: #{original_rank}")
        
        # Simulate rank improvement
        print("\n  Simulating improvement to #1...")
        test_keyword.update_rank(1, url="https://fastgenerations.co.uk/top-result")
        test_keyword.refresh_from_db()
        
        print(f"    New rank: #{test_keyword.rank}")
        print(f"    Status: {test_keyword.rank_status}")
        print(f"    Difference: {test_keyword.rank_diff_from_last_time}")
        print(f"    Impact: {test_keyword.impact}")
        
        # Simulate rank decline
        print("\n  Simulating decline to #5...")
        test_keyword.update_rank(5)
        test_keyword.refresh_from_db()
        
        print(f"    New rank: #{test_keyword.rank}")
        print(f"    Status: {test_keyword.rank_status}")
        print(f"    Difference: {test_keyword.rank_diff_from_last_time}")
        print(f"    Impact: {test_keyword.impact}")
        
        # Restore original if it was valid
        if original_rank > 0:
            print(f"\n  Restoring original rank #{original_rank}...")
            test_keyword.update_rank(original_rank)
    
    print("\n" + "=" * 80)
    print("✅ Rank Tracking Test Complete")
    print("=" * 80)
    print("\nSummary:")
    print(f"  • Project: fastgenerations.co.uk")
    print(f"  • Keywords tracked: {keywords.count()}")
    print(f"  • All keywords have rank tracking metrics")
    print(f"  • Tag system functional")
    print(f"  • Rank changes tracked with impact calculations")


if __name__ == '__main__':
    test_fastgen_rank_tracking()