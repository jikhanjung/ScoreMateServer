"""보표 · 마디 분석 파일을 만든다 — 아직 없는 판 전부(기본) 또는 --version-id 로 하나(다시). scores/layouts.py"""
from django.core.management.base import BaseCommand

from scores import layouts
from scores.models import ScoreVersion


class Command(BaseCommand):
    help = 'Analyze staves/measures of score PDFs (the TV app analysis, ported) and store the layout files.'

    def add_arguments(self, parser):
        parser.add_argument('--version-id', type=int, dest='version_id', help='only this score version id (re-analyze)')

    def handle(self, *args, version_id=None, **options):
        versions = [ScoreVersion.objects.select_related('score').get(pk=version_id)] if version_id else layouts.missing()
        for v in versions:
            try:
                analysis = layouts.analyze_version(v)
            except Exception as exc:  # noqa: BLE001
                self.stdout.write(f'LAYOUT_FAILED version={v.pk} {type(exc).__name__}: {exc}')
                continue
            if analysis is None:
                self.stdout.write(f'LAYOUT_SKIPPED version={v.pk}')
                continue
            d = analysis.data
            self.stdout.write(f"LAYOUT version={v.pk} score={v.score_id} {v.score.title!r}: {d['page_count']}쪽 · "
                              f"시스템 {d['system_count']} · 마디 {d['measure_count']} · 박자표 "
                              f"{[t['time'] for t in d['time_signatures']]} · 이름 {d['labels']}")
