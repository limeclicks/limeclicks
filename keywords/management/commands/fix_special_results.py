"""
Management command to reprocess SERP results and fix special results issue
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from pathlib import Path
from django.conf import settings

from keywords.models import Keyword, Rank
from services.google_search_parser import GoogleSearchParser
from services.r2_storage import get_r2_service


class Command(BaseCommand):
    help = 'Reprocess SERP results to fix special results appearing as organic results'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keyword-id',
            type=int,
            help='Process specific keyword by ID'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making changes'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Limit number of keywords to process'
        )

    def handle(self, *args, **options):
        keyword_id = options.get('keyword_id')
        dry_run = options.get('dry_run')
        limit = options.get('limit')
        
        parser = GoogleSearchParser()
        r2_service = get_r2_service()
        
        if keyword_id:
            keywords = Keyword.objects.filter(id=keyword_id)
        else:
            # Get keywords with recent ranks
            keywords = Keyword.objects.filter(
                archive=False,
                scraped_at__isnull=False
            ).order_by('-scraped_at')[:limit]
        
        self.stdout.write(f"Processing {keywords.count()} keywords...")
        
        fixed_count = 0
        error_count = 0
        
        for keyword in keywords:
            self.stdout.write(f"\nProcessing keyword: {keyword.keyword} (ID: {keyword.id})")
            
            try:
                # Get the latest rank with search results
                latest_rank = Rank.objects.filter(
                    keyword=keyword,
                    search_results_file__isnull=False
                ).order_by('-created_at').first()
                
                if not latest_rank:
                    self.stdout.write(self.style.WARNING("  No rank with search results found"))
                    continue
                
                # Download and reparse the results
                self.stdout.write(f"  Loading results from R2: {latest_rank.search_results_file}")
                search_data = r2_service.download_json(latest_rank.search_results_file)
                
                if not search_data:
                    self.stdout.write(self.style.ERROR("  Failed to load search results"))
                    error_count += 1
                    continue
                
                # Extract the HTML if available (for reparsing)
                if keyword.scrape_do_file_path:
                    storage_root = Path(settings.SCRAPE_DO_STORAGE_ROOT)
                    html_path = storage_root / keyword.scrape_do_file_path
                    
                    if html_path.exists():
                        self.stdout.write("  Found HTML file, reparsing...")
                        html_content = html_path.read_text(encoding='utf-8')
                        
                        # Reparse with updated parser
                        new_results = parser.parse(html_content)
                        
                        # Check for improvements
                        old_organic = search_data.get('results', {}).get('organic_results', [])
                        new_organic = new_results.get('organic_results', [])
                        
                        # Count results without URLs in old data
                        old_no_url = sum(1 for r in old_organic if not r.get('url') or r['url'] == '#')
                        new_no_url = sum(1 for r in new_organic if not r.get('url') or r['url'] == '#')
                        
                        self.stdout.write(f"  Old: {len(old_organic)} results ({old_no_url} without URL)")
                        self.stdout.write(f"  New: {len(new_organic)} results ({new_no_url} without URL)")
                        
                        if old_no_url > 0 and new_no_url == 0:
                            self.stdout.write(self.style.SUCCESS(f"  ✓ Fixed {old_no_url} special results"))
                            fixed_count += 1
                            
                            if not dry_run:
                                # Update R2 with new results
                                updated_data = search_data.copy()
                                updated_data['results'] = new_results
                                updated_data['reprocessed_at'] = timezone.now().isoformat()
                                
                                result = r2_service.upload_json(
                                    updated_data,
                                    latest_rank.search_results_file
                                )
                                
                                if result.get('success'):
                                    self.stdout.write(self.style.SUCCESS("  ✓ Updated R2 storage"))
                                else:
                                    self.stdout.write(self.style.ERROR("  ✗ Failed to update R2"))
                        elif old_no_url == 0:
                            self.stdout.write("  No special results found in old data")
                        else:
                            self.stdout.write("  No improvement after reprocessing")
                    else:
                        self.stdout.write("  HTML file not found")
                else:
                    self.stdout.write("  No HTML file path stored")
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Error: {e}"))
                error_count += 1
        
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"Fixed {fixed_count} keywords"))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"Errors: {error_count}"))
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes were made"))