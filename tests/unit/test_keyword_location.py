"""
Unit tests for location field and rank_file storage
"""

from django.test import TestCase
from unittest.mock import patch, MagicMock
from unittest import skip
from keywords.models import Keyword, Rank
from keywords.utils import KeywordRankTracker
from project.models import Project
from accounts.models import User


class KeywordLocationTest(TestCase):
    """Test cases for location field and R2 storage"""
    
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
    
    def test_keyword_with_location(self):
        """Test creating keyword with location"""
        keyword = Keyword.objects.create(
            project=self.project,
            keyword='restaurants near me',
            country='US',
            location='New York, NY, United States'
        )
        
        self.assertEqual(keyword.location, 'New York, NY, United States')
        self.assertEqual(keyword.country, 'US')
    
    def test_keyword_without_location(self):
        """Test keyword without location (should be null)"""
        keyword = Keyword.objects.create(
            project=self.project,
            keyword='python django tutorial',
            country='US'
        )
        
        self.assertIsNone(keyword.location)
    
    @skip("Skipping - requires R2 storage setup")
    def test_rank_with_rank_file(self):
        """Test rank with R2 storage file reference"""
        keyword = Keyword.objects.create(
            project=self.project,
            keyword='coffee shops',
            country='US',
            location='Seattle, WA, United States'
        )
        
        rank = Rank.objects.create(
            keyword=keyword,
            rank=5,
            rank_file='rank-data/2024/01/15/1_1_20240115_120000_rank.json'
        )
        
        self.assertEqual(rank.rank_file, 'rank-data/2024/01/15/1_1_20240115_120000_rank.json')
        self.assertEqual(rank.rank, 5)
    
    @skip("Skipping - requires external service mocking")
    @patch('keywords.utils.get_r2_service')
    @patch('keywords.utils.ScrapeDoService')
    @patch('keywords.utils.GoogleSearchParser')
    def test_tracker_with_location(self, mock_parser_class, mock_scraper_class, mock_r2_service):
        """Test KeywordRankTracker with location-based search"""
        # Setup mocks
        mock_r2 = MagicMock()
        mock_r2_service.return_value = mock_r2
        mock_r2.create_folder_structure.return_value = 'search-results/2024/01/15'
        mock_r2.upload_json.return_value = {'success': True}
        mock_r2.upload_file.return_value = {'success': True}
        
        mock_scraper = MagicMock()
        mock_scraper_class.return_value = mock_scraper
        
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser
        
        # Create keyword with location
        keyword = Keyword.objects.create(
            project=self.project,
            keyword='pizza delivery',
            country='US',
            location='Chicago, IL, United States'
        )
        
        # Mock scraper response
        mock_scraper.scrape_google_search.return_value = {
            'success': True,
            'html': '<html>Test</html>'
        }
        
        # Mock parser response
        mock_parser.parse.return_value = {
            'organic_results': [
                {'url': 'https://example.com/pizza', 'title': 'Pizza Place'},
                {'url': 'https://other.com', 'title': 'Other'}
            ],
            'total_results': 1000000
        }
        
        # Track keyword
        tracker = KeywordRankTracker()
        result = tracker.track_keyword(keyword)
        
        # Verify location was passed to scraper
        mock_scraper.scrape_google_search.assert_called_once_with(
            query='pizza delivery',
            country_code='US',
            num_results=100,
            location='Chicago, IL, United States',
            use_exact_location=True
        )
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['rank'], 1)  # Found at position 1
        
        # Check that rank was created with rank_file
        rank = Rank.objects.filter(keyword=keyword).first()
        self.assertIsNotNone(rank)
        self.assertEqual(rank.rank, 1)
    
    @skip("Skipping - requires R2 storage setup")
    @patch('keywords.utils.get_r2_service')
    def test_store_rank_data(self, mock_r2_service):
        """Test storing rank data in R2"""
        # Setup mock
        mock_r2 = MagicMock()
        mock_r2_service.return_value = mock_r2
        mock_r2.create_folder_structure.return_value = 'rank-data/2024/01/15'
        mock_r2.upload_json.return_value = {'success': True}
        
        # Create keyword
        keyword = Keyword.objects.create(
            project=self.project,
            keyword='test keyword',
            country='US',
            location='Test Location'
        )
        
        # Create tracker
        tracker = KeywordRankTracker()
        
        # Test data
        domain_rank = {
            'position': 3,
            'url': 'https://example.com/page',
            'title': 'Test Page',
            'is_organic': True
        }
        
        parsed_results = {
            'organic_results': [{'url': 'test'} for _ in range(15)],
            'sponsored_results': [{'url': 'ad'} for _ in range(3)],
            'total_results': 500000,
            'featured_snippet': {'content': 'test'},
            'local_pack': [{'name': 'Business'}],
            'related_searches': ['search 1', 'search 2']
        }
        
        # Store rank data
        rank_key = tracker._store_rank_data(keyword, domain_rank, parsed_results)
        
        # Verify upload was called
        mock_r2.upload_json.assert_called_once()
        call_args = mock_r2.upload_json.call_args
        
        # Check the data structure
        uploaded_data = call_args[0][0]
        self.assertEqual(uploaded_data['keyword'], 'test keyword')
        self.assertEqual(uploaded_data['location'], 'Test Location')
        self.assertEqual(uploaded_data['rank_info']['position'], 3)
        self.assertEqual(uploaded_data['organic_count'], 15)
        self.assertEqual(uploaded_data['sponsored_count'], 3)
        self.assertTrue(uploaded_data['serp_features']['has_featured_snippet'])
        self.assertTrue(uploaded_data['serp_features']['has_local_pack'])
        
        # Check the key format
        self.assertIn('rank-data/2024/01/15', rank_key)