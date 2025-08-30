"""
Management command to clean up Screaming Frog temporary data and caches
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime
import shutil
from pathlib import Path
import glob
import pytz


class Command(BaseCommand):
    help = 'Clean up Screaming Frog temporary crawl data and application cache'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Clean up data older than this many hours (default: 24)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force cleanup of all SF data regardless of age'
        )

    def handle(self, *args, **options):
        hours_old = options['hours']
        dry_run = options['dry_run']
        force = options['force']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No files will be deleted'))
        
        if force:
            self.stdout.write(self.style.WARNING('FORCE MODE - All SF data will be cleaned'))
            hours_old = 0
        
        self.stdout.write(f'Cleaning up Screaming Frog data older than {hours_old} hours...\n')
        
        stats = {
            'temp_dirs': 0,
            'temp_size': 0,
            'sf_instances': 0,
            'sf_size': 0
        }
        
        cutoff_time = timezone.now() - timedelta(hours=hours_old) if not force else None
        
        # 1. Clean temporary crawl directories
        self.stdout.write('Checking /tmp/sf_crawl_* directories...')
        temp_dirs = glob.glob('/tmp/sf_crawl_*')
        
        for temp_dir in temp_dirs:
            dir_path = Path(temp_dir)
            if not dir_path.exists():
                continue
            
            # Check age if not forcing
            if not force:
                mtime = datetime.fromtimestamp(dir_path.stat().st_mtime, tz=pytz.UTC)
                if mtime >= cutoff_time:
                    continue
            
            # Calculate size
            dir_size = sum(f.stat().st_size for f in dir_path.rglob('*') if f.is_file())
            stats['temp_size'] += dir_size
            
            self.stdout.write(f'  - {temp_dir} ({dir_size/1024/1024:.2f} MB)')
            
            if not dry_run:
                try:
                    shutil.rmtree(temp_dir)
                    self.stdout.write(self.style.SUCCESS(f'    ✓ Removed'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'    ✗ Failed: {e}'))
            
            stats['temp_dirs'] += 1
        
        # 2. Clean Screaming Frog ProjectInstanceData
        self.stdout.write('\nChecking Screaming Frog ProjectInstanceData...')
        sf_home = Path.home() / '.ScreamingFrogSEOSpider'
        project_data_dir = sf_home / 'ProjectInstanceData'
        
        if project_data_dir.exists():
            for instance_dir in project_data_dir.iterdir():
                if not instance_dir.is_dir():
                    continue
                
                # Check age if not forcing
                if not force:
                    mtime = datetime.fromtimestamp(instance_dir.stat().st_mtime, tz=pytz.UTC)
                    if mtime >= cutoff_time:
                        continue
                
                # Calculate size
                dir_size = sum(f.stat().st_size for f in instance_dir.rglob('*') if f.is_file())
                stats['sf_size'] += dir_size
                
                self.stdout.write(f'  - {instance_dir.name} ({dir_size/1024/1024:.2f} MB)')
                
                if not dry_run:
                    try:
                        shutil.rmtree(instance_dir)
                        self.stdout.write(self.style.SUCCESS(f'    ✓ Removed'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'    ✗ Failed: {e}'))
                
                stats['sf_instances'] += 1
        
        # 3. Clean other SF cache files if forced
        if force and not dry_run:
            self.stdout.write('\nCleaning Screaming Frog cache files...')
            cache_files = [
                sf_home / 'trace.txt',
                sf_home / 'trace.txt.1',
                sf_home / 'crash.txt',
                sf_home / 'history.log'
            ]
            
            for cache_file in cache_files:
                if cache_file.exists():
                    try:
                        cache_file.unlink()
                        self.stdout.write(self.style.SUCCESS(f'  ✓ Removed {cache_file.name}'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  ✗ Failed to remove {cache_file.name}: {e}'))
        
        # Print summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('CLEANUP SUMMARY:'))
        self.stdout.write(f'Temporary directories: {stats["temp_dirs"]} ({stats["temp_size"]/1024/1024:.2f} MB)')
        self.stdout.write(f'SF instances: {stats["sf_instances"]} ({stats["sf_size"]/1024/1024:.2f} MB)')
        self.stdout.write(f'Total space {"would be" if dry_run else ""} freed: {(stats["temp_size"] + stats["sf_size"])/1024/1024:.2f} MB')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No files were actually deleted'))
            self.stdout.write('Run without --dry-run to perform actual cleanup')