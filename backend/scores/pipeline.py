"""
악보 처리 파이프라인의 상태 — 호스트 오케스트레이터(scripts/score_pipeline.py)가 읽는다. devlog 072

판마다 세 단계(이 순서로):
  ① PDF 분석(scores/layouts.py, 컨테이너 · 수 초)
  ② 모델 위치(scores/model_layouts.py, 모델 · 쪽당 30초)  — 벡터는 ①의 검산, 스캔은 기기 layout
  ③ 악보 인식(scores/omr.py, 모델 · 쪽당 2~4분)           — ②가 끝난 뒤, 믿을 수 있는 위치(① 또는 ②)로 검산
진행(쪽 단위)은 오케스트레이터가 캐시에 알린다(progress) — 상세 화면이 보여 준다.
"""
from django.core.cache import cache
from django.db.models import F

from . import layouts, model_layouts, omr
from .models import ScoreVersion

PROGRESS_KEY = 'pipeline:progress:{}'
PROGRESS_TTL = 6 * 3600


def stage_status(version):
    by = {a.analyzer: a for a in version.analyses.all()}

    def state(analyzer, current_version=None):
        a = by.get(analyzer)
        if a is None or (current_version and a.analyzer_version != current_version):
            return 'none'
        return (a.data or {}).get('status') or 'ok'
    pdf = by.get(layouts.ANALYZER)
    return {
        'pdf': 'ok' if pdf is not None and pdf.analyzer_version == layouts.ANALYZER_VERSION else 'none',
        'pdf_systems': ((pdf.data or {}).get('system_count') or 0) if pdf else 0,
        'model': state(model_layouts.ANALYZER),
        'omr': state(omr.ANALYZER),
    }


def jobs():
    """할 일이 남은 지금 판들 — 오케스트레이터가 우선순위를 정한다"""
    versions = (ScoreVersion.objects.select_related('score').prefetch_related('analyses')
                .filter(score__current_version=F('pk'), mime='application/pdf').exclude(content_hash='')
                .order_by(F('pages').asc(nulls_last=True), 'pk'))
    out = []
    for version in versions:
        status = stage_status(version)
        if status['pdf'] == 'ok' and status['model'] != 'none' and status['omr'] != 'none':
            continue
        hints = layouts.pipeline_hints(version) if status['pdf'] == 'ok' and status['model'] != 'none' else {}
        out.append({'version_id': version.pk, 'score_id': version.score_id, 'title': version.score.title,
                    'pages': version.pages, 'key': version.s3_key, 'sha256': version.content_hash,
                    **status, 'staves': hints.get('staves'), 'page_systems': hints.get('page_systems'),
                    'hint_source': hints.get('source')})
    return out


def set_progress(version_id, stage, done, total):
    cache.set(PROGRESS_KEY.format(version_id), {'stage': stage, 'done': done, 'total': total}, PROGRESS_TTL)


def progress(version):
    return cache.get(PROGRESS_KEY.format(version.pk)) if version else None


def clear_progress(version_id):
    cache.delete(PROGRESS_KEY.format(version_id))
