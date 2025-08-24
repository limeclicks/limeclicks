"""
Tests for Scrape.do service
"""

from django.test import TestCase, override_settings
from unittest.mock import Mock, patch, MagicMock
from django.core.cache import cache
import requests

from .scrape_do import ScrapeDoService, get_scraper


class ScrapeDoServiceTest(TestCase):
    """Test cases for ScrapeDoService"""
    
    def setUp(self):
        """Set up test data"""
        cache.clear()
        self.api_key = 'test_api_key_12345'
        self.service = ScrapeDoService(api_key=self.api_key)
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
    
    @patch('services.scrape_do.requests.Session')
    def test_initialization_with_api_key(self, mock_session):
        """Test service initialization with API key"""
        service = ScrapeDoService(api_key='custom_key')
        self.assertEqual(service.api_key, 'custom_key')
        self.assertIsNotNone(service.session)
    
    @override_settings(SCRAPPER_API_KEY='settings_api_key')
    def test_initialization_from_settings(self):
        """Test service initialization from Django settings"""
        service = ScrapeDoService()
        self.assertEqual(service.api_key, 'settings_api_key')
    
    def test_initialization_without_api_key(self):
        """Test that initialization fails without API key"""
        with override_settings(SCRAPPER_API_KEY=None):
            with self.assertRaises(ValueError) as context:
                ScrapeDoService()
            self.assertIn('SCRAPPER_API_KEY not found', str(context.exception))
    
    @patch.object(requests.Session, 'get')
    def test_scrape_success(self, mock_get):
        """Test successful scraping"""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<html><body>Test content</body></html>'
        mock_response.headers = {'Content-Type': 'text/html'}
        mock_response.url = 'https://example.com'
        mock_get.return_value = mock_response
        
        result = self.service.scrape('https://example.com')
        
        self.assertIsNotNone(result)
        self.assertTrue(result['success'])
        self.assertEqual(result['status_code'], 200)
        self.assertIn('Test content', result['html'])
        
        # Verify API call
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[1]['params']['token'], self.api_key)
        self.assertEqual(call_args[1]['params']['url'], 'https://example.com')
    
    @patch.object(requests.Session, 'get')
    def test_scrape_with_country_code(self, mock_get):
        """Test scraping with country code"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'Content'
        mock_response.headers = {}
        mock_response.url = 'https://example.com'
        mock_get.return_value = mock_response
        
        self.service.scrape('https://example.com', country_code='us')
        
        call_args = mock_get.call_args
        self.assertEqual(call_args[1]['params']['geoCode'], 'us')
    
    @patch.object(requests.Session, 'get')
    def test_scrape_with_render_options(self, mock_get):
        """Test scraping with JavaScript rendering options"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'Rendered content'
        mock_response.headers = {}
        mock_response.url = 'https://example.com'
        mock_get.return_value = mock_response
        
        self.service.scrape(
            'https://example.com',
            render=True,
            wait_for=3000,
            block_resources=True
        )
        
        call_args = mock_get.call_args
        params = call_args[1]['params']
        self.assertEqual(params['render'], 'true')
        self.assertEqual(params['waitFor'], 3000)
        self.assertEqual(params['blockResources'], 'true')
    
    @patch.object(requests.Session, 'get')
    def test_scrape_with_custom_headers(self, mock_get):
        """Test scraping with custom headers"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'Content'
        mock_response.headers = {}
        mock_response.url = 'https://example.com'
        mock_get.return_value = mock_response
        
        custom_headers = {
            'Accept-Language': 'en-US',
            'Custom-Header': 'Value'
        }
        
        self.service.scrape('https://example.com', custom_headers=custom_headers)
        
        call_args = mock_get.call_args
        params = call_args[1]['params']
        self.assertEqual(params['customHeaders[Accept-Language]'], 'en-US')
        self.assertEqual(params['customHeaders[Custom-Header]'], 'Value')
    
    @patch.object(requests.Session, 'get')
    def test_scrape_with_special_characters_in_url(self, mock_get):
        """Test that URLs with special characters are properly handled"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'Content'
        mock_response.headers = {}
        mock_response.url = 'https://example.com'
        mock_get.return_value = mock_response
        
        # URL with special characters
        url_with_special = 'https://example.com/search?q=hello world&filter=price>100'
        
        self.service.scrape(url_with_special)
        
        call_args = mock_get.call_args
        # The URL should be passed as-is to requests, which handles encoding
        self.assertEqual(call_args[1]['params']['url'], url_with_special)
    
    @patch.object(requests.Session, 'get')
    def test_scrape_failure(self, mock_get):
        """Test handling of failed scraping"""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = 'Forbidden'
        mock_get.return_value = mock_response
        
        result = self.service.scrape('https://example.com')
        
        self.assertIsNotNone(result)
        self.assertFalse(result['success'])
        self.assertEqual(result['status_code'], 403)
        self.assertEqual(result['error'], 'Forbidden')
    
    @patch.object(requests.Session, 'get')
    def test_scrape_timeout(self, mock_get):
        """Test handling of request timeout"""
        mock_get.side_effect = requests.exceptions.Timeout()
        
        result = self.service.scrape('https://example.com')
        
        self.assertIsNotNone(result)
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Request timeout')
    
    @patch.object(requests.Session, 'get')
    def test_scrape_request_exception(self, mock_get):
        """Test handling of request exceptions"""
        mock_get.side_effect = requests.exceptions.ConnectionError('Connection failed')
        
        result = self.service.scrape('https://example.com')
        
        self.assertIsNotNone(result)
        self.assertFalse(result['success'])
        self.assertIn('Connection failed', result['error'])
    
    @patch.object(requests.Session, 'get')
    def test_scrape_with_caching(self, mock_get):
        """Test caching functionality"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'Cached content'
        mock_response.headers = {}
        mock_response.url = 'https://example.com'
        mock_get.return_value = mock_response
        
        # First call should hit the API
        result1 = self.service.scrape('https://example.com', use_cache=True)
        self.assertEqual(mock_get.call_count, 1)
        
        # Second call should use cache
        result2 = self.service.scrape('https://example.com', use_cache=True)
        self.assertEqual(mock_get.call_count, 1)  # No additional API call
        
        # Results should be the same
        self.assertEqual(result1['html'], result2['html'])
        
        # Call without cache should hit API again
        result3 = self.service.scrape('https://example.com', use_cache=False)
        self.assertEqual(mock_get.call_count, 2)
    
    @patch.object(requests.Session, 'get')
    def test_scrape_batch(self, mock_get):
        """Test batch scraping"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'Content'
        mock_response.headers = {}
        mock_response.url = 'https://example.com'
        mock_get.return_value = mock_response
        
        urls = [
            'https://example1.com',
            'https://example2.com',
            'https://example3.com'
        ]
        
        results = self.service.scrape_batch(urls, country_code='us')
        
        self.assertEqual(len(results), 3)
        self.assertIn('https://example1.com', results)
        self.assertIn('https://example2.com', results)
        self.assertIn('https://example3.com', results)
        self.assertEqual(mock_get.call_count, 3)
    
    @patch.object(requests.Session, 'get')
    def test_scrape_with_retry(self, mock_get):
        """Test retry functionality"""
        # First two calls fail, third succeeds
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_response_fail.text = 'Server error'
        
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.text = 'Success'
        mock_response_success.headers = {}
        mock_response_success.url = 'https://example.com'
        
        mock_get.side_effect = [
            mock_response_fail,
            mock_response_fail,
            mock_response_success
        ]
        
        result = self.service.scrape_with_retry('https://example.com', max_retries=3)
        
        self.assertIsNotNone(result)
        self.assertTrue(result['success'])
        self.assertEqual(mock_get.call_count, 3)
    
    @patch.object(requests.Session, 'get')
    def test_scrape_google_search(self, mock_get):
        """Test Google search scraping convenience method"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'Search results'
        mock_response.headers = {}
        mock_response.url = 'https://google.com'
        mock_get.return_value = mock_response
        
        result = self.service.scrape_google_search('python django', country_code='uk')
        
        call_args = mock_get.call_args
        params = call_args[1]['params']
        
        # Check that the URL contains the search query
        self.assertIn('python', params['url'])
        self.assertIn('django', params['url'])
        self.assertEqual(params['geoCode'], 'uk')
        self.assertEqual(params['render'], 'true')
        self.assertEqual(params['waitFor'], 3000)
    
    @patch.object(requests.Session, 'get')
    def test_scrape_google_search_with_gl_hl(self, mock_get):
        """Test Google search with gl and hl parameters"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'German search results'
        mock_response.headers = {}
        mock_response.url = 'https://google.de'
        mock_get.return_value = mock_response
        
        result = self.service.scrape_google_search(
            'python django',
            gl='de',  # Germany results
            hl='de',  # German interface
            num_results=100
        )
        
        call_args = mock_get.call_args
        params = call_args[1]['params']
        url = params['url']
        
        # Check URL parameters
        self.assertIn('gl=de', url)
        self.assertIn('hl=de', url)
        self.assertIn('num=100', url)
        self.assertIn('q=python', url)
    
    def test_uule_encoding(self):
        """Test UULE encoding for Google location"""
        # Test New York location
        location = "New York,New York,United States"
        uule = self.service.encode_uule(location)
        
        # UULE should start with w+CAIQICI
        self.assertTrue(uule.startswith('w+CAIQICI'))
        # Should contain the location
        self.assertIn('New York', uule)
        
        # Test another location
        location2 = "London,England,United Kingdom"
        uule2 = self.service.encode_uule(location2)
        self.assertTrue(uule2.startswith('w+CAIQICI'))
        self.assertIn('London', uule2)
        
        # Different locations should produce different UULE
        self.assertNotEqual(uule, uule2)
    
    @patch.object(requests.Session, 'get')
    def test_scrape_google_search_with_uule(self, mock_get):
        """Test Google search with UULE location parameter"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'Location-based results'
        mock_response.headers = {}
        mock_response.url = 'https://google.com'
        mock_get.return_value = mock_response
        
        result = self.service.scrape_google_search(
            'restaurants',
            location='New York,New York,United States',
            use_exact_location=True
        )
        
        call_args = mock_get.call_args
        params = call_args[1]['params']
        url = params['url']
        
        # Check that UULE parameter is in URL
        self.assertIn('uule=', url)
        self.assertIn('w%2BCAIQICI', url)  # URL-encoded w+CAIQICI
    
    @patch.object(requests.Session, 'get')
    def test_scrape_google_search_pagination(self, mock_get):
        """Test Google search with pagination"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'Page 2 results'
        mock_response.headers = {}
        mock_response.url = 'https://google.com'
        mock_get.return_value = mock_response
        
        result = self.service.scrape_google_search(
            'python',
            start=100,  # Start from result 100
            num_results=100
        )
        
        call_args = mock_get.call_args
        params = call_args[1]['params']
        url = params['url']
        
        # Check pagination parameter
        self.assertIn('start=100', url)
        self.assertIn('num=100', url)
    
    @patch.object(requests.Session, 'get')
    def test_scrape_google_search_pages(self, mock_get):
        """Test scraping multiple pages of Google results"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'Results'
        mock_response.headers = {}
        mock_response.url = 'https://google.com'
        mock_get.return_value = mock_response
        
        results = self.service.scrape_google_search_pages(
            'python django',
            pages=3,
            results_per_page=50
        )
        
        # Should make 3 requests
        self.assertEqual(len(results), 3)
        self.assertEqual(mock_get.call_count, 3)
        
        # Check pagination for each call
        calls = mock_get.call_args_list
        for i, call in enumerate(calls):
            url = call[1]['params']['url']
            expected_start = i * 50
            if expected_start > 0:
                self.assertIn(f'start={expected_start}', url)
    
    def test_cache_key_generation(self):
        """Test cache key generation"""
        key1 = self.service._generate_cache_key('https://example.com')
        key2 = self.service._generate_cache_key('https://example.com')
        key3 = self.service._generate_cache_key('https://different.com')
        
        # Same URL should generate same key
        self.assertEqual(key1, key2)
        # Different URL should generate different key
        self.assertNotEqual(key1, key3)
        # Key should start with prefix
        self.assertTrue(key1.startswith('scrape_do_'))
    
    @patch.object(requests.Session, 'get')
    def test_get_usage(self, mock_get):
        """Test API usage statistics retrieval"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'requests_made': 100,
            'requests_limit': 1000
        }
        mock_get.return_value = mock_response
        
        usage = self.service.get_usage()
        
        self.assertIsNotNone(usage)
        self.assertEqual(usage['requests_made'], 100)
        self.assertEqual(usage['requests_limit'], 1000)


class GetScraperTest(TestCase):
    """Test the get_scraper utility function"""
    
    @override_settings(SCRAPPER_API_KEY='test_key')
    def test_get_scraper_singleton(self):
        """Test that get_scraper returns singleton instance"""
        scraper1 = get_scraper()
        scraper2 = get_scraper()
        
        # Should return the same instance
        self.assertIs(scraper1, scraper2)
    
    @override_settings(SCRAPPER_API_KEY='test_key')
    def test_get_scraper_with_different_api_key(self):
        """Test that providing different API key creates new instance"""
        scraper1 = get_scraper()
        scraper2 = get_scraper(api_key='different_key')
        
        # Should create new instance with different API key
        self.assertEqual(scraper2.api_key, 'different_key')