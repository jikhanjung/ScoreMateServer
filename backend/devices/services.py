"""
TV 기기 연결 규칙 — API(device/code · device/token · devices)와 웹(/activate · /devices)이 같이 쓴다

RFC 8628 흐름:
  1. TV  → start_authorization()  : device_code(TV 만 앎) + user_code(사람이 옮겨 적음)
  2. 사람 → approve()/deny()        : 웹에서 로그인한 채로 user_code 를 확인
  3. TV  → poll(device_code)        : authorization_pending · slow_down · access_denied · expired_token → 승인되면 토큰 한 번
"""
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    Device, DeviceAuthorization, generate_user_code, hash_device_code, normalize_user_code,
)

# RFC 8628 §3.5 오류 코드
AUTHORIZATION_PENDING = 'authorization_pending'
SLOW_DOWN = 'slow_down'
ACCESS_DENIED = 'access_denied'
EXPIRED_TOKEN = 'expired_token'
INVALID_GRANT = 'invalid_grant'

SLOW_DOWN_STEP = 5


def device_refresh_lifetime():
    return timedelta(days=settings.DEVICE_REFRESH_TOKEN_DAYS)


def _clip(value, length):
    return (value or '').strip()[:length]


def start_authorization(name='', model='', app_version=''):
    """새 코드 한 쌍. 돌려주는 device_code 원문은 여기서만 보인다(DB 에는 해시)"""
    # 오래된 기록 정리 — 하루 지난 것
    DeviceAuthorization.objects.filter(expires_at__lt=timezone.now() - timedelta(days=1)).delete()
    device_code = secrets.token_urlsafe(32)
    for _ in range(10):
        try:
            with transaction.atomic():
                authorization = DeviceAuthorization.objects.create(
                    device_code_hash=hash_device_code(device_code),
                    user_code=generate_user_code(),
                    device_name=_clip(name, 100), device_model=_clip(model, 100), app_version=_clip(app_version, 50),
                    expires_at=timezone.now() + timedelta(seconds=DeviceAuthorization.EXPIRES_IN),
                )
            return authorization, device_code
        except IntegrityError:   # user_code 가 우연히 겹침 — 다시
            continue
    raise RuntimeError('Could not allocate a user code')


def find_pending(user_code):
    """사람이 입력한 코드 — 기다리는 중이고 만료 전인 것만"""
    code = normalize_user_code(user_code)
    if not code:
        return None
    authorization = DeviceAuthorization.objects.filter(user_code=code, status=DeviceAuthorization.STATUS_PENDING).first()
    if authorization is None or authorization.is_expired:
        return None
    return authorization


def approve(authorization, user, name=None):
    """이 TV 를 user 의 기기로 연결한다. 같은 코드는 한 번만"""
    with transaction.atomic():
        locked = DeviceAuthorization.objects.select_for_update().get(pk=authorization.pk)
        if locked.status != DeviceAuthorization.STATUS_PENDING or locked.is_expired:
            return None
        device = Device.objects.create(
            user=user, name=_clip(name, 100) or locked.device_name or 'TV',
            model=locked.device_model, app_version=locked.app_version,
        )
        locked.status = DeviceAuthorization.STATUS_APPROVED
        locked.user = user
        locked.device = device
        locked.save(update_fields=['status', 'user', 'device'])
    return device


def deny(authorization, user):
    with transaction.atomic():
        locked = DeviceAuthorization.objects.select_for_update().get(pk=authorization.pk)
        if locked.status == DeviceAuthorization.STATUS_PENDING:
            locked.status = DeviceAuthorization.STATUS_DENIED
            locked.user = user
            locked.save(update_fields=['status', 'user'])


def issue_tokens(device):
    """기기 토큰 — refresh 는 길게(DEVICE_REFRESH_TOKEN_DAYS), 모든 토큰에 device_id 클레임"""
    refresh = RefreshToken.for_user(device.user)
    refresh['device_id'] = str(device.id)
    refresh.set_exp(lifetime=device_refresh_lifetime())
    access = refresh.access_token   # device_id 가 복사된다
    return {
        'access_token': str(access),
        'refresh_token': str(refresh),
        'token_type': 'Bearer',
        'expires_in': int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()),
        'device_id': str(device.id),
    }


def poll(device_code):
    """TV 의 토큰 요청 → (오류 코드, None) 또는 (None, 토큰)"""
    if not device_code:
        return INVALID_GRANT, None
    now = timezone.now()
    with transaction.atomic():
        authorization = (DeviceAuthorization.objects.select_for_update()
                         .select_related('device__user').filter(device_code_hash=hash_device_code(device_code)).first())
        if authorization is None or authorization.status == DeviceAuthorization.STATUS_USED:
            return INVALID_GRANT, None
        if authorization.status == DeviceAuthorization.STATUS_DENIED:
            return ACCESS_DENIED, None
        if authorization.status == DeviceAuthorization.STATUS_PENDING and authorization.is_expired:
            return EXPIRED_TOKEN, None

        too_soon = (authorization.last_polled_at is not None and
                    (now - authorization.last_polled_at).total_seconds() < authorization.interval)
        authorization.last_polled_at = now
        if too_soon:
            authorization.interval += SLOW_DOWN_STEP
            authorization.save(update_fields=['last_polled_at', 'interval'])
            return SLOW_DOWN, None
        if authorization.status == DeviceAuthorization.STATUS_PENDING:
            authorization.save(update_fields=['last_polled_at'])
            return AUTHORIZATION_PENDING, None

        # 승인됨 — 토큰은 한 번만
        device = authorization.device
        authorization.status = DeviceAuthorization.STATUS_USED
        authorization.save(update_fields=['last_polled_at', 'status'])
        if device is None or not device.is_active:
            return ACCESS_DENIED, None
        return None, issue_tokens(device)


def revoke(device):
    """해제 — 그 기기의 access · refresh 토큰이 곧바로 거부된다(devices/auth.py · serializers.py)"""
    if device.revoked_at is None:
        device.revoked_at = timezone.now()
        device.save(update_fields=['revoked_at'])


def rename(device, name):
    name = _clip(name, 100)
    if name:
        device.name = name
        device.save(update_fields=['name'])
    return device


def set_sync(device, setlist_ids):
    """이 기기가 받을 세트리스트 — 웹(서버)에서만 정한다(기기는 API 로 보기만). 그 사용자가 읽을 수 있는 것만 남긴다.

    이미 고른 곡목은 그대로 두고(added_at 유지 — 다시 보내지 않게) 빠진 것만 지우고 새로 고른 것만 더한다.
    """
    from setlists.models import Setlist
    from .models import DeviceSetlist

    wanted = set(Setlist.objects.readable_by(device.user)
                 .filter(pk__in=[int(i) for i in setlist_ids if str(i).isdigit()]).values_list('pk', flat=True))
    with transaction.atomic():
        current = set(device.setlist_links.values_list('setlist_id', flat=True))
        DeviceSetlist.objects.filter(device=device, setlist_id__in=current - wanted).delete()
        DeviceSetlist.objects.bulk_create([DeviceSetlist(device=device, setlist_id=i) for i in wanted - current])
    return device

