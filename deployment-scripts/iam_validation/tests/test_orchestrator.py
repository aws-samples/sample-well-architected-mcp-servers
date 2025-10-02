"""
Unit tests for BedrockAgentCoreIntegrator.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

from ..orchestrator import BedrockAgentCoreIntegrator
from ..data_models import ValidationResult, UpdateResult, IntegrationResult
from ..error_handling import ValidationException, TemplateException


class TestBedrockAgentCoreIntegrator:
    """Test cases for BedrockAgentCoreIntegrator class."""
    
    @pytest.fixture
    def temp_files(self):
        """Create temporary files for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create input template
            input_template = temp_path / "input.yaml"
            input_template.write_text("AWSTemplateFormatVersion: '2010-09-09'\nResources: {}")
            
            # Create policy directory
            policy_dir = temp_path / "policies"
            policy_dir.mkdir()
            
            # Create policy files
            for policy_file in ['policy1.json', 'policy2.json']:
                policy_path = policy_dir / policy_file
                policy_path.write_text('{"Version": "2012-10-17", "Statement": []}')
            
            yield {
                'input_template': str(input_template),
                'output_template': str(temp_path / "output.yaml"),
                'policy_directory': str(policy_dir)
            }
    
    @pytest.fixture
    def integrator(self, temp_files):
        """Create BedrockAgentCoreIntegrator with temp files."""
        return BedrockAgentCoreIntegrator(
            input_template_path=temp_files['input_template'],
            output_template_path=temp_files['output_template'],
            policy_directory=temp_files['policy_directory']
        )
    
    def test_init_default_params(self):
        """Test initialization with default parameters."""
        integrator = BedrockAgentCoreIntegrator()
        
        assert integrator.aws_profile is None
        assert integrator.aws_region == 'us-east-1'  # Default from CONFIG
        assert integrator.validator is not None
        assert integrator.template_manager is not None
        assert integrator.ecs_enhancer is not None
        assert integrator.policy_processor is not None
    
    def test_init_custom_params(self, temp_files):
        """Test initialization with custom parameters."""
        integrator = BedrockAgentCoreIntegrator(
            aws_profile='test-profile',
            aws_region='us-west-2',
            input_template_path=temp_files['input_template'],
            output_template_path=temp_files['output_template'],
            policy_directory=temp_files['policy_directory']
        )
        
        assert integrator.aws_profile == 'test-profile'
        assert integrator.aws_region == 'us-west-2'
        assert integrator.input_template_path == temp_files['input_template']
        assert integrator.output_template_path == temp_files['output_template']
        assert integrator.policy_directory == temp_files['policy_directory']
    
    @patch('deployment_scripts.iam_validation.orchestrator.IAMRoleValidator')
    @patch('deployment_scripts.iam_validation.orchestrator.CloudFormationTemplateManager')
    def test_run_validation_and_update_success(self, mock_template_manager_class, mock_validator_class, integrator):
        """Test successful complete integration process."""
        # Mock validator
        mock_validator = Mock()
        mock_validator_class.return_value = mock_validator
        mock_validator.validate_aws_permissions.return_value = True
        mock_validator.validate_policies.return_value = ValidationResult(
            success=True,
            temporary_role_arn='arn:aws:iam::123456789012:role/test-role',
            attached_policies=['Policy1', 'Policy2'],
            errors=[],
            cleanup_successful=True
        )
        
        # Mock template manager
        mock_template_manager = Mock()
        mock_template_manager_class.return_value = mock_template_manager
        mock_template_manager.load_template.return_value = {'Resources': {}}
        mock_template_manager.validate_template_structure.return_value = []
        mock_template_manager.add_bedrock_agentcore_role.return_value = {'Resources': {'NewRole': {}}}
        mock_template_manager.update_ecs_permissions.return_value = {'Resources': {'NewRole': {}, 'ECSRole': {}}}
        mock_template_manager.save_template.return_value = True
        mock_template_manager.get_template_summary.return_value = {
            'total_resources': 2,
            'iam_roles': ['NewRole', 'ECSRole']
        }
        
        # Mock ECS enhancer
        integrator.ecs_enhancer.find_ecs_task_role = Mock(return_value='ECSRole')
        
        result = integrator.run_validation_and_update()
        
        assert result.overall_success is True
        assert result.validation_result.success is True
        assert result.update_result.success is True
        assert len(result.validation_result.attached_policies) == 2
    
    @patch('deployment_scripts.iam_validation.orchestrator.IAMRoleValidator')
    def test_run_validation_and_update_validation_failure(self, mock_validator_class, integrator):
        """Test integration process with validation failure."""
        # Mock validator to fail
        mock_validator = Mock()
        mock_validator_class.return_value = mock_validator
        mock_validator.validate_aws_permissions.return_value = True
        mock_validator.validate_policies.return_value = ValidationResult(
            success=False,
            temporary_role_arn=None,
            attached_policies=[],
            errors=['Validation failed'],
            cleanup_successful=True
        )
        
        result = integrator.run_validation_and_update()
        
        assert result.overall_success is False
        assert result.validation_result.success is False
        assert len(result.validation_result.errors) == 1
        # Template update should not have been attempted
        assert result.update_result.success is True  # Default success since not attempted
    
    def test_run_validation_and_update_skip_validation(self, integrator):
        """Test integration process with validation skipped."""
        with patch.object(integrator, 'update_cloudformation_template') as mock_update:
            mock_update.return_value = UpdateResult(
                success=True,
                output_file='test.yaml',
                new_resources_added=['NewRole'],
                existing_resources_modified=['ECSRole'],
                errors=[]
            )
            
            result = integrator.run_validation_and_update(skip_validation=True)
            
            assert result.overall_success is True
            assert result.validation_result.success is True  # Default success
            assert result.update_result.success is True
            mock_update.assert_called_once()
    
    def test_run_validation_and_update_skip_template_update(self, integrator):
        """Test integration process with template update skipped."""
        with patch.object(integrator, 'validate_iam_policies') as mock_validate:
            mock_validate.return_value = ValidationResult(
                success=True,
                temporary_role_arn='arn:aws:iam::123456789012:role/test-role',
                attached_policies=['Policy1'],
                errors=[],
                cleanup_successful=True
            )
            
            result = integrator.run_validation_and_update(skip_template_update=True)
            
            assert result.overall_success is True
            assert result.validation_result.success is True
            assert result.update_result.success is True  # Default success
            mock_validate.assert_called_once()
    
    def test_run_validation_and_update_dry_run(self, integrator):
        """Test integration process in dry run mode."""
        with patch.object(integrator, 'validate_iam_policies') as mock_validate, \
             patch.object(integrator, 'update_cloudformation_template') as mock_update:
            
            mock_validate.return_value = ValidationResult(
                success=True,
                temporary_role_arn='arn:aws:iam::123456789012:role/test-role',
                attached_policies=['Policy1'],
                errors=[],
                cleanup_successful=True
            )
            
            mock_update.return_value = UpdateResult(
                success=True,
                output_file='[DRY RUN] test.yaml',
                new_resources_added=['NewRole'],
                existing_resources_modified=['ECSRole'],
                errors=[]
            )
            
            result = integrator.run_validation_and_update(dry_run=True)
            
            assert result.overall_success is True
            mock_validate.assert_called_once()
            mock_update.assert_called_once_with(dry_run=True)
    
    def test_validate_iam_policies_success(self, integrator):
        """Test successful IAM policy validation."""
        with patch.object(integrator.validator, 'validate_aws_permissions') as mock_aws_validate, \
             patch.object(integrator.validator, 'validate_policies') as mock_validate:
            
            mock_aws_validate.return_value = True
            mock_validate.return_value = ValidationResult(
                success=True,
                temporary_role_arn='arn:aws:iam::123456789012:role/test-role',
                attached_policies=['Policy1', 'Policy2'],
                errors=[],
                cleanup_successful=True
            )
            
            result = integrator.validate_iam_policies()
            
            assert result.success is True
            assert len(result.attached_policies) == 2
            assert result.cleanup_successful is True
    
    def test_validate_iam_policies_failure(self, integrator):
        """Test IAM policy validation failure."""
        with patch.object(integrator.validator, 'validate_aws_permissions') as mock_aws_validate:
            mock_aws_validate.side_effect = ValidationException("AWS validation failed")
            
            result = integrator.validate_iam_policies()
            
            assert result.success is False
            assert len(result.errors) == 1
            assert "AWS validation failed" in result.errors[0]
    
    @patch('deployment_scripts.iam_validation.orchestrator.Path')
    def test_update_cloudformation_template_success(self, mock_path_class, integrator):
        """Test successful CloudFormation template update."""
        # Mock Path operations
        mock_path = Mock()
        mock_path_class.return_value = mock_path
        
        with patch.object(integrator.template_manager, 'load_template') as mock_load, \
             patch.object(integrator.template_manager, 'validate_template_structure') as mock_validate, \
             patch.object(integrator.template_manager, 'add_bedrock_agentcore_role') as mock_add_role, \
             patch.object(integrator.template_manager, 'update_ecs_permissions') as mock_update_ecs, \
             patch.object(integrator.template_manager, 'save_template') as mock_save, \
             patch.object(integrator.template_manager, 'get_template_summary') as mock_summary, \
             patch.object(integrator.ecs_enhancer, 'find_ecs_task_role') as mock_find_ecs:
            
            mock_load.return_value = {'Resources': {'ExistingRole': {}}}
            mock_validate.return_value = []  # No validation issues
            mock_add_role.return_value = {'Resources': {'ExistingRole': {}, 'BedrockRole': {}}}
            mock_update_ecs.return_value = {'Resources': {'ExistingRole': {}, 'BedrockRole': {}}}
            mock_save.return_value = True
            mock_summary.return_value = {'total_resources': 2, 'iam_roles': ['ExistingRole', 'BedrockRole']}
            mock_find_ecs.return_value = 'ExistingRole'
            
            result = integrator.update_cloudformation_template()
            
            assert result.success is True
            assert len(result.new_resources_added) == 1
            assert len(result.existing_resources_modified) == 1
            assert 'BedrockAgentCoreRuntimeRole' in result.new_resources_added
            assert 'ExistingRole' in result.existing_resources_modified
    
    def test_update_cloudformation_template_dry_run(self, integrator):
        """Test CloudFormation template update in dry run mode."""
        with patch.object(integrator.template_manager, 'load_template') as mock_load, \
             patch.object(integrator.template_manager, 'validate_template_structure') as mock_validate, \
             patch.object(integrator.template_manager, 'add_bedrock_agentcore_role') as mock_add_role, \
             patch.object(integrator.template_manager, 'update_ecs_permissions') as mock_update_ecs, \
             patch.object(integrator.template_manager, 'save_template') as mock_save, \
             patch.object(integrator.template_manager, 'get_template_summary') as mock_summary, \
             patch.object(integrator.ecs_enhancer, 'find_ecs_task_role') as mock_find_ecs:
            
            mock_load.return_value = {'Resources': {}}
            mock_validate.return_value = []
            mock_add_role.return_value = {'Resources': {'BedrockRole': {}}}
            mock_update_ecs.return_value = {'Resources': {'BedrockRole': {}}}
            mock_summary.return_value = {'total_resources': 1, 'iam_roles': ['BedrockRole']}
            mock_find_ecs.return_value = None
            
            result = integrator.update_cloudformation_template(dry_run=True)
            
            assert result.success is True
            assert "[DRY RUN]" in result.output_file
            mock_save.assert_not_called()  # Should not save in dry run mode
    
    def test_update_cloudformation_template_failure(self, integrator):
        """Test CloudFormation template update failure."""
        with patch.object(integrator.template_manager, 'load_template') as mock_load:
            mock_load.side_effect = TemplateException("Template load failed")
            
            result = integrator.update_cloudformation_template()
            
            assert result.success is False
            assert len(result.errors) == 1
            assert "Template load failed" in result.errors[0]
    
    def test_validate_prerequisites_success(self, integrator, temp_files):
        """Test successful prerequisite validation."""
        with patch('boto3.Session') as mock_session:
            mock_credentials = Mock()
            mock_session.return_value.get_credentials.return_value = mock_credentials
            
            issues = integrator.validate_prerequisites()
            
            assert len(issues) == 0
    
    def test_validate_prerequisites_missing_files(self, integrator):
        """Test prerequisite validation with missing files."""
        # Use non-existent paths
        integrator.input_template_path = "/non/existent/template.yaml"
        integrator.policy_directory = "/non/existent/policies"
        
        issues = integrator.validate_prerequisites()
        
        assert len(issues) >= 2
        assert any("Input template not found" in issue for issue in issues)
        assert any("Policy directory not found" in issue for issue in issues)
    
    def test_validate_prerequisites_no_aws_credentials(self, integrator, temp_files):
        """Test prerequisite validation with no AWS credentials."""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.return_value = None
            
            issues = integrator.validate_prerequisites()
            
            assert len(issues) >= 1
            assert any("No AWS credentials found" in issue for issue in issues)
    
    def test_get_process_summary_success(self, integrator):
        """Test process summary generation for successful result."""
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
        
        assert "SUCCESS" in summary
        assert "✓" in summary
        assert "Policy1" in summary or "2" in summary  # Should mention policies
        assert "BedrockRole" in summary
        assert "ECSRole" in summary
    
    def test_get_process_summary_failure(self, integrator):
        """Test process summary generation for failed result."""
        validation_result = ValidationResult(
            success=False,
            temporary_role_arn=None,
            attached_policies=[],
            errors=['Validation error 1', 'Validation error 2'],
            cleanup_successful=False
        )
        
        update_result = UpdateResult(
            success=False,
            output_file='',
            new_resources_added=[],
            existing_resources_modified=[],
            errors=['Template error 1']
        )
        
        integration_result = IntegrationResult.from_results(validation_result, update_result)
        summary = integrator.get_process_summary(integration_result)
        
        assert "FAILED" in summary
        assert "✗" in summary
        assert "Validation error 1" in summary
        assert "Template error 1" in summary
    
    def test_cleanup_on_failure_success(self, integrator):
        """Test successful cleanup on failure."""
        # Mock validator with failure context
        integrator.validator.failure_context = Mock()
        integrator.validator.failure_context.temporary_role_name = 'test-role'
        
        with patch.object(integrator.validator, 'cleanup_temporary_role') as mock_cleanup, \
             patch('pathlib.Path') as mock_path_class:
            
            mock_cleanup.return_value = True
            
            # Mock output file that doesn't exist
            mock_path = Mock()
            mock_path.exists.return_value = False
            mock_path_class.return_value = mock_path
            
            result = integrator.cleanup_on_failure()
            
            assert result is True
            mock_cleanup.assert_called_once_with('test-role')
    
    def test_cleanup_on_failure_with_partial_file(self, integrator):
        """Test cleanup on failure with partial output file."""
        integrator.validator.failure_context = Mock()
        integrator.validator.failure_context.temporary_role_name = None
        
        with patch('pathlib.Path') as mock_path_class, \
             patch('time.time') as mock_time:
            
            # Mock recent file that should be deleted
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_stat = Mock()
            mock_stat.st_mtime = 1000  # File creation time
            mock_path.stat.return_value = mock_stat
            mock_path_class.return_value = mock_path
            
            mock_time.return_value = 2000  # Current time (1000 seconds later)
            
            result = integrator.cleanup_on_failure()
            
            assert result is True
            mock_path.unlink.assert_called_once()  # File should be deleted