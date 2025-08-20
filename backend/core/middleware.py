"""
Custom middleware for ScoreMateServer
"""
import json
import time
import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from rest_framework import status

logger = logging.getLogger(__name__)


class CorsMiddleware(MiddlewareMixin):
    """
    Simple CORS middleware for development
    """
    
    def process_response(self, request, response):
        """Add CORS headers to all responses"""
        # Allow requests from localhost:3000 (frontend)
        response['Access-Control-Allow-Origin'] = 'http://localhost:3000'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, Accept'
        response['Access-Control-Allow-Credentials'] = 'true'
        response['Access-Control-Max-Age'] = '3600'
        
        return response
    
    def process_request(self, request):
        """Handle preflight OPTIONS requests"""
        if request.method == 'OPTIONS':
            response = JsonResponse({'status': 'ok'})
            response['Access-Control-Allow-Origin'] = 'http://localhost:3000'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, Accept'
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Access-Control-Max-Age'] = '3600'
            return response
        return None


class APILoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log API requests and responses for monitoring and debugging
    """
    
    def process_request(self, request):
        """Log incoming requests"""
        request._start_time = time.time()
        
        # Skip logging for certain paths
        skip_paths = ['/admin/', '/static/', '/media/', '/favicon.ico']
        if any(request.path.startswith(path) for path in skip_paths):
            return None
        
        # Log request details
        user_id = getattr(request.user, 'id', 'anonymous') if hasattr(request, 'user') else 'unknown'
        logger.info(
            f"API Request: {request.method} {request.path} "
            f"[User: {user_id}, IP: {self.get_client_ip(request)}]"
        )
        
        return None
    
    def process_response(self, request, response):
        """Log outgoing responses"""
        # Skip logging for certain paths
        skip_paths = ['/admin/', '/static/', '/media/', '/favicon.ico']
        if any(request.path.startswith(path) for path in skip_paths):
            return response
        
        # Calculate response time
        response_time = 0
        if hasattr(request, '_start_time'):
            response_time = (time.time() - request._start_time) * 1000  # Convert to milliseconds
        
        # Log response details
        user_id = getattr(request.user, 'id', 'anonymous') if hasattr(request, 'user') else 'unknown'
        logger.info(
            f"API Response: {request.method} {request.path} "
            f"[Status: {response.status_code}, User: {user_id}, "
            f"Time: {response_time:.2f}ms]"
        )
        
        return response
    
    def process_exception(self, request, exception):
        """Log unhandled exceptions"""
        user_id = getattr(request.user, 'id', 'anonymous') if hasattr(request, 'user') else 'unknown'
        logger.error(
            f"Unhandled Exception: {request.method} {request.path} "
            f"[User: {user_id}, Exception: {exception.__class__.__name__}: {str(exception)}]",
            exc_info=True
        )
        return None
    
    def get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add security headers to responses
    """
    
    def process_response(self, request, response):
        """Add security headers to response"""
        # Only add security headers to API responses
        if request.path.startswith('/api/'):
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            
            # Add CORS headers if needed (basic implementation)
            if request.method == 'OPTIONS':
                response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
                response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
                response['Access-Control-Max-Age'] = '3600'
        
        return response


class QuotaCheckMiddleware(MiddlewareMixin):
    """
    Middleware to check user quota for file upload operations
    """
    
    def process_request(self, request):
        """Check quota before processing file uploads"""
        # Only check for authenticated users and file upload endpoints
        if (hasattr(request, 'user') and 
            request.user.is_authenticated and 
            request.method in ['POST', 'PUT', 'PATCH'] and
            '/api/v1/files/' in request.path):
            
            # Check if request contains file upload
            if hasattr(request, 'FILES') and request.FILES:
                total_size = sum(f.size for f in request.FILES.values())
                total_size_mb = total_size / (1024 * 1024)
                
                # Check quota
                if request.user.available_quota_mb < total_size_mb:
                    return JsonResponse({
                        'error': {
                            'type': 'QuotaExceededError',
                            'code': 'quota_exceeded',
                            'message': f'Upload would exceed quota by {total_size_mb - request.user.available_quota_mb:.2f}MB',
                            'details': {
                                'required_mb': total_size_mb,
                                'available_mb': request.user.available_quota_mb,
                                'used_mb': request.user.used_quota_mb,
                                'total_mb': request.user.total_quota_mb
                            }
                        }
                    }, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        
        return None


class RateLimitingMiddleware(MiddlewareMixin):
    """
    Basic rate limiting middleware (for demonstration)
    In production, use Redis-based rate limiting
    """
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.requests = {}  # Simple in-memory store (not suitable for production)
    
    def process_request(self, request):
        """Basic rate limiting check"""
        # Skip for development or if user is staff
        if hasattr(request, 'user') and request.user.is_staff:
            return None
        
        client_ip = self.get_client_ip(request)
        current_time = int(time.time())
        window_start = current_time - 60  # 1-minute window
        
        # Clean old requests
        if client_ip in self.requests:
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip] 
                if req_time > window_start
            ]
        else:
            self.requests[client_ip] = []
        
        # Check rate limit (100 requests per minute)
        if len(self.requests[client_ip]) >= 100:
            return JsonResponse({
                'error': {
                    'type': 'RateLimitExceeded',
                    'code': 'rate_limit_exceeded',
                    'message': 'Too many requests. Please try again later.',
                    'details': {
                        'limit': 100,
                        'window': '1 minute',
                        'retry_after': 60
                    }
                }
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Add current request
        self.requests[client_ip].append(current_time)
        return None
    
    def get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip