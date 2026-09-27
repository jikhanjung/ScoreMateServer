"""
Serializers for devices app
"""
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings

from .auth import active_device_for
from .models import Device
from .services import device_refresh_lifetime


class DeviceAwareTokenRefreshSerializer(TokenRefreshSerializer):
    """/auth/token/refresh/ — simplejwt 기본과 같되

    - 해제된 기기의 refresh 토큰은 거부한다
    - 기기 토큰은 회전할 때도 긴 수명(DEVICE_REFRESH_TOKEN_DAYS)을 유지한다 (기본 구현은 1일로 줄인다)
    """

    def validate(self, attrs):
        refresh = self.token_class(attrs['refresh'])
        user_id = refresh.payload.get(api_settings.USER_ID_CLAIM)
        user = get_user_model().objects.filter(**{api_settings.USER_ID_FIELD: user_id}).first() if user_id else None
        if user is None or not api_settings.USER_AUTHENTICATION_RULE(user):
            raise AuthenticationFailed(self.error_messages['no_active_account'], 'no_active_account')
        device = active_device_for(refresh, user.pk)

        data = {'access': str(refresh.access_token)}
        if api_settings.ROTATE_REFRESH_TOKENS:
            if api_settings.BLACKLIST_AFTER_ROTATION:
                try:
                    refresh.blacklist()
                except AttributeError:   # 블랙리스트 앱이 없다
                    pass
            refresh.set_jti()
            refresh.set_exp(lifetime=device_refresh_lifetime() if device is not None else None)
            refresh.set_iat()
            refresh.outstand()
            data['refresh'] = str(refresh)
        return data


class DeviceCodeRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    model = serializers.CharField(max_length=100, required=False, allow_blank=True)
    app_version = serializers.CharField(max_length=50, required=False, allow_blank=True)


class DeviceSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)
    is_this_device = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = ['id', 'name', 'model', 'app_version', 'created_at', 'last_seen_at', 'last_synced_at', 'revoked_at',
                  'is_active', 'is_this_device']
        read_only_fields = ['id', 'model', 'app_version', 'created_at', 'last_seen_at', 'last_synced_at', 'revoked_at']

    def get_is_this_device(self, obj):
        request = self.context.get('request')
        return bool(request) and getattr(request.user, 'device_id', None) == str(obj.pk)


class HeartbeatSerializer(serializers.Serializer):
    app_version = serializers.CharField(max_length=50, required=False, allow_blank=True)
    model = serializers.CharField(max_length=100, required=False, allow_blank=True)
