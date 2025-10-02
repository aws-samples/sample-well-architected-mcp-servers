"""
Unit tests for SecurityValidator.
"""

import pytest
from ..security_validator import SecurityValidator, SecurityIssue, SecurityValidationResult
from ..config import CONFIG


class TestSecurityValidator:
    """Test cases for SecurityValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Create SecurityValidator instance."""
        return SecurityValidator()
    
    @pytest.fixture
    def sample_bedrock_role(self):
        """Sample Bedrock AgentCore role resource."""
        return {
            'Type': 'AWS::IAM::Role',
            'Properties': {
                'AssumeRolePolicyDocument': {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Effect': 'Allow',
                            'Principal': {
                                'Service': 'bedrock-agentcore.amazonaws.com'
                            },
                            'Action': 'sts:AssumeRole'
                        }
                    ]
                },
                'Policies': [
                    {
                        'PolicyName': 'AgentCoreRuntimeSTSPolicy',
                        'PolicyDocument': {
                            'Version': '2012-10-17',
                            'Statement': [
                                {
                                    'Effect': 'Allow',
                                    'Action': ['sts:GetCallerIdentity'],
                                    'Resource': '*'
                                }
                            ]
                        }
                    }
                ],
                'Tags': [
                    {'Key': 'Environment', 'Value': 'prod'},
                    {'Key': 'Component', 'Value': 'BedrockAgentCore'},
                    {'Key': 'Project', 'Value': 'CloudOptimization'}
                ]
            }
        }
    
    @pytest.fixture
    def sample_ecs_role(self):
        """Sample ECS task role resource."""
        return {
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
                        'PolicyName': 'BedrockAgentCoreInvokePolicy',
                        'PolicyDocument': {
                            'Version': '2012-10-17',
                            'Statement': [
                                {
                                    'Effect': 'Allow',
                                    'Action': ['bedrock-agentcore:InvokeAgent'],
                                    'Resource': ['arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/*']
                                }
                            ]
                        }
                    }
                ]
            }
        }
    
    def test_validate_bedrock_agentcore_role_success(self, validator, sample_bedrock_role):
        """Test successful Bedrock AgentCore role validation."""
        template = {
            'Resources': {
                'BedrockAgentCoreRuntimeRole': sample_bedrock_role
            }
        }
        
        result = validator.validate_bedrock_agentcore_role(template, 'BedrockAgentCoreRuntimeRole')
        
        # Should pass with minimal issues (maybe some low severity ones)
        high_issues = [i for i in result.issues if i.severity == 'HIGH']
        assert len(high_issues) == 0
        assert result.passed is True
    
    def test_validate_bedrock_agentcore_role_missing(self, validator):
        """Test validation when Bedrock role is missing."""
        template = {'Resources': {}}
        
        result = validator.validate_bedrock_agentcore_role(template, 'MissingRole')
        
        assert result.passed is False
        assert len(result.issues) >= 1
        assert any(issue.category == 'MISSING_RESOURCE' for issue in result.issues)
    
    def test_validate_bedrock_agentcore_role_wrong_type(self, validator):
        """Test validation when resource is not IAM role."""
        template = {
            'Resources': {
                'NotARole': {
                    'Type': 'AWS::S3::Bucket'
                }
            }
        }
        
        result = validator.validate_bedrock_agentcore_role(template, 'NotARole')
        
        assert result.passed is False
        assert any(issue.category == 'INVALID_RESOURCE_TYPE' for issue in result.issues)
    
    def test_validate_bedrock_agentcore_role_wrong_principal(self, validator, sample_bedrock_role):
        """Test validation with wrong service principal."""
        # Change principal to lambda instead of bedrock-agentcore
        sample_bedrock_role['Properties']['AssumeRolePolicyDocument']['Statement'][0]['Principal']['Service'] = 'lambda.amazonaws.com'
        
        template = {
            'Resources': {
                'BedrockAgentCoreRuntimeRole': sample_bedrock_role
            }
        }
        
        result = validator.validate_bedrock_agentcore_role(template, 'BedrockAgentCoreRuntimeRole')
        
        assert result.passed is False
        assert any(issue.category == 'INVALID_PRINCIPAL' for issue in result.issues)
    
    def test_validate_bedrock_agentcore_role_wildcard_principal(self, validator, sample_bedrock_role):
        """Test validation with wildcard principal."""
        # Set principal to wildcard
        sample_bedrock_role['Properties']['AssumeRolePolicyDocument']['Statement'][0]['Principal'] = '*'
        
        template = {
            'Resources': {
                'BedrockAgentCoreRuntimeRole': sample_bedrock_role
            }
        }
        
        result = validator.validate_bedrock_agentcore_role(template, 'BedrockAgentCoreRuntimeRole')
        
        assert result.passed is False
        assert any(issue.category == 'OVERPRIVILEGED' for issue in result.issues)
    
    def test_validate_bedrock_agentcore_role_managed_policies(self, validator, sample_bedrock_role):
        """Test validation with managed policies."""
        # Add managed policy
        sample_bedrock_role['Properties']['ManagedPolicyArns'] = [
            'arn:aws:iam::aws:policy/PowerUserAccess'
        ]
        
        template = {
            'Resources': {
                'BedrockAgentCoreRuntimeRole': sample_bedrock_role
            }
        }
        
        result = validator.validate_bedrock_agentcore_role(template, 'BedrockAgentCoreRuntimeRole')
        
        # Should have medium severity issue for managed policies
        medium_issues = [i for i in result.issues if i.severity == 'MEDIUM']
        assert any(issue.category == 'MANAGED_POLICIES' for issue in medium_issues)
    
    def test_validate_bedrock_agentcore_role_missing_tags(self, validator, sample_bedrock_role):
        """Test validation with missing tags."""
        # Remove tags
        del sample_bedrock_role['Properties']['Tags']
        
        template = {
            'Resources': {
                'BedrockAgentCoreRuntimeRole': sample_bedrock_role
            }
        }
        
        result = validator.validate_bedrock_agentcore_role(template, 'BedrockAgentCoreRuntimeRole')
        
        # Should have low severity issue for missing tags
        low_issues = [i for i in result.issues if i.severity == 'LOW']
        assert any(issue.category == 'MISSING_TAGS' for issue in low_issues)
    
    def test_validate_ecs_permissions_success(self, validator, sample_ecs_role):
        """Test successful ECS permissions validation."""
        template = {
            'Resources': {
                'ECSTaskRole': sample_ecs_role
            }
        }
        
        result = validator.validate_ecs_permissions(template, 'ECSTaskRole')
        
        # Should pass with minimal issues
        high_issues = [i for i in result.issues if i.severity == 'HIGH']
        assert len(high_issues) == 0
        assert result.passed is True
    
    def test_validate_ecs_permissions_missing_role(self, validator):
        """Test ECS validation when role is missing."""
        template = {'Resources': {}}
        
        result = validator.validate_ecs_permissions(template, 'MissingRole')
        
        assert result.passed is False
        assert any(issue.category == 'MISSING_RESOURCE' for issue in result.issues)
    
    def test_validate_ecs_permissions_missing_bedrock_permission(self, validator):
        """Test ECS validation when Bedrock permission is missing."""
        ecs_role_without_bedrock = {
            'Type': 'AWS::IAM::Role',
            'Properties': {
                'Policies': [
                    {
                        'PolicyName': 'S3Policy',
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
        }
        
        template = {
            'Resources': {
                'ECSTaskRole': ecs_role_without_bedrock
            }
        }
        
        result = validator.validate_ecs_permissions(template, 'ECSTaskRole')
        
        assert result.passed is False
        assert any(issue.category == 'MISSING_PERMISSION' for issue in result.issues)
    
    def test_validate_ecs_permissions_improper_resource_scope(self, validator, sample_ecs_role):
        """Test ECS validation with improper resource scope."""
        # Change resource to wildcard
        sample_ecs_role['Properties']['Policies'][0]['PolicyDocument']['Statement'][0]['Resource'] = ['*']
        
        template = {
            'Resources': {
                'ECSTaskRole': sample_ecs_role
            }
        }
        
        result = validator.validate_ecs_permissions(template, 'ECSTaskRole')
        
        assert result.passed is False
        assert any(issue.category == 'IMPROPER_RESOURCE_SCOPE' for issue in result.issues)
    
    def test_validate_ecs_permissions_admin_permissions(self, validator):
        """Test ECS validation with admin permissions."""
        ecs_role_with_admin = {
            'Type': 'AWS::IAM::Role',
            'Properties': {
                'Policies': [
                    {
                        'PolicyName': 'AdminPolicy',
                        'PolicyDocument': {
                            'Version': '2012-10-17',
                            'Statement': [
                                {
                                    'Effect': 'Allow',
                                    'Action': ['*'],
                                    'Resource': '*'
                                }
                            ]
                        }
                    }
                ]
            }
        }
        
        template = {
            'Resources': {
                'ECSTaskRole': ecs_role_with_admin
            }
        }
        
        result = validator.validate_ecs_permissions(template, 'ECSTaskRole')
        
        assert result.passed is False
        assert any(issue.category == 'ADMIN_PERMISSIONS' for issue in result.issues)
    
    def test_validate_policy_documents_success(self, validator):
        """Test successful policy document validation."""
        policies = [
            {
                'file_name': 'test-policy.json',
                'policy_document': {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Effect': 'Allow',
                            'Action': ['s3:GetObject'],
                            'Resource': 'arn:aws:s3:::my-bucket/*'
                        }
                    ]
                }
            }
        ]
        
        result = validator.validate_policy_documents(policies)
        
        # Should pass with minimal issues
        high_issues = [i for i in result.issues if i.severity == 'HIGH']
        assert len(high_issues) == 0
    
    def test_validate_policy_documents_dangerous_actions(self, validator):
        """Test policy validation with dangerous actions."""
        policies = [
            {
                'file_name': 'dangerous-policy.json',
                'policy_document': {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Effect': 'Allow',
                            'Action': ['*'],  # Dangerous action
                            'Resource': '*'
                        }
                    ]
                }
            }
        ]
        
        result = validator.validate_policy_documents(policies)
        
        assert result.passed is False
        assert any(issue.category == 'DANGEROUS_ACTION' for issue in result.issues)
    
    def test_validate_policy_documents_outdated_version(self, validator):
        """Test policy validation with outdated version."""
        policies = [
            {
                'file_name': 'old-policy.json',
                'policy_document': {
                    'Version': '2008-10-17',  # Outdated version
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
        
        result = validator.validate_policy_documents(policies)
        
        medium_issues = [i for i in result.issues if i.severity == 'MEDIUM']
        assert any(issue.category == 'OUTDATED_VERSION' for issue in medium_issues)
    
    def test_validate_policy_documents_missing_statements(self, validator):
        """Test policy validation with missing statements."""
        policies = [
            {
                'file_name': 'empty-policy.json',
                'policy_document': {
                    'Version': '2012-10-17'
                    # Missing Statement
                }
            }
        ]
        
        result = validator.validate_policy_documents(policies)
        
        assert result.passed is False
        assert any(issue.category == 'MISSING_STATEMENTS' for issue in result.issues)
    
    def test_validate_policy_documents_invalid_effect(self, validator):
        """Test policy validation with invalid effect."""
        policies = [
            {
                'file_name': 'invalid-effect-policy.json',
                'policy_document': {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Effect': 'Maybe',  # Invalid effect
                            'Action': ['s3:GetObject'],
                            'Resource': '*'
                        }
                    ]
                }
            }
        ]
        
        result = validator.validate_policy_documents(policies)
        
        assert result.passed is False
        assert any(issue.category == 'INVALID_EFFECT' for issue in result.issues)
    
    def test_is_wildcard_resource_acceptable_true(self, validator):
        """Test wildcard resource acceptance for acceptable actions."""
        acceptable_actions = ['sts:GetCallerIdentity', 'ec2:DescribeInstances', 'iam:ListRoles']
        
        for action in acceptable_actions:
            result = validator._is_wildcard_resource_acceptable([action])
            assert result is True, f"Action {action} should accept wildcard resource"
    
    def test_is_wildcard_resource_acceptable_false(self, validator):
        """Test wildcard resource rejection for unacceptable actions."""
        unacceptable_actions = ['s3:PutObject', 'iam:CreateRole', 'ec2:TerminateInstances']
        
        for action in unacceptable_actions:
            result = validator._is_wildcard_resource_acceptable([action])
            assert result is False, f"Action {action} should not accept wildcard resource"
    
    def test_policy_contains_bedrock_actions_true(self, validator):
        """Test detection of Bedrock actions in policy."""
        policy_with_bedrock = {
            'PolicyDocument': {
                'Statement': [
                    {
                        'Action': ['bedrock-agentcore:InvokeAgent'],
                        'Resource': '*'
                    }
                ]
            }
        }
        
        result = validator._policy_contains_bedrock_actions(policy_with_bedrock)
        assert result is True
    
    def test_policy_contains_bedrock_actions_false(self, validator):
        """Test detection when no Bedrock actions in policy."""
        policy_without_bedrock = {
            'PolicyDocument': {
                'Statement': [
                    {
                        'Action': ['s3:GetObject'],
                        'Resource': '*'
                    }
                ]
            }
        }
        
        result = validator._policy_contains_bedrock_actions(policy_without_bedrock)
        assert result is False
    
    def test_generate_security_report(self, validator):
        """Test security report generation."""
        # Create sample validation results
        result1 = SecurityValidationResult(
            passed=True,
            issues=[
                SecurityIssue(
                    severity='LOW',
                    category='MISSING_TAG',
                    message='Missing tag',
                    recommendation='Add tag'
                )
            ],
            summary={'HIGH': 0, 'MEDIUM': 0, 'LOW': 1}
        )
        
        result2 = SecurityValidationResult(
            passed=False,
            issues=[
                SecurityIssue(
                    severity='HIGH',
                    category='DANGEROUS_ACTION',
                    message='Dangerous action found',
                    resource_name='TestRole',
                    policy_name='TestPolicy',
                    statement_index=0,
                    recommendation='Use specific actions'
                )
            ],
            summary={'HIGH': 1, 'MEDIUM': 0, 'LOW': 0}
        )
        
        report = validator.generate_security_report([result1, result2])
        
        assert "SECURITY VALIDATION REPORT" in report
        assert "Validations: 2" in report
        assert "Passed: 1" in report
        assert "Failed: 1" in report
        assert "Total Issues: 2" in report
        assert "HIGH: 1" in report
        assert "LOW: 1" in report
        assert "Dangerous action found" in report
        assert "Missing tag" in report
    
    def test_generate_security_report_no_issues(self, validator):
        """Test security report generation with no issues."""
        result = SecurityValidationResult(
            passed=True,
            issues=[],
            summary={'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        )
        
        report = validator.generate_security_report([result])
        
        assert "No security issues found!" in report
        assert "Total Issues: 0" in report