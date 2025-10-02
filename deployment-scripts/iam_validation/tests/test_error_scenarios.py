"""
Tests for error scenarios and edge cases.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

from ..orchestrator import BedrockAgentCoreIntegrator
from ..validator import IAMRoleValidator
from ..template_manager import CloudFormationTemplateManager
from ..policy_processor import PolicyDocumentProcessor
from ..error_handling import ValidationException, TemplateException, PolicyException


class TestErrorScenarios:
    """Test various error scenarios and edge cases."""
    
    def test_aws_credentials_not_found(self):
        """Test behavior when AWS credentials are not available."""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.return_value = None
            
            integrator = BedrockAgentCoreIntegrator()
            issues = integrator.validate_prerequisites()
            
            assert len(issues) > 0
            assert any("No AWS credentials found" in issue for issue in issues)
    
    def test_aws_permission_denied(self):
        """Test behavior when AWS permissions are insufficient."""
        with patch('boto3.Session') as mock_session:
            mock_iam_client = Mock()
            mock_session.return_value.client.return_value = mock_iam_client
            
            # Mock permission denied error
            mock_iam_client.create_role.side_effect = ClientError(
                {'Error': {'Code': 'AccessDenied', 'Message': 'User is not authorized'}},
                'CreateRole'
            )
            mock_iam_client.get_user.return_value = {'User': {'UserName': 'test-user'}}
            
            validator = IAMRoleValidator()
            result = validator.validate_policies()
            
            assert result.success is False
            assert len(result.errors) > 0
            assert any("AccessDenied" in error or "not authorized" in error for error in result.errors)
    
    def test_iam_service_limit_exceeded(self):
        """Test behavior when IAM service limits are exceeded."""
        with patch('boto3.Session') as mock_session:
            mock_iam_client = Mock()
            mock_session.return_value.client.return_value = mock_iam_client
            
            # Mock service limit error
            mock_iam_client.create_role.side_effect = ClientError(
                {'Error': {'Code': 'LimitExceeded', 'Message': 'Role limit exceeded'}},
                'CreateRole'
            )
            mock_iam_client.get_user.return_value = {'User': {'UserName': 'test-user'}}
            
            validator = IAMRoleValidator()
            result = validator.validate_policies()
            
            assert result.success is False
            assert any("LimitExceeded" in error for error in result.errors)
    
    def test_policy_file_not_found(self):
        """Test behavior when required policy files are missing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create empty policy directory
            policy_dir = Path(temp_dir)
            
            processor = PolicyDocumentProcessor(str(policy_dir))
            
            with pytest.raises(PolicyException) as exc_info:
                processor.load_policy_files()
            
            assert "Required policy file not found" in str(exc_info.value)
    
    def test_policy_file_invalid_json(self):
        """Test behavior when policy file contains invalid JSON."""
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_dir = Path(temp_dir)
            
            # Create invalid JSON file
            invalid_policy_path = policy_dir / "invalid-policy.json"
            invalid_policy_path.write_text('{"invalid": json syntax}')
            
            # Mock CONFIG to use our invalid policy file
            with patch.dict('deployment_scripts.iam_validation.config.CONFIG', 
                          {'policy_files': ['invalid-policy.json']}):
                processor = PolicyDocumentProcessor(str(policy_dir))
                
                with pytest.raises(PolicyException) as exc_info:
                    processor.load_policy_files()
                
                assert "Invalid JSON in policy file" in str(exc_info.value)
    
    def test_policy_file_missing_required_fields(self):
        """Test behavior when policy file is missing required fields."""
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_dir = Path(temp_dir)
            
            # Create policy file missing Version field
            invalid_policy = {"Statement": [{"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "*"}]}
            invalid_policy_path = policy_dir / "invalid-policy.json"
            with open(invalid_policy_path, 'w') as f:
                json.dump(invalid_policy, f)
            
            with patch.dict('deployment_scripts.iam_validation.config.CONFIG', 
                          {'policy_files': ['invalid-policy.json']}):
                processor = PolicyDocumentProcessor(str(policy_dir))
                
                with pytest.raises(PolicyException) as exc_info:
                    processor.load_policy_files()
                
                assert "missing required fields" in str(exc_info.value)
    
    def test_template_file_not_found(self):
        """Test behavior when CloudFormation template file is missing."""
        manager = CloudFormationTemplateManager("/non/existent/template.yaml")
        
        with pytest.raises(TemplateException) as exc_info:
            manager.load_template()
        
        assert "Template file not found" in str(exc_info.value)
    
    def test_template_invalid_yaml(self):
        """Test behavior when CloudFormation template has invalid YAML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('invalid: yaml: syntax: [')
            temp_path = f.name
        
        try:
            manager = CloudFormationTemplateManager(temp_path)
            
            with pytest.raises(TemplateException) as exc_info:
                manager.load_template()
            
            assert "Invalid YAML syntax" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_template_missing_required_sections(self):
        """Test behavior when template is missing required sections."""
        invalid_template = {"NotATemplate": "true"}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            import yaml
            yaml.dump(invalid_template, f)
            temp_path = f.name
        
        try:
            manager = CloudFormationTemplateManager(temp_path)
            
            with pytest.raises(TemplateException) as exc_info:
                manager.load_template()
            
            assert "missing required section" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_template_no_ecs_role_found(self):
        """Test behavior when no ECS role is found in template."""
        template_without_ecs = {
            'AWSTemplateFormatVersion': '2010-09-09',
            'Resources': {
                'TestBucket': {
                    'Type': 'AWS::S3::Bucket'
                }
            }
        }
        
        manager = CloudFormationTemplateManager()
        
        with pytest.raises(TemplateException) as exc_info:
            manager.update_ecs_permissions(template_without_ecs)
        
        assert "Could not find ECS task role" in str(exc_info.value)
    
    def test_output_directory_not_writable(self):
        """Test behavior when output directory is not writable."""
        # Try to write to a non-existent directory without permission to create it
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            mock_mkdir.side_effect = PermissionError("Permission denied")
            
            integrator = BedrockAgentCoreIntegrator(
                output_template_path="/root/non-writable/output.yaml"
            )
            
            issues = integrator.validate_prerequisites()
            
            assert len(issues) > 0
            assert any("Cannot create output directory" in issue for issue in issues)
    
    def test_partial_policy_attachment_failure(self):
        """Test behavior when some policies attach successfully but others fail."""
        with patch('boto3.Session') as mock_session:
            mock_iam_client = Mock()
            mock_session.return_value.client.return_value = mock_iam_client
            
            # Mock successful role creation
            mock_iam_client.create_role.return_value = {
                'Role': {'Arn': 'arn:aws:iam::123456789012:role/test-role'}
            }
            
            # Mock partial policy attachment failure
            mock_iam_client.put_role_policy.side_effect = [
                {},  # First policy succeeds
                {},  # Second policy succeeds
                ClientError(  # Third policy fails
                    {'Error': {'Code': 'MalformedPolicyDocument', 'Message': 'Invalid policy'}},
                    'PutRolePolicy'
                )
            ]
            
            # Mock cleanup operations
            mock_iam_client.delete_role_policy.return_value = {}
            mock_iam_client.get_user.return_value = {'User': {'UserName': 'test-user'}}
            
            validator = IAMRoleValidator()
            result = validator.validate_policies()
            
            assert result.success is False
            assert len(result.errors) > 0
            assert any("MalformedPolicyDocument" in error for error in result.errors)
            
            # Should have attempted cleanup of successfully attached policies
            assert mock_iam_client.delete_role_policy.call_count >= 1
    
    def test_cleanup_failure_during_validation(self):
        """Test behavior when cleanup operations fail."""
        with patch('boto3.Session') as mock_session:
            mock_iam_client = Mock()
            mock_session.return_value.client.return_value = mock_iam_client
            
            # Mock successful operations up to cleanup
            mock_iam_client.create_role.return_value = {
                'Role': {'Arn': 'arn:aws:iam::123456789012:role/test-role'}
            }
            mock_iam_client.put_role_policy.return_value = {}
            mock_iam_client.list_role_policies.return_value = {'PolicyNames': ['Policy1']}
            mock_iam_client.get_user.return_value = {'User': {'UserName': 'test-user'}}
            
            # Mock cleanup failure
            mock_iam_client.delete_role_policy.side_effect = ClientError(
                {'Error': {'Code': 'NoSuchEntity', 'Message': 'Policy not found'}},
                'DeleteRolePolicy'
            )
            mock_iam_client.delete_role.side_effect = ClientError(
                {'Error': {'Code': 'NoSuchEntity', 'Message': 'Role not found'}},
                'DeleteRole'
            )
            
            validator = IAMRoleValidator()
            result = validator.validate_policies()
            
            # Validation should succeed but cleanup should fail
            assert result.success is True
            assert result.cleanup_successful is False
    
    def test_network_connectivity_issues(self):
        """Test behavior when network connectivity issues occur."""
        with patch('boto3.Session') as mock_session:
            mock_iam_client = Mock()
            mock_session.return_value.client.return_value = mock_iam_client
            
            # Mock network connectivity error
            from botocore.exceptions import EndpointConnectionError
            mock_iam_client.create_role.side_effect = EndpointConnectionError(
                endpoint_url="https://iam.amazonaws.com"
            )
            mock_iam_client.get_user.return_value = {'User': {'UserName': 'test-user'}}
            
            validator = IAMRoleValidator()
            result = validator.validate_policies()
            
            assert result.success is False
            assert len(result.errors) > 0
    
    def test_policy_size_limit_exceeded(self):
        """Test behavior when policy size exceeds limits."""
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_dir = Path(temp_dir)
            
            # Create oversized policy
            large_statement = {
                'Effect': 'Allow',
                'Action': ['s3:GetObject'],
                'Resource': 'x' * 20000  # Very large resource string
            }
            
            oversized_policy = {
                'Version': '2012-10-17',
                'Statement': [large_statement]
            }
            
            policy_path = policy_dir / "oversized-policy.json"
            with open(policy_path, 'w') as f:
                json.dump(oversized_policy, f)
            
            with patch.dict('deployment_scripts.iam_validation.config.CONFIG', 
                          {'policy_files': ['oversized-policy.json'], 'max_policy_size': 1000}):
                processor = PolicyDocumentProcessor(str(policy_dir))
                policies = processor.load_policy_files()
                
                with pytest.raises(ValidationException) as exc_info:
                    processor.validate_policy_syntax(policies[0])
                
                assert "Policy size" in str(exc_info.value)
                assert "exceeds maximum" in str(exc_info.value)
    
    def test_concurrent_role_creation_conflict(self):
        """Test behavior when role name conflicts occur."""
        with patch('boto3.Session') as mock_session:
            mock_iam_client = Mock()
            mock_session.return_value.client.return_value = mock_iam_client
            
            # Mock role already exists error
            mock_iam_client.create_role.side_effect = ClientError(
                {'Error': {'Code': 'EntityAlreadyExists', 'Message': 'Role already exists'}},
                'CreateRole'
            )
            mock_iam_client.get_user.return_value = {'User': {'UserName': 'test-user'}}
            
            validator = IAMRoleValidator()
            result = validator.validate_policies()
            
            assert result.success is False
            assert any("EntityAlreadyExists" in error for error in result.errors)
    
    def test_integration_with_corrupted_state(self):
        """Test integration behavior when system is in corrupted state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            
            # Create partially corrupted workspace
            policy_dir = workspace / "policies"
            policy_dir.mkdir()
            
            # Create one valid and one invalid policy file
            valid_policy = {
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "*"}]
            }
            
            valid_policy_path = policy_dir / "valid-policy.json"
            with open(valid_policy_path, 'w') as f:
                json.dump(valid_policy, f)
            
            invalid_policy_path = policy_dir / "invalid-policy.json"
            invalid_policy_path.write_text('corrupted content')
            
            # Create corrupted template
            template_path = workspace / "template.yaml"
            template_path.write_text('corrupted: yaml: [')
            
            with patch.dict('deployment_scripts.iam_validation.config.CONFIG', 
                          {'policy_files': ['valid-policy.json', 'invalid-policy.json']}):
                integrator = BedrockAgentCoreIntegrator(
                    input_template_path=str(template_path),
                    policy_directory=str(policy_dir)
                )
                
                result = integrator.run_validation_and_update()
                
                # Should fail gracefully with descriptive errors
                assert result.overall_success is False
                assert len(result.validation_result.errors) > 0 or len(result.update_result.errors) > 0
    
    def test_memory_pressure_scenarios(self):
        """Test behavior under memory pressure conditions."""
        # Simulate memory pressure by creating very large data structures
        large_template = {
            'AWSTemplateFormatVersion': '2010-09-09',
            'Resources': {}
        }
        
        # Add many resources to create memory pressure
        for i in range(1000):
            large_template['Resources'][f'Resource{i}'] = {
                'Type': 'AWS::S3::Bucket',
                'Properties': {
                    'BucketName': f'test-bucket-{i}',
                    'Tags': [{'Key': f'Tag{j}', 'Value': f'Value{j}'} for j in range(100)]
                }
            }
        
        # Should handle large templates without crashing
        manager = CloudFormationTemplateManager()
        
        try:
            # This should not raise memory errors
            summary = manager.get_template_summary(large_template)
            assert summary['total_resources'] == 1000
        except MemoryError:
            pytest.fail("Memory error occurred with large template")
    
    def test_unicode_and_encoding_issues(self):
        """Test behavior with unicode and encoding issues."""
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_dir = Path(temp_dir)
            
            # Create policy with unicode characters
            unicode_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:GetObject"],
                        "Resource": "arn:aws:s3:::test-bucket-with-unicode-名前/*"
                    }
                ]
            }
            
            policy_path = policy_dir / "unicode-policy.json"
            with open(policy_path, 'w', encoding='utf-8') as f:
                json.dump(unicode_policy, f, ensure_ascii=False)
            
            with patch.dict('deployment_scripts.iam_validation.config.CONFIG', 
                          {'policy_files': ['unicode-policy.json']}):
                processor = PolicyDocumentProcessor(str(policy_dir))
                
                # Should handle unicode content properly
                policies = processor.load_policy_files()
                assert len(policies) == 1
                assert "名前" in str(policies[0]['policy_document'])