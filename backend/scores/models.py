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
    part_name = models.CharField(max_length=100, blank=True, help_text='e.g. "Full score", "Guitar 1"')
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
    # 지금 쓰는 판. 위의 파일 필드(s3_key · size_bytes · mime · original_filename · pages · content_hash)는
    # 이 판의 사본이다 — 목록 · 받기 · 처리 작업이 판을 몰라도 되게. 바꾸는 곳은 scores/services.py 하나
    current_version = models.ForeignKey(
        'ScoreVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    # 마지막으로 쓴 판 번호 — 판을 지워도 번호를 다시 쓰지 않게(TV 는 판 번호로 받은 파일을 기억한다)
    last_version_number = models.PositiveIntegerField(default=0)

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
    
    def save(self, *args, **kwargs):
        """불변식: 파일이 있는 악보는 판을 적어도 하나 가진다 — 새로 만들면 판 1"""
        creating = self._state.adding
        super().save(*args, **kwargs)
        if creating and self.s3_key and self.current_version_id is None:
            version = ScoreVersion.objects.create(
                score=self, number=1, s3_key=self.s3_key, original_filename=self.original_filename,
                size_bytes=self.size_bytes, mime=self.mime, pages=self.pages, content_hash=self.content_hash,
                uploaded_by_id=self.user_id,
            )
            # update() 는 updated_at 을 건드리지 않는다
            Score.objects.filter(pk=self.pk).update(current_version=version, last_version_number=1)
            self.current_version = version
            self.last_version_number = 1

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


class ScoreVersion(models.Model):
    """악보 한 판 — 수정판이 잦다(`블타바_0829_42페이지까지`). 파일 이름으로 판을 가리던 것을 대신한다 (054 S2)

    쿼터는 그 판을 올린 사람에게 매긴다. 판 번호는 악보 안에서 1 부터 늘기만 한다(지운 번호를 다시 쓰지 않는다).
    """
    score = models.ForeignKey(Score, on_delete=models.CASCADE, related_name='versions')
    number = models.PositiveIntegerField()
    s3_key = models.CharField(max_length=500)
    original_filename = models.CharField(max_length=255, blank=True)
    size_bytes = models.BigIntegerField()
    mime = models.CharField(max_length=100, default='application/pdf')
    pages = models.IntegerField(null=True, blank=True)
    content_hash = models.CharField(max_length=64, blank=True, help_text='SHA-256 of the file')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_versions',
    )
    note = models.TextField(blank=True, help_text='What changed in this version')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'score_versions'
        ordering = ['-number']
        constraints = [
            models.UniqueConstraint(fields=['score', 'number'], name='unique_score_version_number'),
        ]

    def __str__(self):
        return f'{self.score.title} v{self.number}'

    @property
    def is_current(self):
        return self.score.current_version_id == self.pk


def version_key(text):
    """'2.10.1' > '2.9' — 숫자 마디끼리 비교. 숫자가 아니면 문자열 그대로"""
    parts = []
    for piece in str(text or '').replace('-', '.').split('.'):
        parts.append((0, int(piece), '') if piece.isdigit() else (1, 0, piece))
    return tuple(parts)


class ScoreAnalysis(models.Model):
    """TV 가 만든 악보 분석(보표 시스템 · 마디 · 박자표 …)을 판마다 나눈다 — 멤버 TV 가 같은 마디 번호를 쓰게

    서버는 data 를 해석하지 않는다. 분석한 파일의 SHA-256 이 그 판의 것과 같을 때만 받는다.
    """
    MAX_BYTES = 1024 * 1024

    version = models.ForeignKey(ScoreVersion, on_delete=models.CASCADE, related_name='analyses')
    analyzer = models.CharField(max_length=50, help_text='e.g. "mrgq-measures"')
    analyzer_version = models.CharField(max_length=50)
    data = models.JSONField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    related_name='uploaded_analyses')
    device = models.ForeignKey('devices.Device', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'score_analyses'
        constraints = [
            models.UniqueConstraint(fields=['version', 'analyzer'], name='unique_analysis_per_version_analyzer'),
        ]

    def __str__(self):
        return f'{self.version} {self.analyzer} {self.analyzer_version}'
