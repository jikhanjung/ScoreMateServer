"""
URL configuration for ensembles app
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import EnsembleViewSet

app_name = 'ensembles'

router = DefaultRouter()
router.register(r'ensembles', EnsembleViewSet, basename='ensemble')

urlpatterns = [
    path('', include(router.urls)),
]
