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
    ):
        boto3.client('s3', region_name='us-east-1').create_bucket(Bucket='scores')
        yield


@pytest.fixture
def db_setup():
    """Setup test database - pytest-django handles the transaction"""
    pass