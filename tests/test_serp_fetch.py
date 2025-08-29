"""
Comprehensive tests for SERP HTML fetching and storage
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import shutil

from django.test import TestCase, override_settings
from django.utils import timezone
from django.core.cache import cache

from keywords.models import Keyword
from keywords.tasks import fetch_keyword_serp_html
from project.models import Project
from accounts.models import User


@pytest.fixture
def temp_storage(tmp_path):
    """Create temporary storage directory for tests"""
    storage_dir = tmp_path / "test_storage"
    storage_dir.mkdir()
    return str(storage_dir)


class SERPFetchTestCase(TestCase):
    """Test cases for SERP fetching"""
    
    def setUp(self):
        """Set up test data"""
        cache.clear()
        
        # Create test user and project
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.project = Project.objects.create(
            user=self.user,
            domain='example.com',
            title='Test Project',
            active=True
        )
        
        # Create test keyword
        self.keyword = Keyword.objects.create(
            project=self.project,
            keyword='test keyword',
            country='US',
            country_code='US'
        )
        
        # Create temp storage directory
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up"""
        cache.clear()
        # Clean up temp directory
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    @override_settings(
        SCRAPE_DO_STORAGE_ROOT='/tmp/test_storage',
        SCRAPE_DO_TIMEOUT=60,
        SCRAPE_DO_RETRIES=3,
        SERP_HISTORY_DAYS=7,
        FETCH_MIN_INTERVAL_HOURS=24
    )
    @patch('keywords.tasks.ScrapeDoService')
    def test_successful_fetch_and_storage(self, mock_scraper_class):
        """Test successful SERP fetch and file storage"""
        # Setup mock
        mock_scraper = Mock()
        mock_scraper_class.return_value = mock_scraper
        mock_scraper.scrape_google_search.return_value = {
            'status_code': 200,
            'html': '<html>Test SERP HTML</html>',
            'success': True
        }
        
        with override_settings(SCRAPE_DO_STORAGE_ROOT=self.temp_dir):
            # Execute task
            fetch_keyword_serp_html(self.keyword.id)
        
        # Reload keyword
        self.keyword.refresh_from_db()
        
        # Assertions
        self.assertIsNotNone(self.keyword.scraped_at)
        self.assertEqual(self.keyword.success_api_hit_count, 1)
        self.assertEqual(self.keyword.failed_api_hit_count, 0)
        self.assertIsNone(self.keyword.last_error_message)
        
        # Check file was created
        expected_path = f"{self.project.id}/{self.keyword.id}/{datetime.now().strftime('%Y-%m-%d')}.html"
        self.assertEqual(self.keyword.scrape_do_file_path, expected_path)
        self.assertEqual(len(self.keyword.scrape_do_files), 1)
        self.assertEqual(self.keyword.scrape_do_files[0], expected_path)
        
        # Check actual file exists
        file_path = Path(self.temp_dir) / expected_path
        self.assertTrue(file_path.exists())
        content = file_path.read_text()
        self.assertEqual(content, '<html>Test SERP HTML</html>')
    
    @override_settings(SCRAPE_DO_STORAGE_ROOT='/tmp/test_storage')
    @patch('keywords.tasks.ScrapeDoService')
    def test_failed_fetch_non_200(self, mock_scraper_class):
        """Test handling of non-200 response"""
        # Setup mock
        mock_scraper = Mock()
        mock_scraper_class.return_value = mock_scraper
        mock_scraper.scrape_google_search.return_value = {
            'status_code': 429,
            'success': False
        }
        
        with override_settings(SCRAPE_DO_STORAGE_ROOT=self.temp_dir):
            # Execute task
            fetch_keyword_serp_html(self.keyword.id)
        
        # Reload keyword
        self.keyword.refresh_from_db()
        
        # Assertions
        self.assertIsNone(self.keyword.scraped_at)
        self.assertEqual(self.keyword.success_api_hit_count, 0)
        self.assertEqual(self.keyword.failed_api_hit_count, 1)
        self.assertEqual(self.keyword.last_error_message, 'HTTP 429')
        self.assertIsNone(self.keyword.scrape_do_file_path)
        self.assertEqual(len(self.keyword.scrape_do_files), 0)
        
        # Check no file was created
        project_dir = Path(self.temp_dir) / str(self.project.id)
        self.assertFalse(project_dir.exists())
    
    @override_settings(
        SCRAPE_DO_STORAGE_ROOT='/tmp/test_storage',
        SCRAPE_DO_RETRIES=3
    )
    @patch('keywords.tasks.ScrapeDoService')
    def test_timeout_with_retries(self, mock_scraper_class):
        """Test timeout handling with retries"""
        # Setup mock
        mock_scraper = Mock()
        mock_scraper_class.return_value = mock_scraper
        mock_scraper.scrape_google_search.side_effect = TimeoutError("Request timeout")
        
        with override_settings(SCRAPE_DO_STORAGE_ROOT=self.temp_dir):
            # Execute task
            fetch_keyword_serp_html(self.keyword.id)
        
        # Should retry 3 times
        self.assertEqual(mock_scraper.scrape_google_search.call_count, 3)
        
        # Reload keyword
        self.keyword.refresh_from_db()
        
        # Assertions
        self.assertEqual(self.keyword.failed_api_hit_count, 1)
        self.assertEqual(self.keyword.last_error_message, 'Timeout')
    
    @override_settings(
        SCRAPE_DO_STORAGE_ROOT='/tmp/test_storage',
        SERP_HISTORY_DAYS=7
    )
    @patch('keywords.tasks.ScrapeDoService')
    def test_file_rotation_keeps_last_7(self, mock_scraper_class):
        """Test that file rotation keeps only last 7 files"""
        # Setup mock
        mock_scraper = Mock()
        mock_scraper_class.return_value = mock_scraper
        
        with override_settings(SCRAPE_DO_STORAGE_ROOT=self.temp_dir):
            # Pre-populate with 7 existing files
            existing_files = []
            base_dir = Path(self.temp_dir) / str(self.project.id) / str(self.keyword.id)
            base_dir.mkdir(parents=True, exist_ok=True)
            
            for i in range(7):
                date_str = (datetime.now() - timedelta(days=i+1)).strftime('%Y-%m-%d')
                file_path = base_dir / f"{date_str}.html"
                file_path.write_text(f"Old content {i}")
                relative_path = f"{self.project.id}/{self.keyword.id}/{date_str}.html"
                existing_files.append(relative_path)
            
            # Set existing files in keyword (reverse order - oldest last)
            self.keyword.scrape_do_files = existing_files
            self.keyword.save()
            
            # Now fetch new content
            mock_scraper.scrape_google_search.return_value = {
                'status_code': 200,
                'html': '<html>New content</html>',
                'success': True
            }
            
            fetch_keyword_serp_html(self.keyword.id)
        
        # Reload keyword
        self.keyword.refresh_from_db()
        
        # Should have exactly 7 files
        self.assertEqual(len(self.keyword.scrape_do_files), 7)
        
        # Latest file should be at index 0
        today_path = f"{self.project.id}/{self.keyword.id}/{datetime.now().strftime('%Y-%m-%d')}.html"
        self.assertEqual(self.keyword.scrape_do_files[0], today_path)
        
        # Oldest file should have been deleted
        oldest_path = Path(self.temp_dir) / existing_files[-1]
        self.assertFalse(oldest_path.exists())
    
    @override_settings(
        FETCH_MIN_INTERVAL_HOURS=24
    )
    def test_24_hour_rule_enforcement(self):
        """Test that keywords are not fetched if scraped < 24h ago"""
        # Set scraped_at to 12 hours ago
        self.keyword.scraped_at = timezone.now() - timedelta(hours=12)
        self.keyword.save()
        
        with patch('keywords.tasks.ScrapeDoService') as mock_scraper_class:
            fetch_keyword_serp_html(self.keyword.id)
            
            # Should not have called scraper
            mock_scraper_class.assert_not_called()
    
    def test_queue_routing_cold_keywords(self):
        """Test that cold keywords (never scraped) go to high priority queue"""
        # Create cold keyword (never scraped)
        cold_keyword = Keyword.objects.create(
            project=self.project,
            keyword='cold keyword',
            country='US',
            scraped_at=None,
            processing=False
        )
        
        with patch('keywords.tasks.fetch_keyword_serp_html.apply_async') as mock_apply:
            from keywords.tasks import enqueue_keyword_scrapes_batch
            result = enqueue_keyword_scrapes_batch()
            
            # Check that cold keyword was enqueued to serp_high
            calls = mock_apply.call_args_list
            cold_call = None
            for call in calls:
                if call[1]['args'][0] == cold_keyword.id:
                    cold_call = call
                    break
            
            self.assertIsNotNone(cold_call)
            self.assertEqual(cold_call[1]['queue'], 'serp_high')
            self.assertEqual(cold_call[1]['priority'], 10)
            
            # Check that processing flag was set
            cold_keyword.refresh_from_db()
            self.assertTrue(cold_keyword.processing)
    
    def test_queue_routing_regular_keywords(self):
        """Test that previously scraped keywords go to default queue"""
        # Create regular keyword that was scraped before
        regular_keyword = Keyword.objects.create(
            project=self.project,
            keyword='regular keyword',
            country='US',
            scraped_at=timezone.now() - timedelta(hours=25),
            processing=False
        )
        
        with patch('keywords.tasks.fetch_keyword_serp_html.apply_async') as mock_apply:
            from keywords.tasks import enqueue_keyword_scrapes_batch
            result = enqueue_keyword_scrapes_batch()
            
            # Check that regular keyword was enqueued to serp_default
            calls = mock_apply.call_args_list
            regular_call = None
            for call in calls:
                if call[1]['args'][0] == regular_keyword.id:
                    regular_call = call
                    break
            
            self.assertIsNotNone(regular_call)
            self.assertEqual(regular_call[1]['queue'], 'serp_default')
            self.assertEqual(regular_call[1]['priority'], 5)
    
    def test_locking_prevents_concurrent_execution(self):
        """Test that locking prevents concurrent task execution"""
        # Acquire lock manually
        lock_key = f"lock:serp:{self.keyword.id}"
        cache.add(lock_key, "locked", timeout=300)
        
        with patch('keywords.tasks.ScrapeDoService') as mock_scraper_class:
            fetch_keyword_serp_html(self.keyword.id)
            
            # Should not have called scraper due to lock
            mock_scraper_class.assert_not_called()
        
        # Clean up lock
        cache.delete(lock_key)
    
    @override_settings(SCRAPE_DO_STORAGE_ROOT='/tmp/test_storage')
    @patch('keywords.tasks.ScrapeDoService')
    def test_partial_write_cleanup(self, mock_scraper_class):
        """Test cleanup of partial file writes on error"""
        mock_scraper = Mock()
        mock_scraper_class.return_value = mock_scraper
        mock_scraper.scrape_google_search.return_value = {
            'status_code': 200,
            'html': '<html>Test</html>',
            'success': True
        }
        
        with override_settings(SCRAPE_DO_STORAGE_ROOT=self.temp_dir):
            # Patch Path.write_text to simulate write error
            with patch.object(Path, 'write_text', side_effect=IOError("Disk full")):
                fetch_keyword_serp_html(self.keyword.id)
        
        # Check no .tmp files left
        for path in Path(self.temp_dir).rglob('*.tmp'):
            self.fail(f"Found temp file: {path}")
        
        # Keyword should show failure
        self.keyword.refresh_from_db()
        self.assertEqual(self.keyword.failed_api_hit_count, 1)
    
    @override_settings(SCRAPE_DO_STORAGE_ROOT='/tmp/test_storage')
    @patch('keywords.tasks.ScrapeDoService')
    def test_same_day_idempotency(self, mock_scraper_class):
        """Test that same-day fetches are idempotent"""
        mock_scraper = Mock()
        mock_scraper_class.return_value = mock_scraper
        mock_scraper.scrape_google_search.return_value = {
            'status_code': 200,
            'html': '<html>First fetch</html>',
            'success': True
        }
        
        with override_settings(SCRAPE_DO_STORAGE_ROOT=self.temp_dir):
            # First fetch
            fetch_keyword_serp_html(self.keyword.id)
            
            # Refresh keyword to clear cache
            self.keyword.refresh_from_db()
            
            # Clear scraped_at to allow second call to proceed
            # (simulating manual re-trigger or different scenario)
            self.keyword.scraped_at = None
            self.keyword.save()
            
            # Second fetch same day - should skip scraping but increment counter
            mock_scraper.scrape_google_search.return_value = {
                'status_code': 200,
                'html': '<html>Second fetch</html>',
                'success': True
            }
            fetch_keyword_serp_html(self.keyword.id)
        
        # File should contain first content (not overwritten)
        file_path = Path(self.temp_dir) / f"{self.project.id}/{self.keyword.id}/{datetime.now().strftime('%Y-%m-%d')}.html"
        content = file_path.read_text()
        self.assertEqual(content, '<html>First fetch</html>')
        
        # Success count should be 2
        self.keyword.refresh_from_db()
        self.assertEqual(self.keyword.success_api_hit_count, 2)
    
    def test_minimal_error_messages(self):
        """Test that only minimal error messages are stored"""
        with patch('keywords.tasks.ScrapeDoService') as mock_scraper_class:
            mock_scraper = Mock()
            mock_scraper_class.return_value = mock_scraper
            
            # Simulate exception with long message
            long_error = "A" * 500 + " with stack trace and sensitive data"
            mock_scraper.scrape_google_search.side_effect = Exception(long_error)
            
            fetch_keyword_serp_html(self.keyword.id)
        
        self.keyword.refresh_from_db()
        
        # Error message should be truncated
        self.assertIsNotNone(self.keyword.last_error_message)
        self.assertLessEqual(len(self.keyword.last_error_message), 100)
        self.assertNotIn("stack trace", self.keyword.last_error_message)


class CeleryIntegrationTest(TestCase):
    """Integration tests for Celery configuration"""
    
    def test_queue_configuration(self):
        """Test that queues are properly configured"""
        from limeclicks.celery import app
        
        queues = {q.name for q in app.conf.task_queues}
        self.assertIn('serp_high', queues)
        self.assertIn('serp_default', queues)
        self.assertIn('celery', queues)
    
    def test_task_routing(self):
        """Test that task routing is configured"""
        from limeclicks.celery import app
        
        routes = app.conf.task_routes
        self.assertIn('keywords.tasks.fetch_keyword_serp_html', routes)