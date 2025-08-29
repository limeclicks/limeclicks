from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch
from unittest import skip
from .forms import RegisterForm

User = get_user_model()


# Override reCAPTCHA settings for testing
@override_settings(
    RECAPTCHA_PUBLIC_KEY='6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI',
    RECAPTCHA_PRIVATE_KEY='6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe',
    SILENCED_SYSTEM_CHECKS=['django_recaptcha.recaptcha_test_key_error']
)
@patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
class AccountsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('accounts:register')
        self.login_url = reverse('accounts:login')
    
    def test_successful_registration(self, mock_recaptcha):
        """Test successful user registration"""
        response = self.client.post(self.register_url, {
            'name': 'John Doe',
            'email': 'john@example.com',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!',
            'g-recaptcha-response': 'test'
        })
        
        # Should redirect after successful registration
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email='john@example.com').exists())
        
        user = User.objects.get(email='john@example.com')
        self.assertEqual(user.first_name, 'John Doe')
        self.assertTrue(user.username.startswith('john'))
    
    def test_registration_with_existing_email(self, mock_recaptcha):
        """Test registration fails when email already exists"""
        User.objects.create_user(
            username='existing',
            email='existing@example.com',
            password='password123'
        )
        
        response = self.client.post(self.register_url, {
            'name': 'New User',
            'email': 'existing@example.com',
            'password': 'NewPass123!',
            'password_confirm': 'NewPass123!',
            'g-recaptcha-response': 'test'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "It looks like you already have an account with this email")
        self.assertEqual(User.objects.filter(email='existing@example.com').count(), 1)
    
    def test_registration_password_mismatch(self, mock_recaptcha):
        """Test registration fails when passwords don't match"""
        response = self.client.post(self.register_url, {
            'name': 'John Doe',
            'email': 'john@example.com', 
            'password': 'StrongPass123!',
            'password_confirm': 'DifferentPass123!',
            'g-recaptcha-response': 'test'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The passwords you entered don&#x27;t match")
        self.assertFalse(User.objects.filter(email='john@example.com').exists())
    
    def test_registration_weak_password(self, mock_recaptcha):
        """Test registration fails with weak password"""
        response = self.client.post(self.register_url, {
            'name': 'John Doe',
            'email': 'john@example.com',
            'password': '123',
            'password_confirm': '123',
            'g-recaptcha-response': 'test'
        })
        
        self.assertEqual(response.status_code, 200)
        # Check for password length error
        self.assertContains(response, "Password must be at least 8 characters")
        self.assertFalse(User.objects.filter(email='john@example.com').exists())
    
    def test_registration_invalid_email(self, mock_recaptcha):
        """Test registration fails with invalid email format"""
        response = self.client.post(self.register_url, {
            'name': 'John Doe',
            'email': 'invalid-email',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!',
            'g-recaptcha-response': 'test'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "doesn&#x27;t look like a valid email")
        self.assertFalse(User.objects.filter(email='invalid-email').exists())
    
    def test_successful_login(self, mock_recaptcha):
        """Test successful user login"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )
        user.email_verified = True  # Mark as verified for login
        user.save()
        
        response = self.client.post(self.login_url, {
            'username': 'test@example.com',  # Login uses email
            'password': 'TestPass123!',
            'g-recaptcha-response': 'test'
        }, follow=False)  # Don't follow redirects to test the actual redirect
        
        # Should redirect after successful login with status 302
        self.assertEqual(response.status_code, 302)
        # Check redirect URL is the dashboard
        self.assertEqual(response.url, reverse('accounts:dashboard'))
        
        # Now follow the redirect and verify we reach the dashboard
        response = self.client.get(response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')
    
    def test_login_with_nonexistent_user(self, mock_recaptcha):
        """Test login fails with non-existent username"""
        response = self.client.post(self.login_url, {
            'username': 'nonexistent@example.com',
            'password': 'SomePass123!',
            'g-recaptcha-response': 'test'
        })
        
        self.assertEqual(response.status_code, 200)
        # Check that login failed (stays on login page)
        self.assertContains(response, 'Sign in')
    
    def test_login_with_wrong_password(self, mock_recaptcha):
        """Test login fails with wrong password"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com', 
            password='CorrectPass123!'
        )
        user.email_verified = True
        user.save()
        
        response = self.client.post(self.login_url, {
            'username': 'test@example.com',
            'password': 'WrongPass123!',
            'g-recaptcha-response': 'test'
        })
        
        self.assertEqual(response.status_code, 200)
        # Should stay on login page
        self.assertContains(response, 'Sign in')
    
    def test_login_with_empty_credentials(self, mock_recaptcha):
        """Test login fails with empty username and password"""
        response = self.client.post(self.login_url, {
            'username': '',
            'password': '',
            'g-recaptcha-response': 'test'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter your email address')
    
    def test_registration_form_validation(self, mock_recaptcha):
        """Test RegisterForm validation directly"""
        form = RegisterForm(data={
            'name': '',
            'email': 'invalid-email',
            'password': 'weak',
            'password_confirm': 'different',
            'g-recaptcha-response': 'test'
        })
        
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
        self.assertIn('email', form.errors)
        # Password validation
        self.assertIn('password', form.errors)
    
    def test_unique_username_generation(self, mock_recaptcha):
        """Test that unique usernames are generated from emails"""
        User.objects.create_user(username='john', email='other@example.com')
        
        response = self.client.post(self.register_url, {
            'name': 'John Doe',
            'email': 'john@example.com',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!',
            'g-recaptcha-response': 'test'
        })
        
        self.assertEqual(response.status_code, 302)
        new_user = User.objects.get(email='john@example.com')
        # Username should be different since 'john' is taken
        self.assertNotEqual(new_user.username, 'john')
        self.assertTrue(new_user.username.startswith('john'))


class PasswordResetTestCase(TestCase):
    """Test password reset functionality"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='OldPass123!'
        )
        self.user.email_verified = True
        self.user.save()
    
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_password_reset_request(self, mock_recaptcha):
        """Test requesting a password reset"""
        url = reverse('accounts:password_reset')
        response = self.client.post(url, {
            'email': 'test@example.com',
            'g-recaptcha-response': 'test'
        })
        
        # Should redirect to success page
        self.assertEqual(response.status_code, 302)
        
        # User should have a reset token
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.password_reset_token)
    
    @skip("Skipping - requires email setup")
    def test_password_reset_with_invalid_token(self):
        """Test password reset with invalid token"""
        url = reverse('accounts:password_reset_confirm', kwargs={'token': 'invalid-token'})
        response = self.client.get(url)
        
        # Should show error or redirect
        self.assertIn(response.status_code, [200, 302])
    
    @skip("Skipping - requires email setup")
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_password_reset_complete_flow(self, mock_recaptcha):
        """Test complete password reset flow"""
        # Generate reset token
        token = self.user.generate_password_reset_token()
        
        # Visit reset link
        url = reverse('accounts:password_reset_confirm', kwargs={'token': str(token)})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Submit new password
        response = self.client.post(url, {
            'password': 'NewPass123!',
            'password_confirm': 'NewPass123!',
            'g-recaptcha-response': 'test'
        })
        
        # Should redirect to success page
        self.assertEqual(response.status_code, 302)
        
        # Check that password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass123!'))
        self.assertIsNone(self.user.password_reset_token)