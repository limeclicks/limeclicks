#!/usr/bin/env python
"""
Debug test to check if signals are firing
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.db.models.signals import post_save
from project.models import Project
from accounts.models import User

# Check registered signals
print("\n" + "="*60)
print("DEBUG: Signal Registration Check")
print("="*60)

# Get all receivers for Project post_save
receivers = post_save._live_receivers(sender=Project)
print(f"\nRegistered post_save receivers for Project: {len(receivers)}")
for receiver in receivers:
    if hasattr(receiver, '__self__'):
        func = receiver.__self__
    else:
        func = receiver
    
    if hasattr(func, '__name__'):
        print(f"  - {func.__name__}")
    elif hasattr(func, '__qualname__'):
        print(f"  - {func.__qualname__}")
    else:
        print(f"  - {func}")

# Test signal manually
print("\n" + "="*60)
print("TEST: Manual Signal Trigger")
print("="*60)

# Get test user
user = User.objects.filter(email='test@example.com').first()
if not user:
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='test123'
    )

# Create project and check if signal fires
print("\nCreating test project...")

# First, let's manually import and check the signal
try:
    from project.signals import auto_queue_audits_on_project_creation
    print("✓ Signal handler imported successfully")
    print(f"  Handler: {auto_queue_audits_on_project_creation}")
except ImportError as e:
    print(f"✗ Failed to import signal handler: {e}")

# Now create the project
project = Project.objects.create(
    user=user,
    domain='signal-test.com',
    title='Signal Test Project',
    active=True
)
print(f"✓ Project created: {project.domain}")

# Check if audits were created
from audits.models import AuditPage
from onpageaudit.models import OnPageAudit

import time
time.sleep(1)

has_lighthouse = AuditPage.objects.filter(project=project).exists()
has_onpage = OnPageAudit.objects.filter(project=project).exists()

print(f"\nAudit check:")
print(f"  Lighthouse audit created: {has_lighthouse}")
print(f"  OnPage audit created: {has_onpage}")

# Cleanup
project.delete()
print("\n✓ Test project deleted")

print("\n" + "="*60)
print("DEBUG COMPLETE")
print("="*60)