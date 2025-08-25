"""
Run on-page audit for a specific project
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from project.models import Project
from site_audit.models import SiteAudit, OnPagePerformanceHistory
from site_audit.tasks import run_site_audit, run_manual_site_audit
import time


class Command(BaseCommand):
    help = 'Run on-page audit for a specific project'

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
            type=str,
            help='Domain of the project to audit'
        )
        parser.add_argument(
            '--manual',
            action='store_true',
            help='Run as manual audit (respects 3-day rate limit)'
        )
        parser.add_argument(
            '--sync',
            action='store_true',
            help='Run synchronously and wait for completion'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force audit even if rate limited (admin only)'
        )
        parser.add_argument(
            '--max-pages',
            type=int,
            default=500,
            help='Maximum pages to crawl'
        )

    def handle(self, *args, **options):
        domain = options['domain']
        
        self.stdout.write(self.style.NOTICE('=' * 60))
        self.stdout.write(self.style.NOTICE(f'On-Page Audit for {domain}'))
        self.stdout.write(self.style.NOTICE('=' * 60))

        try:
            # Get project
            project = Project.objects.get(domain=domain)
            self.stdout.write(self.style.SUCCESS(f'✓ Found project: {project.title}'))

            # Get or create audit
            audit, created = SiteAudit.objects.get_or_create(
                project=project,
                defaults={'max_pages_to_crawl': options['max_pages']}
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS('✓ Created new SiteAudit record'))
            else:
                self.stdout.write(f'  Using existing audit (ID: {audit.id})')

            # Check rate limiting
            if options['manual'] and not options['force']:
                if not audit.can_run_manual_audit():
                    time_until_next = (audit.last_manual_audit + timezone.timedelta(days=3)) - timezone.now()
                    days = time_until_next.days
                    hours = time_until_next.seconds // 3600
                    self.stdout.write(self.style.ERROR(
                        f'✗ Rate limited: Please wait {days} days and {hours} hours'
                    ))
                    return
            elif not options['force']:
                if not audit.can_run_automatic_audit():
                    time_until_next = (audit.last_automatic_audit + timezone.timedelta(days=30)) - timezone.now()
                    days = time_until_next.days
                    self.stdout.write(self.style.ERROR(
                        f'✗ Rate limited: Please wait {days} days'
                    ))
                    return

            # Create audit history entry
            trigger_type = 'manual' if options['manual'] else 'command'
            performance_history = OnPagePerformanceHistory.objects.create(
                audit=audit,
                trigger_type=trigger_type,
                status='pending',
                max_pages_to_crawl=options['max_pages']
            )
            self.stdout.write(self.style.SUCCESS(f'✓ Created audit history (ID: {performance_history.id})'))

            # Update rate limiting
            if options['manual']:
                audit.last_manual_audit = timezone.now()
            else:
                audit.last_automatic_audit = timezone.now()
            audit.save()

            # Run audit
            if options['sync']:
                self.stdout.write('\nRunning audit synchronously...')
                self.run_audit_sync(performance_history)
            else:
                self.stdout.write('\nQueuing audit to Celery...')
                result = run_site_audit.delay(str(performance_history.id))
                self.stdout.write(self.style.SUCCESS(f'✓ Audit queued (Task ID: {result.id})'))
                self.stdout.write('  Check Django admin for progress')

        except Project.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'✗ Project not found: {domain}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error: {str(e)}'))

    def run_audit_sync(self, performance_history):
        """Run audit synchronously and display progress"""
        from site_audit.screaming_frog import ScreamingFrogCLI
        import json
        from django.core.files.base import ContentFile

        try:
            # Update status
            performance_history.status = 'running'
            performance_history.started_at = timezone.now()
            performance_history.save()

            # Initialize Screaming Frog
            sf_cli = ScreamingFrogCLI()
            
            # Check installation
            if not sf_cli.check_installation():
                self.stdout.write(self.style.ERROR('✗ Screaming Frog is not installed'))
                performance_history.status = 'failed'
                performance_history.error_message = 'Screaming Frog not installed'
                performance_history.save()
                return

            # Prepare URL
            url = performance_history.audit.project.domain
            if not url.startswith(('http://', 'https://')):
                url = f'https://{url}'

            # Configure crawl
            config = {
                'follow_redirects': True,
                'crawl_subdomains': False,
                'check_spelling': True,
                'crawl_depth': performance_history.crawl_depth
            }

            self.stdout.write(f'\nCrawling {url}...')
            self.stdout.write('  This may take several minutes...')

            # Run crawl
            max_pages = performance_history.max_pages_to_crawl
            success, output_dir, error = sf_cli.crawl_website(url, max_pages, config)

            if not success:
                self.stdout.write(self.style.ERROR(f'✗ Crawl failed: {error}'))
                performance_history.status = 'failed'
                performance_history.error_message = error
                performance_history.save()
                return

            self.stdout.write(self.style.SUCCESS('✓ Crawl completed'))

            # Parse results
            self.stdout.write('Parsing results...')
            results = sf_cli.parse_crawl_results(output_dir)

            # Save summary
            performance_history.summary_data = results['summary']
            performance_history.pages_crawled = results['pages_crawled']
            performance_history.issues_summary = {
                'broken_links': results['summary']['broken_links'],
                'redirect_chains': results['summary']['redirect_chains'],
                'missing_titles': results['summary']['missing_titles'],
                'duplicate_titles': results['summary']['duplicate_titles'],
                'missing_meta_descriptions': results['summary']['missing_meta_descriptions'],
                'duplicate_meta_descriptions': results['summary']['duplicate_meta_descriptions'],
                'blocked_by_robots': results['summary']['blocked_by_robots'],
                'missing_hreflang': results['summary']['missing_hreflang'],
                'total_issues': results['summary']['total_issues']
            }
            performance_history.total_issues = results['summary']['total_issues']

            # Save reports
            self.stdout.write('Saving reports to R2...')
            
            # Full report
            full_report = json.dumps(results, indent=2)
            filename = f"{performance_history.audit.project.domain}_{performance_history.id}_full.json"
            performance_history.full_report_json.save(
                filename,
                ContentFile(full_report.encode('utf-8')),
                save=False
            )

            # Issues report
            issues_report = json.dumps(results['details'], indent=2)
            filename = f"{performance_history.audit.project.domain}_{performance_history.id}_issues.json"
            performance_history.issues_report_json.save(
                filename,
                ContentFile(issues_report.encode('utf-8')),
                save=False
            )

            # Update status
            performance_history.status = 'completed'
            performance_history.completed_at = timezone.now()
            performance_history.save()

            # Update main audit
            performance_history.audit.update_from_audit_results(performance_history)

            # Cleanup
            sf_cli.cleanup()

            # Display results
            self.stdout.write('\n' + self.style.SUCCESS('Audit Results:'))
            self.stdout.write('-' * 40)
            self.stdout.write(f"  Pages Crawled: {performance_history.pages_crawled}")
            self.stdout.write(f"  Total Issues: {performance_history.total_issues}")
            
            for key, value in performance_history.issues_summary.items():
                if key != 'total_issues':
                    label = key.replace('_', ' ').title()
                    self.stdout.write(f"  {label}: {value}")

            self.stdout.write('\n' + self.style.SUCCESS('✓ Audit completed successfully'))
            self.stdout.write(f'  View details in Django admin: /admin/site_audit/site_audithistory/{performance_history.id}/')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Audit failed: {str(e)}'))
            performance_history.status = 'failed'
            performance_history.error_message = str(e)
            performance_history.save()