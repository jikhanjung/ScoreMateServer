"""호스트가 읽은 모델 위치를 받는다 — 표준 입력 JSON {"version_id", "sha256", "status", "pages", "run", "problems"}"""
import json
import sys

from django.core.management.base import BaseCommand, CommandError

from scores import model_layouts
from scores.models import ScoreVersion


class Command(BaseCommand):
    help = 'Store a model layout reading (JSON on stdin) as the analysis of a score version.'

    def handle(self, *args, **options):
        try:
            bundle = json.loads(sys.stdin.read())
            version = ScoreVersion.objects.select_related('score').get(pk=bundle['version_id'])
            analysis = model_layouts.ingest(version, sha256=bundle.get('sha256'), status=bundle.get('status'),
                                            pages=bundle.get('pages'), run=bundle.get('run'),
                                            problems=bundle.get('problems'))
        except (ValueError, KeyError, ScoreVersion.DoesNotExist) as exc:
            raise CommandError(f'model layout ingest failed: {exc}') from exc
        if analysis is None:
            self.stdout.write(f'MLAYOUT_RESULT failed version={version.pk}')
        else:
            d = analysis.data
            self.stdout.write(f"MLAYOUT_RESULT ok version={version.pk} systems={d['system_count']} "
                              f"measures={d['measure_count']} agreement={d['agreement']}")
