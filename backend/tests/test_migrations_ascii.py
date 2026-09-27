"""마이그레이션 파일은 ASCII 만 — devdocs guides/web/deployment.md §7

비 ASCII(한글 help_text 등)가 있으면 로캘 기본 인코딩으로 여는 환경(한글 윈도우 cp949)에서
마이그레이션 실행기가 UnicodeDecodeError 로 죽는다. 모델의 help_text · verbose_name 은 영어로 두고,
한글 라벨은 폼(web/forms.py)에서 붙인다.
"""
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


def test_all_migration_files_are_ascii():
    offenders = []
    for path in sorted(BACKEND.glob('*/migrations/*.py')):
        for lineno, line in enumerate(path.read_bytes().splitlines(), 1):
            if any(b > 127 for b in line):
                offenders.append(f'{path.relative_to(BACKEND)}:{lineno}')
    assert not offenders, 'non-ASCII in migrations: ' + ', '.join(offenders)
