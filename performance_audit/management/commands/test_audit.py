from django.core.management.base import BaseCommand
from django.utils import timezone
from performance_audit.models import PerformancePage, PerformanceHistory
from performance_audit.lighthouse_runner import LighthouseRunner, LighthouseService
from project.models import Project


class Command(BaseCommand):
    help = 'Test Lighthouse audit functionality'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            default='https://www.google.com',
            help='URL to audit'
        )
        parser.add_argument(
            '--device',
            type=str,
            default='desktop',
            choices=['desktop', 'mobile'],
            help='Device type for audit'
        )
        parser.add_argument(
            '--project-id',
            type=int,
            help='Project ID to use for audit'
        )
    
    def handle(self, *args, **options):
        url = options['url']
        device = options['device']
        project_id = options.get('project_id')
        
        self.stdout.write(self.style.SUCCESS(f'Testing Lighthouse audit for {url} ({device})'))
        
        # Check if Lighthouse is installed
        if not LighthouseService.check_lighthouse_installed():
            self.stdout.write(self.style.WARNING('Lighthouse not found, installing...'))
            if not LighthouseService.install_lighthouse():
                self.stdout.write(self.style.ERROR('Failed to install Lighthouse'))
                return
        
        # Create a test audit if project is specified
        performance_history = None
        if project_id:
            try:
                project = Project.objects.get(id=project_id)
                performance_page, created = PerformancePage.objects.get_or_create(
                    project=project,
                    defaults={'page_url': url}
                )
                
                performance_history = PerformanceHistory.objects.create(
                    performance_page=performance_page,
                    trigger_type='manual',
                    device_type=device,
                    status='pending'
                )
                
                self.stdout.write(f'Created audit history: {performance_history.id}')
            except Project.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Project {project_id} not found'))
                return
        
        # Run the audit
        runner = LighthouseRunner()
        success, results, error = runner.run_audit(url, device)
        
        if success:
            self.stdout.write(self.style.SUCCESS('Audit completed successfully!'))
            
            # Display scores
            self.stdout.write('\n--- SCORES ---')
            self.stdout.write(f'Performance: {results.get("performance_score")}')
            self.stdout.write(f'Accessibility: {results.get("accessibility_score")}')
            self.stdout.write(f'Best Practices: {results.get("best_practices_score")}')
            self.stdout.write(f'SEO: {results.get("seo_score")}')
            self.stdout.write(f'PWA: {results.get("pwa_score")}')
            
            # Display metrics
            self.stdout.write('\n--- METRICS ---')
            self.stdout.write(f'First Contentful Paint: {results.get("first_contentful_paint")}s')
            self.stdout.write(f'Largest Contentful Paint: {results.get("largest_contentful_paint")}s')
            self.stdout.write(f'Time to Interactive: {results.get("time_to_interactive")}s')
            self.stdout.write(f'Speed Index: {results.get("speed_index")}s')
            self.stdout.write(f'Total Blocking Time: {results.get("total_blocking_time")}ms')
            self.stdout.write(f'Cumulative Layout Shift: {results.get("cumulative_layout_shift")}')
            
            # Save results if we have an audit history
            if performance_history:
                runner.save_audit_results(performance_history, results)
                self.stdout.write(self.style.SUCCESS(f'\nResults saved to audit history {performance_history.id}'))
                
                # Check if files were saved
                if performance_history.json_report:
                    self.stdout.write(f'JSON report saved: {performance_history.json_report.name}')
                if performance_history.html_report:
                    self.stdout.write(f'HTML report saved: {performance_history.html_report.name}')
        else:
            self.stdout.write(self.style.ERROR(f'Audit failed: {error}'))