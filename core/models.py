from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import uuid


class User(AbstractUser):
    """Custom User model extending Django's AbstractUser"""
    
    PLAN_CHOICES = [
        ('solo', 'Solo'),
        ('pro', 'Pro'),
        ('enterprise', 'Enterprise'),
    ]
    
    email = models.EmailField(unique=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='solo')
    total_quota_mb = models.IntegerField(default=200)
    used_quota_mb = models.IntegerField(default=0)
    referral_code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = str(uuid.uuid4())[:8].upper()
        super().save(*args, **kwargs)
    
    @property
    def available_quota_mb(self):
        return max(0, self.total_quota_mb - self.used_quota_mb)
    
    @property
    def quota_usage_percentage(self):
        if self.total_quota_mb == 0:
            return 0
        return (self.used_quota_mb / self.total_quota_mb) * 100
    
    def can_upload(self, size_bytes):
        """Check if user can upload a file of given size"""
        size_mb = size_bytes / (1024 * 1024)
        return self.available_quota_mb >= size_mb
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'


class ReferralLog(models.Model):
    """Track referral bonuses"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_given')
    referred_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_received')
    bonus_mb = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'referral_logs'
        ordering = ['-created_at']
        unique_together = ['user', 'referred_user']


class BillingLog(models.Model):
    """Track billing events"""
    KIND_CHOICES = [
        ('plan_change', 'Plan Change'),
        ('payment', 'Payment'),
        ('refund', 'Refund'),
        ('referral_bonus', 'Referral Bonus'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='billing_logs')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    meta_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'billing_logs'
        ordering = ['-created_at']


class AccessLog(models.Model):
    """Track user access patterns for auditing"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='access_logs')
    action = models.CharField(max_length=50)
    target_type = models.CharField(max_length=50)
    target_id = models.IntegerField(null=True, blank=True)
    meta_json = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'access_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action', '-created_at']),
        ]
