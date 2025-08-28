# Cognito User Pool Centralization Guide

This guide explains how to migrate from individual Cognito user pools per component to a centralized shared user pool architecture.

## Overview

### Current Architecture (Before Refactoring)
- Each component creates its own Cognito user pool
- Separate user management for each service
- Duplicated authentication configuration
- Users need separate accounts for different components

### New Architecture (After Refactoring)
- Single shared Cognito user pool for all components
- Centralized user management
- Multiple client applications for different use cases
- Single sign-on across all components

## Benefits of Centralization

1. **Single Sign-On (SSO)**: Users authenticate once and access all components
2. **Simplified User Management**: One place to manage users, groups, and permissions
3. **Consistent Authentication**: Same authentication flow across all components
4. **Cost Optimization**: Reduced Cognito costs by consolidating user pools
5. **Better Security**: Centralized security policies and monitoring
6. **Easier Maintenance**: Single authentication infrastructure to maintain
7. **Parameter Store Integration**: Automatic configuration distribution via `/coa/cognito/*` parameters
8. **Easy Discovery**: Components can find Cognito configuration without knowing stack names

## Migration Steps

### Step 1: Deploy Shared Cognito Infrastructure

```bash
# Deploy the shared Cognito user pool
python deployment-scripts/deploy_shared_cognito.py \
  --stack-name cloud-optimization-agentflow-cognito \
  --region us-east-1 \
  --environment prod \
  --create-test-user
```

This creates:
- Shared Cognito User Pool
- Multiple client applications (Web App, API, MCP Server)
- Identity Pool for AWS resource access
- IAM roles for authenticated users
- **Parameter Store configuration** at `/coa/cognito/*` paths for easy component discovery

### Step 2: Update Component Deployments

Replace your existing deployment scripts with the refactored versions:

#### For AgentCore Runtime (MCP Server):
```bash
# Old way
python deployment-scripts/deploy_wa_security_agentcore_runtime.py

# New way (using shared Cognito)
python deployment-scripts/deploy_component_wa_security_mcp.py
```

#### For Web Applications:
```bash
# Old way
python deployment-scripts/deploy_chatbot_webapp.py

# New way (using shared Cognito)
python deployment-scripts/deploy_component_chatbot_webapp.py \
  --shared-cognito-stack cloud-optimization-shared-cognito
```

### Step 3: Update Application Code

#### Backend Applications
Update your backend code to use the shared user pool. The configuration is automatically available in Parameter Store:

```python
from cognito_utils import get_shared_cognito_client

# Get shared Cognito configuration (uses Parameter Store by default)
cognito_client = get_shared_cognito_client()
user_pool_id = cognito_client.get_user_pool_id()
api_client_id = cognito_client.get_api_client_id()

# For JWT validation
discovery_url = cognito_client.get_discovery_url()
```

#### Direct Parameter Store Access
You can also access configuration directly:

```python
import boto3

ssm = boto3.client('ssm')
user_pool_id = ssm.get_parameter(Name='/coa/cognito/user_pool_id')['Parameter']['Value']
```

#### Using the Utility Script
```bash
# Get all Cognito configuration
python deployment-scripts/get_cognito_config.py

# Get specific parameter
python deployment-scripts/get_cognito_config.py --parameter user_pool_id

# Export as environment variables
eval $(python deployment-scripts/get_cognito_config.py --format env)
```

#### Frontend Applications
Update your frontend configuration:

```javascript
// Get Cognito configuration for frontend
const cognitoConfig = {
  userPoolId: 'us-east-1_XXXXXXXXX',  // From shared stack
  clientId: 'XXXXXXXXXXXXXXXXXXXXXXXXXX',  // Web App Client ID
  domain: 'cloud-optimization-prod-123456789012.auth.us-east-1.amazoncognito.com',
  identityPoolId: 'us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
  region: 'us-east-1'
};
```

### Step 4: Migrate Existing Users (Optional)

If you have existing users in separate user pools, you can migrate them:

```python
from cognito_utils import get_shared_cognito_client
import boto3

def migrate_users_from_old_pool(old_user_pool_id, shared_cognito_client):
    """Migrate users from old user pool to shared user pool"""
    cognito = boto3.client('cognito-idp')
    
    # List users from old pool
    response = cognito.list_users(UserPoolId=old_user_pool_id)
    
    for user in response['Users']:
        email = None
        for attr in user['Attributes']:
            if attr['Name'] == 'email':
                email = attr['Value']
                break
        
        if email:
            try:
                # Create user in shared pool
                cognito.admin_create_user(
                    UserPoolId=shared_cognito_client.get_user_pool_id(),
                    Username=email,
                    UserAttributes=[
                        {'Name': 'email', 'Value': email},
                        {'Name': 'email_verified', 'Value': 'true'}
                    ],
                    MessageAction='SUPPRESS'
                )
                print(f"Migrated user: {email}")
            except Exception as e:
                print(f"Failed to migrate {email}: {e}")
```

### Step 5: Clean Up Old Resources

After successful migration, clean up old Cognito user pools:

```bash
# List old user pools
aws cognito-idp list-user-pools --max-items 60

# Delete old user pools (be careful!)
aws cognito-idp delete-user-pool --user-pool-id us-east-1_OLDPOOL
```

## Configuration Reference

### Shared Cognito Stack Outputs

The shared Cognito stack provides these outputs:

| Output | Description | Usage |
|--------|-------------|-------|
| `UserPoolId` | Shared user pool ID | Backend authentication |
| `WebAppClientId` | Web application client | Frontend authentication |
| `APIClientId` | API client | Backend services |
| `MCPServerClientId` | MCP server client | AgentCore Runtime |
| `IdentityPoolId` | Identity pool | AWS resource access |
| `DiscoveryUrl` | OIDC discovery URL | JWT validation |
| `UserPoolDomain` | Cognito domain | OAuth flows |

### Client Application Types

1. **Web App Client**: For frontend applications (React, Angular, etc.)
   - OAuth flows enabled
   - Callback/logout URLs configured
   - No client secret

2. **API Client**: For backend services
   - User password authentication
   - Admin authentication flows
   - No OAuth flows

3. **MCP Server Client**: For AgentCore Runtime
   - User password authentication
   - JWT token validation
   - Used by MCP servers

### Environment Variables

Update your applications to use these environment variables:

```bash
# Shared Cognito configuration
COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
COGNITO_WEB_CLIENT_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX
COGNITO_API_CLIENT_ID=YYYYYYYYYYYYYYYYYYYYYYYYYY
COGNITO_MCP_CLIENT_ID=ZZZZZZZZZZZZZZZZZZZZZZZZZZ
COGNITO_IDENTITY_POOL_ID=us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
COGNITO_DOMAIN=cloud-optimization-prod-123456789012.auth.us-east-1.amazoncognito.com
COGNITO_DISCOVERY_URL=https://cognito-idp.us-east-1.amazonaws.com/us-east-1_XXXXXXXXX/.well-known/openid-configuration
```

## Deployment Scenarios

### Scenario 1: New Deployment
1. Deploy shared Cognito first
2. Deploy all components using refactored scripts
3. Configure applications with shared Cognito settings

### Scenario 2: Gradual Migration
1. Deploy shared Cognito alongside existing user pools
2. Migrate components one by one
3. Update callback URLs as needed
4. Clean up old user pools after migration

### Scenario 3: Multi-Environment
```bash
# Development environment
python deployment-scripts/deploy_shared_cognito.py \
  --stack-name cloud-optimization-shared-cognito-dev \
  --environment dev

# Staging environment
python deployment-scripts/deploy_shared_cognito.py \
  --stack-name cloud-optimization-shared-cognito-staging \
  --environment staging

# Production environment
python deployment-scripts/deploy_shared_cognito.py \
  --stack-name cloud-optimization-shared-cognito-prod \
  --environment prod
```

## Troubleshooting

### Common Issues

1. **Callback URL Mismatch**
   ```bash
   # Update callback URLs for web app client
   python -c "
   from cognito_utils import get_shared_cognito_client
   client = get_shared_cognito_client()
   client.update_client_callback_urls(
       client_id=client.get_web_app_client_id(),
       callback_urls=['https://your-domain.com/callback'],
       logout_urls=['https://your-domain.com/logout']
   )
   "
   ```

2. **JWT Validation Errors**
   - Ensure you're using the correct discovery URL
   - Verify the client ID in JWT validation
   - Check token expiration

3. **Cross-Origin Issues**
   - Update CORS settings in your backend
   - Ensure callback URLs include the correct protocol

### Verification Steps

1. **Test Authentication Flow**
   ```python
   from cognito_utils import get_shared_cognito_client
   
   client = get_shared_cognito_client()
   token = client.get_bearer_token('user@example.com', 'password')
   print(f"Token obtained: {token[:50]}...")
   ```

2. **Verify Stack Outputs**
   ```bash
   aws cloudformation describe-stacks \
     --stack-name cloud-optimization-shared-cognito \
     --query 'Stacks[0].Outputs'
   ```

3. **Test Client Configuration**
   ```python
   from cognito_utils import get_shared_cognito_client
   
   client = get_shared_cognito_client()
   config = client.get_cognito_config_for_frontend()
   print(json.dumps(config, indent=2))
   ```

## Security Considerations

1. **Client Secrets**: Web app clients don't use secrets (public clients)
2. **Token Validation**: Always validate JWT tokens on the backend
3. **HTTPS Only**: Use HTTPS for all callback URLs in production
4. **Token Expiration**: Configure appropriate token lifetimes
5. **User Attributes**: Limit user attributes to necessary information

## Cost Optimization

- **Before**: Multiple user pools × $0.0055 per MAU each
- **After**: Single user pool × $0.0055 per MAU total
- **Savings**: Significant reduction in Cognito costs for multiple components

## Next Steps

1. Deploy shared Cognito infrastructure
2. Test with a single component first
3. Gradually migrate other components
4. Update documentation and runbooks
5. Train team on new authentication flow
6. Monitor and optimize performance

For questions or issues, refer to the AWS Cognito documentation or contact the platform team.