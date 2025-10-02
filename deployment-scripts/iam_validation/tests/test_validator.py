"""
Unit tests for IAMRoleValidator.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from ..validator import IAMRoleValidator
from ..data_models import ValidationResult
from ..error_handling import ValidationException


class TestIAMRoleValidator:
    """Test cases for IAMRoleValidator class."""
    
    @pytest.fixture
    def mock_iam_client(self):
        """Mock IAM client for testing."""
        with patch('boto3.Session') as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            yield mock_client
    
    @pytest.fixture
    def validator(self, mock_iam_client):
        """Create IAMRoleValidator with mocked IAM client."""
        return IAMRoleValidator()
    
    @pytest.fixture
    def sample_policies(self):
        """Sample policy documents for testing."""
        return [
            {
                'file_name': 'test-policy-1.json',
                'cloudformation_name': 'TestPolicy1',
                'policy_document': {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Effect': 'Allow',
                            'Action': ['s3:GetObject'],
                            'Resource': '*'
                        }
                    ]
                }
            },
            {
                'file_name': 'test-policy-2.json',
                'cloudformation_name': 'TestPolicy2',
                'policy_document': {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Effect': 'Allow',
                            'Action': ['iam:GetUser'],
                            'Resource': '*'
                        }
                    ]
                }
            }
        ]
    
    def test_init_default_params(self):
        """Test initialization with default parameters."""
        with patch('boto3.Session'):
            validator = IAMRoleValidator()
            assert validator.aws_profile is None
            assert validator.aws_region == 'us-east-1'  # Default from CONFIG
    
    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        with patch('boto3.Session'):
            validator = IAMRoleValidator(aws_profile='test-profile', aws_region='us-west-2')
            assert validator.aws_profile == 'test-profile'
            assert validator.aws_region == 'us-west-2'
    
    @patch('deployment_scripts.iam_validation.validator.PolicyDocumentProcessor')
    def test_validate_policies_success(self, mock_processor_class, validator, mock_iam_client, sample_policies):
        """Test successful policy validation."""
        # Mock policy processor
        mock_processor = Mock()
        mock_processor_class.return_value = mock_processor
        mock_processor.load_policy_files.return_value = sample_policies
        mock_processor.validate_policy_syntax.return_value = True
        
        # Mock IAM operations
        mock_iam_client.create_role.return_value = {
            'Role': {'Arn': 'arn:aws:iam::123456789012:role/test-role'}
        }
        mock_iam_client.put_role_policy.return_value = {}
        mock_iam_client.list_role_policies.return_value = {'PolicyNames': ['TestPolicy1', 'TestPolicy2']}
        mock_iam_client.delete_role_policy.return_value = {}
        mock_iam_client.delete_role.return_value = {}
        
        result = validator.validate_policies()
        
        assert result.success is True
        assert result.temporary_role_arn == 'arn:aws:iam::123456789012:role/test-role'
        assert len(result.attached_policies) == 2
        assert result.cleanup_successful is True
        assert len(result.errors) == 0
    
    @patch('deployment_scripts.iam_validation.validator.PolicyDocumentProcessor')
    def test_validate_policies_policy_load_failure(self, mock_processor_class, validator, mock_iam_client):
        """Test policy validation with policy loading failure."""
        # Mock policy processor to raise exception
        mock_processor = Mock()
        mock_processor_class.return_value = mock_processor
        mock_processor.load_policy_files.side_effect = Exception("Failed to load policies")
        
        result = validator.validate_policies()
        
        assert result.success is False
        assert len(result.errors) == 1
        assert "Failed to load policies" in result.errors[0]
    
    def test_create_temporary_role_success(self, validator, mock_iam_client):
        """Test successful temporary role creation."""
        mock_iam_client.create_role.return_value = {
            'Role': {'Arn': 'arn:aws:iam::123456789012:role/coa-temp-validation-20240101-12345678'}
        }
        
        role_arn = validator.create_temporary_role()
        
        assert role_arn == 'arn:aws:iam::123456789012:role/coa-temp-validation-20240101-12345678'
        assert validator.failure_context.temporary_role_name is not None
        assert validator.failure_context.temporary_role_name.startswith('coa-temp-validation')
        
        # Verify create_role was called with correct parameters
        mock_iam_client.create_role.assert_called_once()
        call_args = mock_iam_client.create_role.call_args
        assert 'RoleName' in call_args.kwargs
        assert 'AssumeRolePolicyDocument' in call_args.kwargs
        assert 'Tags' in call_args.kwargs
    
    def test_create_temporary_role_failure(self, validator, mock_iam_client):
        """Test temporary role creation failure."""
        mock_iam_client.create_role.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'CreateRole'
        )
        
        with pytest.raises(ValidationException) as exc_info:
            validator.create_temporary_role()
        
        assert "Failed to create temporary role" in str(exc_info.value)
        assert exc_info.value.error_code == 'AccessDenied'
    
    def test_attach_policies_success(self, validator, mock_iam_client, sample_policies):
        """Test successful policy attachment."""
        mock_iam_client.put_role_policy.return_value = {}
        
        attached = validator.attach_policies('test-role', sample_policies)
        
        assert len(attached) == 2
        assert 'TestPolicy1' in attached
        assert 'TestPolicy2' in attached
        assert len(validator.failure_context.attached_policies) == 2
        
        # Verify put_role_policy was called for each policy
        assert mock_iam_client.put_role_policy.call_count == 2
    
    def test_attach_policies_partial_failure(self, validator, mock_iam_client, sample_policies):
        """Test policy attachment with partial failure."""
        # First policy succeeds, second fails
        mock_iam_client.put_role_policy.side_effect = [
            {},  # Success for first policy
            ClientError(
                {'Error': {'Code': 'InvalidPolicyDocument', 'Message': 'Invalid policy'}},
                'PutRolePolicy'
            )  # Failure for second policy
        ]
        mock_iam_client.delete_role_policy.return_value = {}
        
        with pytest.raises(ValidationException) as exc_info:
            validator.attach_policies('test-role', sample_policies)
        
        assert "Failed to attach policy TestPolicy2" in str(exc_info.value)
        # Verify cleanup was attempted for the first policy
        mock_iam_client.delete_role_policy.assert_called_once()
    
    def test_cleanup_temporary_role_success(self, validator, mock_iam_client):
        """Test successful temporary role cleanup."""
        mock_iam_client.list_role_policies.return_value = {
            'PolicyNames': ['TestPolicy1', 'TestPolicy2']
        }
        mock_iam_client.delete_role_policy.return_value = {}
        mock_iam_client.delete_role.return_value = {}
        
        result = validator.cleanup_temporary_role('test-role')
        
        assert result is True
        assert mock_iam_client.delete_role_policy.call_count == 2
        mock_iam_client.delete_role.assert_called_once_with(RoleName='test-role')
    
    def test_cleanup_temporary_role_no_role_name(self, validator, mock_iam_client):
        """Test cleanup with no role name provided."""
        result = validator.cleanup_temporary_role('')
        
        assert result is True
        mock_iam_client.delete_role.assert_not_called()
    
    def test_cleanup_temporary_role_failure(self, validator, mock_iam_client):
        """Test cleanup with IAM operation failures."""
        mock_iam_client.list_role_policies.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchEntity', 'Message': 'Role not found'}},
            'ListRolePolicies'
        )
        mock_iam_client.delete_role.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchEntity', 'Message': 'Role not found'}},
            'DeleteRole'
        )
        
        result = validator.cleanup_temporary_role('test-role')
        
        assert result is False
    
    def test_validate_aws_permissions_success(self, validator, mock_iam_client):
        """Test successful AWS permissions validation."""
        mock_iam_client.get_user.return_value = {'User': {'UserName': 'test-user'}}
        
        result = validator.validate_aws_permissions()
        
        assert result is True
    
    def test_validate_aws_permissions_fallback_success(self, validator, mock_iam_client):
        """Test AWS permissions validation with fallback method."""
        mock_iam_client.get_user.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'GetUser'
        )
        mock_iam_client.list_roles.return_value = {'Roles': []}
        
        result = validator.validate_aws_permissions()
        
        assert result is True
    
    def test_validate_aws_permissions_failure(self, validator, mock_iam_client):
        """Test AWS permissions validation failure."""
        mock_iam_client.get_user.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'GetUser'
        )
        mock_iam_client.list_roles.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'ListRoles'
        )
        
        with pytest.raises(ValidationException) as exc_info:
            validator.validate_aws_permissions()
        
        assert "Insufficient AWS permissions" in str(exc_info.value)
    
    def test_get_validation_summary_success(self, validator):
        """Test validation summary for successful result."""
        result = ValidationResult(
            success=True,
            temporary_role_arn='arn:aws:iam::123456789012:role/test-role',
            attached_policies=['Policy1', 'Policy2'],
            errors=[],
            cleanup_successful=True
        )
        
        summary = validator.get_validation_summary(result)
        
        assert "✓ IAM Policy Validation SUCCESSFUL" in summary
        assert "arn:aws:iam::123456789012:role/test-role" in summary
        assert "Policies validated: 2" in summary
        assert "Policy1" in summary
        assert "Policy2" in summary
    
    def test_get_validation_summary_failure(self, validator):
        """Test validation summary for failed result."""
        result = ValidationResult(
            success=False,
            temporary_role_arn=None,
            attached_policies=[],
            errors=['Error 1', 'Error 2'],
            cleanup_successful=False
        )
        
        summary = validator.get_validation_summary(result)
        
        assert "✗ IAM Policy Validation FAILED" in summary
        assert "Errors: 2" in summary
        assert "Cleanup successful: No" in summary
        assert "Error 1" in summary
        assert "Error 2" in summary