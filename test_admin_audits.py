#!/usr/bin/env python
"""
Test admin interface for audits
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from project.models import Project
from accounts.models import User
from performance_audit.models import PerformancePage
from site_audit.models import SiteAudit

# Get admin user
admin = User.objects.filter(is_superuser=True).first()
print(f"Admin user: {admin.username} ({admin.email})")

# Create a test project if it doesn't exist
test_project, created = Project.objects.get_or_create(
    domain='example.com',
    defaults={
        'user': admin,
        'title': 'Example Project with Audits',
        'active': True
    }
)

if created:
    print(f'✅ Created test project: {test_project.domain}')
else:
    print(f'✅ Test project exists: {test_project.domain}')

# Check if audits were created
has_lighthouse = PerformancePage.objects.filter(project=test_project).exists()
has_onpage = SiteAudit.objects.filter(project=test_project).exists()

print(f'  - Lighthouse audit: {"✅ Created" if has_lighthouse else "❌ Not created"}')
print(f'  - OnPage audit: {"✅ Created" if has_onpage else "❌ Not created"}')

if has_onpage:
    audit = SiteAudit.objects.get(project=test_project)
    print(f'  - Max pages to crawl: {audit.max_pages_to_crawl}')

print(f"\n📌 Admin URLs:")
print(f"  - Projects list: http://localhost:8000/admin/project/project/")
print(f"  - Edit project: http://localhost:8000/admin/project/project/{test_project.id}/change/")
print(f"  - Lighthouse audits: http://localhost:8000/admin/performance_audit/performancepage/")
print(f"  - OnPage audits: http://localhost:8000/admin/site_audit/siteaudit/")

print(f"\n✅ Admin interface is ready!")
print(f"   Login with: admin / your_password")
print(f"   Navigate to Projects to see the integrated audit interfaces")