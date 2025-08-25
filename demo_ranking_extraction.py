#!/usr/bin/env python
"""
Demo script showing the complete SERP fetch and ranking extraction flow
"""

import os
import sys
import django
from datetime import datetime, timedelta
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.utils import timezone
from keywords.models import Keyword, Rank
from keywords.tasks import fetch_keyword_serp_html
from keywords.ranking_extractor import process_stored_html
from project.models import Project
from accounts.models import User


def demo_ranking_extraction():
    """Demonstrate the complete ranking extraction flow"""
    
    print("=" * 60)
    print("SERP Fetch and Ranking Extraction Demo")
    print("=" * 60)
    
    # Get or create demo user and project
    user, _ = User.objects.get_or_create(
        username='demo_user',
        defaults={'email': 'demo@example.com'}
    )
    
    project, _ = Project.objects.get_or_create(
        domain='example.com',
        defaults={
            'user': user,
            'title': 'Demo Project',
            'active': True
        }
    )
    
    print(f"\n✓ Using project: {project.domain}")
    
    # Create test keywords
    keywords_data = [
        {'keyword': 'python tutorial', 'country': 'US'},
        {'keyword': 'web scraping guide', 'country': 'US'},
        {'keyword': 'django best practices', 'country': 'US'},
    ]
    
    print("\n📝 Creating test keywords:")
    for kw_data in keywords_data:
        keyword, created = Keyword.objects.get_or_create(
            project=project,
            keyword=kw_data['keyword'],
            country=kw_data['country'],
            defaults={'country_code': kw_data['country']}
        )
        status = "✨ Created" if created else "✓ Exists"
        print(f"  {status}: {keyword.keyword}")
    
    # Show the workflow
    print("\n🔄 Workflow Overview:")
    print("  1. Fetch SERP HTML from Scrape.do API")
    print("  2. Store HTML locally with 7-day rotation")
    print("  3. Parse HTML using GoogleSearchParser")
    print("  4. Store parsed JSON in R2 cloud storage")
    print("  5. Extract domain ranking (1-100)")
    print("  6. Create Rank record with SERP features")
    print("  7. Update Keyword with latest rank")
    
    # Demonstrate ranking extraction for a keyword
    keyword = Keyword.objects.filter(project=project).first()
    if keyword:
        print(f"\n🎯 Demo keyword: {keyword.keyword}")
        print(f"  Current rank: {keyword.rank if keyword.rank else 'Not ranked'}")
        print(f"  Last scraped: {keyword.scraped_at if keyword.scraped_at else 'Never'}")
        
        # Check if we have any stored HTML files
        if keyword.scrape_do_files:
            print(f"\n📁 Stored HTML files: {len(keyword.scrape_do_files)}")
            for file_path in keyword.scrape_do_files[:3]:
                print(f"    • {file_path}")
            
            # Demo ranking extraction from stored HTML
            latest_file = keyword.scrape_do_files[0]
            print(f"\n🔍 Processing latest HTML: {latest_file}")
            
            # Note: This would normally process the HTML and extract rankings
            # In production, this happens automatically after fetch
            print("  → Parse HTML with GoogleSearchParser")
            print("  → Store parsed JSON in R2")
            print("  → Extract ranking for domain: example.com")
            print("  → Create Rank record with features")
        
        # Show ranking history
        ranks = Rank.objects.filter(keyword=keyword).order_by('-created_at')[:5]
        if ranks:
            print(f"\n📊 Ranking History (last 5):")
            for rank in ranks:
                rank_type = "Organic" if rank.is_organic else "Sponsored"
                features = []
                if rank.has_map_result:
                    features.append("📍Map")
                if rank.has_video_result:
                    features.append("🎥Video")
                if rank.has_image_result:
                    features.append("🖼️Image")
                features_str = " ".join(features) if features else "None"
                
                print(f"  {rank.created_at.strftime('%Y-%m-%d')}: "
                      f"#{rank.rank} ({rank_type}) | Features: {features_str}")
    
    # Show queue configuration
    print("\n⚡ Queue Configuration:")
    print("  • serp_high (priority 10): Cold keywords (no rank)")
    print("  • serp_default (priority 5): Regular keywords")
    print("  • Minimum fetch interval: 24 hours")
    print("  • HTML retention: 7 days")
    
    # Show how to trigger fetching
    print("\n🚀 To trigger SERP fetching:")
    print("  1. Manual: fetch_keyword_serp_html.delay(keyword_id)")
    print("  2. Scheduled: enqueue_daily_keyword_scrapes() via Celery Beat")
    print("  3. API: POST /api/keywords/{id}/fetch/")
    
    print("\n✅ Demo complete!")
    print("\n📝 Key Features:")
    print("  • Automatic ranking extraction after fetch")
    print("  • Domain matching with subdomain support")
    print("  • SERP feature detection (maps, videos, images)")
    print("  • Organic vs sponsored result differentiation")
    print("  • Historical ranking tracking")
    print("  • Idempotent same-day fetches")
    print("  • Atomic file writes with cleanup")
    print("  • Redis-based distributed locking")


if __name__ == '__main__':
    demo_ranking_extraction()