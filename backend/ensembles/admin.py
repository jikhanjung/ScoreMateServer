from django.contrib import admin

from .models import Ensemble, Membership, Invite


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    raw_id_fields = ['user']


class InviteInline(admin.TabularInline):
    model = Invite
    extra = 0
    readonly_fields = ['code', 'uses', 'created_at']
    raw_id_fields = ['created_by']


@admin.register(Ensemble)
class EnsembleAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_by', 'created_at']
    search_fields = ['name', 'created_by__email']
    raw_id_fields = ['created_by']
    inlines = [MembershipInline, InviteInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ['ensemble', 'user', 'role', 'part', 'joined_at']
    list_filter = ['role']
    search_fields = ['ensemble__name', 'user__email']
    raw_id_fields = ['ensemble', 'user']


@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ['ensemble', 'code', 'uses', 'max_uses', 'expires_at', 'revoked_at']
    search_fields = ['ensemble__name', 'code']
    raw_id_fields = ['ensemble', 'created_by']
