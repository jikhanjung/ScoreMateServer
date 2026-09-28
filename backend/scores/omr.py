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
    done = ScoreAnalysis.objects.filter(analyzer=ANALYZER).values('version_id')
    versions = (ScoreVersion.objects.select_related('score')
                .filter(score__current_version=F('pk'), mime='application/pdf')
                .exclude(content_hash='').exclude(pk__in=done)
                .order_by(F('pages').asc(nulls_last=True), 'pk'))
    return list(versions[:limit])


def job(version):
    return {'version_id': version.pk, 'score_id': version.score_id, 'number': version.number,
            'title': version.score.title, 'key': version.s3_key, 'sha256': version.content_hash,
            'pages': version.pages}


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
    summary = {'parts': [{'id': p.get('id'), 'name': names.get(p.get('id'), ''), 'measures': len(p.findall('measure'))}
                         for p in parts]}
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

    raw = musicxml.encode('utf-8')
    if not raw or len(raw) > MAX_MUSICXML_BYTES:
        raise OmrError('MusicXML is empty or too large.')
    summary = measure_summary(musicxml)
    key = musicxml_key(version)
    get_storage().write_bytes(key, raw, 'application/vnd.recordare.musicxml+xml')
    data = {'status': STATUS_OK, 'musicxml_key': key, 'musicxml_sha256': hashlib.sha256(raw).hexdigest(),
            'musicxml_bytes': len(raw), **summary, 'run': run, 'metadata': metadata}
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


def stored_keys(versions):
    """지울 때 함께 지울 MusicXML 파일들"""
    return [a.data['musicxml_key'] for a in ScoreAnalysis.objects.filter(version__in=versions, analyzer=ANALYZER)
            if isinstance(a.data, dict) and a.data.get('musicxml_key')]
