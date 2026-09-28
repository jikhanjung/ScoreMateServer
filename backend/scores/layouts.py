"""
보표 · 마디 분석 파일 — scores/score_layout.py(앱 분석을 그대로 옮긴 것)를 판마다 돌려 저장소에 JSON 으로 둔다.
기기는 동기화 응답의 layout(url · sha256)으로 받아 PDF 를 스스로 분석하지 않고 쓸 수 있다(MusicXML 과 같이).

결과는 그 판의 분석(ScoreAnalysis, analyzer=ANALYZER)이고, 파일은 {user}/scores/{score}/layout/v{N}.json.
올리기 요청 안에서는 돌리지 않는다(35쪽에 수 초) — 운영 호스트 cron(deploy/host/layout_lane.sh)이 manage.py score_layout 으로
분석이 없는 판을 채운다.
"""
import hashlib
import json
import logging

from files.utils import get_storage
from . import score_layout
from .models import ScoreAnalysis, ScoreVersion

logger = logging.getLogger(__name__)

ANALYZER = 'score-layout'
# 분석기 버전 = 서버 분석 코드 판(SERVER_REVISION) + 기준으로 옮긴 앱 score/ 커밋(APP_COMMIT). 둘 중 하나가 바뀌면 바뀐다 →
# 레인이 모든 판을 다시 분석하고, 기기는 동기화 응답의 layout.analyzer_version 이 바뀐 것을 보고 다시 받는다
# (앱이 DB 마이그레이션으로 분석 캐시를 비워 오던 것을 대신한다 — TV 요청)
SERVER_REVISION = 2             # 서버 분석 코드(scores/score_layout.py)를 고칠 때마다 1씩 올린다
APP_COMMIT = '9557497'           # MrgqPdfViewer app/src/main/java/com/mrgq/pdfviewer/score/ (2026-09-28)
ANALYZER_VERSION = f'{SERVER_REVISION}+app.{APP_COMMIT}'


def layout_key(version):
    return f'{version.score.user_id}/scores/{version.score_id}/layout/v{version.number}.json'


def analyze_version(version, pdf_bytes=None):
    """그 판의 PDF 를 분석해 파일 · 분석 행으로 남긴다. 해시가 아직 없으면 하지 않는다. 분석 행을 돌려준다"""
    from django.db import transaction
    from django.utils import timezone
    from .models import Score

    if not version.content_hash:
        return None
    storage = get_storage()
    pdf_bytes = pdf_bytes if pdf_bytes is not None else storage.read_bytes(version.s3_key)
    if hashlib.sha256(pdf_bytes).hexdigest() != version.content_hash:
        logger.warning('score layout: file of version %s changed while reading — skipped', version.pk)
        return None
    pages = score_layout.analyze(pdf_bytes)
    document = score_layout.to_document(pages, version.content_hash)
    document.update(analyzer=ANALYZER, analyzer_version=ANALYZER_VERSION, app_commit=APP_COMMIT)
    raw = json.dumps(document, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    key = layout_key(version)
    storage.write_bytes(key, raw, 'application/json')
    signatures = []
    for page in document['pages']:
        for mark in page['timeSignatures']:
            signatures.append({'page': page['pageIndex'] + 1, 'system': mark['systemIndex'] + 1,
                               'time': f"{mark['numerator']}/{mark['denominator']}"})
    labels = sorted({s['label'] for s in document['staves'] if s.get('label')})
    from collections import Counter
    staves_counts = dict(Counter(str(len(s['staffBands'])) for p in document['pages'] for s in p['systems']))
    data = {'status': 'ok', 'layout_key': key, 'layout_sha256': hashlib.sha256(raw).hexdigest(), 'layout_bytes': len(raw),
            'page_count': document['page_count'], 'system_count': document['system_count'],
            'measure_count': document['measure_count'], 'time_signatures': signatures[:50], 'labels': labels[:50],
            'staves_counts': staves_counts,
            'source': score_layout.SOURCE}
    data.update(analyzer_version=ANALYZER_VERSION, app_commit=APP_COMMIT)
    with transaction.atomic():
        analysis, _ = ScoreAnalysis.objects.update_or_create(
            version=version, analyzer=ANALYZER,
            defaults={'analyzer_version': ANALYZER_VERSION, 'data': data, 'uploaded_by': None, 'device': None})
        Score.objects.filter(pk=version.score_id).update(updated_at=timezone.now())   # 기기가 다음 동기화에 알아채게
    return analysis


def staves_per_system(version):
    """이 판의 시스템마다 보표 수(가장 많은 값) — 없으면 None. 악보 인식이 파트를 지어내지 않게 알려 준다"""
    from collections import Counter
    analysis = next((a for a in version.analyses.all() if a.analyzer == ANALYZER), None) if hasattr(version, 'analyses') else None
    if analysis is None:
        return None
    counts = (analysis.data or {}).get('staves_counts')
    if not counts:
        try:
            document = json.loads(get_storage().read_bytes(analysis.data['layout_key']))
        except Exception:  # noqa: BLE001
            return None
        counts = dict(Counter(str(len(s['staffBands'])) for p in document['pages'] for s in p['systems']))
    if not counts:
        return None
    return int(max(counts.items(), key=lambda item: (item[1], item[0]))[0])


def layout_of(version):
    analysis = next((a for a in version.analyses.all() if a.analyzer == ANALYZER), None)
    if analysis is not None and (analysis.data or {}).get('layout_key'):
        return analysis
    return None


def layout_filename(score, version):
    original = version.original_filename or score.original_filename or f'{score.title}.pdf'
    return original.rsplit('.', 1)[0] + '.layout.json'


def missing(limit=None):
    """분석 파일이 없거나 옛 분석기 버전인 판(해시 있음)"""
    done = ScoreAnalysis.objects.filter(analyzer=ANALYZER, analyzer_version=ANALYZER_VERSION).values('version_id')
    versions = ScoreVersion.objects.select_related('score').exclude(content_hash='').exclude(pk__in=done).order_by('pk')
    return list(versions[:limit] if limit else versions)
