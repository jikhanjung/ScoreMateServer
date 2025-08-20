"""
Views for files app (presigned URLs, file operations)
"""
from django.http import HttpResponse, Http404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
import logging
import requests

from scores.models import Score
from .serializers import (
    FileUploadRequestSerializer,
    FileUploadResponseSerializer,
    FileDownloadRequestSerializer,
    FileDownloadResponseSerializer,
    UploadConfirmationSerializer
)
from .utils import S3Handler, QuotaManager, generate_upload_s3_key

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
            
            # Reserve quota with s3_key and mime_type
            upload_id = QuotaManager.reserve_quota(user, size_bytes, s3_key, mime_type)
            
            # Generate presigned URL
            s3_handler = S3Handler()
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
    
    def get(self, request):
        """Generate presigned download URL"""
        serializer = FileDownloadRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        score_id = serializer.validated_data['score_id']
        file_type = serializer.validated_data['file_type']
        page = serializer.validated_data.get('page')
        
        # Get score and verify ownership
        score = get_object_or_404(Score, id=score_id, user=user)
        
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
            s3_handler = S3Handler()
            
            # Check if file exists (optional, can be expensive for many requests)
            # if not s3_handler.check_file_exists(s3_key):
            #     return Response({
            #         'error': 'FILE_NOT_FOUND',
            #         'message': 'File does not exist in storage',
            #         'code': 'E003'
            #     }, status=status.HTTP_404_NOT_FOUND)
            
            presigned_data = s3_handler.generate_presigned_download_url(s3_key)
            
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
            
            score = Score.objects.create(
                user=user,
                title=serializer.validated_data['title'],
                composer=serializer.validated_data.get('composer', ''),
                instrumentation=serializer.validated_data.get('instrument_parts', ''),
                s3_key=s3_key,
                size_bytes=reservation_data['size_bytes'],
                mime=reservation_data.get('mime_type', 'application/pdf'),
                tags=serializer.validated_data.get('tags', [])
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


@api_view(['GET'])
@permission_classes([AllowAny])  # Allow unauthenticated access for thumbnails
def get_thumbnail(request, thumbnail_key):
    """
    Serve thumbnail image directly from S3
    """
    try:
        s3_handler = S3Handler()
        
        # Generate presigned URL for internal access
        result = s3_handler.generate_presigned_download_url(
            thumbnail_key,
            expiry=300,  # 5 minutes
            use_public_endpoint=False  # Use internal endpoint
        )
        
        # Fetch the image from S3
        response = requests.get(result['url'], timeout=10)
        response.raise_for_status()
        
        # Return the image with appropriate headers
        http_response = HttpResponse(
            response.content,
            content_type=response.headers.get('content-type', 'image/jpeg')
        )
        http_response['Cache-Control'] = 'public, max-age=3600'  # 1 hour cache
        
        return http_response
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch thumbnail {thumbnail_key}: {e}")
        raise Http404("Thumbnail not found")
    except Exception as e:
        logger.error(f"Error serving thumbnail {thumbnail_key}: {e}")
        raise Http404("Thumbnail not found")
