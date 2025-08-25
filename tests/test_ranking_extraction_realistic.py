"""
Comprehensive tests for ranking extraction with realistic SERP data
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile

from django.test import TestCase, override_settings
from django.utils import timezone

from keywords.models import Keyword, Rank
from keywords.ranking_extractor import RankingExtractor, process_stored_html
from project.models import Project
from accounts.models import User
from .test_data_helpers import (
    create_realistic_serp_results,
    create_empty_serp_results,
    create_sponsored_only_results,
    create_serp_with_all_features,
    create_test_scenarios
)


class RealisticRankingExtractionTestCase(TestCase):
    """Test cases with realistic SERP data"""
    
    def setUp(self):
        """Set up test data"""
        # Create test user and project with realistic domain
        self.user = User.objects.create_user(
            username='seo_manager',
            email='seo@pythontutorial.net',
            password='testpass123'
        )
        
        self.project = Project.objects.create(
            user=self.user,
            domain='pythontutorial.net',
            title='Python Tutorial Website',
            active=True
        )
        
        # Create realistic keywords
        self.keywords = [
            Keyword.objects.create(
                project=self.project,
                keyword='python basics',
                country='US',
                country_code='US',
                location='New York, NY, United States'
            ),
            Keyword.objects.create(
                project=self.project,
                keyword='python web scraping',
                country='US',
                country_code='US'
            ),
            Keyword.objects.create(
                project=self.project,
                keyword='python machine learning',
                country='UK',
                country_code='GB',
                location='London, England, United Kingdom'
            ),
        ]
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_realistic_rank_1_extraction(self, mock_r2_service, mock_parser_class):
        """Test extraction when domain ranks #1"""
        keyword = self.keywords[0]  # python basics
        
        # Setup mocks with realistic data
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        mock_parser.parse.return_value = create_realistic_serp_results(
            domain=self.project.domain,
            keyword=keyword.keyword,
            rank_position=1,
            include_features=True,
            num_results=100
        )
        
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.return_value = {'success': True}
        
        # Execute
        extractor = RankingExtractor()
        result = extractor.process_serp_html(
            keyword,
            '<html>Actual SERP HTML</html>',
            datetime.now()
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertTrue(result['success'])
        self.assertEqual(result['rank'], 1)
        self.assertTrue(result['is_organic'])
        
        # Check Rank was created correctly
        rank = Rank.objects.get(keyword=keyword)
        self.assertEqual(rank.rank, 1)
        self.assertTrue(rank.is_organic)
        
        # Check SERP features were detected
        self.assertTrue(rank.has_video_result)  # Videos present in realistic data
        self.assertTrue(rank.has_map_result)    # Local pack present
        self.assertTrue(rank.has_image_result)  # Images present
        
        # Check R2 upload data structure
        call_args = mock_r2.upload_json.call_args[0][0]
        self.assertEqual(call_args['keyword'], 'python basics')
        self.assertEqual(call_args['project_domain'], 'pythontutorial.net')
        self.assertEqual(call_args['location'], 'New York, NY, United States')
        self.assertIn('organic_results', call_args['results'])
        self.assertIn('sponsored_results', call_args['results'])
        self.assertIn('people_also_ask', call_args['results'])
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_realistic_rank_50_extraction(self, mock_r2_service, mock_parser_class):
        """Test extraction when domain ranks #50 (middle of results)"""
        keyword = self.keywords[1]  # python web scraping
        
        # Setup mocks
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        mock_parser.parse.return_value = create_realistic_serp_results(
            domain=self.project.domain,
            keyword=keyword.keyword,
            rank_position=50,
            num_results=100
        )
        
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.return_value = {'success': True}
        
        # Execute
        extractor = RankingExtractor()
        result = extractor.process_serp_html(
            keyword,
            '<html>SERP HTML</html>',
            datetime.now()
        )
        
        # Assertions
        self.assertEqual(result['rank'], 50)
        self.assertTrue(result['is_organic'])
        
        # Check keyword was updated
        keyword.refresh_from_db()
        self.assertEqual(keyword.rank, 50)
        self.assertEqual(keyword.rank_status, 'new')  # First rank
        self.assertEqual(keyword.initial_rank, 50)
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_realistic_not_ranked(self, mock_r2_service, mock_parser_class):
        """Test when domain doesn't appear in top 100"""
        keyword = self.keywords[2]  # python machine learning
        
        # Setup mocks - domain not in results
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        mock_parser.parse.return_value = create_realistic_serp_results(
            domain='competitor.com',  # Different domain
            keyword=keyword.keyword,
            rank_position=None,
            num_results=100
        )
        
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.return_value = {'success': True}
        
        # Execute
        extractor = RankingExtractor()
        result = extractor.process_serp_html(
            keyword,
            '<html>SERP HTML</html>',
            datetime.now()
        )
        
        # Assertions
        self.assertEqual(result['rank'], 0)  # Not found = 0
        self.assertTrue(result['is_organic'])
        
        # Check Rank record
        rank = Rank.objects.get(keyword=keyword)
        self.assertEqual(rank.rank, 0)
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_realistic_sponsored_only(self, mock_r2_service, mock_parser_class):
        """Test when domain only appears in sponsored results"""
        keyword = self.keywords[0]
        
        # Setup mocks
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        mock_parser.parse.return_value = create_sponsored_only_results(
            domain=self.project.domain,
            keyword='buy python course'
        )
        
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.return_value = {'success': True}
        
        # Execute
        extractor = RankingExtractor()
        result = extractor.process_serp_html(
            keyword,
            '<html>SERP HTML</html>',
            datetime.now()
        )
        
        # Assertions
        self.assertEqual(result['rank'], 1)  # First sponsored position
        self.assertFalse(result['is_organic'])  # It's a sponsored result
        
        # Check Rank record
        rank = Rank.objects.get(keyword=keyword)
        self.assertEqual(rank.rank, 1)
        self.assertFalse(rank.is_organic)
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_empty_serp_results(self, mock_r2_service, mock_parser_class):
        """Test handling of empty SERP (no results found)"""
        keyword = self.keywords[0]
        
        # Setup mocks with empty results
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        mock_parser.parse.return_value = create_empty_serp_results(
            keyword='xyzabc123nonexistent'
        )
        
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.return_value = {'success': True}
        
        # Execute
        extractor = RankingExtractor()
        result = extractor.process_serp_html(
            keyword,
            '<html>No results</html>',
            datetime.now()
        )
        
        # Assertions
        self.assertEqual(result['rank'], 0)
        self.assertTrue(result['is_organic'])
        
        # Check no SERP features detected
        rank = Rank.objects.get(keyword=keyword)
        self.assertFalse(rank.has_map_result)
        self.assertFalse(rank.has_video_result)
        self.assertFalse(rank.has_image_result)
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_all_serp_features_detection(self, mock_r2_service, mock_parser_class):
        """Test detection of all SERP features"""
        keyword = self.keywords[0]
        
        # Setup mocks with all features
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        mock_parser.parse.return_value = create_serp_with_all_features(
            domain=self.project.domain,
            rank_position=3
        )
        
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.return_value = {'success': True}
        
        # Execute
        extractor = RankingExtractor()
        result = extractor.process_serp_html(
            keyword,
            '<html>Rich SERP</html>',
            datetime.now()
        )
        
        # Assertions
        self.assertEqual(result['rank'], 3)
        self.assertTrue(result['is_organic'])
        
        # Check all features detected
        rank = Rank.objects.get(keyword=keyword)
        self.assertTrue(rank.has_map_result)   # Local pack
        self.assertTrue(rank.has_video_result) # Videos
        self.assertTrue(rank.has_image_result) # Images
        
        # Check R2 data includes all features
        call_args = mock_r2.upload_json.call_args[0][0]
        results = call_args['results']
        self.assertIn('featured_snippet', results)
        self.assertIn('knowledge_panel', results)
        self.assertIn('people_also_ask', results)
        self.assertIn('videos', results)
        self.assertIn('local_pack', results)
        self.assertIn('top_stories', results)
    
    def test_domain_variations_matching(self):
        """Test domain matching with various formats"""
        extractor = RankingExtractor()
        
        test_cases = [
            # (project_domain, result_domain, should_match)
            ('example.com', 'example.com', True),
            ('example.com', 'www.example.com', True),
            ('example.com', 'blog.example.com', True),
            ('example.com', 'shop.example.com', True),
            ('example.com', 'example.org', False),
            ('example.com', 'notexample.com', False),
            ('example.com', 'example.co.uk', False),
            ('blog.example.com', 'example.com', True),  # Subdomain can match parent
            ('example.com', 'my-example.com', False),
            ('example.com', 'examplecom.net', False),
        ]
        
        for project_domain, result_domain, should_match in test_cases:
            with self.subTest(project=project_domain, result=result_domain):
                match = extractor._domains_match(project_domain, result_domain)
                self.assertEqual(
                    match, 
                    should_match,
                    f"Domain matching failed for {project_domain} vs {result_domain}"
                )
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_rank_improvement_tracking(self, mock_r2_service, mock_parser_class):
        """Test tracking rank improvements over time"""
        # Create a fresh keyword for this test
        keyword = Keyword.objects.create(
            project=self.project,
            keyword='python rank tracking test',
            country='US',
            country_code='US'
        )
        
        # Setup mocks
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.return_value = {'success': True}
        
        # First ranking - position 50
        mock_parser.parse.return_value = create_realistic_serp_results(
            domain=keyword.project.domain,  # Use the keyword's project domain
            keyword=keyword.keyword,
            rank_position=50,
            num_results=100
        )
        
        extractor = RankingExtractor()
        result1 = extractor.process_serp_html(
            keyword,
            '<html>First SERP</html>',
            timezone.now() - timedelta(days=7)
        )
        
        # Check that the result is not None
        self.assertIsNotNone(result1, "process_serp_html returned None")
        self.assertEqual(result1.get('rank'), 50, f"Expected rank 50, got {result1}")
        
        keyword.refresh_from_db()
        self.assertEqual(keyword.rank, 50)
        self.assertEqual(keyword.rank_status, 'new')
        self.assertEqual(keyword.initial_rank, 50)
        self.assertEqual(keyword.highest_rank, 50)
        
        # Second ranking - improved to position 25
        mock_parser.parse.return_value = create_realistic_serp_results(
            domain=keyword.project.domain,
            keyword=keyword.keyword,
            rank_position=25,
            num_results=100
        )
        
        result2 = extractor.process_serp_html(
            keyword,
            '<html>Second SERP</html>',
            timezone.now() - timedelta(days=3)
        )
        
        keyword.refresh_from_db()
        self.assertEqual(keyword.rank, 25)
        self.assertEqual(keyword.rank_status, 'up')  # Improved
        self.assertEqual(keyword.rank_diff_from_last_time, 25)  # 50 - 25
        self.assertEqual(keyword.highest_rank, 25)  # New best
        
        # Third ranking - dropped to position 30
        mock_parser.parse.return_value = create_realistic_serp_results(
            domain=keyword.project.domain,
            keyword=keyword.keyword,
            rank_position=30,
            num_results=100
        )
        
        result3 = extractor.process_serp_html(
            keyword,
            '<html>Third SERP</html>',
            timezone.now()
        )
        
        keyword.refresh_from_db()
        self.assertEqual(keyword.rank, 30)
        self.assertEqual(keyword.rank_status, 'down')  # Declined
        self.assertEqual(keyword.rank_diff_from_last_time, -5)  # 25 - 30
        self.assertEqual(keyword.highest_rank, 25)  # Still 25 (best ever)
        
        # Check we have 3 rank records
        ranks = Rank.objects.filter(keyword=keyword).order_by('created_at')
        self.assertEqual(ranks.count(), 3)
        self.assertEqual(list(ranks.values_list('rank', flat=True)), [50, 25, 30])


class IntegrationWithRealisticDataTestCase(TestCase):
    """Integration tests with realistic data flow"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='integration_user',
            email='test@integration.com',
            password='testpass123'
        )
        
        # Create multiple projects with different domains
        self.projects = [
            Project.objects.create(
                user=self.user,
                domain='techblog.io',
                title='Tech Blog',
                active=True
            ),
            Project.objects.create(
                user=self.user,
                domain='ecommerce-store.com',
                title='E-commerce Store',
                active=True
            ),
        ]
    
    @override_settings(
        SCRAPE_DO_STORAGE_ROOT='/tmp/test_storage',
        FETCH_MIN_INTERVAL_HOURS=24
    )
    @patch('keywords.tasks.ScrapeDoService')
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_multiple_keywords_batch_processing(self, mock_r2_service, mock_parser_class, mock_scraper_class):
        """Test processing multiple keywords with different rankings"""
        from keywords.tasks import fetch_keyword_serp_html
        
        # Create keywords for first project
        keywords_data = [
            ('javascript tutorial', 5),    # Ranks #5
            ('react hooks guide', 15),     # Ranks #15
            ('nodejs best practices', 0),  # Not ranked
            ('vue.js components', 1),      # Ranks #1
        ]
        
        keywords = []
        for kw_text, rank_pos in keywords_data:
            keyword = Keyword.objects.create(
                project=self.projects[0],
                keyword=kw_text,
                country='US',
                country_code='US'
            )
            keywords.append((keyword, rank_pos))
        
        # Setup mocks
        mock_scraper = Mock()
        mock_scraper_class.return_value = mock_scraper
        mock_scraper.scrape_google_search.return_value = {
            'status_code': 200,
            'html': '<html>SERP HTML</html>',
            'success': True
        }
        
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.return_value = {'success': True}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with override_settings(SCRAPE_DO_STORAGE_ROOT=temp_dir):
                # Process each keyword
                for keyword, expected_rank in keywords:
                    # Set parser to return appropriate ranking
                    if expected_rank > 0:
                        mock_parser.parse.return_value = create_realistic_serp_results(
                            domain=self.projects[0].domain,
                            keyword=keyword.keyword,
                            rank_position=expected_rank,
                            num_results=100
                        )
                    else:
                        mock_parser.parse.return_value = create_realistic_serp_results(
                            domain='competitor.com',
                            keyword=keyword.keyword,
                            rank_position=None,
                            num_results=100
                        )
                    
                    # Execute fetch
                    fetch_keyword_serp_html(keyword.id)
                    
                    # Verify results
                    keyword.refresh_from_db()
                    self.assertIsNotNone(keyword.scraped_at)
                    self.assertEqual(keyword.rank, expected_rank)
                    
                    # Check Rank was created
                    rank = Rank.objects.get(keyword=keyword)
                    self.assertEqual(rank.rank, expected_rank)
                    self.assertTrue(rank.is_organic)
        
        # Verify all keywords were processed
        for keyword, expected_rank in keywords:
            keyword.refresh_from_db()
            self.assertEqual(
                keyword.rank, 
                expected_rank,
                f"Keyword '{keyword.keyword}' should have rank {expected_rank}"
            )
    
    def test_comprehensive_test_scenarios(self):
        """Run through all predefined test scenarios"""
        scenarios = create_test_scenarios()
        
        for scenario in scenarios:
            with self.subTest(scenario=scenario['name']):
                # Create project for this scenario
                project = Project.objects.create(
                    user=self.user,
                    domain=scenario['domain'],
                    title=f"Test - {scenario['name']}",
                    active=True
                )
                
                # Create keyword
                keyword = Keyword.objects.create(
                    project=project,
                    keyword=scenario['keyword'],
                    country='US',
                    country_code='US'
                )
                
                # Validate the test data structure
                data = scenario['data']
                self.assertIn('organic_results', data)
                self.assertIn('sponsored_results', data)
                self.assertIn('total_results', data)
                
                # Check if domain appears in results
                domain_found = False
                domain_position = 0
                domain_is_organic = True
                
                # Check organic results
                for result in data['organic_results']:
                    if scenario['domain'] in result.get('url', ''):
                        domain_found = True
                        domain_position = result.get('position', 0)
                        domain_is_organic = True
                        break
                
                # Check sponsored if not found in organic
                if not domain_found:
                    for result in data['sponsored_results']:
                        if scenario['domain'] in result.get('url', ''):
                            domain_found = True
                            domain_position = result.get('position', 0)
                            domain_is_organic = False
                            break
                
                # Log scenario results
                print(f"\nScenario: {scenario['name']}")
                print(f"  Domain: {scenario['domain']}")
                print(f"  Keyword: {scenario['keyword']}")
                print(f"  Found: {domain_found}")
                print(f"  Position: {domain_position if domain_found else 'Not ranked'}")
                print(f"  Type: {'Organic' if domain_is_organic else 'Sponsored'}")
                print(f"  Total results: {len(data['organic_results'])} organic, {len(data['sponsored_results'])} sponsored")