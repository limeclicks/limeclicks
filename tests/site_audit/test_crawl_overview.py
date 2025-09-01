#!/usr/bin/env python
import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from project.models import Project
from site_audit.models import SiteAudit
from site_audit.tasks import run_site_audit
import time

# Step 1: Find and remove the test project
print("=" * 80)
print("STEP 1: Finding and removing existing test project...")
print("=" * 80)

test_domain = "seo-test.limeclicks.com"
try:
    project = Project.objects.get(domain=test_domain)
    print(f"✅ Found project: {project.domain} (ID: {project.id})")
    
    # Get audit info before deletion
    audit = SiteAudit.objects.filter(project=project).first()
    if audit:
        print(f"  - Has audit ID: {audit.id}")
        print(f"  - Current temp_audit_dir: {audit.temp_audit_dir}")
        print(f"  - Current crawl_overview: {audit.crawl_overview}")
    
    # Delete the project (will cascade delete audits)
    project.delete()
    print(f"✅ Deleted project: {test_domain}")
except Project.DoesNotExist:
    print(f"ℹ️ Project {test_domain} not found (already deleted)")

print("\n" + "=" * 80)
print("STEP 2: Creating new project...")
print("=" * 80)

# Step 2: Create new project
from accounts.models import User
user = User.objects.first()  # Get first user for testing
if not user:
    print("❌ No user found in database")
    sys.exit(1)

project = Project.objects.create(
    domain=test_domain,
    title="SEO Test Site",
    user=user,
    active=True
)
print(f"✅ Created project: {project.domain} (ID: {project.id})")

# Step 3: Create site audit
print("\n" + "=" * 80)
print("STEP 3: Creating site audit...")
print("=" * 80)

site_audit = SiteAudit.objects.create(
    project=project,
    audit_frequency_days=30,
    manual_audit_frequency_days=1,
    max_pages_to_crawl=5000,
    is_audit_enabled=True
)
print(f"✅ Created site audit (ID: {site_audit.id})")

# Step 4: Run the audit task directly (synchronously for testing)
print("\n" + "=" * 80)
print("STEP 4: Running site audit task...")
print("=" * 80)

print("⏳ Starting crawl... this may take a minute...")

# Run the task directly using .run() method for bind=True tasks
try:
    # For bind=True tasks, we can call the .run() method directly
    result = run_site_audit.run(site_audit.id)
    print(f"\n✅ Audit task completed!")
    print(f"Result: {result}")
except Exception as e:
    print(f"❌ Audit task failed: {e}")
    import traceback
    traceback.print_exc()

# Step 5: Verify the results
print("\n" + "=" * 80)
print("STEP 5: Verifying results...")
print("=" * 80)

# Reload the audit from database
site_audit.refresh_from_db()

print(f"\n📊 Site Audit Results:")
print(f"  - Status: {site_audit.status}")
print(f"  - temp_audit_dir: {site_audit.temp_audit_dir}")
print(f"  - total_pages_crawled: {site_audit.total_pages_crawled}")
print(f"  - crawl_overview: {site_audit.crawl_overview}")

# Check if temp_audit_dir includes timestamped subdirectory
if site_audit.temp_audit_dir:
    from pathlib import Path
    temp_path = Path(site_audit.temp_audit_dir)
    
    print(f"\n📁 Directory Analysis:")
    print(f"  - Path exists: {temp_path.exists()}")
    
    if temp_path.exists():
        # Check if this is the timestamped directory
        parent_name = temp_path.parent.name
        dir_name = temp_path.name
        
        print(f"  - Parent directory: {parent_name}")
        print(f"  - Directory name: {dir_name}")
        
        # Check if directory name matches timestamp pattern (YYYY.MM.DD.HH.MM.SS)
        import re
        timestamp_pattern = r'\d{4}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{2}'
        if re.match(timestamp_pattern, dir_name):
            print(f"  ✅ Directory name matches timestamp pattern!")
        else:
            print(f"  ⚠️ Directory name doesn't match timestamp pattern")
        
        # List files in the directory
        files = list(temp_path.glob('*'))
        print(f"\n  📄 Files in directory ({len(files)} total):")
        for file in files[:10]:  # Show first 10 files
            print(f"    - {file.name}")
        
        # Check if crawl_overview.csv exists
        crawl_overview_file = temp_path / 'crawl_overview.csv'
        if crawl_overview_file.exists():
            print(f"\n  ✅ crawl_overview.csv found!")
            print(f"    - Size: {crawl_overview_file.stat().st_size} bytes")
        else:
            print(f"\n  ❌ crawl_overview.csv not found")

# Final validation
print("\n" + "=" * 80)
print("VALIDATION RESULTS:")
print("=" * 80)

if site_audit.temp_audit_dir and '.' in Path(site_audit.temp_audit_dir).name:
    print("✅ temp_audit_dir includes timestamped subdirectory")
else:
    print("❌ temp_audit_dir does NOT include timestamped subdirectory")

if site_audit.crawl_overview and isinstance(site_audit.crawl_overview, dict):
    if site_audit.crawl_overview.get('total_urls_crawled'):
        print(f"✅ crawl_overview data saved: {site_audit.crawl_overview.get('total_urls_crawled')} URLs crawled")
    else:
        print("⚠️ crawl_overview saved but no URLs crawled data")
else:
    print("❌ crawl_overview data not saved")

if site_audit.total_pages_crawled > 0:
    print(f"✅ total_pages_crawled updated: {site_audit.total_pages_crawled}")
else:
    print("❌ total_pages_crawled not updated")

print("\n✨ Test complete!")