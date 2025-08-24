from django.test import TestCase, TransactionTestCase
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.core.management import call_command
from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from io import StringIO
import json

from .models import SiteConfiguration
from .admin import SiteConfigurationAdmin

User = get_user_model()


class SiteConfigurationModelTest(TestCase):
    """Test cases for SiteConfiguration model"""
    
    def setUp(self):
        """Set up test data"""
        cache.clear()
        
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
        SiteConfiguration.objects.all().delete()
    
    def test_create_string_config(self):
        """Test creating a string configuration"""
        config = SiteConfiguration.objects.create(
            key='site_name',
            value='Test Site',
            value_type='str',
            description='The name of the site'
        )
        self.assertEqual(config.key, 'site_name')
        self.assertEqual(config.value, 'Test Site')
        self.assertEqual(config.get_value(), 'Test Site')
        self.assertIsInstance(config.get_value(), str)
    
    def test_create_integer_config(self):
        """Test creating an integer configuration"""
        config = SiteConfiguration.objects.create(
            key='max_users',
            value='100',
            value_type='int',
            description='Maximum number of users'
        )
        self.assertEqual(config.get_value(), 100)
        self.assertIsInstance(config.get_value(), int)
    
    def test_create_float_config(self):
        """Test creating a float configuration"""
        config = SiteConfiguration.objects.create(
            key='tax_rate',
            value='0.15',
            value_type='float',
            description='Tax rate'
        )
        self.assertEqual(config.get_value(), 0.15)
        self.assertIsInstance(config.get_value(), float)
    
    def test_create_boolean_config(self):
        """Test creating boolean configurations with various inputs"""
        test_cases = [
            ('true', True),
            ('false', False),
            ('1', True),
            ('0', False),
            ('yes', True),
            ('no', False),
            ('TRUE', True),
            ('FALSE', False),
        ]
        
        for value_str, expected in test_cases:
            with self.subTest(value=value_str):
                config = SiteConfiguration.objects.create(
                    key=f'bool_test_{value_str}',
                    value=value_str,
                    value_type='bool'
                )
                self.assertEqual(config.get_value(), expected)
                self.assertIsInstance(config.get_value(), bool)
    
    def test_create_json_config(self):
        """Test creating a JSON configuration"""
        json_data = {'api_key': 'secret', 'endpoints': ['api1', 'api2']}
        config = SiteConfiguration.objects.create(
            key='api_settings',
            value=json.dumps(json_data),
            value_type='json',
            description='API settings'
        )
        self.assertEqual(config.get_value(), json_data)
        self.assertIsInstance(config.get_value(), dict)
    
    def test_unique_key_constraint(self):
        """Test that keys must be unique"""
        SiteConfiguration.objects.create(
            key='unique_key',
            value='value1',
            value_type='str'
        )
        
        with self.assertRaises(Exception):
            SiteConfiguration.objects.create(
                key='unique_key',
                value='value2',
                value_type='str'
            )
    
    def test_invalid_integer_validation(self):
        """Test validation for invalid integer values"""
        config = SiteConfiguration(
            key='invalid_int',
            value='not_a_number',
            value_type='int'
        )
        with self.assertRaises(ValidationError):
            config.full_clean()
    
    def test_invalid_float_validation(self):
        """Test validation for invalid float values"""
        config = SiteConfiguration(
            key='invalid_float',
            value='not_a_float',
            value_type='float'
        )
        with self.assertRaises(ValidationError):
            config.full_clean()
    
    def test_invalid_boolean_validation(self):
        """Test validation for invalid boolean values"""
        config = SiteConfiguration(
            key='invalid_bool',
            value='maybe',
            value_type='bool'
        )
        with self.assertRaises(ValidationError):
            config.full_clean()
    
    def test_invalid_json_validation(self):
        """Test validation for invalid JSON values"""
        config = SiteConfiguration(
            key='invalid_json',
            value='{"invalid": json}',
            value_type='json'
        )
        with self.assertRaises(ValidationError):
            config.full_clean()
    
    def test_sensitive_value_display(self):
        """Test that sensitive values are hidden in string representation"""
        config = SiteConfiguration.objects.create(
            key='api_secret',
            value='super_secret_key',
            value_type='str',
            is_sensitive=True
        )
        self.assertIn('[HIDDEN]', str(config))
        self.assertNotIn('super_secret_key', str(config))
    
    def test_long_value_truncation_in_display(self):
        """Test that long values are truncated in string representation"""
        long_value = 'a' * 100
        config = SiteConfiguration.objects.create(
            key='long_value',
            value=long_value,
            value_type='str',
            is_sensitive=False
        )
        str_repr = str(config)
        self.assertIn('...', str_repr)
        self.assertLess(len(str_repr), len(long_value))


class SiteConfigurationClassMethodsTest(TestCase):
    """Test class methods for SiteConfiguration"""
    
    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
        SiteConfiguration.objects.all().delete()
    
    def test_get_config_existing(self):
        """Test getting an existing configuration"""
        SiteConfiguration.objects.create(
            key='test_key',
            value='test_value',
            value_type='str'
        )
        
        value = SiteConfiguration.get_config('test_key')
        self.assertEqual(value, 'test_value')
    
    def test_get_config_non_existing_with_default(self):
        """Test getting a non-existing configuration with default"""
        value = SiteConfiguration.get_config('non_existing', default='default_value')
        self.assertEqual(value, 'default_value')
    
    def test_get_config_non_existing_without_default(self):
        """Test getting a non-existing configuration without default"""
        value = SiteConfiguration.get_config('non_existing')
        self.assertIsNone(value)
    
    def test_set_config_create(self):
        """Test creating a new configuration with set_config"""
        config = SiteConfiguration.set_config(
            'new_key',
            'new_value',
            value_type='str',
            description='Test description'
        )
        
        self.assertEqual(config.key, 'new_key')
        self.assertEqual(config.value, 'new_value')
        self.assertEqual(config.description, 'Test description')
    
    def test_set_config_update(self):
        """Test updating an existing configuration with set_config"""
        # Create initial config
        SiteConfiguration.objects.create(
            key='update_key',
            value='old_value',
            value_type='str'
        )
        
        # Update it
        config = SiteConfiguration.set_config(
            'update_key',
            'new_value',
            value_type='str',
            description='Updated description'
        )
        
        self.assertEqual(config.value, 'new_value')
        self.assertEqual(config.description, 'Updated description')
        
        # Verify only one instance exists
        self.assertEqual(SiteConfiguration.objects.filter(key='update_key').count(), 1)
    
    def test_set_config_json_conversion(self):
        """Test that set_config properly converts JSON data"""
        data = {'key': 'value', 'list': [1, 2, 3]}
        config = SiteConfiguration.set_config(
            'json_key',
            data,
            value_type='json'
        )
        
        # Value should be stored as string
        self.assertIsInstance(config.value, str)
        # But get_value should return dict
        self.assertEqual(config.get_value(), data)
    
    def test_bulk_get(self):
        """Test getting multiple configurations at once"""
        # Create test configs
        SiteConfiguration.objects.create(key='key1', value='value1', value_type='str')
        SiteConfiguration.objects.create(key='key2', value='100', value_type='int')
        SiteConfiguration.objects.create(key='key3', value='true', value_type='bool')
        
        result = SiteConfiguration.bulk_get(['key1', 'key2', 'key3', 'non_existing'])
        
        self.assertEqual(result['key1'], 'value1')
        self.assertEqual(result['key2'], 100)
        self.assertEqual(result['key3'], True)
        self.assertIsNone(result['non_existing'])


class SiteConfigurationCacheTest(TestCase):
    """Test caching functionality"""
    
    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
        SiteConfiguration.objects.all().delete()
    
    def test_cache_on_get_config(self):
        """Test that get_config uses cache"""
        config = SiteConfiguration.objects.create(
            key='cache_test',
            value='cached_value',
            value_type='str'
        )
        
        # First call should set cache
        value1 = SiteConfiguration.get_config('cache_test')
        
        # Modify database directly (bypassing save method which clears cache)
        SiteConfiguration.objects.filter(key='cache_test').update(value='new_value')
        
        # Second call should return cached value
        value2 = SiteConfiguration.get_config('cache_test')
        self.assertEqual(value2, 'cached_value')
        
        # Without cache should return new value
        value3 = SiteConfiguration.get_config('cache_test', use_cache=False)
        self.assertEqual(value3, 'new_value')
    
    def test_cache_cleared_on_save(self):
        """Test that cache is cleared when configuration is saved"""
        config = SiteConfiguration.objects.create(
            key='cache_clear_test',
            value='initial_value',
            value_type='str'
        )
        
        # Get value (sets cache)
        value1 = SiteConfiguration.get_config('cache_clear_test')
        self.assertEqual(value1, 'initial_value')
        
        # Update through model save (should clear cache)
        config.value = 'updated_value'
        config.save()
        
        # Get value again (should not be cached)
        value2 = SiteConfiguration.get_config('cache_clear_test')
        self.assertEqual(value2, 'updated_value')
    
    def test_cache_key_format(self):
        """Test that cache keys are properly formatted"""
        config = SiteConfiguration.objects.create(
            key='format_test',
            value='test_value',
            value_type='str'
        )
        
        # Get value to set cache
        SiteConfiguration.get_config('format_test')
        
        # Check cache directly
        cache_key = 'siteconfig_format_test'
        cached_value = cache.get(cache_key)
        self.assertEqual(cached_value, 'test_value')


class SeedConfigManagementCommandTest(TransactionTestCase):
    """Test the seed_config management command"""
    
    def setUp(self):
        """Clear data before each test"""
        SiteConfiguration.objects.all().delete()
        cache.clear()
    
    def test_seed_command_creates_configs(self):
        """Test that seed command creates the required configurations"""
        out = StringIO()
        call_command('seed_config', stdout=out)
        
        # Check configurations were created
        sync_config = SiteConfiguration.objects.get(key='KEYWORD_RE_SYNC_TIME')
        self.assertEqual(sync_config.get_value(), 1320)
        self.assertEqual(sync_config.value_type, 'int')
        
        crawl_config = SiteConfiguration.objects.get(key='KEYWORD_RE_CRAWL_HOUR_AFTER')
        self.assertEqual(crawl_config.get_value(), 60)
        self.assertEqual(crawl_config.value_type, 'int')
        
        # Check output
        output = out.getvalue()
        self.assertIn('Created: KEYWORD_RE_SYNC_TIME', output)
        self.assertIn('Created: KEYWORD_RE_CRAWL_HOUR_AFTER', output)
        self.assertIn('successfully', output)
    
    def test_seed_command_updates_existing(self):
        """Test that seed command updates existing configurations"""
        # Create existing config with different value
        SiteConfiguration.objects.create(
            key='KEYWORD_RE_SYNC_TIME',
            value='999',
            value_type='int'
        )
        
        out = StringIO()
        call_command('seed_config', stdout=out)
        
        # Check configuration was updated
        sync_config = SiteConfiguration.objects.get(key='KEYWORD_RE_SYNC_TIME')
        self.assertEqual(sync_config.get_value(), 1320)
        
        # Check output shows update
        output = out.getvalue()
        self.assertIn('Updated: KEYWORD_RE_SYNC_TIME', output)
    
    def test_seed_command_removes_other_configs(self):
        """Test that seed command removes other configurations"""
        # Create some other configs
        SiteConfiguration.objects.create(
            key='OTHER_CONFIG_1',
            value='value1',
            value_type='str'
        )
        SiteConfiguration.objects.create(
            key='OTHER_CONFIG_2',
            value='value2',
            value_type='str'
        )
        
        out = StringIO()
        call_command('seed_config', stdout=out)
        
        # Check other configs were removed
        self.assertFalse(SiteConfiguration.objects.filter(key='OTHER_CONFIG_1').exists())
        self.assertFalse(SiteConfiguration.objects.filter(key='OTHER_CONFIG_2').exists())
        
        # Check only seed configs exist
        self.assertEqual(SiteConfiguration.objects.count(), 2)
        self.assertTrue(SiteConfiguration.objects.filter(key='KEYWORD_RE_SYNC_TIME').exists())
        self.assertTrue(SiteConfiguration.objects.filter(key='KEYWORD_RE_CRAWL_HOUR_AFTER').exists())
        
        # Check output mentions removal
        output = out.getvalue()
        self.assertIn('Removed 2 other configuration(s)', output)
    
    def test_seed_command_idempotent(self):
        """Test that running seed command multiple times is safe"""
        # Run twice
        call_command('seed_config', stdout=StringIO())
        call_command('seed_config', stdout=StringIO())
        
        # Should still have exactly 2 configs
        self.assertEqual(SiteConfiguration.objects.count(), 2)
        
        # Values should be correct
        sync_time = SiteConfiguration.get_config('KEYWORD_RE_SYNC_TIME')
        crawl_hour = SiteConfiguration.get_config('KEYWORD_RE_CRAWL_HOUR_AFTER')
        
        self.assertEqual(sync_time, 1320)
        self.assertEqual(crawl_hour, 60)


class SiteConfigurationAdminTest(TestCase):
    """Test admin interface for SiteConfiguration"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='testpass123'
        )
        self.client.login(username='admin', password='testpass123')
        
        # Create test configuration
        self.config = SiteConfiguration.objects.create(
            key='admin_test',
            value='test_value',
            value_type='str',
            description='Test configuration for admin'
        )
        
        self.sensitive_config = SiteConfiguration.objects.create(
            key='sensitive_test',
            value='secret_value',
            value_type='str',
            is_sensitive=True
        )
    
    def test_admin_list_display(self):
        """Test that admin list view displays correctly"""
        url = reverse('admin:siteconfig_siteconfiguration_changelist')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'admin_test')
        self.assertContains(response, 'test_value')
        
        # Sensitive value should be hidden
        self.assertContains(response, 'sensitive_test')
        self.assertContains(response, '[HIDDEN]')
        self.assertNotContains(response, 'secret_value')
    
    def test_admin_search(self):
        """Test admin search functionality"""
        url = reverse('admin:siteconfig_siteconfiguration_changelist')
        response = self.client.get(url, {'q': 'admin_test'})
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'admin_test')
        self.assertNotContains(response, 'sensitive_test')
    
    def test_admin_filter(self):
        """Test admin filter functionality"""
        url = reverse('admin:siteconfig_siteconfiguration_changelist')
        
        # Filter by value_type
        response = self.client.get(url, {'value_type': 'str'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'admin_test')
        
        # Filter by is_sensitive
        response = self.client.get(url, {'is_sensitive__exact': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'sensitive_test')
        self.assertNotContains(response, 'admin_test')
    
    def test_value_display_method(self):
        """Test the value_display method in admin"""
        admin = SiteConfigurationAdmin(SiteConfiguration, site)
        
        # Test normal value
        normal_config = SiteConfiguration(
            key='test',
            value='short_value',
            is_sensitive=False
        )
        self.assertEqual(admin.value_display(normal_config), 'short_value')
        
        # Test long value
        long_config = SiteConfiguration(
            key='test',
            value='a' * 60,
            is_sensitive=False
        )
        display = admin.value_display(long_config)
        self.assertIn('...', display)
        self.assertEqual(len(display), 53)  # 50 chars + '...'
        
        # Test sensitive value
        sensitive_config = SiteConfiguration(
            key='test',
            value='secret',
            is_sensitive=True
        )
        self.assertEqual(admin.value_display(sensitive_config), '[HIDDEN]')


class SiteConfigurationIntegrationTest(TestCase):
    """Integration tests for the complete workflow"""
    
    def setUp(self):
        """Set up test data"""
        cache.clear()
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
        SiteConfiguration.objects.all().delete()
    
    def test_keyword_configs_workflow(self):
        """Test the complete workflow for keyword configurations"""
        # Seed the configurations
        call_command('seed_config', stdout=StringIO())
        
        # Retrieve configurations
        sync_time = SiteConfiguration.get_config('KEYWORD_RE_SYNC_TIME')
        crawl_hour = SiteConfiguration.get_config('KEYWORD_RE_CRAWL_HOUR_AFTER')
        
        # Verify values and types
        self.assertEqual(sync_time, 1320)
        self.assertIsInstance(sync_time, int)
        
        self.assertEqual(crawl_hour, 60)
        self.assertIsInstance(crawl_hour, int)
        
        # Test calculations with the values
        total_minutes = sync_time + (crawl_hour * 60)
        self.assertEqual(total_minutes, 1320 + 3600)  # 4920 minutes
        
        # Update a value
        SiteConfiguration.set_config('KEYWORD_RE_SYNC_TIME', 2000, value_type='int')
        
        # Verify update
        new_sync_time = SiteConfiguration.get_config('KEYWORD_RE_SYNC_TIME')
        self.assertEqual(new_sync_time, 2000)
        
        # Test bulk get
        configs = SiteConfiguration.bulk_get([
            'KEYWORD_RE_SYNC_TIME',
            'KEYWORD_RE_CRAWL_HOUR_AFTER'
        ])
        
        self.assertEqual(configs['KEYWORD_RE_SYNC_TIME'], 2000)
        self.assertEqual(configs['KEYWORD_RE_CRAWL_HOUR_AFTER'], 60)
