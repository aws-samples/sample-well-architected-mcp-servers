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

All platform parameters use the `/coa/` (Cloud Optimization Architecture) prefix:

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
├── components/                 # Component-specific configuration
│   ├── wa_security_mcp/
│   │   ├── agent_arn
│   │   └── agent_id
│   └── chatbot_webapp/
│       ├── cloudfront_url
│       └── s3_bucket_name
└── environments/               # Environment-specific settings
    ├── dev/
    ├── staging/
    └── prod/
```

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

When components are deployed, they should register their key resources:

```python
import boto3

def register_component(component_name, config, region='us-east-1'):
    """Register component configuration in Parameter Store"""
    ssm = boto3.client('ssm', region_name=region)
    
    for key, value in config.items():
        parameter_name = f'/coa/components/{component_name}/{key}'
        ssm.put_parameter(
            Name=parameter_name,
            Value=value,
            Type='String',
            Description=f'{key} for {component_name}',
            Overwrite=True
        )

# Example usage
register_component('wa_security_mcp', {
    'agent_arn': 'arn:aws:bedrock-agent:us-east-1:123456789012:agent/ABCDEF',
    'agent_id': 'ABCDEF123456'
})
```

## Security Considerations

### Parameter Types

- **String**: For non-sensitive configuration (default)
- **SecureString**: For sensitive data (encrypted with KMS)
- **StringList**: For comma-separated values

### Access Control

Use IAM policies to control parameter access:

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
        "arn:aws:ssm:*:*:parameter/coa/components/my-component/*"
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

If you're migrating from CloudFormation stack outputs:

### Before (CloudFormation)
```python
cf = boto3.client('cloudformation')
response = cf.describe_stacks(StackName='my-stack')
outputs = {o['OutputKey']: o['OutputValue'] for o in response['Stacks'][0]['Outputs']}
user_pool_id = outputs['UserPoolId']
```

### After (Parameter Store)
```python
ssm = boto3.client('ssm')
response = ssm.get_parameter(Name='/coa/cognito/user_pool_id')
user_pool_id = response['Parameter']['Value']
```

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

# Get parameter with metadata
aws ssm get-parameter --name /coa/cognito/user_pool_id --with-decryption

# Check parameter tags
aws ssm list-tags-for-resource --resource-type Parameter --resource-id /coa/cognito/user_pool_id
```

## Best Practices

1. **Use Consistent Naming**: Follow the `/coa/` hierarchy
2. **Document Parameters**: Use descriptive parameter descriptions
3. **Version Control**: Tag parameters with version information
4. **Environment Separation**: Use different parameter paths for different environments
5. **Least Privilege**: Grant minimal required permissions
6. **Monitor Access**: Use CloudTrail to monitor parameter access
7. **Backup Important Parameters**: Export critical configuration regularly

## Example: Complete Component Integration

Here's how a new component should integrate with the parameter-based configuration:

```python
#!/usr/bin/env python3
"""
Example component deployment with parameter integration
"""

import boto3
from cognito_utils import get_shared_cognito_client

def deploy_my_component():
    # Get shared Cognito configuration
    cognito_client = get_shared_cognito_client()
    
    # Deploy your component (CloudFormation, CDK, etc.)
    # ...
    
    # Register component configuration
    ssm = boto3.client('ssm')
    
    component_config = {
        'endpoint_url': 'https://my-component.example.com',
        'api_key': 'my-api-key',
        'version': '1.0.0'
    }
    
    for key, value in component_config.items():
        ssm.put_parameter(
            Name=f'/coa/components/my_component/{key}',
            Value=value,
            Type='String',
            Description=f'{key} for my component',
            Overwrite=True
        )
    
    print("✅ Component deployed and registered in Parameter Store")

if __name__ == "__main__":
    deploy_my_component()
```

This approach ensures all components can easily discover and use shared configuration while maintaining clear separation of concerns.