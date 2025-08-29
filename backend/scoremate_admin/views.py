from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.contrib.auth.hashers import make_password
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from core.models import User
from tasks.models import Task
from .serializers import AdminUserSerializer, AdminTaskSerializer
from .serializers import AdminScoreSerializer, AdminSetlistSerializer
from scores.models import Score
from setlists.models import Setlist


class AdminUserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'is_staff', 'plan']
    search_fields = ['email', 'username']
    ordering_fields = ['date_joined', 'last_login', 'used_quota_mb']

    http_method_names = ['get', 'patch', 'head', 'options']

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reset_password(self, request, pk=None):
        user = self.get_object()
        new_password = request.data.get('new_password')
        if not new_password:
            return Response({'detail': 'new_password is required'}, status=status.HTTP_400_BAD_REQUEST)
        user.password = make_password(new_password)
        user.save(update_fields=['password'])
        return Response({'detail': 'Password reset successfully'})


class AdminTaskViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Task.objects.select_related('user', 'score').all()
    serializer_class = AdminTaskSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'kind', 'user']
    search_fields = ['user__email', 'score__title', 'celery_task_id']
    ordering_fields = ['created_at', 'updated_at', 'try_count']

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def retry(self, request, pk=None):
        task = self.get_object()
        # Policy: keep the same row; bump try_count, reset status to PENDING, clear error
        task.try_count = (task.try_count or 0) + 1
        task.status = 'PENDING'
        task.error_message = ''
        task.save(update_fields=['try_count', 'status', 'error_message', 'updated_at'])
        # TODO: enqueue celery task based on kind (out of scope for this patch)
        return Response({'detail': 'Task marked for retry', 'task_id': task.id})


class AdminScoreViewSet(viewsets.ModelViewSet):
    queryset = Score.objects.select_related('user').all()
    serializer_class = AdminScoreSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['user', 'composer', 'pages']
    search_fields = ['title', 'composer', 'user__email']
    ordering_fields = ['created_at', 'updated_at', 'pages', 'size_bytes']
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']


class AdminSetlistViewSet(viewsets.ModelViewSet):
    queryset = Setlist.objects.select_related('user').all()
    serializer_class = AdminSetlistSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['user']
    search_fields = ['title', 'description', 'user__email']
    ordering_fields = ['created_at', 'updated_at']
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']
