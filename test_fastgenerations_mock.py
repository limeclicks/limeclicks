#!/usr/bin/env python
"""
Mock test for fastgenerations.co.uk that simulates Scrape.do response
and stores to R2 for testing purposes
"""

import os
import sys
import django
import json
from datetime import datetime
from unittest.mock import Mock, patch

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.utils import timezone
from keywords.models import Keyword, Rank
from keywords.ranking_extractor import RankingExtractor
from services.r2_storage import get_r2_service
from project.models import Project
from accounts.models import User
from tests.test_uk_rankings import create_uk_serp_results


def mock_scrape_do_response(keyword_text):
    """
    Create a mock HTML response that would come from Scrape.do
    This simulates what Scrape.do would return for fastgenerations.co.uk
    """
    # For testing, we'll create HTML that contains the key elements
    # that GoogleSearchParser would look for
    
    html_template = '''
    <!DOCTYPE html>
    <html>
    <head><title>{keyword} - Google Search</title></head>
    <body>
        <div id="result-stats">About 2,340,000 results (0.52 seconds)</div>
        
        <!-- Organic Result #1 - fastgenerations.co.uk -->
        <div class="g">
            <div class="yuRUbf">
                <a href="https://fastgenerations.co.uk/services/{keyword_slug}/">
                    <h3 class="LC20lb">Expert {service_type} | Fast Generations</h3>
                </a>
                <cite>fastgenerations.co.uk › services › {keyword_slug}</cite>
            </div>
            <div class="VwiC3b">
                Leading {service_type} in {location}. We deliver ROI-focused campaigns with proven results. 
                Get a free consultation today!
            </div>
        </div>
        
        <!-- More organic results -->
        <div class="g">
            <div class="yuRUbf">
                <a href="https://clickslice.co.uk/{keyword_slug}/">
                    <h3 class="LC20lb">Digital Marketing Services {location} | Clickslice</h3>
                </a>
            </div>
        </div>
        
        <!-- Local pack -->
        <div class="local-pack">
            <div class="business">Fast Generations Digital Marketing - 4.9 stars - 127 reviews</div>
        </div>
        
        <!-- People also ask -->
        <div class="related-question">How much does {service_type} cost in the UK?</div>
    </body>
    </html>
    '''.format(
        keyword=keyword_text,
        keyword_slug=keyword_text.replace(' ', '-'),
        service_type=keyword_text.replace(' agency', '').title(),
        location=keyword_text.split()[-1].title()
    )
    
    return html_template


def test_fastgenerations_with_mock():
    """
    Test fastgenerations.co.uk with mock Scrape.do response
    Store results to R2 for review
    """
    
    print("=" * 80)
    print("🔍 Testing fastgenerations.co.uk with Mock Scrape.do Response")
    print("=" * 80)
    
    # Create or get project
    user, _ = User.objects.get_or_create(
        username='fastgen_mock_test',
        defaults={'email': 'mocktest@fastgenerations.co.uk'}
    )
    
    project, _ = Project.objects.get_or_create(
        domain='fastgenerations.co.uk',
        defaults={
            'user': user,
            'title': 'Fast Generations Digital Marketing',
            'active': True
        }
    )
    
    print(f"\n✓ Project: {project.domain}")
    
    # Test keywords
    test_keywords = [
        ('pay per click agency brixton', 'Brixton, London, United Kingdom'),
        ('seo agency wandsworth', 'Wandsworth, London, United Kingdom'),
        ('digital marketing agency clapham', 'Clapham, London, United Kingdom'),
    ]
    
    for keyword_text, location in test_keywords:
        print(f"\n" + "=" * 60)
        print(f"Testing: {keyword_text}")
        print("=" * 60)
        
        # Create keyword
        keyword, _ = Keyword.objects.get_or_create(
            project=project,
            keyword=keyword_text,
            country='UK',
            defaults={
                'country_code': 'GB',
                'location': location,
            }
        )
        
        # Create realistic SERP data (as if parsed from Scrape.do HTML)
        print("  Creating mock parsed results...")
        parsed_results = create_uk_serp_results(
            domain=project.domain,
            keyword=keyword_text,
            rank_position=1  # fastgenerations.co.uk ranks #1
        )
        
        # Verify our domain is in position 1
        first_result = parsed_results['organic_results'][0] if parsed_results['organic_results'] else None
        if first_result and 'fastgenerations.co.uk' in first_result.get('url', ''):
            print(f"  ✓ Confirmed: fastgenerations.co.uk at position #{first_result['position']}")
        
        # Store to R2
        print(f"\n  📤 Storing to R2...")
        r2_service = get_r2_service()
        
        # Build R2 path (new format: domain/keyword/date.json)
        date_str = datetime.now().strftime('%Y-%m-%d')
        clean_keyword = keyword_text.lower().replace(' ', '-').replace('/', '-')
        r2_path = f"{project.domain}/{clean_keyword}/{date_str}.json"
        
        # Prepare complete data structure
        r2_data = {
            'keyword': keyword_text,
            'project_id': project.id,
            'project_domain': project.domain,
            'country': 'UK',
            'location': location,
            'scraped_at': timezone.now().isoformat(),
            'scraped_via': 'scrape_do_mock',  # Indicate this is mock data
            'results': parsed_results
        }
        
        # Upload to R2
        try:
            upload_result = r2_service.upload_json(r2_data, r2_path)
            
            if upload_result.get('success'):
                print(f"  ✓ Successfully stored to R2")
                print(f"    Path: {r2_path}")
                print(f"    Size: {upload_result.get('size', 'Unknown')} bytes")
                
                # Generate presigned URL for review
                url_result = r2_service.generate_presigned_url(r2_path, expiry=3600)
                if url_result.get('success'):
                    print(f"\n  📎 Review URL (valid for 1 hour):")
                    print(f"     {url_result['url']}")
                    print(f"\n  You can download and review the JSON at this URL")
            else:
                print(f"  ❌ R2 upload failed: {upload_result.get('error')}")
        
        except Exception as e:
            print(f"  ❌ Error uploading to R2: {e}")
        
        # Also save locally for inspection
        local_file = f"mock_serp_{clean_keyword}.json"
        with open(local_file, 'w') as f:
            json.dump(r2_data, f, indent=2)
        print(f"\n  💾 Also saved locally: {local_file}")
        
        # Create Rank record using RankingExtractor
        print(f"\n  📊 Processing ranking...")
        extractor = RankingExtractor()
        
        # Mock the parser to return our data
        with patch.object(extractor, '_parse_html', return_value=parsed_results):
            # Mock R2 upload
            with patch.object(extractor.r2_service, 'upload_json', return_value={'success': True}):
                result = extractor.process_serp_html(
                    keyword,
                    mock_scrape_do_response(keyword_text),  # Mock HTML
                    timezone.now()
                )
                
                if result and result.get('success'):
                    print(f"  ✓ Ranking processed")
                    print(f"    Position: #{result['rank']}")
                    print(f"    Organic: {result['is_organic']}")
                    
                    # Update keyword
                    keyword.refresh_from_db()
                    print(f"    Keyword rank updated: #{keyword.rank}")
                    print(f"    Status: {keyword.rank_status}")
    
    print("\n" + "=" * 80)
    print("📋 Summary:")
    print(f"  • Domain: fastgenerations.co.uk")
    print(f"  • Keywords tested: {len(test_keywords)}")
    print(f"  • All ranking #1 (mock data)")
    print(f"  • Data stored to R2 for review")
    print(f"  • Path format: domain/keyword/YYYY-MM-DD.json")
    print("\n  Note: This uses mock data simulating Scrape.do response")
    print("  For real scraping, configure SCRAPE_DO_API_KEY in .env")
    print("=" * 80)


if __name__ == '__main__':
    test_fastgenerations_with_mock()