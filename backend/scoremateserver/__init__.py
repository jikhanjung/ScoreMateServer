"""
Django project initialization with Celery integration
"""
from .celery import app as celery_app

__all__ = ('celery_app',)