"""이미 끝난 인식 결과(MusicXML)에 PDF 보표 분석의 줄 · 쪽 바뀜(<print new-system/new-page>)을 넣는다 — 마디 수가 같을 때만"""
from django.core.management.base import BaseCommand

from scores import omr
from scores.models import ScoreAnalysis


class Command(BaseCommand):
    help = 'Add system/page breaks from the layout analysis to finished MusicXML results.'

    def handle(self, *args, **options):
        for analysis in ScoreAnalysis.objects.filter(analyzer=omr.ANALYZER).select_related('version__score'):
            version = analysis.version
            changed = omr.apply_layout_breaks(version)
            analysis.refresh_from_db()
            self.stdout.write(f'OMR_BREAKS version={version.pk} {version.score.title!r}: '
                              f"{'ok ' + str(analysis.data.get('breaks')) if changed else 'skipped (no layout or measure count differs)'}")
