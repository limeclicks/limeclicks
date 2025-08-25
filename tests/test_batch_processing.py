"""
Tests for batch processing and duplicate prevention
"""

from datetime import timedelta
from unittest.mock import patch, Mock
from django.test import TestCase
from django.utils import timezone

from keywords.models import Keyword
from keywords.tasks import enqueue_keyword_scrapes_batch
from project.models import Project
from accounts.models import User


class BatchProcessingTestCase(TestCase):
    """Test cases for batch keyword processing"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='batch_user',
            email='batch@test.com',
            password='testpass123'
        )
        
        self.project = Project.objects.create(
            user=self.user,
            domain='batchtest.com',
            title='Batch Test Project',
            active=True
        )
    
    @patch('keywords.tasks.fetch_keyword_serp_html.apply_async')
    def test_batch_size_limit(self, mock_apply):
        """Test that only 500 keywords are processed per batch"""
        # Create 600 eligible keywords
        old_time = timezone.now() - timedelta(hours=25)
        keywords = []
        for i in range(600):
            kw = Keyword.objects.create(
                project=self.project,
                keyword=f'test keyword {i}',
                country='US',
                scraped_at=old_time,
                processing=False
            )
            keywords.append(kw)
        
        # Run batch enqueue
        result = enqueue_keyword_scrapes_batch()
        
        # Should only process 500
        self.assertEqual(result['total'], 500)
        self.assertEqual(mock_apply.call_count, 500)
        
        # Check that 500 keywords have processing=True
        processing_count = Keyword.objects.filter(processing=True).count()
        self.assertEqual(processing_count, 500)
        
        # Check that 100 keywords still have processing=False
        not_processing = Keyword.objects.filter(processing=False).count()
        self.assertEqual(not_processing, 100)
    
    @patch('keywords.tasks.fetch_keyword_serp_html.apply_async')
    def test_duplicate_prevention(self, mock_apply):
        """Test that keywords already processing are not re-queued"""
        # Create keywords with mixed processing states
        old_time = timezone.now() - timedelta(hours=25)
        
        # Already processing (should be skipped)
        Keyword.objects.create(
            project=self.project,
            keyword='already processing',
            country='US',
            scraped_at=old_time,
            processing=True
        )
        
        # Not processing (should be queued)
        eligible = Keyword.objects.create(
            project=self.project,
            keyword='not processing',
            country='US',
            scraped_at=old_time,
            processing=False
        )
        
        # Run batch enqueue
        result = enqueue_keyword_scrapes_batch()
        
        # Should only queue the one not processing
        self.assertEqual(result['total'], 1)
        self.assertEqual(mock_apply.call_count, 1)
        
        # Check it was the right keyword
        call_args = mock_apply.call_args[1]
        self.assertEqual(call_args['args'][0], eligible.id)
    
    @patch('keywords.tasks.fetch_keyword_serp_html.apply_async')
    def test_serp_high_only_for_never_scraped(self, mock_apply):
        """Test that serp_high is only used for keywords never scraped"""
        # Create keywords with different scraped_at values
        
        # Never scraped - should go to serp_high
        never_scraped = Keyword.objects.create(
            project=self.project,
            keyword='never scraped',
            country='US',
            scraped_at=None,
            processing=False
        )
        
        # Previously scraped - should go to serp_default
        old_time = timezone.now() - timedelta(hours=25)
        previously_scraped = Keyword.objects.create(
            project=self.project,
            keyword='previously scraped',
            country='US',
            scraped_at=old_time,
            processing=False
        )
        
        with patch('keywords.tasks.fetch_keyword_serp_html.apply_async') as mock_apply_fixed:
            result = enqueue_keyword_scrapes_batch()
            
            # Check queue assignments
            calls = mock_apply_fixed.call_args_list
            
            for call in calls:
                keyword_id = call[1]['args'][0]
                queue = call[1]['queue']
                priority = call[1]['priority']
                
                if keyword_id == never_scraped.id:
                    self.assertEqual(queue, 'serp_high')
                    self.assertEqual(priority, 10)
                elif keyword_id == previously_scraped.id:
                    self.assertEqual(queue, 'serp_default')
                    self.assertEqual(priority, 5)
        
        # Check result counts
        self.assertEqual(result['high_priority'], 1)
        self.assertEqual(result['default_priority'], 1)
    
    @patch('keywords.tasks.fetch_keyword_serp_html.apply_async')
    def test_no_eligible_keywords(self, mock_apply):
        """Test handling when no keywords are eligible"""
        # Create keywords that are not eligible
        
        # Recently scraped
        Keyword.objects.create(
            project=self.project,
            keyword='recent',
            country='US',
            scraped_at=timezone.now() - timedelta(hours=12),
            processing=False
        )
        
        # Archived
        Keyword.objects.create(
            project=self.project,
            keyword='archived',
            country='US',
            scraped_at=timezone.now() - timedelta(hours=30),
            processing=False,
            archive=True
        )
        
        # Run batch enqueue
        result = enqueue_keyword_scrapes_batch()
        
        # Should process nothing
        self.assertEqual(result['total'], 0)
        self.assertEqual(mock_apply.call_count, 0)
    
    @patch('keywords.tasks.fetch_keyword_serp_html.apply_async')
    def test_inactive_project_keywords_excluded(self, mock_apply):
        """Test that keywords from inactive projects are not queued"""
        # Create inactive project
        inactive_project = Project.objects.create(
            user=self.user,
            domain='inactive.com',
            title='Inactive Project',
            active=False
        )
        
        # Create keyword for inactive project
        old_time = timezone.now() - timedelta(hours=25)
        Keyword.objects.create(
            project=inactive_project,
            keyword='inactive project keyword',
            country='US',
            scraped_at=old_time,
            processing=False
        )
        
        # Create keyword for active project
        active_kw = Keyword.objects.create(
            project=self.project,
            keyword='active project keyword',
            country='US',
            scraped_at=old_time,
            processing=False
        )
        
        # Run batch enqueue
        result = enqueue_keyword_scrapes_batch()
        
        # Should only queue the active project keyword
        self.assertEqual(result['total'], 1)
        self.assertEqual(mock_apply.call_count, 1)
        
        # Verify it's the right keyword
        call_args = mock_apply.call_args[1]
        self.assertEqual(call_args['args'][0], active_kw.id)
    
    def test_processing_flag_reset_on_success(self):
        """Test that processing flag is reset after successful fetch"""
        from keywords.tasks import _handle_successful_fetch
        
        keyword = Keyword.objects.create(
            project=self.project,
            keyword='test',
            country='US',
            processing=True
        )
        
        # Simulate successful fetch
        _handle_successful_fetch(keyword, '<html>Test HTML</html>')
        
        # Check processing flag was reset
        keyword.refresh_from_db()
        self.assertFalse(keyword.processing)
    
    def test_processing_flag_reset_on_failure(self):
        """Test that processing flag is reset after failed fetch"""
        from keywords.tasks import _handle_failed_fetch
        
        keyword = Keyword.objects.create(
            project=self.project,
            keyword='test',
            country='US',
            processing=True
        )
        
        # Simulate failed fetch
        _handle_failed_fetch(keyword, 'Test error')
        
        # Check processing flag was reset
        keyword.refresh_from_db()
        self.assertFalse(keyword.processing)
    
    @patch('keywords.tasks.fetch_keyword_serp_html.apply_async')
    def test_batch_result_structure(self, mock_apply):
        """Test the structure of batch enqueue result"""
        # Create a mix of keywords
        never_scraped = Keyword.objects.create(
            project=self.project,
            keyword='never',
            country='US',
            scraped_at=None,
            processing=False
        )
        
        old_time = timezone.now() - timedelta(hours=25)
        previously_scraped = Keyword.objects.create(
            project=self.project,
            keyword='before',
            country='US',
            scraped_at=old_time,
            processing=False
        )
        
        # Run batch enqueue
        result = enqueue_keyword_scrapes_batch()
        
        # Check result structure
        self.assertIn('total', result)
        self.assertIn('high_priority', result)
        self.assertIn('default_priority', result)
        self.assertIn('batch_size', result)
        
        self.assertEqual(result['batch_size'], 500)
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['high_priority'], 1)
        self.assertEqual(result['default_priority'], 1)