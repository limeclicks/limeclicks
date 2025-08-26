"""
Base test classes and utilities for consistent testing across the application
"""
import os
import django

# Ensure Django is set up before importing Django modules
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'limeclicks.settings'
    django.setup()

from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from unittest.mock import Mock, patch, MagicMock
import json
import uuid
from datetime import timedelta

User = get_user_model()


class BaseTestCase(TestCase):
    """Base test case with common setup and helper methods"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cache.clear()
    
    def setUp(self):
        """Common setup for all tests"""
        self.client = Client()
        self.user = None
        self.authenticated = False
        cache.clear()
    
    def tearDown(self):
        """Clean up after each test"""
        cache.clear()
        super().tearDown()
    
    def create_user(self, email='test@example.com', password='testpass123', **kwargs):
        """Create a test user"""
        defaults = {
            'username': email.split('@')[0],
            'email': email,
            'is_active': True,
            'email_verified': True
        }
        defaults.update(kwargs)
        
        user = User.objects.create_user(
            password=password,
            **defaults
        )
        return user
    
    def authenticate(self, user=None, email='test@example.com', password='testpass123'):
        """Authenticate a user for testing"""
        if not user:
            user = self.create_user(email=email, password=password)
        
        self.client.login(username=email, password=password)
        self.user = user
        self.authenticated = True
        return user
    
    def make_ajax_request(self, method, url, data=None, **kwargs):
        """Make an AJAX request with proper headers"""
        kwargs['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        
        if method.lower() == 'get':
            return self.client.get(url, data, **kwargs)
        elif method.lower() == 'post':
            if isinstance(data, dict):
                data = json.dumps(data)
                kwargs['content_type'] = 'application/json'
            return self.client.post(url, data, **kwargs)
        elif method.lower() == 'put':
            if isinstance(data, dict):
                data = json.dumps(data)
                kwargs['content_type'] = 'application/json'
            return self.client.put(url, data, **kwargs)
        elif method.lower() == 'delete':
            return self.client.delete(url, **kwargs)
    
    def assert_ajax_success(self, response, message=None):
        """Assert that an AJAX response indicates success"""
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'))
        if message:
            self.assertIn(message, data.get('message', ''))
        return data
    
    def assert_ajax_error(self, response, message=None, status_code=200):
        """Assert that an AJAX response indicates an error"""
        self.assertEqual(response.status_code, status_code)
        if response.content:
            data = json.loads(response.content)
            self.assertFalse(data.get('success'))
            if message:
                self.assertIn(message, str(data.get('message', '')) + str(data.get('errors', '')))
            return data
        return None


class ModelTestMixin:
    """Mixin for model testing with common assertions"""
    
    def assert_model_field_exists(self, model, field_name):
        """Assert that a model has a specific field"""
        self.assertIn(field_name, [f.name for f in model._meta.fields])
    
    def assert_model_has_method(self, model, method_name):
        """Assert that a model has a specific method"""
        self.assertTrue(hasattr(model, method_name))
        self.assertTrue(callable(getattr(model, method_name)))
    
    def assert_model_str(self, instance, expected_str):
        """Assert the string representation of a model instance"""
        self.assertEqual(str(instance), expected_str)
    
    def assert_field_optional(self, model, field_name):
        """Assert that a field is optional (null=True, blank=True)"""
        field = model._meta.get_field(field_name)
        self.assertTrue(field.null)
        self.assertTrue(field.blank)
    
    def assert_field_required(self, model, field_name):
        """Assert that a field is required"""
        field = model._meta.get_field(field_name)
        self.assertFalse(field.null)
        self.assertFalse(field.blank)


class AuditTestMixin:
    """Mixin for testing audit-related functionality"""
    
    def create_mock_audit_history(self, status='completed', **kwargs):
        """Create a mock audit history object"""
        defaults = {
            'id': uuid.uuid4(),
            'status': status,
            'created_at': timezone.now(),
            'started_at': timezone.now() if status != 'pending' else None,
            'completed_at': timezone.now() if status == 'completed' else None,
            'error_message': None if status != 'failed' else 'Test error',
            'retry_count': 0,
            'trigger_type': 'manual'
        }
        defaults.update(kwargs)
        
        mock_audit = Mock()
        for key, value in defaults.items():
            setattr(mock_audit, key, value)
        
        # Add methods
        mock_audit.mark_running = Mock()
        mock_audit.mark_completed = Mock()
        mock_audit.mark_failed = Mock()
        
        return mock_audit
    
    def assert_audit_pending(self, audit):
        """Assert that an audit is in pending state"""
        self.assertEqual(audit.status, 'pending')
        self.assertIsNone(audit.started_at)
        self.assertIsNone(audit.completed_at)
    
    def assert_audit_running(self, audit):
        """Assert that an audit is in running state"""
        self.assertEqual(audit.status, 'running')
        self.assertIsNotNone(audit.started_at)
        self.assertIsNone(audit.completed_at)
    
    def assert_audit_completed(self, audit):
        """Assert that an audit is in completed state"""
        self.assertEqual(audit.status, 'completed')
        self.assertIsNotNone(audit.started_at)
        self.assertIsNotNone(audit.completed_at)
    
    def assert_audit_failed(self, audit):
        """Assert that an audit is in failed state"""
        self.assertEqual(audit.status, 'failed')
        self.assertIsNotNone(audit.error_message)


class CeleryTestMixin:
    """Mixin for testing Celery tasks"""
    
    def setUp(self):
        """Set up Celery task testing"""
        super().setUp()
        self.celery_patch = patch('celery.task.control.inspect')
        self.celery_patch.start()
    
    def tearDown(self):
        """Clean up Celery patches"""
        self.celery_patch.stop()
        super().tearDown()
    
    def assert_task_called(self, task_mock, *args, **kwargs):
        """Assert that a Celery task was called with specific arguments"""
        if args and kwargs:
            task_mock.delay.assert_called_with(*args, **kwargs)
        elif args:
            task_mock.delay.assert_called_with(*args)
        elif kwargs:
            task_mock.delay.assert_called_with(**kwargs)
        else:
            task_mock.delay.assert_called()
    
    def create_mock_task_result(self, success=True, result=None):
        """Create a mock Celery task result"""
        mock_result = Mock()
        mock_result.successful.return_value = success
        mock_result.result = result if result else {'success': success}
        mock_result.id = str(uuid.uuid4())
        return mock_result


class IntegrationTestCase(TransactionTestCase):
    """Base class for integration tests that require transactions"""
    
    fixtures = []  # Add fixtures if needed
    
    def setUp(self):
        """Set up integration test environment"""
        super().setUp()
        cache.clear()
        self.client = Client()
    
    def tearDown(self):
        """Clean up after integration tests"""
        cache.clear()
        super().tearDown()
    
    def wait_for_condition(self, condition_func, timeout=5, interval=0.1):
        """Wait for a condition to be true"""
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if condition_func():
                return True
            time.sleep(interval)
        
        return False


class APITestMixin:
    """Mixin for testing API endpoints"""
    
    def assert_api_response_structure(self, response, expected_keys):
        """Assert that API response has expected structure"""
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        for key in expected_keys:
            self.assertIn(key, data)
        
        return data
    
    def assert_pagination_response(self, response):
        """Assert that a paginated response has correct structure"""
        data = self.assert_api_response_structure(
            response,
            ['results', 'page', 'per_page', 'total_pages', 'total_items', 
             'has_next', 'has_previous']
        )
        
        self.assertIsInstance(data['results'], list)
        self.assertIsInstance(data['page'], int)
        self.assertIsInstance(data['total_pages'], int)
        
        return data
    
    def assert_error_response(self, response, status_code=400, error_key='error'):
        """Assert that an error response has correct structure"""
        self.assertEqual(response.status_code, status_code)
        
        if response.content:
            data = json.loads(response.content)
            self.assertIn(error_key, data)
            return data
        
        return None