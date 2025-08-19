"""
API tests for files endpoints (presigned URLs)
"""
import pytest
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from rest_framework import status
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache

from .factories import UserFactory, ScoreFactory
from scores.models import Score

User = get_user_model()


@pytest.mark.django_db
class FileAPITest(TestCase):
    """Test files API endpoints"""
    
    def setUp(self):
        """Set up test client and data"""
        self.client = APIClient()
        self.user = UserFactory(used_quota_mb=50)  # Has some quota used
        self.client.force_authenticate(user=self.user)
        
        self.upload_url = '/api/v1/files/upload-url/'
        self.download_url = '/api/v1/files/download-url/'
        self.confirm_url = '/api/v1/files/upload-confirm/'
        self.cancel_url = '/api/v1/files/upload-cancel/'
    
    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()
    
    @patch('files.utils.S3Handler.generate_presigned_upload_url')
    def test_upload_url_generation_success(self, mock_s3):
        """Test successful presigned upload URL generation"""
        # Mock S3 response
        mock_s3.return_value = {
            'url': 'https://minio.example.com/bucket/user123/uploads/uuid/original.pdf?signature=...',
            'headers': {'Content-Type': 'application/pdf'},
            'method': 'PUT'
        }
        
        data = {
            'filename': 'test-score.pdf',
            'size_bytes': 5 * 1024 * 1024,  # 5MB
            'mime_type': 'application/pdf'
        }
        
        response = self.client.post(self.upload_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('upload_id', response.data)
        self.assertIn('upload_url', response.data)
        self.assertIn('s3_key', response.data)
        self.assertIn('headers', response.data)
        self.assertEqual(response.data['expires_in'], 300)
        self.assertEqual(response.data['method'], 'PUT')
        
        # Verify S3 handler was called
        mock_s3.assert_called_once()
    
    def test_upload_url_quota_exceeded(self):
        """Test upload URL generation when quota is exceeded"""
        # Set user quota to nearly full
        self.user.used_quota_mb = 190
        self.user.total_quota_mb = 200
        self.user.save()
        
        data = {
            'size_bytes': 20 * 1024 * 1024,  # 20MB - exceeds remaining quota
            'mime_type': 'application/pdf'
        }
        
        response = self.client.post(self.upload_url, data)
        
        # Could be 413 (from view) or 400 (from serializer validation)
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE])
        # Check for quota error message (can be in different formats)
        response_text = str(response.data).lower()
        self.assertTrue('quota' in response_text or 'exceed' in response_text)
    
    def test_upload_url_invalid_mime_type(self):
        """Test upload URL generation with invalid MIME type"""
        data = {
            'size_bytes': 5 * 1024 * 1024,
            'mime_type': 'image/jpeg'  # Not allowed
        }
        
        response = self.client.post(self.upload_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('mime_type', response.data)
    
    def test_upload_url_file_too_large(self):
        """Test upload URL generation with file too large"""
        data = {
            'size_bytes': 200 * 1024 * 1024,  # 200MB - exceeds max file size
            'mime_type': 'application/pdf'
        }
        
        response = self.client.post(self.upload_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check for size validation error (can be in size_bytes or non_field_errors)
        self.assertTrue('size_bytes' in response.data or 'non_field_errors' in response.data)
    
    @patch('files.utils.S3Handler.generate_presigned_upload_url')
    def test_upload_confirmation(self, mock_s3):
        """Test upload confirmation"""
        # Mock S3 response
        mock_s3.return_value = {
            'url': 'https://example.com/upload',
            'headers': {'Content-Type': 'application/pdf'},
            'method': 'PUT'
        }
        
        # First, generate upload URL to create reservation
        upload_data = {
            'size_bytes': 5 * 1024 * 1024,  # 5MB
            'mime_type': 'application/pdf'
        }
        
        upload_response = self.client.post(self.upload_url, upload_data)
        self.assertEqual(upload_response.status_code, status.HTTP_201_CREATED)
        
        upload_id = upload_response.data['upload_id']
        initial_quota = self.user.used_quota_mb
        
        # Confirm upload
        confirm_data = {'upload_id': upload_id}
        confirm_response = self.client.post(self.confirm_url, confirm_data)
        
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(confirm_response.data['upload_id']), str(upload_id))
        self.assertIn('quota_used_mb', confirm_response.data)
        self.assertIn('remaining_quota_mb', confirm_response.data)
        
        # Verify quota was updated
        self.user.refresh_from_db()
        self.assertGreater(self.user.used_quota_mb, initial_quota)
    
    def test_upload_confirmation_invalid_id(self):
        """Test upload confirmation with invalid upload ID"""
        data = {'upload_id': '00000000-0000-0000-0000-000000000000'}
        
        response = self.client.post(self.confirm_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check for validation error (DRF format) or custom error format
        self.assertTrue('upload_id' in response.data or 'error' in response.data)
    
    @patch('files.utils.S3Handler.generate_presigned_upload_url')
    def test_upload_cancellation(self, mock_s3):
        """Test upload cancellation"""
        # Mock S3 response
        mock_s3.return_value = {
            'url': 'https://example.com/upload',
            'headers': {'Content-Type': 'application/pdf'},
            'method': 'PUT'
        }
        
        # Generate upload URL
        upload_data = {
            'size_bytes': 5 * 1024 * 1024,  # 5MB
            'mime_type': 'application/pdf'
        }
        
        upload_response = self.client.post(self.upload_url, upload_data)
        upload_id = upload_response.data['upload_id']
        
        # Cancel upload
        cancel_data = {'upload_id': upload_id}
        cancel_response = self.client.post(self.cancel_url, cancel_data)
        
        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel_response.data['upload_id'], upload_id)
        
        # Try to confirm cancelled upload (should fail)
        confirm_data = {'upload_id': upload_id}
        confirm_response = self.client.post(self.confirm_url, confirm_data)
        
        self.assertEqual(confirm_response.status_code, status.HTTP_400_BAD_REQUEST)
    
    @patch('files.utils.S3Handler.generate_presigned_download_url')
    def test_download_url_original_file(self, mock_s3):
        """Test download URL generation for original file"""
        # Create a score
        score = ScoreFactory(user=self.user)
        
        # Mock S3 response
        mock_s3.return_value = {
            'url': f'https://example.com/download/{score.s3_key}',
            'method': 'GET',
            'expires_in': 300
        }
        
        params = {
            'score_id': score.id,
            'file_type': 'original'
        }
        
        response = self.client.get(self.download_url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('download_url', response.data)
        self.assertEqual(response.data['s3_key'], score.s3_key)
        self.assertEqual(response.data['file_type'], 'original')
        self.assertEqual(response.data['method'], 'GET')
        self.assertEqual(response.data['expires_in'], 300)
        
        # Verify S3 handler was called with correct key
        mock_s3.assert_called_once_with(score.s3_key)
    
    @patch('files.utils.S3Handler.generate_presigned_download_url')
    def test_download_url_thumbnail_file(self, mock_s3):
        """Test download URL generation for thumbnail"""
        # Create a score with thumbnail
        score = ScoreFactory(user=self.user)
        score.thumbnail_key = f"{self.user.id}/scores/{score.id}/thumbs/cover.jpg"
        score.save()
        
        mock_s3.return_value = {
            'url': f'https://example.com/download/{score.thumbnail_key}',
            'method': 'GET',
            'expires_in': 300
        }
        
        params = {
            'score_id': score.id,
            'file_type': 'thumbnail'
        }
        
        response = self.client.get(self.download_url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['s3_key'], score.thumbnail_key)
        self.assertEqual(response.data['file_type'], 'thumbnail')
    
    @patch('files.utils.S3Handler.generate_presigned_download_url')
    def test_download_url_page_thumbnail(self, mock_s3):
        """Test download URL generation for page thumbnail"""
        score = ScoreFactory(user=self.user, pages=10)
        page_num = 5
        expected_key = score.generate_page_thumbnail_s3_key(page_num)
        
        mock_s3.return_value = {
            'url': f'https://example.com/download/{expected_key}',
            'method': 'GET',
            'expires_in': 300
        }
        
        params = {
            'score_id': score.id,
            'file_type': 'page',
            'page': page_num
        }
        
        response = self.client.get(self.download_url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['s3_key'], expected_key)
        self.assertEqual(response.data['file_type'], 'page')
    
    def test_download_url_other_user_score_forbidden(self):
        """Test that users cannot download other users' scores"""
        other_user = UserFactory(username='otheruser', email='other@test.com')
        other_score = ScoreFactory(user=other_user)
        
        params = {
            'score_id': other_score.id,
            'file_type': 'original'
        }
        
        response = self.client.get(self.download_url, params)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_download_url_missing_page_parameter(self):
        """Test download URL request for page thumbnail without page number"""
        score = ScoreFactory(user=self.user)
        
        params = {
            'score_id': score.id,
            'file_type': 'page'
            # Missing 'page' parameter
        }
        
        response = self.client.get(self.download_url, params)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('page', response.data)
    
    def test_download_url_invalid_file_type(self):
        """Test download URL with invalid file type"""
        score = ScoreFactory(user=self.user)
        
        params = {
            'score_id': score.id,
            'file_type': 'invalid_type'
        }
        
        response = self.client.get(self.download_url, params)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file_type', response.data)
    
    def test_unauthenticated_access_forbidden(self):
        """Test that unauthenticated requests are forbidden"""
        self.client.force_authenticate(user=None)
        
        # Upload URL
        response = self.client.post(self.upload_url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Download URL
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Confirmation
        response = self.client.post(self.confirm_url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Cancellation
        response = self.client.post(self.cancel_url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)