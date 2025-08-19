from django.contrib import admin
from .models import Setlist, SetlistItem


class SetlistItemInline(admin.TabularInline):
    """Inline admin for SetlistItem"""
    model = SetlistItem
    extra = 1
    fields = ['score', 'order_index', 'notes']
    raw_id_fields = ['score']
    ordering = ['order_index']


@admin.register(Setlist)
class SetlistAdmin(admin.ModelAdmin):
    """Admin for Setlist model"""
    list_display = ['title', 'user', 'item_count', 'total_pages', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['title', 'description', 'user__email']
    date_hierarchy = 'created_at'
    raw_id_fields = ['user']
    inlines = [SetlistItemInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'title', 'description')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        }),
    )
    readonly_fields = ['created_at', 'updated_at']


@admin.register(SetlistItem)
class SetlistItemAdmin(admin.ModelAdmin):
    """Admin for SetlistItem model"""
    list_display = ['setlist', 'score', 'order_index', 'created_at']
    list_filter = ['created_at']
    search_fields = ['setlist__title', 'score__title']
    raw_id_fields = ['setlist', 'score']
    ordering = ['setlist', 'order_index']
