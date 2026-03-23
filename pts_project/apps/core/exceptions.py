"""
Custom exception handling for PTS API.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler for consistent API error responses.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # Log the exception
    logger.error(
        f"Exception occurred: {type(exc).__name__}: {str(exc)}",
        extra={
            'view': context.get('view').__class__.__name__ if context.get('view') else None,
            'request_path': context.get('request').path if context.get('request') else None,
        }
    )
    
    if response is not None:
        # Standardize error response format
        custom_response_data = {
            'success': False,
            'error': {
                'code': response.status_code,
                'message': get_error_message(response.data),
                'details': response.data if isinstance(response.data, dict) else {'detail': response.data}
            }
        }
        response.data = custom_response_data
        return response
    
    # Handle Django ValidationError
    if isinstance(exc, DjangoValidationError):
        return Response(
            {
                'success': False,
                'error': {
                    'code': status.HTTP_400_BAD_REQUEST,
                    'message': 'Validation error',
                    'details': exc.message_dict if hasattr(exc, 'message_dict') else {'detail': exc.messages}
                }
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Handle unexpected exceptions
    return Response(
        {
            'success': False,
            'error': {
                'code': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': 'An unexpected error occurred',
                'details': {'detail': str(exc) if logger.isEnabledFor(logging.DEBUG) else 'Internal server error'}
            }
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def get_error_message(data):
    """Extract a human-readable error message from response data."""
    if isinstance(data, dict):
        if 'detail' in data:
            return str(data['detail'])
        # Get first error message
        for key, value in data.items():
            if isinstance(value, list) and value:
                return f"{key}: {value[0]}"
            elif isinstance(value, str):
                return f"{key}: {value}"
    elif isinstance(data, list) and data:
        return str(data[0])
    return 'An error occurred'


class PTSException(Exception):
    """Base exception for PTS-specific errors."""
    default_message = 'A PTS error occurred'
    default_code = 'pts_error'
    
    def __init__(self, message=None, code=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        super().__init__(self.message)


class WorkflowException(PTSException):
    """Exception for workflow-related errors."""
    default_message = 'Workflow transition error'
    default_code = 'workflow_error'


class DeadlineException(PTSException):
    """Exception for deadline-related errors."""
    default_message = 'Deadline violation'
    default_code = 'deadline_error'


class PermissionDeniedException(PTSException):
    """Exception for permission-related errors."""
    default_message = 'Permission denied'
    default_code = 'permission_denied'
