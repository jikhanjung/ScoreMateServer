from django.contrib import admin
from .models import Score


@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    """Admin for Score model"""
    list_display = ['title', 'composer', 'user', 'pages', 'size_mb_display', 'created_at']
    list_filter = ['mime', 'created_at', 'updated_at']
    search_fields = ['title', 'composer', 'instrumentation', 'user__email']
    date_hierarchy = 'created_at'
    raw_id_fields = ['user']
    readonly_fields = ['size_mb_display', 'content_hash', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'title', 'composer', 'instrumentation', 'note')
        }),
        ('File Information', {
            'fields': ('s3_key', 'thumbnail_key', 'size_bytes', 'size_mb_display', 'mime', 'pages', 'content_hash')
        }),
        ('Categories', {
            'fields': ('tags',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def size_mb_display(self, obj):
        """Display size in MB"""
        return f"{obj.size_mb:.2f} MB"
    size_mb_display.short_description = 'Size'
