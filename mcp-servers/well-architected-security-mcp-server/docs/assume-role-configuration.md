# AssumeRole Configuration Guide

The Well-Architected Security MCP Server now supports AWS AssumeRole functionality through environment variables. This enables cross-account access and enhanced security scenarios.

## Overview

The MCP server uses an enhanced credential chain that supports:
1. **AssumeRole via environment variables** (new feature)
2. **Standard AWS credentials chain** (existing functionality)

## Environment Variables

### Required for AssumeRole
- `AWS_ASSUME_ROLE_ARN`: The ARN of the IAM role to assume

### Optional for AssumeRole
- `AWS_ASSUME_ROLE_SESSION_NAME`: Custom session name (default: "mcp-server-session")
- `AWS_ASSUME_ROLE_EXTERNAL_ID`: External ID for enhanced security

### Standard AWS Credentials (still supported)
- `AWS_ACCESS_KEY_ID`: AWS access key
- `AWS_SECRET_ACCESS_KEY`: AWS secret key
- `AWS_SESSION_TOKEN`: AWS session token (for temporary credentials)
- `AWS_REGION`: AWS region (default: "us-east-1")

## Configuration Examples

### Basic AssumeRole Setup
```bash
export AWS_ASSUME_ROLE_ARN="arn:aws:iam::123456789012:role/SecurityAuditRole"
export AWS_REGION="us-east-1"
```

### AssumeRole with Custom Session Name
```bash
export AWS_ASSUME_ROLE_ARN="arn:aws:iam::123456789012:role/SecurityAuditRole"
export AWS_ASSUME_ROLE_SESSION_NAME="security-assessment-session"
export AWS_REGION="us-east-1"
```

### AssumeRole with External ID (Enhanced Security)
```bash
export AWS_ASSUME_ROLE_ARN="arn:aws:iam::123456789012:role/SecurityAuditRole"
export AWS_ASSUME_ROLE_SESSION_NAME="security-assessment-session"
export AWS_ASSUME_ROLE_EXTERNAL_ID="unique-external-id-12345"
export AWS_REGION="us-east-1"
```

### Docker/Container Environment
```dockerfile
ENV AWS_ASSUME_ROLE_ARN=arn:aws:iam::123456789012:role/SecurityAuditRole
ENV AWS_ASSUME_ROLE_SESSION_NAME=mcp-security-server
ENV AWS_REGION=us-east-1
```

## IAM Role Setup

### 1. Create the Target Role
Create an IAM role in the target account with the necessary permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "guardduty:ListDetectors",
        "guardduty:GetDetector",
        "inspector2:GetStatus",
        "accessanalyzer:ListAnalyzers",
        "securityhub:DescribeHub",
        "support:DescribeTrustedAdvisorChecks",
        "macie2:GetMacieSession",
        "s3:GetEncryptionConfiguration",
        "ec2:DescribeVolumes",
        "rds:DescribeDBInstances",
        "dynamodb:DescribeTable",
        "efs:DescribeFileSystems",
        "elasticache:DescribeCacheClusters"
      ],
      "Resource": "*"
    }
  ]
}
```

### 2. Configure Trust Policy
Set up the trust policy to allow the MCP server to assume the role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::SOURCE-ACCOUNT:role/MCPServerRole"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "unique-external-id-12345"
        }
      }
    }
  ]
}
```

### 3. Source Account Permissions
Ensure the source account (where MCP server runs) has permission to assume the role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": "arn:aws:iam::123456789012:role/SecurityAuditRole"
    }
  ]
}
```

## Usage Patterns

### Cross-Account Security Assessment
```bash
# Set up AssumeRole for target account
export AWS_ASSUME_ROLE_ARN="arn:aws:iam::TARGET-ACCOUNT:role/SecurityAuditRole"
export AWS_ASSUME_ROLE_EXTERNAL_ID="shared-secret-key"

# Run MCP server
python -m src.server
```

### Multiple Account Assessment
```bash
#!/bin/bash
# Script to assess multiple accounts

ACCOUNTS=("123456789012" "234567890123" "345678901234")
ROLE_NAME="SecurityAuditRole"
EXTERNAL_ID="assessment-2024"

for account in "${ACCOUNTS[@]}"; do
    echo "Assessing account: $account"
    
    export AWS_ASSUME_ROLE_ARN="arn:aws:iam::${account}:role/${ROLE_NAME}"
    export AWS_ASSUME_ROLE_EXTERNAL_ID="$EXTERNAL_ID"
    
    # Run assessment (example using MCP client)
    # mcp-client call CheckSecurityServices --region us-east-1
    
    unset AWS_ASSUME_ROLE_ARN AWS_ASSUME_ROLE_EXTERNAL_ID
done
```

## Validation and Troubleshooting

### Use the Validation Tool
The MCP server includes a built-in validation tool:

```python
# Call the ValidateCredentialConfiguration tool
result = await mcp.call_tool("ValidateCredentialConfiguration")
print(result)
```

### Common Issues and Solutions

#### 1. Access Denied Error
```
Error: AssumeRole operation failed: Access denied
```
**Solutions:**
- Verify the trust policy allows your source principal
- Check that the source account has `sts:AssumeRole` permission
- Ensure the external ID matches (if configured)

#### 2. Invalid ARN Format
```
Error: AWS_ASSUME_ROLE_ARN does not appear to be a valid IAM role ARN
```
**Solution:**
- Ensure ARN format: `arn:aws:iam::ACCOUNT-ID:role/ROLE-NAME`

#### 3. Session Name Issues
```
Error: AWS_ASSUME_ROLE_SESSION_NAME must be between 2 and 64 characters
```
**Solution:**
- Use a session name between 2-64 characters
- Valid characters: letters, numbers, and `=,.@-`

### Debug Mode
Enable debug logging to see detailed credential information:

```bash
export FASTMCP_LOG_LEVEL=DEBUG
python -m src.server
```

## Security Best Practices

1. **Use External IDs**: Always configure external IDs for cross-account access
2. **Least Privilege**: Grant only the minimum required permissions
3. **Session Names**: Use descriptive session names for audit trails
4. **Rotate External IDs**: Regularly rotate external IDs
5. **Monitor Usage**: Use CloudTrail to monitor AssumeRole operations
6. **Time-based Access**: Consider using time-based conditions in trust policies

## Integration Examples

### Amazon Bedrock AgentCore Runtime
```yaml
# .bedrock_agentcore.yaml
environment:
  AWS_ASSUME_ROLE_ARN: "arn:aws:iam::123456789012:role/SecurityAuditRole"
  AWS_ASSUME_ROLE_SESSION_NAME: "bedrock-agent-session"
  AWS_ASSUME_ROLE_EXTERNAL_ID: "bedrock-external-id"
  AWS_REGION: "us-east-1"
```

### Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-security-server
spec:
  template:
    spec:
      containers:
      - name: mcp-server
        image: mcp-security-server:latest
        env:
        - name: AWS_ASSUME_ROLE_ARN
          value: "arn:aws:iam::123456789012:role/SecurityAuditRole"
        - name: AWS_ASSUME_ROLE_SESSION_NAME
          value: "k8s-mcp-session"
        - name: AWS_ASSUME_ROLE_EXTERNAL_ID
          valueFrom:
            secretKeyRef:
              name: aws-external-id
              key: external-id
```

### AWS Lambda Function
```python
import os
import json

def lambda_handler(event, context):
    # Set AssumeRole configuration
    os.environ['AWS_ASSUME_ROLE_ARN'] = event['target_role_arn']
    os.environ['AWS_ASSUME_ROLE_EXTERNAL_ID'] = event['external_id']
    
    # Import and use MCP server
    from src.server import mcp
    
    # Run security assessment
    result = await mcp.call_tool("CheckSecurityServices", {
        "region": event.get("region", "us-east-1"),
        "services": ["guardduty", "securityhub", "inspector"]
    })
    
    return {
        'statusCode': 200,
        'body': json.dumps(result)
    }
```

## Migration from Profile-based Authentication

If you were previously using AWS profiles, here's how to migrate:

### Before (Profile-based)
```bash
export AWS_PROFILE=security-audit-profile
python -m src.server
```

### After (AssumeRole-based)
```bash
# Option 1: Use AssumeRole
export AWS_ASSUME_ROLE_ARN="arn:aws:iam::123456789012:role/SecurityAuditRole"
python -m src.server

# Option 2: Use default credentials chain (still supported)
# Configure ~/.aws/credentials or use IAM roles
python -m src.server
```

This enhanced credential system provides more flexibility while maintaining backward compatibility with existing authentication methods.