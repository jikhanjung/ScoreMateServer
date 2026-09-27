"""
TV 기기 연결 — RFC 8628 (OAuth 2.0 Device Authorization Grant), devlog 054 §3

TV 는 리모컨뿐이라 로그인 폼을 쓸 수 없다. TV 가 코드를 받아 화면에 띄우고(코드 + QR),
사람이 휴대폰에서 로그인해 그 코드를 승인하면 TV 가 토큰을 받는다.
"""
import hashlib
import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

# 헷갈리는 글자(0/O, 1/I/L)와 모음(우연한 단어)을 뺀 글자 — 리모컨 · 휴대폰으로 옮겨 적기 쉽게
USER_CODE_ALPHABET = 'BCDFGHJKMNPQRSTVWXZ23456789'
USER_CODE_LENGTH = 8


def generate_user_code():
    return ''.join(secrets.choice(USER_CODE_ALPHABET) for _ in range(USER_CODE_LENGTH))


def format_user_code(code):
    """BCDFGHJK → BCDF-GHJK"""
    return f'{code[:4]}-{code[4:]}' if len(code) == USER_CODE_LENGTH else code


def normalize_user_code(code):
    return (code or '').strip().upper().replace('-', '').replace(' ', '')


def hash_device_code(device_code):
    """device_code 는 해시로만 저장한다 — DB 사본이 새도 TV 행세를 못 하게"""
    return hashlib.sha256(device_code.encode()).hexdigest()


class Device(models.Model):
    """연결된 TV. 해제하면(revoked_at) 그 기기의 토큰이 곧바로 거부된다"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='devices')
    name = models.CharField(max_length=100, help_text='e.g. "Living room TV"')
    model = models.CharField(max_length=100, blank=True)
    app_version = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'devices'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'revoked_at'])]

    def __str__(self):
        return f'{self.name} ({self.user})'

    @property
    def is_active(self):
        return self.revoked_at is None


class DeviceAuthorization(models.Model):
    """코드 한 쌍 — TV 가 받아 가고, 사람이 승인하고, TV 가 토큰으로 한 번 바꾼다"""
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_DENIED = 'denied'
    STATUS_USED = 'used'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_DENIED, 'Denied'),
        (STATUS_USED, 'Used'),
    ]
    EXPIRES_IN = 600          # 10분
    DEFAULT_INTERVAL = 5      # TV 가 토큰을 묻는 간격(초). 너무 자주 물으면 slow_down 과 함께 5초씩 는다

    device_code_hash = models.CharField(max_length=64, unique=True)
    user_code = models.CharField(max_length=USER_CODE_LENGTH, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    # TV 가 알려 준 것
    device_name = models.CharField(max_length=100, blank=True)
    device_model = models.CharField(max_length=100, blank=True)
    app_version = models.CharField(max_length=50, blank=True)
    # 승인
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
                             related_name='device_authorizations')
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    interval = models.PositiveIntegerField(default=DEFAULT_INTERVAL)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_polled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'device_authorizations'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.display_code} ({self.status})'

    @property
    def display_code(self):
        return format_user_code(self.user_code)

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at
