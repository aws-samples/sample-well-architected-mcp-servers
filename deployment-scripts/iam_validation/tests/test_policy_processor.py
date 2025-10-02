"""
Unit tests for PolicyDocumentProcessor.
"""

import json
import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
import tempfile
import os

from ..policy_processor import PolicyDocumentProcessor
from ..error_handling import PolicyException, ValidationException
from ..config import CONFIG


class TestPolicyDocumentProcessor:
    """Test cases for PolicyDocumentProcessor class."""
    
    @pytest.fixture
    def temp_policy_dir(self):
        """Create temporary directory with test policy files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create valid policy file
            valid_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:GetObject"],
                        "Resource": "*"
                    }
                ]
            }
            
            valid_policy_path = temp_path / "valid-policy.json"
            with open(valid_policy_path, 'w') as f:
                json.dump(valid_policy, f)
            
            # Create invalid JSON file
            invalid_json_path = temp_path / "invalid-json.json"
            with open(invalid_json_path, 'w') as f:
                f.write('{"invalid": json}')
            
            # Create invalid policy structure
            invalid_policy = {"NotAPolicy": "true"}
            invalid_policy_path = temp_path / "invalid-policy.json"
            with open(invalid_policy_path, 'w') as f:
                json.dump(invalid_policy, f)
            
            yield temp_path
    
    @pytest.fixture
    def processor(self, temp_policy_dir):
        """Create PolicyDocumentProcessor with temp directory."""
        return PolicyDocumentProcessor(str(temp_policy_dir))
    
    def test_init_default_directory(self):
        """Test initialization with default directory."""
        processor = PolicyDocumentProcessor()
        assert str(processor.policy_directory) == CONFIG['policy_directory']
    
    def test_init_custom_directory(self, temp_policy_dir):
        """Test initialization with custom directory."""
        processor = PolicyDocumentProcessor(str(temp_policy_dir))
        assert processor.policy_directory == temp_policy_dir
    
    def test_load_policy_files_success(self, temp_policy_dir):
        """Test successful loading of policy files."""
        # Create the expected policy files
        for policy_file in CONFIG['policy_files']:
            policy_path = temp_policy_dir / policy_file
            valid_policy = {
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Action": ["sts:GetCallerIdentity"], "Resource": "*"}]
            }
            with open(policy_path, 'w') as f:
                json.dump(valid_policy, f)
        
        processor = PolicyDocumentProcessor(str(temp_policy_dir))
        policies = processor.load_policy_files()
        
        assert len(policies) == len(CONFIG['policy_files'])
        for policy in policies:
            assert 'file_name' in policy
            assert 'policy_document' in policy
            assert 'cloudformation_name' in policy
            assert policy['policy_document']['Version'] == '2012-10-17'
    
    def test_load_policy_files_directory_not_exists(self):
        """Test loading from non-existent directory."""
        processor = PolicyDocumentProcessor("/non/existent/path")
        
        with pytest.raises(PolicyException) as exc_info:
            processor.load_policy_files()
        
        assert "Policy directory does not exist" in str(exc_info.value)
    
    def test_load_policy_files_missing_file(self, temp_policy_dir):
        """Test loading when required policy file is missing."""
        processor = PolicyDocumentProcessor(str(temp_policy_dir))
        
        with pytest.raises(PolicyException) as exc_info:
            processor.load_policy_files()
        
        assert "Required policy file not found" in str(exc_info.value)
    
    def test_load_policy_files_invalid_json(self, temp_policy_dir):
        """Test loading file with invalid JSON."""
        # Create file with invalid JSON
        invalid_file = temp_policy_dir / CONFIG['policy_files'][0]
        with open(invalid_file, 'w') as f:
            f.write('{"invalid": json}')
        
        processor = PolicyDocumentProcessor(str(temp_policy_dir))
        
        with pytest.raises(PolicyException) as exc_info:
            processor.load_policy_files()
        
        assert "Invalid JSON in policy file" in str(exc_info.value)
    
    def test_load_policy_files_missing_required_fields(self, temp_policy_dir):
        """Test loading policy file missing required fields."""
        # Create file missing Version field
        invalid_policy = {"Statement": [{"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "*"}]}
        invalid_file = temp_policy_dir / CONFIG['policy_files'][0]
        with open(invalid_file, 'w') as f:
            json.dump(invalid_policy, f)
        
        processor = PolicyDocumentProcessor(str(temp_policy_dir))
        
        with pytest.raises(PolicyException) as exc_info:
            processor.load_policy_files()
        
        assert "missing required fields" in str(exc_info.value)
    
    @patch('boto3.client')
    def test_validate_policy_syntax_success(self, mock_boto_client, processor):
        """Test successful policy syntax validation."""
        mock_iam = Mock()
        mock_boto_client.return_value = mock_iam
        mock_iam.simulate_principal_policy.return_value = {'EvaluationResults': []}
        
        policy = {
            'file_name': 'test-policy.json',
            'policy_document': {
                'Version': '2012-10-17',
                'Statement': [{'Effect': 'Allow', 'Action': ['s3:GetObject'], 'Resource': '*'}]
            }
        }
        
        result = processor.validate_policy_syntax(policy)
        assert result is True
    
    @patch('boto3.client')
    def test_validate_policy_syntax_too_large(self, mock_boto_client, processor):
        """Test policy validation with oversized policy."""
        mock_iam = Mock()
        mock_boto_client.return_value = mock_iam
        
        # Create oversized policy
        large_statement = {
            'Effect': 'Allow',
            'Action': ['s3:GetObject'],
            'Resource': 'x' * CONFIG['max_policy_size']  # Exceed size limit
        }
        
        policy = {
            'file_name': 'large-policy.json',
            'policy_document': {
                'Version': '2012-10-17',
                'Statement': [large_statement]
            }
        }
        
        with pytest.raises(ValidationException) as exc_info:
            processor.validate_policy_syntax(policy)
        
        assert "Policy size" in str(exc_info.value)
        assert "exceeds maximum" in str(exc_info.value)
    
    def test_basic_policy_validation_success(self, processor):
        """Test basic policy validation without AWS API."""
        policy_doc = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Effect': 'Allow',
                    'Action': ['s3:GetObject'],
                    'Resource': '*'
                }
            ]
        }
        
        result = processor._basic_policy_validation(policy_doc)
        assert result is True
    
    def test_basic_policy_validation_missing_version(self, processor):
        """Test basic validation with missing version."""
        policy_doc = {
            'Statement': [{'Effect': 'Allow', 'Action': ['s3:GetObject'], 'Resource': '*'}]
        }
        
        with pytest.raises(ValidationException) as exc_info:
            processor._basic_policy_validation(policy_doc)
        
        assert "missing required field: Version" in str(exc_info.value)
    
    def test_basic_policy_validation_invalid_effect(self, processor):
        """Test basic validation with invalid effect."""
        policy_doc = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Effect': 'Maybe',  # Invalid effect
                    'Action': ['s3:GetObject'],
                    'Resource': '*'
                }
            ]
        }
        
        with pytest.raises(ValidationException) as exc_info:
            processor._basic_policy_validation(policy_doc)
        
        assert "invalid Effect: Maybe" in str(exc_info.value)
    
    def test_convert_to_inline_policy(self, processor):
        """Test conversion to CloudFormation inline policy format."""
        policy = {
            'file_name': 'test-policy.json',
            'policy_document': {
                'Version': '2012-10-17',
                'Statement': [{'Effect': 'Allow', 'Action': ['s3:GetObject'], 'Resource': '*'}]
            }
        }
        
        result = processor.convert_to_inline_policy(policy, 'TestPolicy')
        
        assert result['PolicyName'] == 'TestPolicy'
        assert result['PolicyDocument'] == policy['policy_document']
    
    def test_get_policy_summary(self, processor):
        """Test policy summary generation."""
        policies = [
            {
                'file_name': 'policy1.json',
                'policy_document': {
                    'Version': '2012-10-17',
                    'Statement': [{'Effect': 'Allow', 'Action': ['s3:GetObject', 's3:PutObject'], 'Resource': '*'}]
                }
            },
            {
                'file_name': 'policy2.json',
                'policy_document': {
                    'Version': '2012-10-17',
                    'Statement': [{'Effect': 'Allow', 'Action': ['iam:GetUser'], 'Resource': '*'}]
                }
            }
        ]
        
        summary = processor.get_policy_summary(policies)
        
        assert summary['total_policies'] == 2
        assert summary['total_size_bytes'] > 0
        assert 's3' in summary['services_used']
        assert 'iam' in summary['services_used']
        assert summary['action_counts_by_service']['s3'] == 2
        assert summary['action_counts_by_service']['iam'] == 1
        assert len(summary['policy_files']) == 2