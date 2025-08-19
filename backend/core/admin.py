from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, ReferralLog, BillingLog, AccessLog


class UserAdmin(BaseUserAdmin):
    """Custom admin for User model"""
    list_display = ['email', 'username', 'plan', 'total_quota_mb', 'used_quota_mb', 'referral_code', 'is_active']
    list_filter = ['plan', 'is_active', 'is_staff', 'date_joined']
    search_fields = ['email', 'username', 'referral_code']
    ordering = ['-date_joined']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Quota & Plan', {'fields': ('plan', 'total_quota_mb', 'used_quota_mb', 'referral_code')}),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Quota & Plan', {'fields': ('plan', 'total_quota_mb', 'referral_code')}),
    )


@admin.register(ReferralLog)
class ReferralLogAdmin(admin.ModelAdmin):
    """Admin for ReferralLog model"""
    list_display = ['user', 'referred_user', 'bonus_mb', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'referred_user__email']
    date_hierarchy = 'created_at'
    raw_id_fields = ['user', 'referred_user']


@admin.register(BillingLog)
class BillingLogAdmin(admin.ModelAdmin):
    """Admin for BillingLog model"""
    list_display = ['user', 'kind', 'amount', 'created_at']
    list_filter = ['kind', 'created_at']
    search_fields = ['user__email']
    date_hierarchy = 'created_at'
    raw_id_fields = ['user']


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    """Admin for AccessLog model"""
    list_display = ['user', 'action', 'target_type', 'target_id', 'ip_address', 'created_at']
    list_filter = ['action', 'target_type', 'created_at']
    search_fields = ['user__email', 'action', 'ip_address']
    date_hierarchy = 'created_at'
    raw_id_fields = ['user']
    readonly_fields = ['created_at']


# Register custom User admin
admin.site.register(User, UserAdmin)
