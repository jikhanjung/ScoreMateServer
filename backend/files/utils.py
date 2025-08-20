"""
Utility functions for file operations (S3 presigned URLs)
"""
import uuid
import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class S3Handler:
    """Handle S3 operations for file upload/download"""
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            endpoint_url=settings.STORAGE_ENDPOINT if hasattr(settings, 'STORAGE_ENDPOINT') else None,
            aws_access_key_id=settings.STORAGE_ACCESS_KEY,
            aws_secret_access_key=settings.STORAGE_SECRET_KEY,
            use_ssl=getattr(settings, 'STORAGE_USE_SSL', True)
        )
        self.bucket_name = settings.STORAGE_BUCKET
    
    def generate_presigned_upload_url(self, s3_key, content_type, expiry=None):
        """Generate presigned URL for file upload"""
        if expiry is None:
            expiry = settings.PRESIGNED_URL_EXPIRY
        
        try:
            response = self.s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key,
                    'ContentType': content_type,
                },
                ExpiresIn=expiry
            )
            
            # Replace internal endpoint with public endpoint for client access
            public_url = response
            if hasattr(settings, 'STORAGE_PUBLIC_ENDPOINT') and settings.STORAGE_PUBLIC_ENDPOINT:
                public_url = response.replace(settings.STORAGE_ENDPOINT, settings.STORAGE_PUBLIC_ENDPOINT)
            
            return {
                'url': public_url,
                'headers': {
                    'Content-Type': content_type,
                },
                'method': 'PUT'
            }
        except ClientError as e:
            logger.error(f"Failed to generate upload URL for {s3_key}: {e}")
            raise
    
    def generate_presigned_download_url(self, s3_key, expiry=None, use_public_endpoint=True):
        """Generate presigned URL for file download"""
        if expiry is None:
            expiry = settings.PRESIGNED_URL_EXPIRY
        
        try:
            # If we need public endpoint, create a separate client with public endpoint
            if (use_public_endpoint and 
                hasattr(settings, 'STORAGE_PUBLIC_ENDPOINT') and 
                settings.STORAGE_PUBLIC_ENDPOINT):
                
                public_client = boto3.client(
                    's3',
                    endpoint_url=settings.STORAGE_PUBLIC_ENDPOINT,
                    aws_access_key_id=settings.STORAGE_ACCESS_KEY,
                    aws_secret_access_key=settings.STORAGE_SECRET_KEY,
                    use_ssl=getattr(settings, 'STORAGE_USE_SSL', True)
                )
                
                response = public_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': self.bucket_name,
                        'Key': s3_key
                    },
                    ExpiresIn=expiry
                )
            else:
                response = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': self.bucket_name,
                        'Key': s3_key
                    },
                    ExpiresIn=expiry
                )
            
            return {
                'url': response,
                'method': 'GET',
                'expires_in': expiry
            }
        except ClientError as e:
            logger.error(f"Failed to generate download URL for {s3_key}: {e}")
            raise
    
    def check_file_exists(self, s3_key):
        """Check if file exists in S3"""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            logger.error(f"Error checking file existence {s3_key}: {e}")
            raise
    
    def delete_file(self, s3_key):
        """Delete file from S3"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"Successfully deleted {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete {s3_key}: {e}")
            raise


class QuotaManager:
    """Manage user quota reservations and confirmations"""
    
    @staticmethod
    def reserve_quota(user, size_bytes, s3_key=None, mime_type=None, upload_id=None):
        """
        Reserve quota for upload (step 1)
        Store reservation in Redis with TTL
        """
        if upload_id is None:
            upload_id = str(uuid.uuid4())
        
        # Check if user can upload
        if not user.can_upload(size_bytes):
            raise ValueError(f"Upload size ({size_bytes / (1024*1024):.1f}MB) exceeds available quota")
        
        # Store reservation in cache (5 minutes TTL)
        reservation_key = f"quota_reservation:{upload_id}"
        reservation_data = {
            'user_id': user.id,
            'size_bytes': size_bytes,
            's3_key': s3_key,
            'mime_type': mime_type,
            'reserved_at': cache.now() if hasattr(cache, 'now') else None,
        }
        
        cache.set(reservation_key, reservation_data, timeout=300)  # 5 minutes
        logger.info(f"Reserved quota for user {user.id}: {size_bytes / (1024*1024):.1f}MB (upload_id: {upload_id})")
        
        return upload_id
    
    @staticmethod
    def confirm_quota(user, upload_id):
        """
        Confirm quota usage (step 2)
        Move from reservation to actual usage
        """
        reservation_key = f"quota_reservation:{upload_id}"
        reservation_data = cache.get(reservation_key)
        
        if not reservation_data:
            raise ValueError(f"Quota reservation not found or expired: {upload_id}")
        
        if reservation_data['user_id'] != user.id:
            raise ValueError(f"Quota reservation belongs to different user")
        
        size_bytes = reservation_data['size_bytes']
        size_mb = size_bytes // (1024 * 1024)
        
        # Update user quota
        user.used_quota_mb += size_mb
        user.save(update_fields=['used_quota_mb'])
        
        # Remove reservation
        cache.delete(reservation_key)
        
        logger.info(f"Confirmed quota usage for user {user.id}: {size_mb}MB")
        return size_mb
    
    @staticmethod
    def cancel_reservation(upload_id):
        """Cancel quota reservation"""
        reservation_key = f"quota_reservation:{upload_id}"
        cache.delete(reservation_key)
        logger.info(f"Cancelled quota reservation: {upload_id}")
    
    @staticmethod
    def release_quota(user, size_bytes):
        """
        Release quota (step 3 - for file deletion)
        """
        size_mb = size_bytes // (1024 * 1024)
        user.used_quota_mb = max(0, user.used_quota_mb - size_mb)
        user.save(update_fields=['used_quota_mb'])
        
        logger.info(f"Released quota for user {user.id}: {size_mb}MB")
        return size_mb


def generate_upload_s3_key(user_id, filename=None):
    """Generate S3 key for file upload"""
    upload_id = str(uuid.uuid4())
    if filename:
        # Extract file extension
        ext = filename.split('.')[-1] if '.' in filename else 'pdf'
        return f"{user_id}/uploads/{upload_id}/original.{ext}"
    else:
        return f"{user_id}/uploads/{upload_id}/original.pdf"


def validate_file_request(user, size_bytes, mime_type):
    """Validate file upload request"""
    # Check MIME type
    if mime_type not in settings.ALLOWED_MIME_TYPES:
        raise ValueError(f"File type not allowed. Allowed types: {', '.join(settings.ALLOWED_MIME_TYPES)}")
    
    # Check file size
    if size_bytes > settings.MAX_UPLOAD_SIZE:
        max_mb = settings.MAX_UPLOAD_SIZE / (1024 * 1024)
        raise ValueError(f"File size ({size_bytes / (1024*1024):.1f}MB) exceeds maximum allowed size ({max_mb}MB)")
    
    # Check quota
    if not user.can_upload(size_bytes):
        available_mb = user.available_quota_mb
        request_mb = size_bytes / (1024 * 1024)
        raise ValueError(f"File size ({request_mb:.1f}MB) exceeds available quota ({available_mb}MB)")
    
    return True