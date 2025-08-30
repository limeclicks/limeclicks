#!/usr/bin/env python
"""
Test SSE audit status updates
"""
import os
import sys
import django
import time
from datetime import timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.utils import timezone
from site_audit.models import SiteAudit
from project.models import Project
from site_audit.tasks import trigger_manual_site_audit

def test_audit_sse():
    """Test audit status transitions and SSE updates"""
    
    # Get an existing project
    project = Project.objects.first()
    if not project:
        print("❌ No projects found in database")
        return
    
    print(f"✅ Using project: {project.domain}")
    
    # Reset any existing audit to allow a fresh trigger
    existing_audit = SiteAudit.objects.filter(project=project).first()
    if existing_audit:
        # Force reset to allow immediate re-audit
        existing_audit.last_manual_audit = timezone.now() - timedelta(days=10)
        existing_audit.status = 'completed'
        existing_audit.save()
        print(f"✅ Reset existing audit (ID: {existing_audit.id})")
    
    # Trigger manual audit
    print("\n🚀 Triggering manual audit...")
    result = trigger_manual_site_audit.delay(project.id)
    print(f"   Task ID: {result.id}")
    
    # Monitor status changes
    print("\n📊 Monitoring status changes (30 seconds)...")
    print("   Time | Status    | Pages | Score | Notes")
    print("   -----|-----------|-------|-------|-------")
    
    start_time = time.time()
    previous_status = None
    status_changes = []
    
    for i in range(15):  # Check for 30 seconds
        time.sleep(2)
        
        # Refresh audit from database
        audit = SiteAudit.objects.filter(project=project).first()
        if audit:
            elapsed = int(time.time() - start_time)
            current_status = audit.status
            
            # Check if status changed
            status_marker = "🔄" if current_status != previous_status else "  "
            
            print(f"   {elapsed:3d}s | {current_status:9s} | {audit.total_pages_crawled or 0:5d} | {audit.overall_site_health_score or 0:5.0f} | {status_marker}")
            
            if current_status != previous_status:
                status_changes.append({
                    'time': elapsed,
                    'from': previous_status,
                    'to': current_status
                })
                previous_status = current_status
            
            # Stop if completed or failed
            if current_status in ['completed', 'failed']:
                break
    
    # Summary
    print("\n📈 Summary:")
    print(f"   Final status: {audit.status if audit else 'Unknown'}")
    print(f"   Status transitions: {len(status_changes)}")
    
    if status_changes:
        print("\n   Transitions:")
        for change in status_changes:
            print(f"   - {change['time']}s: {change['from'] or 'initial'} → {change['to']}")
    
    # Check if SSE would detect these changes
    print("\n🔍 SSE Detection Check:")
    if 'pending' in [c['to'] for c in status_changes]:
        print("   ✅ Pending status detected")
    else:
        print("   ⚠️  Pending status NOT detected")
    
    if 'running' in [c['to'] for c in status_changes]:
        print("   ✅ Running status detected")
    else:
        print("   ⚠️  Running status NOT detected")
    
    if audit and audit.status == 'completed':
        print("   ✅ Completed status reached")
        if audit.overall_site_health_score is not None:
            print(f"   ✅ Health score updated: {audit.overall_site_health_score}")
    
    print("\n✨ Test complete!")

if __name__ == "__main__":
    test_audit_sse()