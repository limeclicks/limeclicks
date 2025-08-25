#!/usr/bin/env python
"""
End-to-end test for authentication flow
Tests the complete login process including hard redirect to dashboard
"""

import os
import sys
import django
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

User = get_user_model()


@override_settings(
    RECAPTCHA_PUBLIC_KEY='6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI',
    RECAPTCHA_PRIVATE_KEY='6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe',
    SILENCED_SYSTEM_CHECKS=['django_recaptcha.recaptcha_test_key_error']
)
class AuthE2ETestCase(TestCase):
    """End-to-end authentication flow tests"""
    
    def setUp(self):
        self.client = Client()
        self.login_url = reverse('accounts:login')
        self.dashboard_url = reverse('accounts:dashboard')
        
        # Create a test user
        self.test_email = 'test@example.com'
        self.test_password = 'TestPass123!'
        self.user = User.objects.create_user(
            username='testuser',
            email=self.test_email,
            password=self.test_password,
            first_name='Test'
        )
        self.user.email_verified = True
        self.user.save()
    
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_login_flow_with_hard_redirect(self, mock_recaptcha):
        """Test complete login flow with hard redirect to dashboard"""
        print("\n" + "="*60)
        print("E2E TEST: Login Flow with Hard Redirect")
        print("="*60)
        
        # Step 1: Navigate to login page
        print("\n1. Navigating to login page...")
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sign in')
        print("   ✓ Login page loaded successfully")
        
        # Step 2: Submit login credentials
        print("\n2. Submitting login credentials...")
        response = self.client.post(self.login_url, {
            'username': self.test_email,
            'password': self.test_password,
            'g-recaptcha-response': 'test'
        }, follow=False)
        
        # Step 3: Verify hard redirect (302)
        print("\n3. Verifying hard redirect...")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.dashboard_url)
        print(f"   ✓ Received 302 redirect to: {response.url}")
        
        # Step 4: Follow redirect to dashboard
        print("\n4. Following redirect to dashboard...")
        response = self.client.get(response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')
        self.assertContains(response, 'Test')  # Check user's name is displayed
        print("   ✓ Dashboard loaded successfully")
        
        # Step 5: Verify session is maintained
        print("\n5. Verifying session persistence...")
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')
        print("   ✓ Session maintained across requests")
        
        print("\n" + "="*60)
        print("✅ E2E TEST PASSED: Login flow working correctly")
        print("="*60 + "\n")
    
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_login_with_next_url_redirect(self, mock_recaptcha):
        """Test login redirects to 'next' URL parameter"""
        print("\n" + "="*60)
        print("E2E TEST: Login with 'next' URL parameter")
        print("="*60)
        
        # Protected URL that requires login
        protected_url = reverse('accounts:profile_settings')
        
        # Step 1: Try to access protected URL (should redirect to login)
        print(f"\n1. Accessing protected URL: {protected_url}")
        response = self.client.get(protected_url, follow=False)
        self.assertEqual(response.status_code, 302)
        login_with_next = f"{self.login_url}?next={protected_url}"
        print(f"   ✓ Redirected to login: {login_with_next}")
        
        # Step 2: Login with next parameter
        print("\n2. Logging in with 'next' parameter...")
        response = self.client.post(
            login_with_next,
            {
                'username': self.test_email,
                'password': self.test_password,
                'g-recaptcha-response': 'test'
            },
            follow=False
        )
        
        # Step 3: Verify redirect to protected URL
        print("\n3. Verifying redirect to protected URL...")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, protected_url)
        print(f"   ✓ Redirected to: {response.url}")
        
        # Step 4: Verify protected page loads
        print("\n4. Verifying protected page loads...")
        response = self.client.get(response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Profile Settings')
        print("   ✓ Protected page loaded successfully")
        
        print("\n" + "="*60)
        print("✅ E2E TEST PASSED: Login with 'next' URL working")
        print("="*60 + "\n")
    
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_logout_and_redirect(self, mock_recaptcha):
        """Test logout functionality and redirect to login"""
        print("\n" + "="*60)
        print("E2E TEST: Logout and Redirect")
        print("="*60)
        
        # First login
        print("\n1. Logging in user...")
        self.client.post(self.login_url, {
            'username': self.test_email,
            'password': self.test_password,
            'g-recaptcha-response': 'test'
        })
        print("   ✓ User logged in")
        
        # Verify can access dashboard
        print("\n2. Verifying dashboard access...")
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        print("   ✓ Dashboard accessible")
        
        # Logout
        print("\n3. Logging out...")
        logout_url = reverse('accounts:logout')
        response = self.client.get(logout_url, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.login_url)
        print(f"   ✓ Logged out and redirected to: {response.url}")
        
        # Verify can't access dashboard anymore
        print("\n4. Verifying dashboard is protected...")
        response = self.client.get(self.dashboard_url, follow=False)
        self.assertEqual(response.status_code, 302)
        print("   ✓ Dashboard protected after logout")
        
        print("\n" + "="*60)
        print("✅ E2E TEST PASSED: Logout flow working correctly")
        print("="*60 + "\n")


def run_tests():
    """Run the E2E tests"""
    from django.test.utils import get_runner
    from django.conf import settings
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=True, keepdb=True)
    
    # Run our E2E test
    failures = test_runner.run_tests(['test_auth_e2e.AuthE2ETestCase'])
    
    if failures:
        print("\n❌ E2E TESTS FAILED")
        sys.exit(1)
    else:
        print("\n✅ ALL E2E TESTS PASSED")
        sys.exit(0)


if __name__ == '__main__':
    run_tests()