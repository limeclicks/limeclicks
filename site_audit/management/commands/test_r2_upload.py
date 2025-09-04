"""
Test command for R2 upload functionality
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from site_audit.models import SiteAudit
from site_audit.r2_upload import AuditFileUploader


class Command(BaseCommand):
    help = 'Test R2 upload functionality for site audit CSV files'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--project-id',
            type=int,
            help='Project ID to test with'
        )
        parser.add_argument(
            '--audit-dir',
            type=str,
            help='Path to audit directory containing CSV files'
        )
        parser.add_argument(
            '--test-retention',
            action='store_true',
            help='Test retention policy'
        )
    
    def handle(self, *args, **options):
        if options['test_retention']:
            self.test_retention_policy(options.get('project_id'))
        elif options['audit_dir']:
            self.test_upload(options['audit_dir'], options.get('project_id'))
        else:
            self.stdout.write(self.style.ERROR('Please provide --audit-dir or --test-retention'))
    
    def test_upload(self, audit_dir, project_id=None):
        """Test uploading CSV files from a directory"""
        # Get or create a test audit
        if project_id:
            try:
                from project.models import Project
                project = Project.objects.get(id=project_id)
                site_audit = SiteAudit.objects.filter(project=project).first()
                if not site_audit:
                    site_audit = SiteAudit.objects.create(
                        project=project,
                        status='completed',
                        last_audit_date=timezone.now()
                    )
                    self.stdout.write(f"Created test site audit for {project.domain}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to get project: {e}"))
                return
        else:
            # Use the first available site audit
            site_audit = SiteAudit.objects.filter(status='completed').first()
            if not site_audit:
                self.stdout.write(self.style.ERROR("No completed site audits found"))
                return
        
        self.stdout.write(f"Using site audit: {site_audit}")
        
        # Test upload
        uploader = AuditFileUploader(site_audit)
        results = uploader.upload_audit_files(audit_dir)
        
        if 'error' in results:
            self.stdout.write(self.style.ERROR(f"Upload failed: {results['error']}"))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Successfully uploaded {results['file_count']} files "
                f"({results['total_size'] / 1024 / 1024:.2f} MB)"
            ))
            
            # Show uploaded files
            for file_info in results.get('uploaded', []):
                self.stdout.write(
                    f"  - {file_info['filename']} -> {file_info['r2_path']} "
                    f"({file_info['size'] / 1024:.2f} KB)"
                )
            
            # Show summary
            summary = uploader.get_audit_files_summary()
            self.stdout.write(f"\nSummary:")
            self.stdout.write(f"  Total files: {summary['total_files']}")
            self.stdout.write(f"  Total size: {summary['total_size'] / 1024 / 1024:.2f} MB")
            
            for file_type, info in summary['files_by_type'].items():
                self.stdout.write(f"  {file_type}: {info['count']} files ({info['size'] / 1024:.2f} KB)")
    
    def test_retention_policy(self, project_id=None):
        """Test retention policy"""
        if project_id:
            try:
                from project.models import Project
                project = Project.objects.get(id=project_id)
                site_audit = SiteAudit.objects.filter(
                    project=project,
                    status='completed'
                ).order_by('-last_audit_date').first()
                
                if not site_audit:
                    self.stdout.write(self.style.ERROR(f"No completed audits for project {project.domain}"))
                    return
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to get project: {e}"))
                return
        else:
            site_audit = SiteAudit.objects.filter(status='completed').order_by('-last_audit_date').first()
            if not site_audit:
                self.stdout.write(self.style.ERROR("No completed site audits found"))
                return
        
        self.stdout.write(f"Testing retention policy for {site_audit.project.domain}")
        
        # Show current audits before
        from site_audit.models import SiteAudit, AuditFile
        audits_before = SiteAudit.objects.filter(
            project=site_audit.project,
            status='completed'
        ).order_by('-last_audit_date')
        
        self.stdout.write(f"\nBefore retention policy:")
        for audit in audits_before:
            file_count = AuditFile.objects.filter(site_audit=audit).count()
            self.stdout.write(
                f"  - Audit {audit.id} from {audit.last_audit_date}: {file_count} files"
            )
        
        # Apply retention policy
        uploader = AuditFileUploader(site_audit)
        uploader.apply_retention_policy(keep_count=2)
        
        # Show after
        audits_after = SiteAudit.objects.filter(
            project=site_audit.project,
            status='completed'
        ).order_by('-last_audit_date')
        
        self.stdout.write(f"\nAfter retention policy (keeping 2):")
        for audit in audits_after:
            file_count = AuditFile.objects.filter(site_audit=audit).count()
            self.stdout.write(
                f"  - Audit {audit.id} from {audit.last_audit_date}: {file_count} files"
            )
        
        self.stdout.write(self.style.SUCCESS("\nRetention policy applied successfully"))