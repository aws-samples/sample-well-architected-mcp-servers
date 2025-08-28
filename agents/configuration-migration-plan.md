# Agent Configuration Migration Plan

## Overview
This document outlines the migration plan to replace hard-coded configurations in agent files with SSM parameters based on the updated parameter design.

## Hard-Coded Configurations Identified

### 1. Region Configuration
**Current Issues:**
- Hard-coded `region = "us-east-1"` in multiple files
- No flexibility for multi-region deployments

**Files to Update:**
- `agents/bedrock-agents/wa-security-agent-multi-mcps/agent_config/wa_security_agent.py`
- `agents/bedrock-agents/wa-security-agent-single-wa-sec-mcp/agent_config/security_agent.py`
- `agents/bedrock-agents/wa-security-agent-multi-mcps/deploy_enhanced_security_agent.py`
- `agents/bedrock-agents/wa-security-agent-single-wa-sec-mcp/agent_config/utils.py`

**SSM Parameter:** `/coa/agents/wa_security_agent/region`

### 2. Model Configuration
**Current Issues:**
- Hard-coded model IDs like `"us.anthropic.claude-3-7-sonnet-20250219-v1:0"`
- No easy way to update model versions

**Files to Update:**
- `agents/bedrock-agents/wa-security-agent-multi-mcps/agent_config/wa_security_agent.py`
- `agents/bedrock-agents/wa-security-agent-single-wa-sec-mcp/agent_config/security_agent.py`
- `agents/bedrock-agents/wa-security-agent-single-wa-sec-mcp/agent_config/agent_task.py`

**SSM Parameters:**
- `/coa/agents/wa_security_agent/model_id`
- `/coa/agents/wa_security_agent/model_version`

### 3. MCP Server Configuration
**Current Issues:**
- Hard-coded parameter paths like `/wa_security_direct_mcp/runtime/agent_arn`
- Inconsistent parameter naming

**Files to Update:**
- `agents/bedrock-agents/wa-security-agent-single-wa-sec-mcp/agent_config/security_agent.py`
- `agents/bedrock-agents/wa-security-agent-multi-mcps/agent_config/wa_security_agent.py`

**SSM Parameters:**
- `/coa/components/wa_security_mcp/agent_arn`
- `/coa/components/wa_security_mcp/agent_id`
- `/coa/components/wa_security_mcp/runtime_id`

### 4. Authentication Configuration
**Current Issues:**
- Hard-coded secret paths and Cognito configuration
- Mixed parameter naming conventions

**Files to Update:**
- `agents/bedrock-agents/wa-security-agent-single-wa-sec-mcp/agent_config/security_agent.py`
- `agents/bedrock-agents/wa-security-agent-single-wa-sec-mcp/deploy_security_agent.py`

**SSM Parameters:**
- `/coa/cognito/user_pool_id`
- `/coa/cognito/mcp_server_client_id`
- `/coa/cognito/discovery_url`
- `/coa/cognito/bearer_token_secret_name`

### 5. AWS Knowledge MCP Server Configuration
**Current Issues:**
- Hard-coded URL `"https://knowledge-mcp.global.api.aws"`
- Hard-coded timeout values

**Files to Update:**
- `agents/bedrock-agents/wa-security-agent-multi-mcps/agent_config/integrations/aws_knowledge_integration.py`
- `agents/bedrock-agents/wa-security-agent-multi-mcps/aws_knowledge_mcp_config_example.json`

**SSM Parameters:**
- `/coa/components/aws_knowledge_mcp/server_url`
- `/coa/components/aws_knowledge_mcp/timeout`
- `/coa/components/aws_knowledge_mcp/retry_attempts`

### 6. Memory and Session Configuration
**Current Issues:**
- Hard-coded memory configuration paths
- Hard-coded session TTL values

**Files to Update:**
- `agents/bedrock-agents/wa-security-agent-single-wa-sec-mcp/agent_config/agent_task.py`

**SSM Parameters:**
- `/coa/agents/wa_security_agent/memory_id`
- `/coa/agents/wa_security_agent/session_ttl`
- `/coa/agents/wa_security_agent/idle_timeout`

### 7. AWS API MCP Server Configuration
**Current Issues:**
- Commented out hard-coded configuration block in `wa_security_agent.py`
- Bearer token and credentials hard-coded

**Files to Update:**
- `agents/bedrock-agents/wa-security-agent-multi-mcps/agent_config/wa_security_agent.py`

**SSM Parameters:**
- `/coa/components/aws_api_mcp_server/agent_arn`
- `/coa/components/aws_api_mcp_server/bearer_token_secret_name`
- `/coa/components/aws_api_mcp_server/client_id`

## Migration Strategy

### Phase 1: Create Utility Functions
1. Create a centralized configuration manager
2. Add SSM parameter retrieval functions
3. Add caching for frequently accessed parameters

### Phase 2: Update Agent Configuration Files
1. Replace hard-coded values with SSM parameter calls
2. Add fallback values for development/testing
3. Update error handling for missing parameters

### Phase 3: Update Deployment Scripts
1. Ensure deployment scripts create the required SSM parameters
2. Update parameter paths to match new naming convention
3. Add parameter validation

### Phase 4: Testing and Validation
1. Test agents with new parameter-based configuration
2. Validate parameter retrieval performance
3. Test fallback mechanisms

## Implementation Details

### Configuration Manager
```python
class AgentConfigurationManager:
    def __init__(self, region: str = None):
        self.region = region or self._get_default_region()
        self.ssm_client = boto3.client('ssm', region_name=self.region)
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
    
    def get_parameter(self, parameter_name: str, default: str = None) -> str:
        # Implementation with caching and error handling
        pass
    
    def get_agent_config(self, agent_name: str) -> Dict[str, Any]:
        # Get all configuration for a specific agent
        pass
```

### Parameter Naming Convention
All parameters follow the pattern: `/coa/{component_type}/{component_name}/{parameter_name}`

Examples:
- `/coa/agents/wa_security_agent/model_id`
- `/coa/components/wa_security_mcp/agent_arn`
- `/coa/cognito/user_pool_id`

### Error Handling Strategy
1. **Graceful Degradation**: Use sensible defaults when parameters are missing
2. **Logging**: Log parameter retrieval failures for debugging
3. **Validation**: Validate parameter values before use
4. **Retry Logic**: Implement retry for transient SSM failures

## Benefits of Migration

### 1. **Centralized Configuration Management**
- All configuration in one place (Parameter Store)
- Easy to update without code changes
- Consistent parameter naming across components

### 2. **Environment Flexibility**
- Easy deployment across different regions
- Support for multiple environments (dev, staging, prod)
- Dynamic configuration updates

### 3. **Security Improvements**
- Sensitive values stored in Parameter Store/Secrets Manager
- IAM-based access control
- Audit trail for configuration changes

### 4. **Operational Excellence**
- Reduced deployment complexity
- Better monitoring and alerting capabilities
- Easier troubleshooting with centralized config

## Next Steps

1. **Review and Approve**: Review this migration plan with the team
2. **Create Configuration Manager**: Implement the centralized configuration utility
3. **Update Deployment Scripts**: Ensure all required parameters are created
4. **Migrate Agent Files**: Update agent configuration files systematically
5. **Test and Validate**: Comprehensive testing of the new configuration system
6. **Documentation**: Update documentation to reflect new parameter structure

## Risk Mitigation

### 1. **Backward Compatibility**
- Maintain fallback to hard-coded values during transition
- Gradual migration approach
- Comprehensive testing

### 2. **Performance Considerations**
- Implement parameter caching
- Batch parameter retrieval where possible
- Monitor SSM API usage

### 3. **Failure Handling**
- Graceful degradation when parameters are unavailable
- Clear error messages for missing configuration
- Health checks for configuration validity