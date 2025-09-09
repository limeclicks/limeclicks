#!/usr/bin/env python
"""
Apply minimal patches to fix keyword crawling issues
This script modifies the existing files with surgical precision
"""

import os
import shutil
from datetime import datetime

def backup_file(filepath):
    """Create a backup of the file"""
    backup_path = f"{filepath}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(filepath, backup_path)
    print(f"✓ Backed up {filepath} to {backup_path}")
    return backup_path

def patch_keywords_tasks():
    """Apply patches to keywords/tasks.py"""
    filepath = "keywords/tasks.py"
    
    # Read the current file
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check if already patched
    if 'from celery.exceptions import SoftTimeLimitExceeded' in content:
        print("✓ keywords/tasks.py already patched")
        return
    
    # Backup first
    backup_file(filepath)
    
    # Apply patches
    patches_applied = []
    
    # Patch 1: Add imports
    import_line = "from celery import shared_task"
    if import_line in content:
        new_imports = """from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db import transaction"""
        content = content.replace(import_line, new_imports)
        patches_applied.append("Added imports")
    
    # Patch 2: Initialize keyword variable
    old_line = '    lock_key = f"lock:serp:{keyword_id}"'
    new_lines = '''    lock_key = f"lock:serp:{keyword_id}"
    lock_timeout = 360  # 6 minutes (slightly longer than task timeout)
    keyword = None  # Initialize for proper cleanup'''
    
    if old_line in content and 'keyword = None' not in content:
        # Find and replace the section
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'lock_key = f"lock:serp:{keyword_id}"' in line:
                if i + 1 < len(lines) and 'keyword = None' not in lines[i + 1]:
                    lines.insert(i + 2, '    keyword = None  # Initialize for proper cleanup')
                    patches_applied.append("Added keyword initialization")
                break
        content = '\n'.join(lines)
    
    # Patch 3: Enhance finally block in fetch_keyword_serp_html
    old_finally = """    finally:
        # Always release the lock
        cache.delete(lock_key)"""
    
    new_finally = """    finally:
        # ALWAYS reset processing flag and release lock
        if keyword:
            try:
                with transaction.atomic():
                    # Re-fetch to avoid stale data
                    keyword.refresh_from_db()
                    keyword.processing = False
                    keyword.save(update_fields=['processing', 'updated_at'])
                    logger.debug(f"Reset processing flag for keyword {keyword_id}")
            except Exception as e:
                logger.error(f"Failed to reset processing flag for keyword {keyword_id}: {e}")
                # Try direct update as last resort
                try:
                    Keyword.objects.filter(id=keyword_id).update(processing=False)
                except:
                    pass
        
        # Always release the lock
        cache.delete(lock_key)"""
    
    if old_finally in content:
        content = content.replace(old_finally, new_finally)
        patches_applied.append("Enhanced finally block")
    
    # Patch 4: Add SoftTimeLimitExceeded handler
    if 'except SoftTimeLimitExceeded:' not in content:
        # Find the main except Exception block and add before it
        exception_marker = "    except Exception as e:"
        exception_index = content.find(exception_marker)
        
        if exception_index > 0:
            soft_limit_handler = """    except SoftTimeLimitExceeded:
        logger.error(f"Task timeout (soft limit) for keyword {keyword_id}")
        if keyword:
            keyword.processing = False
            keyword.last_error_message = "Task timeout"
            keyword.failed_api_hit_count += 1
            keyword.save(update_fields=['processing', 'last_error_message', 'failed_api_hit_count'])
        raise
        
"""
            content = content[:exception_index] + soft_limit_handler + content[exception_index:]
            patches_applied.append("Added SoftTimeLimitExceeded handler")
    
    # Patch 5: Make cleanup more aggressive (1 hour instead of 15 minutes)
    old_cleanup = "stuck_cutoff = now - timedelta(minutes=15)"
    new_cleanup = "stuck_cutoff = now - timedelta(hours=1)  # More aggressive cleanup"
    
    if old_cleanup in content:
        content = content.replace(old_cleanup, new_cleanup)
        patches_applied.append("Made cleanup more aggressive (1 hour)")
    
    # Patch 6: Add NULL next_crawl_at fix to cleanup
    cleanup_marker = "cleanup_stats['errors_cleared'] = recent_success.update(last_error_message=None)"
    if cleanup_marker in content and 'null_next_fixed' not in content:
        null_fix = """
        
        # Fix NULL next_crawl_at values
        null_next = Keyword.objects.filter(
            next_crawl_at__isnull=True,
            archive=False
        )
        null_count = null_next.update(
            next_crawl_at=now,
            updated_at=now
        )
        if null_count > 0:
            logger.info(f"[CLEANUP] Fixed {null_count} keywords with NULL next_crawl_at")
            cleanup_stats['null_next_fixed'] = null_count"""
        
        content = content.replace(cleanup_marker, cleanup_marker + null_fix)
        patches_applied.append("Added NULL next_crawl_at fix")
    
    # Write the patched file
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"✓ Applied {len(patches_applied)} patches to {filepath}:")
    for patch in patches_applied:
        print(f"  - {patch}")

def patch_celery_config():
    """Update celery.py to run cleanup more frequently"""
    filepath = "limeclicks/celery.py"
    
    # Read the current file
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Backup first
    backup_file(filepath)
    
    patches_applied = []
    
    # Patch 1: Update cleanup frequency
    old_schedule = "'schedule': crontab(minute='*/15'),"  # for cleanup-stuck-keywords
    new_schedule = "'schedule': crontab(minute='*/5'),  # More frequent cleanup"
    
    # Find the cleanup-stuck-keywords section and update it
    lines = content.split('\n')
    for i in range(len(lines)):
        if "'cleanup-stuck-keywords':" in lines[i]:
            # Look for the schedule line within the next few lines
            for j in range(i, min(i + 5, len(lines))):
                if "'schedule': crontab(minute='*/15')" in lines[j]:
                    lines[j] = "        'schedule': crontab(minute='*/5'),  # Run every 5 minutes (was 15)"
                    patches_applied.append("Updated cleanup frequency to 5 minutes")
                    break
            break
    
    content = '\n'.join(lines)
    
    # Write the patched file
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"✓ Applied {len(patches_applied)} patches to {filepath}:")
    for patch in patches_applied:
        print(f"  - {patch}")

def main():
    """Apply all patches"""
    print("\n" + "="*60)
    print(" APPLYING KEYWORD CRAWLING FIXES ")
    print("="*60)
    
    # Check we're in the right directory
    if not os.path.exists('keywords/tasks.py'):
        print("❌ Error: Must run from limeclicks root directory")
        print("   Current directory:", os.getcwd())
        return
    
    print("\n📝 Applying patches...\n")
    
    # Apply patches
    patch_keywords_tasks()
    patch_celery_config()
    
    print("\n" + "="*60)
    print(" PATCHES APPLIED SUCCESSFULLY ")
    print("="*60)
    
    print("\n📋 Next steps:")
    print("1. Review the changes")
    print("2. Restart Celery workers:")
    print("   sudo systemctl restart limeclicks-celery")
    print("   sudo systemctl restart limeclicks-celery-beat")
    print("3. Run immediate recovery:")
    print("   python immediate_recovery.py --apply")
    print("4. Monitor for 24 hours:")
    print("   python monitor_crawling_health.py --watch")

if __name__ == "__main__":
    main()