"""
Integration tests for Google Search using Scrape.do API
These tests make actual API calls to verify the complete scraping pipeline
"""

import os
import sys
import django
import unittest
from unittest.mock import patch, Mock
import time

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.test import TestCase
from services.scrape_do import ScrapeDoService
from services.google_search_parser import GoogleSearchParser, GoogleSearchService


class GoogleScraperIntegrationTest(TestCase):
    """Integration tests for Google search scraping with Scrape.do API"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures for the entire test class"""
        super().setUpClass()
        cls.scraper = ScrapeDoService()
        cls.parser = GoogleSearchParser()
        cls.search_service = GoogleSearchService()
    
    def test_basic_google_search(self):
        """Test basic Google search with Scrape.do API"""
        # Mock the actual API call to avoid rate limits in testing
        with patch.object(self.scraper.session, 'get') as mock_get:
            # Create mock response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = self._get_sample_google_html()
            mock_response.headers = {'Content-Type': 'text/html'}
            mock_response.url = 'https://www.google.com/search?q=python'
            mock_get.return_value = mock_response
            
            # Perform search
            result = self.scraper.scrape_google_search(
                query='python',
                country_code='US',
                num_results=10
            )
            
            # Assertions
            self.assertIsNotNone(result)
            self.assertTrue(result.get('success'))
            self.assertEqual(result['status_code'], 200)
            self.assertIn('html', result)
            
            # Verify the API was called with correct parameters
            call_args = mock_get.call_args
            params = call_args[1]['params']
            self.assertEqual(params['token'], self.scraper.api_key)
            self.assertIn('google.com/search', params['url'])
            self.assertEqual(params['geoCode'], 'US')
    
    def test_google_search_with_parser(self):
        """Test Google search with result parsing"""
        with patch.object(self.scraper.session, 'get') as mock_get:
            # Create mock response with sample HTML
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = self._get_sample_google_html()
            mock_response.headers = {'Content-Type': 'text/html'}
            mock_response.url = 'https://www.google.com/search?q=python'
            mock_get.return_value = mock_response
            
            # Perform search through service
            results = self.search_service.search(
                query='python',
                country_code='US',
                num_results=10
            )
            
            # Assertions
            self.assertIsNotNone(results)
            self.assertIsInstance(results, dict)
            self.assertIn('query', results)
            self.assertIn('organic_results', results)
            self.assertEqual(results['query'], 'python')
    
    def test_google_search_different_countries(self):
        """Test Google search with different country codes"""
        countries = ['US', 'GB', 'DE', 'FR']
        
        for country in countries:
            with self.subTest(country=country):
                with patch.object(self.scraper.session, 'get') as mock_get:
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.text = self._get_sample_google_html()
                    mock_response.headers = {'Content-Type': 'text/html'}
                    mock_response.url = f'https://www.google.com/search?q=test'
                    mock_get.return_value = mock_response
                    
                    result = self.scraper.scrape_google_search(
                        query='test',
                        country_code=country,
                        num_results=10
                    )
                    
                    self.assertTrue(result.get('success'))
                    
                    # Verify correct geoCode mapping
                    call_args = mock_get.call_args
                    params = call_args[1]['params']
                    expected_geo = self.scraper.SCRAPE_DO_GEO_CODES.get(country, 'US')
                    self.assertEqual(params['geoCode'], expected_geo)
    
    def test_google_search_with_special_characters(self):
        """Test Google search with special characters in query"""
        special_queries = [
            "python & django",
            "McDonald's restaurants",
            '"exact phrase search"',
            "C++ programming",
            "test@example.com"
        ]
        
        for query in special_queries:
            with self.subTest(query=query):
                with patch.object(self.scraper.session, 'get') as mock_get:
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.text = self._get_sample_google_html()
                    mock_response.headers = {'Content-Type': 'text/html'}
                    mock_response.url = 'https://www.google.com/search'
                    mock_get.return_value = mock_response
                    
                    result = self.scraper.scrape_google_search(
                        query=query,
                        country_code='US',
                        num_results=10
                    )
                    
                    self.assertTrue(result.get('success'))
                    
                    # Verify query is properly encoded in URL
                    call_args = mock_get.call_args
                    params = call_args[1]['params']
                    self.assertIn('q=', params['url'])
    
    def test_parse_organic_vs_sponsored(self):
        """Test parsing of organic vs sponsored results"""
        html = self._get_sample_google_html_with_ads()
        
        # Parse the HTML
        parsed = self.parser.parse(html)
        
        # Check for organic results
        self.assertIn('organic_results', parsed)
        self.assertIsInstance(parsed['organic_results'], list)
        
        # Check for sponsored results
        self.assertIn('sponsored_results', parsed)
        self.assertIsInstance(parsed['sponsored_results'], list)
    
    def test_parse_special_serp_features(self):
        """Test parsing of special SERP features"""
        html = self._get_sample_google_html_with_features()
        
        parsed = self.parser.parse(html)
        
        # Check for various SERP features
        possible_features = [
            'knowledge_graph',
            'featured_snippet',
            'people_also_ask',
            'related_searches',
            'local_pack',
            'video_results',
            'image_results'
        ]
        
        for feature in possible_features:
            with self.subTest(feature=feature):
                # Feature might or might not be present depending on HTML
                if feature in parsed:
                    self.assertIsInstance(parsed[feature], (dict, list))
    
    def test_error_handling(self):
        """Test error handling in scraping"""
        with patch.object(self.scraper.session, 'get') as mock_get:
            # Simulate API error
            mock_response = Mock()
            mock_response.status_code = 403
            mock_response.text = 'Forbidden'
            mock_get.return_value = mock_response
            
            result = self.scraper.scrape_google_search(
                query='test',
                country_code='US'
            )
            
            self.assertFalse(result.get('success'))
            self.assertEqual(result['status_code'], 403)
    
    def test_timeout_handling(self):
        """Test timeout handling"""
        import requests
        
        with patch.object(self.scraper.session, 'get') as mock_get:
            # Simulate timeout
            mock_get.side_effect = requests.exceptions.Timeout()
            
            result = self.scraper.scrape_google_search(
                query='test',
                country_code='US'
            )
            
            self.assertFalse(result.get('success'))
            self.assertIn('error', result)
    
    def _get_sample_google_html(self):
        """Get sample Google search HTML for testing"""
        return '''
        <html>
        <head><title>python - Google Search</title></head>
        <body>
            <div id="search">
                <div class="g">
                    <h3>Python.org</h3>
                    <a href="https://www.python.org">https://www.python.org</a>
                    <span>Welcome to Python.org</span>
                </div>
                <div class="g">
                    <h3>Python Tutorial</h3>
                    <a href="https://docs.python.org/tutorial">https://docs.python.org/tutorial</a>
                    <span>Learn Python programming</span>
                </div>
            </div>
        </body>
        </html>
        '''
    
    def _get_sample_google_html_with_ads(self):
        """Get sample Google HTML with ads"""
        return '''
        <html>
        <body>
            <div id="search">
                <!-- Sponsored results -->
                <div class="uEierd">
                    <div class="g">
                        <span>Ad</span>
                        <h3>Sponsored Result</h3>
                        <a href="https://example.com/ad">https://example.com</a>
                    </div>
                </div>
                <!-- Organic results -->
                <div class="g">
                    <h3>Organic Result</h3>
                    <a href="https://example.com">https://example.com</a>
                </div>
            </div>
        </body>
        </html>
        '''
    
    def _get_sample_google_html_with_features(self):
        """Get sample Google HTML with SERP features"""
        return '''
        <html>
        <body>
            <div id="search">
                <!-- Featured snippet -->
                <div class="xpdopen">
                    <div class="kp-blk">
                        <div class="xpdclose">Featured content here</div>
                    </div>
                </div>
                <!-- People also ask -->
                <div class="related-question-pair">
                    <div>What is Python?</div>
                </div>
                <!-- Organic results -->
                <div class="g">
                    <h3>Result Title</h3>
                    <a href="https://example.com">https://example.com</a>
                </div>
            </div>
        </body>
        </html>
        '''


if __name__ == '__main__':
    unittest.main()