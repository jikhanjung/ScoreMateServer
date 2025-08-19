"""
Tests for advanced features: Search, Filtering, Dashboard
"""
from django.test import TestCase
from django.db.models import Q
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.postgres.search import SearchVector

from core.models import User
from scores.models import Score
from setlists.models import Setlist, SetlistItem
from .factories import UserFactory, ScoreFactory


class ScoreFilteringTest(APITestCase):
    """Test Score API filtering capabilities"""
    
    def setUp(self):
        """Set up test data"""
        self.user = UserFactory()
        self.client = APIClient()
        
        # Authenticate user
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        # Create scores with different characteristics
        self.scores = [
            Score.objects.create(
                user=self.user,
                title='Symphony No. 1',
                composer='Beethoven',
                instrumentation='Full Orchestra',
                s3_key='symphony1.pdf',
                size_bytes=5 * 1024 * 1024,  # 5MB
                pages=20,
                tags=['classical', 'symphony', 'beethoven']
            ),
            Score.objects.create(
                user=self.user,
                title='Moonlight Sonata',
                composer='Beethoven',
                instrumentation='Piano Solo',
                s3_key='moonlight.pdf',
                size_bytes=2 * 1024 * 1024,  # 2MB
                pages=8,
                tags=['classical', 'piano', 'sonata']
            ),
            Score.objects.create(
                user=self.user,
                title='Jazz Improvisation',
                composer='John Coltrane',
                instrumentation='Saxophone Quartet',
                s3_key='jazz_improv.pdf',
                size_bytes=1 * 1024 * 1024,  # 1MB
                pages=4,
                tags=['jazz', 'improvisation', 'saxophone']
            ),
            Score.objects.create(
                user=self.user,
                title='Modern Composition',
                composer='Contemporary Artist',
                instrumentation='Chamber Ensemble',
                s3_key='modern.pdf',
                size_bytes=10 * 1024 * 1024,  # 10MB
                pages=35,
                tags=['modern', 'contemporary', 'chamber']
            ),
            Score.objects.create(
                user=self.user,
                title='String Quartet No. 5',
                composer='Beethoven',
                instrumentation='String Quartet',
                s3_key='quartet.pdf',
                size_bytes=3 * 1024 * 1024,  # 3MB
                pages=12,
                tags=['classical', 'chamber', 'strings']
            )
        ]
    
    def test_basic_filtering(self):
        """Test basic field filtering"""
        # Filter by composer
        response = self.client.get('/api/v1/scores/?composer=Beethoven')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 3)  # 3 Beethoven scores
        for result in results:
            self.assertEqual(result['composer'], 'Beethoven')
        
        # Filter by title (case-insensitive)
        response = self.client.get('/api/v1/scores/?title=symphony')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertIn('Symphony', results[0]['title'])
        
        # Filter by instrumentation
        response = self.client.get('/api/v1/scores/?instrumentation=piano')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'Moonlight Sonata')
    
    def test_tag_filtering(self):
        """Test tag-based filtering"""
        # Filter by single tag
        response = self.client.get('/api/v1/scores/?tags=classical')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 3)  # 3 classical scores
        
        # Filter by multiple tags (comma-separated)
        response = self.client.get('/api/v1/scores/?tags=classical,chamber')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)  # Only String Quartet matches both
        self.assertEqual(results[0]['title'], 'String Quartet No. 5')
        
        # Filter by has_tags boolean
        response = self.client.get('/api/v1/scores/?has_tags=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 5)  # All scores have tags
        
        # Create score without tags for testing
        Score.objects.create(
            user=self.user,
            title='Untagged Score',
            s3_key='untagged.pdf',
            size_bytes=1024000
        )
        
        response = self.client.get('/api/v1/scores/?has_tags=false')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'Untagged Score')
    
    def test_size_filtering(self):
        """Test file size filtering"""
        # Filter by minimum size (2MB+)
        response = self.client.get('/api/v1/scores/?size_mb_min=2')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 4)  # All except Jazz Improvisation (1MB)
        
        # Filter by maximum size (5MB or less)
        response = self.client.get('/api/v1/scores/?size_mb_max=5')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 4)  # All except Modern Composition (10MB)
        
        # Filter by size range (2-5MB)
        response = self.client.get('/api/v1/scores/?size_mb_min=2&size_mb_max=5')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 3)  # Symphony, Moonlight, String Quartet
    
    def test_page_filtering(self):
        """Test page count filtering"""
        # Filter by minimum pages
        response = self.client.get('/api/v1/scores/?pages_min=10')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 3)  # Symphony (20), Modern (35), String Quartet (12)
        
        # Filter by maximum pages
        response = self.client.get('/api/v1/scores/?pages_max=10')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 2)  # Moonlight (8), Jazz (4)
        
        # Filter by has_pages
        response = self.client.get('/api/v1/scores/?has_pages=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 5)  # All test scores have pages
    
    def test_date_filtering(self):
        """Test date-based filtering"""
        # Create score from yesterday (simulate older content)
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        old_score = Score.objects.create(
            user=self.user,
            title='Old Score',
            s3_key='old.pdf',
            size_bytes=1024000
        )
        old_score.created_at = timezone.now() - timedelta(days=1)
        old_score.save()
        
        # Filter by created_after (today)
        today = timezone.now().date()
        response = self.client.get(f'/api/v1/scores/?created_after={today}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 5)  # Only today's scores
        
        # Filter by created_before (today) - should get old score
        response = self.client.get(f'/api/v1/scores/?created_before={today}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'Old Score')
    
    def test_full_text_search(self):
        """Test PostgreSQL full-text search"""
        # Search across title, composer, instrumentation
        response = self.client.get('/api/v1/scores/?search=Beethoven')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 3)
        
        # Search for instrumentation terms
        response = self.client.get('/api/v1/scores/?search=Piano')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'Moonlight Sonata')
        
        # Search for partial matches
        response = self.client.get('/api/v1/scores/?search=Quartet')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        # Should find both String Quartet and Saxophone Quartet
        self.assertEqual(len(results), 2)
        
        # Search with multiple terms
        response = self.client.get('/api/v1/scores/?search=Modern Contemporary')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'Modern Composition')
    
    def test_combined_filtering(self):
        """Test combining multiple filters"""
        # Beethoven classical pieces with more than 10 pages
        response = self.client.get('/api/v1/scores/?composer=Beethoven&tags=classical&pages_min=10')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 2)  # Symphony and String Quartet
        
        # Small files under 2MB with specific tags
        response = self.client.get('/api/v1/scores/?size_mb_max=1.5&tags=jazz')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'Jazz Improvisation')
    
    def test_ordering(self):
        """Test custom ordering options"""
        # Order by size (ascending)
        response = self.client.get('/api/v1/scores/?ordering=size_mb')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        sizes = [result['size_bytes'] for result in results]
        self.assertEqual(sizes, sorted(sizes))
        
        # Order by size (descending)
        response = self.client.get('/api/v1/scores/?ordering=-size_mb')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        sizes = [result['size_bytes'] for result in results]
        self.assertEqual(sizes, sorted(sizes, reverse=True))
        
        # Order by pages
        response = self.client.get('/api/v1/scores/?ordering=pages')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        pages = [result['pages'] for result in results]
        self.assertEqual(pages, sorted(pages))
        
        # Order by title
        response = self.client.get('/api/v1/scores/?ordering=title')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        titles = [result['title'] for result in results]
        self.assertEqual(titles, sorted(titles))
    
    def test_random_ordering(self):
        """Test random ordering"""
        response1 = self.client.get('/api/v1/scores/?ordering=random')
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        response2 = self.client.get('/api/v1/scores/?ordering=random')
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        
        # Should have same number of results
        self.assertEqual(len(response1.data['results']), len(response2.data['results']))
        
        # Results should potentially be in different order (though not guaranteed)
        ids1 = [r['id'] for r in response1.data['results']]
        ids2 = [r['id'] for r in response2.data['results']]
        self.assertEqual(set(ids1), set(ids2))  # Same items, potentially different order


class ScoreStatisticsTest(APITestCase):
    """Test Score statistics endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.user = UserFactory()
        self.client = APIClient()
        
        # Authenticate user
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        # Create scores with varied characteristics
        self.scores = [
            Score.objects.create(
                user=self.user,
                title='Score 1',
                composer='Composer A',
                s3_key='score1.pdf',
                size_bytes=2 * 1024 * 1024,
                pages=10,
                tags=['tag1', 'tag2'],
                thumbnail_key='thumb1.jpg'
            ),
            Score.objects.create(
                user=self.user,
                title='Score 2',
                composer='Composer A',
                s3_key='score2.pdf',
                size_bytes=4 * 1024 * 1024,
                pages=20,
                tags=['tag1', 'tag3']
            ),
            Score.objects.create(
                user=self.user,
                title='Score 3',
                composer='Composer B',
                s3_key='score3.pdf',
                size_bytes=1 * 1024 * 1024,
                pages=5,
                tags=['tag2', 'tag4'],
                thumbnail_key='thumb3.jpg'
            )
        ]
    
    def test_score_statistics(self):
        """Test score statistics endpoint"""
        response = self.client.get('/api/v1/scores/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        
        # Check basic counts
        self.assertEqual(data['total_scores'], 3)
        self.assertEqual(data['scores_with_pages'], 3)
        self.assertEqual(data['scores_with_thumbnails'], 2)
        
        # Check size statistics
        expected_total_mb = (2 + 4 + 1)  # 7MB total
        self.assertEqual(data['size_statistics']['total_size_mb'], expected_total_mb)
        expected_avg_mb = expected_total_mb / 3
        self.assertAlmostEqual(data['size_statistics']['average_size_mb'], expected_avg_mb, places=2)
        
        # Check page statistics
        self.assertEqual(data['page_statistics']['total_pages'], 35)  # 10 + 20 + 5
        self.assertAlmostEqual(data['page_statistics']['average_pages'], 35/3, places=1)
        
        # Check composer statistics
        composers = {c['composer']: c['count'] for c in data['top_composers']}
        self.assertEqual(composers['Composer A'], 2)
        self.assertEqual(composers['Composer B'], 1)
        
        # Check tag statistics
        tags = {t['tag']: t['count'] for t in data['top_tags']}
        self.assertEqual(tags['tag1'], 2)
        self.assertEqual(tags['tag2'], 2)
        self.assertEqual(tags['tag3'], 1)
        self.assertEqual(tags['tag4'], 1)


class DashboardAPITest(APITestCase):
    """Test Dashboard API functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = UserFactory(
            total_quota_mb=100,
            used_quota_mb=30
        )
        self.client = APIClient()
        
        # Authenticate user
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        # Create scores
        self.scores = ScoreFactory.create_batch(5, user=self.user)
        
        # Create setlists
        self.setlist = Setlist.objects.create(
            user=self.user,
            title='Test Setlist',
            description='Test setlist description'
        )
        
        # Add items to setlist
        for i, score in enumerate(self.scores[:3]):
            SetlistItem.objects.create(
                setlist=self.setlist,
                score=score,
                order_index=i + 1
            )
    
    def test_dashboard_overview(self):
        """Test dashboard overview endpoint"""
        response = self.client.get('/api/v1/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        
        # Check user info
        self.assertEqual(data['user']['username'], self.user.username)
        self.assertEqual(data['user']['email'], self.user.email)
        
        # Check counts
        self.assertEqual(data['counts']['total_scores'], 5)
        self.assertEqual(data['counts']['total_setlists'], 1)
        
        # Check quota information
        self.assertEqual(data['quota']['used_mb'], 30)
        self.assertEqual(data['quota']['total_mb'], 100)
        self.assertEqual(data['quota']['available_mb'], 70)
        self.assertEqual(data['quota']['percentage_used'], 30.0)
        
        # Check that we have recent activity data
        self.assertIn('recent_activity', data)
        self.assertIn('scores_this_week', data['recent_activity'])
        self.assertIn('setlists_this_week', data['recent_activity'])
        
        # Check latest content
        self.assertIn('latest_content', data)
        self.assertIn('scores', data['latest_content'])
        self.assertIn('setlists', data['latest_content'])
        
        # Latest setlists should include item counts
        latest_setlists = data['latest_content']['setlists']
        self.assertEqual(len(latest_setlists), 1)
        self.assertEqual(latest_setlists[0]['item_count'], 3)
    
    def test_quota_details(self):
        """Test detailed quota information"""
        response = self.client.get('/api/v1/dashboard/quota_details/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        
        # Check quota summary
        self.assertIn('quota_summary', data)
        quota_summary = data['quota_summary']
        self.assertEqual(quota_summary['used_mb'], 30)
        self.assertEqual(quota_summary['total_mb'], 100)
        self.assertEqual(quota_summary['percentage_used'], 30.0)
        
        # Check size breakdown
        self.assertIn('size_breakdown', data)
        size_breakdown = data['size_breakdown']
        self.assertTrue(len(size_breakdown) > 0)
        
        # Each range should have required fields
        for range_data in size_breakdown:
            self.assertIn('range', range_data)
            self.assertIn('count', range_data)
            self.assertIn('total_size_mb', range_data)
        
        # Check monthly usage
        self.assertIn('monthly_usage', data)
        monthly_usage = data['monthly_usage']
        self.assertTrue(len(monthly_usage) > 0)
        
        # Check recommendations
        self.assertIn('recommendations', data)
        recommendations = data['recommendations']
        
        # Should have recommendations for missing thumbnails
        rec_types = [r['type'] for r in recommendations]
        # May include 'missing_thumbnails' if scores don't have thumbnails
    
    def test_quota_recommendations(self):
        """Test quota recommendation logic"""
        # Create score without thumbnail
        Score.objects.create(
            user=self.user,
            title='No Thumbnail Score',
            s3_key='no_thumb.pdf',
            size_bytes=1024000
        )
        
        # Create large file
        Score.objects.create(
            user=self.user,
            title='Large Score',
            s3_key='large.pdf',
            size_bytes=25 * 1024 * 1024  # 25MB
        )
        
        response = self.client.get('/api/v1/dashboard/quota_details/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        recommendations = response.data['recommendations']
        rec_types = [r['type'] for r in recommendations]
        
        # Should recommend thumbnail generation
        self.assertIn('missing_thumbnails', rec_types)
        
        # Should recommend large file review
        self.assertIn('large_files', rec_types)
    
    def test_high_quota_usage_warning(self):
        """Test high quota usage warnings"""
        # Set user quota to high usage (85%)
        self.user.used_quota_mb = 85
        self.user.save()
        
        response = self.client.get('/api/v1/dashboard/quota_details/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        recommendations = response.data['recommendations']
        rec_types = [r['type'] for r in recommendations]
        
        # Should have high usage warning
        self.assertIn('high_usage', rec_types)
    
    def test_dashboard_user_isolation(self):
        """Test that dashboard only shows current user's data"""
        # Create another user with data
        other_user = UserFactory()
        ScoreFactory.create_batch(10, user=other_user)
        
        response = self.client.get('/api/v1/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        
        # Should only show current user's counts
        self.assertEqual(data['counts']['total_scores'], 5)  # Not 15
        self.assertEqual(data['user']['username'], self.user.username)  # Not other user


class BulkOperationsTest(APITestCase):
    """Test bulk operations on scores"""
    
    def setUp(self):
        """Set up test data"""
        self.user = UserFactory()
        self.client = APIClient()
        
        # Authenticate user
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        # Create scores
        self.scores = [
            Score.objects.create(
                user=self.user,
                title=f'Score {i}',
                s3_key=f'score{i}.pdf',
                size_bytes=1024000,
                tags=['old_tag'] if i < 3 else []
            ) for i in range(5)
        ]
    
    def test_bulk_tag_add(self):
        """Test adding tags to multiple scores"""
        score_ids = [s.id for s in self.scores[:3]]
        data = {
            'score_ids': score_ids,
            'add_tags': ['new_tag', 'bulk_added']
        }
        
        response = self.client.post('/api/v1/scores/bulk_tag/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['updated_scores'], 3)
        
        # Verify tags were added
        for score in Score.objects.filter(id__in=score_ids):
            self.assertIn('new_tag', score.tags)
            self.assertIn('bulk_added', score.tags)
            self.assertIn('old_tag', score.tags)  # Should keep existing tags
    
    def test_bulk_tag_remove(self):
        """Test removing tags from multiple scores"""
        score_ids = [s.id for s in self.scores[:3]]
        data = {
            'score_ids': score_ids,
            'remove_tags': ['old_tag']
        }
        
        response = self.client.post('/api/v1/scores/bulk_tag/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['updated_scores'], 3)
        
        # Verify tags were removed
        for score in Score.objects.filter(id__in=score_ids):
            self.assertNotIn('old_tag', score.tags)
    
    def test_bulk_thumbnail_regeneration(self):
        """Test bulk thumbnail regeneration"""
        score_ids = [s.id for s in self.scores[:3]]
        data = {'score_ids': score_ids}
        
        response = self.client.post('/api/v1/scores/bulk_regenerate_thumbnails/', data)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        
        # Should return task information
        self.assertIn('task_ids', response.data)
        self.assertEqual(len(response.data['task_ids']), 3)
    
    def test_bulk_operations_user_isolation(self):
        """Test that bulk operations respect user isolation"""
        other_user = UserFactory()
        other_score = ScoreFactory(user=other_user)
        
        # Try to tag other user's score
        data = {
            'score_ids': [other_score.id],
            'add_tags': ['hacker_tag']
        }
        
        response = self.client.post('/api/v1/scores/bulk_tag/', data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)