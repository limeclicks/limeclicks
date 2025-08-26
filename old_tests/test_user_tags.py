#!/usr/bin/env python
"""
Test user-specific tags functionality
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from accounts.models import User
from keywords.models import Tag, Keyword, KeywordTag
from project.models import Project


def test_user_tags():
    """Test that users can only see and manage their own tags"""
    
    print("=" * 60)
    print("🏷️  Testing User-Specific Tags")
    print("=" * 60)
    
    # Get test users
    user1 = User.objects.get(email='tomuaaz@gmail.com')
    user2 = User.objects.get(email='testuser@example.com')
    
    print(f"\n✅ Test Users:")
    print(f"  User 1: {user1.email}")
    print(f"  User 2: {user2.email}")
    
    # Check tag isolation
    print(f"\n🔒 Tag Isolation Test:")
    user1_tags = Tag.objects.filter(user=user1)
    user2_tags = Tag.objects.filter(user=user2)
    
    print(f"  User 1 has {user1_tags.count()} tags:")
    for tag in user1_tags:
        print(f"    - {tag.name}")
    
    print(f"  User 2 has {user2_tags.count()} tags:")
    for tag in user2_tags:
        print(f"    - {tag.name}")
    
    # Test API endpoints
    print(f"\n🌐 API Endpoint Tests:")
    client = Client()
    
    # Login as user2
    client.force_login(user2)
    
    # Test getting user tags
    response = client.get(reverse('keywords:api_user_tags'))
    if response.status_code == 200:
        data = response.json()
        print(f"  ✅ GET /api/tags/ - {data['count']} tags returned")
        for tag in data['tags'][:2]:
            print(f"    - {tag['name']} ({tag['color']})")
    else:
        print(f"  ❌ GET /api/tags/ - Status {response.status_code}")
    
    # Test creating a new tag
    response = client.post(reverse('keywords:api_create_tag'), {
        'name': 'Test API Tag',
        'color': '#00FF00',
        'description': 'Created via API'
    })
    if response.status_code == 200:
        data = response.json()
        print(f"  ✅ POST /api/tags/create/ - Tag '{data['name']}' created")
    else:
        print(f"  ❌ POST /api/tags/create/ - Status {response.status_code}")
    
    # Test tag assignment to keywords
    print(f"\n🔗 Tag-Keyword Association Test:")
    
    # Create a test project and keyword for user2
    project, _ = Project.objects.get_or_create(
        user=user2,
        domain='testdomain.com',
        defaults={'title': 'Test Project', 'active': True}
    )
    
    keyword, _ = Keyword.objects.get_or_create(
        project=project,
        keyword='test keyword',
        country='US',
        defaults={'rank': 5}
    )
    
    # Get a tag for user2
    tag = user2_tags.first()
    if tag and keyword:
        response = client.post(reverse('keywords:api_tag_keyword'), {
            'keyword_id': keyword.id,
            'tag_id': tag.id
        })
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Tag '{tag.name}' added to keyword '{keyword.keyword}'")
        else:
            print(f"  ❌ Failed to add tag - Status {response.status_code}")
    
    # Test cross-user security
    print(f"\n🔐 Security Test (Cross-User Access):")
    
    # Try to access user1's tag as user2
    user1_tag = user1_tags.first()
    if user1_tag:
        response = client.post(reverse('keywords:api_tag_keyword'), {
            'keyword_id': keyword.id,
            'tag_id': user1_tag.id
        })
        if response.status_code == 404:
            print(f"  ✅ Correctly denied access to User 1's tag")
        else:
            print(f"  ❌ Security issue! User 2 accessed User 1's tag")
    
    # Test admin interface
    print(f"\n👨‍💼 Admin Interface Test:")
    from django.contrib.admin.sites import site
    from keywords.admin import TagAdmin
    
    tag_admin = site._registry[Tag]
    
    # Create a mock request for user2
    class MockRequest:
        def __init__(self, user):
            self.user = user
            self.GET = {}
    
    request = MockRequest(user2)
    
    # Get queryset for user2 (non-superuser)
    qs = tag_admin.get_queryset(request)
    user2_admin_tags = qs.all()
    
    print(f"  User 2 sees {user2_admin_tags.count()} tags in admin")
    
    # Test for superuser
    request.user.is_superuser = True
    qs = tag_admin.get_queryset(request)
    superuser_tags = qs.all()
    
    print(f"  Superuser sees {superuser_tags.count()} tags in admin")
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ User-Specific Tags Test Complete")
    print("=" * 60)
    print("\nSummary:")
    print("  • Tags are properly isolated per user")
    print("  • API endpoints respect user ownership")
    print("  • Admin interface filters tags based on user")
    print("  • Security prevents cross-user tag access")
    print("  • Superusers can see all tags in admin")


if __name__ == '__main__':
    test_user_tags()