#!/usr/bin/env python
"""
Test Project Listing with Metrics
"""
import os
import django
import sys

# Setup Django environment
sys.path.insert(0, '/home/muaaz/enterprise/limeclicks')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from project.models import Project

User = get_user_model()

def test_project_listing():
    """Test the project listing with metrics"""
    
    print("\n============================================================")
    print("  PROJECT LISTING WITH METRICS TEST")
    print("============================================================")
    
    # Get test owner user
    owner = User.objects.filter(email="testowner@example.com").first()
    if not owner:
        print("✗ Test owner user not found. Run test_complete_flow.py first.")
        return
    
    # Create test client and login
    client = Client()
    logged_in = client.login(username="testowner", password="testpass123")
    
    if not logged_in:
        print("✗ Failed to login as test owner")
        return
    
    print(f"✓ Logged in as: {owner.email}")
    
    # Test project list view
    url = reverse('project:project_list')
    response = client.get(url)
    
    print(f"\n1. Testing URL: {url}")
    print(f"   Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("   ✓ Project list page loaded successfully")
        
        # Check for expected content
        content = response.content.decode('utf-8')
        
        checks = {
            'Projects header': 'Projects' in content and 'Manage your website projects' in content,
            'Search functionality': 'Search projects' in content or 'search' in content.lower(),
            'Create Project button': 'Create Project' in content or 'Create project' in content,
            'Project cards/metrics': 'project-card' in content or 'projects_with_info' in content,
            'Stats overview': 'Total Projects' in content or 'total_projects' in content,
        }
        
        print("\n2. Content Verification:")
        for check, result in checks.items():
            status = "✓" if result else "✗"
            print(f"   {status} {check}: {result}")
        
        # Check for specific project
        project_domain = "testproject.com"
        if project_domain in content:
            print(f"\n3. Found test project: {project_domain}")
            
            # Check for metrics presence
            metrics_checks = {
                'Audit Score section': 'Audit Score' in content,
                'Keywords count': 'Keywords' in content and ('keyword_count' in content or 'Total tracked' in content),
                'Top 10 rankings': 'Top 10' in content,
                'Team members': 'Team' in content and ('member_count' in content or 'Members' in content),
            }
            
            print("\n4. Metrics Verification:")
            for metric, found in metrics_checks.items():
                status = "✓" if found else "✗"
                print(f"   {status} {metric}: {found}")
        else:
            print(f"\n✗ Test project '{project_domain}' not found in listing")
        
        # Get project from database to verify data
        project = Project.objects.filter(domain="testproject.com").first()
        if project:
            print(f"\n5. Database Verification for {project.domain}:")
            print(f"   - Keywords: {project.keywords.count()}")
            print(f"   - Team members: {project.memberships.count()}")
            print(f"   - Site audits: {project.site_audits.count()}")
            
            latest_audit = project.site_audits.order_by('-created_at').first()
            if latest_audit:
                print(f"   - Latest audit status: {latest_audit.status}")
                if latest_audit.overall_site_health_score is not None:
                    print(f"   - Audit score: {latest_audit.overall_site_health_score}")
        
    else:
        print(f"   ✗ Failed to load project list: {response.status_code}")
        print(f"   Error: {response.content.decode('utf-8')[:500]}")
    
    print("\n✅ Project Listing Test Complete!")

if __name__ == "__main__":
    test_project_listing()