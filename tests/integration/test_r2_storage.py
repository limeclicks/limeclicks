"""
Integration tests for R2 Storage
"""

import os
import json
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
from io import BytesIO

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.test import TestCase
from services.r2_storage import R2StorageService, get_r2_service


class R2StorageIntegrationTest(TestCase):
    """Integration tests for R2 storage service"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock environment variables if not set
        with patch.dict(os.environ, {
            'R2_ACCESS_KEY_ID': os.getenv('R2_ACCESS_KEY_ID', 'test_access_key'),
            'R2_SECRET_ACCESS_KEY': os.getenv('R2_SECRET_ACCESS_KEY', 'test_secret_key'),
            'R2_BUCKET_NAME': os.getenv('R2_BUCKET_NAME', 'test-bucket'),
            'R2_ENDPOINT_URL': os.getenv('R2_ENDPOINT_URL', 'https://test.r2.cloudflarestorage.com')
        }):
            self.service = R2StorageService()
    
    @patch('boto3.client')
    @patch('boto3.resource')
    def test_upload_file(self, mock_resource, mock_client):
        """Test file upload to R2"""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_client.return_value = mock_s3_client
        
        mock_s3_resource = MagicMock()
        mock_resource.return_value = mock_s3_resource
        
        # Reinitialize service with mocked boto3
        with patch.dict(os.environ, {
            'R2_ACCESS_KEY_ID': 'test_key',
            'R2_SECRET_ACCESS_KEY': 'test_secret',
            'R2_BUCKET_NAME': 'test-bucket',
            'R2_ENDPOINT_URL': 'https://test.r2.cloudflarestorage.com'
        }):
            service = R2StorageService()
            service.client = mock_s3_client
        
        # Test upload
        test_content = b"Test file content"
        test_key = "test/file.txt"
        
        result = service.upload_file(
            test_content,
            test_key,
            content_type='text/plain'
        )
        
        # Assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['key'], test_key)
        
        # Verify boto3 was called correctly
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args
        self.assertEqual(call_args[1]['Key'], test_key)
        self.assertEqual(call_args[1]['Body'], test_content)
        self.assertEqual(call_args[1]['ContentType'], 'text/plain')
    
    @patch('boto3.client')
    @patch('boto3.resource')
    def test_download_file(self, mock_resource, mock_client):
        """Test file download from R2"""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_client.return_value = mock_s3_client
        
        mock_response = {
            'Body': BytesIO(b"Downloaded content")
        }
        mock_s3_client.get_object.return_value = mock_response
        
        # Reinitialize service
        with patch.dict(os.environ, {
            'R2_ACCESS_KEY_ID': 'test_key',
            'R2_SECRET_ACCESS_KEY': 'test_secret',
            'R2_BUCKET_NAME': 'test-bucket',
            'R2_ENDPOINT_URL': 'https://test.r2.cloudflarestorage.com'
        }):
            service = R2StorageService()
            service.client = mock_s3_client
        
        # Test download
        content = service.download_file("test/file.txt")
        
        # Assertions
        self.assertIsNotNone(content)
        self.assertEqual(content, b"Downloaded content")
        
        mock_s3_client.get_object.assert_called_once_with(
            Bucket='test-bucket',
            Key='test/file.txt'
        )
    
    @patch('boto3.client')
    @patch('boto3.resource')
    def test_upload_json(self, mock_resource, mock_client):
        """Test JSON upload to R2"""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_client.return_value = mock_s3_client
        
        # Reinitialize service
        with patch.dict(os.environ, {
            'R2_ACCESS_KEY_ID': 'test_key',
            'R2_SECRET_ACCESS_KEY': 'test_secret',
            'R2_BUCKET_NAME': 'test-bucket',
            'R2_ENDPOINT_URL': 'https://test.r2.cloudflarestorage.com'
        }):
            service = R2StorageService()
            service.client = mock_s3_client
        
        # Test data
        test_data = {
            'keyword': 'python django',
            'rank': 5,
            'results': ['result1', 'result2']
        }
        
        # Upload JSON
        result = service.upload_json(test_data, 'test/data.json')
        
        # Assertions
        self.assertTrue(result['success'])
        
        # Verify the JSON was serialized correctly
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args
        uploaded_json = call_args[1]['Body']
        parsed_data = json.loads(uploaded_json.decode('utf-8'))
        self.assertEqual(parsed_data, test_data)
    
    @patch('boto3.client')
    @patch('boto3.resource')
    def test_file_exists(self, mock_resource, mock_client):
        """Test checking if file exists in R2"""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_client.return_value = mock_s3_client
        
        # Reinitialize service
        with patch.dict(os.environ, {
            'R2_ACCESS_KEY_ID': 'test_key',
            'R2_SECRET_ACCESS_KEY': 'test_secret',
            'R2_BUCKET_NAME': 'test-bucket',
            'R2_ENDPOINT_URL': 'https://test.r2.cloudflarestorage.com'
        }):
            service = R2StorageService()
            service.client = mock_s3_client
        
        # Test file exists
        mock_s3_client.head_object.return_value = {'ContentLength': 100}
        exists = service.file_exists('test/file.txt')
        self.assertTrue(exists)
        
        # Test file doesn't exist
        from botocore.exceptions import ClientError
        mock_s3_client.head_object.side_effect = ClientError(
            {'Error': {'Code': '404'}},
            'HeadObject'
        )
        exists = service.file_exists('nonexistent.txt')
        self.assertFalse(exists)
    
    def test_generate_unique_key(self):
        """Test unique key generation"""
        service = self.service
        
        # Test with timestamp
        key1 = service.generate_unique_key('uploads', 'test.pdf', include_timestamp=True)
        self.assertTrue(key1.startswith('uploads/'))
        self.assertTrue(key1.endswith('.pdf'))
        
        # Test without timestamp
        key2 = service.generate_unique_key('uploads', 'test.pdf', include_timestamp=False)
        self.assertTrue(key2.startswith('uploads/'))
        self.assertTrue(key2.endswith('.pdf'))
        
        # Keys should be different
        self.assertNotEqual(key1, key2)
    
    def test_create_folder_structure(self):
        """Test folder structure creation"""
        service = self.service
        
        # Mock datetime to get consistent results
        with patch('services.r2_storage.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30, 0)
            
            path = service.create_folder_structure('search-results')
            self.assertEqual(path, 'search-results/2024/01/15')
    
    @patch('boto3.client')
    @patch('boto3.resource')
    def test_get_presigned_url(self, mock_resource, mock_client):
        """Test presigned URL generation"""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_client.return_value = mock_s3_client
        
        mock_s3_client.generate_presigned_url.return_value = 'https://signed-url.example.com'
        
        # Reinitialize service
        with patch.dict(os.environ, {
            'R2_ACCESS_KEY_ID': 'test_key',
            'R2_SECRET_ACCESS_KEY': 'test_secret',
            'R2_BUCKET_NAME': 'test-bucket',
            'R2_ENDPOINT_URL': 'https://test.r2.cloudflarestorage.com'
        }):
            service = R2StorageService()
            service.client = mock_s3_client
        
        # Get URL
        url = service.get_url('test/file.txt', expiration=7200)
        
        # Assertions
        self.assertEqual(url, 'https://signed-url.example.com')
        mock_s3_client.generate_presigned_url.assert_called_once_with(
            'get_object',
            Params={'Bucket': 'test-bucket', 'Key': 'test/file.txt'},
            ExpiresIn=7200
        )
    
    def test_singleton_pattern(self):
        """Test that get_r2_service returns singleton"""
        with patch.dict(os.environ, {
            'R2_ACCESS_KEY_ID': 'test_key',
            'R2_SECRET_ACCESS_KEY': 'test_secret',
            'R2_BUCKET_NAME': 'test-bucket',
            'R2_ENDPOINT_URL': 'https://test.r2.cloudflarestorage.com'
        }):
            service1 = get_r2_service()
            service2 = get_r2_service()
            
            # Should be the same instance
            self.assertIs(service1, service2)


if __name__ == '__main__':
    unittest.main()