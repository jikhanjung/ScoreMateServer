"""
pytest configuration and fixtures for ScoreMateServer tests
"""
import os
import django
from django.conf import settings

# Ensure Django settings are configured
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scoremateserver.settings')
django.setup()

import pytest


@pytest.fixture
def db_setup():
    """Setup test database - pytest-django handles the transaction"""
    pass