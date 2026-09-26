"""헬스 엔드포인트 — 배포 계약 `smoke` 동사가 찌르는 가벼운 상태 확인 (devdocs guides/web/operations.md §4)

반환: 버전 + DB 연결 + 핵심 행 수. 인증 불요, 가볍게 유지 — 여기서 integrity_check 를 돌리지 않는다
(공개 엔드포인트의 full scan 은 DoS 표면). 비싼 검사는 매시 backup_db.py 가 하고 센티넬 파일로 알린다.

상태 3종:
  ok        200 — 정상
  degraded  200 — backup_db.py 가 DB 손상을 발견(센티넬 존재). 서빙은 되고 있다
  unhealthy 503 — DB 연결 실패 / 마이그레이션 미완
smoke 는 status == "ok" 만 통과시키므로 degraded 가 200 이어도 배포 게이트는 걸린다.
"""
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.http import JsonResponse

from scoremateserver.version import VERSION

# scripts/backup_db.py 가 DB 디렉터리에 남기는 손상 플래그. 이름을 양쪽에서 맞춘다
SENTINEL_NAME = 'INTEGRITY_FAIL'


def _integrity_sentinel():
    """DB 옆에 손상 플래그가 있으면 그 첫 줄"""
    try:
        sentinel = Path(settings.DATABASES['default']['NAME']).parent / SENTINEL_NAME
        return sentinel.read_text().splitlines()[0]
    except (OSError, KeyError, TypeError, IndexError):
        return None


def healthz(request):
    payload = {'status': 'ok', 'version': VERSION, 'db': False, 'counts': {}}
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        payload['db'] = True

        from core.models import User
        from ensembles.models import Ensemble
        from scores.models import Score
        payload['counts'] = {
            'user': User.objects.count(),
            'score': Score.objects.count(),
            'ensemble': Ensemble.objects.count(),
        }
    except Exception as exc:
        payload['status'] = 'unhealthy'
        payload['error'] = str(exc)
        return JsonResponse(payload, status=503)

    if sentinel := _integrity_sentinel():
        payload['status'] = 'degraded'
        payload['integrity'] = sentinel
    return JsonResponse(payload)
