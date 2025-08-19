"""
URL patterns for setlists app
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SetlistViewSet

router = DefaultRouter()
router.register(r'setlists', SetlistViewSet, basename='setlist')

urlpatterns = [
    path('', include(router.urls)),
]