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
Unit tests for MCP Orchestrator
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from agent_config.interfaces import ToolCall, ToolPriority, ToolResult
from agent_config.orchestration.mcp_orchestrator import MCPOrchestratorImpl


class TestMCPOrchestrator:
    """Test cases for MCP Orchestrator"""

    @pytest.fixture
    def orchestrator(self):
        """Create MCP Orchestrator instance for testing"""
        return MCPOrchestratorImpl(region="us-east-1")

    @pytest.fixture
    def mock_connectors(self):
        """Create mock connectors for testing"""
        security_connector = AsyncMock()
        security_connector.initialize.return_value = True
        security_connector.discover_tools.return_value = [
            {
                "name": "CheckSecurityServices",
                "description": "Check security services",
                "mcp_server": "security",
            }
        ]
        security_connector.health_check.return_value = True

        knowledge_connector = AsyncMock()
        knowledge_connector.initialize.return_value = True
        knowledge_connector.discover_tools.return_value = [
            {
                "name": "search_documentation",
                "description": "Search AWS docs",
                "mcp_server": "knowledge",
            }
        ]
        knowledge_connector.health_check.return_value = True

        api_connector = AsyncMock()
        api_connector.initialize.return_value = True
        api_connector.discover_tools.return_value = [
            {
                "name": "describe_instances",
                "description": "Describe EC2 instances",
                "mcp_server": "api",
            }
        ]
        api_connector.health_check.return_value = True

        return {
            "security": security_connector,
            "knowledge": knowledge_connector,
            "api": api_connector,
        }

    @pytest.mark.asyncio
    async def test_initialization(self, orchestrator):
        """Test orchestrator initialization"""
        assert orchestrator.region == "us-east-1"
        assert not orchestrator._initialized
        assert len(orchestrator.connectors) == 0
        assert len(orchestrator.tool_registry) == 0

    @pytest.mark.asyncio
    async def test_initialize_connections_success(self, orchestrator, mock_connectors):
        """Test successful connection initialization"""
        with (
            patch.object(
                orchestrator, "_initialize_security_connector"
            ) as mock_security,
            patch.object(
                orchestrator, "_initialize_knowledge_connector"
            ) as mock_knowledge,
            patch.object(orchestrator, "_initialize_api_connector") as mock_api,
            patch.object(orchestrator, "_discover_all_tools_internal") as mock_discover,
        ):
            mock_security.return_value = None
            mock_knowledge.return_value = None
            mock_api.return_value = None
            mock_discover.return_value = None

            # Mock the connectors
            orchestrator.connectors = mock_connectors

            await orchestrator.initialize_connections()

            assert orchestrator._initialized
            mock_security.assert_called_once()
            mock_knowledge.assert_called_once()
            mock_api.assert_called_once()
            mock_discover.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_connections_idempotent(self, orchestrator):
        """Test that initialization is idempotent"""
        with patch.object(orchestrator, "_initialize_security_connector") as mock_init:
            orchestrator._initialized = True

            await orchestrator.initialize_connections()

            mock_init.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_parallel_calls_empty_list(self, orchestrator):
        """Test parallel execution with empty tool calls list"""
        result = await orchestrator.execute_parallel_calls([])
        assert result == []

    @pytest.mark.asyncio
    async def test_execute_parallel_calls_single_priority(
        self, orchestrator, mock_connectors
    ):
        """Test parallel execution with single priority level"""
        orchestrator.connectors = mock_connectors
        orchestrator._initialized = True

        # Mock successful tool call
        mock_connectors["security"].call_tool.return_value = ToolResult(
            tool_name="CheckSecurityServices",
            mcp_server="security",
            success=True,
            data="test result",
            execution_time=1.0,
        )

        tool_calls = [
            ToolCall(
                tool_name="CheckSecurityServices",
                mcp_server="security",
                arguments={"region": "us-east-1"},
                priority=ToolPriority.NORMAL,
            )
        ]

        results = await orchestrator.execute_parallel_calls(tool_calls)

        assert len(results) == 1
        assert results[0].success
        assert results[0].tool_name == "CheckSecurityServices"
        assert results[0].data == "test result"

    @pytest.mark.asyncio
    async def test_execute_parallel_calls_multiple_priorities(
        self, orchestrator, mock_connectors
    ):
        """Test parallel execution with multiple priority levels"""
        orchestrator.connectors = mock_connectors
        orchestrator._initialized = True

        # Mock successful tool calls
        mock_connectors["security"].call_tool.return_value = ToolResult(
            tool_name="CheckSecurityServices",
            mcp_server="security",
            success=True,
            data="security result",
            execution_time=1.0,
        )

        mock_connectors["knowledge"].call_tool.return_value = ToolResult(
            tool_name="search_documentation",
            mcp_server="knowledge",
            success=True,
            data="knowledge result",
            execution_time=0.5,
        )

        tool_calls = [
            ToolCall(
                tool_name="CheckSecurityServices",
                mcp_server="security",
                arguments={"region": "us-east-1"},
                priority=ToolPriority.HIGH,
            ),
            ToolCall(
                tool_name="search_documentation",
                mcp_server="knowledge",
                arguments={"search_phrase": "security"},
                priority=ToolPriority.NORMAL,
            ),
        ]

        results = await orchestrator.execute_parallel_calls(tool_calls)

        assert len(results) == 2
        assert all(result.success for result in results)

    @pytest.mark.asyncio
    async def test_execute_parallel_calls_with_timeout(
        self, orchestrator, mock_connectors
    ):
        """Test parallel execution with timeout"""
        orchestrator.connectors = mock_connectors
        orchestrator._initialized = True

        # Mock a slow tool call that will timeout
        async def slow_call(*args, **kwargs):
            await asyncio.sleep(2)  # Longer than timeout
            return ToolResult(
                tool_name="slow_tool",
                mcp_server="security",
                success=True,
                data="result",
                execution_time=2.0,
            )

        mock_connectors["security"].call_tool.side_effect = slow_call

        tool_calls = [
            ToolCall(
                tool_name="slow_tool",
                mcp_server="security",
                arguments={},
                priority=ToolPriority.NORMAL,
                timeout=1,  # 1 second timeout
            )
        ]

        results = await orchestrator.execute_parallel_calls(tool_calls)

        assert len(results) == 1
        assert not results[0].success
        assert "timed out" in results[0].error_message.lower()

    @pytest.mark.asyncio
    async def test_call_security_tool_success(self, orchestrator, mock_connectors):
        """Test successful security tool call"""
        orchestrator.connectors = mock_connectors

        expected_result = ToolResult(
            tool_name="CheckSecurityServices",
            mcp_server="security",
            success=True,
            data="security data",
            execution_time=1.0,
        )
        mock_connectors["security"].call_tool.return_value = expected_result

        result = await orchestrator.call_security_tool(
            "CheckSecurityServices", {"region": "us-east-1"}
        )

        assert result == expected_result
        mock_connectors["security"].call_tool.assert_called_once_with(
            "CheckSecurityServices", {"region": "us-east-1"}
        )

    @pytest.mark.asyncio
    async def test_call_security_tool_no_connector(self, orchestrator):
        """Test security tool call when connector is not available"""
        result = await orchestrator.call_security_tool("CheckSecurityServices", {})

        assert result is None

    @pytest.mark.asyncio
    async def test_call_knowledge_tool_success(self, orchestrator, mock_connectors):
        """Test successful knowledge tool call"""
        orchestrator.connectors = mock_connectors

        expected_result = ToolResult(
            tool_name="search_documentation",
            mcp_server="knowledge",
            success=True,
            data="knowledge data",
            execution_time=0.5,
        )
        mock_connectors["knowledge"].call_tool.return_value = expected_result

        result = await orchestrator.call_knowledge_tool(
            "search_documentation", {"search_phrase": "security"}
        )

        assert result == expected_result
        mock_connectors["knowledge"].call_tool.assert_called_once_with(
            "search_documentation", {"search_phrase": "security"}
        )

    @pytest.mark.asyncio
    async def test_call_api_tool_success(self, orchestrator, mock_connectors):
        """Test successful API tool call"""
        orchestrator.connectors = mock_connectors

        expected_result = ToolResult(
            tool_name="describe_instances",
            mcp_server="api",
            success=True,
            data="api data",
            execution_time=1.5,
        )
        mock_connectors["api"].call_tool.return_value = expected_result

        result = await orchestrator.call_api_tool(
            "describe_instances", {"region": "us-east-1"}
        )

        assert result == expected_result
        mock_connectors["api"].call_tool.assert_called_once_with(
            "describe_instances", {"region": "us-east-1"}
        )

    @pytest.mark.asyncio
    async def test_discover_all_tools(self, orchestrator, mock_connectors):
        """Test tool discovery across all servers"""
        orchestrator.connectors = mock_connectors
        orchestrator._initialized = True
        orchestrator.tool_registry = {
            "security": [
                {
                    "name": "CheckSecurityServices",
                    "description": "Check security services",
                }
            ],
            "knowledge": [
                {"name": "search_documentation", "description": "Search AWS docs"}
            ],
            "api": [
                {"name": "describe_instances", "description": "Describe EC2 instances"}
            ],
        }

        tools = await orchestrator.discover_all_tools()

        assert len(tools) == 3
        assert "security" in tools
        assert "knowledge" in tools
        assert "api" in tools
        assert len(tools["security"]) == 1
        assert len(tools["knowledge"]) == 1
        assert len(tools["api"]) == 1

    @pytest.mark.asyncio
    async def test_health_check_all_success(self, orchestrator, mock_connectors):
        """Test health check for all connectors"""
        orchestrator.connectors = mock_connectors

        health_status = await orchestrator.health_check_all()

        assert len(health_status) == 3
        assert health_status["security"] is True
        assert health_status["knowledge"] is True
        assert health_status["api"] is True

    @pytest.mark.asyncio
    async def test_health_check_all_with_failures(self, orchestrator, mock_connectors):
        """Test health check with some failures"""
        orchestrator.connectors = mock_connectors

        # Make security connector fail health check
        mock_connectors["security"].health_check.return_value = False

        with patch.object(orchestrator, "_attempt_reconnection") as mock_reconnect:
            health_status = await orchestrator.health_check_all()

            assert health_status["security"] is False
            assert health_status["knowledge"] is True
            assert health_status["api"] is True
            mock_reconnect.assert_called_once_with(
                "security", mock_connectors["security"]
            )

    @pytest.mark.asyncio
    async def test_attempt_reconnection_success(self, orchestrator, mock_connectors):
        """Test successful reconnection attempt"""
        connector = mock_connectors["security"]
        connector.initialize.return_value = True
        connector.discover_tools.return_value = [{"name": "test_tool"}]

        await orchestrator._attempt_reconnection("security", connector)

        connector.close.assert_called_once()
        connector.initialize.assert_called_once()
        connector.discover_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_attempt_reconnection_failure(self, orchestrator, mock_connectors):
        """Test failed reconnection attempt"""
        connector = mock_connectors["security"]
        connector.initialize.return_value = False

        await orchestrator._attempt_reconnection("security", connector)

        connector.close.assert_called_once()
        connector.initialize.assert_called_once()
        connector.discover_tools.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_connection_stats(self, orchestrator, mock_connectors):
        """Test getting connection statistics"""
        orchestrator.connectors = mock_connectors
        orchestrator._initialized = True
        orchestrator.tool_registry = {
            "security": [{"name": "tool1"}, {"name": "tool2"}],
            "knowledge": [{"name": "tool3"}],
            "api": [],
        }

        # Mock connection pool stats
        orchestrator.connection_pool.get_stats = AsyncMock(
            return_value={"total_connections": 5}
        )

        stats = await orchestrator.get_connection_stats()

        assert stats["initialized"] is True
        assert stats["total_connectors"] == 3
        assert stats["active_connectors"] == 3
        assert stats["total_tools"] == 3
        assert stats["tools_by_server"]["security"] == 2
        assert stats["tools_by_server"]["knowledge"] == 1
        assert stats["tools_by_server"]["api"] == 0
        assert stats["connection_pool_stats"]["total_connections"] == 5

    @pytest.mark.asyncio
    async def test_close_all_connections(self, orchestrator, mock_connectors):
        """Test closing all connections"""
        orchestrator.connectors = mock_connectors
        orchestrator._initialized = True
        orchestrator.connection_pool.close_all = AsyncMock()

        await orchestrator.close_all_connections()

        for connector in mock_connectors.values():
            connector.close.assert_called_once()

        orchestrator.connection_pool.close_all.assert_called_once()
        assert not orchestrator._initialized

    def test_prioritize_tool_calls(self, orchestrator):
        """Test tool call prioritization"""
        tool_calls = [
            ToolCall("tool1", "server1", {}, ToolPriority.LOW),
            ToolCall("tool2", "server2", {}, ToolPriority.HIGH),
            ToolCall("tool3", "server1", {}, ToolPriority.NORMAL),
            ToolCall("tool4", "server2", {}, ToolPriority.HIGH),
        ]

        prioritized = orchestrator._prioritize_tool_calls(tool_calls)

        assert len(prioritized[ToolPriority.LOW]) == 1
        assert len(prioritized[ToolPriority.NORMAL]) == 1
        assert len(prioritized[ToolPriority.HIGH]) == 2
        assert len(prioritized[ToolPriority.CRITICAL]) == 0

    @pytest.mark.asyncio
    async def test_execute_single_call_success(self, orchestrator, mock_connectors):
        """Test successful single tool call execution"""
        orchestrator.connectors = mock_connectors

        expected_result = ToolResult(
            tool_name="test_tool",
            mcp_server="security",
            success=True,
            data="test data",
            execution_time=1.0,
        )
        mock_connectors["security"].call_tool.return_value = expected_result

        tool_call = ToolCall("test_tool", "security", {"arg": "value"})
        result = await orchestrator._execute_single_call(tool_call)

        assert result == expected_result
        mock_connectors["security"].call_tool.assert_called_once_with(
            "test_tool", {"arg": "value"}
        )

    @pytest.mark.asyncio
    async def test_execute_single_call_no_connector(self, orchestrator):
        """Test single tool call execution when connector doesn't exist"""
        tool_call = ToolCall("test_tool", "nonexistent", {"arg": "value"})

        with pytest.raises(
            ValueError, match="No connector available for MCP server: nonexistent"
        ):
            await orchestrator._execute_single_call(tool_call)


if __name__ == "__main__":
    pytest.main([__file__])
