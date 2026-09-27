"""
앙상블 규칙 — API(EnsembleViewSet)와 웹이 같은 함수를 쓴다

권한 없음은 django PermissionDenied(DRF 가 403 으로), 규칙 위반은 RuleError(필드 · 메시지)로 알린다.
"""
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Ensemble, Membership, Invite


class RuleError(ValueError):
    """규칙 위반 — field 는 API 가 오류를 붙일 필드 이름"""

    def __init__(self, field, message):
        super().__init__(message)
        self.field = field
        self.message = message


def normalize_code(code):
    """사람이 치는 초대 코드 — 대소문자 · 하이픈 · 공백 무시"""
    return (code or '').strip().upper().replace('-', '').replace(' ', '')


def create_ensemble(user, name, description=''):
    name = (name or '').strip()
    if not name:
        raise RuleError('name', 'Name cannot be empty')
    with transaction.atomic():
        ensemble = Ensemble.objects.create(name=name, description=description or '', created_by=user)
        Membership.objects.create(ensemble=ensemble, user=user, role=Membership.ROLE_OWNER)
    return ensemble


def require_manager(ensemble, user, message='Only owners and leaders can do this.'):
    if not ensemble.can_manage(user):
        raise PermissionDenied(message)


def _ensure_another_owner(ensemble, leaving):
    if not ensemble.memberships.filter(role=Membership.ROLE_OWNER).exclude(pk=leaving.pk).exists():
        raise RuleError('role', 'An ensemble must keep at least one owner. Make someone else owner first.')


def update_member(ensemble, actor, target, role=None, part=None):
    """역할은 owner 만, 파트는 owner · leader · 본인. owner 는 적어도 한 명 남는다"""
    mine = ensemble.membership_of(actor)
    if mine is None:
        raise PermissionDenied('Not a member.')
    if role is not None and role != target.role:
        if role not in dict(Membership.ROLE_CHOICES):
            raise RuleError('role', f'"{role}" is not a valid choice.')
        if mine.role != Membership.ROLE_OWNER:
            raise PermissionDenied('Only owners can change roles.')
        if target.role == Membership.ROLE_OWNER:
            _ensure_another_owner(ensemble, target)
        target.role = role
    if part is not None and part != target.part:
        if not (mine.is_manager or mine.pk == target.pk):
            raise PermissionDenied('Only owners, leaders or the member themself can set the part.')
        target.part = part.strip()[:100]
    target.save()
    return target


def remove_member(ensemble, actor, target):
    """나가기(본인) · owner 는 누구나 · leader 는 member 만 내보낸다"""
    mine = ensemble.membership_of(actor)
    if mine is None:
        raise PermissionDenied('Not a member.')
    if mine.pk == target.pk:
        if target.role == Membership.ROLE_OWNER:
            _ensure_another_owner(ensemble, target)
    elif mine.role == Membership.ROLE_OWNER:
        pass
    elif mine.role == Membership.ROLE_LEADER and target.role == Membership.ROLE_MEMBER:
        pass
    else:
        raise PermissionDenied('You cannot remove this member.')
    target.delete()


def update_ensemble(ensemble, actor, name=None, description=None):
    """앙상블 정보 바꾸기 — API 와 웹이 이 하나로(규칙이 한 곳에 있게)

    이름이 바뀌면 그 앙상블 악보의 updated_at 을 올린다: TV 는 앙상블 이름으로 폴더를 만드는데, 악보가 다시 오지 않으면
    옛 이름 폴더에 머문다(TV P06 §1). 설명만 바꾸면 올리지 않는다 — TV 가 쓰지 않는 필드라 재전송이 필요 없다.
    """
    require_manager(ensemble, actor, 'Only owners and leaders can edit the ensemble.')
    old_name = ensemble.name
    if name is not None:
        name = name.strip()
        if not name:
            raise RuleError('name', 'Name cannot be empty')
        ensemble.name = name
    if description is not None:
        ensemble.description = description
    with transaction.atomic():
        ensemble.save()
        if ensemble.name != old_name:
            ensemble.scores.update(updated_at=timezone.now())
    return ensemble


def delete_ensemble(ensemble, actor):
    """악보는 지우지 않는다 — Score.ensemble 이 SET_NULL 이라 올린 사람의 개인 악보로 돌아간다"""
    if not ensemble.is_owner(actor):
        raise PermissionDenied('Only owners can delete the ensemble.')
    with transaction.atomic():
        # 악보가 개인 악보로 돌아간다 — 올린 사람의 TV 가 "바뀐 것"으로 받게 (동기화 기준 시각)
        ensemble.scores.update(updated_at=timezone.now())
        ensemble.delete()


def create_invite(ensemble, actor, expires_in_days=Invite.DEFAULT_EXPIRY_DAYS, max_uses=None):
    """expires_in_days=None 이면 만료 없음"""
    require_manager(ensemble, actor, 'Only owners and leaders can manage invites.')
    expires_at = timezone.now() + timedelta(days=expires_in_days) if expires_in_days else None
    return Invite.objects.create(ensemble=ensemble, created_by=actor, expires_at=expires_at, max_uses=max_uses)


def revoke_invite(ensemble, actor, invite):
    require_manager(ensemble, actor, 'Only owners and leaders can manage invites.')
    if invite.revoked_at is None:
        invite.revoked_at = timezone.now()
        invite.save(update_fields=['revoked_at'])


def find_usable_invite(code, for_update=False):
    """쓸 수 있는 초대, 아니면 RuleError — 없는 코드와 만료된 코드를 구별해 알려 주지 않는다"""
    queryset = Invite.objects.select_related('ensemble')
    if for_update:
        queryset = queryset.select_for_update()
    invite = queryset.filter(code=normalize_code(code)).first()
    if invite is None or not invite.is_usable:
        raise RuleError('code', 'Invalid or expired invite code.')
    return invite


def join(user, code):
    """초대 코드로 member 가 된다. 이미 멤버면 역할은 그대로. (ensemble, created)"""
    with transaction.atomic():
        invite = find_usable_invite(code, for_update=True)
        ensemble = invite.ensemble
        if ensemble.membership_of(user) is not None:
            return ensemble, False
        Membership.objects.create(ensemble=ensemble, user=user)
        Invite.objects.filter(pk=invite.pk).update(uses=F('uses') + 1)
    return ensemble, True


def registration_invite(code):
    """가입에 쓸 수 있는 초대, 없으면 None — REGISTRATION_OPEN=false 면 이것이 있어야 가입할 수 있다"""
    if not code:
        return None
    try:
        return find_usable_invite(code)
    except RuleError:
        return None


def invite_code_from_next(next_url):
    """로그인 · 가입의 next 가 초대 링크(/join/<code>/)면 그 코드"""
    import re
    match = re.fullmatch(r'/join/([A-Za-z0-9-]+)/?', (next_url or '').split('?')[0])
    return match.group(1) if match else None
