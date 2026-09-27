"""
악보 만들기 · 지우기 — API(upload-confirm · ViewSet)와 웹(Django 템플릿)이 같은 규칙을 쓰게 한 곳에 둔다
"""
import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Max

from .models import Score, ScoreVersion

logger = logging.getLogger(__name__)


def size_mb(size_bytes):
    """쿼터 단위 — 올릴 때 더하고 지울 때 빼는 값이 같아야 한다"""
    return size_bytes // (1024 * 1024)


def start_processing(score):
    """페이지 수 · SHA-256 · 표지 썸네일. REDIS_URL 이 없으면 요청 안에서 바로 돈다.
    실패해도 악보 만들기는 성공시킨다(결과는 Task 기록 · 로그에)"""
    try:
        from tasks.pdf_tasks import process_pdf_info, generate_thumbnail
        process_pdf_info.delay(score.id)
        generate_thumbnail.delay(score.id, page_number=1)
    except Exception as e:
        logger.warning(f"Failed to queue background tasks for score {score.id}: {e}")


def create_score(*, user, s3_key, size_bytes, title, mime='application/pdf', original_filename='',
                 composer='', instrumentation='', tags=None, note='', ensemble=None, part_name='',
                 charge_quota=True):
    """파일이 이미 저장소에 있는 악보를 만든다. 앙상블 권한은 호출자가 먼저 확인한다"""
    with transaction.atomic():
        score = Score.objects.create(
            user=user, title=title, original_filename=original_filename or '',
            composer=composer or '', instrumentation=instrumentation or '',
            s3_key=s3_key, size_bytes=size_bytes, mime=mime or 'application/pdf',
            tags=tags or [], note=note or '', ensemble=ensemble, part_name=part_name or '',
        )
        if charge_quota:
            # type(user) 가 아니라 get_user_model — 웹의 request.user 는 SimpleLazyObject 다
            get_user_model().objects.filter(pk=user.pk).update(used_quota_mb=F('used_quota_mb') + size_mb(size_bytes))
    start_processing(score)
    return score


class VersionError(ValueError):
    """판 규칙 위반 (예: 하나뿐인 판을 지우기)"""


def _mirror(score, version):
    """판을 '지금 쓰는 판'으로 — Score 의 파일 필드를 그 판으로 맞춘다(updated_at 이 바뀌어 동기화가 알아챈다)"""
    score.current_version = version
    score.s3_key = version.s3_key
    score.original_filename = version.original_filename
    score.size_bytes = version.size_bytes
    score.mime = version.mime
    score.pages = version.pages
    score.content_hash = version.content_hash
    score.save()


def add_version(score, *, user, s3_key, size_bytes, original_filename='', mime='application/pdf', note='',
                charge_quota=True):
    """새 판을 올려 지금 쓰는 판으로 만든다. 쓰기 권한(score.can_edit)은 호출자가 확인한다.
    쿼터는 **이 판을 올린 사람**에게 매긴다"""
    with transaction.atomic():
        locked = Score.objects.select_for_update().get(pk=score.pk)
        # 지운 판의 번호도 다시 쓰지 않는다
        number = max(locked.last_version_number, locked.versions.aggregate(n=Max('number'))['n'] or 0) + 1
        locked.last_version_number = number
        version = ScoreVersion.objects.create(
            score=locked, number=number, s3_key=s3_key, original_filename=original_filename or '',
            size_bytes=size_bytes, mime=mime or 'application/pdf', uploaded_by=user, note=note or '',
        )
        _mirror(locked, version)   # pages · content_hash 는 비고 처리 작업이 채운다
        if charge_quota:
            get_user_model().objects.filter(pk=user.pk).update(used_quota_mb=F('used_quota_mb') + size_mb(size_bytes))
    start_processing(locked)
    return version


def make_current(score, version):
    """예전 판으로 되돌린다(판은 지우지 않는다). 썸네일은 그 판으로 다시 만든다"""
    if version.score_id != score.pk:
        raise VersionError('Version does not belong to this score.')
    with transaction.atomic():
        _mirror(Score.objects.select_for_update().get(pk=score.pk), version)
    from tasks.pdf_tasks import generate_thumbnail
    try:
        generate_thumbnail.delay(score.pk, page_number=1)
    except Exception as e:
        logger.warning(f"Failed to queue thumbnail for score {score.pk}: {e}")


def delete_version(score, version):
    """판 하나를 지운다. 하나뿐이면 안 된다(악보를 지운다). 지금 쓰는 판이면 남은 것 중 가장 최근 판으로.
    쿼터는 그 판을 올린 사람에게 돌려준다"""
    if version.score_id != score.pk:
        raise VersionError('Version does not belong to this score.')
    with transaction.atomic():
        locked = Score.objects.select_for_update().get(pk=score.pk)
        if locked.versions.count() <= 1:
            raise VersionError('A score keeps at least one version. Delete the score instead.')
        was_current = locked.current_version_id == version.pk
        s3_key = version.s3_key
        if version.uploaded_by_id:
            get_user_model().objects.filter(pk=version.uploaded_by_id).update(
                used_quota_mb=F('used_quota_mb') - size_mb(version.size_bytes))
        version.delete()
        if was_current:
            _mirror(locked, locked.versions.order_by('-number').first())
    from tasks.file_tasks import delete_single_file
    delete_single_file.delay(s3_key)
    if was_current:
        make_current(locked, locked.current_version)   # 썸네일을 그 판으로


def delete_score(score):
    """악보와 모든 판을 지운다. 쿼터는 **판마다 올린 사람**에게 돌려준다(앙상블 악보를 리더가 지워도)"""
    versions = list(score.versions.all())
    refunds = {}
    for version in versions:
        if version.uploaded_by_id:
            refunds[version.uploaded_by_id] = refunds.get(version.uploaded_by_id, 0) + size_mb(version.size_bytes)
    if not versions:    # 판 없는 옛 행(이론상) — 올린 사람 기준
        refunds[score.user_id] = size_mb(score.size_bytes)
    s3_key, thumbnail_key, score_id = score.s3_key, score.thumbnail_key, score.id
    other_keys = [v.s3_key for v in versions if v.s3_key != s3_key]
    with transaction.atomic():
        User = get_user_model()
        for user_id, mb in refunds.items():
            User.objects.filter(pk=user_id).update(used_quota_mb=F('used_quota_mb') - mb)
        score.delete()
    from tasks.file_tasks import delete_score_files, delete_single_file
    delete_score_files.delay(s3_key, thumbnail_key, score_id)
    for key in other_keys:
        delete_single_file.delay(key)


class AnalysisError(ValueError):
    """code: processing(아직 해시 없음) · mismatch(다른 파일의 분석) · not_newer(더 새 분석기가 아님) · too_large"""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def save_analysis(score, *, user, analyzer, analyzer_version, sha256, data, device_id=None, version=None):
    """TV 가 만든 분석을 판에 붙인다. (analysis, created)

    - 분석한 파일이 그 판의 파일이어야 한다(SHA-256)
    - 이미 있으면: 멤버는 더 새 분석기 버전일 때만 바꾼다, owner · leader 는 언제나
    - 악보 updated_at 을 올린다 — 멤버 TV 가 동기화로 알아채게
    """
    import json
    from django.utils import timezone
    from .models import ScoreAnalysis, version_key

    version = version or score.current_version
    if version is None or not version.content_hash:
        raise AnalysisError('processing', 'The file of this version is still being processed. Try again later.')
    if (sha256 or '').lower() != version.content_hash:
        raise AnalysisError('mismatch', 'sha256 does not match this version of the score.')
    if len(json.dumps(data, separators=(',', ':')).encode()) > ScoreAnalysis.MAX_BYTES:
        raise AnalysisError('too_large', 'Analysis data is too large.')

    with transaction.atomic():
        existing = ScoreAnalysis.objects.select_for_update().filter(version=version, analyzer=analyzer).first()
        if existing is not None and not score.can_edit(user) and \
                version_key(analyzer_version) <= version_key(existing.analyzer_version):
            raise AnalysisError('not_newer', 'An analysis from the same or a newer analyzer already exists.')
        fields = dict(analyzer_version=analyzer_version, data=data, uploaded_by=user, device_id=device_id)
        if existing is None:
            analysis = ScoreAnalysis.objects.create(version=version, analyzer=analyzer, **fields)
        else:
            for name, value in fields.items():
                setattr(existing, name, value)
            existing.save()
            analysis = existing
        Score.objects.filter(pk=score.pk).update(updated_at=timezone.now())
    return analysis, existing is None
