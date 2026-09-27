from django.contrib import admin

from .models import Device, DeviceAuthorization


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'model', 'app_version', 'last_seen_at', 'revoked_at', 'created_at']
    list_filter = ['revoked_at']
    search_fields = ['name', 'user__email', 'model']
    raw_id_fields = ['user']
    readonly_fields = ['id', 'created_at', 'last_seen_at']


@admin.register(DeviceAuthorization)
class DeviceAuthorizationAdmin(admin.ModelAdmin):
    list_display = ['display_code', 'status', 'device_name', 'user', 'created_at', 'expires_at']
    list_filter = ['status']
    raw_id_fields = ['user', 'device']
    # device_code 는 해시만 있다 — 여기서도 원문은 볼 수 없다
    readonly_fields = ['device_code_hash', 'user_code', 'created_at', 'last_polled_at']
