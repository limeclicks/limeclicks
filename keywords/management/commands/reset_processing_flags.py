"""
Management command to reset processing flags for keywords
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from keywords.models import Keyword


class Command(BaseCommand):
    help = 'Reset processing flags for keywords that may be stuck'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Reset all processing flags',
        )
        parser.add_argument(
            '--stuck',
            action='store_true',
            help='Reset only keywords stuck in processing for over 1 hour',
        )

    def handle(self, *args, **options):
        if options['all']:
            count = Keyword.objects.filter(processing=True).update(processing=False)
            self.stdout.write(
                self.style.SUCCESS(f'Reset processing flag for {count} keywords')
            )
        elif options['stuck']:
            # Find keywords that have been processing for over 1 hour
            one_hour_ago = timezone.now() - timedelta(hours=1)
            stuck_keywords = Keyword.objects.filter(
                processing=True,
                updated_at__lte=one_hour_ago
            )
            count = stuck_keywords.update(processing=False)
            self.stdout.write(
                self.style.SUCCESS(f'Reset {count} stuck keywords')
            )
        else:
            # Show current status
            processing = Keyword.objects.filter(processing=True).count()
            total = Keyword.objects.filter(archive=False).count()
            self.stdout.write(
                f'Keywords currently processing: {processing}/{total}'
            )
            
            # Show recently scraped
            recent = Keyword.objects.filter(
                scraped_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            self.stdout.write(
                f'Keywords scraped in last hour: {recent}'
            )