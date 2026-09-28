"""모델 위치 읽기를 기다리는 판 — 호스트 model_layout_lane.sh 가 읽는다(줄 머리 'MLAYOUT_JOB ')"""
import json

from django.core.management.base import BaseCommand

from scores import model_layouts


class Command(BaseCommand):
    help = 'List score versions waiting for the model layout reading (one JSON per line, prefixed "MLAYOUT_JOB ").'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=1)

    def handle(self, *args, limit, **options):
        for version in model_layouts.pending(limit):
            self.stdout.write('MLAYOUT_JOB ' + json.dumps(model_layouts.job(version), ensure_ascii=False))
