from django.contrib import admin
from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """Admin for Task model"""
    list_display = ['id', 'user', 'score_title', 'kind', 'status', 'try_count', 'duration_display', 'created_at']
    list_filter = ['kind', 'status', 'created_at', 'completed_at']
    search_fields = ['user__email', 'score__title', 'celery_task_id']
    date_hierarchy = 'created_at'
    raw_id_fields = ['user', 'score']
    readonly_fields = ['celery_task_id', 'started_at', 'completed_at', 'created_at', 'updated_at', 'duration_display']
    
    fieldsets = (
        ('Task Information', {
            'fields': ('user', 'score', 'kind', 'status', 'try_count', 'celery_task_id')
        }),
        ('Execution Details', {
            'fields': ('log', 'error_message', 'result_json')
        }),
        ('Timestamps', {
            'fields': ('started_at', 'completed_at', 'duration_display', 'created_at', 'updated_at')
        }),
    )
    
    def score_title(self, obj):
        """Display score title"""
        return obj.score.title if obj.score else '-'
    score_title.short_description = 'Score'
    
    def duration_display(self, obj):
        """Display task duration"""
        duration = obj.duration
        if duration:
            return f"{duration:.2f}s"
        return '-'
    duration_display.short_description = 'Duration'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('user', 'score')
