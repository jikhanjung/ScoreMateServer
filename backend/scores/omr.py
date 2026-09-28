"""
악보 인식(OMR) — PDF → MusicXML. devlog P01

모델 호출은 서버 밖(운영 호스트 cron, deploy/host/omr_lane.sh → scripts/astra_musicxml.py, Codex CLI 의 ChatGPT 로그인)에서 한다.
컨테이너는 두 가지만 한다:
  pending(): 아직 인식하지 않은 판(지금 쓰는 판, 해시 있음) — manage.py omr_pending
  ingest():  호스트가 만든 결과를 받는다 — manage.py omr_ingest (표준 입력 JSON)

결과는 그 판의 분석(ScoreAnalysis, analyzer=ANALYZER)으로 남는다. MusicXML 은 커서 분석 data 가 아니라 저장소 파일로 두고
data 에는 키 · 마디 지도 요약만. 실패도 분석 행(status=failed)으로 남긴다 — 같은 판을 계속 다시 부르지 않게(지우면 다시 한다).
"""
import hashlib
import xml.etree.ElementTree as ET

from django.db import transaction
from django.db.models import F

from files.utils import get_storage
from .models import ScoreAnalysis, ScoreVersion

ANALYZER = 'astra-musicxml'
ANALYZER_VERSION = '1'
MAX_MUSICXML_BYTES = 20 * 1024 * 1024
STATUS_OK = 'ok'
STATUS_FAILED = 'failed'


class OmrError(ValueError):
    pass


def musicxml_key(version):
    return f'{version.score.user_id}/scores/{version.score_id}/omr/v{version.number}.musicxml'


def pending(limit=1):
    """인식할 판 — 지금 쓰는 판 중 해시가 있고 이 분석이 (성공이든 실패든) 아직 없는 것. 쪽수가 적은 것부터
    (한 쪽에 수 분 — 짧은 악보가 긴 악보 뒤에서 하루씩 기다리지 않게), 쪽수를 모르면 맨 뒤, 같으면 오래된 것부터"""
    from .layouts import ANALYZER as LAYOUT
    done = ScoreAnalysis.objects.filter(analyzer=ANALYZER).values('version_id')
    # 보표 · 마디 분석(scores/layouts.py)이 먼저 — 시스템마다 보표 수를 인식에 알려 준다(Arpeggione: 기타 셋을 아르페지오네 + 피아노로 지어냈다)
    laid_out = ScoreAnalysis.objects.filter(analyzer=LAYOUT).values('version_id')
    versions = (ScoreVersion.objects.select_related('score')
                .filter(score__current_version=F('pk'), mime='application/pdf', pk__in=laid_out)
                .exclude(content_hash='').exclude(pk__in=done)
                .order_by(F('pages').asc(nulls_last=True), 'pk'))
    return list(versions[:limit])


def job(version):
    from .layouts import page_systems, staves_per_system
    return {'version_id': version.pk, 'score_id': version.score_id, 'number': version.number,
            'title': version.score.title, 'key': version.s3_key, 'sha256': version.content_hash,
            'pages': version.pages, 'staves_per_system': staves_per_system(version),
            'page_systems': page_systems(version)}


def layout_breaks(xml_text, layout_document):
    """보표 · 마디 분석(PDF 에서 잰 것)으로 줄 · 쪽 바뀜(<print new-system/new-page>)을 정한다 — 마디 수가 같을 때만.
    돌려주는 것: (새 XML 또는 None, {'agree': 모델 표시와 같은 마디 수, 'total': 바뀜 수, 'model': 모델이 표시한 수})"""
    if not layout_document:
        return None, None
    root = ET.fromstring(xml_text)
    parts = root.findall('part')
    measures = [m for m in layout_document.get('measures') or []]
    if not parts or len(parts[0].findall('measure')) != len(measures) or not measures:
        return None, None
    wanted = {}
    for index, m in enumerate(measures):
        if index == 0:
            continue
        prev = measures[index - 1]
        if m['pageIndex'] != prev['pageIndex']:
            wanted[index] = 'new-page'
        elif m['systemIndex'] != prev['systemIndex']:
            wanted[index] = 'new-system'

    def kind(measure):
        p = measure.find('print')
        if p is None:
            return None
        return 'new-page' if p.get('new-page') == 'yes' else 'new-system' if p.get('new-system') == 'yes' else None
    first = parts[0].findall('measure')
    model = {i: kind(m) for i, m in enumerate(first) if kind(m)}
    agree = sum(1 for i, k in wanted.items() if model.get(i) == k)
    for part in parts:
        for index, measure in enumerate(part.findall('measure')):
            for old in measure.findall('print'):
                measure.remove(old)
            if index in wanted:
                measure.insert(0, ET.Element('print', {wanted[index]: 'yes'}))
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode')
    return xml, {'agree': agree, 'total': len(wanted), 'model': len(model)}


def apply_layout_breaks(version):
    """이미 끝난 인식 결과에 PDF 분석의 줄 · 쪽 바뀜을 넣는다(파일 · sha256 을 새로, 기기가 다시 받는다). 바꿨으면 True"""
    from django.utils import timezone
    from .layouts import layout_document
    from .models import Score

    analysis = musicxml_of(version)
    if analysis is None:
        return False
    storage = get_storage()
    key = analysis.data['musicxml_key']
    xml, stats = layout_breaks(storage.read_bytes(key).decode('utf-8'), layout_document(version))
    if xml is None:
        return False
    raw = xml.encode('utf-8')
    storage.write_bytes(key, raw, 'application/vnd.recordare.musicxml+xml')
    data = dict(analysis.data, musicxml_sha256=hashlib.sha256(raw).hexdigest(), musicxml_bytes=len(raw),
                breaks={'source': 'layout', **stats})
    with transaction.atomic():
        ScoreAnalysis.objects.filter(pk=analysis.pk).update(data=data, updated_at=timezone.now())
        Score.objects.filter(pk=version.score_id).update(updated_at=timezone.now())
    return True


def measure_summary(xml_text):
    """파트 · 마디 수 · 박자표/조표 바뀌는 곳 — TV 와 웹이 MusicXML 을 열지 않고도 볼 수 있게"""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise OmrError(f'MusicXML is not well-formed: {exc}') from exc
    if root.tag != 'score-partwise':
        raise OmrError(f'Expected score-partwise, got {root.tag}')
    names = {sp.get('id'): (sp.findtext('part-name') or '').strip() for sp in root.iter('score-part')}
    parts = root.findall('part')
    if not parts:
        raise OmrError('MusicXML has no parts')
    def staves(part):
        text = part.findtext('measure/attributes/staves')
        return int(text) if text and text.isdigit() else 1
    summary = {'parts': [{'id': p.get('id'), 'name': names.get(p.get('id'), ''), 'measures': len(p.findall('measure')),
                          'staves': staves(p)} for p in parts]}
    changes, time_sig, key = [], None, None
    for measure in parts[0].findall('measure'):
        for attributes in measure.findall('attributes'):
            t = attributes.find('time')
            if t is not None:
                value = f"{t.findtext('beats')}/{t.findtext('beat-type')}"
                if value != time_sig:
                    time_sig = value
                    changes.append({'measure': measure.get('number'), 'time': value})
            k = attributes.find('key')
            if k is not None and k.findtext('fifths') != key:
                key = k.findtext('fifths')
                changes.append({'measure': measure.get('number'), 'key_fifths': int(key or 0)})
    numbers = [m.get('number') for m in parts[0].findall('measure')]
    summary.update(measure_count=len(numbers), first_measure=numbers[0] if numbers else None,
                   last_measure=numbers[-1] if numbers else None, changes=changes)
    return summary


def ingest(version, *, sha256, status, musicxml='', run=None, problems=None, metadata=None):
    """호스트 결과 → 분석 행. sha256 은 호스트가 읽은 PDF 의 것 — 그 사이 판이 바뀌었으면 받지 않는다"""
    from .services import save_analysis

    if (sha256 or '').lower() != version.content_hash:
        raise OmrError('sha256 does not match this version (the file changed while it was being read).')
    run = run or {}
    # 첫 쪽에서 읽은 곡 정보(제목 · 작곡 · 편곡 …) — 인식이 실패해도 남긴다. 고치기 화면의 제안
    metadata = {k: str(v)[:500] if not isinstance(v, list) else [str(x)[:100] for x in v[:60]]
                for k, v in (metadata or {}).items() if isinstance(k, str)} if isinstance(metadata, dict) else {}
    if status == STATUS_FAILED:
        data = {'status': STATUS_FAILED, 'problems': list(problems or [])[:50], 'run': run, 'metadata': metadata}
        with transaction.atomic():
            ScoreAnalysis.objects.update_or_create(
                version=version, analyzer=ANALYZER,
                defaults={'analyzer_version': ANALYZER_VERSION, 'data': data, 'uploaded_by': None, 'device': None})
        return None
    if status != STATUS_OK:
        raise OmrError(f'Unknown status: {status}')

    if not musicxml or len(musicxml.encode('utf-8')) > MAX_MUSICXML_BYTES:
        raise OmrError('MusicXML is empty or too large.')
    summary = measure_summary(musicxml)
    # 줄 · 쪽 바뀜: PDF 분석과 마디 수가 같으면 그 값(정확)으로, 아니면 모델이 표시한 그대로(스캔 악보 등)
    from .layouts import layout_document
    with_layout, stats = layout_breaks(musicxml, layout_document(version))
    if with_layout is not None:
        musicxml, breaks = with_layout, {'source': 'layout', **stats}
    else:
        marked = len(ET.fromstring(musicxml).findall('part/measure/print'))
        breaks = {'source': 'model' if marked else 'none', 'model': marked}
    raw = musicxml.encode('utf-8')
    key = musicxml_key(version)
    get_storage().write_bytes(key, raw, 'application/vnd.recordare.musicxml+xml')
    data = {'status': STATUS_OK, 'musicxml_key': key, 'musicxml_sha256': hashlib.sha256(raw).hexdigest(),
            'musicxml_bytes': len(raw), **summary, 'run': run, 'metadata': metadata, 'breaks': breaks}
    analysis, _ = save_analysis(version.score, user=version.score.user, analyzer=ANALYZER,
                                analyzer_version=ANALYZER_VERSION, sha256=sha256, data=data, version=version)
    ScoreAnalysis.objects.filter(pk=analysis.pk).update(uploaded_by=None)   # 사람이 올린 것이 아니다
    return analysis


def musicxml_of(version):
    """이 판의 성공한 인식 결과(분석) 또는 None"""
    analysis = next((a for a in version.analyses.all() if a.analyzer == ANALYZER), None)
    if analysis is not None and analysis.data.get('status') == STATUS_OK and analysis.data.get('musicxml_key'):
        return analysis
    return None


def rename_parts(version, names):
    """인식 결과의 파트 이름을 고친다(한글 이름은 원/완처럼 비슷한 글자를 잘못 읽기 쉽다). names: {part id: 새 이름}

    저장된 MusicXML 의 <part-name> 을 바꿔 다시 쓰고, 분석 data(parts · sha256 · 크기)를 맞춘다.
    악보 updated_at 을 올려 기기가 다음 동기화에 다시 받게 한다(musicxml.sha256 이 바뀐다). 바뀐 수를 돌려준다
    """
    from django.utils import timezone
    from .models import Score

    analysis = musicxml_of(version)
    if analysis is None:
        raise OmrError('No MusicXML for this version.')
    names = {pid: ' '.join(str(name).split())[:100] for pid, name in names.items() if str(name).strip()}
    storage = get_storage()
    key = analysis.data['musicxml_key']
    raw = storage.read_bytes(key)
    root = ET.fromstring(raw)
    changed = 0
    for score_part in root.iter('score-part'):
        new = names.get(score_part.get('id'))
        element = score_part.find('part-name')
        if new and element is not None and (element.text or '') != new:
            element.text = new
            changed += 1
    if not changed:
        return 0
    raw = ('<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode')).encode('utf-8')
    storage.write_bytes(key, raw, 'application/vnd.recordare.musicxml+xml')
    data = dict(analysis.data)
    data['parts'] = [dict(p, name=names.get(p.get('id'), p.get('name', ''))) for p in data.get('parts', [])]
    data.update(musicxml_sha256=hashlib.sha256(raw).hexdigest(), musicxml_bytes=len(raw),
                parts_renamed_at=timezone.now().isoformat())
    with transaction.atomic():
        ScoreAnalysis.objects.filter(pk=analysis.pk).update(data=data, updated_at=timezone.now())
        Score.objects.filter(pk=version.score_id).update(updated_at=timezone.now())
    return changed


def page_map(data, pages):
    """[{'page', 'first', 'last'}] — 쪽마다 마디 범위. 인식 기록(run.page_measures)이 있으면 그것으로
    (여러 쪽을 한 번에 옮긴 조각은 마디를 쪽 수로 나눈다), 없으면 전체 마디를 쪽 수로 고르게 나눈 짐작"""
    result = []
    for chunk in (data.get('run') or {}).get('page_measures') or []:
        try:
            first, last, chunk_pages = int(chunk['first']), int(chunk['last']), list(chunk['pages'])
        except (KeyError, TypeError, ValueError):
            continue
        span = (last - first + 1) / max(len(chunk_pages), 1)
        for index, page in enumerate(chunk_pages):
            result.append({'page': page, 'first': first + int(span * index),
                           'last': first + int(span * (index + 1)) - 1 if index < len(chunk_pages) - 1 else last})
    if result:
        return sorted(result, key=lambda item: item['page'])
    try:
        first, last = int(data.get('first_measure')), int(data.get('last_measure'))
    except (TypeError, ValueError):
        return []
    if not pages:
        return []
    span = (last - first + 1) / pages
    return [{'page': p + 1, 'first': first + int(span * p), 'last': first + int(span * (p + 1)) - 1 if p < pages - 1 else last,
             'estimated': True} for p in range(pages)]


def refresh_summary(version):
    """저장된 MusicXML 로 요약(parts 의 staves 등)을 다시 만든다 — 요약에 칸을 더했을 때 옛 결과를 맞춘다"""
    analysis = musicxml_of(version)
    if analysis is None:
        return None
    summary = measure_summary(get_storage().read_bytes(analysis.data['musicxml_key']).decode('utf-8'))
    names = {p['id']: p['name'] for p in analysis.data.get('parts', [])}      # 사람이 고친 이름은 그대로
    for part in summary['parts']:
        part['name'] = names.get(part['id'], part['name'])
    data = dict(analysis.data, **summary)
    ScoreAnalysis.objects.filter(pk=analysis.pk).update(data=data)
    return summary


def set_page_measures(version, page_measures):
    """이미 끝난 인식에 쪽별 마디를 채운다(호스트에 남은 조각 기록으로) — 들어보기가 쪽을 따라 넘기게"""
    analysis = musicxml_of(version)
    if analysis is None:
        raise OmrError('No MusicXML for this version.')
    data = dict(analysis.data)
    data['run'] = dict(data.get('run') or {}, page_measures=page_measures)
    ScoreAnalysis.objects.filter(pk=analysis.pk).update(data=data)


def summary_for(version):
    """악보 상세의 "악보 인식" 칸 — {'status': ok|failed|waiting|none, …}"""
    if version is None:
        return {'status': 'none'}
    analysis = next((a for a in version.analyses.all() if a.analyzer == ANALYZER), None)
    if analysis is None:
        if not version.content_hash or version.score.current_version_id != version.pk:
            return {'status': 'none'}
        queue = [v.pk for v in pending(limit=1000)]
        return {'status': 'waiting', 'position': queue.index(version.pk) + 1 if version.pk in queue else None}
    data = analysis.data or {}
    run = data.get('run') or {}
    info = {'status': data.get('status'), 'analysis': analysis, 'updated_at': analysis.updated_at,
            'metadata': data.get('metadata') or {}, 'elapsed_minutes': round((run.get('elapsed_seconds') or 0) / 60),
            'problems': data.get('problems') or []}
    if data.get('status') == STATUS_OK:
        signatures = []
        for change in data.get('changes') or []:
            if 'time' in change:
                signatures.append(f"{change['time']} ({change['measure']}마디부터)" if change['measure'] not in ('1', '0')
                                  else change['time'])
            if 'key_fifths' in change:
                fifths = change['key_fifths']
                text = f'샵 {fifths}개' if fifths > 0 else f'플랫 {-fifths}개' if fifths < 0 else '조표 없음'
                signatures.append(f"{text} ({change['measure']}마디부터)" if change['measure'] not in ('1', '0') else text)
        info.update(measures=data.get('measure_count'), first=data.get('first_measure'), last=data.get('last_measure'),
                    parts=data.get('parts') or [], signatures=signatures, bytes=data.get('musicxml_bytes'),
                    renamed=bool(data.get('parts_renamed_at')), page_map=page_map(data, version.pages),
                    staves_total=sum(int(p.get('staves') or 1) for p in data.get('parts') or []),
                    breaks=data.get('breaks') or {})
    return info


def musicxml_filename(score, version):
    """받을 때 파일 이름 — PDF 와 같은 이름에 .musicxml (기기가 PDF 옆에 둔다)"""
    original = version.original_filename or score.original_filename or f'{score.title}.pdf'
    return original.rsplit('.', 1)[0] + '.musicxml'


def stored_keys(versions):
    """지울 때 함께 지울 분석 파일들 — MusicXML, 보표 · 마디 분석(scores/layouts.py)"""
    keys = []
    for analysis in ScoreAnalysis.objects.filter(version__in=versions):
        data = analysis.data if isinstance(analysis.data, dict) else {}
        keys += [data[k] for k in ('musicxml_key', 'layout_key') if data.get(k)]
    return keys
