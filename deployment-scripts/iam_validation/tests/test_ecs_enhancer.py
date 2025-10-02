"""
Unit tests for ECSPermissionEnhancer.
"""

import pytest
from copy import deepcopy

from ..ecs_enhancer import ECSPermissionEnhancer
from ..error_handling import TemplateException
from ..config import ECS_BEDROCK_PERMISSION


class TestECSPermissionEnhancer:
    """Test cases for ECSPermissionEnhancer class."""
    
    @pytest.fixture
    def enhancer(self):
        """Create ECSPermissionEnhancer instance."""
        return ECSPermissionEnhancer()
    
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
        }
    
    @pytest.fixture
    def sample_template(self, sample_ecs_role):
        """Sample CloudFormation template with ECS role."""
        return {
            'AWSTemplateFormatVersion': '2010-09-09',
            'Resources': {
                'ECSTaskRole': sample_ecs_role,
                'TestBucket': {
                    'Type': 'AWS::S3::Bucket'
                }
            }
        }
    
    def test_enhance_ecs_task_role_success(self, enhancer, sample_template):
        """Test successful ECS task role enhancement."""
        enhanced_template = enhancer.enhance_ecs_task_role(sample_template)
        
        # Verify original template wasn't modified
        assert len(sample_template['Resources']['ECSTaskRole']['Properties']['Policies']) == 1
        
        # Verify enhanced template has additional policy
        enhanced_role = enhanced_template['Resources']['ECSTaskRole']
        policies = enhanced_role['Properties']['Policies']
        assert len(policies) == 2
        
        # Find Bedrock policy
        bedrock_policy = None
        for policy in policies:
            if policy['PolicyName'] == 'BedrockAgentCoreInvokePolicy':
                bedrock_policy = policy
                break
        
        assert bedrock_policy is not None
        statement = bedrock_policy['PolicyDocument']['Statement'][0]
        assert 'bedrock-agentcore:InvokeAgent' in statement['Action']
    
    def test_enhance_ecs_task_role_specific_role(self, enhancer, sample_template):
        """Test enhancement with specific role name."""
        enhanced_template = enhancer.enhance_ecs_task_role(sample_template, 'ECSTaskRole')
        
        enhanced_role = enhanced_template['Resources']['ECSTaskRole']
        policies = enhanced_role['Properties']['Policies']
        assert len(policies) == 2
    
    def test_enhance_ecs_task_role_no_role_found(self, enhancer):
        """Test enhancement when no ECS role is found."""
        template_without_ecs = {
            'Resources': {
                'TestBucket': {'Type': 'AWS::S3::Bucket'}
            }
        }
        
        with pytest.raises(TemplateException) as exc_info:
            enhancer.enhance_ecs_task_role(template_without_ecs)
        
        assert "Could not find ECS task role" in str(exc_info.value)
    
    def test_enhance_ecs_task_role_invalid_role_name(self, enhancer, sample_template):
        """Test enhancement with invalid role name."""
        with pytest.raises(TemplateException) as exc_info:
            enhancer.enhance_ecs_task_role(sample_template, 'NonExistentRole')
        
        assert "Role NonExistentRole not found" in str(exc_info.value)
    
    def test_enhance_ecs_task_role_not_iam_role(self, enhancer):
        """Test enhancement when specified resource is not IAM role."""
        template_with_non_role = {
            'Resources': {
                'NotARole': {'Type': 'AWS::S3::Bucket'}
            }
        }
        
        with pytest.raises(TemplateException) as exc_info:
            enhancer.enhance_ecs_task_role(template_with_non_role, 'NotARole')
        
        assert "is not an IAM role" in str(exc_info.value)
    
    def test_find_ecs_task_role_by_service(self, enhancer, sample_template):
        """Test finding ECS role by service principal."""
        role_name = enhancer.find_ecs_task_role(sample_template)
        assert role_name == 'ECSTaskRole'
    
    def test_find_ecs_task_role_by_name(self, enhancer):
        """Test finding ECS role by naming convention."""
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
                },
                'ContainerTaskRole': {
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
        
        role_name = enhancer.find_ecs_task_role(template_with_named_role)
        assert role_name in ['MyECSTaskRole', 'ContainerTaskRole']
    
    def test_find_ecs_task_role_by_policies(self, enhancer):
        """Test finding ECS role by examining policies."""
        template_with_ecs_policies = {
            'Resources': {
                'TaskRole': {
                    'Type': 'AWS::IAM::Role',
                    'Properties': {
                        'AssumeRolePolicyDocument': {
                            'Statement': [
                                {
                                    'Principal': {'Service': 'lambda.amazonaws.com'}
                                }
                            ]
                        },
                        'Policies': [
                            {
                                'PolicyName': 'ECSPolicy',
                                'PolicyDocument': {
                                    'Statement': [
                                        {
                                            'Action': ['ecs:DescribeTasks'],
                                            'Resource': '*'
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }
        
        role_name = enhancer.find_ecs_task_role(template_with_ecs_policies)
        assert role_name == 'TaskRole'
    
    def test_find_ecs_task_role_not_found(self, enhancer):
        """Test when no ECS role is found."""
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
        
        role_name = enhancer.find_ecs_task_role(template_without_ecs)
        assert role_name is None
    
    def test_is_ecs_task_role_by_service_single_service(self, enhancer):
        """Test ECS role detection by single service principal."""
        role_resource = {
            'Type': 'AWS::IAM::Role',
            'Properties': {
                'AssumeRolePolicyDocument': {
                    'Statement': [
                        {
                            'Principal': {
                                'Service': 'ecs-tasks.amazonaws.com'
                            }
                        }
                    ]
                }
            }
        }
        
        result = enhancer._is_ecs_task_role_by_service(role_resource)
        assert result is True
    
    def test_is_ecs_task_role_by_service_multiple_services(self, enhancer):
        """Test ECS role detection by multiple service principals."""
        role_resource = {
            'Type': 'AWS::IAM::Role',
            'Properties': {
                'AssumeRolePolicyDocument': {
                    'Statement': [
                        {
                            'Principal': {
                                'Service': ['lambda.amazonaws.com', 'ecs-tasks.amazonaws.com']
                            }
                        }
                    ]
                }
            }
        }
        
        result = enhancer._is_ecs_task_role_by_service(role_resource)
        assert result is True
    
    def test_is_ecs_task_role_by_service_false(self, enhancer):
        """Test ECS role detection returns false for non-ECS role."""
        role_resource = {
            'Type': 'AWS::IAM::Role',
            'Properties': {
                'AssumeRolePolicyDocument': {
                    'Statement': [
                        {
                            'Principal': {
                                'Service': 'lambda.amazonaws.com'
                            }
                        }
                    ]
                }
            }
        }
        
        result = enhancer._is_ecs_task_role_by_service(role_resource)
        assert result is False
    
    def test_is_ecs_task_role_by_name_patterns(self, enhancer):
        """Test ECS role detection by various naming patterns."""
        role_resource = {'Type': 'AWS::IAM::Role'}
        
        test_cases = [
            ('ECSTaskRole', True),
            ('MyECSTaskRole', True),
            ('ecstaskrole', True),
            ('ContainerTaskRole', True),
            ('TaskRole', True),
            ('MyTaskRole', True),
            ('LambdaRole', False),
            ('S3Role', False),
            ('ExecutionRole', False)
        ]
        
        for role_name, expected in test_cases:
            result = enhancer._is_ecs_task_role_by_name(role_name, role_resource)
            assert result == expected, f"Failed for role name: {role_name}"
    
    def test_is_ecs_task_role_by_policies_managed_policies(self, enhancer):
        """Test ECS role detection by managed policies."""
        role_resource = {
            'Type': 'AWS::IAM::Role',
            'Properties': {
                'ManagedPolicyArns': [
                    'arn:aws:iam::aws:policy/service-role/AmazonECSTaskRolePolicy'
                ]
            }
        }
        
        result = enhancer._is_ecs_task_role_by_policies(role_resource)
        assert result is True
    
    def test_is_ecs_task_role_by_policies_inline_policies(self, enhancer):
        """Test ECS role detection by inline policies."""
        role_resource = {
            'Type': 'AWS::IAM::Role',
            'Properties': {
                'Policies': [
                    {
                        'PolicyDocument': {
                            'Statement': [
                                {
                                    'Action': ['ecs:DescribeTasks', 'ecr:GetAuthorizationToken'],
                                    'Resource': '*'
                                }
                            ]
                        }
                    }
                ]
            }
        }
        
        result = enhancer._is_ecs_task_role_by_policies(role_resource)
        assert result is True
    
    def test_add_bedrock_permissions_new_policy(self, enhancer, sample_ecs_role):
        """Test adding Bedrock permissions as new policy."""
        original_policies_count = len(sample_ecs_role['Properties']['Policies'])
        
        enhancer._add_bedrock_permissions(sample_ecs_role)
        
        policies = sample_ecs_role['Properties']['Policies']
        assert len(policies) == original_policies_count + 1
        
        # Find Bedrock policy
        bedrock_policy = policies[-1]  # Should be the last one added
        assert bedrock_policy['PolicyName'] == 'BedrockAgentCoreInvokePolicy'
        
        statement = bedrock_policy['PolicyDocument']['Statement'][0]
        assert statement['Action'] == ['bedrock-agentcore:InvokeAgent']
    
    def test_add_bedrock_permissions_update_existing(self, enhancer, sample_ecs_role):
        """Test updating existing Bedrock permissions."""
        # Add existing Bedrock policy with incomplete permissions
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
        sample_ecs_role['Properties']['Policies'].append(existing_bedrock_policy)
        original_policies_count = len(sample_ecs_role['Properties']['Policies'])
        
        enhancer._add_bedrock_permissions(sample_ecs_role)
        
        # Should not add new policy, just update existing
        policies = sample_ecs_role['Properties']['Policies']
        assert len(policies) == original_policies_count
        
        # Find updated Bedrock policy
        bedrock_policy = policies[-1]  # The existing one we added
        statement = bedrock_policy['PolicyDocument']['Statement'][0]
        resources = statement['Resource']
        
        # Should have both old and new resource patterns
        assert len(resources) == 2
        assert ECS_BEDROCK_PERMISSION['Resource'][0] in resources
    
    def test_validate_bedrock_permissions_valid(self, enhancer, sample_template):
        """Test validation of valid Bedrock permissions."""
        # First enhance the template
        enhanced_template = enhancer.enhance_ecs_task_role(sample_template)
        
        # Then validate
        result = enhancer.validate_bedrock_permissions(enhanced_template, 'ECSTaskRole')
        
        assert result['valid'] is True
        assert result['has_bedrock_permission'] is True
        assert result['has_correct_action'] is True
        assert result['has_correct_resource'] is True
        assert len(result['issues']) == 0
    
    def test_validate_bedrock_permissions_missing(self, enhancer, sample_template):
        """Test validation when Bedrock permissions are missing."""
        result = enhancer.validate_bedrock_permissions(sample_template, 'ECSTaskRole')
        
        assert result['valid'] is False
        assert result['has_bedrock_permission'] is False
        assert len(result['issues']) > 0
        assert any("No Bedrock AgentCore invoke permission found" in issue for issue in result['issues'])
    
    def test_validate_bedrock_permissions_role_not_found(self, enhancer, sample_template):
        """Test validation when role is not found."""
        result = enhancer.validate_bedrock_permissions(sample_template, 'NonExistentRole')
        
        assert result['valid'] is False
        assert len(result['issues']) > 0
        assert any("Role NonExistentRole not found" in issue for issue in result['issues'])
    
    def test_get_enhancement_summary_new_policy(self, enhancer, sample_template):
        """Test enhancement summary when new policy is created."""
        original_template = deepcopy(sample_template)
        enhanced_template = enhancer.enhance_ecs_task_role(sample_template)
        
        summary = enhancer.get_enhancement_summary(original_template, enhanced_template, 'ECSTaskRole')
        
        assert summary['role_name'] == 'ECSTaskRole'
        assert summary['enhancement_applied'] is True
        assert summary['policies_added'] == 1
        assert summary['statements_added'] == 1
        assert summary['new_bedrock_policy_created'] is True
        assert summary['existing_bedrock_policy_updated'] is False
    
    def test_get_enhancement_summary_updated_policy(self, enhancer, sample_template):
        """Test enhancement summary when existing policy is updated."""
        # Add existing Bedrock policy
        existing_bedrock_policy = {
            'PolicyName': 'ExistingBedrockPolicy',
            'PolicyDocument': {
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Effect': 'Allow',
                        'Action': ['bedrock-agentcore:InvokeAgent'],
                        'Resource': ['arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/old']
                    }
                ]
            }
        }
        sample_template['Resources']['ECSTaskRole']['Properties']['Policies'].append(existing_bedrock_policy)
        
        original_template = deepcopy(sample_template)
        enhanced_template = enhancer.enhance_ecs_task_role(sample_template)
        
        summary = enhancer.get_enhancement_summary(original_template, enhanced_template, 'ECSTaskRole')
        
        assert summary['role_name'] == 'ECSTaskRole'
        assert summary['enhancement_applied'] is True
        assert summary['policies_added'] == 0  # No new policy added
        assert summary['existing_bedrock_policy_updated'] is True
        assert summary['new_bedrock_policy_created'] is False