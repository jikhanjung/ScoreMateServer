"""
Views for files app (presigned URLs, file operations)
"""
from urllib.parse import quote

from django.conf import settings
from django.http import (
    FileResponse, Http404, HttpResponse, HttpResponseForbidden, HttpResponseRedirect, JsonResponse,
)
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
import logging

from scores.models import Score
from .serializers import (
    FileUploadRequestSerializer,
    FileUploadResponseSerializer,
    FileDownloadRequestSerializer,
    FileDownloadResponseSerializer,
    UploadConfirmationSerializer
)
from .utils import get_storage, load_blob_token, LocalStorageHandler, QuotaManager, generate_upload_s3_key

logger = logging.getLogger(__name__)


class FileUploadURLView(APIView):
    """Generate presigned URL for file upload"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Generate presigned upload URL and reserve quota"""
        serializer = FileUploadRequestSerializer(
            data=request.data, 
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        filename = serializer.validated_data.get('filename')
        size_bytes = serializer.validated_data['size_bytes']
        mime_type = serializer.validated_data['mime_type']
        
        try:
            # Generate S3 key
            s3_key = generate_upload_s3_key(user.id, filename)
            
            # Reserve quota with s3_key, mime_type, and original filename
            upload_id = QuotaManager.reserve_quota(user, size_bytes, s3_key, mime_type, filename)
            
            # Generate presigned URL
            s3_handler = get_storage()
            presigned_data = s3_handler.generate_presigned_upload_url(
                s3_key, mime_type
            )
            
            # Prepare response
            response_data = {
                'upload_id': upload_id,
                'upload_url': presigned_data['url'],
                's3_key': s3_key,
                'headers': presigned_data['headers'],
                'expires_in': 300,  # 5 minutes
                'method': presigned_data['method']
            }
            
            response_serializer = FileUploadResponseSerializer(response_data)
            
            logger.info(f"Generated upload URL for user {user.id}: {s3_key}")
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response({
                'error': 'QUOTA_EXCEEDED',
                'message': str(e),
                'code': 'E001'
            }, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        
        except Exception as e:
            logger.error(f"Failed to generate upload URL for user {user.id}: {e}")
            return Response({
                'error': 'UPLOAD_URL_GENERATION_FAILED',
                'message': 'Failed to generate upload URL',
                'code': 'E005'
            }, status=status.HTTP_502_BAD_GATEWAY)


class FileDownloadURLView(APIView):
    """Generate presigned URL for file download"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, score_id=None):
        """Generate presigned download URL"""
        # Get score_id from URL path parameter or query parameter
        if score_id is None:
            serializer = FileDownloadRequestSerializer(data=request.query_params)
            serializer.is_valid(raise_exception=True)
            score_id = serializer.validated_data['score_id']
            file_type = serializer.validated_data['file_type']
            page = serializer.validated_data.get('page')
        else:
            # For URL path parameter, default to original file and get other params from query
            file_type = request.query_params.get('file_type', 'original')
            page = request.query_params.get('page')
        
        user = request.user
        
        # 내 개인 악보이거나 내가 멤버인 앙상블의 악보
        score = get_object_or_404(Score.objects.readable_by(user), id=score_id)
        
        # Determine S3 key based on file type
        if file_type == 'original':
            s3_key = score.s3_key
        elif file_type == 'thumbnail':
            s3_key = score.thumbnail_key or score.generate_thumbnail_s3_key()
        elif file_type == 'page':
            s3_key = score.generate_page_thumbnail_s3_key(page)
        else:
            return Response({
                'error': 'INVALID_FILE_TYPE',
                'message': f'Invalid file type: {file_type}',
                'code': 'E004'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not s3_key:
            return Response({
                'error': 'FILE_NOT_FOUND',
                'message': f'File not available: {file_type}',
                'code': 'E003'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            # Generate presigned URL
            s3_handler = get_storage()
            
            # Determine the download filename
            download_filename = None
            if file_type == 'original':
                if score.original_filename:
                    download_filename = score.original_filename
                else:
                    download_filename = f"{score.title}.pdf"
            elif file_type == 'thumbnail':
                download_filename = f"{score.title}_thumbnail.jpg"
            elif file_type == 'page':
                download_filename = f"{score.title}_page_{page}.jpg"
            
            # Check if file exists (optional, can be expensive for many requests)
            # if not s3_handler.check_file_exists(s3_key):
            #     return Response({
            #         'error': 'FILE_NOT_FOUND',
            #         'message': 'File does not exist in storage',
            #         'code': 'E003'
            #     }, status=status.HTTP_404_NOT_FOUND)
            
            presigned_data = s3_handler.generate_presigned_download_url(s3_key, filename=download_filename)
            
            # Prepare response
            response_data = {
                'download_url': presigned_data['url'],
                's3_key': s3_key,
                'expires_in': presigned_data['expires_in'],
                'method': presigned_data['method'],
                'file_type': file_type
            }
            
            response_serializer = FileDownloadResponseSerializer(response_data)
            
            logger.info(f"Generated download URL for user {user.id}, score {score_id}, type {file_type}")
            return Response(response_serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Failed to generate download URL for user {user.id}, score {score_id}: {e}")
            return Response({
                'error': 'DOWNLOAD_URL_GENERATION_FAILED',
                'message': 'Failed to generate download URL',
                'code': 'E005'
            }, status=status.HTTP_502_BAD_GATEWAY)


class UploadConfirmationView(APIView):
    """Confirm upload completion and finalize quota usage"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Confirm upload completion"""
        serializer = UploadConfirmationSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        upload_id = serializer.validated_data['upload_id']
        
        try:
            # Get reservation data
            from django.core.cache import cache
            reservation_key = f"quota_reservation:{upload_id}"
            reservation_data = cache.get(reservation_key)
            
            if not reservation_data:
                return Response({
                    'error': 'UPLOAD_RESERVATION_NOT_FOUND',
                    'message': 'Upload reservation not found or expired',
                    'code': 'E007'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Confirm quota usage
            used_mb = QuotaManager.confirm_quota(user, upload_id)
            
            # Create score with uploaded file
            from scores.models import Score
            
            # Generate S3 key from reservation data
            s3_key = reservation_data['s3_key']
            
            # Extract original filename from s3_key or use the title
            # filename 은 upload-url 에서 선택이라 예약에 None 으로 들어 있을 수 있다
            original_filename = reservation_data.get('original_filename') or ""
            if not original_filename and '/' in s3_key:
                # Extract filename from s3_key path
                s3_filename = s3_key.split('/')[-1]
                if s3_filename and s3_filename != 'original.pdf':
                    original_filename = s3_filename
            
            score = Score.objects.create(
                user=user,
                title=serializer.validated_data['title'],
                original_filename=original_filename,
                composer=serializer.validated_data.get('composer', ''),
                instrumentation=serializer.validated_data.get('instrument_parts', ''),
                s3_key=s3_key,
                size_bytes=reservation_data['size_bytes'],
                mime=reservation_data.get('mime_type', 'application/pdf'),
                tags=serializer.validated_data.get('tags', []),
                ensemble=serializer.validated_data.get('ensemble'),
                part_name=serializer.validated_data.get('part_name', ''),
            )
            
            # Queue background tasks for PDF processing (asynchronously)
            try:
                from tasks.pdf_tasks import process_pdf_info, generate_thumbnail
                process_pdf_info.delay(score.id)
                generate_thumbnail.delay(score.id, page_number=1)
            except Exception as e:
                # Log but don't fail the upload
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to queue background tasks for score {score.id}: {e}")
            
            return Response({
                'message': 'Upload confirmed and score created',
                'upload_id': upload_id,
                'score_id': score.id,
                'quota_used_mb': used_mb,
                'remaining_quota_mb': user.available_quota_mb
            }, status=status.HTTP_200_OK)
            
        except ValueError as e:
            return Response({
                'error': 'UPLOAD_CONFIRMATION_FAILED',
                'message': str(e),
                'code': 'E006'
            }, status=status.HTTP_400_BAD_REQUEST)


class UploadCancellationView(APIView):
    """Cancel upload and release quota reservation"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Cancel upload reservation"""
        upload_id = request.data.get('upload_id')
        
        if not upload_id:
            return Response({
                'error': 'MISSING_UPLOAD_ID',
                'message': 'upload_id is required',
                'code': 'E007'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            QuotaManager.cancel_reservation(upload_id)
            
            return Response({
                'message': 'Upload cancelled',
                'upload_id': upload_id
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Failed to cancel upload {upload_id}: {e}")
            return Response({
                'error': 'CANCELLATION_FAILED',
                'message': 'Failed to cancel upload',
                'code': 'E008'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FileDirectDownloadView(APIView):
    """악보 파일로 보내는 짧은 링크 — 파일을 Django 로 흘리지 않고 서명 URL 로 302"""
    permission_classes = [IsAuthenticated]

    def get(self, request, score_id):
        score = get_object_or_404(Score.objects.readable_by(request.user), id=score_id)
        file_type = request.query_params.get('file_type', 'original')
        if file_type == 'original':
            s3_key = score.s3_key
            filename = score.original_filename or f"{score.title}.pdf"
        elif file_type == 'thumbnail':
            s3_key = score.thumbnail_key
            filename = None
        else:
            return Response({
                'error': 'INVALID_FILE_TYPE',
                'message': f'Invalid file type: {file_type}',
                'code': 'E004'
            }, status=status.HTTP_400_BAD_REQUEST)
        if not s3_key:
            raise Http404('File not available')
        url = get_storage().generate_presigned_download_url(s3_key, expiry=60, filename=filename)['url']
        return HttpResponseRedirect(url)


@method_decorator(csrf_exempt, name='dispatch')
class FileBlobView(View):
    """local 저장소의 서명 토큰 URL — 토큰이 곧 권한이다 (JWT 없음)

    GET: 토큰을 확인하고 nginx 에 X-Accel-Redirect 로 넘긴다 (FILES_X_ACCEL_PREFIX 가 없으면 직접 보낸다 — 개발용)
    PUT: 업로드 예약 때 만든 키에만, 한 번만 쓴다 (이미 있으면 409)
    """
    CHUNK = 1024 * 1024

    def dispatch(self, request, *args, **kwargs):
        if settings.STORAGE_BACKEND != 'local':
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def _payload(self, token, op):
        payload = load_blob_token(token)
        if payload is None or payload.get('op') != op:
            return None
        return payload

    def get(self, request, token):
        payload = self._payload(token, 'get')
        if payload is None:
            return HttpResponseForbidden('Invalid or expired link')
        storage = LocalStorageHandler()
        key = payload['k']
        path = storage.path_for(key)
        if not path.is_file():
            raise Http404('File not found')

        content_type = storage.content_type_for(key)
        filename = payload.get('fn')
        if settings.FILES_X_ACCEL_PREFIX:
            response = HttpResponse(content_type=content_type)
            response['X-Accel-Redirect'] = settings.FILES_X_ACCEL_PREFIX + quote(key)
        else:
            response = FileResponse(open(path, 'rb'), content_type=content_type)
        if filename:
            response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
        # 링크마다 만료가 있으니 브라우저는 그 동안 캐시해도 된다 (공유 캐시는 안 된다)
        response['Cache-Control'] = 'private, max-age=3600'
        return response

    def put(self, request, token):
        payload = self._payload(token, 'put')
        if payload is None:
            return HttpResponseForbidden('Invalid or expired upload link')
        storage = LocalStorageHandler()
        key = payload['k']
        if storage.path_for(key).exists():
            return JsonResponse({'error': 'ALREADY_UPLOADED', 'message': 'This upload link was already used'},
                                status=status.HTTP_409_CONFLICT)
        declared = request.META.get('CONTENT_LENGTH')
        if declared and declared.isdigit() and int(declared) > settings.MAX_UPLOAD_SIZE:
            return JsonResponse({'error': 'FILE_TOO_LARGE'}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        def chunks():
            while True:
                chunk = request.read(self.CHUNK)
                if not chunk:
                    break
                yield chunk
        try:
            written = storage.write_stream(key, chunks(), max_bytes=settings.MAX_UPLOAD_SIZE)
        except ValueError:
            return JsonResponse({'error': 'FILE_TOO_LARGE'}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        logger.info(f"Stored upload {key} ({written} bytes)")
        return JsonResponse({'key': key, 'size_bytes': written}, status=status.HTTP_201_CREATED)
