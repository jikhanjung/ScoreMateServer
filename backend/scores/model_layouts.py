"""
모델이 읽은 보표 · 마디 위치 — 호스트 레인(scripts/model_layout.py, Codex CLI)이 쪽마다 0..1000 좌표로 읽고, 여기서 pt 와
TV 앱의 ScoreLayout 모양(scores/score_layout.to_document — PDF 분석 파일과 같은 모양)으로 바꿔 저장한다. devlog 070 · 071

- 벡터 PDF: PDF 분석(scores/layouts.py)이 정답이다 → 이것은 **검산**(쪽마다 시스템 · 보표 · 마디선 개수와 pt 오차를 남긴다)
- 스캔 PDF: PDF 분석은 시스템을 못 찾는다 → 기기에는 **이 파일을 layout 으로** 내린다(동기화 layout.source = 'model')

결과: 판의 분석(ScoreAnalysis, analyzer=ANALYZER) + 파일 {user}/scores/{score}/model_layout/v{N}.json
"""
import hashlib
import json

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from files.utils import get_storage
from . import score_layout
from .models import Score, ScoreAnalysis, ScoreVersion

ANALYZER = 'model-layout'
ANALYZER_VERSION = '1'


class ModelLayoutError(ValueError):
    pass


def model_layout_key(version):
    return f'{version.score.user_id}/scores/{version.score_id}/model_layout/v{version.number}.json'


def pending(limit=1):
    """모델 위치를 아직 읽지 않은 지금 판 — 쪽수가 적은 것부터"""
    done = ScoreAnalysis.objects.filter(analyzer=ANALYZER).values('version_id')
    versions = (ScoreVersion.objects.select_related('score')
                .filter(score__current_version=F('pk'), mime='application/pdf')
                .exclude(content_hash='').exclude(pk__in=done)
                .order_by(F('pages').asc(nulls_last=True), 'pk'))
    return list(versions[:limit])


def job(version):
    return {'version_id': version.pk, 'score_id': version.score_id, 'title': version.score.title,
            'key': version.s3_key, 'sha256': version.content_hash, 'pages': version.pages}


def page_sizes(pdf_bytes):
    """쪽마다 (폭, 높이) pt — PDF 분석과 같은 CropBox 규칙"""
    import fitz
    with fitz.open(stream=pdf_bytes, filetype='pdf') as doc:
        out = []
        for page in doc:
            llx, lly, urx, ury = score_layout._page_box(doc, page)
            out.append((score_layout.f32(urx - llx), score_layout.f32(ury - lly)))
        return out


def to_pages(read_pages, sizes):
    """모델이 읽은 쪽들(0..1000) → [PageLayout](pt, 위→아래 · 왼쪽 위 원점 — 앱 좌표와 같다)"""
    by_number = {p['page']: p for p in read_pages}
    pages = []
    for index, (width, height) in enumerate(sizes):
        fx, fy = width / 1000, height / 1000
        systems, marks = [], []
        for system_index, s in enumerate((by_number.get(index + 1) or {}).get('systems') or []):
            x0, y0, x1, y1 = s['bbox']
            left, right = score_layout.round1(x0 * fx), score_layout.round1(x1 * fx)
            names = s.get('staff_names') or []
            systems.append(score_layout.SystemLayout(
                top=score_layout.round1(y0 * fy), bottom=score_layout.round1(y1 * fy), left=left, right=right,
                staff_bands=[(score_layout.round1(t * fy), score_layout.round1(b * fy)) for t, b in s['staves']],
                barlines=[left] + [score_layout.round1(x * fx) for x in s['barlines'] if x * fx > left + 4],
                staff_labels=[(n or '').strip() or None for n in names]))
            for mark in s.get('time_signatures') or []:
                marks.append(score_layout.TimeSignatureMark(system_index, score_layout.f32(mark['x'] * fx),
                                                            int(mark['numerator']), int(mark['denominator'])))
        pages.append(score_layout.PageLayout(index, width, height, systems, marks))
    return pages


def agreement(model_doc, pdf_doc):
    """PDF 분석과 비교 — 쪽마다 구조(시스템 · 보표 · 마디선 개수)가 같은가, 같은 쪽의 좌표 오차(pt)"""
    if not pdf_doc or not pdf_doc.get('system_count'):
        return None
    same, compared, errors, differs = 0, 0, [], []
    for mp, pp in zip(model_doc['pages'], pdf_doc['pages']):
        if not pp['systems'] and not mp['systems']:
            continue
        compared += 1
        structure = len(mp['systems']) == len(pp['systems']) and all(
            len(a['staffBands']) == len(b['staffBands']) and len(a['barlines']) == len(b['barlines'])
            for a, b in zip(mp['systems'], pp['systems']))
        if not structure:
            differs.append(pp['pageIndex'] + 1)
            continue
        same += 1
        for a, b in zip(mp['systems'], pp['systems']):
            errors += [abs(a[k] - b[k]) for k in ('top', 'bottom', 'left', 'right')]
            errors += [abs(x - y) for (t1, b1), (t2, b2) in zip(a['staffBands'], b['staffBands']) for x, y in ((t1, t2), (b1, b2))]
            errors += [abs(x - y) for x, y in zip(a['barlines'][1:], b['barlines'][1:])]
    return {'pages_compared': compared, 'pages_same': same, 'pages_differ': differs[:30],
            'mean_pt': round(sum(errors) / len(errors), 2) if errors else None,
            'max_pt': round(max(errors), 2) if errors else None}


def ingest(version, *, sha256, status, pages=None, run=None, problems=None):
    from .layouts import layout_document

    if (sha256 or '').lower() != version.content_hash:
        raise ModelLayoutError('sha256 does not match this version.')
    if status != 'ok':
        data = {'status': 'failed', 'problems': list(problems or [])[:50], 'run': run or {}}
        ScoreAnalysis.objects.update_or_create(version=version, analyzer=ANALYZER, defaults={
            'analyzer_version': ANALYZER_VERSION, 'data': data, 'uploaded_by': None, 'device': None})
        return None
    storage = get_storage()
    pdf_bytes = storage.read_bytes(version.s3_key)
    if hashlib.sha256(pdf_bytes).hexdigest() != version.content_hash:
        raise ModelLayoutError('The file of this version changed.')
    layout_pages = to_pages(pages or [], page_sizes(pdf_bytes))
    document = score_layout.to_document(layout_pages, version.content_hash)
    document.update(analyzer=ANALYZER, analyzer_version=ANALYZER_VERSION, measured_by='model',
                    model=(run or {}).get('model'))
    raw = json.dumps(document, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    key = model_layout_key(version)
    storage.write_bytes(key, raw, 'application/json')
    data = {'status': 'ok', 'layout_key': key, 'layout_sha256': hashlib.sha256(raw).hexdigest(), 'layout_bytes': len(raw),
            'page_count': document['page_count'], 'system_count': document['system_count'],
            'measure_count': document['measure_count'], 'run': run or {},
            'agreement': agreement(document, layout_document(version))}
    with transaction.atomic():
        analysis, _ = ScoreAnalysis.objects.update_or_create(version=version, analyzer=ANALYZER, defaults={
            'analyzer_version': ANALYZER_VERSION, 'data': data, 'uploaded_by': None, 'device': None})
        Score.objects.filter(pk=version.score_id).update(updated_at=timezone.now())
    return analysis


def model_layout_of(version):
    analysis = next((a for a in version.analyses.all() if a.analyzer == ANALYZER), None)
    if analysis is not None and (analysis.data or {}).get('status') == 'ok' and analysis.data.get('layout_key'):
        return analysis
    return None
