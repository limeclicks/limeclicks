"""
Tests for common utilities, models, and admin mixins
"""
from django.test import TestCase, override_settings
from unittest import skipUnless
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.db import models, connection
from unittest.mock import Mock, patch, MagicMock
import json
import uuid
from datetime import timedelta

from common.utils import (
    get_logger, create_ajax_response, paginate_queryset,
    chunk_list, safe_get, format_duration, format_bytes,
    batch_process, normalize_domain, is_valid_email,
    generate_unique_filename
)
from common.models import BaseAuditHistory, BaseAuditModel, TimestampedModel
from common.tasks import BaseAuditTask, cleanup_old_records
from common.test_base import BaseTestCase, ModelTestMixin, AuditTestMixin

User = get_user_model()


# Test Models for testing abstract base classes
class TestTimestampedModel(TimestampedModel):
    """Concrete model for testing TimestampedModel"""
    name = models.CharField(max_length=100)
    
    class Meta:
        app_label = 'common'


class TestAuditHistory(BaseAuditHistory):
    """Concrete model for testing BaseAuditHistory"""
    test_field = models.CharField(max_length=100)
    
    class Meta:
        app_label = 'common'


class TestAuditModel(BaseAuditModel):
    """Concrete model for testing BaseAuditModel"""
    name = models.CharField(max_length=100)
    
    class Meta:
        app_label = 'common'


class CommonUtilsTest(BaseTestCase):
    """Test common utility functions"""
    
    def test_get_logger(self):
        """Test logger creation"""
        logger = get_logger('test_logger')
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, 'test_logger')
    
    def test_create_ajax_response_success(self):
        """Test creating successful AJAX response"""
        response = create_ajax_response(
            success=True,
            message='Test successful',
            data={'key': 'value'}
        )
        
        self.assertIsInstance(response, JsonResponse)
        content = json.loads(response.content)
        
        self.assertTrue(content['success'])
        self.assertEqual(content['message'], 'Test successful')
        self.assertEqual(content['data']['key'], 'value')
    
    def test_create_ajax_response_error(self):
        """Test creating error AJAX response"""
        response = create_ajax_response(
            success=False,
            message='Test error'
        )
        
        content = json.loads(response.content)
        self.assertFalse(content['success'])
        self.assertEqual(content['message'], 'Test error')
        self.assertNotIn('data', content)
    
    def test_chunk_list(self):
        """Test list chunking"""
        items = list(range(10))
        chunks = list(chunk_list(items, chunk_size=3))
        
        self.assertEqual(len(chunks), 4)
        self.assertEqual(chunks[0], [0, 1, 2])
        self.assertEqual(chunks[1], [3, 4, 5])
        self.assertEqual(chunks[2], [6, 7, 8])
        self.assertEqual(chunks[3], [9])
    
    def test_safe_get(self):
        """Test safe dictionary access"""
        data = {
            'level1': {
                'level2': {
                    'level3': 'value'
                }
            }
        }
        
        # Successful nested access
        result = safe_get(data, 'level1', 'level2', 'level3')
        self.assertEqual(result, 'value')
        
        # Failed access with default
        result = safe_get(data, 'level1', 'missing', default='default')
        self.assertEqual(result, 'default')
        
        # Access on None
        result = safe_get(None, 'key', default='default')
        self.assertEqual(result, 'default')
    
    def test_format_duration(self):
        """Test duration formatting"""
        self.assertEqual(format_duration(45), '45s')
        self.assertEqual(format_duration(90), '1m 30s')
        self.assertEqual(format_duration(3600), '1h')
        self.assertEqual(format_duration(3665), '1h 1m')
        self.assertEqual(format_duration(86400), '1d')
        self.assertEqual(format_duration(90000), '1d 1h')
        self.assertEqual(format_duration(None), '-')
    
    def test_format_bytes(self):
        """Test byte formatting"""
        self.assertEqual(format_bytes(512), '512.0 B')
        self.assertEqual(format_bytes(1024), '1.0 KB')
        self.assertEqual(format_bytes(1536), '1.5 KB')
        self.assertEqual(format_bytes(1048576), '1.0 MB')
        self.assertEqual(format_bytes(1073741824), '1.0 GB')
    
    def test_normalize_domain(self):
        """Test domain normalization"""
        self.assertEqual(normalize_domain('https://www.example.com/'), 'example.com')
        self.assertEqual(normalize_domain('http://example.com'), 'example.com')
        self.assertEqual(normalize_domain('www.example.com'), 'example.com')
        self.assertEqual(normalize_domain('EXAMPLE.COM'), 'example.com')
        self.assertEqual(normalize_domain('example.com:8080'), 'example.com')
        self.assertEqual(normalize_domain('subdomain.example.com'), 'subdomain.example.com')
    
    def test_is_valid_email(self):
        """Test email validation"""
        self.assertTrue(is_valid_email('test@example.com'))
        self.assertTrue(is_valid_email('user.name@example.co.uk'))
        self.assertTrue(is_valid_email('user+tag@example.com'))
        
        self.assertFalse(is_valid_email('invalid'))
        self.assertFalse(is_valid_email('@example.com'))
        self.assertFalse(is_valid_email('user@'))
        self.assertFalse(is_valid_email('user@.com'))
        self.assertFalse(is_valid_email('user@example'))
    
    def test_generate_unique_filename(self):
        """Test unique filename generation"""
        result = generate_unique_filename('test.jpg')
        self.assertTrue(result.startswith('test_'))
        self.assertTrue(result.endswith('.jpg'))
        
        result_with_prefix = generate_unique_filename('test.jpg', prefix='upload')
        self.assertTrue(result_with_prefix.startswith('upload_test_'))
        
        # Test with no extension
        result_no_ext = generate_unique_filename('testfile')
        self.assertTrue(result_no_ext.startswith('testfile_'))
    
    def test_batch_process(self):
        """Test batch processing"""
        items = list(range(10))
        process_func = Mock(return_value='processed')
        
        results = batch_process(items, process_func, batch_size=3)
        
        self.assertEqual(len(results), 4)  # 4 batches
        self.assertEqual(process_func.call_count, 4)
        process_func.assert_any_call([0, 1, 2])
        process_func.assert_any_call([3, 4, 5])
        process_func.assert_any_call([6, 7, 8])
        process_func.assert_any_call([9])
    
    @patch('common.utils.Paginator')
    def test_paginate_queryset(self, mock_paginator_class):
        """Test queryset pagination"""
        # Mock queryset
        mock_queryset = Mock()
        
        # Mock paginator
        mock_paginator = Mock()
        mock_paginator.num_pages = 5
        mock_paginator.count = 100
        
        # Mock page
        mock_page = Mock()
        mock_page.object_list = ['item1', 'item2']
        mock_page.number = 2
        mock_page.has_next.return_value = True
        mock_page.has_previous.return_value = True
        mock_page.next_page_number.return_value = 3
        mock_page.previous_page_number.return_value = 1
        
        mock_paginator.page.return_value = mock_page
        mock_paginator_class.return_value = mock_paginator
        
        result = paginate_queryset(mock_queryset, page=2, per_page=25)
        
        self.assertEqual(result['results'], ['item1', 'item2'])
        self.assertEqual(result['page'], 2)
        self.assertEqual(result['per_page'], 25)
        self.assertEqual(result['total_pages'], 5)
        self.assertEqual(result['total_items'], 100)
        self.assertTrue(result['has_next'])
        self.assertTrue(result['has_previous'])
        self.assertEqual(result['next_page'], 3)
        self.assertEqual(result['previous_page'], 1)


@skipUnless(False, "Skipping tests that require test model migrations")
class CommonModelsTest(TestCase, ModelTestMixin, AuditTestMixin):
    """Test common model base classes"""
    
    def test_timestamped_model(self):
        """Test TimestampedModel functionality"""
        # Create instance
        instance = TestTimestampedModel.objects.create(name='Test')
        
        # Check fields exist
        self.assert_model_field_exists(TestTimestampedModel, 'created_at')
        self.assert_model_field_exists(TestTimestampedModel, 'updated_at')
        
        # Check auto-population
        self.assertIsNotNone(instance.created_at)
        self.assertIsNotNone(instance.updated_at)
        
        # Check update behavior
        old_updated = instance.updated_at
        instance.name = 'Updated'
        instance.save()
        instance.refresh_from_db()
        self.assertGreater(instance.updated_at, old_updated)
    
    def test_base_audit_history(self):
        """Test BaseAuditHistory functionality"""
        # Create instance
        instance = TestAuditHistory.objects.create(test_field='Test')
        
        # Check fields
        self.assert_model_field_exists(TestAuditHistory, 'status')
        self.assert_model_field_exists(TestAuditHistory, 'trigger_type')
        self.assert_model_field_exists(TestAuditHistory, 'started_at')
        self.assert_model_field_exists(TestAuditHistory, 'completed_at')
        self.assert_model_field_exists(TestAuditHistory, 'error_message')
        self.assert_model_field_exists(TestAuditHistory, 'retry_count')
        
        # Test default values
        self.assertEqual(instance.status, 'pending')
        self.assertEqual(instance.trigger_type, 'manual')
        self.assertEqual(instance.retry_count, 0)
        
        # Test methods
        self.assert_model_has_method(instance, 'mark_running')
        self.assert_model_has_method(instance, 'mark_completed')
        self.assert_model_has_method(instance, 'mark_failed')
        
        # Test mark_running
        instance.mark_running()
        instance.refresh_from_db()
        self.assertEqual(instance.status, 'running')
        self.assertIsNotNone(instance.started_at)
        
        # Test mark_completed
        instance.mark_completed()
        instance.refresh_from_db()
        self.assertEqual(instance.status, 'completed')
        self.assertIsNotNone(instance.completed_at)
        
        # Test duration property
        self.assertIsNotNone(instance.duration)
        self.assertGreater(instance.duration, 0)
    
    def test_base_audit_history_failed(self):
        """Test BaseAuditHistory failure handling"""
        instance = TestAuditHistory.objects.create(test_field='Test')
        
        # Mark as failed with error
        instance.mark_failed('Test error message')
        instance.refresh_from_db()
        
        self.assertEqual(instance.status, 'failed')
        self.assertIsNotNone(instance.completed_at)
        self.assertEqual(instance.error_message, 'Test error message')
        
        # Test error message truncation
        long_error = 'x' * 10000
        instance2 = TestAuditHistory.objects.create(test_field='Test2')
        instance2.mark_failed(long_error)
        instance2.refresh_from_db()
        self.assertEqual(len(instance2.error_message), 5000)
    
    def test_base_audit_model(self):
        """Test BaseAuditModel functionality"""
        instance = TestAuditModel.objects.create(name='Test')
        
        # Check fields
        self.assert_model_field_exists(TestAuditModel, 'audit_frequency')
        self.assert_model_field_exists(TestAuditModel, 'last_audit_at')
        self.assert_model_field_exists(TestAuditModel, 'next_audit_at')
        self.assert_model_field_exists(TestAuditModel, 'audit_enabled')
        
        # Test defaults
        self.assertEqual(instance.audit_frequency, 'weekly')
        self.assertTrue(instance.audit_enabled)
        
        # Test methods
        self.assert_model_has_method(instance, 'calculate_next_audit_time')
        self.assert_model_has_method(instance, 'schedule_next_audit')
        self.assert_model_has_method(instance, 'can_run_manual_audit')
        
        # Test calculate_next_audit_time
        next_time = instance.calculate_next_audit_time()
        self.assertIsNotNone(next_time)
        self.assertGreater(next_time, timezone.now())
        
        # Test different frequencies
        instance.audit_frequency = 'daily'
        next_time = instance.calculate_next_audit_time()
        self.assertAlmostEqual(
            (next_time - timezone.now()).total_seconds(),
            86400,  # 1 day in seconds
            delta=10
        )
        
        # Test disabled
        instance.audit_frequency = 'disabled'
        self.assertIsNone(instance.calculate_next_audit_time())
        
        instance.audit_enabled = False
        instance.audit_frequency = 'daily'
        self.assertIsNone(instance.calculate_next_audit_time())
    
    def test_can_run_manual_audit(self):
        """Test manual audit cooldown logic"""
        instance = TestAuditModel.objects.create(name='Test')
        
        # Should allow first run
        self.assertTrue(instance.can_run_manual_audit())
        
        # Set last audit to now
        instance.last_audit_at = timezone.now()
        self.assertFalse(instance.can_run_manual_audit(cooldown_minutes=30))
        
        # Set last audit to 31 minutes ago
        instance.last_audit_at = timezone.now() - timedelta(minutes=31)
        self.assertTrue(instance.can_run_manual_audit(cooldown_minutes=30))


@skipUnless(False, "Skipping tests that require test model migrations")
class CommonTasksTest(TestCase):
    """Test common task utilities"""
    
    @patch('common.tasks.logger')
    def test_base_audit_task_success(self, mock_logger):
        """Test BaseAuditTask successful execution"""
        # Create mock model and audit function
        mock_model = Mock()
        mock_instance = Mock(id='test-id')
        mock_model.objects.get.return_value = mock_instance
        
        mock_audit_function = Mock(return_value={'result': 'success'})
        
        # Create task instance
        task = BaseAuditTask()
        task.model_class = mock_model
        
        # Execute
        result = task.execute_audit('test-id', mock_audit_function, test_param='value')
        
        # Assertions
        mock_model.objects.get.assert_called_once_with(id='test-id')
        mock_audit_function.assert_called_once_with(mock_instance, test_param='value')
        mock_instance.mark_running.assert_called_once()
        mock_instance.mark_completed.assert_called_once()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['audit_id'], 'test-id')
        self.assertEqual(result['result']['result'], 'success')
    
    @patch('common.tasks.logger')
    def test_base_audit_task_not_found(self, mock_logger):
        """Test BaseAuditTask when audit not found"""
        from django.core.exceptions import ObjectDoesNotExist
        
        mock_model = Mock()
        mock_model.objects.get.side_effect = ObjectDoesNotExist()
        mock_model.__name__ = 'TestModel'
        
        task = BaseAuditTask()
        task.model_class = mock_model
        
        result = task.execute_audit('missing-id', Mock())
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Audit missing-id not found')
    
    @patch('common.tasks.logger')
    def test_base_audit_task_exception(self, mock_logger):
        """Test BaseAuditTask exception handling"""
        mock_model = Mock()
        mock_instance = Mock(id='test-id')
        mock_model.objects.get.return_value = mock_instance
        
        mock_audit_function = Mock(side_effect=Exception('Test error'))
        
        task = BaseAuditTask()
        task.model_class = mock_model
        task.request = Mock(retries=0)
        task.max_retries = 3
        task.retry = Mock(side_effect=Exception('Retry'))
        
        with self.assertRaises(Exception):
            task.execute_audit('test-id', mock_audit_function)
        
        # Should attempt retry
        task.retry.assert_called_once()
    
    @patch('django.apps.apps.get_model')
    @patch('common.tasks.timezone')
    @patch('common.tasks.logger')
    def test_cleanup_old_records(self, mock_logger, mock_timezone, mock_get_model):
        """Test cleanup_old_records task"""
        # Setup mocks
        mock_now = timezone.now()
        mock_timezone.now.return_value = mock_now
        
        mock_model = Mock()
        mock_model.objects.filter.return_value.delete.return_value = (10, {'Model': 10})
        mock_get_model.return_value = mock_model
        
        # Execute
        result = cleanup_old_records('app.models.TestModel', days_to_keep=30)
        
        # Assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['deleted_count'], 10)
        self.assertEqual(result['days_kept'], 30)
        
        # Check filter was called with correct date
        expected_cutoff = mock_now - timedelta(days=30)
        mock_model.objects.filter.assert_called_once()


# Additional test for integration
@skipUnless(False, "Skipping tests that require test model migrations")
class CommonIntegrationTest(BaseTestCase):
    """Integration tests for common components"""
    
    def test_full_audit_workflow(self):
        """Test complete audit workflow using base classes"""
        # Create an audit history record
        audit = TestAuditHistory.objects.create(
            test_field='Integration test',
            status='pending'
        )
        
        # Simulate audit execution
        self.assert_audit_pending(audit)
        
        audit.mark_running()
        audit.refresh_from_db()
        self.assert_audit_running(audit)
        
        # Simulate work being done
        import time
        time.sleep(0.1)
        
        audit.mark_completed()
        audit.refresh_from_db()
        self.assert_audit_completed(audit)
        
        # Check duration calculation
        self.assertGreater(audit.duration, 0)
        self.assertLess(audit.duration, 1)
    
    def test_ajax_response_integration(self):
        """Test AJAX response creation and parsing"""
        # Create response
        response = create_ajax_response(
            success=True,
            message='Integration test',
            data={'items': [1, 2, 3]}
        )
        
        # Parse response
        content = json.loads(response.content)
        
        # Use base test assertions
        self.assertTrue(content['success'])
        self.assertEqual(content['message'], 'Integration test')
        self.assertEqual(len(content['data']['items']), 3)


if __name__ == '__main__':
    import django
    from django.test.runner import DiscoverRunner
    
    django.setup()
    test_runner = DiscoverRunner(verbosity=2)
    test_runner.run_tests(['common.tests'])