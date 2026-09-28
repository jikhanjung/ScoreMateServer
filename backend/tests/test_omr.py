"""
악보 인식(OMR) — scores/omr.py · manage.py omr_pending / omr_ingest · 웹 MusicXML 받기 (devlog P01)

모델 호출은 호스트 스크립트라 여기서는 결과를 받는 쪽과 조각 합치기(scripts/astra_musicxml.merge)만 본다.
"""
import io
import json
import xml.etree.ElementTree as ET
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase
from django.urls import reverse

from scores import omr
from scores.models import ScoreAnalysis, ScoreVersion
from scores.services import add_version, delete_score, delete_version
from .factories import ScoreFactory
from .test_web import WebTestBase

SHA = 'ab' * 32


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
        self.assertEqual((jobs[0]['sha256'], jobs[0]['key'], jobs[0]['title']), (SHA, self.version.s3_key, 'Moldau'))

        # 처리 중(해시 없음)인 판은 아직 아니다 · 지금 쓰지 않는 판도 아니다
        ScoreVersion.objects.filter(pk=self.version.pk).update(content_hash='')
        self.assertEqual(self.pending(), [])
        ScoreVersion.objects.filter(pk=self.version.pk).update(content_hash=SHA)
        v2 = add_version(self.score, user=self.leader, s3_key=f'{self.leader.pk}/uploads/v2/original.pdf',
                         size_bytes=1000, original_filename='v2.pdf')
        ScoreVersion.objects.filter(pk=v2.pk).update(content_hash='cd' * 32)
        self.assertEqual([j['version_id'] for j in self.pending()], [v2.pk])

    def test_ingest_ok_stores_file_and_summary(self):
        out = self.ingest()
        self.assertIn('OMR_RESULT ok', out)
        analysis = ScoreAnalysis.objects.get(version=self.version, analyzer=omr.ANALYZER)
        data = analysis.data
        self.assertEqual(data['status'], 'ok')
        self.assertEqual([p['name'] for p in data['parts']], ['진호', '예진'])
        self.assertEqual((data['measure_count'], data['first_measure'], data['last_measure']), (2, '1', '2'))
        self.assertEqual(data['changes'], [{'measure': '1', 'time': '6/8'}, {'measure': '1', 'key_fifths': 1}])
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
        self.assertContains(page, '악보 인식 · 2파트 · 2마디')
        self.assertContains(page, url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/api/v1/files/blob/', response['Location'])
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_no_download_for_failed_result(self):
        self.ingest(status='failed', musicxml='')
        self.client.force_login(self.member)
        self.assertContains(self.client.get(reverse('web:score_detail', args=[self.score.pk])), '악보 인식 실패')
        self.assertEqual(self.client.get(reverse('web:version_musicxml', args=[self.score.pk, 1])).status_code, 404)

    def test_deleting_version_or_score_removes_musicxml(self):
        self.ingest()
        first_key = ScoreAnalysis.objects.get(version=self.version).data['musicxml_key']
        v2 = add_version(self.score, user=self.leader, s3_key=f'{self.leader.pk}/uploads/v2/original.pdf',
                         size_bytes=1000, original_filename='v2.pdf')
        ScoreVersion.objects.filter(pk=v2.pk).update(content_hash='cd' * 32)
        self.version = v2
        self.ingest(sha256='cd' * 32)
        second_key = ScoreAnalysis.objects.get(version=v2).data['musicxml_key']
        self.assertNotEqual(first_key, second_key)

        delete_version(self.score, self.score.versions.get(number=1))
        self.assertFalse((self.files_root / first_key).exists())
        self.assertTrue((self.files_root / second_key).exists())
        self.score.refresh_from_db()
        delete_score(self.score)
        self.assertFalse((self.files_root / second_key).exists())


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

    def run_script(self, answers, pages=3):
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        import fitz
        from scripts import astra_musicxml as script

        tmp = Path(tempfile.mkdtemp(prefix='omr-'))
        self.addCleanup(__import__('shutil').rmtree, tmp, ignore_errors=True)
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

        argv = ['astra_musicxml.py', str(pdf), str(tmp / 'out'), '--dpi', '20']
        with patch.object(script, 'call_astra', fake_call), patch.object(script, 'check', fake_check), \
                patch.object(sys, 'argv', argv):
            code = script.main()
        return code, calls, tmp / 'out'

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
