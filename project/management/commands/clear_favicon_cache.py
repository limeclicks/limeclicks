from django.core.management.base import BaseCommand
from django.core.cache import cache
from project.models import Project
import hashlib


class Command(BaseCommand):
    help = 'Clear favicon cache for all projects or specific domains'

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain',
            type=str,
            help='Clear cache for specific domain only',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Clear cache for all project domains',
        )

    def handle(self, *args, **options):
        domain = options.get('domain')
        clear_all = options.get('all')

        if domain:
            # Clear cache for specific domain
            self.clear_domain_cache(domain)
        elif clear_all:
            # Clear cache for all project domains
            self.clear_all_project_caches()
        else:
            self.stdout.write(
                self.style.ERROR('Please specify either --domain <domain> or --all')
            )
            return

    def clear_domain_cache(self, domain):
        """Clear favicon cache for a specific domain"""
        sizes = [16, 32, 64, 128, 256]
        domain_hash = hashlib.md5(domain.encode()).hexdigest()
        
        cleared_count = 0
        for size in sizes:
            cache_key = f"favicon_{domain_hash}_{size}"
            if cache.get(cache_key):
                cache.delete(cache_key)
                cleared_count += 1
                self.stdout.write(f"Cleared cache for {domain} (size {size})")
        
        if cleared_count == 0:
            self.stdout.write(
                self.style.WARNING(f'No cached favicons found for {domain}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Cleared {cleared_count} cached favicons for {domain}')
            )

    def clear_all_project_caches(self):
        """Clear favicon cache for all project domains"""
        projects = Project.objects.values_list('domain', flat=True).distinct()
        total_cleared = 0
        
        for domain in projects:
            sizes = [16, 32, 64, 128, 256]
            domain_hash = hashlib.md5(domain.encode()).hexdigest()
            
            for size in sizes:
                cache_key = f"favicon_{domain_hash}_{size}"
                if cache.get(cache_key):
                    cache.delete(cache_key)
                    total_cleared += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Cleared {total_cleared} cached favicons for {len(projects)} domains')
        )