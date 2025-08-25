"""
Comprehensive test cases for Lighthouse and OnPage audit systems
"""

import pytest
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from datetime import timedelta
from unittest.mock import Mock, patch, MagicMock
import json
import tempfile
import os

from project.models import Project
from accounts.models import User
from audits.models import AuditPage, AuditHistory
from audits.tasks import run_lighthouse_audit
from audits.lighthouse_runner import LighthouseRunner

from onpageaudit.models import OnPageAudit, OnPageAuditHistory, ScreamingFrogLicense
from onpageaudit.tasks import run_onpage_audit
from onpageaudit.screaming_frog import ScreamingFrogCLI


class LighthouseAuditTestCase(TestCase):
    """Test cases for Lighthouse audit system"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.project = Project.objects.create(
            user=self.user,
            domain='example.com',
            title='Test Project',
            active=True
        )
        self.audit_page = AuditPage.objects.create(
            project=self.project
        )
    
    def test_audit_page_creation(self):
        """Test audit page is created properly"""
        self.assertEqual(self.audit_page.project, self.project)
        self.assertTrue(self.audit_page.is_audit_enabled)
        self.assertEqual(self.audit_page.audit_frequency_days, 30)
    
    def test_manual_audit_rate_limiting(self):
        """Test manual audit rate limiting (1 per day)"""
        # First manual audit should be allowed
        self.assertTrue(self.audit_page.can_run_manual_audit())
        
        # Set last manual audit to now
        self.audit_page.last_manual_audit = timezone.now()
        self.audit_page.save()
        
        # Second manual audit should be blocked
        self.assertFalse(self.audit_page.can_run_manual_audit())
        
        # After 1 day, should be allowed again
        self.audit_page.last_manual_audit = timezone.now() - timedelta(days=1, minutes=1)
        self.audit_page.save()
        self.assertTrue(self.audit_page.can_run_manual_audit())
    
    def test_automatic_audit_rate_limiting(self):
        """Test automatic audit rate limiting (30 days)"""
        # First automatic audit should be allowed
        self.assertTrue(self.audit_page.can_run_automatic_audit())
        
        # Set last automatic audit to now
        self.audit_page.last_automatic_audit = timezone.now()
        self.audit_page.save()
        
        # Should be blocked for 30 days
        self.assertFalse(self.audit_page.can_run_automatic_audit())
        
        # After 30 days, should be allowed
        self.audit_page.last_automatic_audit = timezone.now() - timedelta(days=30, minutes=1)
        self.audit_page.save()
        self.assertTrue(self.audit_page.can_run_automatic_audit())
    
    @patch('audits.lighthouse_runner.subprocess.run')
    def test_lighthouse_runner_headless(self, mock_run):
        """Test Lighthouse runner with headless Chrome"""
        # Mock successful lighthouse run
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            'categories': {
                'performance': {'score': 0.95},
                'accessibility': {'score': 0.88},
                'best-practices': {'score': 0.92},
                'seo': {'score': 0.90}
            },
            'audits': {},
            'finalUrl': 'https://example.com'
        })
        mock_run.return_value = mock_result
        
        runner = LighthouseRunner()
        success, data, error = runner.run_audit('https://example.com', 'mobile')
        
        self.assertTrue(success)
        self.assertIsNotNone(data)
        self.assertIsNone(error)
        
        # Verify headless Chrome flags were used
        call_args = mock_run.call_args[0][0]
        self.assertIn('--chrome-flags', ' '.join(call_args))
        self.assertIn('--headless=new', ' '.join(call_args))
        self.assertIn('--no-sandbox', ' '.join(call_args))
    
    def test_audit_history_creation(self):
        """Test audit history is created properly"""
        audit_history = AuditHistory.objects.create(
            audit_page=self.audit_page,
            mode='mobile',
            trigger_type='manual',
            status='pending'
        )
        
        self.assertEqual(audit_history.audit_page, self.audit_page)
        self.assertEqual(audit_history.mode, 'mobile')
        self.assertEqual(audit_history.status, 'pending')
    
    @patch('audits.tasks.LighthouseRunner')
    def test_run_lighthouse_audit_task(self, mock_runner_class):
        """Test Celery task for running Lighthouse audit"""
        # Create audit history
        audit_history = AuditHistory.objects.create(
            audit_page=self.audit_page,
            mode='desktop',
            trigger_type='automatic',
            status='pending'
        )
        
        # Mock lighthouse runner
        mock_runner = Mock()
        mock_runner.run_audit.return_value = (
            True,
            {
                'categories': {
                    'performance': {'score': 0.95},
                    'accessibility': {'score': 0.88},
                    'best-practices': {'score': 0.92},
                    'seo': {'score': 0.90}
                }
            },
            None
        )
        mock_runner_class.return_value = mock_runner
        
        # Run task
        result = run_lighthouse_audit(str(audit_history.id))
        
        self.assertTrue(result['success'])
        
        # Verify audit history was updated
        audit_history.refresh_from_db()
        self.assertEqual(audit_history.status, 'completed')
        self.assertEqual(audit_history.performance_score, 95)
        self.assertEqual(audit_history.accessibility_score, 88)


class OnPageAuditTestCase(TestCase):
    """Test cases for OnPage audit system using Screaming Frog"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.project = Project.objects.create(
            user=self.user,
            domain='example.com',
            title='Test Project',
            active=True
        )
        self.onpage_audit = OnPageAudit.objects.create(
            project=self.project
        )
    
    def test_onpage_audit_creation(self):
        """Test OnPage audit is created properly"""
        self.assertEqual(self.onpage_audit.project, self.project)
        self.assertTrue(self.onpage_audit.is_audit_enabled)
        self.assertEqual(self.onpage_audit.audit_frequency_days, 30)
        self.assertEqual(self.onpage_audit.manual_audit_frequency_days, 3)
    
    def test_manual_audit_rate_limiting_3_days(self):
        """Test manual audit rate limiting (3 days)"""
        # First manual audit should be allowed
        self.assertTrue(self.onpage_audit.can_run_manual_audit())
        
        # Set last manual audit to now
        self.onpage_audit.last_manual_audit = timezone.now()
        self.onpage_audit.save()
        
        # Second manual audit should be blocked
        self.assertFalse(self.onpage_audit.can_run_manual_audit())
        
        # After 3 days, should be allowed again
        self.onpage_audit.last_manual_audit = timezone.now() - timedelta(days=3, minutes=1)
        self.onpage_audit.save()
        self.assertTrue(self.onpage_audit.can_run_manual_audit())
    
    def test_automatic_audit_rate_limiting_30_days(self):
        """Test automatic audit rate limiting (30 days)"""
        # First automatic audit should be allowed
        self.assertTrue(self.onpage_audit.can_run_automatic_audit())
        
        # Set last automatic audit to now
        self.onpage_audit.last_automatic_audit = timezone.now()
        self.onpage_audit.save()
        
        # Should be blocked for 30 days
        self.assertFalse(self.onpage_audit.can_run_automatic_audit())
        
        # After 30 days, should be allowed
        self.onpage_audit.last_automatic_audit = timezone.now() - timedelta(days=30, minutes=1)
        self.onpage_audit.save()
        self.assertTrue(self.onpage_audit.can_run_automatic_audit())
    
    def test_license_singleton(self):
        """Test ScreamingFrogLicense singleton pattern"""
        # Create first license
        license1 = ScreamingFrogLicense.objects.create(
            license_key='TEST-KEY-123',
            license_status='valid',
            max_urls=10000
        )
        
        # Try to create second license - should update existing
        license2 = ScreamingFrogLicense(
            license_key='NEW-KEY-456',
            license_status='expired'
        )
        license2.save()
        
        # Should only have one license record
        self.assertEqual(ScreamingFrogLicense.objects.count(), 1)
        
        # Should have updated the existing record
        license1.refresh_from_db()
        self.assertEqual(license1.license_key, 'NEW-KEY-456')
    
    def test_license_expiry_checking(self):
        """Test license expiry date checking"""
        license = ScreamingFrogLicense.objects.create(
            license_key='TEST-KEY',
            expiry_date=timezone.now().date() + timedelta(days=30)
        )
        
        # Should not be expired
        self.assertFalse(license.is_expired())
        self.assertEqual(license.days_until_expiry(), 30)
        
        # Set to expired
        license.expiry_date = timezone.now().date() - timedelta(days=1)
        license.save()
        
        self.assertTrue(license.is_expired())
        self.assertEqual(license.days_until_expiry(), -1)
    
    @patch('onpageaudit.screaming_frog.subprocess.run')
    def test_screaming_frog_cli_headless(self, mock_run):
        """Test Screaming Frog CLI runs in headless mode"""
        # Mock successful crawl
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        # Create temp directory for output
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mock CSV files
            self._create_mock_csv_files(temp_dir)
            
            cli = ScreamingFrogCLI()
            cli.temp_dir = temp_dir
            
            # Test crawl command includes headless flag
            success, output_dir, error = cli.crawl_website('https://example.com', 100)
            
            # Verify headless flag was included
            call_args = mock_run.call_args[0][0]
            self.assertIn('--headless', call_args)
    
    def test_comprehensive_seo_issue_detection(self):
        """Test that all SEO issues are properly detected"""
        cli = ScreamingFrogCLI()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mock CSV files with various issues
            self._create_mock_csv_files_with_issues(temp_dir)
            
            # Parse results
            results = cli.parse_crawl_results(temp_dir)
            
            # Verify all issue types are detected
            self.assertGreater(len(results['details']['broken_links']), 0)
            self.assertGreater(len(results['details']['missing_titles']), 0)
            self.assertGreater(len(results['details']['duplicate_titles']), 0)
            self.assertGreater(len(results['details']['title_too_long']), 0)
            self.assertGreater(len(results['details']['missing_meta_descriptions']), 0)
            self.assertGreater(len(results['details']['missing_h1']), 0)
            self.assertGreater(len(results['details']['missing_alt_text']), 0)
            self.assertGreater(len(results['details']['thin_content']), 0)
            self.assertGreater(len(results['details']['slow_pages']), 0)
            
            # Verify summary counts are correct
            self.assertEqual(
                results['summary']['total_issues'],
                sum([
                    len(results['details'][key]) 
                    for key in results['details'] 
                    if isinstance(results['details'][key], list)
                ])
            )
    
    def _create_mock_csv_files(self, temp_dir):
        """Create mock CSV files for testing"""
        # Create internal_all.csv
        internal_csv = os.path.join(temp_dir, 'internal_all.csv')
        with open(internal_csv, 'w') as f:
            f.write('Address,Status Code,Title 1,Meta Description 1,H1-1,Word Count,Size (Bytes),Response Time,Crawl Depth\n')
            f.write('https://example.com/,200,Home Page,Welcome to our site,Welcome,500,50000,1500,0\n')
            f.write('https://example.com/about,200,About Us,Learn about us,About,300,30000,1000,1\n')
    
    def _create_mock_csv_files_with_issues(self, temp_dir):
        """Create mock CSV files with various SEO issues for testing"""
        # Internal URLs with issues
        internal_csv = os.path.join(temp_dir, 'internal_all.csv')
        with open(internal_csv, 'w') as f:
            f.write('Address,Status Code,Title 1,Meta Description 1,H1-1,Word Count,Size (Bytes),Response Time,Crawl Depth\n')
            f.write('https://example.com/,200,Home,Short desc,Home,250,50000,4000,0\n')  # Thin content, slow
            f.write('https://example.com/about,200,,Missing desc,,100,4000000,1000,1\n')  # Missing title/H1, large page
            f.write('https://example.com/orphan,200,Orphan Page,Orphan desc,Orphan,400,30000,1000,5\n')  # Orphan page
        
        # Response codes with broken links
        response_csv = os.path.join(temp_dir, 'response_codes_all.csv')
        with open(response_csv, 'w') as f:
            f.write('Address,Status Code,From,Anchor,Redirect URL,Redirect Chain\n')
            f.write('https://example.com/broken,404,https://example.com/,Click here,,0\n')
            f.write('https://example.com/redirect,301,https://example.com/,Link,https://example.com/final,2\n')
        
        # Page titles with issues
        titles_csv = os.path.join(temp_dir, 'page_titles_all.csv')
        with open(titles_csv, 'w') as f:
            f.write('Address,Title 1,Title 1 Length\n')
            f.write('https://example.com/missing-title,,0\n')
            f.write('https://example.com/long-title,This is a very long title that exceeds the recommended 60 character limit for SEO,85\n')
            f.write('https://example.com/dup1,Duplicate Title,15\n')
            f.write('https://example.com/dup2,Duplicate Title,15\n')
        
        # H1 tags with issues
        h1_csv = os.path.join(temp_dir, 'h1_all.csv')
        with open(h1_csv, 'w') as f:
            f.write('Address,H1-1,H1-2\n')
            f.write('https://example.com/no-h1,,\n')
            f.write('https://example.com/multiple-h1,First H1,Second H1\n')
        
        # Images with missing alt text
        images_csv = os.path.join(temp_dir, 'images_all.csv')
        with open(images_csv, 'w') as f:
            f.write('Address,Destination,Alt Text,Size (Bytes)\n')
            f.write('https://example.com/,https://example.com/image1.jpg,,50000\n')
            f.write('https://example.com/,https://example.com/large.jpg,Large Image,500000\n')


class HeadlessOperationTestCase(TestCase):
    """Test cases to ensure both audit systems work in headless mode"""
    
    @patch('subprocess.run')
    def test_lighthouse_headless_flags(self, mock_run):
        """Verify Lighthouse uses correct headless Chrome flags"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({'categories': {}})
        mock_run.return_value = mock_result
        
        runner = LighthouseRunner()
        runner.run_audit('https://example.com', 'mobile')
        
        # Get the command that was run
        cmd = ' '.join(mock_run.call_args[0][0])
        
        # Verify all required headless flags are present
        required_flags = [
            '--headless=new',
            '--no-sandbox',
            '--disable-gpu',
            '--disable-dev-shm-usage',
            '--disable-web-security',
            '--disable-setuid-sandbox',
            '--no-first-run',
            '--no-zygote',
            '--single-process'
        ]
        
        for flag in required_flags:
            self.assertIn(flag, cmd, f"Missing required flag: {flag}")
    
    @patch('subprocess.run')
    def test_screaming_frog_headless_flag(self, mock_run):
        """Verify Screaming Frog uses headless flag"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        cli = ScreamingFrogCLI()
        cli.crawl_website('https://example.com', 100)
        
        # Get the command that was run
        cmd = mock_run.call_args[0][0]
        
        # Verify headless flag is present
        self.assertIn('--headless', cmd, "Screaming Frog not running in headless mode")


# Run tests with: python manage.py test tests.test_audits