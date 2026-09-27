"""호스트가 만든 인식 결과를 받는다 — 표준 입력 JSON:
{"version_id": 12, "sha256": "…", "status": "ok"|"failed", "musicxml": "…", "run": {…}, "problems": […]}"""
import json
import sys

from django.core.management.base import BaseCommand, CommandError

from scores import omr
from scores.models import ScoreVersion


class Command(BaseCommand):
    help = 'Store an OMR result (JSON on stdin) as the analysis of a score version.'

    def handle(self, *args, **options):
        try:
            bundle = json.loads(sys.stdin.read())
            version = ScoreVersion.objects.select_related('score').get(pk=bundle['version_id'])
            analysis = omr.ingest(version, sha256=bundle.get('sha256'), status=bundle.get('status'),
                                  musicxml=bundle.get('musicxml') or '', run=bundle.get('run'),
                                  problems=bundle.get('problems'))
        except (ValueError, KeyError, ScoreVersion.DoesNotExist) as exc:
            raise CommandError(f'OMR ingest failed: {exc}') from exc
        if analysis is None:
            self.stdout.write(f"OMR_RESULT failed version={version.pk}")
        else:
            self.stdout.write(f"OMR_RESULT ok version={version.pk} measures={analysis.data['measure_count']} "
                              f"parts={len(analysis.data['parts'])} key={analysis.data['musicxml_key']}")
