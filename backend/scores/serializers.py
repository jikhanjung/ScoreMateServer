"""
Serializers for scores app
"""
from rest_framework import serializers

from ensembles.models import Ensemble, Membership
from .models import Score


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

    def get_ensemble_name(self, obj):
        return obj.ensemble.name if obj.ensemble_id else None

    def get_uploader(self, obj):
        return {'id': obj.user_id, 'username': obj.user.username}

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


ENSEMBLE_FIELDS = ['ensemble', 'ensemble_name', 'part_name', 'uploader', 'can_edit']


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
            'id', 'title', 'composer', 'instrumentation', 
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
        """Generate thumbnail download URL via frontend proxy"""
        if not obj.thumbnail_key:
            return None
        
        try:
            # Return simple proxy URL with thumbnail key
            proxy_url = f"/api/thumbnail-proxy?key={obj.thumbnail_key}"
            return proxy_url
        except Exception:
            return None
    


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
            'id', 'title', 'composer', 'instrumentation', 
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
        """Generate thumbnail download URL via frontend proxy"""
        if not obj.thumbnail_key:
            return None
        
        try:
            # Return simple proxy URL with thumbnail key
            proxy_url = f"/api/thumbnail-proxy?key={obj.thumbnail_key}"
            return proxy_url
        except Exception:
            return None


class ScoreCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating scores (after file upload)"""
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    ensemble = serializers.PrimaryKeyRelatedField(
        queryset=Ensemble.objects.all(), required=False, allow_null=True
    )
    
    class Meta:
        model = Score
        fields = [
            'id', 'user', 'title', 'composer', 'instrumentation', 
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