"""
웹 화면 (Django 템플릿, 세션 로그인)

권한 규칙은 API 와 같은 곳에 있다:
- 악보: Score.objects.readable_by / writable_by, Score.can_edit
- 앙상블: ensembles/services.py (역할 · 파트 · 내보내기 · 초대 · 가입)
- 악보 만들기 · 지우기: scores/services.py (쿼터 · 처리 · 파일 삭제)
"""
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.http import require_POST

from devices import services as device_services
from devices.models import Device
from ensembles import services as ensemble_services
from ensembles.models import Ensemble, Membership, Invite
from core.models import SocialAccount
from files.utils import LocalStorageHandler, generate_upload_s3_key, get_storage
from scores.models import Score
from setlists.models import Setlist, SetlistItem
from scores.serializers import thumbnail_url
from scores.services import (
    VersionError, add_version, create_score, delete_score, delete_version, make_current, same_title_and_part,
)

from . import google
from .forms import (
    ActivateForm, DeviceNameForm, EnsembleForm, SetlistForm, InviteForm, JoinCodeForm, LoginForm, MemberForm, NewVersionForm, RegisterForm, ScoreEditForm,
    UploadForm,
    managed_ensembles,
)

logger = logging.getLogger(__name__)
User = get_user_model()

ROLE_LABELS = {'owner': '소유자', 'leader': '리더', 'member': '멤버'}

# 로그인 실패 제한 — (이메일, IP) 마다 15분에 10번 (guides/web/operations.md §7: 로그인에 속도 제한)
LOGIN_FAIL_LIMIT = 10
LOGIN_FAIL_WINDOW = 15 * 60


def _client_ip(request):
    if settings.SECURE_PROXY_SSL_HEADER:  # 앞단 nginx 를 믿는 설정일 때만
        return request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR', '')
    return request.META.get('REMOTE_ADDR', '')


def _safe_next(request, default):
    target = request.POST.get('next') or request.GET.get('next')
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                                  require_https=request.is_secure()):
        return target
    return default


# --- 계정 ---

def home(request):
    return redirect('web:scores' if request.user.is_authenticated else 'web:login')


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_safe_next(request, reverse('web:scores')))
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].strip().lower()
        key = f'web-login-fail:{email}:{_client_ip(request)}'
        if cache.get(key, 0) >= LOGIN_FAIL_LIMIT:
            form.add_error(None, '로그인 시도가 너무 많습니다. 15분 뒤에 다시 해 주세요.')
        else:
            user = authenticate(request, username=email, password=form.cleaned_data['password'])
            if user is not None and user.is_active:
                cache.delete(key)
                login(request, user)
                return redirect(_safe_next(request, reverse('web:scores')))
            cache.set(key, cache.get(key, 0) + 1, LOGIN_FAIL_WINDOW)
            form.add_error(None, '이메일 또는 비밀번호가 맞지 않습니다.')
    invite = _registration_invite(request)
    return render(request, 'web/login.html', {'form': form, 'next': request.GET.get('next', ''),
                                              'can_register': settings.REGISTRATION_OPEN or invite is not None,
                                              'invite': invite})


def _registration_invite(request):
    """?invite= 또는 초대 링크로 가는 next 에서 쓸 수 있는 초대"""
    code = (request.POST.get('invite') or request.GET.get('invite')
            or ensemble_services.invite_code_from_next(request.POST.get('next') or request.GET.get('next')))
    return ensemble_services.registration_invite(code)


def register_view(request):
    """가입. REGISTRATION_OPEN=false(초대 전용)면 쓸 수 있는 초대 링크로 온 사람만 — 가입하면 그 앙상블에 들어간다"""
    if request.user.is_authenticated:
        return redirect('web:scores')
    invite = _registration_invite(request)
    if not settings.REGISTRATION_OPEN and invite is None:
        return render(request, 'web/register_closed.html', status=403)

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = User.objects.create_user(email=form.cleaned_data['email'], username=form.cleaned_data['username'],
                                        password=form.cleaned_data['password1'])
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        if invite is not None:
            try:
                ensemble, _ = ensemble_services.join(user, invite.code)
            except ensemble_services.RuleError:
                # 그 사이 인원이 찼거나 취소됐다 — 계정은 만들어졌으니 알리기만
                messages.error(request, '가입했지만 초대 링크가 그 사이 만료됐습니다. 새 링크를 받아 여세요.')
                return redirect('web:scores')
            messages.success(request, f'가입했습니다. "{ensemble.name}" 에 들어왔습니다.')
            return redirect('web:ensemble_detail', pk=ensemble.pk)
        messages.success(request, '가입했습니다. 초대 링크가 있으면 열어서 앙상블에 들어가세요.')
        return redirect(_safe_next(request, reverse('web:scores')))
    return render(request, 'web/register.html', {'form': form, 'next': request.GET.get('next', ''), 'invite': invite})


@require_POST
def logout_view(request):
    logout(request)
    return redirect('web:login')


@login_required
def account(request):
    # Google 로 가입해 비밀번호가 없으면 기존 비밀번호 없이 정한다
    form_class = PasswordChangeForm if request.user.has_usable_password() else SetPasswordForm
    form = form_class(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, '비밀번호를 바꿨습니다.')
        return redirect('web:account')
    user = request.user
    used = user.used_quota_mb
    return render(request, 'web/account/account.html', {
        'form': form,
        'used_pct': min(100, round(used * 100 / user.total_quota_mb)) if user.total_quota_mb else 0,
        'score_count': Score.objects.filter(user=user).count(),
        'google_account': user.social_accounts.filter(provider=SocialAccount.PROVIDER_GOOGLE).first(),
        'has_password': user.has_usable_password(),
    })


# --- 악보 ---

def _decorate(scores, user):
    """카드에 쓸 썸네일 URL · 수정 가능 여부"""
    managed = set(Membership.objects.filter(user=user, role__in=Membership.MANAGER_ROLES)
                  .values_list('ensemble_id', flat=True))
    for score in scores:
        score.thumb = thumbnail_url(score)
        score.editable = (score.user_id == user.id) if score.ensemble_id is None else (score.ensemble_id in managed)
    return scores


@login_required
def score_list(request):
    user = request.user
    scores = Score.objects.readable_by(user).select_related('ensemble', 'user', 'current_version').order_by('-updated_at')
    q = request.GET.get('q', '').strip()
    where = request.GET.get('ensemble', '').strip()
    if q:
        for word in q.split():
            scores = scores.filter(Q(title__icontains=word) | Q(composer__icontains=word) |
                                   Q(instrumentation__icontains=word) | Q(part_name__icontains=word))
    if where == 'personal':
        scores = scores.filter(ensemble__isnull=True)
    elif where.isdigit():
        scores = scores.filter(ensemble_id=int(where))
    page = Paginator(scores, 24).get_page(request.GET.get('page'))
    _decorate(page.object_list, user)
    ensembles = Ensemble.objects.filter(memberships__user=user).order_by('name') if settings.WEB_ENSEMBLES else []
    return render(request, 'web/scores/list.html', {
        'page': page, 'q': q, 'where': where, 'ensembles': ensembles,
        'can_upload_to_ensemble': managed_ensembles(user).exists(),
    })


def _store_upload(user, uploaded):
    """업로드 파일을 저장소에 쓰고 키를 돌려준다"""
    key = generate_upload_s3_key(user.id, uploaded.name)
    storage = get_storage()
    if isinstance(storage, LocalStorageHandler):
        storage.write_stream(key, uploaded.chunks(), max_bytes=settings.MAX_UPLOAD_SIZE)
    else:
        storage.write_bytes(key, uploaded.read(), 'application/pdf')
    return key


@login_required
def score_upload(request):
    user = request.user
    initial = {}
    if request.GET.get('ensemble', '').isdigit():
        initial['ensemble'] = int(request.GET['ensemble'])
    form = UploadForm(request.POST or None, request.FILES or None, user=user, initial=initial)
    context = {'form': form, 'max_mb': settings.MAX_UPLOAD_SIZE // (1024 * 1024), 'duplicates': []}
    if request.method == 'POST' and form.is_valid():
        ensemble = form.cleaned_data.get('ensemble')
        items = list(form.items())
        # 같은 곳에 제목 · 파트가 같은 악보가 있으면 먼저 묻는다 — 대개 수정판을 새 악보로 올리는 경우(새 판이 맞다)
        matches = [(title, part, same_title_and_part(user, ensemble, title, part).first()) for _, title, part in items]
        duplicates = [(title, part, existing) for title, part, existing in matches if existing is not None]
        choice = form.cleaned_data['duplicates']
        if duplicates and not choice:
            context['duplicates'] = duplicates
            return render(request, 'web/scores/upload.html', context)

        created, versioned = [], []
        for (uploaded, title, part), (_, _, existing) in zip(items, matches):
            key = _store_upload(user, uploaded)
            if existing is not None and choice == 'version' and existing.can_edit(user):
                version = add_version(existing, user=user, s3_key=key, size_bytes=uploaded.size,
                                      original_filename=uploaded.name, note=form.cleaned_data['note'])
                versioned.append((existing, version))
                continue
            created.append(create_score(
                user=user, s3_key=key, size_bytes=uploaded.size, title=title, original_filename=uploaded.name,
                composer=form.cleaned_data['composer'], instrumentation=form.cleaned_data['instrumentation'],
                tags=form.tag_list(), note=form.cleaned_data['note'], ensemble=ensemble, part_name=part,
            ))
        parts = []
        if created:
            parts.append(f'{len(created)}개를 새로 올렸습니다')
        if versioned:
            parts.append(f'{len(versioned)}개는 새 판으로 올렸습니다')
        messages.success(request, ', '.join(parts) + '.')
        if len(created) + len(versioned) == 1:
            return redirect('web:score_detail', pk=(created[0].pk if created else versioned[0][0].pk))
        return redirect(reverse('web:ensemble_detail', args=[ensemble.pk]) if ensemble else reverse('web:scores'))
    return render(request, 'web/scores/upload.html', context)


def _readable_score(request, pk):
    return get_object_or_404(Score.objects.readable_by(request.user).select_related('ensemble', 'user'), pk=pk)


def _writable_score(request, pk):
    score = _readable_score(request, pk)
    if not score.can_edit(request.user):
        raise PermissionDenied('Only ensemble owners and leaders can change this score.')
    return score


@login_required
def score_detail(request, pk):
    score = _readable_score(request, pk)
    score.thumb = thumbnail_url(score)
    score.editable = score.can_edit(request.user)
    versions = list(score.versions.select_related('uploaded_by').prefetch_related('analyses'))
    form = NewVersionForm(user=request.user) if score.editable else None
    return render(request, 'web/scores/detail.html', {'score': score, 'versions': versions, 'version_form': form})


def _version_or_404(score, number):
    version = score.versions.filter(number=number).first()
    if version is None:
        raise Http404('No such version')
    return version


@login_required
def score_file(request, pk, disposition, number=None):
    """보기(브라우저 PDF 뷰어) · 받기(파일로 저장) — 짧은 서명 URL 로 보낸다. 파일은 Django 를 지나지 않는다.
    number 가 없으면 지금 쓰는 판"""
    score = _readable_score(request, pk)
    if number is None:
        key, original = score.s3_key, score.original_filename
    else:
        version = _version_or_404(score, number)
        key, original = version.s3_key, version.original_filename
    filename = None
    if disposition == 'download':
        stem = original.rsplit('.', 1)[0] if original else score.title
        filename = f'{stem} (v{number}).pdf' if number is not None else (original or f'{score.title}.pdf')
    url = get_storage().generate_presigned_download_url(key, expiry=300, filename=filename)['url']
    return HttpResponseRedirect(url)


@login_required
@require_POST
def version_upload(request, pk):
    score = _writable_score(request, pk)
    form = NewVersionForm(request.POST, request.FILES, user=request.user)
    if form.is_valid():
        uploaded = form.cleaned_data['file']
        key = _store_upload(request.user, uploaded)
        version = add_version(score, user=request.user, s3_key=key, size_bytes=uploaded.size,
                              original_filename=uploaded.name, note=form.cleaned_data['note'])
        messages.success(request, f'판 {version.number} 을(를) 올렸습니다. 이제 이 판을 씁니다.')
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return redirect(reverse('web:score_detail', args=[pk]) + '#versions')


@login_required
@require_POST
def version_make_current(request, pk, number):
    score = _writable_score(request, pk)
    make_current(score, _version_or_404(score, number))
    messages.success(request, f'판 {number} 으로 되돌렸습니다.')
    return redirect(reverse('web:score_detail', args=[pk]) + '#versions')


@login_required
@require_POST
def version_delete(request, pk, number):
    score = _writable_score(request, pk)
    try:
        delete_version(score, _version_or_404(score, number))
        messages.success(request, f'판 {number} 을(를) 지웠습니다.')
    except VersionError:
        messages.error(request, '판이 하나뿐이면 지울 수 없습니다. 악보를 지우세요.')
    return redirect(reverse('web:score_detail', args=[pk]) + '#versions')


@login_required
def score_edit(request, pk):
    score = _writable_score(request, pk)
    form = ScoreEditForm(request.POST or None, instance=score)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, '저장했습니다.')
        return redirect('web:score_detail', pk=score.pk)
    return render(request, 'web/scores/edit.html', {'form': form, 'score': score})


@login_required
def score_delete(request, pk):
    score = _writable_score(request, pk)
    if request.method == 'POST':
        ensemble_id = score.ensemble_id
        title = score.title
        delete_score(score)
        messages.success(request, f'"{title}" 을(를) 지웠습니다.')
        return redirect(reverse('web:ensemble_detail', args=[ensemble_id]) if ensemble_id else reverse('web:scores'))
    return render(request, 'web/scores/delete.html', {'score': score})


# --- 앙상블 ---

def _my_ensemble(request, pk):
    """멤버가 아니면 없는 것과 같다 (404)"""
    return get_object_or_404(Ensemble.objects.filter(memberships__user=request.user), pk=pk)


def _apply(request, action, success):
    """서비스 호출 — 규칙 위반은 메시지로, 권한 없음은 403"""
    try:
        result = action()
    except ensemble_services.RuleError as exc:
        messages.error(request, _rule_message(exc))
        return None, False
    if success:
        messages.success(request, success)
    return result, True


RULE_MESSAGES = {
    'An ensemble must keep at least one owner. Make someone else owner first.':
        '소유자는 적어도 한 명 있어야 합니다. 다른 사람을 소유자로 정한 뒤에 하세요.',
    'Invalid or expired invite code.': '없거나 만료된 초대 코드입니다.',
    'Name cannot be empty': '이름을 적어 주세요.',
}


def _rule_message(exc):
    return RULE_MESSAGES.get(exc.message, exc.message)


@login_required
def ensemble_list(request):
    user = request.user
    form = EnsembleForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ensemble, ok = _apply(request, lambda: ensemble_services.create_ensemble(
            user, form.cleaned_data['name'], form.cleaned_data['description']), '앙상블을 만들었습니다.')
        if ok:
            return redirect('web:ensemble_detail', pk=ensemble.pk)
    memberships = (Membership.objects.filter(user=user).select_related('ensemble')
                   .annotate(member_count=Count('ensemble__memberships', distinct=True),
                             score_count=Count('ensemble__scores', distinct=True))
                   .order_by('ensemble__name'))
    return render(request, 'web/ensembles/list.html', {'form': form, 'memberships': memberships,
                                                        'role_labels': ROLE_LABELS, 'join_form': JoinCodeForm()})


@login_required
def ensemble_detail(request, pk):
    ensemble = _my_ensemble(request, pk)
    mine = ensemble.membership_of(request.user)
    # 총보가 파트 맨 앞에
    full_score = {'총보', 'score', 'full score', 'full'}
    scores = sorted(ensemble.scores.select_related('user', 'ensemble', 'current_version'),
                    key=lambda s: (s.title, s.part_name.strip().lower() not in full_score, s.part_name))
    # 곡(제목)마다 파트를 묶는다 — 앙상블에서는 "블타바: 총보 · Guitar 1 · …" 로 찾는다
    songs = {}
    for score in scores:
        song = songs.setdefault(score.title, {'title': score.title, 'composer': score.composer, 'parts': []})
        song['parts'].append(score)
        song['composer'] = song['composer'] or score.composer
    members = ensemble.memberships.select_related('user').order_by('joined_at')
    invites = []
    if mine.is_manager:
        for invite in ensemble.invites.select_related('created_by')[:20]:
            invite.url = request.build_absolute_uri(reverse('web:join', args=[invite.code]))
            invites.append(invite)
    setlists = ensemble.setlists.annotate(n_items=Count('items', distinct=True)).order_by('-updated_at')
    return render(request, 'web/ensembles/detail.html', {
        'ensemble': ensemble, 'mine': mine, 'scores': scores, 'songs': list(songs.values()), 'setlists': setlists,
        'members': members, 'invites': invites,
        'role_labels': ROLE_LABELS, 'role_choices': Membership.ROLE_CHOICES,
        'edit_form': EnsembleForm(instance=ensemble), 'invite_form': InviteForm(),
    })


@login_required
@require_POST
def ensemble_edit(request, pk):
    ensemble = _my_ensemble(request, pk)
    ensemble_services.require_manager(ensemble, request.user)
    # ModelForm(instance=…) 은 is_valid() 때 instance 를 바꾼다 — 폼에는 복사본을 주고 저장은 서비스로(이름 변경 → TV 재전송)
    form = EnsembleForm(request.POST, instance=Ensemble(pk=ensemble.pk, name=ensemble.name))
    if form.is_valid():
        ensemble_services.update_ensemble(ensemble, request.user, name=form.cleaned_data['name'],
                                          description=form.cleaned_data['description'])
        messages.success(request, '저장했습니다.')
    else:
        messages.error(request, '이름을 적어 주세요.')
    return redirect('web:ensemble_detail', pk=pk)


@login_required
@require_POST
def ensemble_delete(request, pk):
    ensemble = _my_ensemble(request, pk)
    name = ensemble.name
    ensemble_services.delete_ensemble(ensemble, request.user)
    messages.success(request, f'"{name}" 을(를) 지웠습니다. 악보는 올린 사람의 개인 악보로 돌아갔습니다.')
    return redirect('web:ensembles')


@login_required
@require_POST
def member_update(request, pk, user_id):
    ensemble = _my_ensemble(request, pk)
    target = get_object_or_404(Membership, ensemble=ensemble, user_id=user_id)
    form = MemberForm(request.POST)
    if form.is_valid():
        role = form.cleaned_data['role'] or None
        part = request.POST.get('part') if 'part' in request.POST else None
        _apply(request, lambda: ensemble_services.update_member(ensemble, request.user, target, role=role, part=part),
               f'{target.user.username} — 저장했습니다.')
    return redirect('web:ensemble_detail', pk=pk)


@login_required
@require_POST
def member_remove(request, pk, user_id):
    ensemble = _my_ensemble(request, pk)
    target = get_object_or_404(Membership, ensemble=ensemble, user_id=user_id)
    leaving = target.user_id == request.user.id
    _, ok = _apply(request, lambda: ensemble_services.remove_member(ensemble, request.user, target),
                   f'"{ensemble.name}" 에서 나왔습니다.' if leaving else f'{target.user.username} 을(를) 내보냈습니다.')
    if ok and leaving:
        return redirect('web:ensembles')
    return redirect('web:ensemble_detail', pk=pk)


@login_required
@require_POST
def invite_create(request, pk):
    ensemble = _my_ensemble(request, pk)
    form = InviteForm(request.POST)
    if form.is_valid():
        ensemble_services.create_invite(ensemble, request.user, expires_in_days=form.days(),
                                        max_uses=form.cleaned_data['max_uses'])
        messages.success(request, '초대 링크를 만들었습니다. 링크를 복사해 보내세요.')
    return redirect(reverse('web:ensemble_detail', args=[pk]) + '#invites')


@login_required
@require_POST
def invite_revoke(request, pk, invite_id):
    ensemble = _my_ensemble(request, pk)
    invite = get_object_or_404(Invite, ensemble=ensemble, pk=invite_id)
    ensemble_services.revoke_invite(ensemble, request.user, invite)
    messages.success(request, '초대 링크를 취소했습니다.')
    return redirect(reverse('web:ensemble_detail', args=[pk]) + '#invites')


def join(request, code=None):
    """초대 링크 — 로그인하지 않았으면 로그인(또는 가입) 뒤 여기로 돌아온다"""
    if code is None:
        form = JoinCodeForm(request.GET or None)
        if form.is_valid():
            return redirect('web:join', code=ensemble_services.normalize_code(form.cleaned_data['code']))
        return render(request, 'web/join.html', {'form': form, 'invite': None})
    if not request.user.is_authenticated:
        return redirect(f"{reverse('web:login')}?next={reverse('web:join', args=[code])}")

    # 코드 맞히기 방지 — 사용자당 시간당 30번 (API 의 invite 요청 제한과 같은 값)
    key = f'web-join:{request.user.pk}'
    attempts = cache.get(key, 0)
    if attempts >= 30:
        messages.error(request, '초대 코드 확인이 너무 많습니다. 잠시 뒤에 다시 해 주세요.')
        return redirect('web:ensembles')
    cache.set(key, attempts + 1, 3600)

    try:
        invite = ensemble_services.find_usable_invite(code)
    except ensemble_services.RuleError as exc:
        return render(request, 'web/join.html', {'form': JoinCodeForm(), 'invite': None, 'error': _rule_message(exc)},
                      status=404)
    ensemble = invite.ensemble
    if ensemble.is_member(request.user):
        messages.info(request, f'이미 "{ensemble.name}" 멤버입니다.')
        return redirect('web:ensemble_detail', pk=ensemble.pk)
    if request.method == 'POST':
        result, ok = _apply(request, lambda: ensemble_services.join(request.user, code), None)
        if ok:
            messages.success(request, f'"{result[0].name}" 에 들어왔습니다.')
            return redirect('web:ensemble_detail', pk=result[0].pk)
        return redirect('web:ensembles')
    return render(request, 'web/join.html', {'invite': invite, 'member_count': ensemble.memberships.count()})


# --- TV 기기 연결 (RFC 8628) — 규칙은 devices/services.py ---

ACTIVATE_LOOKUP_LIMIT = 30   # 사용자당 시간당 코드 조회 — 코드 맞히기 방지


@login_required
def activate(request):
    """휴대폰에서 TV 코드를 넣는다. QR(verification_uri_complete)로 오면 ?code= 가 채워져 있다"""
    code = (request.POST.get('code') or request.GET.get('code') or '').strip()
    form = ActivateForm(initial={'code': code})
    if not code:
        return render(request, 'web/devices/activate.html', {'form': form})

    key = f'web-activate:{request.user.pk}'
    attempts = cache.get(key, 0)
    if attempts >= ACTIVATE_LOOKUP_LIMIT:
        messages.error(request, '코드 확인이 너무 많습니다. 잠시 뒤에 다시 해 주세요.')
        return render(request, 'web/devices/activate.html', {'form': form}, status=429)
    cache.set(key, attempts + 1, 3600)

    authorization = device_services.find_pending(code)
    if authorization is None:
        return render(request, 'web/devices/activate.html', {
            'form': form, 'error': '없거나 만료된 코드입니다. TV 에 새 코드가 떠 있는지 확인하세요.'}, status=404)

    if request.method == 'POST' and request.POST.get('decision') in ('approve', 'deny'):
        if request.POST['decision'] == 'deny':
            device_services.deny(authorization, request.user)
            messages.info(request, '연결하지 않았습니다.')
            return redirect('web:devices')
        device = device_services.approve(authorization, request.user, name=request.POST.get('name'))
        if device is None:
            messages.error(request, '이 코드는 이미 쓰였거나 만료됐습니다.')
            return redirect('web:activate')
        device_services.set_sync(device, request.POST.get('sync_mode') or Device.SYNC_SETLISTS,
                                 request.POST.getlist('setlists'))
        messages.success(request, f'"{device.name}" 을(를) 연결했습니다. 곧 TV 화면이 바뀝니다.')
        return redirect('web:devices')
    return render(request, 'web/devices/activate.html', {
        'form': form, 'authorization': authorization,
        'setlists': Setlist.objects.readable_by(request.user).order_by('-updated_at'),
    })


@login_required
def device_list(request):
    devices = list(Device.objects.filter(user=request.user).prefetch_related('setlist_links')
                   .order_by('revoked_at', '-last_seen_at', '-created_at'))
    for device in devices:
        device.chosen = {link.setlist_id for link in device.setlist_links.all()}
    return render(request, 'web/devices/list.html', {
        'devices': devices, 'setlists': Setlist.objects.readable_by(request.user).order_by('-updated_at'),
    })


@login_required
@require_POST
def device_sync(request, pk):
    """이 TV 가 받을 것 — 고른 세트리스트만 / 모든 악보"""
    device = _my_device(request, pk)
    mode = request.POST.get('sync_mode')
    if mode not in dict(Device.SYNC_CHOICES):
        return redirect('web:devices')
    device_services.set_sync(device, mode, request.POST.getlist('setlists'))
    if mode == Device.SYNC_ALL:
        messages.success(request, f'"{device.name}" 은(는) 모든 악보를 받습니다.')
    else:
        n = device.setlist_links.count()
        messages.success(request, f'"{device.name}" 은(는) 고른 세트리스트 {n}개의 곡만 받습니다. 빠진 악보는 TV 에서 정리됩니다.')
    return redirect('web:devices')


def _my_device(request, pk):
    return get_object_or_404(Device, pk=pk, user=request.user)


@login_required
@require_POST
def device_rename(request, pk):
    device = _my_device(request, pk)
    form = DeviceNameForm(request.POST)
    if form.is_valid():
        device_services.rename(device, form.cleaned_data['name'])
        messages.success(request, '이름을 바꿨습니다.')
    return redirect('web:devices')


@login_required
@require_POST
def device_revoke(request, pk):
    device = _my_device(request, pk)
    device_services.revoke(device)
    messages.success(request, f'"{device.name}" 연결을 해제했습니다. 그 TV 는 더는 악보를 받지 못합니다.')
    return redirect('web:devices')


# --- 세트리스트 (연주회 곡목) — 권한은 Setlist.objects.readable_by/writable_by, Setlist.can_edit/can_include ---

def _readable_setlist(request, pk):
    return get_object_or_404(Setlist.objects.readable_by(request.user).select_related('ensemble', 'user'), pk=pk)


def _writable_setlist(request, pk):
    setlist = _readable_setlist(request, pk)
    if not setlist.can_edit(request.user):
        raise PermissionDenied('Only ensemble owners and leaders can change this setlist.')
    return setlist


def _ordered_items(setlist, user):
    """곡 순서대로, 읽을 수 있는 악보만"""
    readable = set(Score.objects.readable_by(user).values_list('id', flat=True))
    items = [i for i in setlist.items.select_related('score', 'score__current_version') if i.score_id in readable]
    return sorted(items, key=lambda i: (i.order_index or 0, i.id))


def _renumber(setlist, items):
    for n, item in enumerate(items, start=1):
        if item.order_index != n:
            SetlistItem.objects.filter(pk=item.pk).update(order_index=n)
    Setlist.objects.filter(pk=setlist.pk).update(updated_at=timezone.now())


@login_required
def setlist_list(request):
    form = SetlistForm(request.POST or None, user=request.user, initial={'ensemble': request.GET.get('ensemble')})
    if request.method == 'POST' and form.is_valid():
        setlist = Setlist.objects.create(user=request.user, title=form.cleaned_data['title'],
                                         description=form.cleaned_data['description'],
                                         ensemble=form.cleaned_data.get('ensemble'))
        messages.success(request, '세트리스트를 만들었습니다. 곡을 넣으세요.')
        return redirect('web:setlist_detail', pk=setlist.pk)
    setlists = (Setlist.objects.readable_by(request.user).select_related('ensemble')
                .annotate(n_items=Count('items', distinct=True)).order_by('-updated_at'))
    return render(request, 'web/setlists/list.html', {'setlists': setlists, 'form': form,
                                                      'can_make_ensemble': settings.WEB_ENSEMBLES and managed_ensembles(request.user).exists()})


@login_required
def setlist_detail(request, pk):
    setlist = _readable_setlist(request, pk)
    items = _ordered_items(setlist, request.user)
    candidates = []
    if setlist.can_edit(request.user):
        in_list = {i.score_id for i in items}
        pool = Score.objects.readable_by(request.user)
        pool = pool.filter(ensemble=setlist.ensemble) if setlist.ensemble_id else pool.filter(user=setlist.user)
        candidates = [s for s in pool.order_by('title', 'part_name') if s.id not in in_list]
    devices = list(Device.objects.filter(user=request.user, revoked_at__isnull=True).order_by('name'))
    linked = set(setlist.device_links.filter(device__in=devices).values_list('device_id', flat=True))
    for device in devices:
        device.sends = device.id in linked
    return render(request, 'web/setlists/detail.html', {
        'setlist': setlist, 'items': items, 'editable': setlist.can_edit(request.user), 'candidates': candidates,
        'total_pages': sum(i.score.pages or 0 for i in items), 'devices': devices,
    })


@login_required
@require_POST
def setlist_devices(request, pk):
    """이 세트리스트를 보낼 내 TV — 읽을 수 있는 세트리스트면 누구나 자기 TV 로 받을 수 있다"""
    setlist = _readable_setlist(request, pk)
    chosen = set(request.POST.getlist('devices'))
    for device in Device.objects.filter(user=request.user, revoked_at__isnull=True):
        device_services.toggle_setlist(device, setlist, str(device.pk) in chosen)
    messages.success(request, '보낼 TV 를 저장했습니다.')
    return redirect(reverse('web:setlist_detail', args=[pk]) + '#tv')


@login_required
@require_POST
def setlist_edit(request, pk):
    setlist = _writable_setlist(request, pk)
    title = request.POST.get('title', '').strip()
    if title:
        setlist.title = title[:255]
        setlist.description = request.POST.get('description', '').strip()
        setlist.save(update_fields=['title', 'description', 'updated_at'])
        messages.success(request, '저장했습니다.')
    return redirect('web:setlist_detail', pk=pk)


@login_required
@require_POST
def setlist_delete(request, pk):
    setlist = _writable_setlist(request, pk)
    ensemble_id = setlist.ensemble_id
    setlist.delete()
    messages.success(request, '세트리스트를 지웠습니다. 악보는 그대로입니다.')
    return redirect(reverse('web:ensemble_detail', args=[ensemble_id]) if ensemble_id else reverse('web:setlists'))


@login_required
@require_POST
def setlist_add(request, pk):
    setlist = _writable_setlist(request, pk)
    added = 0
    for score_id in request.POST.getlist('score'):
        score = Score.objects.readable_by(request.user).filter(pk=score_id).first() if score_id.isdigit() else None
        if score is None or not setlist.can_include(score):
            continue
        _, created = SetlistItem.objects.get_or_create(setlist=setlist, score=score)
        added += created
    _renumber(setlist, _ordered_items(setlist, request.user))
    messages.success(request, f'{added}곡을 넣었습니다.')
    return redirect('web:setlist_detail', pk=pk)


@login_required
@require_POST
def setlist_item(request, pk, item_id):
    """위 · 아래 · 빼기 · 메모"""
    setlist = _writable_setlist(request, pk)
    items = _ordered_items(setlist, request.user)
    index = next((n for n, i in enumerate(items) if i.pk == item_id), None)
    if index is None:
        raise Http404('No such item')
    action = request.POST.get('action')
    if action == 'up' and index > 0:
        items[index - 1], items[index] = items[index], items[index - 1]
    elif action == 'down' and index < len(items) - 1:
        items[index + 1], items[index] = items[index], items[index + 1]
    elif action == 'remove':
        items.pop(index).delete()
    elif action == 'notes':
        SetlistItem.objects.filter(pk=item_id).update(notes=request.POST.get('notes', '').strip()[:2000])
    _renumber(setlist, items)
    return redirect(reverse('web:setlist_detail', args=[pk]) + f'#item-{item_id}')


# --- Google 로그인 (web/google.py) ---

def _unique_username(base):
    base = (base or 'user').strip()[:140] or 'user'
    candidate, n = base, 1
    while User.objects.filter(username=candidate).exists():
        n += 1
        candidate = f'{base}{n}'
    return candidate


def google_start(request):
    if not google.enabled():
        raise Http404('Google login is not configured')
    next_url = _safe_next(request, '')
    invite = request.GET.get('invite') or ensemble_services.invite_code_from_next(next_url) or ''
    redirect_uri = request.build_absolute_uri(reverse('web:google_callback'))
    return HttpResponseRedirect(google.authorization_url(request, redirect_uri, next_url, invite))


def google_callback(request):
    """계정 찾기: Google sub 로 연결된 사용자 → 같은 (확인된) 이메일의 사용자에 연결 → 새 사용자(가입 규칙대로)"""
    if not google.enabled():
        raise Http404('Google login is not configured')
    try:
        claims, next_url, invite_code = google.verify_callback(request, request.GET)
    except google.GoogleLoginError as exc:
        logger.info(f'Google login failed: {exc}')
        messages.error(request, 'Google 로그인에 실패했습니다. 다시 해 주세요.')
        return redirect('web:login')

    email = claims['email'].strip().lower()
    account = SocialAccount.objects.select_related('user').filter(
        provider=SocialAccount.PROVIDER_GOOGLE, subject=claims['sub']).first()
    created_user = False
    if account is not None:
        user = account.user
    else:
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            invite = ensemble_services.registration_invite(invite_code)
            if not settings.REGISTRATION_OPEN and invite is None:
                return render(request, 'web/register_closed.html', status=403)
            user = User.objects.create_user(email=email, password=None,
                                            username=_unique_username(claims.get('name') or email.split('@')[0]))
            created_user = True
        account = SocialAccount.objects.create(user=user, provider=SocialAccount.PROVIDER_GOOGLE,
                                               subject=claims['sub'], email=email)
    if not user.is_active:
        messages.error(request, '사용할 수 없는 계정입니다.')
        return redirect('web:login')
    SocialAccount.objects.filter(pk=account.pk).update(last_login_at=timezone.now(), email=email)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')

    if invite_code and ensemble_services.registration_invite(invite_code) is not None:
        try:
            ensemble, joined = ensemble_services.join(user, invite_code)
        except ensemble_services.RuleError:
            ensemble = None
        if ensemble is not None:
            messages.success(request, f'"{ensemble.name}" 에 들어왔습니다.' if joined else f'"{ensemble.name}" 멤버입니다.')
            return redirect('web:ensemble_detail', pk=ensemble.pk)
    if created_user:
        messages.success(request, '가입했습니다.')
    return redirect(next_url or reverse('web:scores'))
