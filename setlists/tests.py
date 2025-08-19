"""
Tests for setlists app
"""
import json
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Setlist, SetlistItem
from scores.models import Score


User = get_user_model()


class SetlistModelTest(TestCase):
    """Test Setlist model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.score1 = Score.objects.create(
            user=self.user,
            title='Test Score 1',
            composer='Test Composer',
            s3_key='test1.pdf',
            size_bytes=1024000,
            pages=10
        )
        
        self.score2 = Score.objects.create(
            user=self.user,
            title='Test Score 2',
            composer='Another Composer',
            s3_key='test2.pdf',
            size_bytes=2048000,
            pages=15
        )
    
    def test_create_setlist(self):
        """Test creating a setlist"""
        setlist = Setlist.objects.create(
            user=self.user,
            title='My Concert',
            description='Test concert setlist'
        )
        
        self.assertEqual(setlist.title, 'My Concert')
        self.assertEqual(setlist.user, self.user)
        self.assertEqual(setlist.item_count, 0)
        self.assertEqual(setlist.total_pages, 0)
    
    def test_setlist_with_items(self):
        """Test setlist with items"""
        setlist = Setlist.objects.create(
            user=self.user,
            title='My Concert'
        )
        
        # Add items
        item1 = SetlistItem.objects.create(
            setlist=setlist,
            score=self.score1,
            order_index=1,
            notes='Opening piece'
        )
        
        item2 = SetlistItem.objects.create(
            setlist=setlist,
            score=self.score2,
            order_index=2,
            notes='Main piece'
        )
        
        # Refresh setlist to get updated computed fields
        setlist.refresh_from_db()
        
        self.assertEqual(setlist.item_count, 2)
        self.assertEqual(setlist.total_pages, 25)  # 10 + 15 pages
        
        # Test ordering
        items = list(setlist.items.all())
        self.assertEqual(items[0], item1)
        self.assertEqual(items[1], item2)
    
    def test_setlist_string_representation(self):
        """Test string representation"""
        setlist = Setlist.objects.create(
            user=self.user,
            title='My Concert'
        )
        
        expected = f"My Concert (testuser - 0 items)"
        self.assertEqual(str(setlist), expected)


class SetlistItemModelTest(TestCase):
    """Test SetlistItem model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.score = Score.objects.create(
            user=self.user,
            title='Test Score',
            s3_key='test.pdf',
            size_bytes=1024000
        )
        
        self.setlist = Setlist.objects.create(
            user=self.user,
            title='Test Setlist'
        )
    
    def test_create_setlist_item(self):
        """Test creating a setlist item"""
        item = SetlistItem.objects.create(
            setlist=self.setlist,
            score=self.score,
            order_index=1,
            notes='Test notes'
        )
        
        self.assertEqual(item.setlist, self.setlist)
        self.assertEqual(item.score, self.score)
        self.assertEqual(item.order_index, 1)
        self.assertEqual(item.notes, 'Test notes')
    
    def test_setlist_item_string_representation(self):
        """Test string representation"""
        item = SetlistItem.objects.create(
            setlist=self.setlist,
            score=self.score,
            order_index=1
        )
        
        expected = f"Test Setlist - 1: Test Score"
        self.assertEqual(str(item), expected)
    
    def test_unique_score_in_setlist(self):
        """Test that the same score cannot appear multiple times in same setlist"""
        item1 = SetlistItem.objects.create(
            setlist=self.setlist,
            score=self.score,
            order_index=1,
            notes='First performance'
        )
        
        # Try to add the same score again - should fail due to unique constraint
        with self.assertRaises(Exception):  # IntegrityError
            SetlistItem.objects.create(
                setlist=self.setlist,
                score=self.score,
                order_index=2,
                notes='Encore'
            )
        
        # Should only have one item
        self.assertEqual(SetlistItem.objects.filter(setlist=self.setlist).count(), 1)


class SetlistAPITest(APITestCase):
    """Test Setlist API endpoints"""
    
    def setUp(self):
        # Create users
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='pass123'
        )
        
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='pass123'
        )
        
        # Create scores for user1
        self.score1 = Score.objects.create(
            user=self.user1,
            title='Score 1',
            s3_key='score1.pdf',
            size_bytes=1024000,
            pages=10
        )
        
        self.score2 = Score.objects.create(
            user=self.user1,
            title='Score 2',
            s3_key='score2.pdf',
            size_bytes=2048000,
            pages=15
        )
        
        # Create score for user2
        self.user2_score = Score.objects.create(
            user=self.user2,
            title='User2 Score',
            s3_key='user2_score.pdf',
            size_bytes=1024000
        )
        
        # Create setlists
        self.setlist1 = Setlist.objects.create(
            user=self.user1,
            title='Concert 1',
            description='First concert'
        )
        
        self.setlist2 = Setlist.objects.create(
            user=self.user2,
            title='User2 Concert',
            description='Another user\'s concert'
        )
        
        # Setup authentication
        self.client = APIClient()
    
    def authenticate_user(self, user):
        """Helper to authenticate a user"""
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    def test_list_setlists(self):
        """Test listing setlists"""
        self.authenticate_user(self.user1)
        
        url = reverse('setlist-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], 'Concert 1')
    
    def test_create_setlist(self):
        """Test creating a setlist"""
        self.authenticate_user(self.user1)
        
        url = reverse('setlist-list')
        data = {
            'title': 'New Concert',
            'description': 'A new concert setlist'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'New Concert')
        self.assertEqual(response.data['description'], 'A new concert setlist')
        self.assertEqual(response.data['item_count'], 0)
        
        # Verify in database
        setlist = Setlist.objects.get(id=response.data['id'])
        self.assertEqual(setlist.user, self.user1)
    
    def test_retrieve_setlist(self):
        """Test retrieving a specific setlist"""
        self.authenticate_user(self.user1)
        
        url = reverse('setlist-detail', kwargs={'pk': self.setlist1.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Concert 1')
        self.assertIn('items', response.data)
    
    def test_update_setlist(self):
        """Test updating a setlist"""
        self.authenticate_user(self.user1)
        
        url = reverse('setlist-detail', kwargs={'pk': self.setlist1.pk})
        data = {
            'title': 'Updated Concert',
            'description': 'Updated description'
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Updated Concert')
        
        # Verify in database
        self.setlist1.refresh_from_db()
        self.assertEqual(self.setlist1.title, 'Updated Concert')
    
    def test_delete_setlist(self):
        """Test deleting a setlist"""
        self.authenticate_user(self.user1)
        
        url = reverse('setlist-detail', kwargs={'pk': self.setlist1.pk})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Setlist.objects.filter(pk=self.setlist1.pk).exists())
    
    def test_add_item_to_setlist(self):
        """Test adding an item to a setlist"""
        self.authenticate_user(self.user1)
        
        url = reverse('setlist-add-item', kwargs={'pk': self.setlist1.pk})
        data = {
            'score_id': self.score1.id,
            'notes': 'Opening piece'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['score']['id'], self.score1.id)
        self.assertEqual(response.data['notes'], 'Opening piece')
        self.assertEqual(response.data['position'], 1)
        
        # Verify in database
        item = SetlistItem.objects.get(setlist=self.setlist1, score=self.score1)
        self.assertEqual(item.notes, 'Opening piece')
    
    def test_add_multiple_items(self):
        """Test adding multiple items maintains correct positions"""
        self.authenticate_user(self.user1)
        
        # Add first item
        url = reverse('setlist-add-item', kwargs={'pk': self.setlist1.pk})
        data1 = {'score_id': self.score1.id, 'notes': 'First piece'}
        response1 = self.client.post(url, data1)
        self.assertEqual(response1.data['position'], 1)
        
        # Add second item
        data2 = {'score_id': self.score2.id, 'notes': 'Second piece'}
        response2 = self.client.post(url, data2)
        self.assertEqual(response2.data['position'], 2)
        
        # Verify setlist statistics
        self.setlist1.refresh_from_db()
        self.assertEqual(self.setlist1.item_count, 2)
        self.assertEqual(self.setlist1.total_pages, 25)  # 10 + 15
    
    def test_insert_item_at_position(self):
        """Test inserting an item at a specific position"""
        self.authenticate_user(self.user1)
        
        # Add initial items
        SetlistItem.objects.create(setlist=self.setlist1, score=self.score1, position=1)
        SetlistItem.objects.create(setlist=self.setlist1, score=self.score2, position=2)
        
        # Insert new item at position 2
        url = reverse('setlist-add-item', kwargs={'pk': self.setlist1.pk})
        data = {
            'score_id': self.score1.id,  # Can reuse same score
            'position': 2,
            'notes': 'Inserted piece'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['position'], 2)
        
        # Verify positions are correct
        items = list(SetlistItem.objects.filter(setlist=self.setlist1).order_by('position'))
        self.assertEqual(len(items), 3)
        self.assertEqual(items[1].notes, 'Inserted piece')
        self.assertEqual(items[2].position, 3)  # Should be shifted
    
    def test_remove_item_from_setlist(self):
        """Test removing an item from a setlist"""
        self.authenticate_user(self.user1)
        
        # Add an item first
        item = SetlistItem.objects.create(
            setlist=self.setlist1,
            score=self.score1,
            position=1
        )
        
        url = reverse('setlist-remove-item', kwargs={'pk': self.setlist1.pk})
        data = {'item_id': item.id}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(SetlistItem.objects.filter(pk=item.pk).exists())
    
    def test_reorder_items(self):
        """Test reordering items in a setlist"""
        self.authenticate_user(self.user1)
        
        # Create items
        item1 = SetlistItem.objects.create(setlist=self.setlist1, score=self.score1, position=1)
        item2 = SetlistItem.objects.create(setlist=self.setlist1, score=self.score2, position=2)
        
        url = reverse('setlist-reorder-items', kwargs={'pk': self.setlist1.pk})
        data = {
            'item_orders': [
                {'item_id': item2.id, 'position': 1},
                {'item_id': item1.id, 'position': 2}
            ]
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify order changed
        item1.refresh_from_db()
        item2.refresh_from_db()
        self.assertEqual(item2.position, 1)
        self.assertEqual(item1.position, 2)
    
    def test_duplicate_setlist(self):
        """Test duplicating a setlist"""
        self.authenticate_user(self.user1)
        
        # Add items to original setlist
        SetlistItem.objects.create(setlist=self.setlist1, score=self.score1, position=1)
        SetlistItem.objects.create(setlist=self.setlist1, score=self.score2, position=2)
        
        url = reverse('setlist-duplicate', kwargs={'pk': self.setlist1.pk})
        data = {'new_title': 'Concert 1 Copy'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Concert 1 Copy')
        self.assertEqual(response.data['item_count'], 2)
        
        # Verify new setlist exists
        new_setlist = Setlist.objects.get(id=response.data['id'])
        self.assertEqual(new_setlist.items.count(), 2)
    
    def test_user_isolation(self):
        """Test that users can only access their own setlists"""
        self.authenticate_user(self.user1)
        
        # Try to access user2's setlist
        url = reverse('setlist-detail', kwargs={'pk': self.setlist2.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Try to add user2's score to user1's setlist
        url = reverse('setlist-add-item', kwargs={'pk': self.setlist1.pk})
        data = {'score_id': self.user2_score.id}
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not found', str(response.data).lower())
    
    def test_validation_errors(self):
        """Test various validation errors"""
        self.authenticate_user(self.user1)
        
        # Test empty title
        url = reverse('setlist-list')
        data = {'title': '', 'description': 'Test'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test adding non-existent score
        url = reverse('setlist-add-item', kwargs={'pk': self.setlist1.pk})
        data = {'score_id': 99999}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test removing non-existent item
        url = reverse('setlist-remove-item', kwargs={'pk': self.setlist1.pk})
        data = {'item_id': 99999}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_unauthenticated_access(self):
        """Test that unauthenticated users cannot access setlists"""
        url = reverse('setlist-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)