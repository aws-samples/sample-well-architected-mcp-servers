# Configuration Management

The Cloud Optimization Web Interface backend supports flexible configuration management with automatic fallback from AWS Systems Manager Parameter Store to environment variables.

## Configuration Priority

The application loads configuration in the following priority order:

1. **AWS Systems Manager Parameter Store** (highest priority)
2. **Environment Variables** (from `.env` file or system environment)
3. **Default Values** (lowest priority)

## Configuration Parameters

### AWS Configuration
- `AWS_DEFAULT_REGION` - Default AWS region (default: us-east-1)
- `AWS_PROFILE` - AWS profile for authentication
- `AWS_ROLE_ARN` - IAM role ARN for cross-account access
- `AWS_ROLE_SESSION_NAME` - Session name for role assumption

### Bedrock Configuration
- `BEDROCK_REGION` - AWS region for Bedrock service
- `BEDROCK_MODEL_ID` - Bedrock model ID for LLM operations
- `AWS_BEARER_TOKEN_BEDROCK` - Bearer token for Bedrock (stored as SecureString in SSM)

### Enhanced Security Agent
- `ENHANCED_SECURITY_AGENT_ID` - Bedrock agent ID
- `ENHANCED_SECURITY_AGENT_ALIAS_ID` - Bedrock agent alias ID
- `USE_ENHANCED_AGENT` - Enable enhanced agent (true/false)

### MCP Server Configuration
- `MCP_SERVER_URL` - MCP server connection URL
- `MCP_DEMO_MODE` - Enable demo mode (true/false)

## Setting up SSM Parameters

### Option 1: Using the Setup Script

The easiest way to migrate from `.env` to SSM Parameter Store:

```bash
# Navigate to the backend directory
cd cloud-optimization-web-interfaces/cloud-optimization-web-interface/backend

# Make the script executable
chmod +x scripts/setup_ssm_parameters.py

# Dry run to see what would be created
python scripts/setup_ssm_parameters.py --dry-run

# Create parameters (will skip existing ones)
python scripts/setup_ssm_parameters.py

# Force overwrite existing parameters
python scripts/setup_ssm_parameters.py --force

# Use custom prefix
python scripts/setup_ssm_parameters.py --prefix /my-app/config
```

### Option 2: Manual SSM Parameter Creation

Create parameters manually using AWS CLI:

```bash
# String parameters
aws ssm put-parameter \
    --name "/cloud-optimization-web-interface/AWS_DEFAULT_REGION" \
    --value "us-east-1" \
    --type "String" \
    --description "Default AWS region for the application"

# Secure parameters (encrypted)
aws ssm put-parameter \
    --name "/cloud-optimization-web-interface/AWS_BEARER_TOKEN_BEDROCK" \
    --value "your-bearer-token" \
    --type "SecureString" \
    --description "Bearer token for Bedrock authentication"
```

### Option 3: Using the Web Interface

The application provides REST API endpoints for configuration management:

```bash
# Get current configuration
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/config

# Refresh configuration cache
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/config/refresh

# List SSM parameters
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/config/ssm/parameters
```

## SSM Parameter Naming Convention

Parameters are stored with the prefix `/cloud-optimization-web-interface/` by default:

```
/cloud-optimization-web-interface/AWS_DEFAULT_REGION
/cloud-optimization-web-interface/ENHANCED_SECURITY_AGENT_ID
/cloud-optimization-web-interface/AWS_BEARER_TOKEN_BEDROCK
```

## Required IAM Permissions

The application needs the following IAM permissions to access SSM Parameter Store:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter",
                "ssm:GetParameters",
                "ssm:DescribeParameters"
            ],
            "Resource": [
                "arn:aws:ssm:*:*:parameter/cloud-optimization-web-interface/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "ssm:PutParameter"
            ],
            "Resource": [
                "arn:aws:ssm:*:*:parameter/cloud-optimization-web-interface/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "kms:Decrypt"
            ],
            "Resource": [
                "arn:aws:kms:*:*:key/*"
            ],
            "Condition": {
                "StringEquals": {
                    "kms:ViaService": "ssm.*.amazonaws.com"
                }
            }
        }
    ]
}
```

## Environment Variables Fallback

If SSM Parameter Store is not available or parameters are not found, the application will fall back to environment variables:

1. **System environment variables**
2. **Variables from `.env` file**

This ensures the application works in development environments without SSM setup.

## Configuration Service Usage

In your Python code, use the configuration service:

```python
from services.config_service import get_config, config_service

# Get a configuration value with fallback
region = get_config('AWS_DEFAULT_REGION', 'us-east-1')

# Get all configuration
all_config = config_service.get_all_config()

# Refresh cache (force reload from SSM)
config_service.refresh_cache()

# Check SSM status
status = config_service.get_ssm_status()
```

## Troubleshooting

### SSM Not Available
If you see warnings about SSM client initialization:
- Check AWS credentials are configured
- Verify IAM permissions for SSM access
- Ensure the AWS region is correct

### Parameters Not Found
If parameters are not found in SSM:
- Verify parameter names match exactly (case-sensitive)
- Check the parameter prefix is correct
- Ensure parameters exist in the correct AWS region

### Cache Issues
If configuration changes aren't reflected:
- Use the `/api/config/refresh` endpoint to clear cache
- Restart the application to force reload
- Check CloudWatch logs for configuration loading messages

## Security Considerations

- **Sensitive values** (tokens, passwords) should use `SecureString` type in SSM
- **Parameter access** should be restricted using IAM policies
- **Audit logging** is automatically enabled for SSM parameter access
- **Encryption** is handled automatically for SecureString parameters

## Development vs Production

### Development
- Use `.env` file for local development
- SSM parameters are optional
- Configuration service gracefully falls back to environment variables

### Production
- Store all configuration in SSM Parameter Store
- Use SecureString for sensitive values
- Remove `.env` file from production deployments
- Monitor SSM parameter access through CloudTrail
