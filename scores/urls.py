"""
URL configuration for scores app
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ScoreViewSet

app_name = 'scores'

router = DefaultRouter()
router.register(r'scores', ScoreViewSet, basename='score')

urlpatterns = [
    path('', include(router.urls)),
]