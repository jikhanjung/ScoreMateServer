from rest_framework import serializers
from core.models import User
from tasks.models import Task
from scores.models import Score
from setlists.models import Setlist


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id', 'email', 'username', 'is_active', 'is_staff',
            'plan', 'total_quota_mb', 'used_quota_mb', 'date_joined', 'last_login'
        )
        read_only_fields = ('id', 'email', 'username', 'date_joined', 'last_login')


class AdminTaskSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    score_title = serializers.CharField(source='score.title', read_only=True)

    class Meta:
        model = Task
        fields = (
            'id', 'user', 'user_email', 'score', 'score_title', 'kind', 'status',
            'try_count', 'celery_task_id', 'error_message', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at', 'celery_task_id')


class AdminScoreSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    has_thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Score
        fields = (
            'id', 'user', 'user_email', 'title', 'composer', 'instrumentation', 'pages',
            'size_bytes', 'mime', 'tags', 'note', 'thumbnail_key', 'has_thumbnail',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'size_bytes', 'mime', 'thumbnail_key', 'created_at', 'updated_at')

    def get_has_thumbnail(self, obj):
        return bool(obj.thumbnail_key)


class AdminSetlistSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    item_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Setlist
        fields = (
            'id', 'user', 'user_email', 'title', 'description', 'item_count', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'item_count', 'created_at', 'updated_at')
