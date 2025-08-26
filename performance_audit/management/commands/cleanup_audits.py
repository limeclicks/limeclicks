"""
Management command to clean up failed or stuck performance audits
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from performance_audit.models import PerformanceHistory
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up failed or stuck performance audits'

    def add_arguments(self, parser):
        parser.add_argument(
            '--retry-failed',
            action='store_true',
            help='Retry failed audits from the last 24 hours',
        )
        parser.add_argument(
            '--cleanup-stuck',
            action='store_true',
            help='Clean up audits stuck in running state for over 10 minutes',
        )
        parser.add_argument(
            '--remove-duplicates',
            action='store_true',
            help='Remove duplicate audits for the same project on the same day',
        )

    def handle(self, *args, **options):
        if options['cleanup_stuck']:
            self.cleanup_stuck_audits()
        
        if options['retry_failed']:
            self.retry_failed_audits()
        
        if options['remove_duplicates']:
            self.remove_duplicate_audits()
        
        if not any([options['cleanup_stuck'], options['retry_failed'], options['remove_duplicates']]):
            self.stdout.write(self.style.WARNING('No action specified. Use --help for options.'))

    def cleanup_stuck_audits(self):
        """Mark audits stuck in running state as failed"""
        stuck_time = timezone.now() - timedelta(minutes=10)
        
        stuck_audits = PerformanceHistory.objects.filter(
            status='running',
            started_at__lt=stuck_time
        )
        
        count = stuck_audits.count()
        if count > 0:
            stuck_audits.update(
                status='failed',
                error_message='Audit timeout - stuck in running state',
                completed_at=timezone.now()
            )
            self.stdout.write(self.style.SUCCESS(f'Marked {count} stuck audits as failed'))
        else:
            self.stdout.write(self.style.SUCCESS('No stuck audits found'))

    def retry_failed_audits(self):
        """Retry failed audits from the last 24 hours"""
        from performance_audit.tasks import run_lighthouse_audit
        
        yesterday = timezone.now() - timedelta(hours=24)
        
        failed_audits = PerformanceHistory.objects.filter(
            status='failed',
            created_at__gte=yesterday,
            retry_count__lt=3  # Don't retry if already retried 3 times
        )
        
        count = 0
        for audit in failed_audits:
            # Reset status to pending
            audit.status = 'pending'
            audit.error_message = None
            audit.save()
            
            # Queue for retry
            run_lighthouse_audit.delay(str(audit.id), audit.device_type)
            count += 1
            
            self.stdout.write(f'Retrying audit {audit.id} for {audit.performance_page.project.domain} ({audit.device_type})')
        
        if count > 0:
            self.stdout.write(self.style.SUCCESS(f'Queued {count} failed audits for retry'))
        else:
            self.stdout.write(self.style.SUCCESS('No failed audits to retry'))

    def remove_duplicate_audits(self):
        """Remove duplicate audits for the same project on the same day"""
        from django.db.models import Count
        
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Find duplicates
        duplicates = PerformanceHistory.objects.filter(
            created_at__gte=today_start,
            status='pending'
        ).values('performance_page', 'device_type').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        total_removed = 0
        for dup in duplicates:
            # Get all duplicates
            all_duplicates = PerformanceHistory.objects.filter(
                performance_page_id=dup['performance_page'],
                device_type=dup['device_type'],
                created_at__gte=today_start,
                status='pending'
            ).order_by('created_at')
            
            # Keep the first one, delete the rest
            if all_duplicates.count() > 1:
                first = all_duplicates.first()
                to_delete = all_duplicates.exclude(id=first.id)
            
                count = to_delete.count()
                if count > 0:
                    to_delete.delete()
                    total_removed += count
                    self.stdout.write(f'Removed {count} duplicate audits for performance_page {dup["performance_page"]} ({dup["device_type"]})')
        
        if total_removed > 0:
            self.stdout.write(self.style.SUCCESS(f'Removed {total_removed} duplicate audits total'))
        else:
            self.stdout.write(self.style.SUCCESS('No duplicate audits found'))