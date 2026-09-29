"""
악보 인식(OMR) — scores/omr.py · manage.py omr_pending / omr_ingest · 웹 MusicXML 받기 (devlog P01)

모델 호출은 호스트 스크립트라 여기서는 결과를 받는 쪽과 조각 합치기(scripts/astra_musicxml.merge)만 본다.
"""
import hashlib
import io
import json
import xml.etree.ElementTree as ET
from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import Client, SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from devices import services as device_services
from devices.models import DeviceSetlist
from setlists.models import Setlist, SetlistItem

from scores import omr
from scores.models import Score, ScoreAnalysis, ScoreVersion
from scores.services import add_version, delete_score, delete_version
from .factories import ScoreFactory
from .test_web import WebTestBase

SHA = 'ab' * 32


def lay_out(version, staves=2):
    """보표 · 마디 분석이 끝난 것으로 — 인식 대기열은 그 판만 고른다"""
    from scores.layouts import ANALYZER, ANALYZER_VERSION
    ScoreAnalysis.objects.update_or_create(version=version, analyzer=ANALYZER, defaults={
        'analyzer_version': ANALYZER_VERSION, 'data': {'staves_counts': {str(staves): 3}, 'layout_key': 'x'}})


def xml(measures=(('1', '6/8', '1'), ('2', None, None)), parts=(('P1', '진호'), ('P2', '예진'))):
    head = ''.join(f'<score-part id="{pid}"><part-name>{name}</part-name></score-part>' for pid, name in parts)
    body = ''
    for pid, _ in parts:
        body += f'<part id="{pid}">'
        for number, time, key in measures:
            attributes = ''
            if time:
                beats, beat_type = time.split('/')
                attributes = (f'<attributes><divisions>2</divisions><key><fifths>{key}</fifths></key>'
                              f'<time><beats>{beats}</beats><beat-type>{beat_type}</beat-type></time>'
                              f'<clef><sign>G</sign><line>2</line></clef></attributes>')
            body += f'<measure number="{number}">{attributes}<note><rest measure="yes"/><duration>6</duration></note></measure>'
        body += '</part>'
    return f'<?xml version="1.0"?><score-partwise version="4.0"><part-list>{head}</part-list>{body}</score-partwise>'


class OmrTest(WebTestBase):

    def setUp(self):
        super().setUp()
        self.score = ScoreFactory(user=self.leader, ensemble=self.ensemble, title='Moldau', content_hash=SHA)
        ScoreVersion.objects.filter(score=self.score).update(content_hash=SHA)
        self.version = self.score.versions.get()
        lay_out(self.version)

    def ingest(self, **bundle):
        bundle = {'version_id': self.version.pk, 'sha256': SHA, 'status': 'ok', 'musicxml': xml(),
                  'run': {'model': 'gpt-6-astra', 'elapsed': 781.4}, **bundle}
        out = io.StringIO()
        with patch('sys.stdin', io.StringIO(json.dumps(bundle))):
            call_command('omr_ingest', stdout=out)
        return out.getvalue()

    def pending(self):
        out = io.StringIO()
        call_command('omr_pending', '--limit', '10', stdout=out)
        return [json.loads(line[len('OMR_JOB '):]) for line in out.getvalue().splitlines() if line.startswith('OMR_JOB ')]

    def test_pending_lists_current_versions_with_hash(self):
        jobs = self.pending()
        self.assertEqual([j['version_id'] for j in jobs], [self.version.pk])
        self.assertEqual((jobs[0]['sha256'], jobs[0]['key'], jobs[0]['title'], jobs[0]['staves_per_system']),
                         (SHA, self.version.s3_key, 'Moldau', 2))

        # 처리 중(해시 없음)인 판은 아직 아니다 · 지금 쓰지 않는 판도 아니다
        ScoreVersion.objects.filter(pk=self.version.pk).update(content_hash='')
        self.assertEqual(self.pending(), [])
        ScoreVersion.objects.filter(pk=self.version.pk).update(content_hash=SHA)
        v2 = add_version(self.score, user=self.leader, s3_key=f'{self.leader.pk}/uploads/v2/original.pdf',
                         size_bytes=1000, original_filename='v2.pdf')
        ScoreVersion.objects.filter(pk=v2.pk).update(content_hash='cd' * 32)
        self.assertEqual(self.pending(), [])                     # 보표 · 마디 분석이 먼저
        lay_out(v2, staves=3)
        self.assertEqual([(j['version_id'], j['staves_per_system']) for j in self.pending()], [(v2.pk, 3)])

    def test_pending_shortest_first(self):
        ScoreVersion.objects.filter(pk=self.version.pk).update(pages=42)
        short = ScoreFactory(user=self.leader, title='Clair de Lune', content_hash='cd' * 32)
        ScoreVersion.objects.filter(score=short).update(content_hash='cd' * 32, pages=4)
        unknown = ScoreFactory(user=self.leader, title='?', content_hash='ef' * 32)
        ScoreVersion.objects.filter(score=unknown).update(content_hash='ef' * 32, pages=None)
        for score in (short, unknown):
            lay_out(score.versions.get())
        self.assertEqual([j['title'] for j in self.pending()], ['Clair de Lune', 'Moldau', '?'])

    def test_ingest_ok_stores_file_and_summary(self):
        out = self.ingest()
        self.assertIn('OMR_RESULT ok', out)
        analysis = ScoreAnalysis.objects.get(version=self.version, analyzer=omr.ANALYZER)
        data = analysis.data
        self.assertEqual(data['status'], 'ok')
        self.assertEqual([p['name'] for p in data['parts']], ['진호', '예진'])
        self.assertEqual((data['measure_count'], data['first_measure'], data['last_measure']), (2, '1', '2'))
        self.assertEqual(data['changes'], [{'measure': '1', 'time': '6/8'}, {'measure': '1', 'key_fifths': 1}])
        self.assertEqual([p['staves'] for p in data['parts']], [1, 1])
        self.assertIsNone(analysis.uploaded_by)
        stored = (self.files_root / data['musicxml_key']).read_text(encoding='utf-8')
        self.assertIn('<score-partwise', stored)
        self.assertEqual(self.pending(), [])   # 끝난 판은 다시 부르지 않는다

    def test_ingest_rejects_other_file_and_bad_xml(self):
        with self.assertRaisesMessage(Exception, 'sha256 does not match'):
            self.ingest(sha256='ef' * 32)
        with self.assertRaisesMessage(Exception, 'not well-formed'):
            self.ingest(musicxml='<score-partwise><part')
        self.assertFalse(ScoreAnalysis.objects.filter(analyzer=omr.ANALYZER).exists())

    def test_breaks_from_layout_at_ingest_and_backfill(self):
        """PDF 분석과 마디 수가 같으면 줄 · 쪽 바뀜을 그 값으로 — 모델 표시와 맞는 수를 남긴다"""
        from scores.layouts import ANALYZER as LAYOUT
        from files.utils import get_storage
        layout = {'measures': [{'pageIndex': 0, 'systemIndex': 0}, {'pageIndex': 1, 'systemIndex': 0}], 'pages': []}
        get_storage().write_bytes('layout.json', json.dumps(layout).encode())
        ScoreAnalysis.objects.filter(version=self.version, analyzer=LAYOUT).update(data={'layout_key': 'layout.json'})
        self.ingest()
        data = ScoreAnalysis.objects.get(version=self.version, analyzer=omr.ANALYZER).data
        self.assertEqual(data['breaks'], {'source': 'layout', 'layout_source': 'pdf', 'agree': 0, 'total': 1, 'model': 0})
        stored = (self.files_root / data['musicxml_key']).read_text()
        self.assertEqual(stored.count('<print new-page="yes" />'), 2)          # 파트 둘의 2마디
        # 이미 끝난 결과에 다시 — 그대로(같은 바뀜)
        self.assertTrue(omr.apply_layout_breaks(self.version))
        # 마디 수가 다르면 하지 않는다
        get_storage().write_bytes('layout.json', json.dumps({'measures': layout['measures'][:1]}).encode())
        self.assertFalse(omr.apply_layout_breaks(self.version))

    def test_page_map_backfill_command(self):
        self.ingest()
        log = '\n'.join(json.dumps(e) for e in [{'pages': [1], 'measures': [1, 1], 'problems': []},
                                                 {'pages': [2], 'measures': [2, 2], 'problems': []}])
        with patch('sys.stdin', io.StringIO(log)):
            call_command('omr_page_map', str(self.version.pk), stdout=io.StringIO())
        data = ScoreAnalysis.objects.get(version=self.version, analyzer=omr.ANALYZER).data
        self.assertEqual(omr.page_map(data, 2), [{'page': 1, 'first': 1, 'last': 1}, {'page': 2, 'first': 2, 'last': 2}])

    def test_failure_is_recorded_and_not_retried(self):
        out = self.ingest(status='failed', musicxml='', problems=['P1 m3: 2 quarters, time signature wants 3'])
        self.assertIn('OMR_RESULT failed', out)
        analysis = ScoreAnalysis.objects.get(version=self.version, analyzer=omr.ANALYZER)
        self.assertEqual(analysis.data['status'], 'failed')
        self.assertEqual(self.pending(), [])
        # 지우면 다시 한다
        analysis.delete()
        self.assertEqual(len(self.pending()), 1)

    def test_web_download_follows_score_permissions(self):
        self.ingest()
        url = reverse('web:version_musicxml', args=[self.score.pk, self.version.number])
        self.client.force_login(self.member)
        page = self.client.get(reverse('web:score_detail', args=[self.score.pk]))
        self.assertContains(page, '악보 인식 · 2파트(진호 · 예진) · 2마디')
        self.assertContains(page, url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/api/v1/files/blob/', response['Location'])
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_detail_shows_recognition_summary(self):
        detail = reverse('web:score_detail', args=[self.score.pk])
        self.client.force_login(self.leader)
        self.assertContains(self.client.get(detail), '악보 인식 전입니다')   # 진행은 "처리" 줄(파이프라인)
        self.ingest()
        page = self.client.get(detail)
        self.assertContains(page, 'id="omr"')
        self.assertContains(page, '<dt>마디</dt><dd>2마디', html=False)
        self.assertContains(page, '<dt>파트</dt><dd>2개 <span class="muted small">· 보표 2개</span></dd>', html=True)
        self.assertContains(page, '<th>보표</th>')
        self.assertContains(page, '6/8 · 샵 1개')
        self.assertContains(page, 'name="part_P2" value="예진"')          # 고칠 수 있는 사람(리더)은 칸
        self.assertContains(page, 'data-player')                           # 들어보기 — 쪽 보기 창 막대에
        self.assertContains(page, 'web/player.js')
        self.assertContains(page, 'data-listen')
        self.assertContains(page, 'id="page-map"')
        self.client.post(reverse('web:version_musicxml_parts', args=[self.score.pk, 1]), {'part_P1': '진호', 'part_P2': '예완'})
        self.client.force_login(self.member)
        page = self.client.get(detail)
        self.assertContains(page, '<td>예완</td>', html=True)              # 멤버는 보기만
        self.assertNotContains(page, 'name="part_P2"')

    def test_no_download_for_failed_result(self):
        self.ingest(status='failed', musicxml='')
        self.client.force_login(self.member)
        self.assertContains(self.client.get(reverse('web:score_detail', args=[self.score.pk])), '악보 인식 실패')
        self.assertEqual(self.client.get(reverse('web:version_musicxml', args=[self.score.pk, 1])).status_code, 404)

    def test_deleting_version_or_score_removes_musicxml(self):
        self.ingest()
        first_key = ScoreAnalysis.objects.get(version=self.version, analyzer=omr.ANALYZER).data['musicxml_key']
        v2 = add_version(self.score, user=self.leader, s3_key=f'{self.leader.pk}/uploads/v2/original.pdf',
                         size_bytes=1000, original_filename='v2.pdf')
        ScoreVersion.objects.filter(pk=v2.pk).update(content_hash='cd' * 32)
        self.version = v2
        self.ingest(sha256='cd' * 32)
        second_key = ScoreAnalysis.objects.get(version=v2, analyzer=omr.ANALYZER).data['musicxml_key']
        self.assertNotEqual(first_key, second_key)

        delete_version(self.score, self.score.versions.get(number=1))
        self.assertFalse((self.files_root / first_key).exists())
        self.assertTrue((self.files_root / second_key).exists())
        self.score.refresh_from_db()
        delete_score(self.score)
        self.assertFalse((self.files_root / second_key).exists())


class PageMapTest(SimpleTestCase):
    """들어보기가 쪽을 따라 넘기는 데 쓰는 쪽별 마디 범위"""

    def test_from_chunks(self):
        data = {'run': {'page_measures': [{'pages': [1, 2], 'first': 1, 'last': 37}, {'pages': [3], 'first': 38, 'last': 50}]}}
        self.assertEqual(omr.page_map(data, 3), [{'page': 1, 'first': 1, 'last': 18}, {'page': 2, 'first': 19, 'last': 37},
                                                  {'page': 3, 'first': 38, 'last': 50}])

    def test_estimate_without_chunks(self):
        self.assertEqual(omr.page_map({'first_measure': '1', 'last_measure': '20'}, 2),
                         [{'page': 1, 'first': 1, 'last': 10, 'estimated': True},
                          {'page': 2, 'first': 11, 'last': 20, 'estimated': True}])
        self.assertEqual(omr.page_map({}, 2), [])

    def test_script_records_passed_chunks(self):
        from scripts.astra_musicxml import page_measures
        entries = [{'pages': [1], 'measures': [1, 13], 'problems': []},
                   {'pages': [2], 'measures': [14, 20], 'problems': ['bad']},
                   {'pages': [2], 'measures': [14, 25], 'problems': []}]
        self.assertEqual(page_measures(entries), [{'pages': [1], 'first': 1, 'last': 13}, {'pages': [2], 'first': 14, 'last': 25}])


class MergeChunksTest(SimpleTestCase):
    """호스트 스크립트의 조각 합치기 — 앞 조각의 상태와 같은 조표 · 박자표 · 음자리표는 지우고 바뀐 것만 남긴다"""

    def test_merge_drops_repeated_attributes(self):
        from scripts.astra_musicxml import end_state, merge
        base = ET.fromstring(xml())
        chunk = ET.fromstring(xml(measures=(('3', '6/8', '1'), ('4', None, None), ('5', '3/4', '1'))))
        merge(base, chunk)
        part = base.find("part[@id='P1']")
        self.assertEqual([m.get('number') for m in part.findall('measure')], ['1', '2', '3', '4', '5'])
        self.assertIsNone(part.find("measure[@number='3']/attributes"))          # 같은 것만 되풀이 — 통째로 빠짐
        m5 = part.find("measure[@number='5']/attributes")
        self.assertEqual(m5.find('time').findtext('beats'), '3')                  # 바뀐 박자표는 남는다
        self.assertIsNotNone(m5.find('key'))    # 조각 가운데는 모델이 적은 그대로 — 지우는 건 조각 첫 마디의 되풀이뿐
        self.assertEqual(end_state(base)['P2']['time'], '3/4')


class ChunkFallbackTest(SimpleTestCase):
    """두 쪽 조각이 안 되면(검산 실패 두 번 · 시간 초과) 한 쪽씩 다시 — 끝난 조각은 다시 부르지 않는다"""

    def run_script(self, answers, pages=3, chunk=2, out=None):
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        import fitz
        from scripts import astra_musicxml as script

        tmp = Path(tempfile.mkdtemp(prefix='omr-'))
        self.addCleanup(__import__('shutil').rmtree, tmp, ignore_errors=True)
        out = out or tmp / 'out'
        document = fitz.open()
        for _ in range(pages):
            document.new_page()
        pdf = tmp / 'score.pdf'
        document.save(pdf)
        calls = []

        def fake_call(images, prompt, workdir, effort, timeout, schema=script.SCHEMA):
            if schema is script.META_SCHEMA:
                return {'title': 'T'}, 1.0, []
            numbers = [int(Path(i).stem[4:]) for i in images]
            calls.append(numbers)
            answer = answers.get(tuple(numbers), 'ok')
            if answer == 'timeout':
                raise subprocess.TimeoutExpired('codex', timeout)
            if answer == 'bad':
                return {'musicxml': '<score-partwise><part', 'first_measure': 0, 'last_measure': 0, 'notes': ''}, 1.0, []
            measures = tuple((str(n), '6/8' if n == numbers[0] else None, '1' if n == numbers[0] else None) for n in numbers)
            return {'musicxml': xml(measures=measures), 'first_measure': numbers[0], 'last_measure': numbers[-1],
                    'notes': ''}, 1.0, []

        def fake_check(text, expected=None):
            try:
                ET.fromstring(text)
            except ET.ParseError as exc:
                return [str(exc)]
            return []

        argv = ['astra_musicxml.py', str(pdf), str(out), '--dpi', '20', '--format', 'musicxml'] + \
            (['--chunk', str(chunk)] if chunk else [])
        with patch.object(script, 'call_astra', fake_call), patch.object(script, 'check', fake_check), \
                patch.object(sys, 'argv', argv):
            code = script.main()
        return code, calls, out

    def test_default_is_one_page_per_call_and_resumes_old_pairs(self):
        code, calls, out = self.run_script({}, chunk=None)
        self.assertEqual((code, calls), (0, [[1], [2], [3]]))
        # 예전 두 쪽 조각(1~2쪽)이 있으면 그대로 쓰고 3쪽만 부른다
        import shutil
        from scripts import astra_musicxml as script
        chunks = out / 'chunks'
        (chunks / 'p001-002').mkdir()
        shutil.copy(chunks / 'p001-001' / 'chunk.musicxml', chunks / 'p001-002' / 'chunk.musicxml')
        shutil.rmtree(chunks / 'p003-003')
        (out / 'score.musicxml').unlink()
        self.assertEqual(script.finished_from(out, 1)[1], 2)
        code, calls, _ = self.run_script({}, chunk=None, out=out)
        self.assertEqual((code, calls), (0, [[3]]))

    def test_bad_pair_is_split_into_single_pages(self):
        code, calls, out = self.run_script({(1, 2): 'bad'})
        self.assertEqual(code, 0)
        self.assertEqual(calls, [[1, 2], [1, 2], [1], [2], [3]])
        merged = ET.parse(out / 'score.musicxml').getroot()
        self.assertEqual([m.get('number') for m in merged.find('part').findall('measure')], ['1', '2', '3'])
        self.assertEqual(json.loads((out / 'result.json').read_text())['metadata'], {'title': 'T'})

    def test_timeout_splits_at_once(self):
        code, calls, _ = self.run_script({(1, 2): 'timeout'})
        self.assertEqual((code, calls), (0, [[1, 2], [1], [2], [3]]))

    def test_single_page_still_bad_is_a_verdict(self):
        code, calls, out = self.run_script({(1, 2): 'bad', (2,): 'bad'})
        self.assertEqual(code, 3)
        self.assertEqual(json.loads((out / 'result.json').read_text())['status'], 'failed')

    def test_finished_chunks_are_not_called_again(self):
        code, calls, out = self.run_script({})
        self.assertEqual(calls, [[1, 2], [3]])
        # 같은 출력 폴더로 다시 — 부르지 않는다(예전 이름 NNN_pA-B 도 알아본다)
        from scripts import astra_musicxml as script
        (out / 'chunks' / 'p001-002').rename(out / 'chunks' / '001_p1-2')
        self.assertIsNotNone(script.finished_chunk(out, [1, 2]))
        self.assertIsNone(script.finished_chunk(out, [2]))


@override_settings(SYNC_LAG_SECONDS=0)
class MusicXmlSyncTest(WebTestBase):
    """기기 동기화 — 인식 결과가 있으면 musicxml(받을 곳 · sha256)이 실리고, 인식이 끝나면 그 악보가 다시 온다"""

    def setUp(self):
        super().setUp()
        self.score = ScoreFactory(user=self.owner, title='Moldau', original_filename='Moldau0607.pdf', content_hash=SHA)
        ScoreVersion.objects.filter(score=self.score).update(content_hash=SHA, original_filename='Moldau0607.pdf')
        Score.objects.filter(pk=self.score.pk).update(updated_at=timezone.now() - timedelta(days=1))
        self.version = self.score.versions.get()
        setlist = Setlist.objects.create(user=self.owner, title='연주회')
        SetlistItem.objects.create(setlist=setlist, score=self.score)
        SetlistItem.objects.filter(setlist=setlist).update(created_at=timezone.now() - timedelta(days=1))
        authorization, _ = device_services.start_authorization('TV')
        device = device_services.approve(authorization, self.owner)
        device_services.set_sync(device, [setlist.pk])
        DeviceSetlist.objects.filter(device=device).update(added_at=timezone.now() - timedelta(days=1))
        self.tv = APIClient()
        self.tv.credentials(HTTP_AUTHORIZATION=f"Bearer {device_services.issue_tokens(device)['access_token']}")

    def ingest(self, **bundle):
        bundle = {'version_id': self.version.pk, 'sha256': SHA, 'status': 'ok', 'musicxml': xml(), **bundle}
        with patch('sys.stdin', io.StringIO(json.dumps(bundle))):
            call_command('omr_ingest', stdout=io.StringIO())

    def test_sync_carries_musicxml_and_device_can_download(self):
        first = self.tv.get('/api/v1/sync/scores/').data
        self.assertIsNone(first['scores'][0]['musicxml'])
        self.assertEqual(self.tv.get(f'/api/v1/scores/{self.score.pk}/musicxml/').status_code, 404)

        self.ingest()
        again = self.tv.get('/api/v1/sync/scores/', {'cursor': first['cursor']}).data   # 인식이 끝나면 다시 온다
        self.assertEqual([s['id'] for s in again['scores']], [self.score.pk])
        info = again['scores'][0]['musicxml']
        stored = ScoreAnalysis.objects.get(version=self.version, analyzer=omr.ANALYZER).data
        self.assertEqual((info['sha256'], info['size_bytes'], info['filename'], info['parts'], info['measures']),
                         (stored['musicxml_sha256'], stored['musicxml_bytes'], 'Moldau0607.musicxml', ['진호', '예진'], 2))
        self.assertTrue(info['url'].endswith(f'/api/v1/scores/{self.score.pk}/musicxml/'))

        redirect = self.tv.get(info['url'])
        self.assertEqual(redirect.status_code, 302)
        body = b''.join(Client().get(redirect['Location']).streaming_content)
        self.assertEqual(hashlib.sha256(body).hexdigest(), info['sha256'])

    def test_renaming_parts_changes_file_and_resends(self):
        """인식이 한글 이름을 잘못 읽었을 때(예완 → 예원) 웹에서 고친다 — 파일 · sha256 이 바뀌고 기기에 다시 온다"""
        self.ingest(musicxml=xml(parts=(('P1', '하진'), ('P2', '예원'))))
        first = self.tv.get('/api/v1/sync/scores/').data
        old = first['scores'][0]['musicxml']
        self.assertEqual(old['parts'], ['하진', '예원'])

        self.client.force_login(self.owner)
        url = reverse('web:version_musicxml_parts', args=[self.score.pk, 1])
        page = self.client.get(url)
        self.assertContains(page, 'value="예원"')
        self.client.post(url, {'part_P1': '하진', 'part_P2': '예완'})

        again = self.tv.get('/api/v1/sync/scores/', {'cursor': first['cursor']}).data
        new = again['scores'][0]['musicxml']
        self.assertEqual(new['parts'], ['하진', '예완'])
        self.assertNotEqual(new['sha256'], old['sha256'])
        body = b''.join(Client().get(self.tv.get(new['url'])['Location']).streaming_content)
        self.assertEqual(hashlib.sha256(body).hexdigest(), new['sha256'])
        self.assertIn('<part-name>예완</part-name>', body.decode())
        self.assertContains(self.client.get(reverse('web:score_detail', args=[self.score.pk])), '하진 · 예완')

    def test_only_editors_rename_parts(self):
        self.ingest()
        url = reverse('web:version_musicxml_parts', args=[self.score.pk, 1])
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(url, {'part_P1': '진호', 'part_P2': '예진'}).status_code, 302)   # 그대로면 바뀐 것 없음

    def test_failed_recognition_is_not_offered(self):
        self.ingest(status='failed', musicxml='')
        self.assertIsNone(self.tv.get('/api/v1/sync/scores/').data['scores'][0]['musicxml'])

    def test_outsider_cannot_download(self):
        self.ingest()
        other = APIClient()
        other.force_authenticate(user=self.outsider)
        self.assertEqual(other.get(f'/api/v1/scores/{self.score.pk}/musicxml/').status_code, 404)
