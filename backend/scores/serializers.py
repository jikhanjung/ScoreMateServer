"""
Serializers for scores app
"""
from rest_framework import serializers
from .models import Score


class ScoreSerializer(serializers.ModelSerializer):
    """Serializer for Score model"""
    size_mb = serializers.ReadOnlyField()
    file_size = serializers.SerializerMethodField()  # For frontend compatibility
    page_count = serializers.SerializerMethodField()  # Alias for pages
    has_thumbnail = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    
    class Meta:
        model = Score
        fields = [
            'id', 'user', 'title', 'composer', 'instrumentation', 
            's3_key', 'size_bytes', 'size_mb', 'file_size', 'mime', 
            'pages', 'page_count', 'tags', 'note', 'thumbnail_key', 
            'has_thumbnail', 'thumbnail_url', 'content_hash',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'size_mb', 'file_size', 'page_count', 'has_thumbnail', 'thumbnail_url']
    
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
    
    def validate_s3_key(self, value):
        """Validate that s3_key follows the expected pattern"""
        user = self.context['request'].user
        expected_prefix_scores = f"{user.id}/scores/"
        expected_prefix_uploads = f"{user.id}/uploads/"
        
        if not (value.startswith(expected_prefix_scores) or value.startswith(expected_prefix_uploads)):
            raise serializers.ValidationError(
                f"S3 key must start with '{expected_prefix_scores}' or '{expected_prefix_uploads}'"
            )
        return value


class ScoreListSerializer(serializers.ModelSerializer):
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
            'size_mb', 'file_size', 'pages', 'page_count', 'tags', 
            'thumbnail_key', 'has_thumbnail', 'thumbnail_url',
            'created_at', 'updated_at'
        ]
    
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
    
    class Meta:
        model = Score
        fields = [
            'user', 'title', 'composer', 'instrumentation', 
            's3_key', 'size_bytes', 'mime', 'tags', 'note', 'content_hash'
        ]
    
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
        
        # Trigger background tasks for PDF processing
        from tasks.pdf_tasks import process_pdf_info, generate_thumbnail
        
        # Start PDF info extraction
        process_pdf_info.delay(score.id)
        
        # Generate cover thumbnail
        generate_thumbnail.delay(score.id, page_number=1)
        
        return score