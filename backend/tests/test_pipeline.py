"""
악보 처리 파이프라인 — ① PDF 분석 → ② 모델 위치 → ③ 악보 인식 (scores/pipeline.py · scripts/score_pipeline.py). devlog 072
"""
import io
import json
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase
from django.urls import reverse

from scores import layouts, model_layouts, omr, pipeline
from scores.models import Score, ScoreAnalysis
from .test_model_layout import FIXTURES, as_model_reading
from .test_web import WebTestBase, pdf_file


class PipelineStateTest(WebTestBase):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        self.client.post(reverse('web:score_upload'), {
            'files': [pdf_file('Moldau0607.pdf', (FIXTURES / 'Moldau0607.pdf').read_bytes())], 'title': 'Moldau'})
        self.score = Score.objects.get(user=self.owner)
        self.version = self.score.current_version

    def job(self):
        found = [j for j in pipeline.jobs() if j['version_id'] == self.version.pk]
        return found[0] if found else None

    def model_ingest(self, reading):
        bundle = {'version_id': self.version.pk, 'sha256': self.version.content_hash, 'status': 'ok', 'pages': reading}
        with patch('sys.stdin', io.StringIO(json.dumps(bundle))):
            call_command('model_layout_ingest', stdout=io.StringIO())

    def test_stages_in_order_and_hints_from_pdf(self):
        self.assertEqual((self.job()['pdf'], self.job()['model'], self.job()['omr']), ('none', 'none', 'none'))
        layouts.analyze_version(self.version)                                   # ①
        job = self.job()
        self.assertEqual((job['pdf'], job['pdf_systems'], job['model']), ('ok', 26, 'none'))
        self.assertIsNone(job['staves'])                                        # ② 전에는 힌트를 주지 않는다
        self.model_ingest(as_model_reading(layouts.layout_document(self.version)))   # ②
        job = self.job()
        self.assertEqual((job['model'], job['omr'], job['staves'], job['hint_source']), ('ok', 'none', 5, 'pdf'))
        self.assertEqual(job['page_systems'], ','.join(['2'] * 13))
        ScoreAnalysis.objects.create(version=self.version, analyzer=omr.ANALYZER, analyzer_version='1',
                                     data={'status': 'failed'})                  # ③ (실패도 끝)
        self.assertIsNone(self.job())

    def test_pages_where_model_and_pdf_differ_get_no_hint(self):
        layouts.analyze_version(self.version)
        reading = as_model_reading(layouts.layout_document(self.version))
        reading[2]['systems'][0]['barlines'].pop(0)
        self.model_ingest(reading)
        self.assertEqual(self.job()['page_systems'].split(',')[2], '0')         # 3쪽은 검사하지 않는다

    def test_scanned_score_takes_hints_from_model(self):
        layouts.analyze_version(self.version)
        reading = as_model_reading(layouts.layout_document(self.version))
        pdf = ScoreAnalysis.objects.get(version=self.version, analyzer=layouts.ANALYZER)
        pdf.data = dict(pdf.data, system_count=0, measure_count=0)             # 스캔본이라 ①이 비었다
        pdf.save()
        self.model_ingest(reading)
        job = self.job()
        self.assertEqual((job['pdf_systems'], job['hint_source'], job['staves']), (0, 'model', 5))

    def test_agreement_refreshes_when_pdf_analysis_comes_later(self):
        reading = as_model_reading(score_layout_document(self.version))
        self.model_ingest(reading)                                              # ②가 ①보다 먼저 끝났다
        data = ScoreAnalysis.objects.get(version=self.version, analyzer=model_layouts.ANALYZER).data
        self.assertIsNone(data['agreement'])
        layouts.analyze_version(self.version)                                   # ① — 검산을 다시
        data = ScoreAnalysis.objects.get(version=self.version, analyzer=model_layouts.ANALYZER).data
        self.assertEqual((data['agreement']['pages_same'], data['agreement']['pages_compared']), (13, 13))

    def test_progress_on_detail(self):
        layouts.analyze_version(self.version)
        call_command('pipeline_progress', str(self.version.pk), 'model', '4', '13')
        page = self.client.get(reverse('web:score_detail', args=[self.score.pk]))
        self.assertContains(page, '① PDF 분석 ✓')
        self.assertContains(page, '② 위치 4/13쪽')
        call_command('pipeline_progress', str(self.version.pk), 'done')
        self.assertIsNone(pipeline.progress(self.version))

    def test_status_command(self):
        out = io.StringIO()
        call_command('pipeline_status', stdout=out)
        jobs = [json.loads(l[len('PIPELINE_JOB '):]) for l in out.getvalue().splitlines() if l.startswith('PIPELINE_JOB ')]
        self.assertEqual([j['version_id'] for j in jobs], [self.version.pk])


def score_layout_document(version):
    """① 없이 모델 입력을 만들려고 — 분석만 하고 저장하지 않는다"""
    from scores import score_layout
    from files.utils import get_storage
    return score_layout.to_document(score_layout.analyze(get_storage().read_bytes(version.s3_key)))


class OrchestratorTest(SimpleTestCase):
    """scripts/score_pipeline.main — 우선순위(① 전부 → ② 한 쪽 → ③ 한 쪽), 쪽 단위 끼어들기, 로그인 멈춤, 재시도"""

    def run_main(self, state, results):
        """state: 판별 {pdf, model, omr, pages}. results: (stage, vid) → [종료 코드 …] 차례로"""
        from scripts import score_pipeline as sp
        calls = []

        def fake_jobs():
            return [{'version_id': vid, 'title': str(vid), 'key': 'k', 'sha256': 's', 'pages': s['pages'],
                     'pdf': s['pdf'], 'model': s['model'], 'omr': s['omr'], 'staves': None, 'page_systems': None}
                    for vid, s in sorted(state.items(), key=lambda item: item[1]['pages'])   # 컨테이너처럼 짧은 악보부터
                    if not (s['pdf'] == 'ok' and s['model'] != 'none' and s['omr'] != 'none')]

        def fake_manage(*args, stdin=None):
            if args[0] == 'score_layout':
                calls.append(('pdf',))
                for s in state.values():
                    s['pdf'] = 'ok'
            return 0, '', ''

        def fake_run_step(stage, job):
            calls.append((stage, job['version_id']))
            code = results[(stage, job['version_id'])].pop(0)
            return code, Path('/nonexistent')

        def fake_ingest(stage, job, workdir, status):
            state[job['version_id']][stage] = status
            return ''
        with patch.object(sp, 'jobs', fake_jobs), patch.object(sp, 'manage', fake_manage), \
                patch.object(sp, 'run_step', fake_run_step), patch.object(sp, 'ingest', fake_ingest), \
                patch.object(sp, 'sha_ok', lambda job: True), patch.object(sp, 'pages_done', lambda s, w: 0), \
                patch.object(sp, 'login_problem', lambda w: results.get('login', False)), \
                patch.object(sp, 'log', lambda m: None):
            with patch.object(Path, 'mkdir', lambda *a, **k: None), \
                    patch.object(Path, 'exists', lambda self: False), \
                    patch.object(Path, 'write_text', lambda self, t: None):
                code = sp.main()
        return code, calls

    def test_priority_and_page_interleaving(self):
        # 긴 악보(1)의 인식 중에 새 악보(2)가 올라온 상황 — 2의 ① · ②가 1의 ③ 쪽 사이에 끼어든다
        state = {1: {'pdf': 'ok', 'model': 'ok', 'omr': 'none', 'pages': 42},
                 2: {'pdf': 'none', 'model': 'none', 'omr': 'none', 'pages': 2}}
        results = {('model', 2): [4, 0], ('omr', 2): [4, 0], ('omr', 1): [4, 0]}
        code, calls = self.run_main(state, results)
        self.assertEqual(code, 0)
        # ① 전부 → 2 의 ② 두 쪽(③보다 먼저) → ③은 짧은 악보(2)부터
        self.assertEqual(calls, [('pdf',), ('model', 2), ('model', 2), ('omr', 2), ('omr', 2), ('omr', 1), ('omr', 1)])

    def test_login_problem_stops_the_pipeline(self):
        state = {1: {'pdf': 'ok', 'model': 'none', 'omr': 'none', 'pages': 3}}
        code, calls = self.run_main(state, {('model', 1): [1], 'login': True})
        self.assertEqual((code, calls), (1, [('model', 1)]))
        self.assertEqual(state[1]['model'], 'none')                             # 실패로 기록하지 않는다

    def test_run_failure_is_retried_later_not_now(self):
        state = {1: {'pdf': 'ok', 'model': 'none', 'omr': 'none', 'pages': 3},
                 2: {'pdf': 'ok', 'model': 'none', 'omr': 'none', 'pages': 5}}
        code, calls = self.run_main(state, {('model', 1): [1], ('model', 2): [0], ('omr', 2): [0]})
        self.assertEqual(calls, [('model', 1), ('model', 2), ('omr', 2)])      # 1 은 이번 실행에서 건너뛴다
        self.assertEqual(state[1]['model'], 'none')
