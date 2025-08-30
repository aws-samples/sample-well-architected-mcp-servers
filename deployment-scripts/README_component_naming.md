# Component Deployment Script Naming Convention

This document explains the naming convention for component deployment scripts in the AWS Well-Architected Cloud Optimization Suite.

## Naming Convention

Component deployment scripts follow these patterns:

### Primary Pattern (Recommended)
```
deploy_component_<component_name>.py
```

### Specialized Patterns
```
deploy_<specific_service>_<component_type>.py    # For specialized deployments
deploy_agentcore_runtime_<component_name>.py    # For AgentCore Runtime deployments
```

Where `<component_name>` matches the component name used in Parameter Store paths.

## Current Components

| Component | Script Name | Parameter Store Path | Type |
|-----------|-------------|---------------------|------|
| WA Security MCP | `deploy_component_wa_security_mcp.py` | `/coa/components/wa_security_mcp/` | Component |
| Chatbot Web App | `deploy_component_chatbot_webapp.py` | `/coa/components/chatbot_webapp/` | Component |
| AWS API MCP Server | `deploy_component_aws_api_mcp_server.py` | `/coa/components/aws_api_mcp_server/` | Component |
| Bedrock Security Agent | `deploy_bedrockagent_wa_security_agent.py` | `/coa/agents/wa_security_agent/` | Agent |
| AgentCore AWS API MCP | `deploy_agentcore_runtime_aws_api_mcp_server.py` | `/coa/agentcore/aws_api_mcp/` | Runtime |
| Frontend CloudFront | `deploy_frontend_cloudfront.py` | `/coa/frontend/cloudfront/` | Infrastructure |

## Parameter Store Alignment

The component names in deployment scripts align with Parameter Store paths:

### Component Configuration Storage
```
/coa/components/<component_name>/
├── agent_arn          # For MCP components
├── agent_id           # For MCP components
├── cloudfront_url     # For web applications
├── s3_bucket_name     # For web applications
├── lambda_arn         # For serverless components
├── api_endpoint       # For API components
└── ...                # Other component-specific config
```

### Agent Configuration Storage
```
/coa/agents/<agent_name>/
├── agent_arn          # Bedrock Agent ARN
├── agent_id           # Bedrock Agent ID
├── agent_alias_id     # Agent alias for production
├── knowledge_base_id  # Associated knowledge bases
└── ...                # Agent-specific config
```

### AgentCore Runtime Configuration
```
/coa/agentcore/<runtime_name>/
├── runtime_id         # AgentCore Runtime ID
├── server_endpoint    # MCP server endpoint
├── health_check_url   # Health monitoring endpoint
└── ...                # Runtime-specific config
```

### Shared Configuration Access
All components access shared Cognito configuration from:
```
/coa/cognito/
├── user_pool_id
├── web_app_client_id
├── api_client_id
├── mcp_server_client_id
├── identity_pool_id
├── discovery_url
└── ...
```

## Benefits of This Convention

1. **Consistency**: Easy to predict script names from component names
2. **Parameter Store Alignment**: Script names match parameter paths
3. **Discoverability**: Clear relationship between deployment and configuration
4. **Maintainability**: Easier to manage multiple components

## Usage Examples

### Deploy Individual Components
```bash
# Deploy WA Security MCP Server
python deployment-scripts/deploy_component_wa_security_mcp.py

# Deploy Chatbot Web Application
python deployment-scripts/deploy_component_chatbot_webapp.py

# Deploy AWS API MCP Server
python deployment-scripts/deploy_component_aws_api_mcp_server.py
```

### Deploy Specialized Services
```bash
# Deploy Bedrock Security Agent
python deployment-scripts/deploy_bedrockagent_wa_security_agent.py

# Deploy AgentCore Runtime with AWS API MCP
python deployment-scripts/deploy_agentcore_runtime_aws_api_mcp_server.py

# Deploy Frontend with CloudFront
python deployment-scripts/deploy_frontend_cloudfront.py
```

### Deploy All Components
```bash
# Deploy everything with shared Cognito
python deployment-scripts/deploy_all_with_shared_cognito.py
```

### Get Component Configuration
```bash
# Get WA Security MCP configuration
aws ssm get-parameters-by-path --path /coa/components/wa_security_mcp/

# Get Chatbot Web App configuration
aws ssm get-parameters-by-path --path /coa/components/chatbot_webapp/

# Get Bedrock Agent configuration
aws ssm get-parameters-by-path --path /coa/agents/wa_security_agent/

# Get AgentCore Runtime configuration
aws ssm get-parameters-by-path --path /coa/agentcore/aws_api_mcp/
```

## Adding New Components

When adding a new component, choose the appropriate pattern:

### For Standard Components
1. **Create deployment script**: `deploy_component_<new_component>.py`
2. **Store configuration**: Use `/coa/components/<new_component>/` path
3. **Access shared config**: Use `get_shared_cognito_client()` from `cognito_utils.py`
4. **Update documentation**: Add to this table and relevant guides

### For Bedrock Agents
1. **Create deployment script**: `deploy_bedrockagent_<agent_name>.py`
2. **Store configuration**: Use `/coa/agents/<agent_name>/` path
3. **Include agent configuration**: Agent instructions, tools, and knowledge bases

### For AgentCore Runtime Services
1. **Create deployment script**: `deploy_agentcore_runtime_<service_name>.py`
2. **Store configuration**: Use `/coa/agentcore/<service_name>/` path
3. **Include runtime config**: Server endpoints, health checks, and monitoring

### Example New Component

For a component called `data_processor`:

1. **Script**: `deploy_component_data_processor.py`
2. **Parameters**: 
   - `/coa/components/data_processor/lambda_arn`
   - `/coa/components/data_processor/queue_url`
   - `/coa/components/data_processor/api_endpoint`
3. **Shared Access**: Uses `/coa/cognito/*` parameters automatically

### Example New Agent

For an agent called `cost_optimizer`:

1. **Script**: `deploy_bedrockagent_cost_optimizer.py`
2. **Parameters**:
   - `/coa/agents/cost_optimizer/agent_arn`
   - `/coa/agents/cost_optimizer/agent_id`
   - `/coa/agents/cost_optimizer/agent_alias_id`

## Current Deployment Scripts

### ✅ Production Ready
- `deploy_shared_cognito.py` - Shared Cognito infrastructure
- `deploy_all_with_shared_cognito.py` - Complete platform deployment
- `deploy_component_wa_security_mcp.py` - WA Security MCP Server
- `deploy_component_chatbot_webapp.py` - Chatbot Web Application
- `deploy_component_aws_api_mcp_server.py` - AWS API MCP Server
- `deploy_bedrockagent_wa_security_agent.py` - Security Assessment Agent
- `deploy_agentcore_runtime_aws_api_mcp_server.py` - AgentCore AWS API MCP
- `deploy_frontend_cloudfront.py` - Frontend with CloudFront

### 🔧 Utilities
- `cognito_utils.py` - Shared Cognito utilities
- `get_cognito_config.py` - Configuration retrieval
- `test_parameter_store_integration.py` - Integration testing
- `test_wa_security_agentcore_runtime.py` - Runtime testing

### 🚀 Infrastructure
- `deploy_with_codebuild.py` - CI/CD deployment
- `setup-cross-account-roles.sh` - Cross-account setup
- `deploy_webapp.sh` - Web application deployment script

## Migration from Old Names

| Old Name | New Name | Status |
|----------|----------|--------|
| `deploy_wa_security_agentcore_runtime_refactored.py` | `deploy_component_wa_security_mcp.py` | ✅ Migrated |
| `deploy_chatbot_webapp_refactored.py` | `deploy_component_chatbot_webapp.py` | ✅ Migrated |
| `deploy_aws_api_mcp_standalone.py` | `deploy_component_aws_api_mcp_server.py` | ✅ Migrated |

All references in documentation and other scripts have been updated to use the new names.