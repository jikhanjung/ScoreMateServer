"""
API tests for authentication endpoints
"""
import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.test import TestCase
from django.contrib.auth import get_user_model

from .factories import UserFactory

User = get_user_model()


@pytest.mark.django_db
class AuthAPITest(TestCase):
    """Test authentication API endpoints"""
    
    def setUp(self):
        """Set up test client"""
        self.client = APIClient()
        self.register_url = '/api/v1/auth/register/'
        self.login_url = '/api/v1/auth/login/'
        self.profile_url = '/api/v1/user/profile/'
    
    def test_user_registration_success(self):
        """Test successful user registration"""
        data = {
            'email': 'test@example.com',
            'username': 'testuser',
            'password': 'securepassword123',
            'password_confirm': 'securepassword123',
            'plan': 'solo'
        }
        
        response = self.client.post(self.register_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('user', response.data)
        self.assertIn('tokens', response.data)
        self.assertIn('access', response.data['tokens'])
        self.assertIn('refresh', response.data['tokens'])
        
        # Verify user was created
        user = User.objects.get(email='test@example.com')
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.plan, 'solo')
        self.assertEqual(user.total_quota_mb, 200)  # Default quota
    
    def test_user_registration_password_mismatch(self):
        """Test registration with password mismatch"""
        data = {
            'email': 'test@example.com',
            'username': 'testuser',
            'password': 'securepassword123',
            'password_confirm': 'differentpassword',
            'plan': 'solo'
        }
        
        response = self.client.post(self.register_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password_confirm', response.data)
    
    def test_user_registration_duplicate_email(self):
        """Test registration with existing email"""
        # Create existing user
        UserFactory(email='test@example.com')
        
        data = {
            'email': 'test@example.com',
            'username': 'testuser2',
            'password': 'securepassword123',
            'password_confirm': 'securepassword123'
        }
        
        response = self.client.post(self.register_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)
    
    def test_user_login_success(self):
        """Test successful user login"""
        # Create user
        user = UserFactory(email='test@example.com', username='testuser')
        
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'  # Default password from factory
        }
        
        response = self.client.post(self.login_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user', response.data)
        self.assertIn('tokens', response.data)
        self.assertEqual(response.data['user']['id'], user.id)
    
    def test_user_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        UserFactory(email='test@example.com')
        
        data = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }
        
        response = self.client.post(self.login_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid email or password', str(response.data))
    
    def test_user_profile_authenticated(self):
        """Test accessing user profile with authentication"""
        user = UserFactory()
        self.client.force_authenticate(user=user)
        
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], user.id)
        self.assertEqual(response.data['email'], user.email)
        self.assertIn('available_quota_mb', response.data)
        self.assertIn('quota_usage_percentage', response.data)
    
    def test_user_profile_unauthenticated(self):
        """Test accessing user profile without authentication"""
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_jwt_token_authentication(self):
        """Test JWT token authentication"""
        user = UserFactory()
        
        # Login to get tokens
        login_data = {
            'email': user.email,
            'password': 'testpass123'
        }
        login_response = self.client.post(self.login_url, login_data)
        access_token = login_response.data['tokens']['access']
        
        # Use token to access protected endpoint
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        profile_response = self.client.get(self.profile_url)
        
        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_response.data['id'], user.id)