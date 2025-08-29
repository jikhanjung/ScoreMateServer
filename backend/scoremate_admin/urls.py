from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AdminUserViewSet, AdminTaskViewSet, AdminScoreViewSet, AdminSetlistViewSet

router = DefaultRouter()
router.register(r'users', AdminUserViewSet, basename='admin-users')
router.register(r'tasks', AdminTaskViewSet, basename='admin-tasks')
router.register(r'scores', AdminScoreViewSet, basename='admin-scores')
router.register(r'setlists', AdminSetlistViewSet, basename='admin-setlists')

urlpatterns = [
    path('', include(router.urls)),
]
