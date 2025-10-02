"""
Configuration constants for IAM validation and template updates.
"""

import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent
POLICY_DIR = BASE_DIR / "policies"
TEMPLATE_INPUT = BASE_DIR / "cloud-optimization-assistant-0.1.0.yaml"
TEMPLATE_OUTPUT = BASE_DIR / "cloud-optimization-assistant-0.1.1.yaml"

CONFIG = {
    # File paths
    'policy_directory': str(POLICY_DIR),
    'template_input': str(TEMPLATE_INPUT),
    'template_output': str(TEMPLATE_OUTPUT),
    
    # IAM role configuration
    'temporary_role_prefix': 'coa-temp-validation',
    'bedrock_role_name': '${AWS::StackName}-bedrock-agentcore-runtime-role',
    
    # AWS configuration
    'aws_region': os.getenv('AWS_REGION', 'us-east-1'),
    'aws_profile': os.getenv('AWS_PROFILE'),
    
    # Policy file names (expected in policy directory)
    'policy_files': [
        'agentCore-runtime-coa-mcp-sts-policy.json',
        'agentCore-runtime-coa-ssm-policy.json', 
        'agentCore-runtime-execution-role-plicy.json'
    ],
    
    # CloudFormation configuration
    'bedrock_role_resource_name': 'BedrockAgentCoreRuntimeRole',
    'ecs_task_role_name': 'ECSTaskRole',
    
    # Security settings
    'max_policy_size': 10240,  # 10KB max policy size
    'cleanup_timeout': 300,    # 5 minutes cleanup timeout
    
    # Logging configuration
    'log_level': os.getenv('LOG_LEVEL', 'INFO'),
    'verbose': os.getenv('VERBOSE', 'false').lower() == 'true'
}

# Policy name mappings for CloudFormation inline policies
POLICY_NAME_MAPPING = {
    'agentCore-runtime-coa-mcp-sts-policy.json': 'AgentCoreRuntimeSTSPolicy',
    'agentCore-runtime-coa-ssm-policy.json': 'AgentCoreRuntimeSSMPolicy',
    'agentCore-runtime-execution-role-plicy.json': 'AgentCoreRuntimeExecutionPolicy'
}

# ECS permission template
ECS_BEDROCK_PERMISSION = {
    'Effect': 'Allow',
    'Action': ['bedrock-agentcore:InvokeAgent'],
    'Resource': ['!Sub \'arn:aws:bedrock-agentcore:${AWS::Region}:${AWS::AccountId}:runtime/*\'']
}

# Bedrock AgentCore role assume role policy
BEDROCK_ASSUME_ROLE_POLICY = {
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
}