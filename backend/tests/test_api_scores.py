"""
API tests for scores endpoints
"""
import pytest
import os
from rest_framework.test import APIClient
from rest_framework import status
from django.test import TestCase
from django.contrib.auth import get_user_model

from .factories import UserFactory, ScoreFactory
from scores.models import Score
from files.utils import S3Handler

User = get_user_model()


@pytest.mark.django_db
class ScoreAPITest(TestCase):
    """Test scores API endpoints"""
    
    def setUp(self):
        """Set up test client and data"""
        self.client = APIClient()
        self.user = UserFactory()
        self.other_user = UserFactory(username='otheruser', email='other@test.com')
        self.client.force_authenticate(user=self.user)
        
        # Initialize S3 handler
        self.s3_handler = S3Handler()
        
        # Upload test PDF file to MinIO
        self.test_pdf_path = os.path.join(os.path.dirname(__file__), 'LaGazzaLadra.pdf')
        self.upload_test_pdf_to_minio()
        
        # Create test scores with actual S3 keys
        self.score1 = ScoreFactory(
            user=self.user, 
            title="Symphony No. 1",
            s3_key=f'{self.user.id}/scores/test1/original.pdf'
        )
        self.score2 = ScoreFactory(
            user=self.user, 
            title="Piano Sonata",
            s3_key=f'{self.user.id}/scores/test2/original.pdf'
        ) 
        self.other_score = ScoreFactory(
            user=self.other_user, 
            title="Other User Score",
            s3_key=f'{self.other_user.id}/scores/test3/original.pdf'
        )
        
        self.list_url = '/api/v1/scores/'
        self.detail_url = lambda pk: f'/api/v1/scores/{pk}/'
    
    def upload_test_pdf_to_minio(self):
        """Upload test PDF file to MinIO for all test cases"""
        if not os.path.exists(self.test_pdf_path):
            self.skipTest(f"Test PDF file not found: {self.test_pdf_path}")
        
        with open(self.test_pdf_path, 'rb') as pdf_file:
            pdf_content = pdf_file.read()
        
        # Upload for different test cases
        test_keys = [
            f'{self.user.id}/scores/test1/original.pdf',
            f'{self.user.id}/scores/test2/original.pdf', 
            f'{self.other_user.id}/scores/test3/original.pdf',
            f'{self.user.id}/scores/new/original.pdf',  # For create test
            f'{self.user.id}/scores/test/original.pdf'   # For action tests
        ]
        
        for s3_key in test_keys:
            try:
                self.s3_handler.s3_client.put_object(
                    Bucket='scores',
                    Key=s3_key,
                    Body=pdf_content,
                    ContentType='application/pdf'
                )
            except Exception as e:
                # If upload fails, skip the test
                self.skipTest(f"Could not upload test PDF to MinIO: {e}")
    
    def tearDown(self):
        """Clean up uploaded test files"""
        # Clean up test files from MinIO
        test_keys = [
            f'{self.user.id}/scores/test1/original.pdf',
            f'{self.user.id}/scores/test2/original.pdf', 
            f'{self.other_user.id}/scores/test3/original.pdf',
            f'{self.user.id}/scores/new/original.pdf',
            f'{self.user.id}/scores/test/original.pdf'
        ]
        
        for s3_key in test_keys:
            try:
                self.s3_handler.s3_client.delete_object(
                    Bucket='scores',
                    Key=s3_key
                )
            except:
                pass  # Ignore cleanup errors
    
    def test_score_list_own_only(self):
        """Test that users only see their own scores"""
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        
        # Verify only user's scores are returned
        score_ids = [score['id'] for score in response.data['results']]
        self.assertIn(self.score1.id, score_ids)
        self.assertIn(self.score2.id, score_ids)
        self.assertNotIn(self.other_score.id, score_ids)
    
    def test_score_list_search(self):
        """Test searching scores by title"""
        response = self.client.get(self.list_url, {'search': 'Symphony'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], 'Symphony No. 1')
    
    def test_score_list_filter_by_composer(self):
        """Test filtering scores by composer"""
        # Update composer for one score
        self.score1.composer = 'Beethoven'
        self.score1.save()
        
        response = self.client.get(self.list_url, {'composer': 'Beethoven'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], self.score1.id)
    
    def test_score_detail_own(self):
        """Test retrieving own score details"""
        response = self.client.get(self.detail_url(self.score1.id))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.score1.id)
        self.assertEqual(response.data['title'], self.score1.title)
        self.assertIn('s3_key', response.data)
        self.assertIn('content_hash', response.data)
    
    def test_score_detail_other_user_forbidden(self):
        """Test that users cannot access other users' scores"""
        response = self.client.get(self.detail_url(self.other_score.id))
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_score_create_success(self):
        """Test creating a new score"""
        data = {
            'title': 'New Symphony',
            'composer': 'Test Composer',
            'instrumentation': 'Full Orchestra',
            's3_key': f'{self.user.id}/scores/new/original.pdf',
            'size_bytes': 5 * 1024 * 1024,  # 5MB
            'mime': 'application/pdf',
            'tags': ['classical', 'symphony'],
            'content_hash': 'abcd1234567890'
        }
        
        initial_quota = self.user.used_quota_mb
        response = self.client.post(self.list_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'New Symphony')
        self.assertEqual(response.data['composer'], 'Test Composer')
        
        # Verify quota was updated
        self.user.refresh_from_db()
        self.assertGreater(self.user.used_quota_mb, initial_quota)
    
    def test_score_create_invalid_s3_key(self):
        """Test creating score with invalid S3 key"""
        data = {
            'title': 'Invalid Score',
            's3_key': 'wrong/path/file.pdf',  # Should start with user.id
            'size_bytes': 1024 * 1024,
            'mime': 'application/pdf'
        }
        
        response = self.client.post(self.list_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('s3_key', response.data)
    
    def test_score_create_quota_exceeded(self):
        """Test creating score when quota is exceeded"""
        # Set user quota to very low value
        self.user.used_quota_mb = 199
        self.user.total_quota_mb = 200
        self.user.save()
        
        data = {
            'title': 'Large Score',
            's3_key': f'{self.user.id}/scores/large/original.pdf',
            'size_bytes': 10 * 1024 * 1024,  # 10MB - exceeds remaining quota
            'mime': 'application/pdf'
        }
        
        response = self.client.post(self.list_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('size_bytes', response.data)
    
    def test_score_update_own(self):
        """Test updating own score"""
        data = {
            'title': 'Updated Title',
            'tags': ['updated', 'classical']
        }
        
        response = self.client.patch(self.detail_url(self.score1.id), data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Updated Title')
        self.assertEqual(response.data['tags'], ['updated', 'classical'])
    
    def test_score_update_other_user_forbidden(self):
        """Test that users cannot update other users' scores"""
        data = {'title': 'Hacked Title'}
        
        response = self.client.patch(self.detail_url(self.other_score.id), data)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_score_delete_own(self):
        """Test deleting own score"""
        initial_quota = self.user.used_quota_mb
        score_size_mb = self.score1.size_bytes // (1024 * 1024)
        
        response = self.client.delete(self.detail_url(self.score1.id))
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify score was deleted
        self.assertFalse(Score.objects.filter(id=self.score1.id).exists())
        
        # Verify quota was updated
        self.user.refresh_from_db()
        expected_quota = initial_quota - score_size_mb
        self.assertEqual(self.user.used_quota_mb, expected_quota)
    
    def test_score_delete_other_user_forbidden(self):
        """Test that users cannot delete other users' scores"""
        response = self.client.delete(self.detail_url(self.other_score.id))
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Verify score was not deleted
        self.assertTrue(Score.objects.filter(id=self.other_score.id).exists())
    
    def test_score_regenerate_thumbnail(self):
        """Test regenerating thumbnail for score"""
        url = f'/api/v1/scores/{self.score1.id}/regenerate_thumbnail/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('message', response.data)
        self.assertEqual(response.data['score_id'], self.score1.id)
    
    def test_score_refresh_info(self):
        """Test refreshing PDF info for score"""
        url = f'/api/v1/scores/{self.score1.id}/refresh_info/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('message', response.data)
        self.assertEqual(response.data['score_id'], self.score1.id)
    
    def test_unauthenticated_access_forbidden(self):
        """Test that unauthenticated requests are forbidden"""
        self.client.force_authenticate(user=None)
        
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        response = self.client.post(self.list_url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_score_ordering(self):
        """Test score ordering (most recent first)"""
        # Scores should be ordered by -updated_at by default
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        scores = response.data['results']
        
        # Verify scores are in descending order by update time
        if len(scores) > 1:
            for i in range(len(scores) - 1):
                current = scores[i]['updated_at']
                next_score = scores[i + 1]['updated_at']
                self.assertGreaterEqual(current, next_score)