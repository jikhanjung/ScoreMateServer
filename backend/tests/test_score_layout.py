"""
보표 · 마디 분석 — TV 앱 score/ 를 옮긴 scores/score_layout.py 가 앱의 골든 테스트(ScoreLayoutAnalyzerTest)와 같은 결과를 내는가,
그리고 판마다 파일로 저장 · 동기화 · 받기 · 지우기 (scores/layouts.py)

픽스처는 앱 저장소 app/src/androidTest/assets/score/ 와 같은 파일이다:
  Moldau0607.pdf — Sibelius → Microsoft Print to PDF 5파트 총보, 13쪽
  Moldau0607_layout.json — 파이썬 원본 분석 결과(26 시스템 / 81 마디, 인쇄된 마디 번호와 육안 대조 #037)
"""
import hashlib
import json
from datetime import timedelta
from pathlib import Path

from django.test import Client, SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from devices import services as device_services
from scores import layouts, score_layout
from scores.models import Score, ScoreAnalysis
from scores.services import delete_score
from setlists.models import Setlist, SetlistItem
from .test_web import WebTestBase, pdf_file

FIXTURES = Path(__file__).parent / 'fixtures' / 'score'
TOL = 0.6


class GoldenLayoutTest(SimpleTestCase):
    """앱 ScoreLayoutAnalyzerTest 와 같은 단언"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pages = score_layout.analyze(str(FIXTURES / 'Moldau0607.pdf'))
        cls.golden = json.loads((FIXTURES / 'Moldau0607_layout.json').read_text())

    def test_26_systems_81_measures(self):
        self.assertEqual(len(self.pages), 13)
        self.assertEqual(sum(len(p.systems) for p in self.pages), 26)
        self.assertEqual(sum(s.measure_count for p in self.pages for s in p.systems), 81)

    def test_systems_measures_barlines_bands_match(self):
        for page in self.pages:
            expected = self.golden[str(page.page_index + 1)]
            self.assertEqual(len(expected), len(page.systems), f'p{page.page_index + 1}')
            for i, (system, e) in enumerate(zip(page.systems, expected)):
                where = f'p{page.page_index + 1} s{i + 1}'
                self.assertEqual(e['n_measures'], system.measure_count, where)
                self.assertEqual(len(e['barlines']), len(system.barlines), where)
                for a, b in zip(e['barlines'], system.barlines):
                    self.assertAlmostEqual(a, b, delta=TOL, msg=where)
                for key, value in (('y_top', system.top), ('y_bot', system.bottom), ('x_left', system.left),
                                   ('x_right', system.right)):
                    self.assertAlmostEqual(e[key], value, delta=TOL, msg=f'{where} {key}')
                self.assertEqual(len(e['staff_bands']), len(system.staff_bands), where)
                for (et, eb), (t, b) in zip(e['staff_bands'], system.staff_bands):
                    self.assertAlmostEqual(et, t, delta=TOL, msg=where)
                    self.assertAlmostEqual(eb, b, delta=TOL, msg=where)

    def test_measure_numbers_follow_print(self):
        measures = score_layout.to_measures(self.pages)
        firsts, seen = [], set()
        for m in measures:
            if (m['pageIndex'], m['systemIndex']) not in seen:
                seen.add((m['pageIndex'], m['systemIndex']))
                firsts.append(m['measureNumber'])
        self.assertEqual(firsts[:6], [1, 5, 8, 11, 14, 17])
        self.assertEqual(measures[-1]['measureNumber'], 81)

    def test_time_signature_6_8_applies_to_every_measure(self):
        marks = [(p.page_index, m) for p in self.pages for m in p.time_signatures]
        self.assertEqual(len(marks), 1)
        page_index, mark = marks[0]
        self.assertEqual((page_index, mark.system_index, mark.numerator, mark.denominator), (0, 0, 6, 8))
        self.assertEqual({(m['timeSigNumerator'], m['timeSigDenominator']) for m in score_layout.to_measures(self.pages)},
                         {(6, 8)})

    def test_staves_rows_like_app(self):
        staves = score_layout.to_staves(self.pages)
        self.assertEqual(len(staves), 26 * 5)
        self.assertEqual(set(staves[0]), {'pageIndex', 'systemIndex', 'staffIndex', 'topPt', 'bottomPt', 'label'})
        self.assertTrue(all(s['label'] is None for s in staves))   # Moldau 는 이름이 글자가 아니다(앱도 못 읽는다)


class InterpreterTest(SimpleTestCase):
    """PathContentInterpreter 의 규칙 몇 가지 — 끝점만 · re 네 모서리 · q/Q · 폼 · 텍스트 위치 · 문자열 건너뛰기"""

    def run_content(self, content, resolver=None):
        return score_layout.ContentInterpreter().run(content, resolver)

    def test_paths(self):
        it = self.run_content(b'q 2 0 0 2 10 10 cm 0 0 m 5 0 l S Q 0 0 m 10 10 20 20 30 0 c f 5 5 10 2 re f (ignored 1 2 l) Tj')
        boxes = [(b.x0, b.y0, b.x1, b.y1, b.curved) for b in it.boxes]
        self.assertEqual(boxes, [(10, 10, 20, 10, False), (0, 0, 30, 0, True), (5, 5, 15, 7, False)])

    def test_text_position_and_size(self):
        class Fonts:
            def decode_text(self, font, data):
                return data.decode('latin-1')

            def form(self, name):
                return None
        it = self.run_content(b'0.75 0 0 0.75 0 0 cm BT /F1 20 Tf 1 0 0 1 100 200 Tm (6) Tj 0 -10 Td [(8)] TJ ET', Fonts())
        self.assertEqual([(t.text, t.x, t.y, t.size) for t in it.texts], [('6', 75, 150, 15), ('8', 75, 142.5, 15)])


@override_settings(SYNC_LAG_SECONDS=0)
class LayoutFileTest(WebTestBase):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        self.client.post(reverse('web:score_upload'), {
            'files': [pdf_file('Moldau0607.pdf', (FIXTURES / 'Moldau0607.pdf').read_bytes())], 'title': 'Moldau'})
        self.score = Score.objects.get(user=self.owner)
        self.version = self.score.current_version
        self.assertEqual([v.pk for v in layouts.missing()], [self.version.pk])   # 올리기는 분석하지 않는다(레인이 한다)
        layouts.analyze_version(self.version)

    def test_analysis_stores_layout_file(self):
        analysis = ScoreAnalysis.objects.get(version=self.version, analyzer=layouts.ANALYZER)
        data = analysis.data
        self.assertEqual((data['page_count'], data['system_count'], data['measure_count']), (13, 26, 81))
        self.assertEqual(data['time_signatures'], [{'page': 1, 'system': 1, 'time': '6/8'}])
        raw = (self.files_root / data['layout_key']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), data['layout_sha256'])
        document = json.loads(raw)
        self.assertEqual(document['format'], score_layout.FORMAT)
        self.assertEqual(document['pdf_sha256'], self.version.content_hash)
        self.assertEqual(len(document['measures']), 81)
        self.assertEqual(document['measures'][0]['timeSigNumerator'], 6)

    def test_sync_and_device_download(self):
        setlist = Setlist.objects.create(user=self.owner, title='연주회')
        SetlistItem.objects.create(setlist=setlist, score=self.score)
        authorization, _ = device_services.start_authorization('TV')
        device = device_services.approve(authorization, self.owner)
        device_services.set_sync(device, [setlist.pk])
        tv = APIClient()
        tv.credentials(HTTP_AUTHORIZATION=f"Bearer {device_services.issue_tokens(device)['access_token']}")
        info = tv.get('/api/v1/sync/scores/').data['scores'][0]['layout']
        self.assertEqual((info['measures'], info['systems'], info['filename'], info['analyzer_version'], info['pdf_sha256']),
                         (81, 26, 'Moldau0607.layout.json', layouts.ANALYZER_VERSION, self.version.content_hash))
        body = b''.join(Client().get(tv.get(info['url'])['Location']).streaming_content)
        self.assertEqual(hashlib.sha256(body).hexdigest(), info['sha256'])

    def test_command_backfills_and_delete_cleans_up(self):
        key = ScoreAnalysis.objects.get(version=self.version, analyzer=layouts.ANALYZER).data['layout_key']
        ScoreAnalysis.objects.filter(analyzer=layouts.ANALYZER).delete()
        self.assertEqual([v.pk for v in layouts.missing()], [self.version.pk])
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('score_layout', stdout=out)
        self.assertIn('마디 81', out.getvalue())
        self.assertEqual(layouts.missing(), [])
        self.assertTrue((self.files_root / key).exists())
        self.score.refresh_from_db()
        delete_score(self.score)
        self.assertFalse((self.files_root / key).exists())

    def test_new_analyzer_version_reanalyzes(self):
        """분석기 버전이 바뀌면 레인이 다시 분석하고 기기에 다시 온다(TV 는 analyzer_version 으로 판단)"""
        ScoreAnalysis.objects.filter(analyzer=layouts.ANALYZER).update(analyzer_version='0+app.old')
        self.assertEqual([v.pk for v in layouts.missing()], [self.version.pk])
        layouts.analyze_version(self.version)
        self.assertEqual(layouts.missing(), [])
        document = json.loads((self.files_root / layouts.layout_key(self.version)).read_text())
        self.assertEqual((document['analyzer_version'], document['app_commit']), (layouts.ANALYZER_VERSION, layouts.APP_COMMIT))

    def test_detail_shows_layout_summary(self):
        page = self.client.get(reverse('web:score_detail', args=[self.score.pk]))
        self.assertContains(page, '26시스템 · 81마디')
