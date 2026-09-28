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
ANALYZER_VERSION = str(score_layout.FORMAT_VERSION)


def layout_key(version):
    return f'{version.score.user_id}/scores/{version.score_id}/layout/v{version.number}.json'


def analyze_version(version, pdf_bytes=None):
    """그 판의 PDF 를 분석해 파일 · 분석 행으로 남긴다. 해시가 아직 없으면 하지 않는다. 분석 행을 돌려준다"""
    from .services import save_analysis

    if not version.content_hash:
        return None
    storage = get_storage()
    pdf_bytes = pdf_bytes if pdf_bytes is not None else storage.read_bytes(version.s3_key)
    if hashlib.sha256(pdf_bytes).hexdigest() != version.content_hash:
        logger.warning('score layout: file of version %s changed while reading — skipped', version.pk)
        return None
    pages = score_layout.analyze(pdf_bytes)
    document = score_layout.to_document(pages, version.content_hash)
    raw = json.dumps(document, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    key = layout_key(version)
    storage.write_bytes(key, raw, 'application/json')
    signatures = []
    for page in document['pages']:
        for mark in page['timeSignatures']:
            signatures.append({'page': page['pageIndex'] + 1, 'system': mark['systemIndex'] + 1,
                               'time': f"{mark['numerator']}/{mark['denominator']}"})
    labels = sorted({s['label'] for s in document['staves'] if s.get('label')})
    data = {'status': 'ok', 'layout_key': key, 'layout_sha256': hashlib.sha256(raw).hexdigest(), 'layout_bytes': len(raw),
            'page_count': document['page_count'], 'system_count': document['system_count'],
            'measure_count': document['measure_count'], 'time_signatures': signatures[:50], 'labels': labels[:50],
            'source': score_layout.SOURCE}
    analysis, _ = save_analysis(version.score, user=version.score.user, analyzer=ANALYZER,
                                analyzer_version=ANALYZER_VERSION, sha256=version.content_hash, data=data, version=version)
    ScoreAnalysis.objects.filter(pk=analysis.pk).update(uploaded_by=None)
    return analysis


def layout_of(version):
    analysis = next((a for a in version.analyses.all() if a.analyzer == ANALYZER), None)
    if analysis is not None and (analysis.data or {}).get('layout_key'):
        return analysis
    return None


def layout_filename(score, version):
    original = version.original_filename or score.original_filename or f'{score.title}.pdf'
    return original.rsplit('.', 1)[0] + '.layout.json'


def missing(limit=None):
    """분석 파일이 없는 판(해시 있음)"""
    done = ScoreAnalysis.objects.filter(analyzer=ANALYZER).values('version_id')
    versions = ScoreVersion.objects.select_related('score').exclude(content_hash='').exclude(pk__in=done).order_by('pk')
    return list(versions[:limit] if limit else versions)
