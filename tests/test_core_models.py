"""
Tests for core models - User quota system
"""
import pytest
from django.test import TestCase
from django.db import IntegrityError
from core.models import User, ReferralLog, BillingLog, AccessLog
from .factories import UserFactory, ReferralLogFactory


@pytest.mark.django_db
class TestUserQuotaSystem(TestCase):
    """Test User model quota-related functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = UserFactory(
            email="quota@test.com",
            username="quotauser",
            plan="solo"
        )
    
    def test_default_quota_allocation(self):
        """Test that new users get default quota"""
        user = UserFactory(
            username="newuser",
            email="new@test.com"
        )
        self.assertEqual(user.total_quota_mb, 200)  # Default from factory
        self.assertEqual(user.used_quota_mb, 0)
        self.assertEqual(user.plan, "solo")  # Default plan
    
    def test_available_quota_calculation(self):
        """Test available_quota_mb property calculation"""
        # Initial state
        self.assertEqual(self.user.available_quota_mb, 200)
        
        # After using some quota
        self.user.used_quota_mb = 50
        self.user.save()
        self.assertEqual(self.user.available_quota_mb, 150)
        
        # Quota fully used
        self.user.used_quota_mb = 200
        self.user.save()
        self.assertEqual(self.user.available_quota_mb, 0)
        
        # Over quota (edge case)
        self.user.used_quota_mb = 250
        self.user.save()
        self.assertEqual(self.user.available_quota_mb, 0)  # Should not be negative
    
    def test_quota_usage_percentage(self):
        """Test quota_usage_percentage property calculation"""
        # No usage
        self.assertEqual(self.user.quota_usage_percentage, 0.0)
        
        # 25% usage
        self.user.used_quota_mb = 50
        self.user.save()
        self.assertEqual(self.user.quota_usage_percentage, 25.0)
        
        # 100% usage
        self.user.used_quota_mb = 200
        self.user.save()
        self.assertEqual(self.user.quota_usage_percentage, 100.0)
        
        # Over quota
        self.user.used_quota_mb = 300
        self.user.save()
        self.assertEqual(self.user.quota_usage_percentage, 150.0)
        
        # Zero total quota (edge case)
        self.user.total_quota_mb = 0
        self.user.used_quota_mb = 0
        self.user.save()
        self.assertEqual(self.user.quota_usage_percentage, 0)
    
    def test_can_upload_method(self):
        """Test can_upload() method for different file sizes"""
        # Small file (1MB = 1024*1024 bytes)
        small_file_bytes = 1024 * 1024
        self.assertTrue(self.user.can_upload(small_file_bytes))
        
        # Large file (150MB)
        large_file_bytes = 150 * 1024 * 1024
        self.assertTrue(self.user.can_upload(large_file_bytes))
        
        # File that exceeds quota (250MB)
        oversized_file_bytes = 250 * 1024 * 1024
        self.assertFalse(self.user.can_upload(oversized_file_bytes))
        
        # Test with used quota
        self.user.used_quota_mb = 150
        self.user.save()
        
        # 40MB file should fit (150 + 40 = 190 < 200)
        medium_file_bytes = 40 * 1024 * 1024
        self.assertTrue(self.user.can_upload(medium_file_bytes))
        
        # 60MB file should not fit (150 + 60 = 210 > 200)
        too_big_file_bytes = 60 * 1024 * 1024
        self.assertFalse(self.user.can_upload(too_big_file_bytes))
    
    def test_referral_code_generation(self):
        """Test automatic referral code generation"""
        # Check existing user has referral code
        self.assertIsNotNone(self.user.referral_code)
        self.assertEqual(len(self.user.referral_code), 8)
        self.assertTrue(self.user.referral_code.isupper())
        
        # Create new user and check referral code
        new_user = UserFactory(
            username="refuser",
            email="ref@test.com"
        )
        self.assertIsNotNone(new_user.referral_code)
        self.assertEqual(len(new_user.referral_code), 8)
        
        # Referral codes should be unique
        self.assertNotEqual(self.user.referral_code, new_user.referral_code)
    
    def test_different_plans(self):
        """Test different user plans"""
        # Pro plan user
        pro_user = UserFactory(
            username="prouser",
            email="pro@test.com",
            plan="pro",
            total_quota_mb=1000  # Pro users might have more quota
        )
        self.assertEqual(pro_user.plan, "pro")
        self.assertEqual(pro_user.total_quota_mb, 1000)
        
        # Enterprise plan user
        enterprise_user = UserFactory(
            username="enterprise",
            email="enterprise@test.com",
            plan="enterprise",
            total_quota_mb=5000
        )
        self.assertEqual(enterprise_user.plan, "enterprise")
        self.assertEqual(enterprise_user.total_quota_mb, 5000)


@pytest.mark.django_db
class TestReferralLogModel(TestCase):
    """Test ReferralLog model functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.referrer = UserFactory(email="referrer@test.com", username="referrer")
        self.referred = UserFactory(email="referred@test.com", username="referred")
    
    def test_referral_log_creation(self):
        """Test creating a referral log entry"""
        referral = ReferralLogFactory(
            user=self.referrer,
            referred_user=self.referred,
            bonus_mb=50
        )
        
        self.assertEqual(referral.user, self.referrer)
        self.assertEqual(referral.referred_user, self.referred)
        self.assertEqual(referral.bonus_mb, 50)
        self.assertIsNotNone(referral.created_at)
    
    def test_referral_uniqueness(self):
        """Test that same referral cannot be logged twice"""
        # Create first referral
        ReferralLogFactory(
            user=self.referrer,
            referred_user=self.referred,
            bonus_mb=50
        )
        
        # Try to create duplicate - should raise IntegrityError
        with self.assertRaises(IntegrityError):
            ReferralLogFactory(
                user=self.referrer,
                referred_user=self.referred,
                bonus_mb=50
            )