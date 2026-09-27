from django.db import models
from django.db.models import Q
from django.conf import settings
from ensembles.models import Membership
from scores.models import Score


class SetlistQuerySet(models.QuerySet):
    """악보와 같은 접근 범위 — 내 세트리스트 + 내가 멤버인 앙상블의 세트리스트(쓰기는 owner · leader)"""

    def readable_by(self, user):
        return self.filter(Q(ensemble__isnull=True, user=user) | Q(ensemble__memberships__user=user))

    def writable_by(self, user):
        return self.filter(
            Q(ensemble__isnull=True, user=user) |
            Q(ensemble__memberships__user=user, ensemble__memberships__role__in=Membership.MANAGER_ROLES)
        )


class Setlist(models.Model):
    """Collection of scores organized for performance"""
    ensemble = models.ForeignKey(
        'ensembles.Ensemble',
        on_delete=models.CASCADE,   # 연주회 곡목은 앙상블의 것 — 앙상블을 지우면 함께
        null=True,
        blank=True,
        related_name='setlists',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='setlists'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = SetlistQuerySet.as_manager()

    class Meta:
        db_table = 'setlists'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
        ]
    
    def __str__(self):
        return self.title

    def can_edit(self, user):
        if self.ensemble_id is None:
            return self.user_id == user.id
        return self.ensemble.can_manage(user)

    def can_include(self, score):
        """앙상블 세트리스트에는 그 앙상블의 악보만, 내 세트리스트에는 내가 올린 악보만"""
        if self.ensemble_id is not None:
            return score.ensemble_id == self.ensemble_id
        return score.user_id == self.user_id
    
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
