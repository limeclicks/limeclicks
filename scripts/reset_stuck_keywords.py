#!/usr/bin/env python3
"""
Script to reset all stuck keywords that are showing as 'checking' (processing=True)
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.utils import timezone
from django.db import connection
from keywords.models import Keyword
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_stuck_keywords_info():
    """Get information about stuck keywords"""
    # Count keywords stuck in processing
    stuck_keywords = Keyword.objects.filter(processing=True)
    stuck_count = stuck_keywords.count()
    
    # Get more details
    stuck_for_long = stuck_keywords.filter(
        scraped_at__lt=timezone.now() - timedelta(minutes=30)
    ).count()
    
    # Keywords that have never been scraped but are stuck
    never_scraped_stuck = stuck_keywords.filter(scraped_at__isnull=True).count()
    
    return {
        'total_stuck': stuck_count,
        'stuck_over_30min': stuck_for_long,
        'never_scraped_stuck': never_scraped_stuck,
        'stuck_keywords': stuck_keywords
    }


def reset_all_stuck_keywords(force=False):
    """Reset all keywords that are stuck in processing state"""
    info = get_stuck_keywords_info()
    
    logger.info("=" * 60)
    logger.info("STUCK KEYWORDS ANALYSIS")
    logger.info("=" * 60)
    logger.info(f"Total stuck keywords (processing=True): {info['total_stuck']}")
    logger.info(f"Stuck for over 30 minutes: {info['stuck_over_30min']}")
    logger.info(f"Never scraped but stuck: {info['never_scraped_stuck']}")
    
    if info['total_stuck'] == 0:
        logger.info("✅ No stuck keywords found!")
        return 0
    
    # Show sample of stuck keywords
    sample_keywords = info['stuck_keywords'].select_related('project')[:10]
    logger.info("\nSample of stuck keywords:")
    for kw in sample_keywords:
        project_name = kw.project.name if kw.project else "No Project"
        last_scraped = kw.scraped_at.strftime("%Y-%m-%d %H:%M") if kw.scraped_at else "Never"
        logger.info(f"  - {kw.keyword[:50]} (Project: {project_name}, Last: {last_scraped})")
    
    if not force:
        logger.info("\n⚠️  To reset these keywords, run with --force flag")
        return 0
    
    # Reset all stuck keywords
    logger.info("\n🔧 Resetting all stuck keywords...")
    
    try:
        # Reset in batches to avoid locking issues
        batch_size = 100
        total_reset = 0
        
        while True:
            # Get batch of stuck keywords
            batch_ids = list(Keyword.objects.filter(
                processing=True
            ).values_list('id', flat=True)[:batch_size])
            
            if not batch_ids:
                break
            
            # Reset this batch
            updated = Keyword.objects.filter(
                id__in=batch_ids
            ).update(
                processing=False,
                updated_at=timezone.now()
            )
            
            total_reset += updated
            logger.info(f"  Reset batch of {updated} keywords (Total: {total_reset})")
        
        logger.info(f"\n✅ Successfully reset {total_reset} stuck keywords!")
        
        # Close connection to free resources
        connection.close()
        
        return total_reset
        
    except Exception as e:
        logger.error(f"❌ Error resetting keywords: {e}")
        connection.close()
        return 0


def reset_specific_project_keywords(project_id, force=False):
    """Reset stuck keywords for a specific project"""
    from project.models import Project
    
    try:
        project = Project.objects.get(id=project_id)
        stuck_count = Keyword.objects.filter(
            project=project,
            processing=True
        ).count()
        
        logger.info(f"Project: {project.name} ({project.domain})")
        logger.info(f"Stuck keywords: {stuck_count}")
        
        if stuck_count == 0:
            logger.info("✅ No stuck keywords for this project")
            return 0
        
        if not force:
            logger.info("⚠️  To reset, run with --force flag")
            return 0
        
        updated = Keyword.objects.filter(
            project=project,
            processing=True
        ).update(
            processing=False,
            updated_at=timezone.now()
        )
        
        logger.info(f"✅ Reset {updated} keywords for project {project.name}")
        return updated
        
    except Project.DoesNotExist:
        logger.error(f"❌ Project with ID {project_id} not found")
        return 0
    finally:
        connection.close()


def reset_old_stuck_keywords(hours=2, force=False):
    """Reset only keywords that have been stuck for more than X hours"""
    cutoff_time = timezone.now() - timedelta(hours=hours)
    
    stuck_old = Keyword.objects.filter(
        processing=True,
        scraped_at__lt=cutoff_time
    )
    
    stuck_count = stuck_old.count()
    
    logger.info(f"Keywords stuck for more than {hours} hours: {stuck_count}")
    
    if stuck_count == 0:
        logger.info("✅ No old stuck keywords found")
        return 0
    
    if not force:
        logger.info(f"⚠️  To reset these {stuck_count} keywords, run with --force flag")
        return 0
    
    updated = stuck_old.update(
        processing=False,
        updated_at=timezone.now()
    )
    
    logger.info(f"✅ Reset {updated} keywords that were stuck for over {hours} hours")
    connection.close()
    return updated


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Reset stuck keywords')
    parser.add_argument('--force', action='store_true', help='Actually perform the reset')
    parser.add_argument('--project', type=int, help='Reset only keywords for specific project ID')
    parser.add_argument('--old', type=int, help='Reset only keywords stuck for more than X hours')
    parser.add_argument('--info', action='store_true', help='Just show information, don\'t reset')
    
    args = parser.parse_args()
    
    if args.info:
        info = get_stuck_keywords_info()
        print(f"\n📊 Stuck Keywords Summary:")
        print(f"   Total stuck: {info['total_stuck']}")
        print(f"   Stuck > 30min: {info['stuck_over_30min']}")
        print(f"   Never scraped: {info['never_scraped_stuck']}")
        return
    
    if args.project:
        reset_specific_project_keywords(args.project, force=args.force)
    elif args.old:
        reset_old_stuck_keywords(hours=args.old, force=args.force)
    else:
        reset_all_stuck_keywords(force=args.force)


if __name__ == "__main__":
    main()