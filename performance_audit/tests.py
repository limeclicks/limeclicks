from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import timedelta, datetime

from project.models import Project
from .models import PerformancePage, PerformanceHistory, PerformanceSchedule
from .tasks import (
    create_audit_for_project,
    run_manual_audit,
    check_scheduled_audits,
    run_lighthouse_audit
)

User = get_user_model()


class PerformanceAuditModelTests(TestCase):
    """Test the performance audit models"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.project = Project.objects.create(
            user=self.user,
            domain='example.com',
            title='Test Project',
            active=True
        )
    
    def test_performance_page_creation(self):
        """Test that PerformancePage is created with correct defaults"""
        page = PerformancePage.objects.create(project=self.project)
        
        self.assertEqual(page.page_url, 'https://example.com')
        self.assertEqual(page.audit_frequency_days, 30)
        self.assertTrue(page.is_audit_enabled)
        self.assertIsNotNone(page.next_scheduled_audit)
    
    def test_performance_history_stores_combined_data(self):
        """Test that PerformanceHistory stores both mobile and desktop data"""
        page = PerformancePage.objects.create(project=self.project)
        history = PerformanceHistory.objects.create(
            performance_page=page,
            trigger_type='manual',
            status='completed',
            # Mobile scores
            mobile_performance_score=85,
            mobile_accessibility_score=90,
            mobile_best_practices_score=88,
            mobile_seo_score=92,
            # Desktop scores
            desktop_performance_score=90,
            desktop_accessibility_score=92,
            desktop_best_practices_score=89,
            desktop_seo_score=93
        )
        
        # Check mobile scores
        self.assertEqual(history.mobile_performance_score, 85)
        self.assertEqual(history.mobile_accessibility_score, 90)
        
        # Check desktop scores
        self.assertEqual(history.desktop_performance_score, 90)
        self.assertEqual(history.desktop_accessibility_score, 92)
    
    def test_can_run_manual_audit_rate_limiting(self):
        """Test daily rate limiting for manual audits"""
        page = PerformancePage.objects.create(project=self.project)
        
        # First time should be allowed
        self.assertTrue(page.can_run_manual_audit())
        
        # Set last manual audit to now
        page.last_manual_audit = timezone.now()
        page.save()
        
        # Should not be allowed immediately
        self.assertFalse(page.can_run_manual_audit())
        
        # Should be allowed after 24 hours
        page.last_manual_audit = timezone.now() - timedelta(days=1, minutes=1)
        page.save()
        self.assertTrue(page.can_run_manual_audit())
    
    def test_schedule_next_audit(self):
        """Test that next audit is scheduled correctly (30 days default)"""
        page = PerformancePage.objects.create(project=self.project)
        initial_schedule = page.next_scheduled_audit
        
        page.schedule_next_audit()
        
        # Should be scheduled 30 days from now
        expected = timezone.now() + timedelta(days=30)
        self.assertAlmostEqual(
            page.next_scheduled_audit,
            expected,
            delta=timedelta(minutes=1)
        )
        self.assertNotEqual(page.next_scheduled_audit, initial_schedule)


class PerformanceAuditTaskTests(TransactionTestCase):
    """Test the performance audit tasks"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.project = Project.objects.create(
            user=self.user,
            domain='example.com',
            title='Test Project',
            active=True
        )
    
    @patch('performance_audit.tasks.run_lighthouse_audit.delay')
    def test_create_audit_for_project(self, mock_delay):
        """Test that project creation triggers a combined audit"""
        result = create_audit_for_project(self.project.id, 'project_created')
        
        # Check that PerformancePage was created
        self.assertTrue(PerformancePage.objects.filter(project=self.project).exists())
        
        # Check that a single PerformanceHistory was created
        histories = PerformanceHistory.objects.filter(
            performance_page__project=self.project
        )
        self.assertEqual(histories.count(), 1)
        
        # Check that the audit task was queued
        mock_delay.assert_called_once()
        
        # Verify the result
        self.assertTrue(result['success'])
        self.assertEqual(result['project_id'], self.project.id)
    
    @patch('performance_audit.tasks.run_lighthouse_audit.delay')
    def test_create_audit_prevents_duplicate_today(self, mock_delay):
        """Test that only one audit per day is created"""
        # Create first audit
        result1 = create_audit_for_project(self.project.id, 'project_created')
        self.assertTrue(result1['success'])
        
        # Try to create second audit same day
        result2 = create_audit_for_project(self.project.id, 'manual')
        
        # Should succeed but indicate audit already exists
        self.assertTrue(result2['success'])
        self.assertIn('already exists', result2.get('message', '').lower())
        
        # Should still only have one audit
        histories = PerformanceHistory.objects.filter(
            performance_page__project=self.project
        )
        self.assertEqual(histories.count(), 1)
    
    @patch('performance_audit.tasks.run_lighthouse_audit.delay')
    def test_run_manual_audit_rate_limiting(self, mock_delay):
        """Test manual audit daily rate limiting"""
        mock_delay.return_value = MagicMock(id='test-task-id')
        
        page = PerformancePage.objects.create(project=self.project)
        
        # First manual audit should succeed
        result1 = run_manual_audit(page.id)
        self.assertTrue(result1['success'])
        
        # Second manual audit same day should fail
        result2 = run_manual_audit(page.id)
        self.assertFalse(result2['success'])
        self.assertIn('rate limited', result2['error'].lower())
        
        # Update last_manual_audit to more than 24 hours ago
        page.refresh_from_db()
        page.last_manual_audit = timezone.now() - timedelta(days=1, minutes=1)
        page.save()
        
        # Clear any existing audits for today to allow test to pass
        PerformanceHistory.objects.filter(
            performance_page=page,
            created_at__gte=timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ).delete()
        
        # Now it should succeed again
        result3 = run_manual_audit(page.id)
        self.assertTrue(result3['success'])
    
    @patch('performance_audit.tasks.run_lighthouse_audit.delay')
    def test_check_scheduled_audits(self, mock_delay):
        """Test that scheduled audits are created correctly"""
        mock_delay.return_value = MagicMock(id='test-task-id')
        
        page = PerformancePage.objects.create(project=self.project)
        
        # Set next scheduled audit to past
        page.next_scheduled_audit = timezone.now() - timedelta(hours=1)
        page.save()
        
        # Run the scheduler
        result = check_scheduled_audits()
        
        # Should have created one audit
        self.assertTrue(result['success'])
        self.assertEqual(result['scheduled_count'], 1)
        
        # Check that audit was created
        histories = PerformanceHistory.objects.filter(
            performance_page=page,
            trigger_type='scheduled'
        )
        self.assertEqual(histories.count(), 1)
        
        # Check task was queued
        mock_delay.assert_called_once()
        
        # Check that next audit was scheduled
        page.refresh_from_db()
        expected_next = timezone.now() + timedelta(days=page.audit_frequency_days)
        self.assertAlmostEqual(
            page.next_scheduled_audit,
            expected_next,
            delta=timedelta(minutes=5)
        )
    
    @patch('performance_audit.lighthouse_runner.LighthouseRunner.run_audit')
    def test_run_lighthouse_audit_combined(self, mock_run_audit):
        """Test that run_lighthouse_audit handles both mobile and desktop"""
        # Setup mock responses
        mock_run_audit.side_effect = [
            (True, {  # Mobile result
                'performance_score': 85,
                'accessibility_score': 90,
                'best_practices_score': 88,
                'seo_score': 92,
                'overall_score': 89,
                'first_contentful_paint': 1.2,
                'largest_contentful_paint': 2.5,
                'cumulative_layout_shift': 0.05,
                'errors': {},
                'json_content': '{"mobile": "data"}'
            }, None),
            (True, {  # Desktop result
                'performance_score': 90,
                'accessibility_score': 92,
                'best_practices_score': 89,
                'seo_score': 93,
                'overall_score': 91,
                'first_contentful_paint': 0.9,
                'largest_contentful_paint': 2.0,
                'cumulative_layout_shift': 0.03,
                'errors': {},
                'json_content': '{"desktop": "data"}'
            }, None)
        ]
        
        page = PerformancePage.objects.create(project=self.project)
        history = PerformanceHistory.objects.create(
            performance_page=page,
            trigger_type='manual',
            status='pending'
        )
        
        # Run the audit
        result = run_lighthouse_audit(str(history.id))
        
        # Check the result
        self.assertTrue(result['success'])
        self.assertIn('mobile', result['scores'])
        self.assertIn('desktop', result['scores'])
        self.assertEqual(result['scores']['mobile']['performance'], 85)
        self.assertEqual(result['scores']['desktop']['performance'], 90)
        
        # Check that the history was updated
        history.refresh_from_db()
        self.assertEqual(history.status, 'completed')
        self.assertEqual(history.mobile_performance_score, 85)
        self.assertEqual(history.desktop_performance_score, 90)


class PerformanceAuditIntegrationTests(TransactionTestCase):
    """Integration tests for the full audit workflow"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            email_verified=True,
            is_active=True
        )
    
    @patch('performance_audit.tasks.create_audit_for_project.delay')
    @patch('site_audit.tasks.create_site_audit_for_project.delay')
    def test_project_creation_triggers_audit(self, mock_site_audit, mock_perf_audit):
        """Test that creating a project automatically triggers performance audit"""
        # Mock the delay to call the actual task
        mock_perf_audit.return_value = MagicMock(id='test-task-id')
        
        # Simulate project creation with signal
        project = Project.objects.create(
            user=self.user,
            domain='newproject.com',
            title='New Test Project',
            active=True
        )
        
        # Check that the task was called
        mock_perf_audit.assert_called_once_with(project.id, 'project_created')
    
    def test_monthly_audit_frequency(self):
        """Test that audits are scheduled monthly (30 days default)"""
        project = Project.objects.create(
            user=self.user,
            domain='monthly-test.com',
            title='Monthly Test Project',
            active=True
        )
        
        page = PerformancePage.objects.create(
            project=project,
            audit_frequency_days=30  # Monthly
        )
        
        # Initial scheduling
        initial_schedule = page.next_scheduled_audit
        self.assertIsNotNone(initial_schedule)
        
        # Schedule next audit
        page.schedule_next_audit()
        
        # Check it's scheduled 30 days later
        time_diff = page.next_scheduled_audit - initial_schedule
        self.assertAlmostEqual(
            time_diff.days,
            30,
            delta=1
        )
    
    def test_update_from_audit_results(self):
        """Test that PerformancePage is updated with latest audit results"""
        project = Project.objects.create(
            user=self.user,
            domain='update-test.com',
            title='Update Test Project',
            active=True
        )
        
        page = PerformancePage.objects.create(project=project)
        
        # Create a completed audit
        history = PerformanceHistory.objects.create(
            performance_page=page,
            trigger_type='manual',
            status='completed',
            completed_at=timezone.now(),
            mobile_performance_score=85,
            mobile_accessibility_score=90,
            mobile_best_practices_score=88,
            mobile_seo_score=92,
            mobile_pwa_score=80
        )
        
        # Update page from results
        page.update_from_audit_results(history)
        
        # Check that page was updated with mobile scores (mobile-first)
        self.assertEqual(page.performance_score, 85)
        self.assertEqual(page.accessibility_score, 90)
        self.assertEqual(page.best_practices_score, 88)
        self.assertEqual(page.seo_score, 92)
        self.assertEqual(page.pwa_score, 80)
        self.assertEqual(page.last_audit_date, history.completed_at)


class PerformanceAuditEdgeCaseTests(TestCase):
    """Test edge cases and error handling"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_project_deletion_cascades(self):
        """Test that deleting a project removes all audit data"""
        project = Project.objects.create(
            user=self.user,
            domain='delete-test.com',
            title='Delete Test',
            active=True
        )
        
        page = PerformancePage.objects.create(project=project)
        history = PerformanceHistory.objects.create(
            performance_page=page,
            trigger_type='manual',
            status='completed'
        )
        
        # Delete the project
        project.delete()
        
        # Check that everything was deleted
        self.assertFalse(PerformancePage.objects.filter(id=page.id).exists())
        self.assertFalse(PerformanceHistory.objects.filter(id=history.id).exists())
    
    def test_handle_partial_audit_results(self):
        """Test handling when only one device type succeeds"""
        page = PerformancePage.objects.create(
            project=Project.objects.create(
                user=self.user,
                domain='partial-test.com',
                title='Partial Test',
                active=True
            )
        )
        
        history = PerformanceHistory.objects.create(
            performance_page=page,
            trigger_type='manual',
            status='completed',
            # Only mobile data available
            mobile_performance_score=85,
            mobile_accessibility_score=90,
            # Desktop data is None
            desktop_performance_score=None,
            desktop_accessibility_score=None
        )
        
        # Should still be able to get mobile scores
        self.assertEqual(history.mobile_performance_score, 85)
        self.assertIsNone(history.desktop_performance_score)
    
    def test_invalid_project_id(self):
        """Test handling of invalid project ID"""
        result = create_audit_for_project(99999, 'manual')
        
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'].lower())
    
    def test_schedule_prevents_duplicates(self):
        """Test that scheduler prevents duplicate audits"""
        project = Project.objects.create(
            user=self.user,
            domain='schedule-test.com',
            title='Schedule Test',
            active=True
        )
        
        page = PerformancePage.objects.create(project=project)
        
        # Create multiple schedules for the same time
        schedule_time = timezone.now()
        schedule1 = PerformanceSchedule.objects.create(
            performance_page=page,
            scheduled_for=schedule_time
        )
        
        # Second schedule should fail due to unique constraint
        with self.assertRaises(Exception):
            PerformanceSchedule.objects.create(
                performance_page=page,
                scheduled_for=schedule_time
            )