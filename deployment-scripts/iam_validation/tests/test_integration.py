"""
Integration tests for the complete IAM validation and template update workflow.
"""

import pytest
import tempfile
import json
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from ..orchestrator import BedrockAgentCoreIntegrator
from ..data_models import ValidationResult, UpdateResult, IntegrationResult
from ..config import CONFIG


class TestIntegrationWorkflow:
    """Integration tests for the complete workflow."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace with all required files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            
            # Create policy directory and files
            policy_dir = workspace / "policies"
            policy_dir.mkdir()
            
            # Create sample policy files
            sample_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["sts:GetCallerIdentity"],
                        "Resource": "*"
                    }
                ]
            }
            
            for policy_file in CONFIG['policy_files']:
                policy_path = policy_dir / policy_file
                with open(policy_path, 'w') as f:
                    json.dump(sample_policy, f)
            
            # Create input CloudFormation template
            input_template = {
                'AWSTemplateFormatVersion': '2010-09-09',
                'Description': 'Test CloudFormation template',
                'Parameters': {
                    'Environment': {
                        'Type': 'String',
                        'Default': 'prod'
                    }
                },
                'Resources': {
                    'ECSTaskRole': {
                        'Type': 'AWS::IAM::Role',
                        'Properties': {
                            'AssumeRolePolicyDocument': {
                                'Version': '2012-10-17',
                                'Statement': [
                                    {
                                        'Effect': 'Allow',
                                        'Principal': {
                                            'Service': 'ecs-tasks.amazonaws.com'
                                        },
                                        'Action': 'sts:AssumeRole'
                                    }
                                ]
                            },
                            'Policies': [
                                {
                                    'PolicyName': 'ExistingPolicy',
                                    'PolicyDocument': {
                                        'Version': '2012-10-17',
                                        'Statement': [
                                            {
                                                'Effect': 'Allow',
                                                'Action': ['s3:GetObject'],
                                                'Resource': '*'
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    },
                    'TestBucket': {
                        'Type': 'AWS::S3::Bucket',
                        'Properties': {
                            'BucketName': 'test-bucket'
                        }
                    }
                }
            }
            
            input_template_path = workspace / "input-template.yaml"
            with open(input_template_path, 'w') as f:
                yaml.dump(input_template, f)
            
            output_template_path = workspace / "output-template.yaml"
            
            yield {
                'workspace': workspace,
                'policy_directory': str(policy_dir),
                'input_template': str(input_template_path),
                'output_template': str(output_template_path),
                'input_template_content': input_template
            }
    
    @pytest.fixture
    def integrator(self, temp_workspace):
        """Create integrator with temporary workspace."""
        return BedrockAgentCoreIntegrator(
            input_template_path=temp_workspace['input_template'],
            output_template_path=temp_workspace['output_template'],
            policy_directory=temp_workspace['policy_directory']
        )
    
    @patch('boto3.Session')
    def test_complete_workflow_success(self, mock_session, integrator, temp_workspace):
        """Test complete successful workflow from start to finish."""
        # Mock AWS session and IAM client
        mock_iam_client = Mock()
        mock_session.return_value.client.return_value = mock_iam_client
        
        # Mock IAM operations for validation
        mock_iam_client.create_role.return_value = {
            'Role': {'Arn': 'arn:aws:iam::123456789012:role/coa-temp-validation-test'}
        }
        mock_iam_client.put_role_policy.return_value = {}
        mock_iam_client.list_role_policies.return_value = {'PolicyNames': ['Policy1', 'Policy2', 'Policy3']}
        mock_iam_client.delete_role_policy.return_value = {}
        mock_iam_client.delete_role.return_value = {}
        mock_iam_client.get_user.return_value = {'User': {'UserName': 'test-user'}}
        
        # Run complete workflow
        result = integrator.run_validation_and_update()
        
        # Verify overall success
        assert result.overall_success is True
        assert result.validation_result.success is True
        assert result.update_result.success is True
        
        # Verify validation results
        assert result.validation_result.temporary_role_arn is not None
        assert len(result.validation_result.attached_policies) == 3  # All policy files
        assert result.validation_result.cleanup_successful is True
        
        # Verify template update results
        assert result.update_result.output_file == temp_workspace['output_template']
        assert len(result.update_result.new_resources_added) == 1
        assert CONFIG['bedrock_role_resource_name'] in result.update_result.new_resources_added
        assert len(result.update_result.existing_resources_modified) == 1
        assert 'ECSTaskRole' in result.update_result.existing_resources_modified
        
        # Verify output file was created
        output_path = Path(temp_workspace['output_template'])
        assert output_path.exists()
        
        # Verify output template content
        with open(output_path, 'r') as f:
            output_template = yaml.safe_load(f)
        
        # Should have original resources plus new Bedrock role
        assert len(output_template['Resources']) == 3  # Original 2 + new Bedrock role
        assert CONFIG['bedrock_role_resource_name'] in output_template['Resources']
        
        # Verify Bedrock role structure
        bedrock_role = output_template['Resources'][CONFIG['bedrock_role_resource_name']]
        assert bedrock_role['Type'] == 'AWS::IAM::Role'
        assert 'AssumeRolePolicyDocument' in bedrock_role['Properties']
        assert 'Policies' in bedrock_role['Properties']
        assert len(bedrock_role['Properties']['Policies']) == 3  # All policy files
        
        # Verify ECS role was enhanced
        ecs_role = output_template['Resources']['ECSTaskRole']
        policies = ecs_role['Properties']['Policies']
        assert len(policies) == 2  # Original + new Bedrock policy
        
        # Find Bedrock policy in ECS role
        bedrock_policy_found = False
        for policy in policies:
            if 'bedrock-agentcore' in str(policy):
                bedrock_policy_found = True
                break
        assert bedrock_policy_found
    
    @patch('boto3.Session')
    def test_workflow_validation_failure(self, mock_session, integrator):
        """Test workflow when IAM validation fails."""
        # Mock AWS session and IAM client to fail
        mock_iam_client = Mock()
        mock_session.return_value.client.return_value = mock_iam_client
        
        # Mock validation failure
        from botocore.exceptions import ClientError
        mock_iam_client.create_role.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'CreateRole'
        )
        mock_iam_client.get_user.return_value = {'User': {'UserName': 'test-user'}}
        
        # Run workflow
        result = integrator.run_validation_and_update()
        
        # Should fail overall due to validation failure
        assert result.overall_success is False
        assert result.validation_result.success is False
        assert len(result.validation_result.errors) > 0
        
        # Template update should not have been attempted
        assert result.update_result.success is True  # Default success since not attempted
    
    def test_workflow_template_failure(self, integrator, temp_workspace):
        """Test workflow when template update fails."""
        # Remove input template to cause failure
        Path(temp_workspace['input_template']).unlink()
        
        # Skip validation to focus on template failure
        result = integrator.run_validation_and_update(skip_validation=True)
        
        # Should fail overall due to template failure
        assert result.overall_success is False
        assert result.update_result.success is False
        assert len(result.update_result.errors) > 0
    
    @patch('boto3.Session')
    def test_workflow_dry_run(self, mock_session, integrator, temp_workspace):
        """Test workflow in dry run mode."""
        # Mock AWS operations
        mock_iam_client = Mock()
        mock_session.return_value.client.return_value = mock_iam_client
        mock_iam_client.create_role.return_value = {
            'Role': {'Arn': 'arn:aws:iam::123456789012:role/test-role'}
        }
        mock_iam_client.put_role_policy.return_value = {}
        mock_iam_client.list_role_policies.return_value = {'PolicyNames': ['Policy1']}
        mock_iam_client.delete_role_policy.return_value = {}
        mock_iam_client.delete_role.return_value = {}
        mock_iam_client.get_user.return_value = {'User': {'UserName': 'test-user'}}
        
        # Run in dry run mode
        result = integrator.run_validation_and_update(dry_run=True)
        
        # Should succeed
        assert result.overall_success is True
        
        # Output file should not be created in dry run
        output_path = Path(temp_workspace['output_template'])
        assert not output_path.exists()
        
        # But result should indicate dry run
        assert "[DRY RUN]" in result.update_result.output_file
    
    def test_workflow_skip_validation(self, integrator, temp_workspace):
        """Test workflow with validation skipped."""
        result = integrator.run_validation_and_update(skip_validation=True)
        
        # Should succeed (validation was skipped)
        assert result.overall_success is True
        assert result.validation_result.success is True  # Default success
        assert result.update_result.success is True
        
        # Output file should be created
        output_path = Path(temp_workspace['output_template'])
        assert output_path.exists()
    
    def test_workflow_skip_template_update(self, integrator):
        """Test workflow with template update skipped."""
        with patch.object(integrator, 'validate_iam_policies') as mock_validate:
            mock_validate.return_value = ValidationResult(
                success=True,
                temporary_role_arn='arn:aws:iam::123456789012:role/test-role',
                attached_policies=['Policy1'],
                errors=[],
                cleanup_successful=True
            )
            
            result = integrator.run_validation_and_update(skip_template_update=True)
            
            # Should succeed
            assert result.overall_success is True
            assert result.validation_result.success is True
            assert result.update_result.success is True  # Default success
    
    def test_prerequisite_validation_success(self, integrator):
        """Test successful prerequisite validation."""
        with patch('boto3.Session') as mock_session:
            mock_credentials = Mock()
            mock_session.return_value.get_credentials.return_value = mock_credentials
            
            issues = integrator.validate_prerequisites()
            
            # Should have no issues with temp workspace
            assert len(issues) == 0
    
    def test_prerequisite_validation_failures(self, integrator):
        """Test prerequisite validation with various failures."""
        # Test with non-existent paths
        integrator.input_template_path = "/non/existent/template.yaml"
        integrator.policy_directory = "/non/existent/policies"
        integrator.output_template_path = "/non/existent/output.yaml"
        
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.return_value = None
            
            issues = integrator.validate_prerequisites()
            
            # Should have multiple issues
            assert len(issues) >= 3
            assert any("Input template not found" in issue for issue in issues)
            assert any("Policy directory not found" in issue for issue in issues)
            assert any("No AWS credentials found" in issue for issue in issues)
    
    def test_process_summary_generation(self, integrator):
        """Test process summary generation."""
        # Create sample results
        validation_result = ValidationResult(
            success=True,
            temporary_role_arn='arn:aws:iam::123456789012:role/test-role',
            attached_policies=['Policy1', 'Policy2'],
            errors=[],
            cleanup_successful=True
        )
        
        update_result = UpdateResult(
            success=True,
            output_file='output.yaml',
            new_resources_added=['BedrockRole'],
            existing_resources_modified=['ECSRole'],
            errors=[]
        )
        
        integration_result = IntegrationResult.from_results(validation_result, update_result)
        summary = integrator.get_process_summary(integration_result)
        
        # Verify summary content
        assert "BEDROCK AGENTCORE INTEGRATION SUMMARY" in summary
        assert "SUCCESS" in summary
        assert "Policy1" in summary or "2" in summary
        assert "BedrockRole" in summary
        assert "ECSRole" in summary
        assert str(integrator.aws_region) in summary
    
    @patch('boto3.Session')
    def test_cleanup_on_failure(self, mock_session, integrator, temp_workspace):
        """Test cleanup operations when workflow fails."""
        # Mock IAM client
        mock_iam_client = Mock()
        mock_session.return_value.client.return_value = mock_iam_client
        
        # Set up failure context
        integrator.validator.failure_context.temporary_role_name = 'test-role'
        
        # Mock cleanup operations
        mock_iam_client.list_role_policies.return_value = {'PolicyNames': ['Policy1']}
        mock_iam_client.delete_role_policy.return_value = {}
        mock_iam_client.delete_role.return_value = {}
        
        # Create a partial output file
        output_path = Path(temp_workspace['output_template'])
        output_path.write_text("partial content")
        
        # Perform cleanup
        result = integrator.cleanup_on_failure()
        
        # Should succeed
        assert result is True
        
        # Verify IAM cleanup was called
        mock_iam_client.delete_role_policy.assert_called()
        mock_iam_client.delete_role.assert_called_with(RoleName='test-role')
    
    def test_error_handling_and_recovery(self, integrator, temp_workspace):
        """Test error handling and recovery mechanisms."""
        # Test with corrupted input template
        corrupted_template_path = Path(temp_workspace['input_template'])
        corrupted_template_path.write_text("invalid: yaml: content: [")
        
        # Should handle YAML parsing error gracefully
        result = integrator.run_validation_and_update(skip_validation=True)
        
        assert result.overall_success is False
        assert result.update_result.success is False
        assert len(result.update_result.errors) > 0
        
        # Error should be descriptive
        error_found = any("yaml" in error.lower() or "template" in error.lower() 
                         for error in result.update_result.errors)
        assert error_found
    
    def test_configuration_validation(self, integrator):
        """Test configuration validation and parameter handling."""
        # Test with custom configuration
        custom_integrator = BedrockAgentCoreIntegrator(
            aws_profile='custom-profile',
            aws_region='us-west-2'
        )
        
        assert custom_integrator.aws_profile == 'custom-profile'
        assert custom_integrator.aws_region == 'us-west-2'
        
        # Test configuration is passed to components
        assert custom_integrator.validator.aws_profile == 'custom-profile'
        assert custom_integrator.validator.aws_region == 'us-west-2'


class TestEndToEndScenarios:
    """End-to-end scenario tests."""
    
    @pytest.fixture
    def real_policy_files(self):
        """Use actual policy files from the project."""
        policy_dir = Path(__file__).parent.parent.parent / "policies"
        if policy_dir.exists():
            return str(policy_dir)
        else:
            pytest.skip("Real policy files not available")
    
    def test_real_policy_validation(self, real_policy_files):
        """Test validation with real policy files."""
        from ..policy_processor import PolicyDocumentProcessor
        
        processor = PolicyDocumentProcessor(real_policy_files)
        
        try:
            policies = processor.load_policy_files()
            assert len(policies) > 0
            
            # Validate each policy
            for policy in policies:
                result = processor.validate_policy_syntax(policy)
                assert result is True
                
        except Exception as e:
            # If real files have issues, that's valuable feedback
            pytest.fail(f"Real policy validation failed: {str(e)}")
    
    def test_real_template_processing(self):
        """Test with real CloudFormation template if available."""
        template_path = Path(__file__).parent.parent.parent / "cloud-optimization-assistant-0.1.0.yaml"
        
        if not template_path.exists():
            pytest.skip("Real CloudFormation template not available")
        
        from ..template_manager import CloudFormationTemplateManager
        
        manager = CloudFormationTemplateManager(str(template_path))
        
        try:
            template = manager.load_template()
            assert 'Resources' in template
            assert len(template['Resources']) > 0
            
            # Validate template structure
            issues = manager.validate_template_structure(template)
            # Real template might have some issues, but should be loadable
            assert isinstance(issues, list)
            
        except Exception as e:
            pytest.fail(f"Real template processing failed: {str(e)}")


class TestPerformanceAndScaling:
    """Performance and scaling tests."""
    
    def test_large_template_handling(self):
        """Test handling of large CloudFormation templates."""
        # Create a large template with many resources
        large_template = {
            'AWSTemplateFormatVersion': '2010-09-09',
            'Resources': {}
        }
        
        # Add 100 resources
        for i in range(100):
            large_template['Resources'][f'Resource{i}'] = {
                'Type': 'AWS::S3::Bucket',
                'Properties': {
                    'BucketName': f'test-bucket-{i}'
                }
            }
        
        # Add ECS role
        large_template['Resources']['ECSTaskRole'] = {
            'Type': 'AWS::IAM::Role',
            'Properties': {
                'AssumeRolePolicyDocument': {
                    'Statement': [
                        {
                            'Principal': {'Service': 'ecs-tasks.amazonaws.com'},
                            'Action': 'sts:AssumeRole'
                        }
                    ]
                },
                'Policies': []
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(large_template, f)
            temp_path = f.name
        
        try:
            from ..template_manager import CloudFormationTemplateManager
            
            manager = CloudFormationTemplateManager(temp_path)
            
            # Should handle large template efficiently
            loaded_template = manager.load_template()
            assert len(loaded_template['Resources']) == 101
            
            # Should be able to add Bedrock role
            updated_template = manager.add_bedrock_agentcore_role(loaded_template)
            assert len(updated_template['Resources']) == 102
            
            # Should be able to update ECS permissions
            final_template = manager.update_ecs_permissions(updated_template)
            assert len(final_template['Resources']) == 102
            
        finally:
            Path(temp_path).unlink()
    
    def test_many_policy_files(self):
        """Test handling of many policy files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_dir = Path(temp_dir)
            
            # Create many policy files
            sample_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:GetObject"],
                        "Resource": "*"
                    }
                ]
            }
            
            policy_files = []
            for i in range(10):
                policy_file = f"policy-{i}.json"
                policy_path = policy_dir / policy_file
                with open(policy_path, 'w') as f:
                    json.dump(sample_policy, f)
                policy_files.append(policy_file)
            
            # Mock CONFIG to use our policy files
            with patch.dict(CONFIG, {'policy_files': policy_files}):
                from ..policy_processor import PolicyDocumentProcessor
                
                processor = PolicyDocumentProcessor(str(policy_dir))
                
                # Should handle many policies efficiently
                policies = processor.load_policy_files()
                assert len(policies) == 10
                
                # Should validate all policies
                for policy in policies:
                    result = processor.validate_policy_syntax(policy)
                    assert result is True