#!/usr/bin/env python3
"""
EXAMPLE: Updated Security Agent using Configuration Manager
This shows how to replace hard-coded configurations with SSM parameters
"""

import asyncio
import json
import boto3
from datetime import timedelta
from typing import AsyncGenerator, List, Dict, Any, Optional
from bedrock_agentcore.agent import Agent
from bedrock_agentcore.memory import MemoryHook
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import logging

# Import the new configuration manager
from agents.shared.config_manager import get_config_manager, get_agent_config, get_component_config, get_cognito_config

logger = logging.getLogger(__name__)


class UpdatedSecurityAgent(Agent):
    """
    Updated Security Agent using Configuration Manager instead of hard-coded values
    """
    
    def __init__(
        self,
        bearer_token: str,
        memory_hook: MemoryHook,
        agent_name: str = "wa_security_agent",
        **kwargs
    ):
        """Initialize the Security Agent with configuration from SSM Parameter Store"""
        
        # Get configuration from Parameter Store
        self.config_manager = get_config_manager()
        self.agent_config = get_agent_config(agent_name)
        self.cognito_config = get_cognito_config()
        
        # Use configuration values instead of hard-coded ones
        model_id = self.agent_config.get('model_id', "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
        region = self.agent_config.get('region', "us-east-1")
        
        super().__init__(
            bearer_token=bearer_token,
            memory_hook=memory_hook,
            model_id=model_id,
            **kwargs
        )
        
        self.region = region
        self.agent_name = agent_name
        self.mcp_session = None
        self.mcp_tools = []
        self.mcp_url = None
        self.mcp_headers = None
        
        # Store responses for comprehensive analysis
        self.session_responses = []
        
        # Initialize MCP connection
        asyncio.create_task(self._initialize_mcp_connection())
        
        logger.info(f"Security Agent initialized with config from Parameter Store")
        logger.info(f"Region: {self.region}, Model: {model_id}")
    
    async def _initialize_mcp_connection(self):
        """Initialize connection to the Well-Architected Security MCP Server using configuration"""
        try:
            logger.info("Initializing MCP connection using Parameter Store configuration...")
            
            # Get MCP component configuration
            mcp_config = get_component_config("wa_security_mcp")
            
            # Get agent ARN from configuration
            agent_arn = mcp_config.get('agent_arn')
            if not agent_arn:
                logger.error("MCP agent ARN not found in configuration")
                return
            
            # Get credentials from Secrets Manager
            credentials = self.config_manager.get_mcp_server_credentials("wa_security_mcp")
            bearer_token = credentials.get('bearer_token')
            
            if not bearer_token:
                # Fallback to Cognito configuration
                cognito_secret_name = self.cognito_config.get('bearer_token_secret_name')
                if cognito_secret_name:
                    cognito_credentials = self.config_manager.get_secret(cognito_secret_name, {})
                    bearer_token = cognito_credentials.get('bearer_token')
            
            if not bearer_token:
                logger.error("Bearer token not found in configuration")
                return
            
            # Build MCP connection details using configuration
            encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
            self.mcp_url = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
            self.mcp_headers = {
                "authorization": f"Bearer {bearer_token}",
                "Content-Type": "application/json"
            }
            
            # Test connection and get available tools
            await self._discover_mcp_tools()
            
            logger.info(f"✅ MCP connection initialized with {len(self.mcp_tools)} security tools")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP connection: {e}")
            self.mcp_tools = []
    
    async def _discover_mcp_tools(self):
        """Discover available MCP tools with configurable timeout"""
        try:
            # Get timeout from configuration
            mcp_config = get_component_config("wa_security_mcp")
            timeout_seconds = mcp_config.get('timeout', 30)
            
            async with streamablehttp_client(
                self.mcp_url, 
                self.mcp_headers, 
                timeout=timedelta(seconds=timeout_seconds)
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tool_result = await session.list_tools()
                    self.mcp_tools = [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.inputSchema.get("properties", {}) if hasattr(tool, 'inputSchema') and tool.inputSchema else {}
                        }
                        for tool in tool_result.tools
                    ]
        except Exception as e:
            logger.error(f"Failed to discover MCP tools: {e}")
            self.mcp_tools = []
    
    async def _call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any], user_query: str = "") -> Optional[str]:
        """Call an MCP tool with configurable timeout and retry"""
        try:
            logger.info(f"Calling MCP tool: {tool_name} with args: {arguments}")
            
            # Get configuration for timeout and retry
            mcp_config = get_component_config("wa_security_mcp")
            timeout_seconds = mcp_config.get('timeout', 120)
            retry_attempts = mcp_config.get('retry_attempts', 3)
            
            for attempt in range(retry_attempts):
                try:
                    async with streamablehttp_client(
                        self.mcp_url, 
                        self.mcp_headers, 
                        timeout=timedelta(seconds=timeout_seconds)
                    ) as (read_stream, write_stream, _):
                        async with ClientSession(read_stream, write_stream) as session:
                            await session.initialize()
                            result = await session.call_tool(name=tool_name, arguments=arguments)
                            raw_response = result.content[0].text
                            
                            logger.info(f"MCP tool {tool_name} completed successfully")
                            return raw_response
                            
                except Exception as e:
                    if attempt < retry_attempts - 1:
                        logger.warning(f"MCP tool {tool_name} attempt {attempt + 1} failed, retrying: {e}")
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        raise e
                        
        except Exception as e:
            logger.error(f"Failed to call MCP tool {tool_name} after {retry_attempts} attempts: {e}")
            return f"Error calling {tool_name}: {str(e)}"
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt with configuration-aware tool descriptions"""
        tools_description = "\n".join([
            f"- {tool['name']}: {tool['description']}"
            for tool in self.mcp_tools
        ])
        
        # Get session configuration
        session_ttl = self.agent_config.get('session_ttl', 1800)
        
        return f"""You are an Enhanced Well-Architected Security Expert Assistant.

Your role is to help users assess, understand, and improve their AWS security posture according to the AWS Well-Architected Framework Security Pillar.

## Configuration:
- Region: {self.region}
- Model: {self.agent_config.get('model_id', 'default')}
- Session TTL: {session_ttl} seconds
- Available Tools: {len(self.mcp_tools)}

## Available Security Assessment Tools:
{tools_description}

## Enhanced Capabilities:
1. **Real-Time Assessment**: Use MCP tools to get current AWS security data
2. **Intelligent Analysis**: Transform raw data into actionable insights
3. **Risk Prioritization**: Focus on critical and high-severity issues first
4. **Business Context**: Explain security issues in business terms and impact
5. **Remediation Guidance**: Provide specific, step-by-step remediation instructions

## Response Style Guidelines:
- **Comprehensive but Digestible**: Detailed analysis presented in clear, structured format
- **Visual Enhancement**: Use emojis, formatting, and visual indicators for better readability
- **Action-Oriented**: Always include specific next steps and recommendations
- **Risk-Focused**: Prioritize critical and high-risk issues
- **Business-Aware**: Explain technical issues in business impact terms

Remember: You provide intelligence, not just data. Transform every response into actionable insights that help users improve their security posture effectively."""

    async def _process_security_query(self, user_message: str) -> str:
        """Process user query and determine which security tools to use"""
        user_message_lower = user_message.lower()
        
        # Determine which tools to call based on user intent
        tool_calls = []
        
        # Security services queries
        if any(word in user_message_lower for word in ['security services', 'guardduty', 'security hub', 'inspector']):
            tool_calls.append({
                'tool': 'CheckSecurityServices',
                'args': {
                    'region': self.region,
                    'services': ['guardduty', 'securityhub', 'inspector', 'accessanalyzer', 'macie'],
                    'debug': True,
                    'store_in_context': True
                }
            })
        
        # Storage encryption queries
        if any(word in user_message_lower for word in ['s3', 'encryption', 'encrypted', 'storage', 'buckets']):
            tool_calls.append({
                'tool': 'CheckStorageEncryption',
                'args': {
                    'region': self.region,
                    'services': ['s3', 'ebs', 'rds', 'dynamodb'],
                    'store_in_context': True
                }
            })
        
        # Network security queries
        if any(word in user_message_lower for word in ['network', 'https', 'ssl', 'tls', 'load balancer']):
            tool_calls.append({
                'tool': 'CheckNetworkSecurity',
                'args': {
                    'region': self.region,
                    'services': ['elb', 'apigateway', 'cloudfront'],
                    'store_in_context': True
                }
            })
        
        # Execute tool calls and collect results
        tool_results = []
        for tool_call in tool_calls:
            logger.info(f"Processing tool call: {tool_call['tool']}")
            result = await self._call_mcp_tool(
                tool_name=tool_call['tool'], 
                arguments=tool_call['args'],
                user_query=user_message
            )
            if result:
                tool_results.append(result)
        
        # Combine results
        if len(tool_results) > 1:
            separator = "\n" + "="*50 + "\n\n"
            return separator.join(tool_results)
        elif tool_results:
            return tool_results[0]
        else:
            return ""
    
    async def stream(self, user_query: str) -> AsyncGenerator[str, None]:
        """Stream enhanced response to user query with configuration-aware processing"""
        try:
            logger.info(f"Processing security query: {user_query}")
            
            # Get security data using MCP tools
            security_data = await self._process_security_query(user_query)
            
            if security_data:
                # Stream the security data
                yield security_data + "\n\n"
                yield "---\n\n"
                yield "## 🧠 Strategic Analysis & Recommendations\n\n"
                
                # Prepare enhanced query for Claude
                enhanced_query = f"""User Query: {user_query}

## Security Assessment Results
{security_data}

Based on this security assessment, provide strategic insights and recommendations focusing on:
1. **Key Findings**: What are the most important security issues identified?
2. **Risk Prioritization**: Which issues should be addressed first and why?
3. **Implementation Guidance**: Specific steps to remediate identified issues
4. **Best Practices**: Additional AWS Well-Architected security recommendations
5. **Monitoring**: How to maintain and monitor these security improvements

Keep your response actionable and business-focused."""
                
                # Stream Claude's analysis
                async for chunk in super().stream(user_query=enhanced_query):
                    yield chunk
            else:
                # No specific security tools triggered, use general knowledge
                enhanced_query = f"""User Query: {user_query}

As a Well-Architected Security Expert, provide comprehensive guidance including:
1. **Direct Answer**: Address the specific security question
2. **Best Practices**: Relevant AWS security principles and recommendations
3. **Implementation Steps**: Practical guidance for implementation
4. **Risk Considerations**: Potential security risks and mitigation strategies
5. **Monitoring**: How to maintain security posture over time

Use clear formatting and actionable recommendations."""
                
                async for chunk in super().stream(user_query=enhanced_query):
                    yield chunk
                
        except Exception as e:
            logger.error(f"Error in security agent stream: {e}")
            yield f"❌ **Error Processing Security Query**: {str(e)}\n\nPlease check your configuration and try again."
    
    def get_configuration_status(self) -> Dict[str, Any]:
        """Get current configuration status for debugging"""
        return {
            'agent_name': self.agent_name,
            'region': self.region,
            'agent_config': self.agent_config,
            'cognito_config': {k: v for k, v in self.cognito_config.items() if 'secret' not in k.lower()},
            'mcp_tools_count': len(self.mcp_tools),
            'mcp_connection_status': 'connected' if self.mcp_url else 'not_connected',
            'config_manager_health': self.config_manager.health_check()
        }
    
    async def validate_configuration(self) -> Dict[str, Any]:
        """Validate that all required configuration is available"""
        required_agent_params = [
            f"/coa/agents/{self.agent_name}/region",
            f"/coa/agents/{self.agent_name}/model_id"
        ]
        
        required_component_params = [
            "/coa/components/wa_security_mcp/agent_arn"
        ]
        
        required_cognito_params = [
            "/coa/cognito/user_pool_id",
            "/coa/cognito/mcp_server_client_id"
        ]
        
        all_required = required_agent_params + required_component_params + required_cognito_params
        
        validation_results = self.config_manager.validate_configuration(all_required)
        
        return {
            'overall_status': 'valid' if all(validation_results.values()) else 'invalid',
            'agent_params': {k: v for k, v in validation_results.items() if k in required_agent_params},
            'component_params': {k: v for k, v in validation_results.items() if k in required_component_params},
            'cognito_params': {k: v for k, v in validation_results.items() if k in required_cognito_params},
            'missing_params': [k for k, v in validation_results.items() if not v]
        }


# Example usage and testing
async def example_usage():
    """Example of how to use the updated security agent"""
    
    # Initialize with configuration from Parameter Store
    from bedrock_agentcore.memory import MemoryHook
    
    # Mock memory hook for example
    class MockMemoryHook(MemoryHook):
        def __init__(self):
            pass
    
    try:
        # Create agent with configuration manager
        agent = UpdatedSecurityAgent(
            bearer_token="example_token",
            memory_hook=MockMemoryHook(),
            agent_name="wa_security_agent"
        )
        
        # Check configuration status
        config_status = agent.get_configuration_status()
        print("Configuration Status:")
        print(json.dumps(config_status, indent=2, default=str))
        
        # Validate configuration
        validation_results = await agent.validate_configuration()
        print("\nValidation Results:")
        print(json.dumps(validation_results, indent=2))
        
        # Example query
        print("\nProcessing example security query...")
        async for chunk in agent.stream("Check my security services status"):
            print(chunk, end='')
        
    except Exception as e:
        print(f"Error in example usage: {e}")


if __name__ == "__main__":
    asyncio.run(example_usage())