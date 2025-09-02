# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
Unit tests for MCP Connectors
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from agent_config.orchestration.connectors import SecurityMCPConnector, KnowledgeMCPConnector, APIMCPConnector
from agent_config.orchestration.connection_pool import ConnectionPoolManager
from agent_config.interfaces import MCPServerConfig, MCPServerType, ToolResult


class TestBaseMCPConnector:
    """Test cases for base MCP connector functionality"""
    
    @pytest.fixture
    def security_config(self):
        """Create security MCP server config"""
        return MCPServerConfig(
            name="security",
            server_type=MCPServerType.SECURITY,
            connection_type="agentcore",
            timeout=120,
            retry_attempts=3
        )
    
    @pytest.fixture
    def connection_pool(self):
        """Create connection pool manager"""
        return ConnectionPoolManager()
    
    @pytest.fixture
    def security_connector(self, security_config, connection_pool):
        """Create security MCP connector"""
        return SecurityMCPConnector(security_config, "us-east-1", connection_pool)
    
    def test_base_connector_initialization(self, security_connector, security_config):
        """Test base connector initialization"""
        assert security_connector.config == security_config
        assert security_connector.region == "us-east-1"
        assert security_connector.is_initialized is False
        assert security_connector.last_health_check == 0
    
    @pytest.mark.asyncio
    async def test_health_check_caching(self, security_connector):
        """Test health check result caching"""
        # Mock the actual health check
        security_connector._perform_health_check = AsyncMock(return_value=True)
        
        # First call should perform actual check
        result1 = await security_connector.health_check()
        assert result1 is True
        security_connector._perform_health_check.assert_called_once()
        
        # Second call within cache duration should use cached result
        security_connector._perform_health_check.reset_mock()
        result2 = await security_connector.health_check()
        assert result2 is True
        security_connector._perform_health_check.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self, security_connector):
        """Test successful operation with retry logic"""
        mock_operation = AsyncMock(return_value="success")
        
        result = await security_connector._execute_with_retry(mock_operation, "arg1", kwarg1="value1")
        
        assert result == "success"
        mock_operation.assert_called_once_with("arg1", kwarg1="value1")
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_failure_then_success(self, security_connector):
        """Test retry logic with initial failure then success"""
        mock_operation = AsyncMock(side_effect=[Exception("First failure"), "success"])
        
        result = await security_connector._execute_with_retry(mock_operation)
        
        assert result == "success"
        assert mock_operation.call_count == 2
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_all_failures(self, security_connector):
        """Test retry logic with all attempts failing"""
        mock_operation = AsyncMock(side_effect=Exception("Always fails"))
        
        with pytest.raises(Exception, match="Always fails"):
            await security_connector._execute_with_retry(mock_operation)
        
        assert mock_operation.call_count == 3  # retry_attempts = 3


class TestSecurityMCPConnector:
    """Test cases for Security MCP Connector"""
    
    @pytest.fixture
    def security_config(self):
        """Create security MCP server config"""
        return MCPServerConfig(
            name="security",
            server_type=MCPServerType.SECURITY,
            connection_type="agentcore",
            timeout=120,
            retry_attempts=3
        )
    
    @pytest.fixture
    def connection_pool(self):
        """Create connection pool manager"""
        return ConnectionPoolManager()
    
    @pytest.fixture
    def security_connector(self, security_config, connection_pool):
        """Create security MCP connector"""
        return SecurityMCPConnector(security_config, "us-east-1", connection_pool)
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, security_connector):
        """Test successful initialization"""
        with patch('boto3.client') as mock_boto3:
            # Mock SSM client
            mock_ssm = Mock()
            mock_ssm.get_parameter.return_value = {
                'Parameter': {'Value': 'arn:aws:bedrock-agent:us-east-1:123456789012:agent/test-agent'}
            }
            
            # Mock Secrets Manager client
            mock_secrets = Mock()
            mock_secrets.get_secret_value.return_value = {
                'SecretString': '{"bearer_token": "test-token"}'
            }
            
            mock_boto3.side_effect = [mock_ssm, mock_secrets]
            
            # Mock test connection
            security_connector._test_connection = AsyncMock()
            
            result = await security_connector.initialize()
            
            assert result is True
            assert security_connector.is_initialized is True
            assert security_connector.mcp_url is not None
            assert security_connector.mcp_headers is not None
            security_connector._test_connection.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_missing_credentials(self, security_connector):
        """Test initialization with missing credentials"""
        with patch('boto3.client') as mock_boto3:
            mock_ssm = Mock()
            mock_ssm.get_parameter.side_effect = Exception("Parameter not found")
            mock_boto3.return_value = mock_ssm
            
            result = await security_connector.initialize()
            
            assert result is False
            assert security_connector.is_initialized is False
    
    @pytest.mark.asyncio
    async def test_discover_tools_success(self, security_connector):
        """Test successful tool discovery"""
        security_connector.is_initialized = True
        security_connector.mcp_url = "https://test.com"
        security_connector.mcp_headers = {"Authorization": "Bearer test"}
        
        # Mock the internal discovery method
        expected_tools = [
            {"name": "CheckSecurityServices", "description": "Check security services", "mcp_server": "security"}
        ]
        security_connector._discover_tools_internal = AsyncMock(return_value=expected_tools)
        
        tools = await security_connector.discover_tools()
        
        assert tools == expected_tools
        security_connector._discover_tools_internal.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_discover_tools_not_initialized(self, security_connector):
        """Test tool discovery when not initialized"""
        security_connector.is_initialized = False
        
        tools = await security_connector.discover_tools()
        
        assert tools == []
    
    @pytest.mark.asyncio
    async def test_call_tool_success(self, security_connector):
        """Test successful tool call"""
        security_connector.is_initialized = True
        security_connector._call_tool_internal = AsyncMock(return_value="test result")
        
        result = await security_connector.call_tool("CheckSecurityServices", {"region": "us-east-1"})
        
        assert result.success is True
        assert result.tool_name == "CheckSecurityServices"
        assert result.mcp_server == "security"
        assert result.data == "test result"
        assert result.execution_time > 0
    
    @pytest.mark.asyncio
    async def test_call_tool_not_initialized(self, security_connector):
        """Test tool call when not initialized"""
        security_connector.is_initialized = False
        
        result = await security_connector.call_tool("CheckSecurityServices", {})
        
        assert result.success is False
        assert result.error_message == "Security MCP Server not initialized"
    
    @pytest.mark.asyncio
    async def test_call_tool_failure(self, security_connector):
        """Test tool call with failure"""
        security_connector.is_initialized = True
        security_connector._call_tool_internal = AsyncMock(side_effect=Exception("Tool call failed"))
        
        result = await security_connector.call_tool("CheckSecurityServices", {})
        
        assert result.success is False
        assert "Tool call failed" in result.error_message
    
    @pytest.mark.asyncio
    async def test_close(self, security_connector):
        """Test closing connection"""
        security_connector.is_initialized = True
        security_connector.mcp_url = "https://test.com"
        security_connector.mcp_headers = {"Authorization": "Bearer test"}
        
        await security_connector.close()
        
        assert security_connector.is_initialized is False
        assert security_connector.mcp_url is None
        assert security_connector.mcp_headers is None


class TestKnowledgeMCPConnector:
    """Test cases for Knowledge MCP Connector"""
    
    @pytest.fixture
    def knowledge_config(self):
        """Create knowledge MCP server config"""
        return MCPServerConfig(
            name="knowledge",
            server_type=MCPServerType.KNOWLEDGE,
            connection_type="direct",
            timeout=60,
            retry_attempts=3
        )
    
    @pytest.fixture
    def connection_pool(self):
        """Create connection pool manager"""
        return ConnectionPoolManager()
    
    @pytest.fixture
    def knowledge_connector(self, knowledge_config, connection_pool):
        """Create knowledge MCP connector"""
        return KnowledgeMCPConnector(knowledge_config, "us-east-1", connection_pool)
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, knowledge_connector):
        """Test successful initialization"""
        result = await knowledge_connector.initialize()
        
        assert result is True
        assert knowledge_connector.is_initialized is True
        assert len(knowledge_connector.available_tools) == 3
        
        # Check that expected tools are available
        tool_names = [tool['name'] for tool in knowledge_connector.available_tools]
        assert 'search_documentation' in tool_names
        assert 'read_documentation' in tool_names
        assert 'recommend' in tool_names
    
    @pytest.mark.asyncio
    async def test_discover_tools(self, knowledge_connector):
        """Test tool discovery"""
        await knowledge_connector.initialize()
        
        tools = await knowledge_connector.discover_tools()
        
        assert len(tools) == 3
        assert all(tool['mcp_server'] == 'knowledge' for tool in tools)
    
    @pytest.mark.asyncio
    async def test_discover_tools_not_initialized(self, knowledge_connector):
        """Test tool discovery when not initialized"""
        tools = await knowledge_connector.discover_tools()
        
        assert tools == []
    
    @pytest.mark.asyncio
    async def test_call_search_documentation_tool(self, knowledge_connector):
        """Test calling search_documentation tool"""
        await knowledge_connector.initialize()
        
        result = await knowledge_connector.call_tool("search_documentation", {"search_phrase": "security"})
        
        assert result.success is True
        assert result.tool_name == "search_documentation"
        assert result.mcp_server == "knowledge"
        assert "AWS Documentation Search Results" in result.data
    
    @pytest.mark.asyncio
    async def test_call_read_documentation_tool(self, knowledge_connector):
        """Test calling read_documentation tool"""
        await knowledge_connector.initialize()
        
        result = await knowledge_connector.call_tool("read_documentation", {"url": "https://docs.aws.amazon.com/security/"})
        
        assert result.success is True
        assert result.tool_name == "read_documentation"
        assert "AWS Documentation Content" in result.data
    
    @pytest.mark.asyncio
    async def test_call_recommend_tool(self, knowledge_connector):
        """Test calling recommend tool"""
        await knowledge_connector.initialize()
        
        result = await knowledge_connector.call_tool("recommend", {"url": "https://docs.aws.amazon.com/"})
        
        assert result.success is True
        assert result.tool_name == "recommend"
        assert "Related AWS Documentation Recommendations" in result.data
    
    @pytest.mark.asyncio
    async def test_call_unknown_tool(self, knowledge_connector):
        """Test calling unknown tool"""
        await knowledge_connector.initialize()
        
        result = await knowledge_connector.call_tool("unknown_tool", {})
        
        assert result.success is False
        assert "Unknown AWS Knowledge tool" in result.error_message
    
    @pytest.mark.asyncio
    async def test_call_tool_not_initialized(self, knowledge_connector):
        """Test tool call when not initialized"""
        result = await knowledge_connector.call_tool("search_documentation", {})
        
        assert result.success is False
        assert result.error_message == "AWS Knowledge MCP Server not initialized"


class TestAPIMCPConnector:
    """Test cases for API MCP Connector"""
    
    @pytest.fixture
    def api_config(self):
        """Create API MCP server config"""
        return MCPServerConfig(
            name="api",
            server_type=MCPServerType.API,
            connection_type="api",
            timeout=120,
            retry_attempts=3
        )
    
    @pytest.fixture
    def connection_pool(self):
        """Create connection pool manager"""
        return ConnectionPoolManager()
    
    @pytest.fixture
    def api_connector(self, api_config, connection_pool):
        """Create API MCP connector"""
        return APIMCPConnector(api_config, "us-east-1", connection_pool)
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, api_connector):
        """Test successful initialization"""
        result = await api_connector.initialize()
        
        assert result is True
        assert api_connector.is_initialized is True
        assert len(api_connector.available_tools) == 4
        
        # Check that expected tools are available
        tool_names = [tool['name'] for tool in api_connector.available_tools]
        assert 'describe_instances' in tool_names
        assert 'list_s3_buckets' in tool_names
        assert 'get_security_groups' in tool_names
        assert 'execute_remediation' in tool_names
    
    @pytest.mark.asyncio
    async def test_call_describe_instances_tool(self, api_connector):
        """Test calling describe_instances tool"""
        await api_connector.initialize()
        
        result = await api_connector.call_tool("describe_instances", {"region": "us-west-2"})
        
        assert result.success is True
        assert result.tool_name == "describe_instances"
        assert result.mcp_server == "api"
        assert "EC2 Instances in us-west-2" in result.data
    
    @pytest.mark.asyncio
    async def test_call_list_s3_buckets_tool(self, api_connector):
        """Test calling list_s3_buckets tool"""
        await api_connector.initialize()
        
        result = await api_connector.call_tool("list_s3_buckets", {"include_encryption": True})
        
        assert result.success is True
        assert result.tool_name == "list_s3_buckets"
        assert "S3 Buckets Configuration" in result.data
        assert "Encryption" in result.data
    
    @pytest.mark.asyncio
    async def test_call_get_security_groups_tool(self, api_connector):
        """Test calling get_security_groups tool"""
        await api_connector.initialize()
        
        result = await api_connector.call_tool("get_security_groups", {"region": "us-east-1"})
        
        assert result.success is True
        assert result.tool_name == "get_security_groups"
        assert "Security Groups in us-east-1" in result.data
    
    @pytest.mark.asyncio
    async def test_call_execute_remediation_tool(self, api_connector):
        """Test calling execute_remediation tool"""
        await api_connector.initialize()
        
        result = await api_connector.call_tool("execute_remediation", {
            "action_type": "enable_encryption",
            "resource_arn": "arn:aws:s3:::test-bucket"
        })
        
        assert result.success is True
        assert result.tool_name == "execute_remediation"
        assert "Remediation Action Executed" in result.data
        assert "enable_encryption" in result.data
    
    @pytest.mark.asyncio
    async def test_health_check(self, api_connector):
        """Test health check for API connector"""
        await api_connector.initialize()
        
        is_healthy = await api_connector._perform_health_check()
        
        assert is_healthy is True
    
    @pytest.mark.asyncio
    async def test_close(self, api_connector):
        """Test closing API connector"""
        await api_connector.initialize()
        
        await api_connector.close()
        
        assert api_connector.is_initialized is False
        assert len(api_connector.available_tools) == 0


if __name__ == "__main__":
    pytest.main([__file__])