"""
모델이 읽은 보표 · 마디 위치 (scores/model_layouts.py · scripts/model_layout.py) — pt 변환 · 앱 ScoreLayout 모양 파일 ·
PDF 분석과의 검산 · 스캔 악보(PDF 분석 없음)에서는 기기에 이것을 내린다. devlog 070 · 071

모델 호출 대신 PDF 분석 결과(Moldau)를 0..1000 좌표로 바꿔 "모델이 읽은 것"으로 넣는다.
"""
import hashlib
import io
import json
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import Client, SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from devices import services as device_services
from scores import layouts, model_layouts, score_layout
from scores.models import Score, ScoreAnalysis
from setlists.models import Setlist, SetlistItem
from .test_web import WebTestBase, pdf_file

FIXTURES = Path(__file__).parent / 'fixtures' / 'score'


def as_model_reading(document):
    """PDF 분석 파일 → 모델이 읽은 모양(쪽마다 0..1000 정수)"""
    pages = []
    for page in document['pages']:
        fx, fy = 1000 / page['widthPt'], 1000 / page['heightPt']
        systems = []
        for s in page['systems']:
            systems.append({
                'bbox': [round(s['left'] * fx), round(s['top'] * fy), round(s['right'] * fx), round(s['bottom'] * fy)],
                'staves': [[round(t * fy), round(b * fy)] for t, b in s['staffBands']],
                'barlines': [round(x * fx) for x in s['barlines'][1:]],
                'staff_names': ['' for _ in s['staffBands']],
                'time_signatures': [{'x': round(m['x'] * fx), 'numerator': m['numerator'], 'denominator': m['denominator']}
                                    for m in page['timeSignatures'] if page['systems'].index(s) == m['systemIndex']],
            })
        pages.append({'page': page['pageIndex'] + 1, 'systems': systems, 'notes': ''})
    return pages


class ScriptCheckTest(SimpleTestCase):

    def test_check_rules(self):
        from scripts.model_layout import check
        good = {'systems': [{'bbox': [70, 100, 930, 300], 'staves': [[100, 150], [250, 300]], 'barlines': [400, 930],
                             'staff_names': ['', ''], 'time_signatures': []}]}
        self.assertEqual(check(good), [])
        bad = {'systems': [{'bbox': [70, 100, 930, 300], 'staves': [[120, 150]], 'barlines': [930, 400],
                            'staff_names': ['a', 'b'], 'time_signatures': []}]}
        joined = ' | '.join(check(bad))
        self.assertIn('first staff top', joined)
        self.assertIn('barlines must be increasing', joined)
        self.assertIn('one staff name per staff', joined)
        self.assertEqual(check({'systems': []}), [])            # 악보가 아닌 쪽


@override_settings(SYNC_LAG_SECONDS=0)
class ModelLayoutTest(WebTestBase):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        self.client.post(reverse('web:score_upload'), {
            'files': [pdf_file('Moldau0607.pdf', (FIXTURES / 'Moldau0607.pdf').read_bytes())], 'title': 'Moldau'})
        self.score = Score.objects.get(user=self.owner)
        self.version = self.score.current_version
        layouts.analyze_version(self.version)
        self.pdf_document = layouts.layout_document(self.version)

    def ingest(self, pages, status='ok'):
        bundle = {'version_id': self.version.pk, 'sha256': self.version.content_hash, 'status': status, 'pages': pages,
                  'run': {'model': 'gpt-6-astra', 'calls': 13}, 'problems': ['page 3: bad'] if status != 'ok' else []}
        out = io.StringIO()
        with patch('sys.stdin', io.StringIO(json.dumps(bundle))):
            call_command('model_layout_ingest', stdout=out)
        return out.getvalue()

    def test_pending_and_job(self):
        out = io.StringIO()
        call_command('model_layout_pending', '--limit', '5', stdout=out)
        jobs = [json.loads(line[len('MLAYOUT_JOB '):]) for line in out.getvalue().splitlines() if line.startswith('MLAYOUT_JOB ')]
        self.assertEqual([(j['version_id'], j['sha256']) for j in jobs], [(self.version.pk, self.version.content_hash)])

    def test_reading_becomes_app_layout_and_agrees_with_pdf(self):
        out = self.ingest(as_model_reading(self.pdf_document))
        self.assertIn('MLAYOUT_RESULT ok', out)
        data = ScoreAnalysis.objects.get(version=self.version, analyzer=model_layouts.ANALYZER).data
        self.assertEqual((data['system_count'], data['measure_count']), (26, 81))
        agreement = data['agreement']
        self.assertEqual((agreement['pages_compared'], agreement['pages_same'], agreement['pages_differ']), (13, 13, []))
        self.assertLess(agreement['max_pt'], 0.9)                # 0..1000 눈금 한 칸(세로 0.84pt) 안
        document = json.loads((self.files_root / data['layout_key']).read_text())
        self.assertEqual(document['measured_by'], 'model')
        self.assertEqual(document['measures'][0]['timeSigNumerator'], 6)      # 박자표도 앱 행으로
        self.assertEqual(len(document['staves']), 26 * 5)
        self.assertEqual(model_layouts.pending(), [])
        page = self.client.get(reverse('web:score_detail', args=[self.score.pk]))
        self.assertContains(page, 'PDF 분석과 13/13쪽 같음')

    def test_time_signatures_repeated_per_staff_become_one_per_system(self):
        reading = as_model_reading(self.pdf_document)
        mark = reading[0]['systems'][0]['time_signatures'][0]
        reading[0]['systems'][0]['time_signatures'] = [dict(mark, x=mark['x'] + dx) for dx in (0, 1, -1, 2, 0)]  # 보표 다섯
        self.ingest(reading)
        data = ScoreAnalysis.objects.get(version=self.version, analyzer=model_layouts.ANALYZER).data
        document = json.loads((self.files_root / data['layout_key']).read_text())
        self.assertEqual([(t['systemIndex'], t['numerator'], t['denominator']) for t in document['pages'][0]['timeSignatures']],
                         [(0, 6, 8)])

    def test_structure_difference_is_reported(self):
        reading = as_model_reading(self.pdf_document)
        reading[2]['systems'][0]['barlines'].pop(0)              # 3쪽 첫 시스템 마디선 하나를 놓쳤다
        self.ingest(reading)
        agreement = ScoreAnalysis.objects.get(version=self.version, analyzer=model_layouts.ANALYZER).data['agreement']
        self.assertEqual((agreement['pages_same'], agreement['pages_differ']), (12, [3]))

    def test_failure_is_recorded(self):
        self.assertIn('MLAYOUT_RESULT failed', self.ingest([], status='failed'))
        self.assertEqual(model_layouts.pending(), [])
        self.assertIsNone(model_layouts.model_layout_of(self.version))

    def test_scanned_score_gets_model_layout_on_devices(self):
        """PDF 분석이 시스템을 못 찾은 악보(스캔본) — 기기에는 모델이 읽은 위치가 layout 으로 내려간다"""
        setlist = Setlist.objects.create(user=self.owner, title='연주회')
        SetlistItem.objects.create(setlist=setlist, score=self.score)
        authorization, _ = device_services.start_authorization('TV')
        device = device_services.approve(authorization, self.owner)
        device_services.set_sync(device, [setlist.pk])
        tv = APIClient()
        tv.credentials(HTTP_AUTHORIZATION=f"Bearer {device_services.issue_tokens(device)['access_token']}")
        self.assertEqual(tv.get('/api/v1/sync/scores/').data['scores'][0]['layout']['source'], 'pdf')

        self.ingest(as_model_reading(self.pdf_document))
        pdf = ScoreAnalysis.objects.get(version=self.version, analyzer=layouts.ANALYZER)
        pdf.data = dict(pdf.data, system_count=0, measure_count=0)   # 스캔본이라 PDF 분석이 비었다고 치자
        pdf.save()
        info = tv.get('/api/v1/sync/scores/').data['scores'][0]['layout']
        self.assertEqual((info['source'], info['measures']), ('model', 81))
        body = b''.join(Client().get(tv.get(info['url'])['Location']).streaming_content)
        self.assertEqual(hashlib.sha256(body).hexdigest(), info['sha256'])
        self.assertEqual(json.loads(body)['measured_by'], 'model')
