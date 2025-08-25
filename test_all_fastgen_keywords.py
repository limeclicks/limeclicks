#!/usr/bin/env python
"""
Test all three fastgenerations.co.uk keywords via Scrape.do API
"""

import os
import sys
import django
import json
from datetime import datetime
import time

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.utils import timezone
from django.conf import settings
from keywords.models import Keyword
from keywords.tasks import fetch_keyword_serp_html
from services.r2_storage import get_r2_service
from project.models import Project
from accounts.models import User


def test_all_keywords():
    """Test all three UK keywords for fastgenerations.co.uk"""
    
    print("=" * 80)
    print("🔍 Testing All fastgenerations.co.uk Keywords via Scrape.do")
    print("=" * 80)
    
    # Get project
    project = Project.objects.get(domain='fastgenerations.co.uk')
    print(f"\n✓ Project: {project.domain}")
    
    # Get all keywords for this project
    keywords = Keyword.objects.filter(
        project=project,
        country='UK'
    ).order_by('id')
    
    print(f"\n📝 Found {keywords.count()} keywords to test:")
    
    results_summary = []
    r2_service = get_r2_service()
    
    for idx, keyword in enumerate(keywords, 1):
        print(f"\n" + "=" * 60)
        print(f"[{idx}/{keywords.count()}] Testing: {keyword.keyword}")
        print("=" * 60)
        print(f"  Location: {keyword.location}")
        print(f"  ID: {keyword.id}")
        
        # Reset for fresh scrape
        keyword.processing = False
        keyword.scraped_at = None
        keyword.save()
        
        # Execute the task
        try:
            print(f"  ⏳ Scraping via Scrape.do...")
            fetch_keyword_serp_html(keyword.id)
            
            # Refresh from DB
            keyword.refresh_from_db()
            
            if keyword.scraped_at:
                print(f"  ✓ Successfully scraped!")
                print(f"    Rank: #{keyword.rank if keyword.rank else 'Not ranked'}")
                print(f"    Status: {keyword.rank_status}")
                
                # Generate R2 URL
                date_str = datetime.now().strftime('%Y-%m-%d')
                clean_keyword = keyword.keyword.lower().replace(' ', '-').replace('/', '-')
                r2_path = f"{project.domain}/{clean_keyword}/{date_str}.json"
                
                url_result = r2_service.generate_presigned_url(r2_path, expiry=7200)
                
                result_data = {
                    'keyword': keyword.keyword,
                    'rank': keyword.rank,
                    'status': 'Success',
                    'r2_path': r2_path,
                    'review_url': url_result.get('url') if url_result.get('success') else None
                }
                results_summary.append(result_data)
                
                if url_result.get('success'):
                    print(f"\n  📎 Review URL (valid for 2 hours):")
                    print(f"     {url_result['url']}")
                
            else:
                print(f"  ❌ Failed to scrape")
                if keyword.last_error_message:
                    print(f"     Error: {keyword.last_error_message}")
                
                results_summary.append({
                    'keyword': keyword.keyword,
                    'rank': None,
                    'status': 'Failed',
                    'error': keyword.last_error_message
                })
        
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results_summary.append({
                'keyword': keyword.keyword,
                'rank': None,
                'status': 'Error',
                'error': str(e)
            })
        
        # Small delay between API calls
        if idx < keywords.count():
            print(f"\n  ⏸️  Waiting 2 seconds before next keyword...")
            time.sleep(2)
    
    # Print summary
    print("\n" + "=" * 80)
    print("📊 RESULTS SUMMARY")
    print("=" * 80)
    
    for result in results_summary:
        status_icon = "✓" if result['status'] == 'Success' else "❌"
        rank_str = f"#{result['rank']}" if result.get('rank') else "Not ranked"
        print(f"\n{status_icon} {result['keyword']}")
        print(f"   Status: {result['status']}")
        print(f"   Rank: {rank_str}")
        if result.get('r2_path'):
            print(f"   R2 Path: {result['r2_path']}")
        if result.get('review_url'):
            print(f"   Review: {result['review_url'][:80]}...")
        if result.get('error'):
            print(f"   Error: {result['error']}")
    
    # Save summary to file
    summary_file = f"fastgen_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_file, 'w') as f:
        json.dump({
            'domain': project.domain,
            'tested_at': timezone.now().isoformat(),
            'results': results_summary
        }, f, indent=2)
    
    print(f"\n💾 Summary saved to: {summary_file}")
    
    # Stats
    success_count = sum(1 for r in results_summary if r['status'] == 'Success')
    rank1_count = sum(1 for r in results_summary if r.get('rank') == 1)
    
    print("\n" + "=" * 80)
    print("📈 STATISTICS")
    print("=" * 80)
    print(f"  Total keywords: {len(results_summary)}")
    print(f"  Successful scrapes: {success_count}/{len(results_summary)}")
    print(f"  Ranking #1: {rank1_count}/{len(results_summary)}")
    print(f"  Domain: fastgenerations.co.uk")
    print(f"  Country: UK")
    print(f"  Storage: R2 ({project.domain}/keyword/date.json)")
    print("=" * 80)


if __name__ == '__main__':
    test_all_keywords()