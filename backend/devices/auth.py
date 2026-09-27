"""
기기 토큰을 아는 JWT 인증 — device_id 클레임이 있으면 그 기기가 살아 있어야 한다

해제(revoked_at)하면 이미 발급된 access 토큰(최대 60분)도 곧바로 막힌다. 마지막 접속 시각은 5분에 한 번만 쓴다
(TV 는 자주 부른다 — 요청마다 DB 쓰기를 하지 않게).
"""
from datetime import timedelta

from django.utils import timezone
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from .models import Device

LAST_SEEN_RESOLUTION = timedelta(minutes=5)


def active_device_for(token, user_id):
    """토큰의 device_id 가 가리키는 살아 있는 기기, 없으면 AuthenticationFailed. 기기 토큰이 아니면 None"""
    device_id = token.get('device_id')
    if not device_id:
        return None
    device = Device.objects.filter(pk=device_id).only('id', 'user_id', 'revoked_at', 'last_seen_at').first()
    if device is None or device.revoked_at is not None or str(device.user_id) != str(user_id):
        raise AuthenticationFailed('This device has been disconnected.', code='device_revoked')
    return device


class DeviceAwareJWTAuthentication(JWTAuthentication):

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        device = active_device_for(validated_token, user.pk)
        if device is not None:
            now = timezone.now()
            if device.last_seen_at is None or now - device.last_seen_at > LAST_SEEN_RESOLUTION:
                Device.objects.filter(pk=device.pk).update(last_seen_at=now)
            user.device_id = str(device.pk)   # 뷰가 "지금 이 요청은 어느 기기인가"를 안다
        return user


class PerDeviceScopedRateThrottle(ScopedRateThrottle):
    """동기화 · 받기 · 분석 — 계정이 아니라 **기기마다** 센다

    기본 UserRateThrottle(사용자당 1000/시간)은 한 계정의 TV 여러 대와 웹이 한 통을 나눠 쓴다 —
    악보 300개를 처음 받는 TV 두 대가 함께 막힐 수 있다. 기기 토큰이면 device_id, 아니면 사용자 id 로 센다.
    """

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = f"device:{request.user.device_id}" if getattr(request.user, 'device_id', None) else f"user:{request.user.pk}"
        else:
            ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}
