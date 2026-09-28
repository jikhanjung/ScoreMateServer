"""이미 끝난 인식에 쪽별 마디를 채운다 — 표준 입력: 호스트의 omr/work/v<id>/log.jsonl
(scripts/astra_musicxml.py 가 새로 쓰는 결과에는 run.page_measures 가 이미 있다)"""
import json
import sys

from django.core.management.base import BaseCommand, CommandError

from scores import omr
from scores.models import ScoreVersion


class Command(BaseCommand):
    help = 'Fill page → measure ranges of a finished OMR result from its chunk log (log.jsonl on stdin).'

    def add_arguments(self, parser):
        parser.add_argument('version_id', type=int)

    def handle(self, *args, version_id, **options):
        entries = [json.loads(line) for line in sys.stdin.read().splitlines() if line.strip()]
        try:
            from scripts.astra_musicxml import page_measures
        except ImportError:       # 이미지 안: /app/scripts
            sys.path.insert(0, '/app/scripts')
            from astra_musicxml import page_measures
        found = page_measures(entries)
        try:
            omr.set_page_measures(ScoreVersion.objects.get(pk=version_id), found)
        except (ScoreVersion.DoesNotExist, omr.OmrError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f'OMR_PAGE_MAP version={version_id} {json.dumps(found)}')
