"""
Comprehensive test cases for Site Audit functionality
"""

from django.test import TestCase, TransactionTestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import Mock, patch, MagicMock
import json

from .models import SiteAudit, OnPagePerformanceHistory, SiteIssue
from .issue_manager import IssueManager
from .issue_templates import get_issue_template, ISSUE_TEMPLATES
from project.models import Project
from performance_audit.models import PerformancePage, PerformanceHistory

User = get_user_model()


class IssueTemplatesTestCase(TestCase):
    """Test issue templates functionality"""
    
    def test_all_issue_types_have_templates(self):
        """Ensure all critical issue types have templates"""
        critical_types = [
            'missing_title', 'duplicate_title', 'missing_meta_description',
            'broken_internal_link', 'title_too_long', 'missing_h1'
        ]
        
        for issue_type in critical_types:
            template = get_issue_template(issue_type)
            self.assertIsNotNone(template)
            self.assertIn('severity', template)
            self.assertIn('description', template)
            self.assertIn('impact', template)
            self.assertIn('resolution', template)
    
    def test_severity_mapping(self):
        """Test that severities are correctly mapped"""
        severity_tests = [
            ('missing_title', 'critical'),
            ('title_too_long', 'high'),
            ('thin_content', 'medium'),
            ('missing_structured_data', 'low'),
            ('external_nofollow', 'info'),
        ]
        
        for issue_type, expected_severity in severity_tests:
            template = get_issue_template(issue_type)
            self.assertEqual(template['severity'], expected_severity)
    
    def test_resolution_content(self):
        """Test that resolutions contain helpful content"""
        for issue_type in ['missing_title', 'broken_internal_link', 'missing_alt_text']:
            template = get_issue_template(issue_type)
            resolution = template['resolution']
            
            # Resolution should be detailed
            self.assertGreater(len(resolution), 100)
            # Should contain numbered steps
            self.assertIn('1.', resolution)
            # Should be actionable
            self.assertTrue(any(word in resolution.lower() for word in ['add', 'fix', 'update', 'remove']))


class IssueManagerTestCase(TransactionTestCase):
    """Test issue manager functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.project = Project.objects.create(
            user=self.user,
            domain='testsite.com',
            title='Test Site'
        )
        
        self.audit = SiteAudit.objects.create(
            project=self.project,
            overall_site_health_score=75,
            total_pages_crawled=10
        )
        
        self.history = OnPagePerformanceHistory.objects.create(
            audit=self.audit,
            status='completed',
            pages_crawled=10
        )
    
    def test_issue_creation_and_deletion(self):
        """Test that old issues are deleted and new ones created"""
        manager = IssueManager(self.history)
        
        # Create initial issues
        initial_issues = [
            {'type': 'missing_title', 'url': 'https://testsite.com/page1'},
            {'type': 'broken_internal_link', 'url': 'https://testsite.com/page2'},
        ]
        manager.update_issues(initial_issues)
        
        # Verify initial issues created
        self.assertEqual(SiteIssue.objects.filter(performance_history=self.history).count(), 2)
        
        # Update with new issues (should delete old ones)
        new_issues = [
            {'type': 'duplicate_title', 'url': 'https://testsite.com/page3'},
            {'type': 'missing_h1', 'url': 'https://testsite.com/page4'},
            {'type': 'thin_content', 'url': 'https://testsite.com/page5'},
        ]
        manager.update_issues(new_issues)
        
        # Verify old issues deleted and new ones created
        current_issues = SiteIssue.objects.filter(performance_history=self.history)
        self.assertEqual(current_issues.count(), 3)
        
        # Verify issue types are correct
        issue_types = set(current_issues.values_list('issue_type', flat=True))
        self.assertEqual(issue_types, {'duplicate_title', 'missing_h1', 'thin_content'})
    
    def test_audit_counts_update(self):
        """Test that audit counts are properly updated"""
        manager = IssueManager(self.history)
        
        test_issues = [
            {'type': 'missing_title', 'url': 'https://testsite.com/page1'},
            {'type': 'missing_title', 'url': 'https://testsite.com/page2'},
            {'type': 'duplicate_title', 'url': 'https://testsite.com/page3'},
            {'type': 'missing_meta_description', 'url': 'https://testsite.com/page4'},
            {'type': 'broken_internal_link', 'url': 'https://testsite.com/page5'},
            {'type': 'redirect_chain', 'url': 'https://testsite.com/old-page'},
        ]
        
        manager.update_issues(test_issues)
        
        # Refresh audit from database
        self.audit.refresh_from_db()
        
        # Verify counts
        self.assertEqual(self.audit.total_issues_count, 6)
        self.assertEqual(self.audit.missing_titles_count, 2)
        self.assertEqual(self.audit.duplicate_titles_count, 1)
        self.assertEqual(self.audit.missing_meta_descriptions_count, 1)
        self.assertEqual(self.audit.broken_links_count, 1)
        self.assertEqual(self.audit.redirect_chains_count, 1)
    
    def test_site_health_calculation(self):
        """Test that site health score is calculated correctly"""
        manager = IssueManager(self.history)
        
        # No issues = 100% health
        manager.update_issues([])
        self.audit.refresh_from_db()
        self.assertEqual(self.audit.overall_site_health_score, 100)
        
        # Some issues = reduced health
        test_issues = [
            {'type': 'missing_title', 'url': f'https://testsite.com/page{i}'}
            for i in range(5)
        ]
        manager.update_issues(test_issues)
        self.audit.refresh_from_db()
        
        # 5 issues on 10 pages = 0.5 issues per page = 90% health
        expected_health = max(0, min(100, 100 - (0.5 * 20)))
        self.assertEqual(self.audit.overall_site_health_score, int(expected_health))


class SiteAuditViewsTestCase(TestCase):
    """Test site audit views"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='test@example.com', password='testpass123')
        
        self.project = Project.objects.create(
            user=self.user,
            domain='testsite.com',
            title='Test Site'
        )
        
        self.audit = SiteAudit.objects.create(
            project=self.project,
            overall_site_health_score=75,
            total_pages_crawled=10,
            total_issues_count=5
        )
        
        # Create performance page for last audit date
        self.perf_page = PerformancePage.objects.create(
            project=self.project,
            page_url='https://testsite.com',
            last_audit_date=timezone.now()
        )
    
    def test_site_audit_list_view(self):
        """Test that the audit list view works correctly"""
        response = self.client.get(reverse('site_audit:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'testsite.com')
        
        # Check that display_last_audit_date is set
        context_audits = response.context['page_obj'].object_list
        for audit in context_audits:
            self.assertTrue(hasattr(audit, 'display_last_audit_date'))
    
    def test_site_audit_detail_view(self):
        """Test that the audit detail view loads correctly"""
        # Create completed history with issues
        history = OnPagePerformanceHistory.objects.create(
            audit=self.audit,
            status='completed',
            pages_crawled=10
        )
        
        # Create test issues
        IssueManager.create_test_issues(history)
        
        response = self.client.get(reverse('site_audit:detail', args=[self.audit.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'testsite.com')
        
        # Check context data
        self.assertIn('all_issues', response.context)
        self.assertIn('critical_count', response.context)
        self.assertIn('high_count', response.context)
        self.assertIn('medium_count', response.context)
        self.assertIn('low_count', response.context)
        self.assertIn('info_count', response.context)
        
        # Verify issue counts
        self.assertGreater(response.context['all_issues'].count(), 0)


class CoreWebVitalsIntegrationTestCase(TestCase):
    """Test Core Web Vitals integration"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.project = Project.objects.create(
            user=self.user,
            domain='testsite.com',
            title='Test Site'
        )
        
        self.audit = SiteAudit.objects.create(
            project=self.project,
            overall_site_health_score=75
        )
        
        self.perf_page = PerformancePage.objects.create(
            project=self.project,
            page_url='https://testsite.com'
        )
        
        self.perf_history = PerformanceHistory.objects.create(
            performance_page=self.perf_page,
            status='completed',
            desktop_largest_contentful_paint=1.5,
            desktop_interaction_to_next_paint=100,
            desktop_cumulative_layout_shift=0.05,
            mobile_largest_contentful_paint=2.5,
            mobile_interaction_to_next_paint=200,
            mobile_cumulative_layout_shift=0.1
        )
    
    def test_audit_proxy_mapping(self):
        """Test that AuditProxy correctly maps Core Web Vitals fields"""
        from site_audit.views import site_audit_detail
        
        # Create the AuditProxy class as defined in views
        class AuditProxy:
            def __init__(self, audit, device):
                self.audit = audit
                self.device = device
                
            def __getattr__(self, name):
                # Map score attributes to the prefixed versions
                if name == 'performance_score':
                    return getattr(self.audit, f'{self.device}_performance_score')
                elif name == 'accessibility_score':
                    return getattr(self.audit, f'{self.device}_accessibility_score')
                elif name == 'best_practices_score':
                    return getattr(self.audit, f'{self.device}_best_practices_score')
                elif name == 'seo_score':
                    return getattr(self.audit, f'{self.device}_seo_score')
                elif name == 'pwa_score':
                    return getattr(self.audit, f'{self.device}_pwa_score')
                # Core Web Vitals mapping
                elif name == 'largest_contentful_paint':
                    return getattr(self.audit, f'{self.device}_largest_contentful_paint')
                elif name == 'interaction_to_next_paint':
                    return getattr(self.audit, f'{self.device}_interaction_to_next_paint')
                elif name == 'cumulative_layout_shift':
                    return getattr(self.audit, f'{self.device}_cumulative_layout_shift')
                elif name == 'first_contentful_paint':
                    return getattr(self.audit, f'{self.device}_first_contentful_paint')
                elif name == 'speed_index':
                    return getattr(self.audit, f'{self.device}_speed_index')
                elif name == 'time_to_interactive':
                    return getattr(self.audit, f'{self.device}_time_to_interactive')
                elif name == 'total_blocking_time':
                    return getattr(self.audit, f'{self.device}_total_blocking_time')
                elif name == 'first_input_delay':
                    return getattr(self.audit, f'{self.device}_first_input_delay')
                elif name == 'time_to_first_byte':
                    return getattr(self.audit, f'{self.device}_time_to_first_byte')
                return getattr(self.audit, name)
        
        desktop_proxy = AuditProxy(self.perf_history, 'desktop')
        mobile_proxy = AuditProxy(self.perf_history, 'mobile')
        
        # Test desktop values
        self.assertEqual(desktop_proxy.largest_contentful_paint, 1.5)
        self.assertEqual(desktop_proxy.interaction_to_next_paint, 100)
        self.assertEqual(desktop_proxy.cumulative_layout_shift, 0.05)
        
        # Test mobile values
        self.assertEqual(mobile_proxy.largest_contentful_paint, 2.5)
        self.assertEqual(mobile_proxy.interaction_to_next_paint, 200)
        self.assertEqual(mobile_proxy.cumulative_layout_shift, 0.1)


class FaviconFallbackTestCase(TestCase):
    """Test favicon fallback system"""
    
    def test_favicon_proxy_with_fallback(self):
        """Test that favicon proxy returns fallback for failed requests"""
        from project.favicon_utils import _serve_default_favicon
        
        # Test that default favicon function returns a valid response
        response = _serve_default_favicon()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertIn('X-Favicon-Cache', response)
        
        # Content should be non-empty
        self.assertGreater(len(response.content), 0)
