"""
Standardized response helpers for consistent API responses
"""
from rest_framework.response import Response
from rest_framework import status
from typing import Any, Dict, Optional


class APIResponse:
    """
    Helper class for creating standardized API responses
    """
    
    @staticmethod
    def success(data: Any = None, message: str = None, status_code: int = status.HTTP_200_OK) -> Response:
        """
        Create a successful response
        
        Args:
            data: Response data
            message: Optional success message
            status_code: HTTP status code
            
        Returns:
            Response: DRF Response object
        """
        response_data = {}
        
        if data is not None:
            response_data['data'] = data
        
        if message:
            response_data['message'] = message
            
        return Response(response_data, status=status_code)
    
    @staticmethod
    def created(data: Any = None, message: str = "Resource created successfully") -> Response:
        """
        Create a successful creation response
        
        Args:
            data: Created resource data
            message: Success message
            
        Returns:
            Response: DRF Response object with 201 status
        """
        return APIResponse.success(data, message, status.HTTP_201_CREATED)
    
    @staticmethod
    def accepted(data: Any = None, message: str = "Request accepted for processing") -> Response:
        """
        Create an accepted response (for async operations)
        
        Args:
            data: Response data (e.g., task_id)
            message: Acceptance message
            
        Returns:
            Response: DRF Response object with 202 status
        """
        return APIResponse.success(data, message, status.HTTP_202_ACCEPTED)
    
    @staticmethod
    def no_content(message: str = None) -> Response:
        """
        Create a no content response
        
        Args:
            message: Optional message
            
        Returns:
            Response: DRF Response object with 204 status
        """
        response_data = {}
        if message:
            response_data['message'] = message
            
        return Response(response_data, status=status.HTTP_204_NO_CONTENT)
    
    @staticmethod
    def error(
        message: str, 
        code: str = "error",
        details: Dict[str, Any] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST
    ) -> Response:
        """
        Create an error response
        
        Args:
            message: Error message
            code: Error code
            details: Additional error details
            status_code: HTTP status code
            
        Returns:
            Response: DRF Response object
        """
        return Response({
            'error': {
                'type': 'APIError',
                'code': code,
                'message': message,
                'details': details or {}
            }
        }, status=status_code)
    
    @staticmethod
    def validation_error(errors: Dict[str, Any], message: str = "Validation failed") -> Response:
        """
        Create a validation error response
        
        Args:
            errors: Validation errors dictionary
            message: Error message
            
        Returns:
            Response: DRF Response object with 400 status
        """
        return Response({
            'error': {
                'type': 'ValidationError',
                'code': 'validation_error',
                'message': message,
                'details': errors
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    @staticmethod
    def not_found(resource: str = "Resource") -> Response:
        """
        Create a not found error response
        
        Args:
            resource: Name of the resource that was not found
            
        Returns:
            Response: DRF Response object with 404 status
        """
        return Response({
            'error': {
                'type': 'NotFound',
                'code': 'not_found',
                'message': f"{resource} not found",
                'details': {}
            }
        }, status=status.HTTP_404_NOT_FOUND)
    
    @staticmethod
    def forbidden(message: str = "Permission denied") -> Response:
        """
        Create a forbidden error response
        
        Args:
            message: Permission error message
            
        Returns:
            Response: DRF Response object with 403 status
        """
        return Response({
            'error': {
                'type': 'PermissionDenied',
                'code': 'permission_denied',
                'message': message,
                'details': {}
            }
        }, status=status.HTTP_403_FORBIDDEN)
    
    @staticmethod
    def unauthorized(message: str = "Authentication required") -> Response:
        """
        Create an unauthorized error response
        
        Args:
            message: Authentication error message
            
        Returns:
            Response: DRF Response object with 401 status
        """
        return Response({
            'error': {
                'type': 'Unauthorized',
                'code': 'authentication_required',
                'message': message,
                'details': {}
            }
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    @staticmethod
    def quota_exceeded(
        required_mb: float,
        available_mb: float,
        used_mb: float,
        total_mb: float,
        message: str = None
    ) -> Response:
        """
        Create a quota exceeded error response
        
        Args:
            required_mb: Required storage in MB
            available_mb: Available quota in MB
            used_mb: Used quota in MB
            total_mb: Total quota in MB
            message: Custom error message
            
        Returns:
            Response: DRF Response object with 413 status
        """
        if not message:
            message = f"Cannot upload file: would exceed quota by {required_mb - available_mb:.2f}MB"
            
        return Response({
            'error': {
                'type': 'QuotaExceededError',
                'code': 'quota_exceeded',
                'message': message,
                'details': {
                    'required_mb': required_mb,
                    'available_mb': available_mb,
                    'used_mb': used_mb,
                    'total_mb': total_mb
                }
            }
        }, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
    
    @staticmethod
    def rate_limited(limit: int = 100, window: str = "1 minute", retry_after: int = 60) -> Response:
        """
        Create a rate limited error response
        
        Args:
            limit: Request limit
            window: Time window
            retry_after: Retry after seconds
            
        Returns:
            Response: DRF Response object with 429 status
        """
        return Response({
            'error': {
                'type': 'RateLimitExceeded',
                'code': 'rate_limit_exceeded',
                'message': 'Too many requests. Please try again later.',
                'details': {
                    'limit': limit,
                    'window': window,
                    'retry_after': retry_after
                }
            }
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)


class PaginatedResponse:
    """
    Helper class for creating paginated responses
    """
    
    @staticmethod
    def paginate(
        queryset, 
        paginator, 
        serializer_class,
        request,
        message: str = None
    ) -> Response:
        """
        Create a paginated response
        
        Args:
            queryset: Django queryset to paginate
            paginator: DRF paginator instance
            serializer_class: Serializer class to use
            request: Request object
            message: Optional message
            
        Returns:
            Response: Paginated response
        """
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = serializer_class(page, many=True, context={'request': request})
            response_data = paginator.get_paginated_response(serializer.data).data
            
            if message:
                response_data['message'] = message
                
            return Response(response_data)
        
        # If pagination is not needed
        serializer = serializer_class(queryset, many=True, context={'request': request})
        response_data = {
            'results': serializer.data,
            'count': len(serializer.data)
        }
        
        if message:
            response_data['message'] = message
            
        return Response(response_data)


class TaskResponse:
    """
    Helper class for creating task-related responses
    """
    
    @staticmethod
    def task_started(task_id: str, resource_id: Any = None, message: str = None) -> Response:
        """
        Create a response for started background task
        
        Args:
            task_id: Celery task ID
            resource_id: ID of the resource being processed
            message: Custom message
            
        Returns:
            Response: Task started response with 202 status
        """
        data = {'task_id': task_id}
        if resource_id is not None:
            data['resource_id'] = resource_id
            
        return APIResponse.accepted(
            data=data,
            message=message or "Task started successfully"
        )
    
    @staticmethod
    def bulk_task_started(task_ids: list, resource_count: int, message: str = None) -> Response:
        """
        Create a response for bulk background tasks
        
        Args:
            task_ids: List of Celery task IDs
            resource_count: Number of resources being processed
            message: Custom message
            
        Returns:
            Response: Bulk task started response with 202 status
        """
        data = {
            'task_ids': task_ids,
            'task_count': len(task_ids),
            'resource_count': resource_count
        }
        
        return APIResponse.accepted(
            data=data,
            message=message or f"Started {len(task_ids)} tasks for {resource_count} resources"
        )