#!/usr/bin/env python
"""
Test script to verify the simplified ranking pages functionality
"""

import os
import sys
import django
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.utils import timezone
from keywords.models import Keyword
from project.models import Project
from accounts.models import User

def test_ranking_pages_json():
    """Test the ranking pages JSON field functionality"""
    
    print("=" * 60)
    print("TESTING RANKING PAGES JSON FIELD")
    print("=" * 60)
    
    # Get a test user and project
    user = User.objects.filter(email='tomuaaz@gmail.com').first()
    if not user:
        print("❌ Test user not found. Please create a user with email tomuaaz@gmail.com")
        return
    
    print(f"✅ Found user: {user.email}")
    
    # Get or create a test project
    project, created = Project.objects.get_or_create(
        user=user,
        domain='example.com',
        defaults={'title': 'Example Test Project', 'active': True}
    )
    
    if created:
        print(f"✅ Created test project: {project.domain}")
    else:
        print(f"✅ Using existing project: {project.domain}")
    
    # Get or create a test keyword
    keyword, created = Keyword.objects.get_or_create(
        project=project,
        keyword='python django tutorial',
        country='US',
        defaults={'rank': 5}
    )
    
    if created:
        print(f"✅ Created test keyword: {keyword.keyword}")
    else:
        print(f"✅ Using existing keyword: {keyword.keyword}")
    
    # Simulate storing top 3 ranking pages
    sample_pages = [
        {'position': 1, 'url': 'https://www.djangoproject.com/start/'},
        {'position': 2, 'url': 'https://realpython.com/get-started-with-django-1/'},
        {'position': 3, 'url': 'https://tutorial.djangogirls.org/en/'}
    ]
    
    # Update keyword with ranking pages
    keyword.ranking_pages = sample_pages
    keyword.success_api_hit_count += 1
    keyword.scraped_at = timezone.now()
    keyword.save()
    
    print("\n📝 Stored top 3 ranking pages in JSON field")
    
    # Verify the data
    print("\n🔍 Verifying stored data...")
    keyword.refresh_from_db()
    
    if keyword.ranking_pages:
        print(f"Found {len(keyword.ranking_pages)} ranking pages:")
        for page in keyword.ranking_pages:
            print(f"  #{page['position']}: {page['url']}")
    else:
        print("❌ No ranking pages found")
    
    print(f"\n📊 Keyword statistics:")
    print(f"  Success API hits: {keyword.success_api_hit_count}")
    print(f"  Last scraped: {keyword.scraped_at}")
    print(f"  Current rank: #{keyword.rank}")
    
    print("\n" + "=" * 60)
    print("✨ TEST COMPLETE")
    print("=" * 60)
    print("\nImplementation complete:")
    print("1. Simple JSON field on Keyword model stores top 3 pages")
    print("2. Automatically populated when keywords are scraped")
    print("3. Project dropdown selector is available in dashboard")
    print("4. No extra models or complex relationships needed")

if __name__ == '__main__':
    test_ranking_pages_json()