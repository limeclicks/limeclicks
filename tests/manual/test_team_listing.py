#!/usr/bin/env python
"""
Test Team Projects Listing
"""
import os
import django
import sys

# Setup Django environment
sys.path.insert(0, '/home/muaaz/enterprise/limeclicks')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.contrib.auth import get_user_model
from project.models import Project, ProjectMember, ProjectRole
from django.test import Client
from django.urls import reverse

User = get_user_model()

def test_team_listing():
    """Test the team projects listing page"""
    
    print("\n============================================================")
    print("  TEAM PROJECTS LISTING TEST")
    print("============================================================")
    
    # Get test owner user
    owner = User.objects.filter(email="testowner@example.com").first()
    if not owner:
        print("✗ Test owner user not found. Run test_complete_flow.py first.")
        return
    
    # Create test client and login
    client = Client()
    # Use username for login instead of email
    logged_in = client.login(username="testowner", password="testpass123")
    
    if not logged_in:
        print("✗ Failed to login as test owner")
        return
    
    print(f"✓ Logged in as: {owner.email}")
    
    # Test team projects list view
    url = reverse('project:team_projects_list')
    response = client.get(url)
    
    print(f"\n1. Testing URL: {url}")
    print(f"   Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("   ✓ Team projects list page loaded successfully")
        
        # Check for expected content
        content = response.content.decode('utf-8')
        
        checks = {
            'Team Projects header': 'Team Projects' in content,
            'Project cards': 'team-card' in content or 'team-cards-container' in content,
            'Member count display': 'Team Members' in content,
            'Invitation count': 'Pending Invites' in content,
            'testproject.com': 'testproject.com' in content,
            'Owner badge': 'Owner' in content or 'OWNER' in content,
            'Manage Team button': 'Manage Team' in content,
        }
        
        print("\n2. Content Verification:")
        for check, result in checks.items():
            status = "✓" if result else "✗"
            print(f"   {status} {check}: {result}")
        
        # Get projects for this user
        user_projects = Project.objects.filter(
            memberships__user=owner
        ).distinct()
        
        print(f"\n3. Database Verification:")
        print(f"   Total projects for user: {user_projects.count()}")
        
        for project in user_projects:
            members = project.memberships.all()
            print(f"\n   Project: {project.domain}")
            print(f"   - Members: {members.count()}")
            print(f"   - Title: {project.title}")
            
            for member in members:
                print(f"     • {member.user.email} ({member.role})")
    else:
        print(f"   ✗ Failed to load team projects list: {response.status_code}")
    
    # Test team management page for specific project
    project = Project.objects.filter(domain="testproject.com").first()
    if project:
        print(f"\n4. Testing Team Management Page:")
        url = reverse('project:team_management', kwargs={'project_id': project.id})
        response = client.get(url)
        print(f"   URL: {url}")
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("   ✓ Team management page loaded successfully")
        else:
            print(f"   ✗ Failed to load team management page")
    
    print("\n✅ Team Projects Listing Test Complete!")

if __name__ == "__main__":
    test_team_listing()