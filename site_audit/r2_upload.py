"""
R2 upload utilities for site audit CSV files with retention management
"""

import os
import io
import csv
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from django.db import transaction
from django.utils import timezone
from limeclicks.storage_backends import CloudflareR2Storage

logger = logging.getLogger(__name__)


class AuditFileUploader:
    """Handle uploading audit CSV files to R2 with retention management"""
    
    def __init__(self, site_audit):
        self.site_audit = site_audit
        self.storage = CloudflareR2Storage()
        self.project = site_audit.project
        
    def upload_audit_files(self, audit_dir: str) -> Dict[str, any]:
        """
        Upload all CSV files from audit directory to R2.
        
        Args:
            audit_dir: Path to the directory containing audit CSV files
            
        Returns:
            Dict with upload statistics and results
        """
        from .models import AuditFile
        
        audit_path = Path(audit_dir)
        if not audit_path.exists():
            logger.error(f"Audit directory not found: {audit_dir}")
            return {"error": "Audit directory not found"}
        
        results = {
            "uploaded": [],
            "failed": [],
            "total_size": 0,
            "file_count": 0
        }
        
        # Map filenames to file types
        file_type_mapping = {
            'crawl_overview': ['crawl_overview'],
            'issues_overview': ['issues_overview', 'issues_reports'],
            'internal_all': ['internal_all', 'internal_html'],
            'external_all': ['external_all', 'external_html'],
            'response_codes': ['response_codes', 'client_error', 'server_error'],
            'page_titles': ['page_titles', 'page_title', 'titles'],
            'meta_descriptions': ['meta_description', 'meta_desc'],
            'h1': ['h1_all', 'h1_1', 'h1-all'],
            'h2': ['h2_all', 'h2_1', 'h2-all'],
            'images': ['images', 'images_missing_alt'],
            'canonicals': ['canonical', 'canonicals'],
            'directives': ['directives', 'robots'],
            'hreflang': ['hreflang'],
            'structured_data': ['structured_data', 'schema'],
            'links': ['links', 'inlinks', 'outlinks'],
            'javascript': ['javascript', 'js'],
            'validation': ['validation', 'html_validation'],
        }
        
        # Find all CSV files
        csv_files = list(audit_path.glob('*.csv'))
        logger.info(f"Found {len(csv_files)} CSV files to upload")
        
        with transaction.atomic():
            for csv_file in csv_files:
                try:
                    # Determine file type
                    file_type = self._determine_file_type(csv_file.name, file_type_mapping)
                    
                    # Calculate checksum
                    checksum = self._calculate_checksum(csv_file)
                    
                    # Generate R2 path with timestamp
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    r2_path = f"site_audits/{self.project.domain}/{timestamp}/{csv_file.name}"
                    
                    # Read file content
                    with open(csv_file, 'rb') as f:
                        file_content = f.read()
                    
                    # Upload to R2
                    file_obj = io.BytesIO(file_content)
                    saved_path = self.storage.save(r2_path, file_obj)
                    
                    # Get file size
                    file_size = len(file_content)
                    
                    # Create database record
                    audit_file = AuditFile.objects.create(
                        site_audit=self.site_audit,
                        file_type=file_type,
                        original_filename=csv_file.name,
                        r2_path=saved_path,
                        file_size=file_size,
                        mime_type='text/csv',
                        checksum=checksum
                    )
                    
                    results["uploaded"].append({
                        "filename": csv_file.name,
                        "r2_path": saved_path,
                        "size": file_size,
                        "type": file_type
                    })
                    results["total_size"] += file_size
                    results["file_count"] += 1
                    
                    logger.info(f"Uploaded {csv_file.name} to R2: {saved_path}")
                    
                except Exception as e:
                    logger.error(f"Failed to upload {csv_file.name}: {e}")
                    results["failed"].append({
                        "filename": csv_file.name,
                        "error": str(e)
                    })
        
        # Apply retention policy after successful upload
        if results["file_count"] > 0:
            self.apply_retention_policy()
        
        return results
    
    def _determine_file_type(self, filename: str, mapping: Dict) -> str:
        """Determine file type based on filename"""
        filename_lower = filename.lower()
        
        for file_type, patterns in mapping.items():
            for pattern in patterns:
                if pattern in filename_lower:
                    return file_type
        
        return 'other'
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate MD5 checksum of a file"""
        md5_hash = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    
    def apply_retention_policy(self, keep_count: int = 2):
        """
        Apply retention policy to keep only the most recent N successful audits.
        Deletes older audit files from both R2 and database.
        
        Args:
            keep_count: Number of successful audits to keep (default: 2)
        """
        from .models import SiteAudit, AuditFile
        
        logger.info(f"Applying retention policy for {self.project.domain} (keep {keep_count} audits)")
        
        # Get all successful audits for this project, ordered by date
        successful_audits = SiteAudit.objects.filter(
            project=self.project,
            status='completed'
        ).order_by('-last_audit_date')
        
        # If we have more than keep_count audits, delete the older ones
        if successful_audits.count() > keep_count:
            audits_to_delete = successful_audits[keep_count:]
            
            for audit in audits_to_delete:
                # Get all files associated with this audit
                audit_files = AuditFile.objects.filter(site_audit=audit)
                
                for audit_file in audit_files:
                    try:
                        # Delete from R2
                        if audit_file.r2_path:
                            self.storage.delete(audit_file.r2_path)
                            logger.info(f"Deleted from R2: {audit_file.r2_path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete from R2: {audit_file.r2_path} - {e}")
                
                # Delete audit file records (cascade will handle related data)
                deleted_count = audit_files.delete()[0]
                logger.info(f"Deleted {deleted_count} audit file records for audit {audit.id}")
        
        logger.info(f"Retention policy applied. Keeping {min(successful_audits.count(), keep_count)} audits")
    
    def get_audit_files_summary(self) -> Dict:
        """Get summary of uploaded files for this audit"""
        from .models import AuditFile
        
        audit_files = AuditFile.objects.filter(site_audit=self.site_audit)
        
        summary = {
            "total_files": audit_files.count(),
            "total_size": sum(f.file_size for f in audit_files),
            "files_by_type": {}
        }
        
        for audit_file in audit_files:
            file_type = audit_file.get_file_type_display()
            if file_type not in summary["files_by_type"]:
                summary["files_by_type"][file_type] = {
                    "count": 0,
                    "size": 0,
                    "files": []
                }
            
            summary["files_by_type"][file_type]["count"] += 1
            summary["files_by_type"][file_type]["size"] += audit_file.file_size
            summary["files_by_type"][file_type]["files"].append({
                "filename": audit_file.original_filename,
                "size": audit_file.file_size,
                "uploaded_at": audit_file.uploaded_at.isoformat()
            })
        
        return summary


def cleanup_old_r2_files(days_to_keep: int = 90):
    """
    Cleanup old R2 files that are no longer referenced in the database.
    This is a maintenance task that should run periodically.
    
    Args:
        days_to_keep: Keep files newer than this many days
    """
    from .models import AuditFile
    
    cutoff_date = timezone.now() - timezone.timedelta(days=days_to_keep)
    
    # Find old audit files
    old_files = AuditFile.objects.filter(uploaded_at__lt=cutoff_date)
    
    storage = CloudflareR2Storage()
    deleted_count = 0
    
    for audit_file in old_files:
        try:
            if audit_file.r2_path:
                storage.delete(audit_file.r2_path)
                deleted_count += 1
                logger.info(f"Deleted old R2 file: {audit_file.r2_path}")
        except Exception as e:
            logger.warning(f"Failed to delete R2 file: {audit_file.r2_path} - {e}")
    
    # Delete database records
    old_files.delete()
    
    logger.info(f"Cleaned up {deleted_count} old R2 files older than {days_to_keep} days")
    
    return deleted_count