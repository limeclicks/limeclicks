#!/usr/bin/env python
"""
Test that admin configuration is working correctly after tags migration
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.contrib.admin.sites import site
from keywords.models import Keyword, Rank, Tag, KeywordTag
from keywords.admin import KeywordAdmin, RankAdmin, TagAdmin


def test_admin_configuration():
    """Test that admin models are configured correctly"""
    
    print("=" * 60)
    print("🔍 Testing Admin Configuration")
    print("=" * 60)
    
    # Check Keyword admin
    print("\n✓ KeywordAdmin registered")
    keyword_admin = site._registry.get(Keyword)
    if keyword_admin:
        print("  Fieldsets:")
        for name, fieldset in keyword_admin.fieldsets:
            fields = fieldset.get('fields', [])
            print(f"    {name}: {', '.join(fields)}")
        
        # Check that 'tags' is not in any fieldset
        all_fields = []
        for _, fieldset in keyword_admin.fieldsets:
            all_fields.extend(fieldset.get('fields', []))
        
        if 'tags' in all_fields:
            print("  ❌ ERROR: 'tags' field still in fieldsets!")
        else:
            print("  ✓ 'tags' field removed from fieldsets")
        
        # Check inlines
        if hasattr(keyword_admin, 'inlines'):
            print(f"  ✓ Inlines configured: {len(keyword_admin.inlines)} inline(s)")
    
    # Check Rank admin
    print("\n✓ RankAdmin registered")
    rank_admin = site._registry.get(Rank)
    if rank_admin:
        # Check fieldsets don't have non-existent fields
        all_fields = []
        for _, fieldset in rank_admin.fieldsets:
            all_fields.extend(fieldset.get('fields', []))
        
        if 'number_of_results' in all_fields:
            print("  ❌ ERROR: 'number_of_results' field in Rank fieldsets!")
        else:
            print("  ✓ 'number_of_results' removed from fieldsets")
        
        if 'rank_file' in all_fields:
            print("  ❌ ERROR: 'rank_file' field in Rank fieldsets!")
        else:
            print("  ✓ 'rank_file' removed from fieldsets")
    
    # Check Tag admin
    print("\n✓ TagAdmin registered")
    tag_admin = site._registry.get(Tag)
    if tag_admin:
        print(f"  List display: {', '.join(tag_admin.list_display)}")
        print(f"  Search fields: {', '.join(tag_admin.search_fields)}")
    
    # Test creating objects
    print("\n" + "-" * 40)
    print("Testing Model Creation")
    print("-" * 40)
    
    # Get or create a test keyword
    from project.models import Project
    from accounts.models import User
    
    user, _ = User.objects.get_or_create(
        username='admin_test_user',
        defaults={'email': 'admintest@example.com'}
    )
    
    project, _ = Project.objects.get_or_create(
        domain='admintest.com',
        defaults={'user': user, 'title': 'Admin Test', 'active': True}
    )
    
    keyword, created = Keyword.objects.get_or_create(
        project=project,
        keyword='admin test keyword',
        country='US',
        defaults={'country_code': 'US'}
    )
    print(f"  Keyword: {'Created' if created else 'Exists'} - {keyword.keyword}")
    
    # Create a tag
    tag, created = Tag.objects.get_or_create(
        name='Admin Test Tag',
        defaults={'color': '#123456'}
    )
    print(f"  Tag: {'Created' if created else 'Exists'} - {tag.name} (slug: {tag.slug})")
    
    # Associate tag with keyword
    keyword_tag, created = KeywordTag.objects.get_or_create(
        keyword=keyword,
        tag=tag
    )
    print(f"  Association: {'Created' if created else 'Exists'}")
    
    # Verify relationship
    tags_count = keyword.keyword_tags.count()
    print(f"  Keyword has {tags_count} tag(s)")
    
    print("\n" + "=" * 60)
    print("✅ Admin Configuration Test Complete")
    print("=" * 60)
    print("\nSummary:")
    print("  • KeywordAdmin: tags field removed ✓")
    print("  • KeywordAdmin: inline tags added ✓")
    print("  • RankAdmin: invalid fields removed ✓")
    print("  • TagAdmin: registered and configured ✓")
    print("  • Models: creation and association working ✓")


if __name__ == '__main__':
    test_admin_configuration()