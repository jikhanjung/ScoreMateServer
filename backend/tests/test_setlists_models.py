"""
Tests for setlists models - Order management and statistics
"""
import pytest
from django.test import TestCase
from django.db import IntegrityError
from setlists.models import Setlist, SetlistItem
from .factories import UserFactory, ScoreFactory, SetlistFactory, SetlistItemFactory


@pytest.mark.django_db
class TestSetlistOrderManagement(TestCase):
    """Test SetlistItem automatic order management"""
    
    def setUp(self):
        """Set up test data"""
        self.user = UserFactory(email="setlist@test.com", username="setlistuser")
        self.setlist = SetlistFactory(user=self.user, title="Concert Setlist")
        
        # Create some scores
        self.score1 = ScoreFactory(user=self.user, title="First Piece", size_bytes=1024*1024)
        self.score2 = ScoreFactory(user=self.user, title="Second Piece", size_bytes=2*1024*1024)
        self.score3 = ScoreFactory(user=self.user, title="Third Piece", size_bytes=3*1024*1024)
    
    def test_automatic_order_assignment(self):
        """Test that SetlistItems get automatic order_index assignment"""
        # Add first item
        item1 = SetlistItem.objects.create(
            setlist=self.setlist,
            score=self.score1
        )
        self.assertEqual(item1.order_index, 1)
        
        # Add second item
        item2 = SetlistItem.objects.create(
            setlist=self.setlist,
            score=self.score2
        )
        self.assertEqual(item2.order_index, 2)
        
        # Add third item
        item3 = SetlistItem.objects.create(
            setlist=self.setlist,
            score=self.score3
        )
        self.assertEqual(item3.order_index, 3)
    
    def test_manual_order_assignment(self):
        """Test manual order_index assignment"""
        # Create item with specific order
        item1 = SetlistItem.objects.create(
            setlist=self.setlist,
            score=self.score1,
            order_index=5
        )
        self.assertEqual(item1.order_index, 5)
        
        # Next automatic assignment should be 6
        item2 = SetlistItem.objects.create(
            setlist=self.setlist,
            score=self.score2
        )
        self.assertEqual(item2.order_index, 6)
    
    def test_setlist_item_uniqueness(self):
        """Test that same score cannot be added to setlist twice"""
        # Add first item
        SetlistItem.objects.create(
            setlist=self.setlist,
            score=self.score1
        )
        
        # Try to add same score again - should raise IntegrityError
        with self.assertRaises(IntegrityError):
            SetlistItem.objects.create(
                setlist=self.setlist,
                score=self.score1
            )
    
    def test_setlist_item_ordering(self):
        """Test that SetlistItems are ordered by order_index"""
        # Add items in random order_index
        item3 = SetlistItem.objects.create(
            setlist=self.setlist,
            score=self.score3,
            order_index=3
        )
        item1 = SetlistItem.objects.create(
            setlist=self.setlist,
            score=self.score1,
            order_index=1
        )
        item2 = SetlistItem.objects.create(
            setlist=self.setlist,
            score=self.score2,
            order_index=2
        )
        
        # Get items in order
        ordered_items = self.setlist.items.all()
        self.assertEqual(list(ordered_items), [item1, item2, item3])
        self.assertEqual([item.order_index for item in ordered_items], [1, 2, 3])


@pytest.mark.django_db
class TestSetlistStatistics(TestCase):
    """Test Setlist statistics properties"""
    
    def setUp(self):
        """Set up test data"""
        self.user = UserFactory()
        self.setlist = SetlistFactory(user=self.user, title="Stats Test Setlist")
        
        # Create scores with different page counts
        self.score1 = ScoreFactory(user=self.user, title="Short Piece", size_bytes=1024*1024, pages=4)
        self.score2 = ScoreFactory(user=self.user, title="Medium Piece", size_bytes=2*1024*1024, pages=8) 
        self.score3 = ScoreFactory(user=self.user, title="Long Piece", size_bytes=3*1024*1024, pages=12)
    
    def test_empty_setlist_statistics(self):
        """Test statistics for empty setlist"""
        self.assertEqual(self.setlist.item_count, 0)
        self.assertEqual(self.setlist.total_pages, 0)
    
    def test_setlist_item_count(self):
        """Test item_count property"""
        # Add one item
        SetlistItem.objects.create(setlist=self.setlist, score=self.score1)
        self.assertEqual(self.setlist.item_count, 1)
        
        # Add second item
        SetlistItem.objects.create(setlist=self.setlist, score=self.score2)
        self.assertEqual(self.setlist.item_count, 2)
        
        # Add third item
        SetlistItem.objects.create(setlist=self.setlist, score=self.score3)
        self.assertEqual(self.setlist.item_count, 3)
    
    def test_setlist_total_pages(self):
        """Test total_pages property"""
        # Add items to setlist
        SetlistItem.objects.create(setlist=self.setlist, score=self.score1)  # 4 pages
        SetlistItem.objects.create(setlist=self.setlist, score=self.score2)  # 8 pages
        SetlistItem.objects.create(setlist=self.setlist, score=self.score3)  # 12 pages
        
        # Total should be 4 + 8 + 12 = 24
        self.assertEqual(self.setlist.total_pages, 24)
    
    def test_setlist_total_pages_with_none_pages(self):
        """Test total_pages when some scores have None pages"""
        # Create score with None pages
        score_no_pages = ScoreFactory(user=self.user, title="No Pages Score", pages=None)
        
        # Add items
        SetlistItem.objects.create(setlist=self.setlist, score=self.score1)  # 4 pages
        SetlistItem.objects.create(setlist=self.setlist, score=score_no_pages)  # None pages
        SetlistItem.objects.create(setlist=self.setlist, score=self.score2)  # 8 pages
        
        # Total should be 4 + 0 + 8 = 12 (None is treated as 0)
        self.assertEqual(self.setlist.total_pages, 12)


@pytest.mark.django_db
class TestSetlistModel(TestCase):
    """Test basic Setlist model functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = UserFactory()
    
    def test_setlist_creation(self):
        """Test creating a setlist"""
        setlist = SetlistFactory(
            user=self.user,
            title="My Concert",
            description="Evening concert repertoire"
        )
        
        self.assertEqual(setlist.user, self.user)
        self.assertEqual(setlist.title, "My Concert")
        self.assertEqual(setlist.description, "Evening concert repertoire")
        self.assertIsNotNone(setlist.created_at)
        self.assertIsNotNone(setlist.updated_at)
    
    def test_setlist_str_method(self):
        """Test Setlist __str__ method"""
        setlist = SetlistFactory(
            user=self.user,
            title="Test Setlist"
        )
        self.assertEqual(str(setlist), "Test Setlist")
    
    def test_setlist_ordering(self):
        """Test that setlists are ordered by updated_at descending"""
        # Create setlists
        setlist1 = SetlistFactory(user=self.user, title="First")
        setlist2 = SetlistFactory(user=self.user, title="Second") 
        setlist3 = SetlistFactory(user=self.user, title="Third")
        
        # Get all setlists (should be ordered by -updated_at)
        setlists = list(Setlist.objects.all())
        
        # Most recently created should be first
        self.assertEqual(setlists[0], setlist3)
        self.assertEqual(setlists[1], setlist2)
        self.assertEqual(setlists[2], setlist1)


@pytest.mark.django_db
class TestSetlistItemModel(TestCase):
    """Test SetlistItem model functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = UserFactory()
        self.setlist = SetlistFactory(user=self.user)
        self.score = ScoreFactory(user=self.user)
    
    def test_setlist_item_creation(self):
        """Test creating a setlist item"""
        item = SetlistItemFactory(
            setlist=self.setlist,
            score=self.score,
            notes="Play softly in the beginning"
        )
        
        self.assertEqual(item.setlist, self.setlist)
        self.assertEqual(item.score, self.score)
        self.assertEqual(item.notes, "Play softly in the beginning")
        self.assertIsNotNone(item.created_at)
        self.assertIsNotNone(item.updated_at)
    
    def test_setlist_item_str_method(self):
        """Test SetlistItem __str__ method"""
        item = SetlistItem.objects.create(
            setlist=self.setlist,
            score=self.score,
            order_index=1
        )
        
        expected_str = f"{self.setlist.title} - 1: {self.score.title}"
        self.assertEqual(str(item), expected_str)