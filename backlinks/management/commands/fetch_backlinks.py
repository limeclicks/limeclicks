from django.core.management.base import BaseCommand
from django.db.models import Q
from project.models import Project
from backlinks.tasks import fetch_backlink_summary_from_dataforseo, fetch_backlinks_for_all_projects


class Command(BaseCommand):
    help = 'Fetch backlink summaries for projects'

    def add_arguments(self, parser):
        parser.add_argument(
            '--project-id',
            type=int,
            help='Fetch backlinks for specific project ID'
        )
        parser.add_argument(
            '--domain',
            type=str,
            help='Fetch backlinks for specific domain'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Fetch backlinks for all active projects'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without actually processing'
        )
        parser.add_argument(
            '--get-url',
            type=str,
            help='Get signed URL for backlinks file (provide project ID or domain)'
        )

    def handle(self, *args, **options):
        if options['get_url']:
            self.handle_get_signed_url(options['get_url'])
        elif options['project_id']:
            self.fetch_for_project(options['project_id'], options['dry_run'])
        elif options['domain']:
            self.fetch_for_domain(options['domain'], options['dry_run'])
        elif options['all']:
            self.fetch_for_all_projects(options['dry_run'])
        else:
            self.stdout.write(
                self.style.ERROR('Please specify --project-id, --domain, --all, or --get-url')
            )

    def fetch_for_project(self, project_id, dry_run=False):
        """Fetch backlinks for a specific project"""
        try:
            project = Project.objects.get(id=project_id)
            self.stdout.write(f'Processing project {project_id}: {project.domain}')
            
            if dry_run:
                self.stdout.write(self.style.WARNING(f'DRY RUN: Would fetch backlinks for {project.domain}'))
                return
                
            result = fetch_backlink_summary_from_dataforseo.delay(project_id)
            self.stdout.write(
                self.style.SUCCESS(f'Queued backlink fetch for {project.domain} (Task ID: {result.id})')
            )
            
        except Project.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Project with ID {project_id} not found')
            )

    def fetch_for_domain(self, domain, dry_run=False):
        """Fetch backlinks for projects matching a domain"""
        projects = Project.objects.filter(
            Q(domain=domain) | Q(domain__icontains=domain),
            active=True
        )
        
        if not projects.exists():
            self.stdout.write(
                self.style.ERROR(f'No active projects found for domain: {domain}')
            )
            return
            
        self.stdout.write(f'Found {projects.count()} project(s) for domain: {domain}')
        
        for project in projects:
            self.stdout.write(f'Processing project {project.id}: {project.domain}')
            
            if dry_run:
                self.stdout.write(self.style.WARNING(f'DRY RUN: Would fetch backlinks for {project.domain}'))
                continue
                
            result = fetch_backlink_summary_from_dataforseo.delay(project.id)
            self.stdout.write(
                self.style.SUCCESS(f'Queued backlink fetch for {project.domain} (Task ID: {result.id})')
            )

    def fetch_for_all_projects(self, dry_run=False):
        """Fetch backlinks for all active projects"""
        active_projects = Project.objects.filter(active=True)
        total_count = active_projects.count()
        
        self.stdout.write(f'Found {total_count} active projects')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN: Would process the following projects:'))
            for project in active_projects[:10]:  # Show first 10
                self.stdout.write(f'  - {project.id}: {project.domain}')
            if total_count > 10:
                self.stdout.write(f'  ... and {total_count - 10} more projects')
            return
            
        # Use the bulk fetch task
        result = fetch_backlinks_for_all_projects.delay()
        self.stdout.write(
            self.style.SUCCESS(f'Queued bulk backlink fetch for all projects (Task ID: {result.id})')
        )
        
    def handle_get_signed_url(self, project_id_or_domain):
        """Get signed URL for backlinks file"""
        from backlinks.models import BacklinkProfile
        
        try:
            if project_id_or_domain.isdigit():
                profile = BacklinkProfile.objects.filter(project_id=project_id_or_domain).first()
            else:
                profile = BacklinkProfile.objects.filter(target=project_id_or_domain).first()
            
            if not profile:
                self.stdout.write(
                    self.style.ERROR(f'No backlink profile found for: {project_id_or_domain}')
                )
                return
            
            if not profile.backlinks_file_path:
                self.stdout.write(
                    self.style.WARNING(f'No backlinks file found for: {profile.target}')
                )
                return
            
            # Generate 24-hour signed URL
            signed_url = profile.get_backlinks_file_signed_url(expiry_hours=24)
            
            if signed_url:
                self.stdout.write(
                    self.style.SUCCESS(f'Signed URL for {profile.target} (expires in 24 hours):')
                )
                self.stdout.write(signed_url)
                
                # Show file info
                file_info = profile.get_file_info()
                if file_info:
                    self.stdout.write(f'File size: {file_info.get("size", 0):,} bytes')
                    self.stdout.write(f'Collected: {profile.backlinks_count_collected:,} backlinks')
                    self.stdout.write(f'Last updated: {profile.backlinks_collected_at}')
            else:
                self.stdout.write(
                    self.style.ERROR(f'Failed to generate signed URL for: {profile.target}')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error getting signed URL: {str(e)}')
            )