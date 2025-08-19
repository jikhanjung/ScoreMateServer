from django.db import models
from django.conf import settings
from scores.models import Score


class Task(models.Model):
    """Background task tracking for async operations"""
    
    KIND_CHOICES = [
        ('pdf_info', 'PDF Info Extraction'),
        ('thumbnail', 'Thumbnail Generation'),
        ('layout_hook', 'Layout Analysis Hook'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('SUCCEEDED', 'Succeeded'),
        ('FAILED', 'Failed'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tasks'
    )
    score = models.ForeignKey(
        Score,
        on_delete=models.CASCADE,
        related_name='tasks',
        null=True,
        blank=True
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    try_count = models.IntegerField(default=0)
    celery_task_id = models.CharField(max_length=255, blank=True, help_text="Celery task UUID")
    log = models.TextField(blank=True, help_text="Task execution log")
    result_json = models.JSONField(default=dict, blank=True, help_text="Task result data")
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tasks'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['score', 'kind']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['celery_task_id']),
        ]
        unique_together = ['score', 'kind']
    
    def __str__(self):
        return f"{self.get_kind_display()} - {self.status} ({self.score.title if self.score else 'No score'})"
    
    @property
    def is_running(self):
        return self.status == 'RUNNING'
    
    @property
    def is_completed(self):
        return self.status in ['SUCCEEDED', 'FAILED']
    
    @property
    def is_failed(self):
        return self.status == 'FAILED'
    
    @property
    def duration(self):
        """Calculate task duration if completed"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def mark_running(self):
        """Mark task as running"""
        from django.utils import timezone
        self.status = 'RUNNING'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at', 'updated_at'])
    
    def mark_succeeded(self, result=None, log=""):
        """Mark task as succeeded"""
        from django.utils import timezone
        self.status = 'SUCCEEDED'
        self.completed_at = timezone.now()
        if result:
            self.result_json = result
        if log:
            self.log = log
        self.save(update_fields=['status', 'completed_at', 'result_json', 'log', 'updated_at'])
    
    def mark_failed(self, error_message="", log=""):
        """Mark task as failed"""
        from django.utils import timezone
        self.status = 'FAILED'
        self.completed_at = timezone.now()
        self.error_message = error_message
        if log:
            self.log = log
        self.save(update_fields=['status', 'completed_at', 'error_message', 'log', 'updated_at'])
