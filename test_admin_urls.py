#!/usr/bin/env python
"""
Test admin URLs are working correctly
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.urls import reverse
from django.contrib.admin.sites import site
from django.test import Client
from accounts.models import User


def test_admin_urls():
    """Test that all admin URLs are accessible"""
    
    print("=" * 60)
    print("🔍 Testing Admin URLs")
    print("=" * 60)
    
    # Create a test admin user
    admin_user, created = User.objects.get_or_create(
        username='admin_url_test',
        defaults={
            'email': 'admin@test.com',
            'is_staff': True,
            'is_superuser': True
        }
    )
    if created:
        admin_user.set_password('testpass123')
        admin_user.save()
    
    # Create a test client and login
    client = Client()
    logged_in = client.login(username='admin_url_test', password='testpass123')
    
    if not logged_in:
        print("❌ Failed to login as admin")
        return
    
    print("✓ Logged in as admin\n")
    
    # Test URLs from navigation
    test_urls = [
        ('/admin/', 'Dashboard'),
        ('/admin/keywords/keyword/', 'Keywords'),
        ('/admin/keywords/rank/', 'Rankings'),
        ('/admin/keywords/tag/', 'Tags'),
        ('/admin/project/project/', 'Projects'),
        ('/admin/accounts/user/', 'Users'),
        ('/admin/auth/group/', 'Groups'),
        ('/admin/auth/permission/', 'Permissions'),
        ('/admin/sites/site/', 'Sites'),
        ('/admin/django_celery_beat/periodictask/', 'Periodic Tasks'),
        ('/admin/django_celery_beat/intervalschedule/', 'Intervals'),
        ('/admin/django_celery_beat/crontabschedule/', 'Crontabs'),
    ]
    
    print("Testing navigation URLs:")
    for url, name in test_urls:
        try:
            response = client.get(url)
            if response.status_code == 200:
                print(f"  ✅ {name}: {url} - OK")
            elif response.status_code == 302:
                print(f"  🔄 {name}: {url} - Redirect to {response.url}")
            else:
                print(f"  ❌ {name}: {url} - Status {response.status_code}")
        except Exception as e:
            print(f"  ❌ {name}: {url} - Error: {e}")
    
    # Check registered models
    print("\n📋 Registered Admin Models:")
    for model, admin_class in site._registry.items():
        app_label = model._meta.app_label
        model_name = model._meta.model_name
        print(f"  • {app_label}.{model_name}")
    
    # Test reverse URLs
    print("\n🔗 Testing Reverse URLs:")
    try:
        keywords_url = reverse('admin:keywords_keyword_changelist')
        print(f"  Keywords: {keywords_url}")
        
        rank_url = reverse('admin:keywords_rank_changelist')
        print(f"  Rankings: {rank_url}")
        
        tag_url = reverse('admin:keywords_tag_changelist')
        print(f"  Tags: {tag_url}")
        
        project_url = reverse('admin:project_project_changelist')
        print(f"  Projects: {project_url}")
    except Exception as e:
        print(f"  ❌ Error getting reverse URLs: {e}")
    
    # Clean up
    if created:
        admin_user.delete()
    
    print("\n" + "=" * 60)
    print("✅ Admin URL Test Complete")
    print("=" * 60)


if __name__ == '__main__':
    test_admin_urls()