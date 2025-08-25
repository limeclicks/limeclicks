"""
Test Screaming Frog CLI integration and license validation
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from site_audit.screaming_frog import ScreamingFrogCLI, ScreamingFrogService
from site_audit.models import ScreamingFrogLicense
import json
import pprint


class Command(BaseCommand):
    help = 'Test Screaming Frog CLI integration and license validation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            default='https://example.com',
            help='URL to test crawl'
        )
        parser.add_argument(
            '--max-pages',
            type=int,
            default=10,
            help='Maximum pages to crawl'
        )
        parser.add_argument(
            '--validate-license',
            action='store_true',
            help='Validate and display license information'
        )
        parser.add_argument(
            '--test-crawl',
            action='store_true',
            help='Run a test crawl'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('=' * 60))
        self.stdout.write(self.style.NOTICE('Screaming Frog Integration Test'))
        self.stdout.write(self.style.NOTICE('=' * 60))

        # Test license validation
        if options['validate_license'] or not options['test_crawl']:
            self.test_license_validation()

        # Test crawl
        if options['test_crawl']:
            self.test_crawl(options['url'], options['max_pages'])

    def test_license_validation(self):
        """Test license validation and storage"""
        self.stdout.write('\n' + self.style.WARNING('Testing License Validation...'))
        self.stdout.write('-' * 40)

        try:
            # Validate and save license
            license_obj, license_info = ScreamingFrogService.validate_and_save_license()

            self.stdout.write(self.style.SUCCESS('✓ License validation successful'))
            self.stdout.write(f"  License Type: {license_info['type']}")
            self.stdout.write(f"  Valid: {license_info['valid']}")
            self.stdout.write(f"  Message: {license_info['message']}")

            if license_obj:
                self.stdout.write('\nLicense Details:')
                self.stdout.write(f"  License Key: {license_obj.license_key[:10]}...")
                self.stdout.write(f"  Max URLs: {license_obj.max_urls or 'Unlimited'}")
                self.stdout.write(f"  Status: {license_obj.license_status}")
                
                if license_obj.expiry_date:
                    days_until_expiry = license_obj.days_until_expiry()
                    self.stdout.write(f"  Expiry Date: {license_obj.expiry_date}")
                    
                    if days_until_expiry < 0:
                        self.stdout.write(self.style.ERROR(f"  Status: EXPIRED ({abs(days_until_expiry)} days ago)"))
                    elif days_until_expiry <= 30:
                        self.stdout.write(self.style.WARNING(f"  Status: Expiring soon ({days_until_expiry} days)"))
                    else:
                        self.stdout.write(self.style.SUCCESS(f"  Status: Active ({days_until_expiry} days remaining)"))
                else:
                    self.stdout.write(f"  Expiry Date: Not set")

                self.stdout.write(f"  Last Validated: {license_obj.last_validated}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ License validation failed: {str(e)}'))

    def test_crawl(self, url, max_pages):
        """Test website crawl"""
        self.stdout.write('\n' + self.style.WARNING(f'Testing Crawl for {url}...'))
        self.stdout.write('-' * 40)

        try:
            # Check if Screaming Frog is installed
            sf_cli = ScreamingFrogCLI()
            
            if not sf_cli.check_installation():
                self.stdout.write(self.style.ERROR('✗ Screaming Frog is not installed'))
                self.stdout.write('  Please install Screaming Frog SEO Spider first')
                self.stdout.write('  Download from: https://www.screamingfrog.co.uk/seo-spider/')
                return

            self.stdout.write(self.style.SUCCESS('✓ Screaming Frog is installed'))

            # Configure crawl
            config = {
                'follow_redirects': True,
                'crawl_subdomains': False,
                'check_spelling': True,
                'crawl_depth': 3
            }

            self.stdout.write(f'\nStarting crawl with config:')
            for key, value in config.items():
                self.stdout.write(f'  {key}: {value}')

            # Run crawl
            self.stdout.write(f'\nCrawling {url} (max {max_pages} pages)...')
            success, output_dir, error = sf_cli.crawl_website(url, max_pages, config)

            if not success:
                self.stdout.write(self.style.ERROR(f'✗ Crawl failed: {error}'))
                return

            self.stdout.write(self.style.SUCCESS(f'✓ Crawl completed successfully'))
            self.stdout.write(f'  Output directory: {output_dir}')

            # Parse results
            self.stdout.write('\nParsing crawl results...')
            results = sf_cli.parse_crawl_results(output_dir)

            # Display summary
            self.stdout.write('\n' + self.style.SUCCESS('Crawl Summary:'))
            self.stdout.write('-' * 30)
            summary = results['summary']
            self.stdout.write(f"  Pages Crawled: {results['pages_crawled']}")
            self.stdout.write(f"  Total Issues: {summary['total_issues']}")
            self.stdout.write(f"  Broken Links: {summary['broken_links']}")
            self.stdout.write(f"  Redirect Chains: {summary['redirect_chains']}")
            self.stdout.write(f"  Missing Titles: {summary['missing_titles']}")
            self.stdout.write(f"  Duplicate Titles: {summary['duplicate_titles']}")
            self.stdout.write(f"  Missing Meta Descriptions: {summary['missing_meta_descriptions']}")
            self.stdout.write(f"  Duplicate Meta Descriptions: {summary['duplicate_meta_descriptions']}")
            self.stdout.write(f"  Blocked by Robots: {summary['blocked_by_robots']}")
            self.stdout.write(f"  Missing Hreflang: {summary['missing_hreflang']}")
            self.stdout.write(f"  Spelling Errors: {summary.get('spelling_errors', 0)}")

            # Show sample issues
            details = results['details']
            
            if details.get('broken_links'):
                self.stdout.write('\n' + self.style.WARNING('Sample Broken Links:'))
                for link in details['broken_links'][:3]:
                    self.stdout.write(f"  - {link['url']} (Status: {link['status_code']})")

            if details.get('missing_titles'):
                self.stdout.write('\n' + self.style.WARNING('Sample Pages Missing Titles:'))
                for page in details['missing_titles'][:3]:
                    self.stdout.write(f"  - {page['url']}")

            if details.get('duplicate_titles'):
                self.stdout.write('\n' + self.style.WARNING('Sample Duplicate Titles:'))
                for dup in details['duplicate_titles'][:2]:
                    self.stdout.write(f"  Title: \"{dup['title']}\"")
                    for url in dup['urls'][:2]:
                        self.stdout.write(f"    - {url}")

            # Cleanup
            self.stdout.write('\nCleaning up temporary files...')
            sf_cli.cleanup()
            self.stdout.write(self.style.SUCCESS('✓ Cleanup completed'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Test crawl failed: {str(e)}'))
            import traceback
            self.stdout.write(traceback.format_exc())

        self.stdout.write('\n' + self.style.NOTICE('=' * 60))
        self.stdout.write(self.style.SUCCESS('Test completed'))