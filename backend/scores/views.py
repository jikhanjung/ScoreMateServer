"""
Views for scores app
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponseRedirect
from files.utils import get_storage
from devices.auth import PerDeviceScopedRateThrottle
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
from .services import (
    AnalysisError, VersionError, add_version, delete_score, delete_version, make_current, save_analysis,
)
from .serializers import AnalysisSerializer, AnalysisWriteSerializer, ScoreVersionSerializer
from files.serializers import NewVersionSerializer
from files.utils import QuotaManager


class ScoreViewSet(viewsets.ModelViewSet):
    """ViewSet for managing scores"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, ScoreOrderingFilter]
    filterset_class = ScoreFilter
    ordering_fields = ['created_at', 'updated_at', 'title', 'composer', 'size_mb', 'pages']
    ordering = ['-updated_at']
    throttle_scope = None   # download · analysis 동작만 'sync'(기기마다) — 나머지는 기본 제한

    # 앙상블 악보를 바꾸는 동작 — owner · leader 만 (멤버는 읽기만)
    WRITE_ACTIONS = {
        'update', 'partial_update', 'destroy',
        'regenerate_thumbnail', 'refresh_info', 'generate_all_thumbnails',
    }
    
    def get_queryset(self):
        """내 개인 악보 + 내가 멤버인 앙상블의 악보"""
        return (Score.objects.readable_by(self.request.user)
                .select_related('ensemble', 'user', 'current_version')
                .annotate(version_count=Count('versions', distinct=True)))

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
        """악보 삭제 — 쿼터는 올린 사람에게 돌려주고 파일을 지운다 (scores/services.py)"""
        delete_score(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'], throttle_classes=[PerDeviceScopedRateThrottle], throttle_scope='sync')
    def download(self, request, pk=None):
        """파일 받기 — 서명 URL 로 302 (파일은 Django 를 지나지 않는다). ?version=n 이면 그 판"""
        score = self.get_object()
        number = request.query_params.get('version')
        if number:
            if not number.isdigit():
                raise ValidationError({'version': 'Must be a version number.'})
            version = self._version(score, number)
            key, original = version.s3_key, version.original_filename
        else:
            key, original = score.s3_key, score.original_filename
        url = get_storage().generate_presigned_download_url(
            key, expiry=300, filename=original or f'{score.title}.pdf')['url']
        return HttpResponseRedirect(request.build_absolute_uri(url) if url.startswith('/') else url)

    # --- 분석 공유 (S6) ---

    @action(detail=True, methods=['get', 'put'], throttle_classes=[PerDeviceScopedRateThrottle], throttle_scope='sync')
    def analysis(self, request, pk=None):
        """GET 지금 판(?version=n)의 분석들 · PUT {analyzer, analyzer_version, sha256, data} — TV 가 올린다"""
        score = self.get_object()
        if request.method == 'GET':
            number = request.query_params.get('version')
            version = self._version(score, number) if number and number.isdigit() else score.current_version
            analyses = version.analyses.select_related('uploaded_by', 'version') if version else []
            analyzer = request.query_params.get('analyzer')
            if analyzer:
                analyses = [a for a in analyses if a.analyzer == analyzer]
                if not analyses:
                    raise Http404('No analysis')
            return Response({'version': version.number if version else None,
                             'analyses': AnalysisSerializer(analyses, many=True).data})

        serializer = AnalysisWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            analysis, created = save_analysis(
                score, user=request.user, analyzer=data['analyzer'], analyzer_version=data['analyzer_version'],
                sha256=data['sha256'], data=data['data'], device_id=getattr(request.user, 'device_id', None))
        except AnalysisError as exc:
            code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE if exc.code == 'too_large' else status.HTTP_409_CONFLICT
            return Response({'error': exc.code, 'message': str(exc)}, status=code)
        return Response(AnalysisSerializer(analysis).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    # --- 판 (S2) ---

    def _version(self, score, number):
        version = score.versions.filter(number=number).first()
        if version is None:
            raise Http404('No such version')
        return version

    def _require_edit(self, score):
        if not score.can_edit(self.request.user):
            raise PermissionDenied('Only ensemble owners and leaders can change this score.')

    @action(detail=True, methods=['get', 'post'])
    def versions(self, request, pk=None):
        """GET 판 목록(최신부터) · POST 새 판 {upload_id, note} — upload-url → PUT 다음에"""
        score = self.get_object()
        if request.method == 'GET':
            versions = score.versions.select_related('uploaded_by', 'score')
            return Response(ScoreVersionSerializer(versions, many=True).data)

        self._require_edit(score)
        serializer = NewVersionSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        upload_id = serializer.validated_data['upload_id']
        from django.core.cache import cache
        reservation = cache.get(f"quota_reservation:{upload_id}")
        QuotaManager.confirm_quota(request.user, upload_id)   # 쿼터는 이 판을 올린 사람에게
        version = add_version(
            score, user=request.user, s3_key=reservation['s3_key'], size_bytes=reservation['size_bytes'],
            original_filename=reservation.get('original_filename') or '', mime=reservation.get('mime_type'),
            note=serializer.validated_data.get('note', ''), charge_quota=False,
        )
        version.refresh_from_db()
        return Response(ScoreVersionSerializer(version).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path=r'versions/(?P<number>\d+)')
    def delete_version(self, request, pk=None, number=None):
        score = self.get_object()
        self._require_edit(score)
        try:
            delete_version(score, self._version(score, number))
        except VersionError as exc:
            raise ValidationError({'version': str(exc)})
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path=r'versions/(?P<number>\d+)/make_current')
    def make_current(self, request, pk=None, number=None):
        """예전 판으로 되돌린다 (판은 남는다)"""
        score = self.get_object()
        self._require_edit(score)
        make_current(score, self._version(score, number))
        score.refresh_from_db()
        return Response(ScoreSerializer(score, context={'request': request}).data)

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
