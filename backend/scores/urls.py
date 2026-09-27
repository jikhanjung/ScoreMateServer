"""
URL configuration for scores app
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ScoreViewSet
from .views_sync import ScoreSyncView

app_name = 'scores'

router = DefaultRouter()
router.register(r'scores', ScoreViewSet, basename='score')

urlpatterns = [
    path('sync/scores/', ScoreSyncView.as_view(), name='sync_scores'),
    path('sync/scores', ScoreSyncView.as_view()),
    path('', include(router.urls)),
]