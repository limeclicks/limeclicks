#!/usr/bin/env python
"""
Verify fastgenerations.co.uk data in R2 storage
"""

import os
import sys
import django
import json
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from services.r2_storage import get_r2_service
from project.models import Project
from keywords.models import Keyword, Rank


def verify_r2_data():
    """Verify and display fastgenerations.co.uk data stored in R2"""
    
    print("=" * 80)
    print("🔍 Verifying fastgenerations.co.uk Data in R2 Storage")
    print("=" * 80)
    
    r2_service = get_r2_service()
    project = Project.objects.get(domain='fastgenerations.co.uk')
    
    print(f"\n✓ Project: {project.domain}")
    print(f"  Title: {project.title}")
    
    # List all files for this domain
    prefix = f"{project.domain}/"
    files = r2_service.list_files(prefix=prefix, max_keys=100)
    
    print(f"\n📁 Found {len(files)} files in R2 for {project.domain}:")
    
    for file_path in sorted(files):
        print(f"\n  📄 {file_path}")
        
        # Get file info
        file_info = r2_service.get_file_info(file_path)
        if file_info:
            print(f"     Size: {file_info['size']:,} bytes")
            print(f"     Modified: {file_info['last_modified']}")
            
            # Download and check content
            json_data = r2_service.download_json(file_path)
            if json_data:
                print(f"     Keyword: {json_data.get('keyword')}")
                print(f"     Location: {json_data.get('location')}")
                print(f"     Scraped: {json_data.get('scraped_at')}")
                
                results = json_data.get('results', {})
                organic = results.get('organic_results', [])
                sponsored = results.get('sponsored_results', [])
                
                print(f"     Organic results: {len(organic)}")
                print(f"     Sponsored results: {len(sponsored)}")
                
                # Check if fastgenerations.co.uk is ranking
                for idx, result in enumerate(organic[:10], 1):
                    if 'fastgenerations.co.uk' in result.get('url', ''):
                        print(f"     🎯 Ranking: #{idx} - {result.get('title')}")
                        break
                
                # Generate review URL
                url_result = r2_service.generate_presigned_url(file_path, expiry=3600)
                if url_result.get('success'):
                    print(f"     📎 Review URL (1 hour): {url_result['url'][:80]}...")
    
    # Check database records
    print(f"\n\n📊 Database Records:")
    keywords = Keyword.objects.filter(project=project).order_by('keyword')
    
    for keyword in keywords:
        print(f"\n  🔑 {keyword.keyword}")
        print(f"     ID: {keyword.id}")
        print(f"     Location: {keyword.location}")
        print(f"     Last scraped: {keyword.scraped_at}")
        print(f"     Current rank: #{keyword.rank if keyword.rank else 'Not ranked'}")
        print(f"     Status: {keyword.rank_status}")
        
        # Get latest rank record
        latest_rank = Rank.objects.filter(keyword=keyword).order_by('-created_at').first()
        if latest_rank:
            print(f"     Latest rank record: #{latest_rank.rank} (Organic: {latest_rank.is_organic})")
            print(f"     R2 file: {latest_rank.search_results_file}")
    
    print("\n" + "=" * 80)
    print("✅ Verification Complete")
    print(f"   • Domain: fastgenerations.co.uk")
    print(f"   • Files in R2: {len(files)}")
    print(f"   • Keywords tracked: {keywords.count()}")
    print(f"   • Storage format: domain/keyword/YYYY-MM-DD.json")
    print("=" * 80)


if __name__ == '__main__':
    verify_r2_data()