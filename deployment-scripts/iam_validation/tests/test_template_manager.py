"""
Unit tests for CloudFormationTemplateManager.
"""

import pytest
import yaml
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
import tempfile
import os

from ..template_manager import CloudFormationTemplateManager
from ..error_handling import TemplateException
from ..config import CONFIG


class TestCloudFormationTemplateManager:
    """Test cases for CloudFormationTemplateManager class."""
    
    @pytest.fixture
    def sample_template(self):
        """Sample CloudFormation template for testing."""
        return {
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
    
    @pytest.fixture
    def temp_template_files(self, sample_template):
        """Create temporary template files for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create valid template file
            input_file = temp_path / "input-template.yaml"
            with open(input_file, 'w') as f:
                yaml.dump(sample_template, f)
            
            # Create invalid YAML file
            invalid_file = temp_path / "invalid-template.yaml"
            with open(invalid_file, 'w') as f:
                f.write('invalid: yaml: content: [')
            
            # Create invalid structure file
            invalid_structure = {'NotATemplate': 'true'}
            invalid_structure_file = temp_path / "invalid-structure.yaml"
            with open(invalid_structure_file, 'w') as f:
                yaml.dump(invalid_structure, f)
            
            yield {
                'input_file': str(input_file),
                'invalid_file': str(invalid_file),
                'invalid_structure_file': str(invalid_structure_file),
                'output_file': str(temp_path / "output-template.yaml")
            }
    
    @pytest.fixture
    def template_manager(self, temp_template_files):
        """Create CloudFormationTemplateManager with temp files."""
        return CloudFormationTemplateManager(
            input_template_path=temp_template_files['input_file'],
            output_template_path=temp_template_files['output_file']
        )
    
    def test_init_default_paths(self):
        """Test initialization with default paths."""
        manager = CloudFormationTemplateManager()
        assert str(manager.input_template_path) == CONFIG['template_input']
        assert str(manager.output_template_path) == CONFIG['template_output']
    
    def test_init_custom_paths(self, temp_template_files):
        """Test initialization with custom paths."""
        manager = CloudFormationTemplateManager(
            input_template_path=temp_template_files['input_file'],
            output_template_path=temp_template_files['output_file']
        )
        assert str(manager.input_template_path) == temp_template_files['input_file']
        assert str(manager.output_template_path) == temp_template_files['output_file']
    
    def test_load_template_success(self, template_manager, sample_template):
        """Test successful template loading."""
        template = template_manager.load_template()
        
        assert template['AWSTemplateFormatVersion'] == '2010-09-09'
        assert 'Resources' in template
        assert len(template['Resources']) == 2
        assert 'ECSTaskRole' in template['Resources']
    
    def test_load_template_file_not_found(self, template_manager):
        """Test loading non-existent template file."""
        with pytest.raises(TemplateException) as exc_info:
            template_manager.load_template("/non/existent/file.yaml")
        
        assert "Template file not found" in str(exc_info.value)
    
    def test_load_template_invalid_yaml(self, temp_template_files):
        """Test loading template with invalid YAML."""
        manager = CloudFormationTemplateManager(
            input_template_path=temp_template_files['invalid_file']
        )
        
        with pytest.raises(TemplateException) as exc_info:
            manager.load_template()
        
        assert "Invalid YAML syntax" in str(exc_info.value)
    
    def test_load_template_invalid_structure(self, temp_template_files):
        """Test loading template with invalid CloudFormation structure."""
        manager = CloudFormationTemplateManager(
            input_template_path=temp_template_files['invalid_structure_file']
        )
        
        with pytest.raises(TemplateException) as exc_info:
            manager.load_template()
        
        assert "missing required section" in str(exc_info.value)
    
    @patch('deployment_scripts.iam_validation.template_manager.PolicyDocumentProcessor')
    def test_add_bedrock_agentcore_role_success(self, mock_processor_class, template_manager, sample_template):
        """Test successful addition of Bedrock AgentCore role."""
        # Mock policy processor
        mock_processor = Mock()
        mock_processor_class.return_value = mock_processor
        
        sample_policies = [
            {
                'file_name': 'test-policy.json',
                'cloudformation_name': 'TestPolicy',
                'policy_document': {
                    'Version': '2012-10-17',
                    'Statement': [{'Effect': 'Allow', 'Action': ['s3:GetObject'], 'Resource': '*'}]
                }
            }
        ]
        mock_processor.load_policy_files.return_value = sample_policies
        mock_processor.convert_to_inline_policy.return_value = {
            'PolicyName': 'TestPolicy',
            'PolicyDocument': sample_policies[0]['policy_document']
        }
        
        updated_template = template_manager.add_bedrock_agentcore_role(sample_template)
        
        # Verify Bedrock role was added
        assert 'BedrockAgentCoreRuntimeRole' in updated_template['Resources']
        bedrock_role = updated_template['Resources']['BedrockAgentCoreRuntimeRole']
        
        assert bedrock_role['Type'] == 'AWS::IAM::Role'
        assert 'AssumeRolePolicyDocument' in bedrock_role['Properties']
        assert 'Policies' in bedrock_role['Properties']
        assert len(bedrock_role['Properties']['Policies']) == 1
        assert 'Tags' in bedrock_role['Properties']
        
        # Verify original template wasn't modified
        assert 'BedrockAgentCoreRuntimeRole' not in sample_template['Resources']
    
    def test_update_ecs_permissions_success(self, template_manager, sample_template):
        """Test successful ECS permissions update."""
        updated_template = template_manager.update_ecs_permissions(sample_template)
        
        # Verify ECS role was updated
        ecs_role = updated_template['Resources']['ECSTaskRole']
        policies = ecs_role['Properties']['Policies']
        
        # Should have original policy plus new Bedrock policy
        assert len(policies) == 2
        
        # Find the Bedrock policy
        bedrock_policy = None
        for policy in policies:
            if 'bedrock-agentcore' in str(policy):
                bedrock_policy = policy
                break
        
        assert bedrock_policy is not None
        assert bedrock_policy['PolicyName'] == 'BedrockAgentCoreInvokePolicy'
        
        # Verify original template wasn't modified
        assert len(sample_template['Resources']['ECSTaskRole']['Properties']['Policies']) == 1
    
    def test_update_ecs_permissions_no_ecs_role(self, template_manager):
        """Test ECS permissions update when no ECS role exists."""
        template_without_ecs = {
            'AWSTemplateFormatVersion': '2010-09-09',
            'Resources': {
                'TestBucket': {
                    'Type': 'AWS::S3::Bucket'
                }
            }
        }
        
        with pytest.raises(TemplateException) as exc_info:
            template_manager.update_ecs_permissions(template_without_ecs)
        
        assert "Could not find ECS task role" in str(exc_info.value)
    
    def test_update_ecs_permissions_existing_bedrock_policy(self, template_manager, sample_template):
        """Test ECS permissions update when Bedrock policy already exists."""
        # Add existing Bedrock policy to template
        existing_bedrock_policy = {
            'PolicyName': 'ExistingBedrockPolicy',
            'PolicyDocument': {
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Effect': 'Allow',
                        'Action': ['bedrock-agentcore:InvokeAgent'],
                        'Resource': ['arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/old-pattern']
                    }
                ]
            }
        }
        sample_template['Resources']['ECSTaskRole']['Properties']['Policies'].append(existing_bedrock_policy)
        
        updated_template = template_manager.update_ecs_permissions(sample_template)
        
        # Should still have 2 policies (original + updated Bedrock policy)
        ecs_role = updated_template['Resources']['ECSTaskRole']
        policies = ecs_role['Properties']['Policies']
        assert len(policies) == 2
        
        # Verify the Bedrock policy was updated with correct resource
        bedrock_policy = policies[1]  # The existing Bedrock policy
        statement = bedrock_policy['PolicyDocument']['Statement'][0]
        resources = statement['Resource']
        
        # Should contain both old and new resource patterns
        assert len(resources) == 2
    
    def test_save_template_success(self, template_manager, sample_template, temp_template_files):
        """Test successful template saving."""
        result = template_manager.save_template(sample_template)
        
        assert result is True
        
        # Verify file was created and contains correct content
        output_path = Path(temp_template_files['output_file'])
        assert output_path.exists()
        
        with open(output_path, 'r') as f:
            saved_template = yaml.safe_load(f)
        
        assert saved_template['AWSTemplateFormatVersion'] == '2010-09-09'
        assert len(saved_template['Resources']) == 2
    
    def test_save_template_custom_path(self, template_manager, sample_template, temp_template_files):
        """Test saving template to custom path."""
        custom_path = str(Path(temp_template_files['output_file']).parent / "custom-output.yaml")
        
        result = template_manager.save_template(sample_template, custom_path)
        
        assert result is True
        assert Path(custom_path).exists()
    
    def test_find_ecs_task_role_by_service(self, template_manager, sample_template):
        """Test finding ECS task role by service principal."""
        role_name = template_manager._find_ecs_task_role(sample_template)
        assert role_name == 'ECSTaskRole'
    
    def test_find_ecs_task_role_by_name(self, template_manager):
        """Test finding ECS task role by naming convention."""
        template_with_named_role = {
            'Resources': {
                'MyECSTaskRole': {
                    'Type': 'AWS::IAM::Role',
                    'Properties': {
                        'AssumeRolePolicyDocument': {
                            'Statement': [
                                {
                                    'Principal': {'Service': 'lambda.amazonaws.com'}
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        role_name = template_manager._find_ecs_task_role(template_with_named_role)
        assert role_name == 'MyECSTaskRole'
    
    def test_find_ecs_task_role_not_found(self, template_manager):
        """Test ECS task role not found."""
        template_without_ecs = {
            'Resources': {
                'LambdaRole': {
                    'Type': 'AWS::IAM::Role',
                    'Properties': {
                        'AssumeRolePolicyDocument': {
                            'Statement': [
                                {
                                    'Principal': {'Service': 'lambda.amazonaws.com'}
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        role_name = template_manager._find_ecs_task_role(template_without_ecs)
        assert role_name is None
    
    def test_get_template_summary(self, template_manager, sample_template):
        """Test template summary generation."""
        summary = template_manager.get_template_summary(sample_template)
        
        assert summary['total_resources'] == 2
        assert summary['total_parameters'] == 1
        assert summary['total_outputs'] == 0
        assert 'AWS::IAM::Role' in summary['resource_types']
        assert 'AWS::S3::Bucket' in summary['resource_types']
        assert 'ECSTaskRole' in summary['iam_roles']
        assert summary['template_version'] == '2010-09-09'
    
    def test_validate_template_structure_valid(self, template_manager, sample_template):
        """Test validation of valid template structure."""
        issues = template_manager.validate_template_structure(sample_template)
        assert len(issues) == 0
    
    def test_validate_template_structure_invalid(self, template_manager):
        """Test validation of invalid template structure."""
        invalid_template = {
            'Resources': {}  # Missing AWSTemplateFormatVersion, empty Resources
        }
        
        issues = template_manager.validate_template_structure(invalid_template)
        
        assert len(issues) >= 2
        assert any("Missing AWSTemplateFormatVersion" in issue for issue in issues)
        assert any("Resources section is empty" in issue for issue in issues)