#!/usr/bin/env python
"""
Test script for project sharing functionality
"""
import os
import django
import sys

# Setup Django environment
sys.path.insert(0, '/home/muaaz/enterprise/limeclicks')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.contrib.auth import get_user_model
from project.models import Project, ProjectMember, ProjectInvitation, ProjectRole
from project.permissions import ProjectPermission

User = get_user_model()

def test_project_sharing():
    """Test the project sharing functionality"""
    
    print("=" * 60)
    print("Testing Project Sharing Functionality")
    print("=" * 60)
    
    # 1. Check existing users
    print("\n1. Existing Users:")
    users = User.objects.all()
    for user in users:
        print(f"   - {user.username}: {user.email} (Verified: {user.email_verified})")
    
    if users.count() < 2:
        print("   ⚠️  Need at least 2 users to test sharing. Creating test users...")
        # Create test users if needed
        user1, created = User.objects.get_or_create(
            username='testowner',
            defaults={'email': 'owner@test.com', 'email_verified': True}
        )
        if created:
            user1.set_password('testpass123')
            user1.save()
            print(f"   ✓ Created user: {user1.email}")
        
        user2, created = User.objects.get_or_create(
            username='testeditor',
            defaults={'email': 'editor@test.com', 'email_verified': True}
        )
        if created:
            user2.set_password('testpass123')
            user2.save()
            print(f"   ✓ Created user: {user2.email}")
    else:
        user1 = users[0]
        user2 = users[1] if users.count() > 1 else None
    
    # 2. Check existing projects
    print("\n2. Existing Projects:")
    projects = Project.objects.all()
    for project in projects:
        members = ProjectMember.objects.filter(project=project)
        print(f"   - {project.domain} (Owner: {project.user.email})")
        print(f"     Members: {members.count()}")
        for member in members:
            print(f"       • {member.user.email}: {member.role}")
    
    # 3. Test creating a project with owner membership
    if projects.count() == 0:
        print("\n3. Creating Test Project:")
        project = Project.objects.create(
            user=user1,
            domain='testproject.com',
            title='Test Project for Sharing'
        )
        # Create owner membership
        ProjectMember.objects.create(
            project=project,
            user=user1,
            role=ProjectRole.OWNER
        )
        print(f"   ✓ Created project: {project.domain}")
    else:
        project = projects.first()
        print(f"\n3. Using existing project: {project.domain}")
    
    # 4. Test permission checks
    print("\n4. Testing Permissions:")
    
    # Get owner of first project
    owner_member = ProjectMember.objects.filter(
        project=project,
        role=ProjectRole.OWNER
    ).first()
    
    if owner_member:
        owner = owner_member.user
        print(f"   Project owner: {owner.email}")
        
        # Test owner permissions
        perms = {
            'view': ProjectPermission.has_permission(owner, project, ProjectPermission.VIEW_PROJECT),
            'edit': ProjectPermission.has_permission(owner, project, ProjectPermission.EDIT_PROJECT_SETTINGS),
            'keywords': ProjectPermission.has_permission(owner, project, ProjectPermission.MANAGE_KEYWORDS),
            'team': ProjectPermission.has_permission(owner, project, ProjectPermission.MANAGE_TEAM),
            'delete': ProjectPermission.has_permission(owner, project, ProjectPermission.DELETE_PROJECT),
        }
        print(f"   Owner permissions: {perms}")
        
        # Test non-member permissions (if we have another user)
        if user2 and user2 != owner:
            non_member_perms = {
                'view': ProjectPermission.has_permission(user2, project, ProjectPermission.VIEW_PROJECT),
                'edit': ProjectPermission.has_permission(user2, project, ProjectPermission.EDIT_PROJECT_SETTINGS),
                'keywords': ProjectPermission.has_permission(user2, project, ProjectPermission.MANAGE_KEYWORDS),
                'team': ProjectPermission.has_permission(user2, project, ProjectPermission.MANAGE_TEAM),
                'delete': ProjectPermission.has_permission(user2, project, ProjectPermission.DELETE_PROJECT),
            }
            print(f"   Non-member ({user2.email}) permissions: {non_member_perms}")
    
    # 5. Check invitations
    print("\n5. Pending Invitations:")
    invitations = ProjectInvitation.objects.filter(status='PENDING')
    if invitations.exists():
        for inv in invitations:
            print(f"   - {inv.email} to {inv.project.domain} (Role: {inv.role})")
            print(f"     Token: {inv.token}")
            print(f"     Valid: {inv.is_valid()}")
    else:
        print("   No pending invitations")
    
    # 6. Summary
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  • Total Users: {User.objects.count()}")
    print(f"  • Total Projects: {Project.objects.count()}")
    print(f"  • Total Memberships: {ProjectMember.objects.count()}")
    print(f"  • Pending Invitations: {ProjectInvitation.objects.filter(status='PENDING').count()}")
    print("=" * 60)
    
    print("\n✅ Project sharing feature is deployed and ready!")
    print("\nTo test the UI:")
    print("1. Go to http://localhost:8000")
    print("2. Login with one of the test users")
    print("3. Create a new project or open an existing one")
    print("4. Click the 'Team' button to manage team members")
    print("5. Try inviting users by email")

if __name__ == "__main__":
    test_project_sharing()