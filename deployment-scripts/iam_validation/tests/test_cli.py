"""
Unit tests for CLI functionality.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

from ..cli import (
    create_parser, validate_arguments, run_security_validation,
    run_main_workflow, show_configuration, main
)
from ..data_models import ValidationResult, UpdateResult, IntegrationResult


class TestCLI:
    """Test cases for CLI functionality."""
    
    def test_create_parser(self):
        """Test argument parser creation."""
        parser = create_parser()
        
        # Test default arguments
        args = parser.parse_args([])
        assert args.aws_profile is None
        assert args.aws_region == 'us-east-1'
        assert args.dry_run is False
        assert args.skip_validation is False
        assert args.skip_template_update is False
        assert args.verbose is False
        assert args.quiet is False
    
    def test_parser_with_arguments(self):
        """Test parser with various arguments."""
        parser = create_parser()
        
        args = parser.parse_args([
            '--aws-profile', 'test-profile',
            '--aws-region', 'us-west-2',
            '--input-template', '/path/to/input.yaml',
            '--output-template', '/path/to/output.yaml',
            '--policy-directory', '/path/to/policies',
            '--dry-run',
            '--verbose',
            '--log-file', 'test.log'
        ])
        
        assert args.aws_profile == 'test-profile'
        assert args.aws_region == 'us-west-2'
        assert args.input_template == '/path/to/input.yaml'
        assert args.output_template == '/path/to/output.yaml'
        assert args.policy_directory == '/path/to/policies'
        assert args.dry_run is True
        assert args.verbose is True
        assert args.log_file == 'test.log'
    
    def test_parser_conflicting_arguments(self):
        """Test parser with conflicting arguments."""
        parser = create_parser()
        
        # Should not raise error during parsing (validation happens later)
        args = parser.parse_args(['--verbose', '--quiet'])
        assert args.verbose is True
        assert args.quiet is True
    
    def test_validate_arguments_success(self):
        """Test successful argument validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create required files
            policy_dir = temp_path / "policies"
            policy_dir.mkdir()
            
            input_template = temp_path / "input.yaml"
            input_template.write_text("test content")
            
            # Create mock args
            args = Mock()
            args.policy_directory = str(policy_dir)
            args.input_template = str(input_template)
            args.skip_validation = False
            args.skip_template_update = False
            args.security_only = False
            args.quiet = False
            args.verbose = False
            
            result = validate_arguments(args)
            assert result is True
    
    def test_validate_arguments_missing_files(self):
        """Test argument validation with missing files."""
        args = Mock()
        args.policy_directory = "/non/existent/policies"
        args.input_template = "/non/existent/template.yaml"
        args.skip_validation = False
        args.skip_template_update = False
        args.security_only = False
        args.quiet = False
        args.verbose = False
        
        with patch('sys.stderr', new_callable=StringIO):
            result = validate_arguments(args)
            assert result is False
    
    def test_validate_arguments_conflicting_options(self):
        """Test argument validation with conflicting options."""
        args = Mock()
        args.policy_directory = "/path/to/policies"
        args.input_template = "/path/to/template.yaml"
        args.skip_validation = True
        args.skip_template_update = True
        args.security_only = False
        args.quiet = True
        args.verbose = True
        
        with patch('sys.stderr', new_callable=StringIO):
            result = validate_arguments(args)
            assert result is False
    
    @patch('iam_validation.cli.CloudFormationTemplateManager')
    @patch('iam_validation.cli.SecurityValidator')
    @patch('iam_validation.cli.ECSPermissionEnhancer')
    def test_run_security_validation_success(self, mock_enhancer_class, mock_validator_class, mock_manager_class):
        """Test successful security validation."""
        # Mock template manager
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager
        mock_manager.load_template.return_value = {
            'Resources': {
                'BedrockAgentCoreRuntimeRole': {'Type': 'AWS::IAM::Role'},
                'ECSTaskRole': {'Type': 'AWS::IAM::Role'}
            }
        }
        
        # Mock security validator
        mock_validator = Mock()
        mock_validator_class.return_value = mock_validator
        
        from ..security_validator import SecurityValidationResult, SecurityIssue
        mock_validator.validate_bedrock_agentcore_role.return_value = SecurityValidationResult(
            passed=True, issues=[], summary={'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        )
        mock_validator.validate_ecs_permissions.return_value = SecurityValidationResult(
            passed=True, issues=[], summary={'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        )
        mock_validator.generate_security_report.return_value = "Security validation passed"
        
        # Mock ECS enhancer
        mock_enhancer = Mock()
        mock_enhancer_class.return_value = mock_enhancer
        mock_enhancer.find_ecs_task_role.return_value = 'ECSTaskRole'
        
        # Create mock args
        args = Mock()
        args.input_template = "test-template.yaml"
        
        with patch('builtins.print') as mock_print:
            result = run_security_validation(args)
            
            assert result == 0
            mock_print.assert_called()
    
    @patch('iam_validation.cli.CloudFormationTemplateManager')
    def test_run_security_validation_failure(self, mock_manager_class):
        """Test security validation with failure."""
        # Mock template manager to raise exception
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager
        mock_manager.load_template.side_effect = Exception("Template load failed")
        
        args = Mock()
        args.input_template = "test-template.yaml"
        
        with patch('sys.stderr', new_callable=StringIO):
            result = run_security_validation(args)
            assert result == 1
    
    @patch('iam_validation.cli.BedrockAgentCoreIntegrator')
    def test_run_main_workflow_success(self, mock_integrator_class):
        """Test successful main workflow execution."""
        # Mock integrator
        mock_integrator = Mock()
        mock_integrator_class.return_value = mock_integrator
        
        # Mock successful result
        validation_result = ValidationResult(
            success=True,
            temporary_role_arn='arn:aws:iam::123456789012:role/test-role',
            attached_policies=['Policy1'],
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
        mock_integrator.run_validation_and_update.return_value = integration_result
        mock_integrator.get_process_summary.return_value = "Process completed successfully"
        
        # Create mock args
        args = Mock()
        args.aws_profile = None
        args.aws_region = 'us-east-1'
        args.input_template = 'input.yaml'
        args.output_template = 'output.yaml'
        args.policy_directory = 'policies'
        args.validate_prerequisites = False
        args.skip_validation = False
        args.skip_template_update = False
        args.dry_run = False
        args.quiet = False
        args.verbose = False
        
        with patch('builtins.print') as mock_print:
            result = run_main_workflow(args)
            
            assert result == 0
            mock_integrator.run_validation_and_update.assert_called_once()
    
    @patch('iam_validation.cli.BedrockAgentCoreIntegrator')
    def test_run_main_workflow_prerequisites_validation(self, mock_integrator_class):
        """Test main workflow with prerequisites validation."""
        # Mock integrator
        mock_integrator = Mock()
        mock_integrator_class.return_value = mock_integrator
        mock_integrator.validate_prerequisites.return_value = []  # No issues
        
        args = Mock()
        args.aws_profile = None
        args.aws_region = 'us-east-1'
        args.input_template = 'input.yaml'
        args.output_template = 'output.yaml'
        args.policy_directory = 'policies'
        args.validate_prerequisites = True
        args.verbose = False
        
        with patch('builtins.print') as mock_print:
            result = run_main_workflow(args)
            
            assert result == 0
            mock_integrator.validate_prerequisites.assert_called_once()
    
    @patch('iam_validation.cli.BedrockAgentCoreIntegrator')
    def test_run_main_workflow_prerequisites_failure(self, mock_integrator_class):
        """Test main workflow with prerequisites validation failure."""
        # Mock integrator
        mock_integrator = Mock()
        mock_integrator_class.return_value = mock_integrator
        mock_integrator.validate_prerequisites.return_value = ['Missing file', 'Invalid config']
        
        args = Mock()
        args.aws_profile = None
        args.aws_region = 'us-east-1'
        args.input_template = 'input.yaml'
        args.output_template = 'output.yaml'
        args.policy_directory = 'policies'
        args.validate_prerequisites = True
        args.verbose = False
        
        with patch('builtins.print') as mock_print:
            result = run_main_workflow(args)
            
            assert result == 1
    
    def test_run_main_workflow_keyboard_interrupt(self):
        """Test main workflow with keyboard interrupt."""
        args = Mock()
        args.aws_profile = None
        args.aws_region = 'us-east-1'
        args.input_template = 'input.yaml'
        args.output_template = 'output.yaml'
        args.policy_directory = 'policies'
        args.validate_prerequisites = False
        args.verbose = False
        
        with patch('iam_validation.cli.BedrockAgentCoreIntegrator') as mock_integrator_class:
            mock_integrator_class.side_effect = KeyboardInterrupt()
            
            with patch('sys.stderr', new_callable=StringIO):
                result = run_main_workflow(args)
                assert result == 130  # SIGINT exit code
    
    def test_show_configuration(self):
        """Test configuration display."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create policy directory with some files
            policy_dir = temp_path / "policies"
            policy_dir.mkdir()
            
            policy_file = policy_dir / "test-policy.json"
            policy_file.write_text('{"Version": "2012-10-17"}')
            
            input_template = temp_path / "input.yaml"
            input_template.write_text("test template")
            
            args = Mock()
            args.aws_profile = 'test-profile'
            args.aws_region = 'us-west-2'
            args.input_template = str(input_template)
            args.output_template = str(temp_path / "output.yaml")
            args.policy_directory = str(policy_dir)
            args.dry_run = True
            args.skip_validation = False
            args.skip_template_update = False
            args.security_only = False
            args.verbose = True
            args.log_file = 'test.log'
            
            with patch('builtins.print') as mock_print:
                show_configuration(args)
                
                # Verify configuration was printed
                mock_print.assert_called()
                call_args = [call[0][0] for call in mock_print.call_args_list]
                config_output = '\n'.join(call_args)
                
                assert 'test-profile' in config_output
                assert 'us-west-2' in config_output
                assert 'True' in config_output  # dry_run
    
    @patch('iam_validation.cli.setup_logging')
    @patch('iam_validation.cli.validate_arguments')
    @patch('iam_validation.cli.run_main_workflow')
    def test_main_success(self, mock_run_workflow, mock_validate_args, mock_setup_logging):
        """Test successful main function execution."""
        mock_validate_args.return_value = True
        mock_run_workflow.return_value = 0
        
        with patch('sys.argv', ['cli.py']):
            result = main()
            assert result == 0
    
    @patch('iam_validation.cli.setup_logging')
    @patch('iam_validation.cli.validate_arguments')
    def test_main_validation_failure(self, mock_validate_args, mock_setup_logging):
        """Test main function with argument validation failure."""
        mock_validate_args.return_value = False
        
        with patch('sys.argv', ['cli.py']):
            result = main()
            assert result == 1
    
    @patch('iam_validation.cli.setup_logging')
    @patch('iam_validation.cli.show_configuration')
    def test_main_show_config(self, mock_show_config, mock_setup_logging):
        """Test main function with show configuration option."""
        with patch('sys.argv', ['cli.py', '--show-config']):
            result = main()
            assert result == 0
            mock_show_config.assert_called_once()
    
    @patch('iam_validation.cli.setup_logging')
    @patch('iam_validation.cli.validate_arguments')
    @patch('iam_validation.cli.run_security_validation')
    def test_main_security_only(self, mock_run_security, mock_validate_args, mock_setup_logging):
        """Test main function with security-only option."""
        mock_validate_args.return_value = True
        mock_run_security.return_value = 0
        
        with patch('sys.argv', ['cli.py', '--security-only', '--input-template', 'test.yaml']):
            result = main()
            assert result == 0
            mock_run_security.assert_called_once()
    
    def test_setup_logging_basic(self):
        """Test basic logging setup."""
        from ..cli import setup_logging
        
        with patch('logging.basicConfig') as mock_basic_config:
            setup_logging()
            mock_basic_config.assert_called_once()
    
    def test_setup_logging_with_file(self):
        """Test logging setup with file handler."""
        from ..cli import setup_logging
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            with patch('logging.basicConfig'), \
                 patch('logging.FileHandler') as mock_file_handler, \
                 patch('logging.getLogger') as mock_get_logger:
                
                mock_logger = Mock()
                mock_get_logger.return_value = mock_logger
                
                setup_logging(verbose=True, log_file=temp_path)
                
                mock_file_handler.assert_called_once_with(temp_path)
                mock_logger.addHandler.assert_called()
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestCLIIntegration:
    """Integration tests for CLI functionality."""
    
    def test_cli_help(self):
        """Test CLI help output."""
        parser = create_parser()
        
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            try:
                parser.parse_args(['--help'])
            except SystemExit as e:
                # Help should exit with code 0
                assert e.code == 0
    
    def test_cli_version_handling(self):
        """Test CLI version and error handling."""
        parser = create_parser()
        
        # Test invalid argument
        with patch('sys.stderr', new_callable=StringIO):
            try:
                parser.parse_args(['--invalid-argument'])
            except SystemExit as e:
                # Invalid arguments should exit with non-zero code
                assert e.code != 0
    
    @patch('deployment_scripts.iam_validation.cli.BedrockAgentCoreIntegrator')
    def test_end_to_end_dry_run(self, mock_integrator_class):
        """Test end-to-end dry run execution."""
        # Mock integrator for dry run
        mock_integrator = Mock()
        mock_integrator_class.return_value = mock_integrator
        
        validation_result = ValidationResult(
            success=True,
            temporary_role_arn='arn:aws:iam::123456789012:role/test-role',
            attached_policies=['Policy1'],
            errors=[],
            cleanup_successful=True
        )
        
        update_result = UpdateResult(
            success=True,
            output_file='[DRY RUN] output.yaml',
            new_resources_added=['BedrockRole'],
            existing_resources_modified=['ECSRole'],
            errors=[]
        )
        
        integration_result = IntegrationResult.from_results(validation_result, update_result)
        mock_integrator.run_validation_and_update.return_value = integration_result
        mock_integrator.get_process_summary.return_value = "Dry run completed successfully"
        
        with patch('sys.argv', ['cli.py', '--dry-run', '--quiet']):
            result = main()
            assert result == 0
            
            # Verify dry run was called
            mock_integrator.run_validation_and_update.assert_called_once_with(
                skip_validation=False,
                skip_template_update=False,
                dry_run=True
            )