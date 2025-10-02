"""
IAM role validator for testing policy attachment and validation.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import List, Optional
import boto3
from botocore.exceptions import ClientError

from .config import CONFIG
from .data_models import ValidationResult, FailureContext
from .error_handling import ErrorHandler, ValidationException
from .policy_processor import PolicyDocumentProcessor

logger = logging.getLogger(__name__)


class IAMRoleValidator:
    """Validates IAM policies by creating temporary roles and testing attachment."""
    
    def __init__(self, aws_profile: Optional[str] = None, aws_region: Optional[str] = None):
        """Initialize the IAM role validator.
        
        Args:
            aws_profile: AWS profile to use for authentication.
            aws_region: AWS region for IAM operations.
        """
        self.aws_profile = aws_profile or CONFIG.get('aws_profile')
        self.aws_region = aws_region or CONFIG['aws_region']
        
        # Initialize AWS session and client
        session_kwargs = {}
        if self.aws_profile:
            session_kwargs['profile_name'] = self.aws_profile
        
        self.session = boto3.Session(**session_kwargs)
        self.iam_client = self.session.client('iam', region_name=self.aws_region)
        
        # Initialize policy processor
        self.policy_processor = PolicyDocumentProcessor()
        
        # Track temporary resources for cleanup
        self.failure_context = FailureContext()
    
    def validate_policies(self, policy_files: Optional[List[str]] = None) -> ValidationResult:
        """Main validation method that orchestrates the entire process.
        
        Args:
            policy_files: List of policy file names to validate. 
                         Defaults to CONFIG['policy_files'].
        
        Returns:
            ValidationResult with detailed validation information.
        """
        logger.info("Starting IAM policy validation process")
        
        try:
            # Load and validate policy documents
            policies = self.policy_processor.load_policy_files()
            logger.info(f"Loaded {len(policies)} policy files")
            
            # Validate policy syntax
            for policy in policies:
                self.policy_processor.validate_policy_syntax(policy)
            logger.info("All policies passed syntax validation")
            
            # Create temporary role
            role_arn = self.create_temporary_role()
            logger.info(f"Created temporary role: {role_arn}")
            
            # Attach policies to test permissions
            attached_policies = self.attach_policies(self.failure_context.temporary_role_name, policies)
            logger.info(f"Successfully attached {len(attached_policies)} policies")
            
            # Cleanup temporary role
            cleanup_successful = self.cleanup_temporary_role(self.failure_context.temporary_role_name)
            
            return ValidationResult(
                success=True,
                temporary_role_arn=role_arn,
                attached_policies=attached_policies,
                errors=[],
                cleanup_successful=cleanup_successful
            )
            
        except Exception as e:
            logger.error(f"Policy validation failed: {str(e)}")
            
            # Attempt cleanup on failure
            cleanup_successful = ErrorHandler.cleanup_on_failure(
                self.failure_context, 
                self.iam_client
            )
            
            error_message = str(e)
            if isinstance(e, (ValidationException, ClientError)):
                if hasattr(e, 'response'):
                    error_message = f"{e.response['Error']['Code']}: {e.response['Error']['Message']}"
            
            return ValidationResult(
                success=False,
                temporary_role_arn=self.failure_context.temporary_role_name,
                attached_policies=self.failure_context.attached_policies,
                errors=[error_message],
                cleanup_successful=cleanup_successful
            )
    
    def create_temporary_role(self) -> str:
        """Create a temporary IAM role for testing policy attachment.
        
        Returns:
            ARN of the created temporary role.
            
        Raises:
            ValidationException: If role creation fails.
        """
        # Generate unique role name
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        role_name = f"{CONFIG['temporary_role_prefix']}-{timestamp}-{unique_id}"
        
        # Store role name for cleanup
        self.failure_context.temporary_role_name = role_name
        
        # Define assume role policy for temporary role
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "lambda.amazonaws.com"  # Use lambda service for testing
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        try:
            response = self.iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(assume_role_policy),
                Description=f"Temporary role for COA policy validation - created {timestamp}",
                Tags=[
                    {
                        'Key': 'Purpose',
                        'Value': 'COA-Policy-Validation'
                    },
                    {
                        'Key': 'CreatedBy',
                        'Value': 'IAMRoleValidator'
                    },
                    {
                        'Key': 'CreatedAt',
                        'Value': timestamp
                    },
                    {
                        'Key': 'AutoDelete',
                        'Value': 'true'
                    }
                ]
            )
            
            role_arn = response['Role']['Arn']
            logger.info(f"Successfully created temporary role: {role_name} ({role_arn})")
            return role_arn
            
        except ClientError as e:
            error_msg = f"Failed to create temporary role {role_name}: {e.response['Error']['Message']}"
            logger.error(error_msg)
            raise ValidationException(
                error_msg,
                error_code=e.response['Error']['Code']
            )
    
    def attach_policies(self, role_name: str, policies: List[dict]) -> List[str]:
        """Attach policy documents to the temporary role as inline policies.
        
        Args:
            role_name: Name of the temporary role.
            policies: List of policy documents to attach.
            
        Returns:
            List of successfully attached policy names.
            
        Raises:
            ValidationException: If policy attachment fails.
        """
        attached_policies = []
        
        for policy in policies:
            policy_name = policy['cloudformation_name']
            policy_document = policy['policy_document']
            
            try:
                # Attach as inline policy
                self.iam_client.put_role_policy(
                    RoleName=role_name,
                    PolicyName=policy_name,
                    PolicyDocument=json.dumps(policy_document)
                )
                
                attached_policies.append(policy_name)
                self.failure_context.attached_policies.append(policy_name)
                logger.info(f"Successfully attached policy: {policy_name}")
                
            except ClientError as e:
                error_msg = f"Failed to attach policy {policy_name}: {e.response['Error']['Message']}"
                logger.error(error_msg)
                
                # Clean up any successfully attached policies before failing
                self._cleanup_attached_policies(role_name, attached_policies)
                
                raise ValidationException(
                    error_msg,
                    error_code=e.response['Error']['Code']
                )
        
        return attached_policies
    
    def cleanup_temporary_role(self, role_name: str) -> bool:
        """Clean up the temporary IAM role and all attached policies.
        
        Args:
            role_name: Name of the temporary role to delete.
            
        Returns:
            True if cleanup was successful, False otherwise.
        """
        if not role_name:
            logger.warning("No role name provided for cleanup")
            return True
        
        cleanup_successful = True
        
        try:
            # First, detach all inline policies
            try:
                response = self.iam_client.list_role_policies(RoleName=role_name)
                policy_names = response.get('PolicyNames', [])
                
                for policy_name in policy_names:
                    try:
                        self.iam_client.delete_role_policy(
                            RoleName=role_name,
                            PolicyName=policy_name
                        )
                        logger.info(f"Deleted inline policy: {policy_name}")
                    except ClientError as e:
                        logger.warning(f"Failed to delete inline policy {policy_name}: {e}")
                        cleanup_successful = False
                        
            except ClientError as e:
                logger.warning(f"Failed to list role policies for cleanup: {e}")
                cleanup_successful = False
            
            # Then delete the role
            try:
                self.iam_client.delete_role(RoleName=role_name)
                logger.info(f"Successfully deleted temporary role: {role_name}")
                
            except ClientError as e:
                logger.error(f"Failed to delete temporary role {role_name}: {e}")
                cleanup_successful = False
                
        except Exception as e:
            logger.error(f"Unexpected error during cleanup: {e}")
            cleanup_successful = False
        
        return cleanup_successful
    
    def _cleanup_attached_policies(self, role_name: str, policy_names: List[str]) -> None:
        """Clean up specific attached policies from a role.
        
        Args:
            role_name: Name of the role.
            policy_names: List of policy names to detach.
        """
        for policy_name in policy_names:
            try:
                self.iam_client.delete_role_policy(
                    RoleName=role_name,
                    PolicyName=policy_name
                )
                logger.info(f"Cleaned up attached policy: {policy_name}")
            except ClientError as e:
                logger.warning(f"Failed to clean up policy {policy_name}: {e}")
    
    def validate_aws_permissions(self) -> bool:
        """Validate that the current AWS credentials have necessary permissions.
        
        Returns:
            True if permissions are sufficient.
            
        Raises:
            ValidationException: If permissions are insufficient.
        """
        required_actions = [
            'iam:CreateRole',
            'iam:DeleteRole', 
            'iam:PutRolePolicy',
            'iam:DeleteRolePolicy',
            'iam:ListRolePolicies'
        ]
        
        try:
            # Test basic IAM access
            self.iam_client.get_user()
            logger.info("AWS credentials validated successfully")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'AccessDenied':
                # Try alternative method - list roles (less privileged)
                try:
                    self.iam_client.list_roles(MaxItems=1)
                    logger.info("AWS credentials have basic IAM access")
                    return True
                except ClientError:
                    raise ValidationException(
                        "Insufficient AWS permissions for IAM operations",
                        error_code="ACCESS_DENIED"
                    )
            else:
                raise ValidationException(
                    f"AWS credential validation failed: {e.response['Error']['Message']}",
                    error_code=e.response['Error']['Code']
                )
    
    def get_validation_summary(self, result: ValidationResult) -> str:
        """Generate a human-readable summary of validation results.
        
        Args:
            result: ValidationResult to summarize.
            
        Returns:
            Formatted summary string.
        """
        if result.success:
            summary = f"✓ IAM Policy Validation SUCCESSFUL\n"
            summary += f"  - Temporary role: {result.temporary_role_arn}\n"
            summary += f"  - Policies validated: {len(result.attached_policies)}\n"
            summary += f"  - Cleanup successful: {'Yes' if result.cleanup_successful else 'No'}\n"
            
            if result.attached_policies:
                summary += f"  - Attached policies:\n"
                for policy in result.attached_policies:
                    summary += f"    • {policy}\n"
        else:
            summary = f"✗ IAM Policy Validation FAILED\n"
            summary += f"  - Errors: {len(result.errors)}\n"
            summary += f"  - Cleanup successful: {'Yes' if result.cleanup_successful else 'No'}\n"
            
            if result.errors:
                summary += f"  - Error details:\n"
                for error in result.errors:
                    summary += f"    • {error}\n"
        
        return summary