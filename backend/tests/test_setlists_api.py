"""
API integration tests for Setlists
"""
import json
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import User
from scores.models import Score
from setlists.models import Setlist, SetlistItem
from .factories import UserFactory, ScoreFactory


class SetlistAPIIntegrationTest(APITestCase):
    """Integration tests for Setlist API with complex scenarios"""
    
    def setUp(self):
        """Set up test data"""
        # Create users
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        
        # Create scores for user1
        self.scores = ScoreFactory.create_batch(5, user=self.user1)
        
        # Create setlist for user1
        self.setlist = Setlist.objects.create(
            user=self.user1,
            title='Concert Setlist',
            description='Main concert program'
        )
        
        # Add some items
        for i, score in enumerate(self.scores[:3]):
            SetlistItem.objects.create(
                setlist=self.setlist,
                score=score,
                order_index=i + 1,
                notes=f'Notes for position {i + 1}'
            )
        
        self.client = APIClient()
    
    def authenticate_user(self, user):
        """Helper to authenticate a user"""
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    def test_complete_setlist_workflow(self):
        """Test complete setlist creation and management workflow"""
        self.authenticate_user(self.user1)
        
        # 1. Create new setlist
        create_data = {
            'title': 'Evening Concert',
            'description': 'Special evening performance'
        }
        response = self.client.post('/api/v1/setlists/', create_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        setlist_id = response.data['id']
        
        # 2. Add items to setlist
        for i, score in enumerate(self.scores[:3]):
            add_data = {
                'score_id': score.id,
                'notes': f'Performance note {i + 1}'
            }
            response = self.client.post(f'/api/v1/setlists/{setlist_id}/add_item/', add_data)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(response.data['position'], i + 1)
        
        # 3. Retrieve setlist with items
        response = self.client.get(f'/api/v1/setlists/{setlist_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['items']), 3)
        self.assertEqual(response.data['item_count'], 3)
        
        # 4. Reorder items
        items = response.data['items']
        reorder_data = {
            'item_orders': [
                {'item_id': items[2]['id'], 'position': 1},
                {'item_id': items[0]['id'], 'position': 2},
                {'item_id': items[1]['id'], 'position': 3}
            ]
        }
        response = self.client.post(f'/api/v1/setlists/{setlist_id}/reorder_items/', reorder_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 5. Verify new order
        response = self.client.get(f'/api/v1/setlists/{setlist_id}/')
        new_items = response.data['items']
        self.assertEqual(new_items[0]['id'], items[2]['id'])  # Third item is now first
        
        # 6. Remove middle item
        remove_data = {'item_id': new_items[1]['id']}
        response = self.client.post(f'/api/v1/setlists/{setlist_id}/remove_item/', remove_data)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # 7. Verify item removed and positions adjusted
        response = self.client.get(f'/api/v1/setlists/{setlist_id}/')
        final_items = response.data['items']
        self.assertEqual(len(final_items), 2)
        self.assertEqual(final_items[0]['position'], 1)
        self.assertEqual(final_items[1]['position'], 2)
        
        # 8. Duplicate setlist
        duplicate_data = {'new_title': 'Evening Concert - Copy'}
        response = self.client.post(f'/api/v1/setlists/{setlist_id}/duplicate/', duplicate_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Evening Concert - Copy')
        self.assertEqual(response.data['item_count'], 2)
        
        # 9. Update setlist
        update_data = {
            'title': 'Evening Concert - Updated',
            'description': 'Updated description'
        }
        response = self.client.patch(f'/api/v1/setlists/{setlist_id}/', update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Evening Concert - Updated')
    
    def test_setlist_statistics(self):
        """Test setlist statistics calculation"""
        self.authenticate_user(self.user1)
        
        # Get setlist with statistics
        response = self.client.get(f'/api/v1/setlists/{self.setlist.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertEqual(data['item_count'], 3)
        
        # Calculate expected total pages
        expected_pages = sum(score.pages or 0 for score in self.scores[:3])
        self.assertEqual(data['total_pages'], expected_pages)
        
        # Check items are properly nested
        self.assertEqual(len(data['items']), 3)
        for item in data['items']:
            self.assertIn('score', item)
            self.assertIn('title', item['score'])
            self.assertIn('position', item)
            self.assertIn('notes', item)
    
    def test_setlist_filtering_and_ordering(self):
        """Test setlist filtering and ordering"""
        self.authenticate_user(self.user1)
        
        # Create more setlists with different characteristics
        recent_setlist = Setlist.objects.create(
            user=self.user1,
            title='Recent Concert',
            description='New setlist'
        )
        
        old_setlist = Setlist.objects.create(
            user=self.user1,
            title='Old Concert',
            description='Archived setlist'
        )
        
        # Test ordering by creation time (newest first)
        response = self.client.get('/api/v1/setlists/?ordering=-created_at')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertTrue(len(results) >= 3)
        # Most recent should be first
        self.assertEqual(results[0]['id'], recent_setlist.id)
        
        # Test ordering by title
        response = self.client.get('/api/v1/setlists/?ordering=title')
        results = response.data['results']
        titles = [item['title'] for item in results]
        self.assertEqual(titles, sorted(titles))
        
        # Test search functionality (if implemented in future)
        response = self.client.get('/api/v1/setlists/?search=Concert')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_setlist_pagination(self):
        """Test setlist pagination"""
        self.authenticate_user(self.user1)
        
        # Create many setlists to test pagination
        for i in range(25):
            Setlist.objects.create(
                user=self.user1,
                title=f'Concert {i:02d}',
                description=f'Concert number {i}'
            )
        
        # Test first page
        response = self.client.get('/api/v1/setlists/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
        self.assertIn('results', response.data)
        
        # Should have 20 items per page (default)
        self.assertEqual(len(response.data['results']), 20)
        self.assertTrue(response.data['count'] >= 25)
        
        # Test second page
        response = self.client.get('/api/v1/setlists/?page=2')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should have remaining items
        self.assertTrue(len(response.data['results']) >= 5)
    
    def test_complex_item_operations(self):
        """Test complex item operations"""
        self.authenticate_user(self.user1)
        
        # Insert item at specific position
        insert_data = {
            'score_id': self.scores[3].id,
            'position': 2,  # Insert between first and second
            'notes': 'Inserted piece'
        }
        response = self.client.post(f'/api/v1/setlists/{self.setlist.id}/add_item/', insert_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['position'], 2)
        
        # Verify all positions are correct
        response = self.client.get(f'/api/v1/setlists/{self.setlist.id}/')
        items = response.data['items']
        self.assertEqual(len(items), 4)
        
        positions = [item['position'] for item in items]
        self.assertEqual(positions, [1, 2, 3, 4])
        self.assertEqual(items[1]['notes'], 'Inserted piece')
        
        # Add duplicate score (should be allowed)
        duplicate_data = {
            'score_id': self.scores[0].id,  # Same as first item
            'notes': 'Encore performance'
        }
        response = self.client.post(f'/api/v1/setlists/{self.setlist.id}/add_item/', duplicate_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['position'], 5)
        
        # Verify duplicate is allowed
        response = self.client.get(f'/api/v1/setlists/{self.setlist.id}/')
        items = response.data['items']
        self.assertEqual(len(items), 5)
        
        # Check that first and last items have the same score
        self.assertEqual(items[0]['score']['id'], items[4]['score']['id'])
    
    def test_error_handling(self):
        """Test various error conditions"""
        self.authenticate_user(self.user1)
        
        # Try to add non-existent score
        bad_data = {'score_id': 99999}
        response = self.client.post(f'/api/v1/setlists/{self.setlist.id}/add_item/', bad_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        
        # Try to remove non-existent item
        bad_remove_data = {'item_id': 99999}
        response = self.client.post(f'/api/v1/setlists/{self.setlist.id}/remove_item/', bad_remove_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Try to reorder with invalid item IDs
        bad_reorder_data = {
            'item_orders': [
                {'item_id': 99999, 'position': 1}
            ]
        }
        response = self.client.post(f'/api/v1/setlists/{self.setlist.id}/reorder_items/', bad_reorder_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Try to access another user's setlist
        self.authenticate_user(self.user2)
        response = self.client.get(f'/api/v1/setlists/{self.setlist.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_setlist_performance(self):
        """Test setlist API performance with many items"""
        self.authenticate_user(self.user1)
        
        # Create setlist with many items
        large_setlist = Setlist.objects.create(
            user=self.user1,
            title='Large Concert',
            description='Concert with many pieces'
        )
        
        # Add 50 items
        for i in range(50):
            score = self.scores[i % len(self.scores)]  # Cycle through available scores
            SetlistItem.objects.create(
                setlist=large_setlist,
                score=score,
                position=i + 1,
                notes=f'Piece {i + 1}'
            )
        
        # Test retrieval performance
        response = self.client.get(f'/api/v1/setlists/{large_setlist.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['items']), 50)
        self.assertEqual(response.data['item_count'], 50)
        
        # Test that all items have proper nesting
        for item in response.data['items']:
            self.assertIn('score', item)
            self.assertIn('id', item['score'])
            self.assertIn('title', item['score'])
    
    def test_setlist_data_consistency(self):
        """Test data consistency across operations"""
        self.authenticate_user(self.user1)
        
        initial_count = self.setlist.item_count
        initial_pages = self.setlist.total_pages
        
        # Add item and verify counts update
        add_data = {
            'score_id': self.scores[4].id,
            'notes': 'Additional piece'
        }
        response = self.client.post(f'/api/v1/setlists/{self.setlist.id}/add_item/', add_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify setlist statistics are updated
        self.setlist.refresh_from_db()
        self.assertEqual(self.setlist.item_count, initial_count + 1)
        
        expected_new_pages = initial_pages + (self.scores[4].pages or 0)
        self.assertEqual(self.setlist.total_pages, expected_new_pages)
        
        # Remove item and verify counts update
        item = SetlistItem.objects.filter(setlist=self.setlist).last()
        remove_data = {'item_id': item.id}
        response = self.client.post(f'/api/v1/setlists/{self.setlist.id}/remove_item/', remove_data)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify counts are back to original
        self.setlist.refresh_from_db()
        self.assertEqual(self.setlist.item_count, initial_count)
        self.assertEqual(self.setlist.total_pages, initial_pages)