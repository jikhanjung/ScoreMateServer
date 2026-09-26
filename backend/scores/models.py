from django.db import models
from django.db.models import Q
from django.conf import settings
import hashlib

from ensembles.models import Membership


class ScoreQuerySet(models.QuerySet):
    """악보 접근 범위 — 모든 악보 조회는 이 두 메서드 중 하나를 거친다 (devlog 054 §2)"""

    def readable_by(self, user):
        """내 개인 악보 + 내가 멤버인 앙상블의 악보"""
        # 한 filter() 안의 조건이라 ensemble__memberships 가 같은 멤버십 행을 가리킨다.
        # (ensemble, user) 가 유일해서 행이 중복되지 않는다
        return self.filter(
            Q(ensemble__isnull=True, user=user) |
            Q(ensemble__memberships__user=user)
        )

    def writable_by(self, user):
        """내 개인 악보 + 내가 owner · leader 인 앙상블의 악보"""
        return self.filter(
            Q(ensemble__isnull=True, user=user) |
            Q(ensemble__memberships__user=user,
              ensemble__memberships__role__in=Membership.MANAGER_ROLES)
        )


class Score(models.Model):
    """Sheet music score metadata and storage information"""
    # 올린 사람 — 쿼터는 이 사람에게 매긴다 (앙상블 악보도)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='scores'
    )
    # null 이면 개인 악보. 앙상블이 지워지면 올린 사람의 개인 악보로 돌아간다
    ensemble = models.ForeignKey(
        'ensembles.Ensemble',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scores'
    )
    part_name = models.CharField(max_length=100, blank=True, help_text='예: "총보", "Guitar 1"')
    title = models.CharField(max_length=255)
    original_filename = models.CharField(
        max_length=255, 
        blank=True,
        help_text="Original filename when uploaded"
    )
    composer = models.CharField(max_length=255, blank=True)
    instrumentation = models.CharField(max_length=255, blank=True)
    pages = models.IntegerField(null=True, blank=True)
    s3_key = models.CharField(max_length=500)
    size_bytes = models.BigIntegerField()
    mime = models.CharField(max_length=100, default='application/pdf')
    thumbnail_key = models.CharField(max_length=500, blank=True)
    # 문자열 목록. SQLite 로 옮기며 Postgres 전용 ArrayField 대신 JSONField (054)
    tags = models.JSONField(
        blank=True,
        default=list,
        help_text="Tags for categorizing scores (list of strings)"
    )
    note = models.TextField(blank=True)
    content_hash = models.CharField(
        max_length=64, 
        blank=True,
        help_text="SHA256 hash of file content for deduplication"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ScoreQuerySet.as_manager()
    
    class Meta:
        db_table = 'scores'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['content_hash']),
            models.Index(fields=['title']),
            models.Index(fields=['ensemble', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.composer}" if self.composer else self.title
    
    def can_read(self, user):
        if self.ensemble_id is None:
            return self.user_id == user.id
        return self.ensemble.is_member(user)

    def can_edit(self, user):
        if self.ensemble_id is None:
            return self.user_id == user.id
        return self.ensemble.can_manage(user)

    @property
    def size_mb(self):
        """Return size in megabytes"""
        return self.size_bytes / (1024 * 1024)
    
    def generate_s3_key(self):
        """Generate S3 key for storing the PDF"""
        return f"{self.user_id}/scores/{self.id}/original.pdf"
    
    def generate_thumbnail_s3_key(self):
        """Generate S3 key for storing the thumbnail"""
        return f"{self.user_id}/scores/{self.id}/thumbs/cover.jpg"
    
    def generate_page_thumbnail_s3_key(self, page_number):
        """Generate S3 key for storing a specific page thumbnail"""
        return f"{self.user_id}/scores/{self.id}/thumbs/page-{page_number:04d}.jpg"
    
    def calculate_content_hash(self, file_content):
        """Calculate SHA256 hash of file content"""
        return hashlib.sha256(file_content).hexdigest()
