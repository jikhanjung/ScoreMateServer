"""
Serializers for scores app
"""
from django.conf import settings
from rest_framework import serializers

from ensembles.models import Ensemble, Membership
from files.utils import get_storage
from .models import Score, ScoreAnalysis, ScoreVersion


def thumbnail_url(score):
    if not score.thumbnail_key:
        return None
    try:
        return get_storage().generate_presigned_download_url(
            score.thumbnail_key, expiry=settings.THUMBNAIL_URL_EXPIRY,
            variant=score.current_version_id)['url']   # 새 판이면 URL 이 바뀐다
    except Exception:
        return None


def validate_target_ensemble(request, ensemble):
    """악보를 이 앙상블에 둘 수 있는가 — owner · leader 만. None(개인 악보)은 늘 된다"""
    if ensemble is not None and not ensemble.can_manage(request.user):
        # 멤버가 아닌 앙상블은 있는지도 알려 주지 않는다
        if not ensemble.is_member(request.user):
            raise serializers.ValidationError('Ensemble not found.')
        raise serializers.ValidationError('Only ensemble owners and leaders can add scores.')
    return ensemble


class EnsembleFieldsMixin(serializers.Serializer):
    """앙상블 소속 · 파트 · 올린 사람 · 요청한 사람이 고칠 수 있는지"""
    ensemble = serializers.PrimaryKeyRelatedField(
        queryset=Ensemble.objects.all(), required=False, allow_null=True
    )
    ensemble_name = serializers.SerializerMethodField()
    uploader = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    version = serializers.SerializerMethodField()
    version_count = serializers.SerializerMethodField()

    def get_ensemble_name(self, obj):
        return obj.ensemble.name if obj.ensemble_id else None

    def get_uploader(self, obj):
        return {'id': obj.user_id, 'username': obj.user.username}

    def get_version(self, obj):
        """지금 쓰는 판 번호"""
        return obj.current_version.number if obj.current_version_id else None

    def get_version_count(self, obj):
        annotated = getattr(obj, 'version_count', None)
        return annotated if annotated is not None else obj.versions.count()

    def get_can_edit(self, obj):
        request = self.context.get('request')
        if not request:
            return False
        if obj.ensemble_id is None:
            return obj.user_id == request.user.id
        # 목록에서 악보마다 멤버십을 묻지 않도록 요청당 한 번 모아 둔다 (context 는 목록의 항목들이 함께 쓴다)
        managed = self.context.get('_managed_ensemble_ids')
        if managed is None:
            managed = set(
                Membership.objects.filter(user=request.user, role__in=Membership.MANAGER_ROLES)
                .values_list('ensemble_id', flat=True)
            )
            self.context['_managed_ensemble_ids'] = managed
        return obj.ensemble_id in managed


ENSEMBLE_FIELDS = ['ensemble', 'ensemble_name', 'part_name', 'uploader', 'can_edit', 'version', 'version_count']


class ScoreVersionSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.SerializerMethodField()
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = ScoreVersion
        fields = ['number', 'is_current', 'original_filename', 'size_bytes', 'pages', 'content_hash',
                  'note', 'uploaded_by', 'created_at']
        read_only_fields = fields

    def get_uploaded_by(self, obj):
        return {'id': obj.uploaded_by_id, 'username': obj.uploaded_by.username} if obj.uploaded_by_id else None

    def get_is_current(self, obj):
        return obj.score.current_version_id == obj.pk


class ScoreSerializer(EnsembleFieldsMixin, serializers.ModelSerializer):
    """Serializer for Score model (상세 · 수정)

    올린 사람(user)과 파일 필드는 바꿀 수 없다 — 리더가 다른 멤버의 악보를 고쳐도 올린 사람 · 쿼터는 그대로
    """
    size_mb = serializers.ReadOnlyField()
    file_size = serializers.SerializerMethodField()  # For frontend compatibility
    page_count = serializers.SerializerMethodField()  # Alias for pages
    has_thumbnail = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Score
        fields = [
            'id', 'title', 'composer', 'arranger', 'instrumentation', 
            's3_key', 'size_bytes', 'size_mb', 'file_size', 'mime', 
            'pages', 'page_count', 'tags', 'note', 'thumbnail_key', 
            'has_thumbnail', 'thumbnail_url', 'content_hash',
            'created_at', 'updated_at'
        ] + ENSEMBLE_FIELDS
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'size_mb', 'file_size', 'page_count', 'has_thumbnail', 'thumbnail_url',
            's3_key', 'size_bytes', 'mime', 'thumbnail_key', 'content_hash',
        ]

    def validate_ensemble(self, value):
        request = self.context['request']
        instance = self.instance
        if instance is not None and value != instance.ensemble:
            # 개인 ↔ 앙상블, 앙상블 ↔ 앙상블 옮기기는 올린 사람만 (쿼터가 그 사람 것이다)
            if instance.user_id != request.user.id:
                raise serializers.ValidationError('Only the uploader can move this score.')
        return validate_target_ensemble(request, value)
    
    def get_file_size(self, obj):
        """Return size in bytes for frontend compatibility"""
        return obj.size_bytes
    
    def get_page_count(self, obj):
        """Return pages count"""
        return obj.pages
    
    def get_has_thumbnail(self, obj):
        """Check if score has thumbnail"""
        return bool(obj.thumbnail_key)
    
    def get_thumbnail_url(self, obj):
        """썸네일의 서명 URL — 이 응답을 받은 사람만 한동안 쓸 수 있다 (예전의 인증 없는 썸네일 경로를 대신한다)"""
        return thumbnail_url(obj)
    


class ScoreListSerializer(EnsembleFieldsMixin, serializers.ModelSerializer):
    """Lightweight serializer for score lists"""
    size_mb = serializers.ReadOnlyField()
    file_size = serializers.SerializerMethodField()  # For frontend compatibility
    page_count = serializers.SerializerMethodField()  # Alias for pages
    has_thumbnail = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Score
        fields = [
            'id', 'title', 'composer', 'arranger', 'instrumentation', 
            'size_bytes', 'size_mb', 'file_size', 'pages', 'page_count', 'tags', 
            'thumbnail_key', 'has_thumbnail', 'thumbnail_url',
            'created_at', 'updated_at'
        ] + ENSEMBLE_FIELDS
    
    def get_file_size(self, obj):
        """Return size in bytes for frontend compatibility"""
        return obj.size_bytes
    
    def get_page_count(self, obj):
        """Return pages count"""
        return obj.pages
    
    def get_has_thumbnail(self, obj):
        """Check if score has thumbnail"""
        return bool(obj.thumbnail_key)
    
    def get_thumbnail_url(self, obj):
        """썸네일의 서명 URL — 이 응답을 받은 사람만 한동안 쓸 수 있다 (예전의 인증 없는 썸네일 경로를 대신한다)"""
        return thumbnail_url(obj)


class ScoreCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating scores (after file upload)"""
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    ensemble = serializers.PrimaryKeyRelatedField(
        queryset=Ensemble.objects.all(), required=False, allow_null=True
    )
    
    class Meta:
        model = Score
        fields = [
            'id', 'user', 'title', 'composer', 'arranger', 'instrumentation', 
            's3_key', 'size_bytes', 'mime', 'tags', 'note', 'content_hash',
            'ensemble', 'part_name'
        ]
        read_only_fields = ['id']

    def validate_ensemble(self, value):
        return validate_target_ensemble(self.context['request'], value)
    
    def validate_s3_key(self, value):
        """Validate that s3_key follows the expected pattern and file exists"""
        user = self.context['request'].user
        expected_prefix_scores = f"{user.id}/scores/"
        expected_prefix_uploads = f"{user.id}/uploads/"
        
        if not (value.startswith(expected_prefix_scores) or value.startswith(expected_prefix_uploads)):
            raise serializers.ValidationError(
                f"S3 key must start with '{expected_prefix_scores}' or '{expected_prefix_uploads}'"
            )
        
        # TODO: Add S3 file existence check here
        # This would involve checking if the file actually exists in S3
        
        return value
    
    def validate_size_bytes(self, value):
        """Validate file size against user quota"""
        user = self.context['request'].user
        size_mb = value / (1024 * 1024)
        
        if not user.can_upload(value):
            available_mb = user.available_quota_mb
            raise serializers.ValidationError(
                f"File size ({size_mb:.1f}MB) exceeds available quota ({available_mb}MB)"
            )
        
        return value
    
    def create(self, validated_data):
        """Create score and update user quota"""
        user = validated_data['user']
        size_bytes = validated_data['size_bytes']
        
        # Create the score
        score = super().create(validated_data)
        
        # Update user quota
        size_mb = size_bytes // (1024 * 1024)
        user.used_quota_mb += size_mb
        user.save(update_fields=['used_quota_mb'])
        
        # Trigger background tasks for PDF processing (asynchronously)
        try:
            from tasks.pdf_tasks import process_pdf_info, generate_thumbnail
            
            # Start PDF info extraction asynchronously
            process_pdf_info.delay(score.id)
            
            # Generate cover thumbnail asynchronously  
            generate_thumbnail.delay(score.id, page_number=1)
        except Exception as e:
            # Log the error but don't fail the score creation
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to queue background tasks for score {score.id}: {e}")
        
        return score

class SyncScoreSerializer(serializers.ModelSerializer):
    """TV 동기화용 악보 — 받을 파일을 판 번호와 SHA-256 으로 가리킨다

    version.sha256 이 비어 있으면 아직 처리 중이다(쪽수 · 해시가 채워지면 updated_at 이 바뀌어 다음 동기화에 다시 온다).
    musicxml: 이 판의 악보 인식 결과(scores/omr.py)가 있으면 받을 곳과 sha256 — 없으면 null. 인식이 끝나면 updated_at 이 바뀌어 다시 온다
    """
    ensemble = serializers.SerializerMethodField()
    version = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    musicxml = serializers.SerializerMethodField()
    layout = serializers.SerializerMethodField()

    class Meta:
        model = Score
        fields = ['id', 'title', 'composer', 'arranger', 'instrumentation', 'part_name', 'tags', 'note',
                  'ensemble', 'version', 'download_url', 'musicxml', 'layout', 'updated_at']
        read_only_fields = fields

    def get_ensemble(self, obj):
        return {'id': obj.ensemble_id, 'name': obj.ensemble.name} if obj.ensemble_id else None

    def get_version(self, obj):
        v = obj.current_version
        return {
            'number': v.number if v else 1,
            'sha256': obj.content_hash or None,
            'size_bytes': obj.size_bytes,
            'pages': obj.pages,
            'filename': obj.original_filename or f'{obj.title}.pdf',
            'created_at': v.created_at if v else obj.created_at,
            'note': v.note if v else '',
            # 이 판에 붙은 분석 — TV 는 가진 것보다 새 것만 GET /scores/{id}/analysis/ 로 받는다
            'analyses': [{'analyzer': a.analyzer, 'analyzer_version': a.analyzer_version, 'updated_at': a.updated_at}
                         for a in (v.analyses.all() if v else [])],
        }

    def get_download_url(self, obj):
        request = self.context.get('request')
        path = f'/api/v1/scores/{obj.pk}/download/'
        return request.build_absolute_uri(path) if request else path

    def get_layout(self, obj):
        """보표 · 마디 분석 파일(앱 분석과 같은 결과, scores/layouts.py) — 없으면 null"""
        from .layouts import layout_filename, layout_of
        v = obj.current_version
        analysis = layout_of(v) if v else None
        if analysis is None:
            return None
        request = self.context.get('request')
        path = f'/api/v1/scores/{obj.pk}/layout/'
        data = analysis.data
        return {
            'url': request.build_absolute_uri(path) if request else path,
            'sha256': data.get('layout_sha256'), 'size_bytes': data.get('layout_bytes'),
            'filename': layout_filename(obj, v), 'analyzer_version': analysis.analyzer_version,
            'pdf_sha256': v.content_hash or None,
            'measures': data.get('measure_count'), 'systems': data.get('system_count'),
            'updated_at': analysis.updated_at,
        }

    def get_musicxml(self, obj):
        from .omr import musicxml_filename, musicxml_of
        v = obj.current_version
        analysis = musicxml_of(v) if v else None
        if analysis is None:
            return None
        request = self.context.get('request')
        path = f'/api/v1/scores/{obj.pk}/musicxml/'
        data = analysis.data
        return {
            'url': request.build_absolute_uri(path) if request else path,
            'sha256': data.get('musicxml_sha256'),
            'size_bytes': data.get('musicxml_bytes'),
            'filename': musicxml_filename(obj, v),
            'parts': [p.get('name', '') for p in data.get('parts', [])],
            'measures': data.get('measure_count'),
            'updated_at': analysis.updated_at,
        }


class AnalysisWriteSerializer(serializers.Serializer):
    analyzer = serializers.RegexField(r'^[a-z0-9][a-z0-9._-]{0,49}$', help_text='e.g. mrgq-measures')
    analyzer_version = serializers.CharField(max_length=50)
    sha256 = serializers.RegexField(r'^[0-9a-fA-F]{64}$')
    data = serializers.JSONField()


class AnalysisSerializer(serializers.ModelSerializer):
    version = serializers.IntegerField(source='version.number', read_only=True)
    sha256 = serializers.CharField(source='version.content_hash', read_only=True)
    uploaded_by = serializers.SerializerMethodField()

    class Meta:
        model = ScoreAnalysis
        fields = ['analyzer', 'analyzer_version', 'version', 'sha256', 'data', 'uploaded_by', 'created_at', 'updated_at']

    def get_uploaded_by(self, obj):
        return {'id': obj.uploaded_by_id, 'username': obj.uploaded_by.username} if obj.uploaded_by_id else None
