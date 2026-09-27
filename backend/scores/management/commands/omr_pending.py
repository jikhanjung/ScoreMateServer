"""인식할 판을 한 줄씩 — 운영 호스트 omr_lane.sh 가 읽는다. 앱이 stdout 에 다른 것을 찍어도 섞이지 않게 줄 머리 'OMR_JOB '"""
import json

from django.core.management.base import BaseCommand

from scores import omr


class Command(BaseCommand):
    help = 'List score versions waiting for OMR (one JSON per line, prefixed with "OMR_JOB ").'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=1)

    def handle(self, *args, limit, **options):
        for version in omr.pending(limit):
            self.stdout.write('OMR_JOB ' + json.dumps(omr.job(version), ensure_ascii=False))
