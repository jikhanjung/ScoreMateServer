"""
Tests for standardized error handling system
"""
from django.test import TestCase
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch

from core.models import User
from core.exceptions import (
    ScoreMateError, ValidationError, QuotaExceededError,
    FileProcessingError, S3Error, TaskError,
    PermissionDeniedError, NotFoundError,
    custom_exception_handler, handle_quota_check,
    handle_file_validation, handle_model_validation
)
from scores.models import Score
from .factories import UserFactory


class CustomExceptionsTest(TestCase):
    """Test custom exception classes"""
    
    def test_base_scoremate_error(self):
        """Test base ScoreMateError"""
        error = ScoreMateError()
        self.assertEqual(str(error), "An error occurred")
        self.assertEqual(error.code, "error")
        self.assertEqual(error.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Test custom parameters
        error = ScoreMateError(
            message="Custom error",
            code="custom_code",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={'key': 'value'}
        )
        self.assertEqual(str(error), "Custom error")
        self.assertEqual(error.code, "custom_code")
        self.assertEqual(error.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(error.details, {'key': 'value'})
    
    def test_validation_error(self):
        """Test ValidationError"""
        error = ValidationError("Invalid input")
        self.assertEqual(str(error), "Invalid input")
        self.assertEqual(error.code, "validation_error")
        self.assertEqual(error.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_quota_exceeded_error(self):
        """Test QuotaExceededError"""
        error = QuotaExceededError()
        self.assertEqual(error.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        self.assertIn("quota", str(error).lower())
    
    def test_file_processing_error(self):
        """Test FileProcessingError"""
        error = FileProcessingError("PDF parsing failed")
        self.assertEqual(str(error), "PDF parsing failed")
        self.assertEqual(error.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
    
    def test_permission_denied_error(self):
        """Test PermissionDeniedError"""
        error = PermissionDeniedError()
        self.assertEqual(error.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_not_found_error(self):
        """Test NotFoundError"""
        error = NotFoundError("Score not found")
        self.assertEqual(str(error), "Score not found")
        self.assertEqual(error.status_code, status.HTTP_404_NOT_FOUND)


class ExceptionHandlerTest(APITestCase):
    """Test custom exception handler"""
    
    def setUp(self):
        """Set up test data"""
        self.user = UserFactory()
        self.client = APIClient()
        
        # Authenticate user
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    def test_scoremate_error_handling(self):
        """Test handling of ScoreMate custom errors"""
        # This would be tested by triggering actual API endpoints
        # that raise ScoreMateError exceptions
        
        # Try to access non-existent score
        response = self.client.get('/api/v1/scores/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['type'], 'NotFound')
        self.assertEqual(response.data['error']['code'], 'not_found')
    
    def test_validation_error_handling(self):
        """Test handling of validation errors"""
        # Try to create score with invalid data
        invalid_data = {
            'title': '',  # Empty title should fail validation
            'file_size_mb': -1  # Negative size should fail
        }
        
        response = self.client.post('/api/v1/scores/', invalid_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_authentication_error_handling(self):
        """Test handling of authentication errors"""
        # Remove authentication
        self.client.credentials()
        
        response = self.client.get('/api/v1/scores/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
    
    def test_permission_error_handling(self):
        """Test handling of permission errors"""
        # Create another user's score
        other_user = UserFactory()
        other_score = Score.objects.create(
            user=other_user,
            title='Other User Score',
            s3_key='other.pdf',
            size_bytes=1024000
        )
        
        # Try to access it
        response = self.client.get(f'/api/v1/scores/{other_score.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)


class HelperFunctionsTest(TestCase):
    """Test error handling helper functions"""
    
    def setUp(self):
        """Set up test data"""
        self.user = UserFactory(
            total_quota_mb=100,
            used_quota_mb=50
        )
    
    def test_quota_check_success(self):
        """Test successful quota check"""
        # Should not raise exception for allowed upload
        try:
            handle_quota_check(self.user, 30)  # 30MB upload, 50MB available
        except QuotaExceededError:
            self.fail("Should not raise exception for valid quota")
    
    def test_quota_check_failure(self):
        """Test quota check failure"""
        with self.assertRaises(QuotaExceededError) as cm:
            handle_quota_check(self.user, 60)  # 60MB upload, only 50MB available
        
        error = cm.exception
        self.assertIn('quota', str(error).lower())
        self.assertEqual(error.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        
        # Check details
        details = error.details
        self.assertEqual(details['required_mb'], 60)
        self.assertEqual(details['available_mb'], 50)
        self.assertEqual(details['used_mb'], 50)
        self.assertEqual(details['total_mb'], 100)
    
    def test_file_validation_success(self):
        """Test successful file validation"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        # Create mock file
        file_obj = SimpleUploadedFile(
            "test.pdf",
            b"file_content",
            content_type="application/pdf"
        )
        file_obj.size = 1024 * 1024  # 1MB
        
        # Should not raise exception
        try:
            handle_file_validation(
                file_obj,
                allowed_types=['application/pdf'],
                max_size_mb=5
            )
        except ValidationError:
            self.fail("Should not raise exception for valid file")
    
    def test_file_validation_type_error(self):
        """Test file validation type error"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        file_obj = SimpleUploadedFile(
            "test.txt",
            b"file_content",
            content_type="text/plain"
        )
        
        with self.assertRaises(ValidationError) as cm:
            handle_file_validation(
                file_obj,
                allowed_types=['application/pdf']
            )
        
        error = cm.exception
        self.assertIn('not allowed', str(error))
        self.assertEqual(error.details['received_type'], 'text/plain')
    
    def test_file_validation_size_error(self):
        """Test file validation size error"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        file_obj = SimpleUploadedFile(
            "test.pdf",
            b"file_content",
            content_type="application/pdf"
        )
        file_obj.size = 10 * 1024 * 1024  # 10MB
        
        with self.assertRaises(ValidationError) as cm:
            handle_file_validation(
                file_obj,
                max_size_mb=5
            )
        
        error = cm.exception
        self.assertIn('exceeds maximum', str(error))
        self.assertEqual(error.details['max_size_mb'], 5)
    
    def test_model_validation_success(self):
        """Test successful model validation"""
        user = User(
            username='testuser',
            email='test@example.com'
        )
        
        # Should not raise exception for valid model
        try:
            handle_model_validation(user)
        except ValidationError:
            self.fail("Should not raise exception for valid model")
    
    def test_model_validation_error(self):
        """Test model validation error"""
        # Create invalid user (missing required fields)
        user = User()
        
        with self.assertRaises(ValidationError) as cm:
            handle_model_validation(user)
        
        error = cm.exception
        self.assertIn('validation failed', str(error).lower())
        self.assertIn('details', str(error.details))


class APIErrorResponseTest(APITestCase):
    """Test API error response format consistency"""
    
    def setUp(self):
        """Set up test data"""
        self.user = UserFactory()
        self.client = APIClient()
        
        # Authenticate user
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    def test_error_response_format(self):
        """Test that all error responses follow consistent format"""
        # Test 404 error
        response = self.client.get('/api/v1/scores/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        error_data = response.data
        self.assertIn('error', error_data)
        
        error = error_data['error']
        self.assertIn('type', error)
        self.assertIn('code', error)
        self.assertIn('message', error)
        self.assertIn('details', error)
        
        # Verify error structure
        self.assertEqual(error['type'], 'NotFound')
        self.assertEqual(error['code'], 'not_found')
        self.assertIsInstance(error['message'], str)
        self.assertIsInstance(error['details'], dict)
    
    def test_validation_error_format(self):
        """Test validation error response format"""
        # Try to create score with invalid data
        invalid_data = {'title': ''}
        
        response = self.client.post('/api/v1/scores/', invalid_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        error_data = response.data
        self.assertIn('error', error_data)
        
        error = error_data['error']
        self.assertEqual(error['type'], 'ValidationError')
        self.assertEqual(error['code'], 'validation_error')
        self.assertIn('details', error)
        
        # Details should contain field-specific errors
        self.assertIsInstance(error['details'], dict)
    
    def test_authentication_error_format(self):
        """Test authentication error response format"""
        # Remove authentication
        self.client.credentials()
        
        response = self.client.get('/api/v1/scores/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        error_data = response.data
        self.assertIn('error', error_data)
        
        error = error_data['error']
        self.assertIn('type', error)
        self.assertIn('code', error)
        self.assertIn('message', error)


class MiddlewareTest(APITestCase):
    """Test custom middleware functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = UserFactory()
        self.client = APIClient()
    
    def test_security_headers(self):
        """Test that security headers are added"""
        # Authenticate user
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        response = self.client.get('/api/v1/scores/')
        
        # Check security headers
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        self.assertEqual(response['X-XSS-Protection'], '1; mode=block')
        self.assertEqual(response['Referrer-Policy'], 'strict-origin-when-cross-origin')
    
    def test_quota_check_middleware(self):
        """Test quota check middleware"""
        # Set user to nearly full quota
        self.user.used_quota_mb = 95
        self.user.total_quota_mb = 100
        self.user.save()
        
        # Authenticate user
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        # Try to upload large file (would be caught by middleware if file upload endpoint exists)
        # This is more of a conceptual test since we don't have actual file upload in this test
        
        # Test accessing quota info
        response = self.client.get('/api/v1/dashboard/quota_details/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        quota_data = response.data['quota_summary']
        self.assertEqual(quota_data['percentage_used'], 95.0)


class ErrorLoggingTest(TestCase):
    """Test error logging functionality"""
    
    def test_error_logging_configuration(self):
        """Test that error logging is properly configured"""
        from django.conf import settings
        
        # Check that logging is configured
        self.assertIn('LOGGING', dir(settings))
        logging_config = settings.LOGGING
        
        # Check that we have error handlers
        self.assertIn('handlers', logging_config)
        handlers = logging_config['handlers']
        
        # Should have console and file handlers
        self.assertIn('console', handlers)
        self.assertIn('file', handlers)
        self.assertIn('error_file', handlers)
        
        # Check loggers configuration
        self.assertIn('loggers', logging_config)
        loggers = logging_config['loggers']
        
        # Should have core logger configured
        self.assertIn('core', loggers)
        core_logger = loggers['core']
        self.assertIn('error_file', core_logger['handlers'])
    
    @patch('core.exceptions.logger')
    def test_exception_handler_logging(self, mock_logger):
        """Test that exception handler logs errors"""
        from django.http import HttpRequest
        from core.exceptions import custom_exception_handler
        
        # Create mock request and exception
        request = HttpRequest()
        request.path = '/test/path/'
        request.user = self.user = UserFactory()
        
        context = {'request': request}
        exception = ScoreMateError("Test error")
        
        # Call exception handler
        response = custom_exception_handler(exception, context)
        
        # Verify logging was called
        mock_logger.error.assert_called_once()
        log_call_args = mock_logger.error.call_args[0]
        self.assertIn('API Exception', log_call_args[0])
        self.assertIn('Test error', log_call_args[0])