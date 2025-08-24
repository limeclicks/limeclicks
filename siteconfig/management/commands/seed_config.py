from django.core.management.base import BaseCommand
from django.db import transaction
from siteconfig.models import SiteConfiguration


class Command(BaseCommand):
    help = 'Seed initial site configuration values'

    def handle(self, *args, **options):
        self.stdout.write('Seeding site configuration...')
        
        # Define seed data
        seed_configs = [
            {
                'key': 'KEYWORD_RE_SYNC_TIME',
                'value': '1320',
                'value_type': 'int',
                'description': 'Time in minutes for keyword re-sync operation'
            },
            {
                'key': 'KEYWORD_RE_CRAWL_HOUR_AFTER',
                'value': '60',
                'value_type': 'int',
                'description': 'Hours to wait after initial crawl before re-crawling keywords'
            }
        ]
        
        with transaction.atomic():
            # First, remove any other configurations (as requested)
            existing_keys = [config['key'] for config in seed_configs]
            deleted_count = SiteConfiguration.objects.exclude(key__in=existing_keys).delete()[0]
            if deleted_count > 0:
                self.stdout.write(
                    self.style.WARNING(f'Removed {deleted_count} other configuration(s)')
                )
            
            # Add or update seed configurations
            for config_data in seed_configs:
                config, created = SiteConfiguration.objects.update_or_create(
                    key=config_data['key'],
                    defaults={
                        'value': config_data['value'],
                        'value_type': config_data['value_type'],
                        'description': config_data['description']
                    }
                )
                
                action = 'Created' if created else 'Updated'
                self.stdout.write(
                    self.style.SUCCESS(
                        f'{action}: {config.key} = {config.value} ({config.value_type})'
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS('Site configuration seeded successfully!')
        )
        
        # Display current configurations
        self.stdout.write('\nCurrent configurations:')
        for config in SiteConfiguration.objects.all():
            self.stdout.write(f'  - {config.key}: {config.get_value()} (type: {config.value_type})')