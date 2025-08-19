"""
Simple Setlist API tests - corrected field names
"""
from django.test import TestCase
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import User
from scores.models import Score
from setlists.models import Setlist, SetlistItem
from .factories import UserFactory, ScoreFactory


class SetlistModelTest(TestCase):
    """Test Setlist model functionality"""
    
    def setUp(self):
        self.user = UserFactory()
        self.score1 = ScoreFactory(user=self.user, pages=10)
        self.score2 = ScoreFactory(user=self.user, pages=15)
    
    def test_create_setlist_with_items(self):
        """Test creating setlist with items"""
        setlist = Setlist.objects.create(
            user=self.user,
            title='Test Concert'
        )
        
        # Add items
        SetlistItem.objects.create(
            setlist=setlist,
            score=self.score1,
            order_index=1
        )
        SetlistItem.objects.create(
            setlist=setlist,
            score=self.score2,
            order_index=2
        )
        
        self.assertEqual(setlist.item_count, 2)
        self.assertEqual(setlist.total_pages, 25)  # 10 + 15


class SetlistAPIBasicTest(APITestCase):
    """Basic Setlist API tests"""
    
    def setUp(self):
        self.user = UserFactory()
        self.scores = ScoreFactory.create_batch(3, user=self.user)
        self.client = APIClient()
        
        # Authenticate
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    def test_create_setlist(self):
        """Test creating a setlist"""
        data = {
            'title': 'My Concert',
            'description': 'Test concert'
        }
        
        response = self.client.post('/api/v1/setlists/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'My Concert')
    
    def test_list_setlists(self):
        """Test listing setlists"""
        Setlist.objects.create(user=self.user, title='Concert 1')
        Setlist.objects.create(user=self.user, title='Concert 2')
        
        response = self.client.get('/api/v1/setlists/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_add_item_to_setlist(self):
        """Test adding item to setlist"""
        setlist = Setlist.objects.create(user=self.user, title='Test')
        
        data = {
            'score_id': self.scores[0].id,
            'notes': 'Opening piece'
        }
        
        response = self.client.post(f'/api/v1/setlists/{setlist.id}/add_item/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check that item was created
        item = SetlistItem.objects.get(setlist=setlist)
        self.assertEqual(item.score, self.scores[0])
        self.assertEqual(item.notes, 'Opening piece')
    
    def test_remove_item_from_setlist(self):
        """Test removing item from setlist"""
        setlist = Setlist.objects.create(user=self.user, title='Test')
        item = SetlistItem.objects.create(
            setlist=setlist,
            score=self.scores[0]
        )
        
        response = self.client.delete(f'/api/v1/setlists/{setlist.id}/items/{item.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Check that item was removed
        self.assertFalse(SetlistItem.objects.filter(id=item.id).exists())
    
    def test_user_isolation(self):
        """Test that users can only access their own setlists"""
        other_user = UserFactory()
        other_setlist = Setlist.objects.create(user=other_user, title='Other')
        
        response = self.client.get(f'/api/v1/setlists/{other_setlist.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class SetlistItemConstraintTest(TestCase):
    """Test SetlistItem model constraints"""
    
    def setUp(self):
        self.user = UserFactory()
        self.score = ScoreFactory(user=self.user)
        self.setlist = Setlist.objects.create(user=self.user, title='Test')
    
    def test_unique_score_constraint(self):
        """Test that same score cannot be added twice to same setlist"""
        # Add score once
        SetlistItem.objects.create(
            setlist=self.setlist,
            score=self.score,
            order_index=1
        )
        
        # Try to add again - should fail
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            SetlistItem.objects.create(
                setlist=self.setlist,
                score=self.score,
                order_index=2
            )
    
    def test_auto_order_index(self):
        """Test that order_index is auto-assigned"""
        item = SetlistItem.objects.create(
            setlist=self.setlist,
            score=self.score
        )
        
        # Should auto-assign order_index
        self.assertIsNotNone(item.order_index)
        self.assertEqual(item.order_index, 1)