#!/usr/bin/env python
"""
Demo script showing UK rankings for fastgenerations.co.uk
"""

import json
import os
import sys
import django
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.utils import timezone
from keywords.models import Keyword, Rank
from project.models import Project
from accounts.models import User
from tests.test_uk_rankings import create_uk_serp_results


def demo_uk_rankings():
    """Demonstrate UK ranking data structure for fastgenerations.co.uk"""
    
    print("=" * 80)
    print("🇬🇧 UK SERP Rankings Demo - fastgenerations.co.uk")
    print("=" * 80)
    
    # Create or get demo project
    user, _ = User.objects.get_or_create(
        username='uk_demo_user',
        defaults={'email': 'demo@fastgenerations.co.uk'}
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
    print(f"  Title: {project.title}")
    
    # UK Keywords where fastgenerations.co.uk ranks #1
    uk_keywords = [
        {
            'keyword': 'pay per click agency brixton',
            'location': 'Brixton, London, United Kingdom',
            'rank': 1
        },
        {
            'keyword': 'seo agency wandsworth',
            'location': 'Wandsworth, London, United Kingdom',
            'rank': 1
        },
        {
            'keyword': 'digital marketing agency clapham',
            'location': 'Clapham, London, United Kingdom',
            'rank': 1
        }
    ]
    
    print("\n📝 UK Keywords (Ranking #1):")
    for kw_data in uk_keywords:
        keyword, created = Keyword.objects.get_or_create(
            project=project,
            keyword=kw_data['keyword'],
            country='UK',
            defaults={
                'country_code': 'GB',
                'location': kw_data['location']
            }
        )
        status = "✨ Created" if created else "✓ Exists"
        print(f"  {status}: {keyword.keyword}")
        print(f"    Location: {kw_data['location']}")
        print(f"    Expected Rank: #{kw_data['rank']}")
    
    # Generate sample SERP data
    print("\n" + "=" * 80)
    print("📊 Sample SERP Data Structure")
    print("=" * 80)
    
    for kw_data in uk_keywords[:1]:  # Show first keyword only for demo
        print(f"\n🔍 Keyword: '{kw_data['keyword']}'")
        print(f"   Location: {kw_data['location']}")
        print(f"   Country: UK")
        
        # Generate realistic SERP data
        serp_data = create_uk_serp_results(
            domain='fastgenerations.co.uk',
            keyword=kw_data['keyword'],
            rank_position=1
        )
        
        # Build the complete JSON structure as it would be stored in R2
        complete_json = {
            'keyword': kw_data['keyword'],
            'project_id': project.id,
            'project_domain': project.domain,
            'country': 'UK',
            'location': kw_data['location'],
            'scraped_at': timezone.now().isoformat(),
            'results': serp_data
        }
        
        # Display summary
        print(f"\n📈 SERP Summary:")
        print(f"   Total Results: {serp_data['total_results']}")
        print(f"   Search Time: {serp_data['search_time']}")
        print(f"   Organic Results: {serp_data['organic_count']}")
        print(f"   Sponsored Results: {serp_data['sponsored_count']}")
        
        # Check our ranking
        our_rank = None
        for result in serp_data['organic_results']:
            if 'fastgenerations.co.uk' in result['url']:
                our_rank = result['position']
                break
        
        print(f"   Our Ranking: #{our_rank if our_rank else 'Not Found'}")
        
        # SERP Features
        print(f"\n🎯 SERP Features Present:")
        if serp_data.get('featured_snippet'):
            print(f"   ✓ Featured Snippet")
        if serp_data.get('local_pack'):
            print(f"   ✓ Local Pack ({len(serp_data['local_pack'])} businesses)")
        if serp_data.get('people_also_ask'):
            print(f"   ✓ People Also Ask ({len(serp_data['people_also_ask'])} questions)")
        if serp_data.get('related_searches'):
            print(f"   ✓ Related Searches ({len(serp_data['related_searches'])} suggestions)")
        
        # Show top 3 organic results
        print(f"\n🏆 Top 3 Organic Results:")
        for result in serp_data['organic_results'][:3]:
            print(f"   #{result['position']}: {result['title']}")
            print(f"       URL: {result['url']}")
            if result.get('sitelinks'):
                print(f"       Sitelinks: {', '.join([s['title'] for s in result['sitelinks']])}")
        
        # Show sponsored results
        if serp_data['sponsored_results']:
            print(f"\n💰 Sponsored Results:")
            for ad in serp_data['sponsored_results']:
                print(f"   Ad #{ad['position']}: {ad['title']}")
                print(f"      {ad['displayed_url']}")
        
        # Show local pack
        if serp_data.get('local_pack'):
            print(f"\n📍 Local Pack:")
            for business in serp_data['local_pack'][:2]:
                print(f"   • {business['name']}")
                print(f"     Rating: {business['rating']}⭐ ({business['reviews']} reviews)")
                print(f"     Address: {business['address']}")
        
        # Featured snippet
        if serp_data.get('featured_snippet'):
            print(f"\n✨ Featured Snippet:")
            snippet = serp_data['featured_snippet']
            print(f"   {snippet['text'][:200]}...")
            print(f"   Source: {snippet['source']}")
        
        # Export sample JSON
        output_file = f"sample_uk_serp_{kw_data['keyword'].replace(' ', '_')}.json"
        print(f"\n💾 Exporting complete JSON structure to: {output_file}")
        
        with open(output_file, 'w') as f:
            json.dump(complete_json, f, indent=2)
        
        print(f"   File size: {os.path.getsize(output_file):,} bytes")
        
        # Show R2 path format
        clean_keyword = kw_data['keyword'].lower().replace(' ', '-')
        r2_path = f"{project.domain}/{clean_keyword}/{datetime.now().strftime('%Y-%m-%d')}.json"
        print(f"\n☁️  R2 Storage Path: {r2_path}")
    
    print("\n" + "=" * 80)
    print("📝 Key Points:")
    print("  • Domain fastgenerations.co.uk ranks #1 for all 3 keywords")
    print("  • Complete JSON includes 100 organic + sponsored results")
    print("  • UK-specific features: Local Pack, GBP pricing, UK competitors")
    print("  • SERP features properly populated (snippet, PAA, local pack)")
    print("  • R2 path format: domain/keyword/YYYY-MM-DD.json")
    print("=" * 80)


if __name__ == '__main__':
    demo_uk_rankings()