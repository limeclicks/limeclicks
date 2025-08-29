"""
Comprehensive tests for ranking extraction from SERP HTML
"""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile

from django.test import TestCase, override_settings
from django.utils import timezone

from keywords.models import Keyword, Rank
from keywords.ranking_extractor import RankingExtractor, process_stored_html
from project.models import Project
from accounts.models import User


class RankingExtractorTestCase(TestCase):
    """Test cases for ranking extraction"""
    
    def setUp(self):
        """Set up test data"""
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
        
        # Sample parsed results
        self.sample_parsed_results = {
            'organic_results': [
                {'url': 'https://competitor1.com/page', 'title': 'Competitor 1'},
                {'url': 'https://example.com/test', 'title': 'Our Site'},
                {'url': 'https://competitor2.com/page', 'title': 'Competitor 2'},
            ],
            'sponsored_results': [
                {'url': 'https://ads.example.com/promo', 'title': 'Ad Example'},
            ],
            'featured_snippet': {'content': 'Some snippet'},
            'people_also_ask': [{'question': 'What is this?'}],
            'local_pack': [{'name': 'Local Business'}],
            'video_results': [{'title': 'Video'}],
        }
        
        # Sample HTML content
        self.sample_html = '<html><body>Test SERP HTML</body></html>'
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_successful_ranking_extraction(self, mock_r2_service, mock_parser_class):
        """Test successful ranking extraction and Rank creation"""
        # Setup mocks
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        mock_parser.parse.return_value = self.sample_parsed_results
        
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.return_value = {'success': True}
        
        # Execute
        extractor = RankingExtractor()
        result = extractor.process_serp_html(
            self.keyword,
            self.sample_html,
            datetime.now()
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertTrue(result['success'])
        self.assertEqual(result['rank'], 2)  # example.com is at position 2
        self.assertTrue(result['is_organic'])
        
        # Check Rank was created
        rank = Rank.objects.get(keyword=self.keyword)
        self.assertEqual(rank.rank, 2)
        self.assertTrue(rank.is_organic)
        self.assertTrue(rank.has_video_result)
        self.assertTrue(rank.has_map_result)
        
        # Check keyword was updated
        self.keyword.refresh_from_db()
        self.assertEqual(self.keyword.rank, 2)
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_domain_not_found_in_results(self, mock_r2_service, mock_parser_class):
        """Test when domain is not found in top 100 results"""
        # Setup mocks - results without our domain
        results_without_domain = {
            'organic_results': [
                {'url': 'https://competitor1.com/page', 'title': 'Competitor 1'},
                {'url': 'https://competitor2.com/page', 'title': 'Competitor 2'},
            ],
            'sponsored_results': []
        }
        
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        mock_parser.parse.return_value = results_without_domain
        
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.return_value = {'success': True}
        
        # Execute
        extractor = RankingExtractor()
        result = extractor.process_serp_html(
            self.keyword,
            self.sample_html,
            datetime.now()
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result['rank'], 0)  # Not found = rank 0
        self.assertTrue(result['is_organic'])
        
        # Check Rank was created with rank 0
        rank = Rank.objects.get(keyword=self.keyword)
        self.assertEqual(rank.rank, 0)
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_sponsored_result_detection(self, mock_r2_service, mock_parser_class):
        """Test detection of sponsored (non-organic) results"""
        # Setup mocks - domain only in sponsored results
        results_sponsored = {
            'organic_results': [
                {'url': 'https://competitor1.com/page', 'title': 'Competitor 1'},
            ],
            'sponsored_results': [
                {'url': 'https://www.example.com/ad', 'title': 'Our Ad'},
                {'url': 'https://competitor.com/ad', 'title': 'Competitor Ad'},
            ]
        }
        
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        mock_parser.parse.return_value = results_sponsored
        
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.return_value = {'success': True}
        
        # Execute
        extractor = RankingExtractor()
        result = extractor.process_serp_html(
            self.keyword,
            self.sample_html,
            datetime.now()
        )
        
        # Assertions
        self.assertEqual(result['rank'], 1)  # First sponsored position
        self.assertFalse(result['is_organic'])  # Sponsored, not organic
        
        # Check Rank was created
        rank = Rank.objects.get(keyword=self.keyword)
        self.assertEqual(rank.rank, 1)
        self.assertFalse(rank.is_organic)
    
    def test_domain_normalization(self):
        """Test domain normalization and matching"""
        extractor = RankingExtractor()
        
        # Test normalization
        self.assertEqual(
            extractor._normalize_domain('https://www.example.com/'),
            'example.com'
        )
        self.assertEqual(
            extractor._normalize_domain('HTTP://EXAMPLE.COM'),
            'example.com'
        )
        self.assertEqual(
            extractor._normalize_domain('www.example.com'),
            'example.com'
        )
        
        # Test domain matching
        self.assertTrue(extractor._domains_match('example.com', 'example.com'))
        self.assertTrue(extractor._domains_match('example.com', 'www.example.com'))
        self.assertTrue(extractor._domains_match('example.com', 'sub.example.com'))
        self.assertFalse(extractor._domains_match('example.com', 'notexample.com'))
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_serp_feature_detection(self, mock_r2_service, mock_parser_class):
        """Test SERP feature detection"""
        # Setup mocks with various SERP features
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        mock_parser.parse.return_value = self.sample_parsed_results
        
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.return_value = {'success': True}
        
        # Execute
        extractor = RankingExtractor()
        result = extractor.process_serp_html(
            self.keyword,
            self.sample_html,
            datetime.now()
        )
        
        # Check SERP features were detected
        rank = Rank.objects.get(keyword=self.keyword)
        self.assertTrue(rank.has_map_result)  # Has local_pack
        self.assertTrue(rank.has_video_result)  # Has video_results
        self.assertFalse(rank.has_image_result)  # No image results
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_r2_storage_path_format(self, mock_r2_service, mock_parser_class):
        """Test R2 storage path format"""
        # Setup mocks
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        mock_parser.parse.return_value = self.sample_parsed_results
        
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.return_value = {'success': True}
        
        # Execute
        extractor = RankingExtractor()
        scraped_date = datetime(2024, 1, 15)
        result = extractor.process_serp_html(
            self.keyword,
            self.sample_html,
            scraped_date
        )
        
        # Check R2 upload was called with correct path
        clean_keyword = self.keyword.keyword.lower().replace(' ', '-')
        expected_path = f"{self.project.domain}/{clean_keyword}/2024-01-15.json"
        mock_r2.upload_json.assert_called_once()
        call_args = mock_r2.upload_json.call_args
        self.assertEqual(call_args[0][1], expected_path)
        
        # Check stored data includes metadata
        stored_data = call_args[0][0]
        self.assertEqual(stored_data['keyword'], 'test keyword')
        self.assertEqual(stored_data['project_id'], self.project.id)
        self.assertEqual(stored_data['project_domain'], 'example.com')
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    def test_parse_failure_handling(self, mock_parser_class):
        """Test handling of HTML parsing failures"""
        # Setup mock to fail
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        mock_parser.parse.side_effect = Exception("Parse error")
        
        # Execute
        extractor = RankingExtractor()
        result = extractor.process_serp_html(
            self.keyword,
            self.sample_html,
            datetime.now()
        )
        
        # Should return None on failure
        self.assertIsNone(result)
        
        # No Rank should be created
        self.assertEqual(Rank.objects.filter(keyword=self.keyword).count(), 0)
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_r2_upload_failure_handling(self, mock_r2_service, mock_parser_class):
        """Test handling of R2 upload failures"""
        # Setup mocks
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        mock_parser.parse.return_value = self.sample_parsed_results
        
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.return_value = {'success': False, 'error': 'Upload failed'}
        
        # Execute
        extractor = RankingExtractor()
        result = extractor.process_serp_html(
            self.keyword,
            self.sample_html,
            datetime.now()
        )
        
        # Should return None on R2 failure
        self.assertIsNone(result)
        
        # No Rank should be created
        self.assertEqual(Rank.objects.filter(keyword=self.keyword).count(), 0)
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_created_at_uses_scraped_date(self, mock_r2_service, mock_parser_class):
        """Test that Rank created_at uses the scraping date"""
        # Setup mocks
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        mock_parser.parse.return_value = self.sample_parsed_results
        
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.return_value = {'success': True}
        
        # Execute with specific date
        extractor = RankingExtractor()
        scraped_date = timezone.now() - timedelta(days=3)
        result = extractor.process_serp_html(
            self.keyword,
            self.sample_html,
            scraped_date
        )
        
        # Check Rank created_at matches scraped_date
        rank = Rank.objects.get(keyword=self.keyword)
        self.assertEqual(rank.created_at, scraped_date)
    
    @override_settings(SCRAPE_DO_STORAGE_ROOT='/tmp/test_storage')
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_process_stored_html_function(self, mock_r2_service, mock_parser_class):
        """Test the convenience function for processing stored HTML"""
        # Create temp HTML file
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create HTML file
            html_path = Path(temp_dir) / f"{self.project.id}/{self.keyword.id}"
            html_path.mkdir(parents=True, exist_ok=True)
            html_file = html_path / "2024-01-15.html"
            html_file.write_text(self.sample_html)
            
            # Setup mocks
            mock_parser = Mock()
            mock_parser_class.return_value = mock_parser
            mock_parser.parse.return_value = self.sample_parsed_results
            
            mock_r2 = Mock()
            mock_r2_service.return_value = mock_r2
            mock_r2.upload_json.return_value = {'success': True}
            
            # Execute with override settings
            with override_settings(SCRAPE_DO_STORAGE_ROOT=temp_dir):
                relative_path = f"{self.project.id}/{self.keyword.id}/2024-01-15.html"
                result = process_stored_html(self.keyword.id, relative_path)
            
            # Assertions
            self.assertIsNotNone(result)
            self.assertTrue(result['success'])
            self.assertEqual(result['rank'], 2)
            
            # Check date was parsed from filename
            rank = Rank.objects.get(keyword=self.keyword)
            self.assertEqual(rank.created_at.date(), datetime(2024, 1, 15).date())
    
    def test_keyword_update_rank_method(self):
        """Test the Keyword.update_rank method"""
        # Initial state
        self.assertEqual(self.keyword.rank, 0)
        self.assertEqual(self.keyword.rank_status, 'no_change')
        
        # First update (new rank)
        self.keyword.update_rank(5)
        self.assertEqual(self.keyword.rank, 5)
        self.assertEqual(self.keyword.rank_status, 'new')
        self.assertEqual(self.keyword.initial_rank, 5)
        self.assertEqual(self.keyword.highest_rank, 5)
        
        # Improvement
        self.keyword.update_rank(3)
        self.assertEqual(self.keyword.rank, 3)
        self.assertEqual(self.keyword.rank_status, 'up')
        self.assertEqual(self.keyword.rank_diff_from_last_time, 2)
        self.assertEqual(self.keyword.highest_rank, 3)
        
        # Decline
        self.keyword.update_rank(7)
        self.assertEqual(self.keyword.rank, 7)
        self.assertEqual(self.keyword.rank_status, 'down')
        self.assertEqual(self.keyword.rank_diff_from_last_time, -4)
        self.assertEqual(self.keyword.highest_rank, 3)  # Unchanged
        
        # No change
        self.keyword.update_rank(7)
        self.assertEqual(self.keyword.rank_status, 'no_change')
        self.assertEqual(self.keyword.rank_diff_from_last_time, 0)


class IntegrationTestCase(TestCase):
    """Integration tests for the full flow"""
    
    def setUp(self):
        """Set up test data"""
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
        
        self.keyword = Keyword.objects.create(
            project=self.project,
            keyword='python tutorial',
            country='US',
            country_code='US'
        )
    
    @override_settings(
        SCRAPE_DO_STORAGE_ROOT='/tmp/test_storage',
        FETCH_MIN_INTERVAL_HOURS=24
    )
    @patch('keywords.tasks.ScrapeDoService')
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_full_fetch_and_rank_flow(self, mock_r2_service, mock_parser_class, mock_scraper_class):
        """Test the complete flow from fetch to ranking"""
        from keywords.tasks import fetch_keyword_serp_html
        
        # Setup scraper mock
        mock_scraper = Mock()
        mock_scraper_class.return_value = mock_scraper
        mock_scraper.scrape_google_search.return_value = {
            'status_code': 200,
            'html': '<html>SERP content</html>',
            'success': True
        }
        
        # Setup parser mock
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        mock_parser.parse.return_value = {
            'organic_results': [
                {'url': 'https://python.org', 'title': 'Python'},
                {'url': 'https://example.com/learn', 'title': 'Learn Python'},
            ]
        }
        
        # Setup R2 mock
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.return_value = {'success': True}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with override_settings(SCRAPE_DO_STORAGE_ROOT=temp_dir):
                # Execute the fetch task
                fetch_keyword_serp_html(self.keyword.id)
        
        # Verify complete flow
        self.keyword.refresh_from_db()
        
        # Check HTML was fetched
        self.assertIsNotNone(self.keyword.scraped_at)
        self.assertEqual(self.keyword.success_api_hit_count, 1)
        
        # Check Rank was created
        rank = Rank.objects.get(keyword=self.keyword)
        self.assertEqual(rank.rank, 2)  # example.com at position 2
        self.assertTrue(rank.is_organic)
        
        # Check keyword rank was updated
        self.assertEqual(self.keyword.rank, 2)
        self.assertEqual(self.keyword.rank_status, 'new')
        self.assertEqual(self.keyword.initial_rank, 2)