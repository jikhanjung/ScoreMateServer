from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
import hashlib


class Score(models.Model):
    """Sheet music score metadata and storage information"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='scores'
    )
    title = models.CharField(max_length=255)
    composer = models.CharField(max_length=255, blank=True)
    instrumentation = models.CharField(max_length=255, blank=True)
    pages = models.IntegerField(null=True, blank=True)
    s3_key = models.CharField(max_length=500)
    size_bytes = models.BigIntegerField()
    mime = models.CharField(max_length=100, default='application/pdf')
    thumbnail_key = models.CharField(max_length=500, blank=True)
    tags = ArrayField(
        models.CharField(max_length=50),
        blank=True,
        default=list,
        help_text="Tags for categorizing scores"
    )
    note = models.TextField(blank=True)
    content_hash = models.CharField(
        max_length=64, 
        blank=True,
        help_text="SHA256 hash of file content for deduplication"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'scores'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['content_hash']),
            models.Index(fields=['title']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.composer}" if self.composer else self.title
    
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
