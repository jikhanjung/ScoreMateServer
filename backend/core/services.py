"""
사용자 관리 규칙 — 웹(/manage/users/)과 API 가 같이 쓴다. devlog 075

- 관리자(superuser)만 다른 사용자를 바꿀 수 있다: 등급 · 저장 공간 한도 · 관리자 권한 · 사용 중지
- 자기 자신의 관리자 권한을 빼거나 자기 자신을 사용 중지할 수는 없다. 활성 관리자는 적어도 한 명 남는다
- 등급(User.plan)마다 기본 저장 공간(settings.USER_GRADES). 등급을 바꾸면 그 기본 한도가 들어가고, 한도를 따로 주면 그 값
- 사용 중지: 로그인 · API · 기기 토큰이 모두 막힌다(simplejwt 가 비활성 사용자를 거부한다). 악보 · 파일은 그대로 둔다
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied


class UserRuleError(ValueError):
    pass


def grades():
    """[(키, 이름, 기본 저장 공간 MB)] — 설정 순서대로"""
    return [(key, label, quota) for key, (label, quota) in settings.USER_GRADES.items()]


def grade_label(key):
    return settings.USER_GRADES.get(key, (key, None))[0]


def grade_quota(key):
    return settings.USER_GRADES.get(key, (key, None))[1]


def _require_superuser(actor):
    if not (actor and actor.is_authenticated and actor.is_superuser and actor.is_active):
        raise PermissionDenied('Only administrators can manage users.')


def active_superusers():
    return get_user_model().objects.filter(is_superuser=True, is_active=True)


def update_user(actor, target, *, grade=None, quota_mb=None, is_superuser=None, is_active=None):
    """target 을 바꾼다. 바뀐 항목 목록을 돌려준다. quota_mb=None 이고 등급이 바뀌면 등급 기본 한도"""
    _require_superuser(actor)
    changes = []
    fields = set()
    if grade is not None and grade != target.plan:
        if grade not in settings.USER_GRADES:
            raise UserRuleError(f'Unknown grade: {grade}')
        target.plan = grade
        fields.add('plan')
        changes.append(f'등급 → {grade_label(grade)}')
        if quota_mb is None:
            quota_mb = grade_quota(grade)
    if quota_mb is not None and int(quota_mb) != target.total_quota_mb:
        if int(quota_mb) < 0:
            raise UserRuleError('Quota must not be negative.')
        target.total_quota_mb = int(quota_mb)
        fields.add('total_quota_mb')
        changes.append(f'저장 공간 → {int(quota_mb)}MB')
    if is_superuser is not None and bool(is_superuser) != target.is_superuser:
        if not is_superuser:
            if target.pk == actor.pk:
                raise UserRuleError('You cannot remove your own administrator role.')
            if target.is_active and active_superusers().exclude(pk=target.pk).count() == 0:
                raise UserRuleError('At least one active administrator must remain.')
        target.is_superuser = target.is_staff = bool(is_superuser)   # Django 관리 화면(/admin/)도 함께
        fields.update({'is_superuser', 'is_staff'})
        changes.append('관리자 권한 → ' + ('줌' if is_superuser else '뺌'))
    if is_active is not None and bool(is_active) != target.is_active:
        if not is_active:
            if target.pk == actor.pk:
                raise UserRuleError('You cannot deactivate yourself.')
            if target.is_superuser and active_superusers().exclude(pk=target.pk).count() == 0:
                raise UserRuleError('At least one active administrator must remain.')
        target.is_active = bool(is_active)
        fields.add('is_active')
        changes.append('사용 ' + ('다시 허용' if is_active else '중지'))
    if fields:
        target.save(update_fields=sorted(fields))
    return changes
