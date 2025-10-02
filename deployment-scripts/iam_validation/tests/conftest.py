"""
Pytest configuration and shared fixtures for IAM validation tests.
"""

import pytest
import tempfile
import json
import yaml
from pathlib import Path
from unittest.mock import Mock, patch

# Test configuration
TEST_CONFIG = {
    'aws_region': 'us-east-1',
    'policy_files': [
        'test-policy-1.json',
        'test-policy-2.json',
        'test-policy-3.json'
    ],
    'bedrock_role_resource_name': 'BedrockAgentCoreRuntimeRole',
    'temporary_role_prefix': 'test-coa-temp-validation'
}


@pytest.fixture(scope="session")
def sample_policy_document():
    """Sample IAM policy document for testing."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "sts:GetCallerIdentity",
                    "ec2:DescribeInstances"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject"
                ],
                "Resource": "arn:aws:s3:::test-bucket/*"
            }
        ]
    }


@pytest.fixture(scope="session")
def sample_cloudformation_template():
    """Sample CloudFormation template for testing."""
    return {
        'AWSTemplateFormatVersion': '2010-09-09',
        'Description': 'Test CloudFormation template for IAM validation',
        'Parameters': {
            'Environment': {
                'Type': 'String',
                'Default': 'test',
                'AllowedValues': ['dev', 'test', 'prod']
            }
        },
        'Resources': {
            'ECSTaskRole': {
                'Type': 'AWS::IAM::Role',
                'Properties': {
                    'RoleName': '!Sub \'${AWS::StackName}-ecs-task-role\'',
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
                            'PolicyName': 'S3AccessPolicy',
                            'PolicyDocument': {
                                'Version': '2012-10-17',
                                'Statement': [
                                    {
                                        'Effect': 'Allow',
                                        'Action': [
                                            's3:GetObject',
                                            's3:PutObject'
                                        ],
                                        'Resource': 'arn:aws:s3:::test-bucket/*'
                                    }
                                ]
                            }
                        }
                    ],
                    'Tags': [
                        {
                            'Key': 'Environment',
                            'Value': '!Ref Environment'
                        },
                        {
                            'Key': 'Component',
                            'Value': 'ECS'
                        }
                    ]
                }
            },
            'TestS3Bucket': {
                'Type': 'AWS::S3::Bucket',
                'Properties': {
                    'BucketName': '!Sub \'${AWS::StackName}-test-bucket\'',
                    'PublicAccessBlockConfiguration': {
                        'BlockPublicAcls': True,
                        'BlockPublicPolicy': True,
                        'IgnorePublicAcls': True,
                        'RestrictPublicBuckets': True
                    }
                }
            }
        },
        'Outputs': {
            'ECSTaskRoleArn': {
                'Description': 'ARN of the ECS task role',
                'Value': '!GetAtt ECSTaskRole.Arn',
                'Export': {
                    'Name': '!Sub \'${AWS::StackName}-ecs-task-role-arn\''
                }
            }
        }
    }


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace with policy files and templates."""
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        
        # Create policy directory
        policy_dir = workspace / "policies"
        policy_dir.mkdir()
        
        # Create sample policy files
        sample_policies = {
            'test-policy-1.json': {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["sts:GetCallerIdentity"],
                        "Resource": "*"
                    }
                ]
            },
            'test-policy-2.json': {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["ec2:DescribeInstances"],
                        "Resource": "*"
                    }
                ]
            },
            'test-policy-3.json': {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:ListBucket"],
                        "Resource": "arn:aws:s3:::test-bucket"
                    }
                ]
            }
        }
        
        for filename, policy_content in sample_policies.items():
            policy_path = policy_dir / filename
            with open(policy_path, 'w') as f:
                json.dump(policy_content, f, indent=2)
        
        # Create input template
        input_template_path = workspace / "input-template.yaml"
        
        # Create output template path (will be created by tests)
        output_template_path = workspace / "output-template.yaml"
        
        yield {
            'workspace': workspace,
            'policy_directory': str(policy_dir),
            'input_template': str(input_template_path),
            'output_template': str(output_template_path),
            'policy_files': list(sample_policies.keys())
        }


@pytest.fixture
def mock_aws_session():
    """Mock AWS session and clients for testing."""
    with patch('boto3.Session') as mock_session_class:
        # Create mock session
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Create mock IAM client
        mock_iam_client = Mock()
        mock_session.client.return_value = mock_iam_client
        
        # Configure mock IAM client responses
        mock_iam_client.create_role.return_value = {
            'Role': {
                'Arn': 'arn:aws:iam::123456789012:role/test-temp-role',
                'RoleName': 'test-temp-role',
                'CreateDate': '2024-01-01T00:00:00Z'
            }
        }
        
        mock_iam_client.put_role_policy.return_value = {}
        
        mock_iam_client.list_role_policies.return_value = {
            'PolicyNames': ['TestPolicy1', 'TestPolicy2', 'TestPolicy3']
        }
        
        mock_iam_client.delete_role_policy.return_value = {}
        mock_iam_client.delete_role.return_value = {}
        
        mock_iam_client.get_user.return_value = {
            'User': {
                'UserName': 'test-user',
                'Arn': 'arn:aws:iam::123456789012:user/test-user'
            }
        }
        
        mock_iam_client.simulate_principal_policy.return_value = {
            'EvaluationResults': []
        }
        
        # Configure mock credentials
        mock_credentials = Mock()
        mock_credentials.access_key = 'test-access-key'
        mock_session.get_credentials.return_value = mock_credentials
        
        yield {
            'session': mock_session,
            'iam_client': mock_iam_client,
            'credentials': mock_credentials
        }


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    with patch.dict('deployment_scripts.iam_validation.config.CONFIG', TEST_CONFIG):
        yield TEST_CONFIG


@pytest.fixture
def sample_validation_result():
    """Sample validation result for testing."""
    from ..data_models import ValidationResult
    
    return ValidationResult(
        success=True,
        temporary_role_arn='arn:aws:iam::123456789012:role/test-temp-role',
        attached_policies=['TestPolicy1', 'TestPolicy2', 'TestPolicy3'],
        errors=[],
        cleanup_successful=True
    )


@pytest.fixture
def sample_update_result():
    """Sample update result for testing."""
    from ..data_models import UpdateResult
    
    return UpdateResult(
        success=True,
        output_file='test-output.yaml',
        new_resources_added=['BedrockAgentCoreRuntimeRole'],
        existing_resources_modified=['ECSTaskRole'],
        errors=[]
    )


@pytest.fixture
def sample_integration_result(sample_validation_result, sample_update_result):
    """Sample integration result for testing."""
    from ..data_models import IntegrationResult
    
    return IntegrationResult.from_results(
        sample_validation_result,
        sample_update_result
    )


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "aws: mark test as requiring AWS credentials"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names."""
    for item in items:
        # Mark integration tests
        if "integration" in item.nodeid.lower():
            item.add_marker(pytest.mark.integration)
        
        # Mark slow tests
        if any(keyword in item.name.lower() for keyword in ["large", "performance", "scaling"]):
            item.add_marker(pytest.mark.slow)
        
        # Mark AWS tests
        if any(keyword in item.name.lower() for keyword in ["aws", "iam", "real_"]):
            item.add_marker(pytest.mark.aws)


# Custom assertions for testing
def assert_valid_arn(arn_string, service=None, resource_type=None):
    """Assert that a string is a valid AWS ARN."""
    assert arn_string.startswith('arn:aws:'), f"Invalid ARN format: {arn_string}"
    
    parts = arn_string.split(':')
    assert len(parts) >= 6, f"ARN has insufficient parts: {arn_string}"
    
    if service:
        assert parts[2] == service, f"Expected service {service}, got {parts[2]}"
    
    if resource_type:
        resource_part = parts[5]
        if '/' in resource_part:
            actual_resource_type = resource_part.split('/')[0]
        else:
            actual_resource_type = resource_part.split(':')[0] if ':' in resource_part else resource_part
        assert actual_resource_type == resource_type, f"Expected resource type {resource_type}, got {actual_resource_type}"


def assert_valid_policy_document(policy_doc):
    """Assert that a dictionary is a valid IAM policy document."""
    assert isinstance(policy_doc, dict), "Policy document must be a dictionary"
    assert 'Version' in policy_doc, "Policy document must have Version field"
    assert 'Statement' in policy_doc, "Policy document must have Statement field"
    
    statements = policy_doc['Statement']
    if not isinstance(statements, list):
        statements = [statements]
    
    for statement in statements:
        assert 'Effect' in statement, "Statement must have Effect field"
        assert statement['Effect'] in ['Allow', 'Deny'], f"Invalid Effect: {statement['Effect']}"
        assert 'Action' in statement or 'NotAction' in statement, "Statement must have Action or NotAction"


def assert_cloudformation_resource(resource, resource_type):
    """Assert that a dictionary is a valid CloudFormation resource."""
    assert isinstance(resource, dict), "Resource must be a dictionary"
    assert 'Type' in resource, "Resource must have Type field"
    assert resource['Type'] == resource_type, f"Expected type {resource_type}, got {resource['Type']}"
    
    if resource_type == 'AWS::IAM::Role':
        assert 'Properties' in resource, "IAM Role must have Properties"
        properties = resource['Properties']
        assert 'AssumeRolePolicyDocument' in properties, "IAM Role must have AssumeRolePolicyDocument"


# Export custom assertions for use in tests
pytest.assert_valid_arn = assert_valid_arn
pytest.assert_valid_policy_document = assert_valid_policy_document
pytest.assert_cloudformation_resource = assert_cloudformation_resource