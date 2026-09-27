"""
pytest configuration and fixtures for ScoreMateServer tests
"""
import os
import django
from django.conf import settings

# Ensure Django settings are configured
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scoremateserver.settings')
django.setup()

import boto3
import pytest
from django.core.cache import cache
from django.test import override_settings
from moto import mock_aws


@pytest.fixture(autouse=True)
def mock_s3_storage():
    """모든 테스트에서 S3 를 moto 로 대신한다 — MinIO 없이, 네트워크 재시도 없이 돈다.

    버킷 'scores' 는 미리 만들어 둔다. 테스트가 끝나면 내용은 사라진다.
    """
    with mock_aws(), override_settings(
        STORAGE_ENDPOINT=None,
        STORAGE_PUBLIC_ENDPOINT=None,
        STORAGE_BUCKET='scores',
        STORAGE_ACCESS_KEY='testing',
        STORAGE_SECRET_KEY='testing',
        STORAGE_USE_SSL=True,
        # 테스트에서는 느린 PBKDF2 대신 (사용자 · 로그인을 많이 만든다)
        PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
        WEB_ENSEMBLES=True,   # 앙상블 웹 화면 테스트는 켠 상태로. 숨김은 test_web_ensembles_hidden.py
        # 테스트는 collectstatic 을 하지 않는다 — manifest 저장소 대신 일반 저장소(운영 이미지는 빌드 때 모은다)
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    ):
        boto3.client('s3', region_name='us-east-1').create_bucket(Bucket='scores')
        # 요청 제한 카운터 · 업로드 예약이 테스트 사이에 남지 않게
        cache.clear()
        yield


@pytest.fixture
def db_setup():
    """Setup test database - pytest-django handles the transaction"""
    pass