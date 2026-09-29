"""할 일이 남은 판(PIPELINE_JOB JSON 한 줄씩) — 호스트 scripts/score_pipeline.py 가 읽는다"""
import json

from django.core.management.base import BaseCommand

from scores import pipeline


class Command(BaseCommand):
    help = 'List current score versions with pipeline work left (one JSON per line, prefixed "PIPELINE_JOB ").'

    def handle(self, *args, **options):
        for job in pipeline.jobs():
            self.stdout.write('PIPELINE_JOB ' + json.dumps(job, ensure_ascii=False))
