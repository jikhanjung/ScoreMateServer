"""
Tests for scores models - S3 key generation and core functionality
"""
import pytest
from django.test import TestCase
from scores.models import Score
from .factories import UserFactory, ScoreFactory


@pytest.mark.django_db
class TestScoreS3KeyGeneration(TestCase):
    """Test Score model S3 key generation methods"""
    
    def setUp(self):
        """Set up test data"""
        self.user = UserFactory(email="score@test.com", username="scoreuser")
        self.score = ScoreFactory(
            user=self.user,
            title="Test Symphony",
            size_bytes=5 * 1024 * 1024  # 5MB
        )
    
    def test_s3_key_generation(self):
        """Test generate_s3_key method"""
        expected_key = f"{self.user.id}/scores/{self.score.id}/original.pdf"
        actual_key = self.score.generate_s3_key()
        self.assertEqual(actual_key, expected_key)
    
    def test_thumbnail_s3_key_generation(self):
        """Test generate_thumbnail_s3_key method"""
        expected_key = f"{self.user.id}/scores/{self.score.id}/thumbs/cover.jpg"
        actual_key = self.score.generate_thumbnail_s3_key()
        self.assertEqual(actual_key, expected_key)
    
    def test_page_thumbnail_s3_key_generation(self):
        """Test generate_page_thumbnail_s3_key method"""
        # Test first page
        expected_key_1 = f"{self.user.id}/scores/{self.score.id}/thumbs/page-0001.jpg"
        actual_key_1 = self.score.generate_page_thumbnail_s3_key(1)
        self.assertEqual(actual_key_1, expected_key_1)
        
        # Test page 25
        expected_key_25 = f"{self.user.id}/scores/{self.score.id}/thumbs/page-0025.jpg"
        actual_key_25 = self.score.generate_page_thumbnail_s3_key(25)
        self.assertEqual(actual_key_25, expected_key_25)
        
        # Test page 100
        expected_key_100 = f"{self.user.id}/scores/{self.score.id}/thumbs/page-0100.jpg"
        actual_key_100 = self.score.generate_page_thumbnail_s3_key(100)
        self.assertEqual(actual_key_100, expected_key_100)
    
    def test_size_mb_property(self):
        """Test size_mb property calculation"""
        # 5MB file
        expected_size_mb = 5.0
        self.assertAlmostEqual(self.score.size_mb, expected_size_mb, places=2)
        
        # Test different file sizes
        small_score = ScoreFactory(
            user=self.user,
            title="Small Score",
            composer="Test Composer",
            s3_key="test/small.pdf",
            size_bytes=512 * 1024  # 512KB = 0.5MB
        )
        self.assertAlmostEqual(small_score.size_mb, 0.5, places=2)
        
        large_score = ScoreFactory(
            user=self.user,
            title="Large Score",
            composer="Test Composer", 
            s3_key="test/large.pdf",
            size_bytes=100 * 1024 * 1024  # 100MB
        )
        self.assertAlmostEqual(large_score.size_mb, 100.0, places=2)


@pytest.mark.django_db
class TestScoreModel(TestCase):
    """Test Score model basic functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = UserFactory()
    
    def test_score_creation(self):
        """Test creating a score with required fields"""
        score = ScoreFactory(
            user=self.user,
            title="Beethoven Symphony No. 9",
            composer="Ludwig van Beethoven",
            instrumentation="Full Orchestra",
            size_bytes=15 * 1024 * 1024,  # 15MB
            pages=45
        )
        
        self.assertEqual(score.user, self.user)
        self.assertEqual(score.title, "Beethoven Symphony No. 9")
        self.assertEqual(score.composer, "Ludwig van Beethoven")
        self.assertEqual(score.instrumentation, "Full Orchestra")
        self.assertEqual(score.pages, 45)
        self.assertEqual(score.mime, "application/pdf")
        self.assertIsNotNone(score.created_at)
        self.assertIsNotNone(score.updated_at)
    
    def test_score_str_method(self):
        """Test Score __str__ method"""
        # Score with composer
        score_with_composer = ScoreFactory(
            user=self.user,
            title="Moonlight Sonata",
            composer="Beethoven"
        )
        expected_str = "Moonlight Sonata - Beethoven"
        self.assertEqual(str(score_with_composer), expected_str)
        
        # Score without composer
        score_without_composer = ScoreFactory(
            user=self.user,
            title="Unknown Piece",
            composer=""
        )
        expected_str = "Unknown Piece"
        self.assertEqual(str(score_without_composer), expected_str)
    
    def test_tags_field(self):
        """Test tags ArrayField functionality"""
        score = ScoreFactory(
            user=self.user,
            title="Tagged Score",
            tags=["classical", "piano", "beginner"]
        )
        
        # Test tags are stored correctly
        self.assertEqual(len(score.tags), 3)
        self.assertIn("classical", score.tags)
        self.assertIn("piano", score.tags)
        self.assertIn("beginner", score.tags)
        
        # Test adding tags
        score.tags.append("favorite")
        score.save()
        
        # Refresh from database
        score.refresh_from_db()
        self.assertEqual(len(score.tags), 4)
        self.assertIn("favorite", score.tags)
    
    def test_content_hash_field(self):
        """Test content hash functionality"""
        score = ScoreFactory(
            user=self.user,
            title="Hash Test Score",
            content_hash="abcd1234567890"
        )
        
        self.assertEqual(score.content_hash, "abcd1234567890")
        
        # Test calculate_content_hash method
        test_content = b"test file content"
        calculated_hash = score.calculate_content_hash(test_content)
        
        # Should return a SHA256 hash (64 characters)
        self.assertEqual(len(calculated_hash), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in calculated_hash))
    
    def test_optional_fields(self):
        """Test score creation with minimal required fields"""
        minimal_score = ScoreFactory(
            user=self.user,
            title="Minimal Score",
            composer="",  # Override factory default
            instrumentation="",  # Override factory default
            tags=[],  # Override factory default
            pages=None  # Override factory default to test None values
        )
        
        # Check defaults
        self.assertEqual(minimal_score.composer, "")
        self.assertEqual(minimal_score.instrumentation, "")
        self.assertEqual(minimal_score.mime, "application/pdf")
        self.assertEqual(minimal_score.tags, [])
        self.assertEqual(minimal_score.note, "")
        self.assertEqual(minimal_score.thumbnail_key, "")
        self.assertIsNone(minimal_score.pages)