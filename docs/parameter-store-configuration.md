# Parameter Store Configuration Guide

This document explains how the Cloud Optimization platform uses AWS Systems Manager Parameter Store for centralized configuration management.

## Overview

The platform uses standardized parameter paths in Parameter Store to share configuration across components. This approach provides:

- **Centralized Configuration**: All components can access shared settings from a single source
- **Easy Discovery**: Components can find configuration without knowing stack names
- **Environment Isolation**: Different environments use separate parameter namespaces
- **Secure Storage**: Sensitive configuration can be encrypted
- **Version Control**: Parameter Store provides built-in versioning

## Parameter Hierarchy

The platform uses multiple parameter namespaces for different purposes:

### Primary Namespace: `/coa/` (Cloud Optimization Architecture)
```
/coa/
├── cognito/                    # Shared Cognito configuration
│   ├── user_pool_id
│   ├── web_app_client_id
│   ├── api_client_id
│   ├── mcp_server_client_id
│   ├── identity_pool_id
│   ├── user_pool_domain
│   ├── discovery_url
│   ├── region
│   └── user_pool_arn
├── components/                 # MCP Server configurations
│   ├── wa_security_mcp/
│   │   ├── agent_arn
│   │   ├── agent_id
│   │   ├── deployment_type
│   │   ├── region
│   │   └── connection_info
│   └── aws_api_mcp/
│       ├── agent_arn
│       ├── agent_id
│       └── connection_info
└── agent/                      # Bedrock Agent configurations
    └── {agent_name}/
        ├── agent-id
        ├── alias-id
        ├── region
        ├── version
        ├── environment
        ├── feature_flags
        ├── deployment_metadata
        └── mcp/
            └── {mcp_name}/
                └── config
```

### Legacy Namespace: `/cloud-optimization-platform/`
```
/cloud-optimization-platform/
├── BEDROCK_REGION             # Legacy Bedrock region parameter
├── BEDROCK_MODEL_ID           # Legacy Bedrock model parameter
└── USE_ENHANCED_AGENT         # Legacy agent flag
```

### Web Interface Namespace: `/cloud-optimization-web-interface/`
```
/cloud-optimization-web-interface/
├── AWS_ROLE_ARN
├── AWS_ROLE_SESSION_NAME
├── BEDROCK_REGION
├── BEDROCK_MODEL_ID
├── AWS_BEARER_TOKEN_BEDROCK   # SecureString
├── ENHANCED_SECURITY_AGENT_ID
└── ENHANCED_SECURITY_AGENT_ALIAS_ID
```

## Parameter Namespaces

### `/coa/` - Primary Platform Namespace

This is the main namespace for the Cloud Optimization Architecture platform. It contains:

- **Shared Cognito Configuration** (`/coa/cognito/`): Authentication and authorization settings
- **Component Registration** (`/coa/components/`): MCP server configurations and metadata
- **Agent Configuration** (`/coa/agent/`): Bedrock agent settings and MCP integrations

### `/cloud-optimization-platform/` - Legacy Namespace

Legacy parameters from earlier deployments. These are still used by some components:

- `BEDROCK_REGION`: AWS region for Bedrock service
- `BEDROCK_MODEL_ID`: Default Bedrock model identifier
- `USE_ENHANCED_AGENT`: Flag to enable enhanced agent features

### `/cloud-optimization-web-interface/` - Web Interface Namespace

Web interface specific configuration parameters:

- Authentication tokens and credentials (SecureString)
- Service endpoints and identifiers
- Runtime configuration settings

## Cognito Configuration Parameters

When you deploy the shared Cognito infrastructure, these parameters are automatically created:

| Parameter Path | Description | Example Value |
|----------------|-------------|---------------|
| `/coa/cognito/user_pool_id` | Shared Cognito User Pool ID | `us-east-1_XXXXXXXXX` |
| `/coa/cognito/web_app_client_id` | Web Application Client ID | `1234567890abcdef` |
| `/coa/cognito/api_client_id` | API Client ID | `abcdef1234567890` |
| `/coa/cognito/mcp_server_client_id` | MCP Server Client ID | `fedcba0987654321` |
| `/coa/cognito/identity_pool_id` | Identity Pool ID | `us-east-1:uuid-here` |
| `/coa/cognito/user_pool_domain` | User Pool Domain | `cloud-optimization-prod-123456789012` |
| `/coa/cognito/discovery_url` | OIDC Discovery URL | `https://cognito-idp.us-east-1.amazonaws.com/...` |
| `/coa/cognito/region` | AWS Region | `us-east-1` |
| `/coa/cognito/user_pool_arn` | User Pool ARN | `arn:aws:cognito-idp:us-east-1:...` |

## MCP Server Configuration Parameters

MCP servers register their configuration automatically during deployment:

| Parameter Path | Description | Example Value |
|----------------|-------------|---------------|
| `/coa/components/wa_security_mcp/agent_arn` | WA Security MCP Agent ARN | `arn:aws:bedrock-agent:us-east-1:123456789012:agent/ABCDEF` |
| `/coa/components/wa_security_mcp/agent_id` | WA Security MCP Agent ID | `ABCDEF123456` |
| `/coa/components/wa_security_mcp/deployment_type` | Deployment method | `custom_build` |
| `/coa/components/wa_security_mcp/region` | Deployment region | `us-east-1` |
| `/coa/components/wa_security_mcp/connection_info` | JSON connection details | `{"agent_id": "...", "region": "..."}` |
| `/coa/components/aws_api_mcp/agent_arn` | AWS API MCP Agent ARN | `arn:aws:bedrock-agent:us-east-1:123456789012:agent/FEDCBA` |
| `/coa/components/aws_api_mcp/agent_id` | AWS API MCP Agent ID | `FEDCBA654321` |
| `/coa/components/aws_api_mcp/connection_info` | JSON connection details | `{"agent_id": "...", "region": "..."}` |

## Bedrock Agent Configuration Parameters

Enhanced Bedrock agents store comprehensive configuration:

| Parameter Path | Description | Example Value |
|----------------|-------------|---------------|
| `/coa/agent/{agent_name}/agent-id` | Bedrock Agent ID | `ABCDEF123456` |
| `/coa/agent/{agent_name}/alias-id` | Agent Alias ID | `TSTALIASID` |
| `/coa/agent/{agent_name}/region` | Deployment region | `us-east-1` |
| `/coa/agent/{agent_name}/version` | Agent version | `2.0` |
| `/coa/agent/{agent_name}/environment` | Environment type | `prod` |
| `/coa/agent/{agent_name}/feature_flags` | JSON feature configuration | `{"multi_mcp_orchestration": true, ...}` |
| `/coa/agent/{agent_name}/deployment_metadata` | JSON deployment info | `{"deployment_time": "...", "capabilities": [...]}` |
| `/coa/agent/{agent_name}/mcp/{mcp_name}/config` | MCP server configuration | `{"name": "...", "url": "...", "timeout": 30}` |

## Web Interface Configuration Parameters

Web interface uses a separate namespace for its configuration:

| Parameter Path | Description | Type | Example Value |
|----------------|-------------|------|---------------|
| `/cloud-optimization-web-interface/AWS_ROLE_ARN` | Cross-account IAM role | String | `arn:aws:iam::123456789012:role/...` |
| `/cloud-optimization-web-interface/AWS_ROLE_SESSION_NAME` | IAM session name | String | `CloudOptimizationSession` |
| `/cloud-optimization-web-interface/BEDROCK_REGION` | Bedrock service region | String | `us-east-1` |
| `/cloud-optimization-web-interface/BEDROCK_MODEL_ID` | Bedrock model identifier | String | `anthropic.claude-3-haiku-20240307-v1:0` |
| `/cloud-optimization-web-interface/AWS_BEARER_TOKEN_BEDROCK` | Bedrock auth token | SecureString | `encrypted-token-value` |
| `/cloud-optimization-web-interface/ENHANCED_SECURITY_AGENT_ID` | Security agent ID | String | `ABCDEF123456` |
| `/cloud-optimization-web-interface/ENHANCED_SECURITY_AGENT_ALIAS_ID` | Security agent alias | String | `TSTALIASID` |

## Using Parameters in Your Code

### Python (using boto3)

```python
import boto3

def get_cognito_config(region='us-east-1'):
    """Get Cognito configuration from Parameter Store"""
    ssm = boto3.client('ssm', region_name=region)

    # Get all Cognito parameters
    response = ssm.get_parameters_by_path(
        Path='/coa/cognito/',
        Recursive=True
    )

    config = {}
    for param in response['Parameters']:
        key = param['Name'].replace('/coa/cognito/', '')
        config[key] = param['Value']

    return config

# Usage
config = get_cognito_config()
user_pool_id = config['user_pool_id']
```

### Using the Utility Script

```bash
# Get all Cognito configuration
python deployment-scripts/get_cognito_config.py

# Get specific parameter
python deployment-scripts/get_cognito_config.py --parameter user_pool_id

# Get configuration as environment variables
python deployment-scripts/get_cognito_config.py --format env

# Get configuration as JSON
python deployment-scripts/get_cognito_config.py --format json
```

### Using the Cognito Utils Module

```python
from cognito_utils import get_shared_cognito_client

# This automatically uses Parameter Store by default
client = get_shared_cognito_client(region='us-east-1')

# Get specific values
user_pool_id = client.get_user_pool_id()
web_client_id = client.get_web_app_client_id()
```

## Environment Variables

You can export parameters as environment variables:

```bash
# Export all Cognito configuration
eval $(python deployment-scripts/get_cognito_config.py --format env)

# Now use in your application
echo $COGNITO_USER_POOL_ID
```

## CloudFormation Integration

You can reference parameters in CloudFormation templates:

```yaml
Parameters:
  CognitoUserPoolId:
    Type: AWS::SSM::Parameter::Value<String>
    Default: /coa/cognito/user_pool_id

Resources:
  MyResource:
    Type: AWS::SomeService::Resource
    Properties:
      UserPoolId: !Ref CognitoUserPoolId
```

## Component Registration

### MCP Server Components

MCP servers automatically register their configuration during deployment:

```python
# Example: WA Security MCP Server registration
ssm_client.put_parameter(
    Name='/coa/components/wa_security_mcp/agent_arn',
    Value=launch_result.agent_arn,
    Type='String',
    Description='WA Security MCP Server Agent ARN',
    Overwrite=True
)

ssm_client.put_parameter(
    Name='/coa/components/wa_security_mcp/connection_info',
    Value=json.dumps({
        "agent_id": agent_id,
        "agent_arn": agent_arn,
        "region": region,
        "deployment_type": "custom_build"
    }),
    Type='String',
    Description='WA Security MCP Server connection information',
    Overwrite=True
)
```

### Bedrock Agent Registration

Bedrock agents store comprehensive configuration including MCP server configs:

```python
# Example: Enhanced Security Agent registration
parameters = {
    f"/coa/agent/{agent_name}/agent-id": agent_id,
    f"/coa/agent/{agent_name}/alias-id": alias_id,
    f"/coa/agent/{agent_name}/region": region,
    f"/coa/agent/{agent_name}/version": "2.0",
    f"/coa/agent/{agent_name}/environment": environment,
    f"/coa/agent/{agent_name}/feature_flags": json.dumps({
        "multi_mcp_orchestration": True,
        "parallel_tool_execution": True,
        "enhanced_response_formatting": True,
        "session_context_management": True,
        "automated_remediation": False,
        "comprehensive_reporting": True,
        "health_monitoring": True,
        "knowledge_integration": True,
        "api_integration": True
    }),
    f"/coa/agent/{agent_name}/mcp/{mcp_name}/config": json.dumps(mcp_config)
}
```

## Security Considerations

### Parameter Types

- **String**: For non-sensitive configuration (default)
- **SecureString**: For sensitive data (encrypted with KMS)
- **StringList**: For comma-separated values

### Access Control

Use IAM policies to control parameter access across all namespaces:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:GetParametersByPath"
      ],
      "Resource": [
        "arn:aws:ssm:*:*:parameter/coa/cognito/*",
        "arn:aws:ssm:*:*:parameter/coa/components/*",
        "arn:aws:ssm:*:*:parameter/coa/agent/*",
        "arn:aws:ssm:*:*:parameter/cloud-optimization-platform/*",
        "arn:aws:ssm:*:*:parameter/cloud-optimization-web-interface/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:PutParameter",
        "ssm:DeleteParameter"
      ],
      "Resource": [
        "arn:aws:ssm:*:*:parameter/coa/components/my-component/*",
        "arn:aws:ssm:*:*:parameter/coa/agent/my-agent/*"
      ]
    }
  ]
}
```

### Encryption

For sensitive parameters, use SecureString type:

```python
ssm.put_parameter(
    Name='/coa/secrets/database_password',
    Value='my-secret-password',
    Type='SecureString',
    KeyId='alias/aws/ssm',  # or your custom KMS key
    Overwrite=True
)
```

## Migration from CloudFormation Outputs

The platform has evolved to use Parameter Store for configuration management:

### Before (CloudFormation Outputs)
```python
cf = boto3.client('cloudformation')
response = cf.describe_stacks(StackName='my-stack')
outputs = {o['OutputKey']: o['OutputValue'] for o in response['Stacks'][0]['Outputs']}
user_pool_id = outputs['UserPoolId']
```

### After (Parameter Store - Multiple Approaches)

#### Option 1: Direct Parameter Access
```python
ssm = boto3.client('ssm')
response = ssm.get_parameter(Name='/coa/cognito/user_pool_id')
user_pool_id = response['Parameter']['Value']
```

#### Option 2: Batch Parameter Retrieval
```python
ssm = boto3.client('ssm')
response = ssm.get_parameters_by_path(Path='/coa/cognito/', Recursive=True)
config = {p['Name'].split('/')[-1]: p['Value'] for p in response['Parameters']}
user_pool_id = config['user_pool_id']
```

#### Option 3: Using Utility Functions
```python
from cognito_utils import get_shared_cognito_client
client = get_shared_cognito_client()
user_pool_id = client.get_user_pool_id()
```

### Namespace Migration Strategy

When migrating existing components:

1. **Legacy Parameters** (`/cloud-optimization-platform/`): Keep for backward compatibility
2. **New Components**: Use `/coa/` namespace for consistency
3. **Web Interface**: Use `/cloud-optimization-web-interface/` for isolation
4. **Gradual Migration**: Update components incrementally to use new namespaces

## Troubleshooting

### Common Issues

1. **Parameter Not Found**
   ```bash
   # Check if parameter exists
   aws ssm get-parameter --name /coa/cognito/user_pool_id

   # List all Cognito parameters
   aws ssm get-parameters-by-path --path /coa/cognito/ --recursive
   ```

2. **Access Denied**
   - Check IAM permissions for `ssm:GetParameter`
   - Verify the parameter path is correct
   - Ensure you're in the right AWS region

3. **Stale Configuration**
   ```bash
   # Check parameter history
   aws ssm get-parameter-history --name /coa/cognito/user_pool_id
   ```

### Debugging Commands

```bash
# List all COA parameters
aws ssm get-parameters-by-path --path /coa/ --recursive

# List legacy platform parameters
aws ssm get-parameters-by-path --path /cloud-optimization-platform/ --recursive

# List web interface parameters
aws ssm get-parameters-by-path --path /cloud-optimization-web-interface/ --recursive

# Get specific parameter with metadata
aws ssm get-parameter --name /coa/cognito/user_pool_id --with-decryption

# Get MCP server configuration
aws ssm get-parameter --name /coa/components/wa_security_mcp/connection_info --with-decryption

# Get Bedrock agent configuration
aws ssm get-parameters-by-path --path /coa/agent/wa-security-agent-multi-mcps/ --recursive

# Check parameter tags
aws ssm list-tags-for-resource --resource-type Parameter --resource-id /coa/cognito/user_pool_id

# Search for parameters by pattern
aws ssm describe-parameters --parameter-filters "Key=Name,Option=BeginsWith,Values=/coa/"
```

## Deployment Integration

The `deploy-coa.sh` script automatically manages parameter cleanup and validation:

### Parameter Cleanup
```bash
# Clean up existing parameters before deployment
./deploy-coa.sh --cleanup

# This removes parameters from:
# - /coa/cognito/*
# - /cloud-optimization-platform/*
```

### Deployment with Resume Support
```bash
# Deploy with progress tracking
./deploy-coa.sh

# Resume from specific stage if deployment fails
./deploy-coa.sh --resume-from-stage 3

# Check deployment progress
./deploy-coa.sh --show-progress
```

The deployment script handles parameter conflicts and provides guidance for resolution.

## Best Practices

1. **Use Appropriate Namespaces**:
   - `/coa/` for shared platform components
   - `/cloud-optimization-web-interface/` for web interface
   - `/cloud-optimization-platform/` for legacy compatibility
2. **Document Parameters**: Use descriptive parameter descriptions
3. **Version Control**: Tag parameters with version information
4. **Environment Separation**: Use different parameter paths for different environments
5. **Least Privilege**: Grant minimal required permissions
6. **Monitor Access**: Use CloudTrail to monitor parameter access
7. **Backup Important Parameters**: Export critical configuration regularly
8. **Consistent Deployment**: Use the deployment scripts for parameter management
9. **Secure Sensitive Data**: Use SecureString type for credentials and tokens
10. **Regular Cleanup**: Remove unused parameters to avoid conflicts

## Example: Complete Multi-Namespace Integration

Here's how components integrate across all parameter namespaces:

```python
#!/usr/bin/env python3
"""
Example showing integration across all parameter namespaces
"""

import boto3
import json
from cognito_utils import get_shared_cognito_client

class CloudOptimizationComponent:
    def __init__(self, region='us-east-1'):
        self.ssm = boto3.client('ssm', region_name=region)
        self.region = region

    def get_shared_cognito_config(self):
        """Get shared Cognito configuration from /coa/ namespace"""
        response = self.ssm.get_parameters_by_path(
            Path='/coa/cognito/',
            Recursive=True
        )
        return {p['Name'].split('/')[-1]: p['Value'] for p in response['Parameters']}

    def get_mcp_server_config(self, server_name):
        """Get MCP server configuration"""
        try:
            response = self.ssm.get_parameter(
                Name=f'/coa/components/{server_name}/connection_info'
            )
            return json.loads(response['Parameter']['Value'])
        except Exception as e:
            print(f"Could not get MCP server config: {e}")
            return None

    def get_bedrock_agent_config(self, agent_name):
        """Get Bedrock agent configuration"""
        response = self.ssm.get_parameters_by_path(
            Path=f'/coa/agent/{agent_name}/',
            Recursive=True
        )
        config = {}
        for param in response['Parameters']:
            key = param['Name'].split('/')[-1]
            try:
                # Try to parse JSON values
                config[key] = json.loads(param['Value'])
            except:
                config[key] = param['Value']
        return config

    def get_web_interface_config(self):
        """Get web interface configuration"""
        response = self.ssm.get_parameters_by_path(
            Path='/cloud-optimization-web-interface/',
            Recursive=True,
            WithDecryption=True  # For SecureString parameters
        )
        return {p['Name'].split('/')[-1]: p['Value'] for p in response['Parameters']}

    def get_legacy_config(self):
        """Get legacy platform configuration"""
        response = self.ssm.get_parameters_by_path(
            Path='/cloud-optimization-platform/',
            Recursive=True
        )
        return {p['Name'].split('/')[-1]: p['Value'] for p in response['Parameters']}

    def deploy_new_component(self, component_name):
        """Deploy and register a new component"""

        # 1. Get shared Cognito configuration
        cognito_config = self.get_shared_cognito_config()
        print(f"Using Cognito User Pool: {cognito_config.get('user_pool_id')}")

        # 2. Get existing MCP server configurations
        wa_security_config = self.get_mcp_server_config('wa_security_mcp')
        aws_api_config = self.get_mcp_server_config('aws_api_mcp')

        # 3. Deploy your component (CloudFormation, CDK, etc.)
        # ... deployment logic here ...

        # 4. Register component configuration in appropriate namespace
        component_config = {
            'endpoint_url': 'https://my-component.example.com',
            'version': '1.0.0',
            'deployment_type': 'custom',
            'region': self.region,
            'connection_info': json.dumps({
                'component_id': 'my-component-123',
                'region': self.region,
                'capabilities': ['analysis', 'reporting']
            })
        }

        for key, value in component_config.items():
            self.ssm.put_parameter(
                Name=f'/coa/components/{component_name}/{key}',
                Value=value,
                Type='String',
                Description=f'{key} for {component_name}',
                Overwrite=True
            )

        print(f"✅ Component {component_name} deployed and registered")
        return True

# Usage example
def main():
    component = CloudOptimizationComponent()

    # Show current configuration across all namespaces
    print("=== Current Configuration ===")
    print("Cognito Config:", component.get_shared_cognito_config())
    print("WA Security MCP:", component.get_mcp_server_config('wa_security_mcp'))
    print("Web Interface Config:", component.get_web_interface_config())
    print("Legacy Config:", component.get_legacy_config())

    # Deploy new component
    component.deploy_new_component('my_new_component')

if __name__ == "__main__":
    main()
```

This example demonstrates how to:

1. **Access shared configuration** from `/coa/cognito/`
2. **Integrate with MCP servers** via `/coa/components/`
3. **Use Bedrock agents** from `/coa/agent/`
4. **Handle web interface settings** from `/cloud-optimization-web-interface/`
5. **Maintain legacy compatibility** with `/cloud-optimization-platform/`
6. **Register new components** following the established patterns

The multi-namespace approach ensures clear separation of concerns while enabling seamless integration across all platform components.
