"""
Serializers for files app (file upload/download)
"""
from rest_framework import serializers
from django.conf import settings
from .utils import validate_file_request


class FileUploadRequestSerializer(serializers.Serializer):
    """Serializer for file upload URL request"""
    filename = serializers.CharField(max_length=255, required=False)
    size_bytes = serializers.IntegerField(min_value=1)
    mime_type = serializers.CharField(max_length=100)
    
    def validate_size_bytes(self, value):
        """Validate file size"""
        if value > settings.MAX_UPLOAD_SIZE:
            max_mb = settings.MAX_UPLOAD_SIZE / (1024 * 1024)
            current_mb = value / (1024 * 1024)
            raise serializers.ValidationError(
                f"File size ({current_mb:.1f}MB) exceeds maximum allowed size ({max_mb}MB)"
            )
        return value
    
    def validate_mime_type(self, value):
        """Validate MIME type"""
        if value not in settings.ALLOWED_MIME_TYPES:
            raise serializers.ValidationError(
                f"File type not allowed. Allowed types: {', '.join(settings.ALLOWED_MIME_TYPES)}"
            )
        return value
    
    def validate(self, attrs):
        """Cross-field validation"""
        user = self.context['request'].user
        size_bytes = attrs['size_bytes']
        mime_type = attrs['mime_type']
        
        try:
            validate_file_request(user, size_bytes, mime_type)
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        
        return attrs


class FileUploadResponseSerializer(serializers.Serializer):
    """Serializer for file upload URL response"""
    upload_id = serializers.UUIDField(read_only=True)
    upload_url = serializers.URLField(read_only=True)
    s3_key = serializers.CharField(read_only=True)
    headers = serializers.DictField(read_only=True)
    expires_in = serializers.IntegerField(read_only=True)
    method = serializers.CharField(read_only=True)


class FileDownloadRequestSerializer(serializers.Serializer):
    """Serializer for file download URL request"""
    score_id = serializers.IntegerField()
    file_type = serializers.ChoiceField(
        choices=['original', 'thumbnail', 'page'],
        default='original'
    )
    page = serializers.IntegerField(min_value=1, required=False)
    
    def validate(self, attrs):
        """Cross-field validation"""
        file_type = attrs['file_type']
        page = attrs.get('page')
        
        # Page number required for page thumbnails
        if file_type == 'page' and not page:
            raise serializers.ValidationError({
                'page': 'Page number is required for page thumbnails'
            })
        
        # Page number not allowed for other file types
        if file_type != 'page' and page:
            raise serializers.ValidationError({
                'page': 'Page number only allowed for page thumbnails'
            })
        
        return attrs


class FileDownloadResponseSerializer(serializers.Serializer):
    """Serializer for file download URL response"""
    download_url = serializers.URLField(read_only=True)
    s3_key = serializers.CharField(read_only=True)
    expires_in = serializers.IntegerField(read_only=True)
    method = serializers.CharField(read_only=True)
    file_type = serializers.CharField(read_only=True)


class UploadConfirmationSerializer(serializers.Serializer):
    """Serializer for confirming upload completion and creating score"""
    upload_id = serializers.UUIDField()
    title = serializers.CharField(max_length=255)
    composer = serializers.CharField(max_length=255, required=False, allow_blank=True)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        allow_empty=True
    )
    duration_minutes = serializers.IntegerField(required=False, allow_null=True)
    instrument_parts = serializers.CharField(max_length=255, required=False, allow_blank=True)
    
    def validate_upload_id(self, value):
        """Validate upload ID exists in reservations"""
        from django.core.cache import cache
        
        reservation_key = f"quota_reservation:{value}"
        reservation_data = cache.get(reservation_key)
        
        if not reservation_data:
            raise serializers.ValidationError(
                "Upload reservation not found or expired"
            )
        
        user = self.context['request'].user
        if reservation_data['user_id'] != user.id:
            raise serializers.ValidationError(
                "Upload reservation belongs to different user"
            )
        
        return value