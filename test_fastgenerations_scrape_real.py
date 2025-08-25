#!/usr/bin/env python
"""
Test script to scrape fastgenerations.co.uk keywords via Scrape.do
and store results to R2 for review
"""

import os
import sys
import django
import json
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.utils import timezone
from django.conf import settings
from keywords.models import Keyword, Rank
from keywords.tasks import fetch_keyword_serp_html
from keywords.ranking_extractor import RankingExtractor
from services.scrape_do import ScrapeDoService
from services.google_search_parser import GoogleSearchParser
from services.r2_storage import get_r2_service
from project.models import Project
from accounts.models import User


def test_fastgenerations_scraping():
    """
    Test scraping fastgenerations.co.uk keywords through actual Scrape.do API
    and store results to R2
    """
    
    print("=" * 80)
    print("🔍 Testing Scrape.do Integration for fastgenerations.co.uk")
    print("=" * 80)
    
    # Check for API key
    api_key = getattr(settings, 'SCRAPPER_API_KEY', None)
    if not api_key:
        print("❌ Error: SCRAPPER_API_KEY not found in settings")
        print("   Please set your Scrape.do API key in .env file")
        print("   Current .env has the key, so this should work")
        return
    
    print(f"✓ API Key found: {api_key[:10]}...")
    
    # Create or get project
    user, _ = User.objects.get_or_create(
        username='fastgen_test',
        defaults={'email': 'test@fastgenerations.co.uk'}
    )
    
    project, created = Project.objects.get_or_create(
        domain='fastgenerations.co.uk',
        defaults={
            'user': user,
            'title': 'Fast Generations Digital Marketing',
            'active': True
        }
    )
    
    print(f"\n✓ Project: {project.domain}")
    print(f"  Status: {'Created' if created else 'Existing'}")
    
    # UK Keywords to test
    test_keywords = [
        {
            'keyword': 'pay per click agency brixton',
            'location': 'Brixton, London, United Kingdom',
        },
        {
            'keyword': 'seo agency wandsworth',
            'location': 'Wandsworth, London, United Kingdom',
        },
        {
            'keyword': 'digital marketing agency clapham',
            'location': 'Clapham, London, United Kingdom',
        }
    ]
    
    print("\n📝 Keywords to test:")
    keywords = []
    for kw_data in test_keywords:
        keyword, created = Keyword.objects.get_or_create(
            project=project,
            keyword=kw_data['keyword'],
            country='UK',
            defaults={
                'country_code': 'GB',
                'location': kw_data['location'],
                'processing': False,
                'scraped_at': None  # Force fresh scrape
            }
        )
        
        # Reset for fresh scrape
        if not created:
            keyword.processing = False
            keyword.save()
        
        keywords.append(keyword)
        print(f"  • {keyword.keyword}")
        print(f"    Location: {kw_data['location']}")
        print(f"    ID: {keyword.id}")
    
    # Test with one keyword first
    test_keyword = keywords[0]
    print(f"\n🚀 Testing with: {test_keyword.keyword}")
    
    # Direct Scrape.do API Test
    print("\n" + "-" * 40)
    print("Direct Scrape.do API Test")
    print("-" * 40)
    
    scraper = ScrapeDoService()
    print(f"  Calling Scrape.do API...")
    
    try:
        result = scraper.scrape_google_search(
            query=test_keyword.keyword,
            country_code='GB',
            num_results=100,
            location=test_keyword.location,
            use_exact_location=False
        )
        
        if result and result.get('status_code') == 200:
            print(f"  ✓ Scrape successful! Status: {result['status_code']}")
            html_content = result.get('html', '')
            print(f"  HTML size: {len(html_content):,} bytes")
            
            # Parse the HTML
            print(f"\n  Parsing HTML with GoogleSearchParser...")
            parser = GoogleSearchParser()
            parsed_results = parser.parse(html_content)
            
            if parsed_results:
                print(f"  ✓ Parsing successful!")
                print(f"    Organic results: {len(parsed_results.get('organic_results', []))}")
                print(f"    Sponsored results: {len(parsed_results.get('sponsored_results', []))}")
                
                # Check if fastgenerations.co.uk is ranking
                our_rank = 0
                for i, r in enumerate(parsed_results.get('organic_results', [])[:100], 1):
                    if 'fastgenerations.co.uk' in r.get('url', ''):
                        our_rank = i
                        print(f"\n  🎯 Found fastgenerations.co.uk at position #{our_rank}")
                        print(f"     Title: {r.get('title')}")
                        print(f"     URL: {r.get('url')}")
                        break
                
                if not our_rank:
                    print(f"\n  ⚠️ fastgenerations.co.uk not found in top 100")
                
                # Store to R2
                print(f"\n  📤 Storing to R2...")
                r2_service = get_r2_service()
                
                # Build R2 path
                date_str = datetime.now().strftime('%Y-%m-%d')
                clean_keyword = test_keyword.keyword.lower().replace(' ', '-').replace('/', '-')
                r2_path = f"{project.domain}/{clean_keyword}/{date_str}.json"
                
                # Prepare data with metadata
                r2_data = {
                    'keyword': test_keyword.keyword,
                    'project_id': project.id,
                    'project_domain': project.domain,
                    'country': 'UK',
                    'location': test_keyword.location,
                    'scraped_at': timezone.now().isoformat(),
                    'scraped_via': 'scrape_do',
                    'results': parsed_results
                }
                
                upload_result = r2_service.upload_json(r2_data, r2_path)
                
                if upload_result.get('success'):
                    print(f"  ✓ Stored to R2: {r2_path}")
                    
                    # Generate presigned URL for review
                    url_result = r2_service.generate_presigned_url(r2_path, expiry=3600)
                    if url_result.get('success'):
                        print(f"\n  📎 Review URL (valid for 1 hour):")
                        print(f"     {url_result['url']}")
                    else:
                        print(f"  ❌ Failed to generate review URL: {url_result.get('error')}")
                else:
                    print(f"  ❌ R2 upload failed: {upload_result.get('error')}")
                
                # Save sample locally too
                local_file = f"scrape_do_result_{clean_keyword}.json"
                with open(local_file, 'w') as f:
                    json.dump(r2_data, f, indent=2)
                print(f"\n  💾 Also saved locally: {local_file}")
                
            else:
                print(f"  ❌ Failed to parse HTML")
        else:
            status = result.get('status_code', 'Unknown') if result else 'No response'
            print(f"  ❌ Scrape failed! Status: {status}")
            if result and result.get('error'):
                print(f"     Error: {result['error']}")
    
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test via Task System
    print("\n" + "-" * 40)
    print("Via Task System (Production Method)")
    print("-" * 40)
    
    print(f"  Triggering fetch_keyword_serp_html task...")
    print(f"  Keyword ID: {test_keyword.id}")
    
    # Reset processing flag
    test_keyword.processing = False
    test_keyword.scraped_at = None  # Force fresh scrape
    test_keyword.save()
    
    # Execute the task synchronously for testing
    try:
        fetch_keyword_serp_html(test_keyword.id)
        print(f"  ✓ Task completed")
        
        # Check results
        test_keyword.refresh_from_db()
        if test_keyword.scraped_at:
            print(f"  ✓ Keyword scraped at: {test_keyword.scraped_at}")
            print(f"    Rank: #{test_keyword.rank if test_keyword.rank else 'Not ranked'}")
            print(f"    Success count: {test_keyword.success_api_hit_count}")
            
            # Check if Rank record was created
            latest_rank = Rank.objects.filter(keyword=test_keyword).order_by('-created_at').first()
            if latest_rank:
                print(f"\n  📊 Rank Record:")
                print(f"    Position: #{latest_rank.rank}")
                print(f"    Organic: {latest_rank.is_organic}")
                print(f"    Has map: {latest_rank.has_map_result}")
                print(f"    Has video: {latest_rank.has_video_result}")
                print(f"    R2 file: {latest_rank.search_results_file}")
                
                # Get presigned URL for the R2 file
                if latest_rank.search_results_file:
                    r2_service = get_r2_service()
                    url_result = r2_service.generate_presigned_url(
                        latest_rank.search_results_file, 
                        expiry=3600
                    )
                    if url_result.get('success'):
                        print(f"\n  📎 R2 JSON Review URL (valid for 1 hour):")
                        print(f"     {url_result['url']}")
        else:
            print(f"  ⚠️ Keyword not scraped")
            if test_keyword.last_error_message:
                print(f"     Error: {test_keyword.last_error_message}")
    
    except Exception as e:
        print(f"  ❌ Task error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("📋 Summary:")
    print(f"  • Project: fastgenerations.co.uk")
    print(f"  • Keyword: {test_keyword.keyword}")
    print(f"  • Location: {test_keyword.location}")
    print(f"  • Country: UK")
    print(f"  • Scraping: Via Scrape.do API")
    print(f"  • Storage: R2 bucket")
    print(f"  • Path format: domain/keyword/date.json")
    print("=" * 80)


if __name__ == '__main__':
    test_fastgenerations_scraping()