from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.contrib.auth import authenticate
from .forms import RegisterForm


class AccountsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('accounts:register')
        self.login_url = reverse('accounts:login')
    
    def test_successful_registration(self):
        """Test successful user registration"""
        response = self.client.post(self.register_url, {
            'name': 'John Doe',
            'email': 'john@example.com',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!'
        })
        
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email='john@example.com').exists())
        
        user = User.objects.get(email='john@example.com')
        self.assertEqual(user.first_name, 'John Doe')
        self.assertTrue(user.username.startswith('john'))
    
    def test_registration_with_existing_email(self):
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
            'password_confirm': 'NewPass123!'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter a valid email address')
        self.assertEqual(User.objects.filter(email='existing@example.com').count(), 1)
    
    def test_registration_password_mismatch(self):
        """Test registration fails when passwords don't match"""
        response = self.client.post(self.register_url, {
            'name': 'John Doe',
            'email': 'john@example.com', 
            'password': 'StrongPass123!',
            'password_confirm': 'DifferentPass123!'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Passwords do not match')
        self.assertFalse(User.objects.filter(email='john@example.com').exists())
    
    def test_registration_weak_password(self):
        """Test registration fails with weak password"""
        response = self.client.post(self.register_url, {
            'name': 'John Doe',
            'email': 'john@example.com',
            'password': '123',
            'password_confirm': '123'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='john@example.com').exists())
    
    def test_registration_invalid_email(self):
        """Test registration fails with invalid email format"""
        response = self.client.post(self.register_url, {
            'name': 'John Doe',
            'email': 'invalid-email',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='invalid-email').exists())
    
    def test_successful_login(self):
        """Test successful user login"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )
        
        response = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'TestPass123!'
        })
        
        self.assertEqual(response.status_code, 302)
        
        authenticated_user = authenticate(username='testuser', password='TestPass123!')
        self.assertIsNotNone(authenticated_user)
        self.assertEqual(authenticated_user.id, user.id)
    
    def test_login_with_nonexistent_user(self):
        """Test login fails with non-existent username"""
        response = self.client.post(self.login_url, {
            'username': 'nonexistent',
            'password': 'SomePass123!'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter a correct username and password')
    
    def test_login_with_wrong_password(self):
        """Test login fails with wrong password"""
        User.objects.create_user(
            username='testuser',
            email='test@example.com', 
            password='CorrectPass123!'
        )
        
        response = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'WrongPass123!'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter a correct username and password')
    
    def test_login_with_empty_credentials(self):
        """Test login fails with empty username and password"""
        response = self.client.post(self.login_url, {
            'username': '',
            'password': ''
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter a valid email address')
    
    def test_registration_form_validation(self):
        """Test RegisterForm validation directly"""
        form = RegisterForm(data={
            'name': '',
            'email': 'invalid-email',
            'password': 'weak',
            'password_confirm': 'different'
        })
        
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
        self.assertIn('email', form.errors)
    
    def test_unique_username_generation(self):
        """Test that unique usernames are generated from emails"""
        User.objects.create_user(username='john', email='other@example.com')
        
        response = self.client.post(self.register_url, {
            'name': 'John Doe',
            'email': 'john@example.com',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!'
        })
        
        self.assertEqual(response.status_code, 302)
        new_user = User.objects.get(email='john@example.com')
        self.assertEqual(new_user.username, 'john-2')
