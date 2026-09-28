"""
Utility functions for file operations

저장소 백엔드 두 가지 (settings.STORAGE_BACKEND):
- 's3'    : S3/MinIO presigned URL (개발용 docker-compose, 테스트는 moto)
- 'local' : 서버 디스크(FILES_ROOT). 서명한 토큰 URL 로 올리고 받는다 — 받기는 Django 가 토큰만
            확인하고 전송은 nginx X-Accel-Redirect 가 한다 (devlog 054 §6, dolfinid 배포)
어느 쪽이든 get_storage() 로 얻고 같은 메서드를 쓴다.
"""
import math
import mimetypes
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import quote

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core import signing
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
    
    def generate_presigned_download_url(self, s3_key, expiry=None, use_public_endpoint=True, filename=None, variant=None):
        """Generate presigned URL for file download (variant 는 local 저장소용 — S3 URL 은 요청마다 다르다)"""
        if expiry is None:
            expiry = settings.PRESIGNED_URL_EXPIRY
        
        try:
            # Prepare parameters for the presigned URL
            params = {
                'Bucket': self.bucket_name,
                'Key': s3_key
            }
            
            # Add Content-Disposition header to set download filename
            if filename:
                params['ResponseContentDisposition'] = f'attachment; filename="{filename}"'
            
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
                    Params=params,
                    ExpiresIn=expiry
                )
            else:
                response = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params=params,
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

    def read_bytes(self, s3_key):
        """서버 안에서 파일 내용을 읽는다 (PDF 처리 작업용)"""
        return self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)['Body'].read()

    def write_bytes(self, s3_key, data, content_type='application/octet-stream'):
        """서버 안에서 파일을 쓴다 (썸네일)"""
        self.s3_client.put_object(
            Bucket=self.bucket_name, Key=s3_key, Body=data,
            ContentType=content_type, CacheControl='max-age=86400',
        )

    def delete_prefix(self, prefix):
        """prefix/ 아래를 모두 지운다 (쪽 이미지 캐시)"""
        paginator = self.s3_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix.rstrip('/') + '/'):
            objects = [{'Key': o['Key']} for o in page.get('Contents', [])]
            if objects:
                self.s3_client.delete_objects(Bucket=self.bucket_name, Delete={'Objects': objects})


BLOB_SIGNING_SALT = 'scoremate.files.blob'


def sign_blob_token(payload, expiry):
    """파일 하나에 대한 권한을 담은 토큰. 만료 시각을 올림해 같은 파일의 URL 이 한동안 같게 한다
    (목록을 다시 불러와도 썸네일이 브라우저 캐시에서 나온다)"""
    step = max(60, min(3600, expiry // 4))
    expires_at = int(math.ceil((time.time() + expiry) / step) * step)
    return signing.dumps({**payload, 'x': expires_at}, salt=BLOB_SIGNING_SALT, compress=True)


def load_blob_token(token):
    """서명과 만료를 확인한 payload, 아니면 None"""
    try:
        payload = signing.loads(token, salt=BLOB_SIGNING_SALT)
    except signing.BadSignature:
        return None
    if not isinstance(payload, dict) or payload.get('x', 0) < time.time():
        return None
    return payload


class LocalStorageHandler:
    """서버 디스크 저장소 — S3Handler 와 같은 메서드

    키는 S3 와 같은 모양({user_id}/uploads/…, {user_id}/scores/…)이고 FILES_ROOT 아래의 상대 경로다.
    """

    def __init__(self):
        self.root = Path(settings.FILES_ROOT)

    def path_for(self, key):
        path = (self.root / key).resolve()
        root = self.root.resolve()
        if not key or path == root or root not in path.parents:
            raise ValueError(f'Invalid storage key: {key!r}')
        return path

    def _url(self, token):
        return f"{settings.FILES_PUBLIC_BASE}{settings.FILES_BLOB_PATH}{token}/"

    def generate_presigned_upload_url(self, s3_key, content_type, expiry=None):
        expiry = expiry or settings.PRESIGNED_URL_EXPIRY
        self.path_for(s3_key)  # 키 검증
        token = sign_blob_token({'op': 'put', 'k': s3_key, 'ct': content_type}, expiry)
        return {'url': self._url(token), 'headers': {'Content-Type': content_type}, 'method': 'PUT'}

    def generate_presigned_download_url(self, s3_key, expiry=None, use_public_endpoint=True, filename=None, variant=None):
        """variant: 같은 키의 내용이 바뀔 때(새 판의 표지 썸네일) URL 을 바꿔 브라우저 캐시를 피한다"""
        expiry = expiry or settings.PRESIGNED_URL_EXPIRY
        self.path_for(s3_key)
        payload = {'op': 'get', 'k': s3_key}
        if filename:
            payload['fn'] = filename
        if variant is not None:
            payload['v'] = variant
        return {'url': self._url(sign_blob_token(payload, expiry)), 'method': 'GET', 'expires_in': expiry}

    def check_file_exists(self, s3_key):
        return self.path_for(s3_key).is_file()

    def delete_file(self, s3_key):
        path = self.path_for(s3_key)
        path.unlink(missing_ok=True)
        # 비게 된 상위 디렉터리도 지운다 (FILES_ROOT 는 남긴다) — 악보마다 디렉터리가 쌓이지 않게
        root = self.root.resolve()
        parent = path.parent
        while parent != root and root in parent.parents:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
        logger.info(f"Successfully deleted {s3_key}")
        return True

    def read_bytes(self, s3_key):
        return self.path_for(s3_key).read_bytes()

    def delete_prefix(self, prefix):
        """prefix/ 아래를 모두 지운다 (쪽 이미지 캐시) — 비게 된 상위 디렉터리도"""
        path = self.path_for(prefix.rstrip('/'))
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        root = self.root.resolve()
        parent = path.parent
        while parent != root and root in parent.parents:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent

    def write_bytes(self, s3_key, data, content_type='application/octet-stream'):
        self.write_stream(s3_key, [data])

    def write_stream(self, s3_key, chunks, max_bytes=None):
        """임시 파일에 쓰고 같은 디렉터리에서 rename — 반쯤 쓴 파일이 보이지 않게. 쓴 바이트 수를 돌려준다"""
        path = self.path_for(s3_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.upload-')
        written = 0
        try:
            with os.fdopen(fd, 'wb') as out:
                for chunk in chunks:
                    written += len(chunk)
                    if max_bytes is not None and written > max_bytes:
                        raise ValueError('File exceeds the maximum upload size')
                    out.write(chunk)
            os.chmod(tmp, 0o664)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return written

    @staticmethod
    def content_type_for(s3_key):
        return mimetypes.guess_type(s3_key)[0] or 'application/octet-stream'


def get_storage():
    """설정에 맞는 저장소 (STORAGE_BACKEND = 's3' | 'local')"""
    if settings.STORAGE_BACKEND == 'local':
        return LocalStorageHandler()
    return S3Handler()


class QuotaManager:
    """Manage user quota reservations and confirmations"""
    
    @staticmethod
    def reserve_quota(user, size_bytes, s3_key=None, mime_type=None, original_filename=None, upload_id=None):
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
            'original_filename': original_filename,
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