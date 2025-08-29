import os
import django

# Ensure Django is set up before importing Django modules
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'limeclicks.settings'
    django.setup()

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from unittest.mock import patch, Mock
from .models import Project

User = get_user_model()


class FaviconCachingTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        cache.clear()  # Clear cache before each test

    def test_cached_favicon_url_generation(self):
        """Test that cached favicon URLs are generated correctly"""
        project = Project.objects.create(
            user=self.user,
            domain='github.com'
        )
        
        # Test cached URL generation
        cached_url = project.get_cached_favicon_url()
        expected_url = reverse('project:favicon_proxy', kwargs={'domain': 'github.com'}) + '?size=64'
        self.assertEqual(cached_url, expected_url)
        
        # Test with custom size
        cached_url_32 = project.get_cached_favicon_url(32)
        expected_url_32 = reverse('project:favicon_proxy', kwargs={'domain': 'github.com'}) + '?size=32'
        self.assertEqual(cached_url_32, expected_url_32)

    @patch('project.favicon_utils.requests.get')
    def test_favicon_proxy_cache_miss(self, mock_get):
        """Test favicon proxy on cache miss"""
        # Mock successful response from Google
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'fake_favicon_data'
        mock_response.headers = {'Content-Type': 'image/png'}
        mock_get.return_value = mock_response
        
        # Make request to proxy
        url = reverse('project:favicon_proxy', kwargs={'domain': 'github.com'})
        response = self.client.get(url + '?size=64')
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'fake_favicon_data')
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertEqual(response['X-Favicon-Cache'], 'MISS')
        self.assertIn('Cache-Control', response)
        
        # Verify Google API was called
        mock_get.assert_called_once_with(
            'https://www.google.com/s2/favicons?domain=github.com&sz=64',
            timeout=10
        )

    @patch('project.favicon_utils.requests.get')
    def test_favicon_proxy_cache_hit(self, mock_get):
        """Test favicon proxy on cache hit"""
        # Pre-populate cache with correct hash
        import hashlib
        domain_hash = hashlib.md5('github.com'.encode()).hexdigest()
        cache_key = f'favicon_{domain_hash}_64'
        cache.set(cache_key, {
            'content': b'cached_favicon_data',
            'content_type': 'image/png'
        }, 21600)
        
        # Make request to proxy
        url = reverse('project:favicon_proxy', kwargs={'domain': 'github.com'})
        response = self.client.get(url + '?size=64')
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'cached_favicon_data')
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertEqual(response['X-Favicon-Cache'], 'HIT')
        self.assertIn('Cache-Control', response)
        
        # Verify Google API was NOT called
        mock_get.assert_not_called()

    def test_favicon_proxy_invalid_size(self):
        """Test favicon proxy with invalid size parameter"""
        with patch('project.favicon_utils.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b'favicon_data'
            mock_response.headers = {'Content-Type': 'image/png'}
            mock_get.return_value = mock_response
            
            # Test with invalid size
            url = reverse('project:favicon_proxy', kwargs={'domain': 'github.com'})
            response = self.client.get(url + '?size=invalid')
            
            self.assertEqual(response.status_code, 200)
            
            # Should default to size 64
            mock_get.assert_called_once_with(
                'https://www.google.com/s2/favicons?domain=github.com&sz=64',
                timeout=10
            )

    def test_favicon_proxy_unsupported_size(self):
        """Test favicon proxy with unsupported size parameter"""
        with patch('project.favicon_utils.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b'favicon_data'
            mock_response.headers = {'Content-Type': 'image/png'}
            mock_get.return_value = mock_response
            
            # Test with unsupported size
            url = reverse('project:favicon_proxy', kwargs={'domain': 'github.com'})
            response = self.client.get(url + '?size=999')
            
            self.assertEqual(response.status_code, 200)
            
            # Should default to size 64
            mock_get.assert_called_once_with(
                'https://www.google.com/s2/favicons?domain=github.com&sz=64',
                timeout=10
            )

    @patch('project.favicon_utils.requests.get')
    def test_favicon_proxy_google_error(self, mock_get):
        """Test favicon proxy when Google service returns error"""
        # Mock error response from Google
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        # Make request to proxy
        url = reverse('project:favicon_proxy', kwargs={'domain': 'nonexistent.domain'})
        response = self.client.get(url)
        
        # Verify error response
        self.assertEqual(response.status_code, 404)
        
        # Verify Google API was called
        mock_get.assert_called_once()

    @patch('project.favicon_utils.requests.get')
    def test_favicon_proxy_network_error(self, mock_get):
        """Test favicon proxy when network error occurs"""
        # Mock network error
        mock_get.side_effect = Exception("Network error")
        
        # Make request to proxy
        url = reverse('project:favicon_proxy', kwargs={'domain': 'github.com'})
        response = self.client.get(url)
        
        # Verify error response
        self.assertEqual(response.status_code, 404)

    def test_favicon_cache_key_generation(self):
        """Test that cache keys are generated consistently"""
        import hashlib
        
        domain = 'github.com'
        size = 64
        
        expected_key = f"favicon_{hashlib.md5(domain.encode()).hexdigest()}_{size}"
        
        # The actual cache key generation happens in favicon_utils
        # Let's verify it matches our expectation
        project = Project.objects.create(user=self.user, domain=domain)
        
        # Make a request to trigger cache key generation
        with patch('project.favicon_utils.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b'favicon_data'
            mock_response.headers = {'Content-Type': 'image/png'}
            mock_get.return_value = mock_response
            
            url = reverse('project:favicon_proxy', kwargs={'domain': domain})
            self.client.get(url + f'?size={size}')
            
            # Verify data was cached with expected key
            cached_data = cache.get(expected_key)
            self.assertIsNotNone(cached_data)
            self.assertEqual(cached_data['content'], b'favicon_data')

    def test_favicon_cache_expiration(self):
        """Test that favicon cache has proper expiration"""
        # This test verifies cache timeout but doesn't wait for actual expiration
        # Instead, we verify the cache.set call parameters
        
        with patch('project.favicon_utils.cache.set') as mock_cache_set:
            with patch('project.favicon_utils.requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.content = b'favicon_data'
                mock_response.headers = {'Content-Type': 'image/png'}
                mock_get.return_value = mock_response
                
                url = reverse('project:favicon_proxy', kwargs={'domain': 'github.com'})
                self.client.get(url)
                
                # Verify cache.set was called with 6 hours (21600 seconds)
                mock_cache_set.assert_called_once()
                args, kwargs = mock_cache_set.call_args
                self.assertEqual(args[2], 21600)  # 6 hours in seconds

    def test_multiple_sizes_cached_separately(self):
        """Test that different sizes are cached separately"""
        with patch('project.favicon_utils.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b'favicon_data'
            mock_response.headers = {'Content-Type': 'image/png'}
            mock_get.return_value = mock_response
            
            url = reverse('project:favicon_proxy', kwargs={'domain': 'github.com'})
            
            # Request different sizes
            self.client.get(url + '?size=32')
            self.client.get(url + '?size=64')
            self.client.get(url + '?size=128')
            
            # Verify separate Google API calls for each size
            self.assertEqual(mock_get.call_count, 3)
            
            # Verify different cache keys exist
            import hashlib
            domain_hash = hashlib.md5('github.com'.encode()).hexdigest()
            
            self.assertIsNotNone(cache.get(f'favicon_{domain_hash}_32'))
            self.assertIsNotNone(cache.get(f'favicon_{domain_hash}_64'))
            self.assertIsNotNone(cache.get(f'favicon_{domain_hash}_128'))