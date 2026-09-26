"""
앙상블 · 멤버 · 초대 (devlog 054 §2, S1)

권한 규칙:
- 앙상블 악보는 멤버가 읽고, owner · leader 가 쓴다 (올리기 · 수정 · 지우기)
- 멤버 관리: 역할 변경은 owner 만, 파트 지정 · 초대 · 내보내기는 owner · leader
- owner 는 적어도 한 명 남아 있어야 한다
"""
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Ensemble(models.Model):
    """악보를 함께 쓰는 모임 (합주단 · 밴드 · 반주 팀)"""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_ensembles'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ensembles'
        ordering = ['name']

    def __str__(self):
        return self.name

    def membership_of(self, user):
        """user 의 Membership, 멤버가 아니면 None"""
        if not user or not user.is_authenticated:
            return None
        return self.memberships.filter(user=user).first()

    def role_of(self, user):
        membership = self.membership_of(user)
        return membership.role if membership else None

    def is_member(self, user):
        return self.role_of(user) is not None

    def can_manage(self, user):
        """악보 쓰기 · 초대 · 파트 지정 · 멤버 내보내기"""
        return self.role_of(user) in Membership.MANAGER_ROLES

    def is_owner(self, user):
        return self.role_of(user) == Membership.ROLE_OWNER


class Membership(models.Model):
    ROLE_OWNER = 'owner'
    ROLE_LEADER = 'leader'
    ROLE_MEMBER = 'member'
    ROLE_CHOICES = [
        (ROLE_OWNER, 'Owner'),
        (ROLE_LEADER, 'Leader'),
        (ROLE_MEMBER, 'Member'),
    ]
    MANAGER_ROLES = (ROLE_OWNER, ROLE_LEADER)

    ensemble = models.ForeignKey(Ensemble, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    part = models.CharField(max_length=100, blank=True, help_text='예: "Guitar 1", "총보"')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ensemble_memberships'
        ordering = ['joined_at']
        constraints = [
            models.UniqueConstraint(fields=['ensemble', 'user'], name='unique_ensemble_member'),
        ]
        indexes = [
            models.Index(fields=['user', 'role']),
        ]

    def __str__(self):
        return f'{self.user} @ {self.ensemble} ({self.role})'

    @property
    def is_manager(self):
        return self.role in self.MANAGER_ROLES


# 헷갈리는 글자(0/O, 1/I/L, 모음 — 우연한 단어 방지)를 뺀 초대 코드 글자
INVITE_CODE_ALPHABET = 'BCDFGHJKMNPQRSTVWXZ23456789'
INVITE_CODE_LENGTH = 10


def generate_invite_code():
    return ''.join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(INVITE_CODE_LENGTH))


class Invite(models.Model):
    """초대 링크 — 코드를 아는 로그인 사용자는 member 로 가입한다"""
    DEFAULT_EXPIRY_DAYS = 7

    ensemble = models.ForeignKey(Ensemble, on_delete=models.CASCADE, related_name='invites')
    code = models.CharField(max_length=32, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_invites'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text='비우면 만료 없음')
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text='비우면 횟수 제한 없음')
    uses = models.PositiveIntegerField(default=0)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'ensemble_invites'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.ensemble} invite {self.code}'

    def save(self, *args, **kwargs):
        if not self.code:
            code = generate_invite_code()
            while Invite.objects.filter(code=code).exists():
                code = generate_invite_code()
            self.code = code
        super().save(*args, **kwargs)

    @classmethod
    def default_expiry(cls):
        return timezone.now() + timedelta(days=cls.DEFAULT_EXPIRY_DAYS)

    @property
    def is_usable(self):
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at <= timezone.now():
            return False
        if self.max_uses is not None and self.uses >= self.max_uses:
            return False
        return True
