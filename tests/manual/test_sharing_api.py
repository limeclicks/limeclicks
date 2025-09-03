#!/usr/bin/env python
"""
Test project sharing functionality via API
"""
import os
import django
import sys

# Setup Django environment
sys.path.insert(0, '/home/muaaz/enterprise/limeclicks')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from project.models import Project, ProjectMember, ProjectInvitation, ProjectRole
from project.permissions import ProjectPermission

User = get_user_model()

def test_sharing_api():
    """Test sharing functionality through simulated requests"""
    
    print("\n" + "=" * 60)
    print("Testing Project Sharing API")
    print("=" * 60)
    
    # Get or create test users
    owner, _ = User.objects.get_or_create(
        username='projectowner',
        defaults={'email': 'owner@example.com', 'email_verified': True}
    )
    owner.set_password('testpass123')
    owner.save()
    
    editor, _ = User.objects.get_or_create(
        username='projecteditor', 
        defaults={'email': 'editor@example.com', 'email_verified': True}
    )
    editor.set_password('testpass123')
    editor.save()
    
    # Get first project or create one
    project = Project.objects.first()
    if not project:
        project = Project.objects.create(
            user=owner,
            domain='testsharing.com',
            title='Test Sharing Project'
        )
        ProjectMember.objects.create(
            project=project,
            user=owner,
            role=ProjectRole.OWNER
        )
    
    print(f"\nTest Setup:")
    print(f"  • Project: {project.domain}")
    print(f"  • Owner: {project.user.email}")
    print(f"  • Test Editor: {editor.email}")
    
    # Test 1: Check current memberships
    print(f"\n1. Current Memberships for {project.domain}:")
    members = ProjectMember.objects.filter(project=project)
    for member in members:
        print(f"   • {member.user.email}: {member.role}")
    
    # Test 2: Add editor as a member
    print(f"\n2. Adding {editor.email} as EDITOR:")
    member, created = ProjectMember.objects.get_or_create(
        project=project,
        user=editor,
        defaults={'role': ProjectRole.EDITOR}
    )
    if created:
        print(f"   ✓ Added {editor.email} as {member.role}")
    else:
        print(f"   • {editor.email} is already a member with role: {member.role}")
    
    # Test 3: Verify permissions
    print(f"\n3. Testing Permissions for {editor.email}:")
    perms = {
        'View Project': ProjectPermission.has_permission(editor, project, ProjectPermission.VIEW_PROJECT),
        'Edit Settings': ProjectPermission.has_permission(editor, project, ProjectPermission.EDIT_PROJECT_SETTINGS),
        'Manage Keywords': ProjectPermission.has_permission(editor, project, ProjectPermission.MANAGE_KEYWORDS),
        'Manage Team': ProjectPermission.has_permission(editor, project, ProjectPermission.MANAGE_TEAM),
        'Delete Project': ProjectPermission.has_permission(editor, project, ProjectPermission.DELETE_PROJECT),
    }
    for perm, has_perm in perms.items():
        status = "✓" if has_perm else "✗"
        print(f"   {status} {perm}: {has_perm}")
    
    # Test 4: Create an invitation for a new user
    print(f"\n4. Creating invitation for new user:")
    new_email = "newuser@example.com"
    
    # Check if invitation already exists
    existing = ProjectInvitation.objects.filter(
        project=project,
        email=new_email,
        status='PENDING'
    ).first()
    
    if not existing:
        invitation = ProjectInvitation.objects.create(
            project=project,
            email=new_email,
            role=ProjectRole.EDITOR,
            invited_by=owner
        )
        print(f"   ✓ Created invitation for {new_email}")
        print(f"   • Token: {invitation.token}")
        print(f"   • Role: {invitation.role}")
        print(f"   • Expires: {invitation.expires_at}")
        print(f"   • Valid: {invitation.is_valid()}")
    else:
        print(f"   • Invitation already exists for {new_email}")
        print(f"   • Token: {existing.token}")
        print(f"   • Valid: {existing.is_valid()}")
    
    # Test 5: List all project access
    print(f"\n5. Complete Access List for {project.domain}:")
    
    print("   Members:")
    for member in ProjectMember.objects.filter(project=project):
        print(f"     • {member.user.email} ({member.role})")
    
    print("   Pending Invitations:")
    pending = ProjectInvitation.objects.filter(project=project, status='PENDING')
    if pending.exists():
        for inv in pending:
            print(f"     • {inv.email} (invited as {inv.role})")
    else:
        print("     • None")
    
    print("\n" + "=" * 60)
    print("✅ Sharing API Test Complete!")
    print("\nYou can now:")
    print(f"1. Login at http://localhost:8000 with:")
    print(f"   • Owner: {owner.email} / testpass123")
    print(f"   • Editor: {editor.email} / testpass123")
    print(f"2. Navigate to any project and click 'Team' button")
    print(f"3. Test inviting users and managing team members")
    print("=" * 60)

if __name__ == "__main__":
    test_sharing_api()