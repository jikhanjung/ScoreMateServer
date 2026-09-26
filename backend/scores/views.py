"""
Views for scores app
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import F, Count, Sum, Avg, Q
from django.db import transaction

from .models import Score
from .serializers import (
    ScoreSerializer, 
    ScoreListSerializer, 
    ScoreCreateSerializer
)
from .filters import ScoreFilter, ScoreOrderingFilter


class ScoreViewSet(viewsets.ModelViewSet):
    """ViewSet for managing scores"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, ScoreOrderingFilter]
    filterset_class = ScoreFilter
    ordering_fields = ['created_at', 'updated_at', 'title', 'composer', 'size_mb', 'pages']
    ordering = ['-updated_at']

    # 앙상블 악보를 바꾸는 동작 — owner · leader 만 (멤버는 읽기만)
    WRITE_ACTIONS = {
        'update', 'partial_update', 'destroy',
        'regenerate_thumbnail', 'refresh_info', 'generate_all_thumbnails',
    }
    
    def get_queryset(self):
        """내 개인 악보 + 내가 멤버인 앙상블의 악보"""
        return Score.objects.readable_by(self.request.user).select_related('ensemble', 'user')

    def get_writable_queryset(self):
        """일괄 작업용 — 쓸 수 있는 악보만"""
        return Score.objects.writable_by(self.request.user)

    def get_object(self):
        score = super().get_object()
        # 읽을 수는 있지만 쓸 수 없는 악보는 404 가 아니라 403
        if self.action in self.WRITE_ACTIONS and not score.can_edit(self.request.user):
            raise PermissionDenied('Only ensemble owners and leaders can change this score.')
        return score
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return ScoreListSerializer
        elif self.action == 'create':
            return ScoreCreateSerializer
        return ScoreSerializer
    
    def destroy(self, request, *args, **kwargs):
        """Delete score and update user quota"""
        score = self.get_object()
        size_mb = score.size_bytes // (1024 * 1024)
        
        # Store file information before deletion
        s3_key = score.s3_key
        thumbnail_key = score.thumbnail_key
        score_id = score.id
        
        # 쿼터는 올린 사람 것을 돌려준다 (앙상블 악보를 리더가 지워도)
        uploader = score.user
        uploader.used_quota_mb = F('used_quota_mb') - size_mb
        uploader.save(update_fields=['used_quota_mb'])
        
        # Delete the score record first
        response = super().destroy(request, *args, **kwargs)
        
        # Trigger background task to delete S3 files
        from tasks.file_tasks import delete_score_files
        delete_score_files.delay(s3_key, thumbnail_key, score_id)
        
        return response
    
    @action(detail=True, methods=['post'])
    def regenerate_thumbnail(self, request, pk=None):
        """Regenerate thumbnail for a score"""
        score = self.get_object()
        
        # Trigger thumbnail regeneration task
        from tasks.pdf_tasks import generate_thumbnail
        task = generate_thumbnail.delay(score.id, page_number=1)
        
        return Response({
            'message': 'Thumbnail regeneration started',
            'score_id': score.id,
            'task_id': task.id
        }, status=status.HTTP_202_ACCEPTED)
    
    @action(detail=True, methods=['post'])
    def refresh_info(self, request, pk=None):
        """Refresh PDF info (pages, metadata) for a score"""
        score = self.get_object()
        
        # Trigger PDF info extraction task
        from tasks.pdf_tasks import process_pdf_info
        task = process_pdf_info.delay(score.id)
        
        return Response({
            'message': 'PDF info refresh started',
            'score_id': score.id,
            'task_id': task.id
        }, status=status.HTTP_202_ACCEPTED)
    
    @action(detail=True, methods=['post'])
    def generate_all_thumbnails(self, request, pk=None):
        """Generate thumbnails for all pages of a score"""
        score = self.get_object()
        
        # Trigger all page thumbnails generation
        from tasks.pdf_tasks import generate_all_page_thumbnails
        task = generate_all_page_thumbnails.delay(score.id)
        
        return Response({
            'message': 'All page thumbnails generation started',
            'score_id': score.id,
            'task_id': task.id
        }, status=status.HTTP_202_ACCEPTED)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get statistics about user's scores"""
        queryset = self.get_queryset()
        
        # Basic counts
        total_scores = queryset.count()
        scores_with_pages = queryset.exclude(Q(pages__isnull=True) | Q(pages=0)).count()
        scores_with_thumbnails = queryset.exclude(Q(thumbnail_key__isnull=True) | Q(thumbnail_key='')).count()
        
        # Size statistics
        size_stats = queryset.aggregate(
            total_size_bytes=Sum('size_bytes'),
            avg_size_bytes=Avg('size_bytes'),
            total_size_mb=Sum('size_bytes') / (1024 * 1024) if queryset.exists() else 0
        )
        
        # Page statistics
        page_stats = queryset.exclude(Q(pages__isnull=True) | Q(pages=0)).aggregate(
            total_pages=Sum('pages'),
            avg_pages=Avg('pages')
        )
        
        # Composer statistics (top 10)
        composer_stats = queryset.exclude(Q(composer__isnull=True) | Q(composer='')).values('composer').annotate(
            count=Count('composer')
        ).order_by('-count')[:10]
        
        # Tag statistics (all unique tags)
        # 악보마다의 태그 목록 (SQLite 로 옮기며 ArrayAgg 대신 파이썬에서 모은다 — 054)
        all_tags = {'unique_tags': list(queryset.exclude(Q(tags__isnull=True) | Q(tags=[])).values_list('tags', flat=True))}
        
        # Flatten and count tags
        tag_counts = {}
        if all_tags['unique_tags']:
            flat_tags = []
            for tag_list in all_tags['unique_tags']:
                if tag_list:
                    flat_tags.extend(tag_list)
            
            for tag in flat_tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        # Sort tags by count
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return Response({
            'total_scores': total_scores,
            'scores_with_pages': scores_with_pages,
            'scores_with_thumbnails': scores_with_thumbnails,
            'size_statistics': {
                'total_size_mb': round(size_stats['total_size_mb'] or 0, 2),
                'average_size_mb': round((size_stats['avg_size_bytes'] or 0) / (1024 * 1024), 2),
            },
            'page_statistics': {
                'total_pages': page_stats['total_pages'] or 0,
                'average_pages': round(page_stats['avg_pages'] or 0, 1),
            },
            'top_composers': [
                {'composer': item['composer'], 'count': item['count']} 
                for item in composer_stats
            ],
            'top_tags': [
                {'tag': tag, 'count': count} 
                for tag, count in top_tags
            ]
        })
    
    @action(detail=False, methods=['post'])
    def bulk_tag(self, request):
        """Add or remove tags from multiple scores"""
        score_ids = request.data.get('score_ids', [])
        tags_to_add = request.data.get('add_tags', [])
        tags_to_remove = request.data.get('remove_tags', [])
        
        if not score_ids:
            return Response({'error': 'score_ids is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 쓸 수 있는 악보만
        scores = self.get_writable_queryset().filter(id__in=score_ids)
        
        if not scores.exists():
            return Response({'error': 'No valid scores found'}, status=status.HTTP_404_NOT_FOUND)
        
        updated_count = 0
        with transaction.atomic():
            for score in scores:
                current_tags = set(score.tags or [])
                modified = False
                
                # Add tags
                if tags_to_add:
                    for tag in tags_to_add:
                        if tag not in current_tags:
                            current_tags.add(tag)
                            modified = True
                
                # Remove tags
                if tags_to_remove:
                    for tag in tags_to_remove:
                        if tag in current_tags:
                            current_tags.discard(tag)
                            modified = True
                
                if modified:
                    score.tags = list(current_tags)
                    score.save(update_fields=['tags'])
                    updated_count += 1
        
        return Response({
            'message': f'Updated tags for {updated_count} scores',
            'updated_scores': updated_count,
            'total_scores': len(score_ids)
        })
    
    @action(detail=False, methods=['post'])
    def bulk_regenerate_thumbnails(self, request):
        """Regenerate thumbnails for multiple scores"""
        score_ids = request.data.get('score_ids', [])
        
        if not score_ids:
            # If no specific IDs, regenerate for all writable scores
            scores = self.get_writable_queryset()
        else:
            scores = self.get_writable_queryset().filter(id__in=score_ids)
        
        if not scores.exists():
            return Response({'error': 'No scores found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Trigger thumbnail regeneration for each score
        task_ids = []
        from tasks.pdf_tasks import generate_thumbnail
        
        for score in scores:
            if score.s3_key:  # Only process scores with S3 files
                task = generate_thumbnail.delay(score.id, page_number=1)
                task_ids.append(task.id)
        
        return Response({
            'message': f'Thumbnail regeneration started for {len(task_ids)} scores',
            'task_ids': task_ids,
            'total_scores': scores.count()
        }, status=status.HTTP_202_ACCEPTED)
