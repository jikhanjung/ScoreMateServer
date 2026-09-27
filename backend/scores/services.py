"""
악보 만들기 · 지우기 — API(upload-confirm · ViewSet)와 웹(Django 템플릿)이 같은 규칙을 쓰게 한 곳에 둔다
"""
import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F

from .models import Score

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


def delete_score(score):
    """악보를 지우고, 쿼터는 **올린 사람**에게 돌려주고(앙상블 악보를 리더가 지워도), 파일을 지운다"""
    s3_key, thumbnail_key, score_id = score.s3_key, score.thumbnail_key, score.id
    with transaction.atomic():
        get_user_model().objects.filter(pk=score.user_id).update(
            used_quota_mb=F('used_quota_mb') - size_mb(score.size_bytes))
        score.delete()
    from tasks.file_tasks import delete_score_files
    delete_score_files.delay(s3_key, thumbnail_key, score_id)
