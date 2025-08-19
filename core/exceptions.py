"""
Custom exception handling for ScoreMateServer
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
import logging

logger = logging.getLogger(__name__)


class ScoreMateError(Exception):
    """Base exception for ScoreMate-specific errors"""
    default_message = "An error occurred"
    default_code = "error"
    default_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def __init__(self, message=None, code=None, status_code=None, details=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.status_code = status_code or self.default_status
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(ScoreMateError):
    """Validation-related errors"""
    default_message = "Validation failed"
    default_code = "validation_error"
    default_status = status.HTTP_400_BAD_REQUEST


class QuotaExceededError(ScoreMateError):
    """User quota exceeded errors"""
    default_message = "Storage quota exceeded"
    default_code = "quota_exceeded"
    default_status = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


class FileProcessingError(ScoreMateError):
    """File processing errors"""
    default_message = "File processing failed"
    default_code = "file_processing_error"
    default_status = status.HTTP_422_UNPROCESSABLE_ENTITY


class S3Error(ScoreMateError):
    """S3/Storage-related errors"""
    default_message = "Storage operation failed"
    default_code = "storage_error"
    default_status = status.HTTP_500_INTERNAL_SERVER_ERROR


class TaskError(ScoreMateError):
    """Background task errors"""
    default_message = "Task execution failed"
    default_code = "task_error"
    default_status = status.HTTP_500_INTERNAL_SERVER_ERROR


class PermissionDeniedError(ScoreMateError):
    """Permission denied errors"""
    default_message = "Permission denied"
    default_code = "permission_denied"
    default_status = status.HTTP_403_FORBIDDEN


class NotFoundError(ScoreMateError):
    """Resource not found errors"""
    default_message = "Resource not found"
    default_code = "not_found"
    default_status = status.HTTP_404_NOT_FOUND


def custom_exception_handler(exc, context):
    """
    Custom exception handler that provides consistent error responses
    """
    # Get the standard DRF error response first
    response = exception_handler(exc, context)
    
    # Log the exception for debugging
    request = context.get('request')
    user_id = getattr(request.user, 'id', 'anonymous') if request else 'unknown'
    logger.error(
        f"API Exception: {exc.__class__.__name__}: {str(exc)} "
        f"[User: {user_id}, Path: {request.path if request else 'unknown'}]",
        exc_info=True
    )
    
    # Handle ScoreMate custom exceptions
    if isinstance(exc, ScoreMateError):
        return Response({
            'error': {
                'type': exc.__class__.__name__,
                'code': exc.code,
                'message': exc.message,
                'details': exc.details,
            }
        }, status=exc.status_code)
    
    # Handle Django validation errors
    if isinstance(exc, DjangoValidationError):
        return Response({
            'error': {
                'type': 'ValidationError',
                'code': 'validation_error',
                'message': 'Validation failed',
                'details': {'non_field_errors': exc.messages} if hasattr(exc, 'messages') else {}
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Handle Http404 specifically
    if isinstance(exc, Http404):
        return Response({
            'error': {
                'type': 'NotFound',
                'code': 'not_found',
                'message': 'Resource not found',
                'details': {}
            }
        }, status=status.HTTP_404_NOT_FOUND)
    
    # If we have a standard DRF response, format it consistently
    if response is not None:
        # Format DRF error responses consistently
        error_data = response.data
        
        # Handle different DRF error formats
        if isinstance(error_data, dict):
            if 'detail' in error_data:
                # Standard DRF error with detail
                formatted_response = {
                    'error': {
                        'type': exc.__class__.__name__,
                        'code': getattr(exc, 'default_code', 'error'),
                        'message': str(error_data['detail']),
                        'details': {}
                    }
                }
            else:
                # Validation errors or field errors
                formatted_response = {
                    'error': {
                        'type': 'ValidationError',
                        'code': 'validation_error',
                        'message': 'Validation failed',
                        'details': error_data
                    }
                }
        elif isinstance(error_data, list):
            # List of errors
            formatted_response = {
                'error': {
                    'type': exc.__class__.__name__,
                    'code': 'error',
                    'message': str(error_data[0]) if error_data else 'An error occurred',
                    'details': {'errors': error_data}
                }
            }
        else:
            # String or other format
            formatted_response = {
                'error': {
                    'type': exc.__class__.__name__,
                    'code': 'error',
                    'message': str(error_data),
                    'details': {}
                }
            }
        
        response.data = formatted_response
        return response
    
    # Unhandled exception - return generic 500 error
    return Response({
        'error': {
            'type': 'InternalServerError',
            'code': 'internal_error',
            'message': 'An internal server error occurred',
            'details': {}
        }
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def handle_quota_check(user, additional_size_mb):
    """
    Helper function to check user quota before file operations
    
    Args:
        user: User instance
        additional_size_mb: Additional size in MB to check
        
    Raises:
        QuotaExceededError: If quota would be exceeded
    """
    if user.available_quota_mb < additional_size_mb:
        raise QuotaExceededError(
            message=f"Cannot upload file: would exceed quota by {additional_size_mb - user.available_quota_mb:.2f}MB",
            details={
                'required_mb': additional_size_mb,
                'available_mb': user.available_quota_mb,
                'used_mb': user.used_quota_mb,
                'total_mb': user.total_quota_mb
            }
        )


def handle_file_validation(file_obj, allowed_types=None, max_size_mb=None):
    """
    Helper function to validate uploaded files
    
    Args:
        file_obj: Django UploadedFile object
        allowed_types: List of allowed MIME types
        max_size_mb: Maximum file size in MB
        
    Raises:
        ValidationError: If file validation fails
    """
    if allowed_types and file_obj.content_type not in allowed_types:
        raise ValidationError(
            message=f"File type '{file_obj.content_type}' not allowed",
            details={
                'received_type': file_obj.content_type,
                'allowed_types': allowed_types
            }
        )
    
    if max_size_mb and file_obj.size > (max_size_mb * 1024 * 1024):
        raise ValidationError(
            message=f"File size {file_obj.size / (1024 * 1024):.2f}MB exceeds maximum of {max_size_mb}MB",
            details={
                'file_size_mb': file_obj.size / (1024 * 1024),
                'max_size_mb': max_size_mb
            }
        )


def handle_model_validation(model_instance):
    """
    Helper function to handle Django model validation
    
    Args:
        model_instance: Django model instance to validate
        
    Raises:
        ValidationError: If model validation fails
    """
    try:
        model_instance.full_clean()
    except DjangoValidationError as e:
        error_dict = e.error_dict if hasattr(e, 'error_dict') else {}
        formatted_errors = {}
        
        for field, errors in error_dict.items():
            formatted_errors[field] = [str(error) for error in errors]
        
        raise ValidationError(
            message="Model validation failed",
            details=formatted_errors
        )