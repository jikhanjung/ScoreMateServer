"""진행 알림 — 호스트 오케스트레이터가 쪽을 하나 끝낼 때마다(상세 화면의 "악보 인식 12/42쪽")"""
from django.core.management.base import BaseCommand

from scores import pipeline


class Command(BaseCommand):
    help = 'Record pipeline progress for a version (or clear it).'

    def add_arguments(self, parser):
        parser.add_argument('version_id', type=int)
        parser.add_argument('stage', choices=('model', 'omr', 'done'))
        parser.add_argument('done', type=int, nargs='?', default=0)
        parser.add_argument('total', type=int, nargs='?', default=0)

    def handle(self, *args, version_id, stage, done, total, **options):
        if stage == 'done':
            pipeline.clear_progress(version_id)
        else:
            pipeline.set_progress(version_id, stage, done, total)
