# Deployment Scripts

This directory contains all deployment scripts for the AWS Well-Architected Cloud Optimization Suite components.

## 📋 **Available Scripts**

### 🚀 **Shared Infrastructure**

#### `deploy_shared_cognito.py`
**Purpose**: Deploy shared Cognito user pool infrastructure for all components
**Status**: ✅ **Production Ready**

```bash
python3 deploy_shared_cognito.py --create-test-user
```

**Features:**
- Creates centralized Cognito user pool
- Multiple client applications (Web, API, MCP)
- Automatic Parameter Store configuration at `/coa/cognito/*`
- Identity pool for AWS resource access

#### `deploy_all_with_shared_cognito.py`
**Purpose**: Deploy entire platform with shared Cognito
**Status**: ✅ **Production Ready**

```bash
python3 deploy_all_with_shared_cognito.py --region us-east-1
```

### 🔧 **Component Deployments**

#### `deploy_component_wa_security_mcp.py`
**Purpose**: Deploy WA Security MCP Server component
**Status**: ✅ **Production Ready**

```bash
python3 deploy_component_wa_security_mcp.py
```

**Features:**
- Uses shared Cognito from Parameter Store
- Deploys to AgentCore Runtime
- Stores configuration at `/coa/components/wa_security_mcp/`

#### `deploy_component_chatbot_webapp.py`
**Purpose**: Deploy Chatbot Web Application component
**Status**: ✅ **Production Ready**

```bash
python3 deploy_component_chatbot_webapp.py
```

**Features:**
- ECS Fargate deployment
- CloudFront distribution
- Uses shared Cognito authentication
- Stores configuration at `/coa/components/chatbot_webapp/`

### 🔧 **Legacy MCP Server Deployments**

#### `deploy_agentcore_runtime_wa_security_mcp.py`
**Purpose**: Deploy the Well-Architected Security MCP Server to AWS AgentCore Runtime
**Status**: ✅ **Production Ready**

```bash
python3 deploy_agentcore_runtime_wa_security_mcp.py
```

**Features:**
- Deploys security MCP server with 6 assessment tools
- Configures AgentCore Runtime integration
- Sets up proper IAM roles and permissions
- Includes health checks and validation

### 🛠️ **Utilities**

#### `get_cognito_config.py`
**Purpose**: Retrieve shared Cognito configuration from Parameter Store

```bash
# Get all configuration
python3 get_cognito_config.py

# Get specific parameter
python3 get_cognito_config.py --parameter user_pool_id

# Export as environment variables
eval $(python3 get_cognito_config.py --format env)
```

#### `test_parameter_store_integration.py`
**Purpose**: Test Parameter Store integration for shared Cognito

```bash
python3 test_parameter_store_integration.py --region us-east-1
```

#### `cognito_utils.py`
**Purpose**: Utility module for Cognito integration

```python
from cognito_utils import get_shared_cognito_client

client = get_shared_cognito_client()
user_pool_id = client.get_user_pool_id()
```


### Bedrock Agent Deployments

#### `deploy_bedrockagent_wa_security_agent.py`
**Purpose**: Deploy the Security Assessment Bedrock Agent
**Status**: ✅ **Production Ready**

```bash
python3 deploy_bedrockagent_wa_security_agent.py
```

**Features:**
- Creates Bedrock Agent with security expertise
- Configures Claude 3.5 Sonnet integration
- Sets up MCP tool integration
- Includes memory and context management

## 🚀 **Deployment Order**

For a complete setup, deploy in this order:

1. **Deploy MCP Server**
   ```bash
   python3 deploy_agentcore_runtime_wa_security_mcp.py
   ```

2. **Deploy Bedrock Agent**
   ```bash
   python3 deploy_bedrockagent_wa_security_agent.py
   ```

3. **Launch Web Interface In local**
   ```bash
   cd ../cloud-optimization-web-interfaces/cloud-optimization-web-interface
   Edit .venv with required settings.
   python3 start_server.py
   ```

4. **Test Integration**
   ```bash
   cd ../cloud-optimization-web-interfaces/cloud-optimization-web-interface
   python3 test_integration.py
   ```

## 🔧 **Configuration**

### Prerequisites
- AWS CLI configured with appropriate permissions
- Python 3.8+ with required dependencies
- Access to Amazon Bedrock and AgentCore services

### Deployment Artifacts
The deployment scripts create temporary directories during deployment:
- `wa-security-direct-deploy/` - Created by `deploy_wa_security_direct.py`
- `wa-security-mcp-deploy/` - Created by `deploy_wa_security_mcp.py`

These directories are automatically created and can be safely deleted after deployment.

### Required Permissions
The deployment scripts require the following AWS permissions:
- `bedrock:*` - For Bedrock agent creation and management
- `bedrock-agentcore:*` - For AgentCore Runtime operations
- `iam:CreateRole`, `iam:AttachRolePolicy` - For IAM role management
- `lambda:*` - For serverless function deployment (if applicable)

## 📊 **Deployment Status**

| Component | Script | Status | Last Updated |
|-----------|--------|--------|--------------|
| Security MCP Server | `deploy_wa_security_mcp.py` | ✅ **Deployed** | Latest |
| Security Agent | `deploy_security_agent.py` | ✅ **Deployed** | Latest |
| Reliability MCP Server | *TBD* | 🔄 **Planned** | - |
| Cost Optimization Agent | *TBD* | 🔄 **Planned** | - |

## 🧪 **Testing Deployments**

After deployment, use these commands to verify:

### Test MCP Server
```bash
# From the web interface directory
python3 test_integration.py
```

### Test Bedrock Agent
```bash
# Test agent functionality
python3 test_bedrock_agent.py
```

### Test Full Integration
```bash
# Launch web interface and test end-to-end
cd ../cloud-optimization-web-interfaces/cloud-optimization-web-interface
python3 start_server.py
```

## 🔍 **Troubleshooting**

### Common Issues

#### Permission Errors
```bash
# Ensure AWS credentials are configured
aws configure list
aws sts get-caller-identity
```

#### Deployment Failures
- Check AWS service quotas and limits
- Verify region availability for Bedrock services
- Review CloudFormation stack events for detailed errors

#### Integration Issues
- Verify MCP server is accessible from AgentCore Runtime
- Check Bedrock agent configuration and tool definitions
- Test WebSocket connections for web interface

## 📝 **Logs and Monitoring**

### Deployment Logs
- Scripts output detailed logs during deployment
- Check CloudWatch logs for runtime issues
- AgentCore Runtime provides execution logs

### Monitoring
- Use AWS CloudWatch for service monitoring
- Check Bedrock agent invocation metrics
- Monitor MCP server response times and errors

## 🔄 **Updates and Maintenance**

### Updating Components
1. Pull latest code changes
2. Run deployment script with `--update` flag (if supported)
3. Verify functionality with integration tests

### Rollback Procedures
- Each deployment script supports rollback capabilities
- Use AWS CloudFormation stack rollback for infrastructure changes
- Maintain backup configurations for quick recovery

---

**🚀 These scripts provide automated deployment of the complete cloud optimization suite!**