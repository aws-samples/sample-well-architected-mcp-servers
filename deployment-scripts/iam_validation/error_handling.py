"""
Error handling utilities for IAM validation and template updates.
"""

import logging
from typing import Optional
from botocore.exceptions import ClientError, BotoCoreError
from .data_models import ErrorResponse, FailureContext

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Centralized error handling for the IAM validation system."""
    
    @staticmethod
    def handle_aws_error(error: ClientError, context: str = "") -> ErrorResponse:
        """Handle AWS API errors with detailed information."""
        error_code = error.response.get('Error', {}).get('Code', 'Unknown')
        error_message = error.response.get('Error', {}).get('Message', str(error))
        
        logger.error(f"AWS API Error in {context}: {error_code} - {error_message}")
        
        return ErrorResponse(
            error_type="AWS_API_ERROR",
            error_code=error_code,
            message=error_message,
            details=f"Context: {context}" if context else None
        )
    
    @staticmethod
    def handle_file_error(error: Exception, file_path: str, operation: str) -> ErrorResponse:
        """Handle file system errors with path information."""
        logger.error(f"File {operation} error for {file_path}: {str(error)}")
        
        return ErrorResponse(
            error_type="FILE_ERROR",
            error_code=type(error).__name__,
            message=f"Failed to {operation} file: {file_path}",
            details=str(error)
        )
    
    @staticmethod
    def handle_validation_error(error: Exception, validation_type: str) -> ErrorResponse:
        """Handle validation errors with type information."""
        logger.error(f"Validation error in {validation_type}: {str(error)}")
        
        return ErrorResponse(
            error_type="VALIDATION_ERROR",
            error_code=type(error).__name__,
            message=f"Validation failed for {validation_type}",
            details=str(error)
        )
    
    @staticmethod
    def cleanup_on_failure(context: FailureContext, iam_client=None) -> bool:
        """Perform cleanup operations when failures occur."""
        cleanup_successful = True
        
        # Clean up temporary IAM role
        if context.temporary_role_name and iam_client:
            try:
                # First detach all policies
                for policy_name in context.attached_policies:
                    try:
                        iam_client.detach_role_policy(
                            RoleName=context.temporary_role_name,
                            PolicyArn=policy_name
                        )
                        logger.info(f"Detached policy {policy_name} from role {context.temporary_role_name}")
                    except ClientError as e:
                        logger.warning(f"Failed to detach policy {policy_name}: {e}")
                        cleanup_successful = False
                
                # Delete the role
                iam_client.delete_role(RoleName=context.temporary_role_name)
                logger.info(f"Successfully deleted temporary role: {context.temporary_role_name}")
                
            except ClientError as e:
                logger.error(f"Failed to delete temporary role {context.temporary_role_name}: {e}")
                cleanup_successful = False
        
        return cleanup_successful


class ValidationException(Exception):
    """Custom exception for validation errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[str] = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details


class TemplateException(Exception):
    """Custom exception for CloudFormation template errors."""
    
    def __init__(self, message: str, template_path: Optional[str] = None, line_number: Optional[int] = None):
        super().__init__(message)
        self.template_path = template_path
        self.line_number = line_number


class PolicyException(Exception):
    """Custom exception for policy-related errors."""
    
    def __init__(self, message: str, policy_name: Optional[str] = None, policy_content: Optional[str] = None):
        super().__init__(message)
        self.policy_name = policy_name
        self.policy_content = policy_content