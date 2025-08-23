from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Project
from .admin import ProjectAdminForm

User = get_user_model()


class ProjectModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_project_creation(self):
        """Test basic project creation"""
        project = Project.objects.create(
            user=self.user,
            domain='example.com',
            title='Test Project',
            active=True
        )
        self.assertEqual(project.domain, 'example.com')
        self.assertEqual(project.title, 'Test Project')
        self.assertTrue(project.active)
        self.assertEqual(project.user, self.user)

    def test_project_str_method(self):
        """Test string representation of project"""
        project = Project.objects.create(
            user=self.user,
            domain='example.com',
            title='Test Project'
        )
        expected = 'example.com - Test Project'
        self.assertEqual(str(project), expected)

    def test_project_str_without_title(self):
        """Test string representation without title"""
        project = Project.objects.create(
            user=self.user,
            domain='example.com'
        )
        expected = 'example.com - Untitled'
        self.assertEqual(str(project), expected)

    def test_project_default_active(self):
        """Test project active field defaults to True"""
        project = Project.objects.create(
            user=self.user,
            domain='example.com'
        )
        self.assertTrue(project.active)

    def test_get_favicon_url_default_size(self):
        """Test Google favicon URL generation with default size"""
        project = Project.objects.create(
            user=self.user,
            domain='google.com'
        )
        expected_url = 'https://www.google.com/s2/favicons?domain=google.com&sz=64'
        self.assertEqual(project.get_favicon_url(), expected_url)

    def test_get_favicon_url_custom_size(self):
        """Test Google favicon URL generation with custom size"""
        project = Project.objects.create(
            user=self.user,
            domain='github.com'
        )
        expected_url = 'https://www.google.com/s2/favicons?domain=github.com&sz=32'
        self.assertEqual(project.get_favicon_url(32), expected_url)

    def test_get_favicon_url_subdomain(self):
        """Test Google favicon URL generation for subdomains"""
        project = Project.objects.create(
            user=self.user,
            domain='api.github.com'
        )
        expected_url = 'https://www.google.com/s2/favicons?domain=api.github.com&sz=64'
        self.assertEqual(project.get_favicon_url(), expected_url)

    def test_get_favicon_url_various_sizes(self):
        """Test Google favicon URL generation with various sizes"""
        project = Project.objects.create(
            user=self.user,
            domain='example.com'
        )
        
        test_cases = [16, 32, 64, 128, 256]
        for size in test_cases:
            with self.subTest(size=size):
                expected_url = f'https://www.google.com/s2/favicons?domain=example.com&sz={size}'
                self.assertEqual(project.get_favicon_url(size), expected_url)

    def test_get_cached_favicon_url_default_size(self):
        """Test cached favicon URL generation with default size"""
        project = Project.objects.create(
            user=self.user,
            domain='github.com'
        )
        from django.urls import reverse
        expected_url = reverse('project:favicon_proxy', kwargs={'domain': 'github.com'}) + '?size=64'
        self.assertEqual(project.get_cached_favicon_url(), expected_url)

    def test_get_cached_favicon_url_custom_size(self):
        """Test cached favicon URL generation with custom size"""
        project = Project.objects.create(
            user=self.user,
            domain='stackoverflow.com'
        )
        from django.urls import reverse
        expected_url = reverse('project:favicon_proxy', kwargs={'domain': 'stackoverflow.com'}) + '?size=32'
        self.assertEqual(project.get_cached_favicon_url(32), expected_url)


class ProjectAdminFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.form_data = {
            'user': self.user.id,
            'title': 'Test Project',
            'active': True
        }

    def test_valid_domain_cases(self):
        """Test valid domain cases"""
        valid_domains = [
            'example.com',
            'subdomain.example.com',
            'deep.sub.domain.example.com',
            'test-site.example.com',
            'site123.example.com',
            'a.b.c.example.com',
            'google.com',
            'api.github.com'
        ]
        
        for domain in valid_domains:
            with self.subTest(domain=domain):
                self.form_data['domain'] = domain
                form = ProjectAdminForm(data=self.form_data)
                self.assertTrue(form.is_valid(), f"Domain '{domain}' should be valid. Errors: {form.errors}")
                self.assertEqual(form.cleaned_data['domain'], domain)

    def test_protocol_and_www_removal(self):
        """Test automatic removal of http://, https:// protocols and www. prefix"""
        test_cases = [
            ('http://example.com', 'example.com'),
            ('https://example.com', 'example.com'),
            ('HTTP://EXAMPLE.COM', 'example.com'),
            ('HTTPS://EXAMPLE.COM', 'example.com'),
            ('https://subdomain.example.com', 'subdomain.example.com'),
            ('http://www.google.com/', 'google.com'),
            ('https://www.example.com/', 'example.com'),
            ('www.github.com', 'github.com'),
            ('WWW.EXAMPLE.COM', 'example.com'),
            ('https://www.subdomain.example.com/', 'subdomain.example.com'),
            ('https://api.github.com/', 'api.github.com')
        ]
        
        for input_domain, expected_domain in test_cases:
            with self.subTest(input=input_domain, expected=expected_domain):
                self.form_data['domain'] = input_domain
                form = ProjectAdminForm(data=self.form_data)
                self.assertTrue(form.is_valid(), f"Domain '{input_domain}' should be valid. Errors: {form.errors}")
                self.assertEqual(form.cleaned_data['domain'], expected_domain)

    def test_invalid_single_words(self):
        """Test rejection of single words including localhost"""
        invalid_domains = [
            'localhost',
            'sss',
            'test',
            'admin',
            'api',
            'www',
            'subdomain'
        ]
        
        for domain in invalid_domains:
            with self.subTest(domain=domain):
                self.form_data['domain'] = domain
                form = ProjectAdminForm(data=self.form_data)
                self.assertFalse(form.is_valid(), f"Domain '{domain}' should be invalid")
                self.assertIn('must contain at least one dot', str(form.errors['domain']))

    def test_invalid_special_characters(self):
        """Test rejection of domains with invalid special characters"""
        invalid_domains = [
            'example@domain.com',
            'example#domain.com',
            'example$domain.com',
            'example%domain.com',
            'example&domain.com',
            'example*domain.com',
            'example+domain.com',
            'example=domain.com',
            'example?domain.com',
            'example[domain.com',
            'example]domain.com',
            'example{domain.com',
            'example}domain.com',
            'example|domain.com',
            'example\\domain.com',
            'example/domain.com',
            'example:domain.com',
            'example;domain.com',
            'example<domain.com',
            'example>domain.com',
            'example domain.com',  # space
            'exämple.com',  # unicode characters
            'example.cöm'   # unicode characters
        ]
        
        for domain in invalid_domains:
            with self.subTest(domain=domain):
                self.form_data['domain'] = domain
                form = ProjectAdminForm(data=self.form_data)
                self.assertFalse(form.is_valid(), f"Domain '{domain}' should be invalid")
                self.assertIn('invalid characters', str(form.errors['domain']))

    def test_invalid_dot_positions(self):
        """Test rejection of domains with invalid dot positions"""
        invalid_domains = [
            '.example.com',      # starts with dot
            'example.com.',      # ends with dot
            'example..com',      # consecutive dots
            '.example..com.',    # multiple issues
        ]
        
        for domain in invalid_domains:
            with self.subTest(domain=domain):
                self.form_data['domain'] = domain
                form = ProjectAdminForm(data=self.form_data)
                self.assertFalse(form.is_valid(), f"Domain '{domain}' should be invalid")

    def test_invalid_hyphen_positions(self):
        """Test rejection of domains with invalid hyphen positions"""
        invalid_domains = [
            '-example.com',      # starts with hyphen
            'example.com-',      # ends with hyphen
            'sub-.example.com',  # part ends with hyphen
            '-sub.example.com',  # part starts with hyphen
        ]
        
        for domain in invalid_domains:
            with self.subTest(domain=domain):
                self.form_data['domain'] = domain
                form = ProjectAdminForm(data=self.form_data)
                self.assertFalse(form.is_valid(), f"Domain '{domain}' should be invalid")

    def test_empty_domain(self):
        """Test rejection of empty domain"""
        self.form_data['domain'] = ''
        form = ProjectAdminForm(data=self.form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('domain', form.errors)

    def test_case_conversion(self):
        """Test that domains are converted to lowercase"""
        test_cases = [
            ('EXAMPLE.COM', 'example.com'),
            ('SubDomain.Example.COM', 'subdomain.example.com'),
            ('HTTP://EXAMPLE.COM', 'example.com'),
            ('HTTPS://WWW.GOOGLE.COM/', 'google.com')
        ]
        
        for input_domain, expected_domain in test_cases:
            with self.subTest(input=input_domain, expected=expected_domain):
                self.form_data['domain'] = input_domain
                form = ProjectAdminForm(data=self.form_data)
                self.assertTrue(form.is_valid(), f"Domain '{input_domain}' should be valid")
                self.assertEqual(form.cleaned_data['domain'], expected_domain)

    def test_trailing_slash_removal(self):
        """Test automatic removal of trailing slashes"""
        test_cases = [
            ('example.com/', 'example.com'),
            ('subdomain.example.com/', 'subdomain.example.com'),
            ('example.com///', 'example.com')
        ]
        
        for input_domain, expected_domain in test_cases:
            with self.subTest(input=input_domain, expected=expected_domain):
                self.form_data['domain'] = input_domain
                form = ProjectAdminForm(data=self.form_data)
                self.assertTrue(form.is_valid(), f"Domain '{input_domain}' should be valid")
                self.assertEqual(form.cleaned_data['domain'], expected_domain)

    def test_form_with_missing_user(self):
        """Test form validation with missing user"""
        form_data = {
            'domain': 'example.com',
            'title': 'Test Project',
            'active': True
        }
        form = ProjectAdminForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('user', form.errors)

    def test_form_with_optional_title(self):
        """Test form validation with optional title"""
        self.form_data['domain'] = 'example.com'
        self.form_data.pop('title', None)  # Remove title
        form = ProjectAdminForm(data=self.form_data)
        self.assertTrue(form.is_valid())
        # Title field allows null/blank, so it returns None when not provided
        self.assertIsNone(form.cleaned_data['title'])

    def test_very_long_domain(self):
        """Test rejection of very long domains"""
        # Domain longer than 253 characters (DNS limit)
        long_domain = 'a' * 60 + '.' + 'b' * 60 + '.' + 'c' * 60 + '.' + 'd' * 60 + '.' + 'e' * 60 + '.com'
        self.form_data['domain'] = long_domain
        form = ProjectAdminForm(data=self.form_data)
        # This should be caught by the max_length=255 on the model field
        # but we test the regex validation here
        if len(long_domain) <= 255:
            # If it's within model limits, test regex behavior
            is_valid = form.is_valid()
            # Very long domains might still pass regex but fail at DNS level
            # This test documents current behavior
        else:
            self.assertFalse(form.is_valid())


class GoogleFaviconTest(TestCase):
    """Test Google favicon service integration"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_google_favicon_url_format(self):
        """Test that Google favicon URLs are formatted correctly"""
        project = Project.objects.create(
            user=self.user,
            domain='google.com'
        )
        
        # Test default size (64px)
        url = project.get_favicon_url()
        self.assertEqual(url, 'https://www.google.com/s2/favicons?domain=google.com&sz=64')
        
        # Test custom sizes
        for size in [16, 32, 64, 128]:
            with self.subTest(size=size):
                url = project.get_favicon_url(size)
                expected = f'https://www.google.com/s2/favicons?domain=google.com&sz={size}'
                self.assertEqual(url, expected)

    def test_google_favicon_with_subdomain(self):
        """Test Google favicon URL for subdomains"""
        project = Project.objects.create(
            user=self.user,
            domain='mail.google.com'
        )
        
        url = project.get_favicon_url()
        self.assertEqual(url, 'https://www.google.com/s2/favicons?domain=mail.google.com&sz=64')

    def test_google_favicon_with_special_domains(self):
        """Test Google favicon URL for various domain types"""
        test_domains = [
            'github.com',
            'api.github.com',
            'docs.python.org',
            'stackoverflow.com',
            'en.wikipedia.org',
        ]
        
        for domain in test_domains:
            with self.subTest(domain=domain):
                project = Project.objects.create(
                    user=self.user,
                    domain=domain
                )
                url = project.get_favicon_url()
                expected = f'https://www.google.com/s2/favicons?domain={domain}&sz=64'
                self.assertEqual(url, expected)

    def test_google_favicon_service_availability(self):
        """Test that Google favicon service returns valid responses"""
        import requests
        
        # Test a few well-known domains
        test_domains = ['google.com', 'github.com', 'stackoverflow.com']
        
        for domain in test_domains:
            with self.subTest(domain=domain):
                try:
                    project = Project.objects.create(
                        user=self.user,
                        domain=domain
                    )
                    favicon_url = project.get_favicon_url(32)  # Use smaller size for faster testing
                    
                    # Make actual request to Google's favicon service
                    response = requests.get(favicon_url, timeout=5)
                    
                    # Should return a successful response
                    self.assertEqual(response.status_code, 200)
                    
                    # Should return an image (check Content-Type)
                    content_type = response.headers.get('Content-Type', '')
                    self.assertTrue(
                        content_type.startswith('image/'),
                        f"Expected image content type for {domain}, got {content_type}"
                    )
                    
                    # Should have some content
                    self.assertGreater(len(response.content), 0)
                    
                except requests.RequestException:
                    # Skip test if network is not available
                    self.skipTest(f"Network test skipped for {domain}")

    def test_favicon_url_caching_behavior(self):
        """Test that favicon URLs are generated consistently"""
        project = Project.objects.create(
            user=self.user,
            domain='example.com'
        )
        
        # Generate URL multiple times
        url1 = project.get_favicon_url()
        url2 = project.get_favicon_url()
        url3 = project.get_favicon_url(64)  # Same size as default
        
        # All should be identical
        self.assertEqual(url1, url2)
        self.assertEqual(url1, url3)
        
        # Different sizes should be different
        url_small = project.get_favicon_url(16)
        url_large = project.get_favicon_url(128)
        
        self.assertNotEqual(url1, url_small)
        self.assertNotEqual(url1, url_large)
        self.assertNotEqual(url_small, url_large)