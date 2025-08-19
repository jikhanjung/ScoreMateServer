from django.db import models
from django.conf import settings
from scores.models import Score


class Setlist(models.Model):
    """Collection of scores organized for performance"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='setlists'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'setlists'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
        ]
    
    def __str__(self):
        return self.title
    
    @property
    def item_count(self):
        """Number of scores in this setlist"""
        return self.items.count()
    
    @property
    def total_pages(self):
        """Total pages across all scores in setlist"""
        return sum(item.score.pages or 0 for item in self.items.all())


class SetlistItem(models.Model):
    """Individual score in a setlist with ordering"""
    setlist = models.ForeignKey(
        Setlist,
        on_delete=models.CASCADE,
        related_name='items'
    )
    score = models.ForeignKey(
        Score,
        on_delete=models.CASCADE,
        related_name='setlist_items'
    )
    order_index = models.IntegerField(null=True, blank=True)
    notes = models.TextField(blank=True, help_text="Performance notes for this item")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'setlist_items'
        ordering = ['order_index', 'created_at']
        unique_together = ['setlist', 'score']
        indexes = [
            models.Index(fields=['setlist', 'order_index']),
        ]
    
    def __str__(self):
        return f"{self.setlist.title} - {self.order_index}: {self.score.title}"
    
    def save(self, *args, **kwargs):
        """Auto-assign order_index if not provided"""
        if self.order_index is None:
            max_index = SetlistItem.objects.filter(
                setlist=self.setlist
            ).aggregate(models.Max('order_index'))['order_index__max']
            self.order_index = (max_index or 0) + 1
        super().save(*args, **kwargs)
