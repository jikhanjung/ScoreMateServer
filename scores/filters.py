"""
Custom filters for scores app
"""
import django_filters
from django.db import models
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from rest_framework.filters import OrderingFilter
from .models import Score


class ScoreFilter(django_filters.FilterSet):
    """Advanced filtering for Score model"""
    
    # Text search filters
    title = django_filters.CharFilter(lookup_expr='icontains', help_text="Filter by title (case-insensitive)")
    composer = django_filters.CharFilter(lookup_expr='icontains', help_text="Filter by composer (case-insensitive)")
    instrumentation = django_filters.CharFilter(lookup_expr='icontains', help_text="Filter by instrumentation")
    
    # Tag filtering
    tags = django_filters.CharFilter(method='filter_tags', help_text="Filter by tags (comma-separated)")
    has_tags = django_filters.BooleanFilter(method='filter_has_tags', help_text="Filter scores that have any tags")
    
    # File size filters
    size_mb_min = django_filters.NumberFilter(field_name='size_bytes', lookup_expr='gte', method='filter_size_mb_min')
    size_mb_max = django_filters.NumberFilter(field_name='size_bytes', lookup_expr='lte', method='filter_size_mb_max')
    
    # Page count filters
    pages_min = django_filters.NumberFilter(field_name='pages', lookup_expr='gte')
    pages_max = django_filters.NumberFilter(field_name='pages', lookup_expr='lte')
    has_pages = django_filters.BooleanFilter(method='filter_has_pages', help_text="Filter scores with known page count")
    
    # Date filters
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    updated_after = django_filters.DateTimeFilter(field_name='updated_at', lookup_expr='gte')
    updated_before = django_filters.DateTimeFilter(field_name='updated_at', lookup_expr='lte')
    
    # Thumbnail filters
    has_thumbnail = django_filters.BooleanFilter(method='filter_has_thumbnail', help_text="Filter scores with thumbnails")
    
    # Content filters
    has_content_hash = django_filters.BooleanFilter(method='filter_has_content_hash', help_text="Filter scores with content hash")
    
    # Full-text search
    search = django_filters.CharFilter(method='filter_search', help_text="Full-text search across title, composer, and instrumentation")
    
    class Meta:
        model = Score
        fields = []
    
    def filter_tags(self, queryset, name, value):
        """Filter by tags (supports comma-separated values)"""
        if not value:
            return queryset
        
        tags = [tag.strip() for tag in value.split(',') if tag.strip()]
        if not tags:
            return queryset
        
        # Use PostgreSQL array contains for efficient tag filtering
        for tag in tags:
            queryset = queryset.filter(tags__contains=[tag])
        
        return queryset
    
    def filter_has_tags(self, queryset, name, value):
        """Filter scores that have any tags"""
        if value is True:
            return queryset.exclude(tags__isnull=True).exclude(tags=[])
        elif value is False:
            return queryset.filter(models.Q(tags__isnull=True) | models.Q(tags=[]))
        return queryset
    
    def filter_size_mb_min(self, queryset, name, value):
        """Filter by minimum file size in MB"""
        if value is not None:
            size_bytes = value * 1024 * 1024
            return queryset.filter(size_bytes__gte=size_bytes)
        return queryset
    
    def filter_size_mb_max(self, queryset, name, value):
        """Filter by maximum file size in MB"""
        if value is not None:
            size_bytes = value * 1024 * 1024
            return queryset.filter(size_bytes__lte=size_bytes)
        return queryset
    
    def filter_has_pages(self, queryset, name, value):
        """Filter scores with known page count"""
        if value is True:
            return queryset.exclude(pages__isnull=True).exclude(pages=0)
        elif value is False:
            return queryset.filter(models.Q(pages__isnull=True) | models.Q(pages=0))
        return queryset
    
    def filter_has_thumbnail(self, queryset, name, value):
        """Filter scores with thumbnails"""
        if value is True:
            return queryset.exclude(thumbnail_key__isnull=True).exclude(thumbnail_key='')
        elif value is False:
            return queryset.filter(models.Q(thumbnail_key__isnull=True) | models.Q(thumbnail_key=''))
        return queryset
    
    def filter_has_content_hash(self, queryset, name, value):
        """Filter scores with content hash"""
        if value is True:
            return queryset.exclude(content_hash__isnull=True).exclude(content_hash='')
        elif value is False:
            return queryset.filter(models.Q(content_hash__isnull=True) | models.Q(content_hash=''))
        return queryset
    
    def filter_search(self, queryset, name, value):
        """Full-text search using PostgreSQL search features"""
        if not value:
            return queryset
        
        # Use PostgreSQL full-text search for better performance
        search_vector = SearchVector('title', weight='A') + \
                       SearchVector('composer', weight='B') + \
                       SearchVector('instrumentation', weight='C')
        
        search_query = SearchQuery(value)
        
        return queryset.annotate(
            search=search_vector,
            rank=SearchRank(search_vector, search_query)
        ).filter(search=search_query).order_by('-rank', '-updated_at')


class ScoreOrderingFilter(OrderingFilter):
    """Custom ordering filter with additional options"""
    
    ordering_param = 'ordering'
    
    def get_valid_fields(self, queryset, view, context={}):
        """Get valid fields for ordering"""
        valid_fields = super().get_valid_fields(queryset, view, context)
        
        # Add custom fields
        valid_fields += [
            ('size_bytes', 'size_mb'),
            ('pages', 'pages'),
            ('?', 'random'),
        ]
        
        return valid_fields
    
    def filter_queryset(self, request, queryset, view):
        """Filter queryset with custom ordering logic"""
        ordering = self.get_ordering(request, queryset, view)
        
        if ordering:
            # Handle custom orderings
            processed_ordering = []
            for order_field in ordering:
                if order_field == 'size_mb':
                    processed_ordering.append('size_bytes')
                elif order_field == '-size_mb':
                    processed_ordering.append('-size_bytes')
                elif order_field == 'random':
                    processed_ordering.append('?')
                else:
                    processed_ordering.append(order_field)
            
            return queryset.order_by(*processed_ordering)
        
        return queryset