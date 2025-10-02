"""
Policy document processor for loading and validating IAM policies.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import boto3
from botocore.exceptions import ClientError

from .config import CONFIG, POLICY_NAME_MAPPING
from .error_handling import ErrorHandler, PolicyException, ValidationException
from .data_models import ErrorResponse

logger = logging.getLogger(__name__)


class PolicyDocumentProcessor:
    """Handles loading, validation, and processing of IAM policy documents."""
    
    def __init__(self, policy_directory: Optional[str] = None):
        """Initialize the policy processor.
        
        Args:
            policy_directory: Path to directory containing policy JSON files.
                            Defaults to CONFIG['policy_directory'].
        """
        self.policy_directory = Path(policy_directory or CONFIG['policy_directory'])
        self.iam_client = boto3.client('iam', region_name=CONFIG['aws_region'])
        
    def load_policy_files(self) -> List[Dict]:
        """Load all policy files from the configured directory.
        
        Returns:
            List of policy documents with metadata.
            
        Raises:
            PolicyException: If policy files cannot be loaded or parsed.
        """
        policies = []
        
        if not self.policy_directory.exists():
            raise PolicyException(
                f"Policy directory does not exist: {self.policy_directory}",
                policy_name="directory_check"
            )
        
        for policy_file in CONFIG['policy_files']:
            policy_path = self.policy_directory / policy_file
            
            if not policy_path.exists():
                raise PolicyException(
                    f"Required policy file not found: {policy_file}",
                    policy_name=policy_file
                )
            
            try:
                with open(policy_path, 'r', encoding='utf-8') as f:
                    policy_content = json.load(f)
                
                # Validate basic structure
                if not isinstance(policy_content, dict):
                    raise PolicyException(
                        f"Policy file must contain a JSON object: {policy_file}",
                        policy_name=policy_file
                    )
                
                if 'Version' not in policy_content or 'Statement' not in policy_content:
                    raise PolicyException(
                        f"Policy file missing required fields (Version, Statement): {policy_file}",
                        policy_name=policy_file
                    )
                
                # Add metadata
                policy_info = {
                    'file_name': policy_file,
                    'file_path': str(policy_path),
                    'policy_document': policy_content,
                    'cloudformation_name': POLICY_NAME_MAPPING.get(policy_file, policy_file.replace('.json', ''))
                }
                
                policies.append(policy_info)
                logger.info(f"Successfully loaded policy: {policy_file}")
                
            except json.JSONDecodeError as e:
                raise PolicyException(
                    f"Invalid JSON in policy file: {policy_file}",
                    policy_name=policy_file,
                    policy_content=f"JSON error: {str(e)}"
                )
            except Exception as e:
                raise PolicyException(
                    f"Failed to load policy file: {policy_file}",
                    policy_name=policy_file,
                    policy_content=str(e)
                )
        
        logger.info(f"Successfully loaded {len(policies)} policy files")
        return policies
    
    def validate_policy_syntax(self, policy: Dict) -> bool:
        """Validate IAM policy syntax using AWS IAM API.
        
        Args:
            policy: Policy document to validate.
            
        Returns:
            True if policy is valid.
            
        Raises:
            ValidationException: If policy syntax is invalid.
        """
        try:
            # Use AWS IAM simulate_policy API for validation
            policy_json = json.dumps(policy['policy_document'])
            
            # Check policy size
            if len(policy_json) > CONFIG['max_policy_size']:
                raise ValidationException(
                    f"Policy size ({len(policy_json)} bytes) exceeds maximum ({CONFIG['max_policy_size']} bytes)",
                    error_code="POLICY_TOO_LARGE"
                )
            
            # Validate using AWS IAM policy simulator (dry run)
            try:
                # This is a basic validation - AWS will validate syntax when we try to attach
                response = self.iam_client.simulate_principal_policy(
                    PolicySourceArn=f"arn:aws:iam::{boto3.Session().get_credentials().access_key}:user/test",
                    ActionNames=['sts:GetCallerIdentity'],  # Simple action for validation
                    PolicyInputList=[policy_json]
                )
                logger.debug(f"Policy validation successful for {policy['file_name']}")
                return True
                
            except ClientError as e:
                # If simulate fails due to permissions, try basic JSON validation
                if e.response['Error']['Code'] in ['AccessDenied', 'InvalidUserID.NotFound']:
                    logger.warning(f"Cannot use policy simulator, falling back to basic validation: {e}")
                    return self._basic_policy_validation(policy['policy_document'])
                else:
                    raise ValidationException(
                        f"Policy validation failed: {e.response['Error']['Message']}",
                        error_code=e.response['Error']['Code']
                    )
                    
        except Exception as e:
            if isinstance(e, ValidationException):
                raise
            raise ValidationException(
                f"Policy validation error: {str(e)}",
                error_code="VALIDATION_ERROR"
            )
    
    def _basic_policy_validation(self, policy_doc: Dict) -> bool:
        """Perform basic policy validation without AWS API.
        
        Args:
            policy_doc: Policy document to validate.
            
        Returns:
            True if basic validation passes.
            
        Raises:
            ValidationException: If basic validation fails.
        """
        # Check required fields
        required_fields = ['Version', 'Statement']
        for field in required_fields:
            if field not in policy_doc:
                raise ValidationException(
                    f"Policy missing required field: {field}",
                    error_code="MISSING_REQUIRED_FIELD"
                )
        
        # Validate version
        if policy_doc['Version'] not in ['2012-10-17', '2008-10-17']:
            raise ValidationException(
                f"Invalid policy version: {policy_doc['Version']}",
                error_code="INVALID_VERSION"
            )
        
        # Validate statements
        statements = policy_doc['Statement']
        if not isinstance(statements, list):
            statements = [statements]
        
        for i, statement in enumerate(statements):
            if not isinstance(statement, dict):
                raise ValidationException(
                    f"Statement {i} must be an object",
                    error_code="INVALID_STATEMENT"
                )
            
            # Check required statement fields
            if 'Effect' not in statement:
                raise ValidationException(
                    f"Statement {i} missing Effect field",
                    error_code="MISSING_EFFECT"
                )
            
            if statement['Effect'] not in ['Allow', 'Deny']:
                raise ValidationException(
                    f"Statement {i} has invalid Effect: {statement['Effect']}",
                    error_code="INVALID_EFFECT"
                )
        
        return True
    
    def convert_to_inline_policy(self, policy: Dict, name: str) -> Dict:
        """Convert policy document to CloudFormation inline policy format.
        
        Args:
            policy: Policy information including document.
            name: Name for the inline policy.
            
        Returns:
            CloudFormation inline policy object.
        """
        return {
            'PolicyName': name,
            'PolicyDocument': policy['policy_document']
        }
    
    def get_policy_summary(self, policies: List[Dict]) -> Dict:
        """Get summary information about loaded policies.
        
        Args:
            policies: List of policy information.
            
        Returns:
            Summary dictionary with policy statistics.
        """
        total_size = 0
        action_counts = {}
        
        for policy in policies:
            policy_json = json.dumps(policy['policy_document'])
            total_size += len(policy_json)
            
            # Count actions in policy
            statements = policy['policy_document'].get('Statement', [])
            if not isinstance(statements, list):
                statements = [statements]
            
            for statement in statements:
                actions = statement.get('Action', [])
                if isinstance(actions, str):
                    actions = [actions]
                
                for action in actions:
                    service = action.split(':')[0] if ':' in action else 'unknown'
                    action_counts[service] = action_counts.get(service, 0) + 1
        
        return {
            'total_policies': len(policies),
            'total_size_bytes': total_size,
            'services_used': list(action_counts.keys()),
            'action_counts_by_service': action_counts,
            'policy_files': [p['file_name'] for p in policies]
        }