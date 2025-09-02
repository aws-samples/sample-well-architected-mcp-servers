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
Integration tests for Tool Discovery with MCP Orchestrator
"""

from unittest.mock import AsyncMock, patch

import pytest
from agent_config.orchestration.mcp_orchestrator import MCPOrchestratorImpl


class TestToolDiscoveryIntegration:
    """Integration tests for tool discovery with orchestrator"""

    def setup_method(self):
        """Set up test fixtures"""
        self.orchestrator = MCPOrchestratorImpl(region="us-east-1")

    @pytest.mark.asyncio
    async def test_orchestrator_tool_discovery_integration(self):
        """Test tool discovery integration with orchestrator"""
        # Mock the connectors to avoid actual AWS calls
        with (
            patch.object(
                self.orchestrator, "_initialize_security_connector"
            ) as mock_security,
            patch.object(
                self.orchestrator, "_initialize_knowledge_connector"
            ) as mock_knowledge,
            patch.object(self.orchestrator, "_initialize_api_connector") as mock_api,
        ):
            # Mock successful initialization
            mock_security.return_value = None
            mock_knowledge.return_value = None
            mock_api.return_value = None

            # Create mock connectors
            mock_security_connector = AsyncMock()
            mock_knowledge_connector = AsyncMock()
            mock_api_connector = AsyncMock()

            # Mock tool discovery responses
            mock_security_connector.discover_tools.return_value = [
                {
                    "name": "CheckSecurityServices",
                    "description": "Check if AWS security services are enabled",
                    "parameters": {
                        "region": {"type": "string", "description": "AWS region"},
                        "services": {
                            "type": "array",
                            "description": "List of services to check",
                        },
                    },
                },
                {
                    "name": "GetSecurityFindings",
                    "description": "Get security findings from AWS security services",
                    "parameters": {
                        "service": {
                            "type": "string",
                            "description": "Security service name",
                        },
                        "severity_filter": {
                            "type": "string",
                            "description": "Severity filter",
                        },
                    },
                },
            ]

            mock_knowledge_connector.discover_tools.return_value = [
                {
                    "name": "search_documentation",
                    "description": "Search AWS documentation for security best practices",
                    "parameters": {
                        "search_phrase": {
                            "type": "string",
                            "description": "Search phrase",
                        },
                        "limit": {"type": "integer", "description": "Maximum results"},
                    },
                },
                {
                    "name": "read_documentation",
                    "description": "Read specific AWS documentation pages",
                    "parameters": {
                        "url": {"type": "string", "description": "Documentation URL"}
                    },
                },
            ]

            mock_api_connector.discover_tools.return_value = [
                {
                    "name": "describe_instances",
                    "description": "Describe EC2 instances for security analysis",
                    "parameters": {
                        "region": {"type": "string", "description": "AWS region"},
                        "instance_ids": {
                            "type": "array",
                            "description": "Instance IDs",
                        },
                    },
                },
                {
                    "name": "execute_remediation",
                    "description": "Execute automated security remediation",
                    "parameters": {
                        "action_type": {
                            "type": "string",
                            "description": "Remediation action",
                        },
                        "resource_arn": {
                            "type": "string",
                            "description": "Resource ARN",
                        },
                    },
                },
            ]

            # Set mock connectors
            self.orchestrator.connectors = {
                "security": mock_security_connector,
                "knowledge": mock_knowledge_connector,
                "api": mock_api_connector,
            }

            # Initialize the orchestrator (this will trigger tool discovery)
            await self.orchestrator.initialize_connections()

            # Test that tools were discovered
            tools_registry = await self.orchestrator.discover_all_tools()

            assert "security" in tools_registry
            assert "knowledge" in tools_registry
            assert "api" in tools_registry

            assert len(tools_registry["security"]) == 2
            assert len(tools_registry["knowledge"]) == 2
            assert len(tools_registry["api"]) == 2

            # Verify tool metadata
            security_tools = tools_registry["security"]
            security_tool_names = [tool["name"] for tool in security_tools]
            assert "CheckSecurityServices" in security_tool_names
            assert "GetSecurityFindings" in security_tool_names

            # Check that capabilities were inferred
            for tool in security_tools:
                assert "capabilities" in tool
                assert len(tool["capabilities"]) > 0
                assert "category" in tool
                assert tool["category"] == "security"

    @pytest.mark.asyncio
    async def test_get_tools_by_capability(self):
        """Test getting tools by capability"""
        # Setup mock connectors as in previous test
        with (
            patch.object(self.orchestrator, "_initialize_security_connector"),
            patch.object(self.orchestrator, "_initialize_knowledge_connector"),
            patch.object(self.orchestrator, "_initialize_api_connector"),
        ):
            mock_security_connector = AsyncMock()
            mock_security_connector.discover_tools.return_value = [
                {
                    "name": "vulnerability_scan",
                    "description": "Scan for security vulnerabilities",
                    "parameters": {},
                }
            ]

            self.orchestrator.connectors = {"security": mock_security_connector}
            await self.orchestrator.initialize_connections()

            # Test getting tools by capability
            security_tools = await self.orchestrator.get_tools_by_capability(
                "security_assessment"
            )

            assert len(security_tools) >= 1
            assert any(tool["name"] == "vulnerability_scan" for tool in security_tools)

    @pytest.mark.asyncio
    async def test_get_tools_by_category(self):
        """Test getting tools by category"""
        with (
            patch.object(self.orchestrator, "_initialize_security_connector"),
            patch.object(self.orchestrator, "_initialize_knowledge_connector"),
            patch.object(self.orchestrator, "_initialize_api_connector"),
        ):
            mock_knowledge_connector = AsyncMock()
            mock_knowledge_connector.discover_tools.return_value = [
                {
                    "name": "search_best_practices",
                    "description": "Search for AWS security best practices",
                    "parameters": {},
                }
            ]

            self.orchestrator.connectors = {"knowledge": mock_knowledge_connector}
            await self.orchestrator.initialize_connections()

            # Test getting tools by category
            knowledge_tools = await self.orchestrator.get_tools_by_category("knowledge")

            assert len(knowledge_tools) >= 1
            assert any(
                tool["name"] == "search_best_practices" for tool in knowledge_tools
            )

    @pytest.mark.asyncio
    async def test_search_tools(self):
        """Test tool search functionality"""
        with (
            patch.object(self.orchestrator, "_initialize_security_connector"),
            patch.object(self.orchestrator, "_initialize_knowledge_connector"),
            patch.object(self.orchestrator, "_initialize_api_connector"),
        ):
            mock_api_connector = AsyncMock()
            mock_api_connector.discover_tools.return_value = [
                {
                    "name": "remediate_security_issue",
                    "description": "Automatically remediate security issues",
                    "parameters": {},
                }
            ]

            self.orchestrator.connectors = {"api": mock_api_connector}
            await self.orchestrator.initialize_connections()

            # Test search functionality
            search_results = await self.orchestrator.search_tools(
                "remediate", max_results=5
            )

            assert len(search_results) >= 1
            assert any(
                tool["name"] == "remediate_security_issue" for tool in search_results
            )

    @pytest.mark.asyncio
    async def test_get_tool_capabilities(self):
        """Test getting all tool capabilities"""
        with (
            patch.object(self.orchestrator, "_initialize_security_connector"),
            patch.object(self.orchestrator, "_initialize_knowledge_connector"),
            patch.object(self.orchestrator, "_initialize_api_connector"),
        ):
            # Mock multiple connectors with different tools
            mock_security_connector = AsyncMock()
            mock_security_connector.discover_tools.return_value = [
                {
                    "name": "security_assessment",
                    "description": "Perform comprehensive security assessment",
                    "parameters": {},
                }
            ]

            mock_knowledge_connector = AsyncMock()
            mock_knowledge_connector.discover_tools.return_value = [
                {
                    "name": "documentation_search",
                    "description": "Search AWS documentation",
                    "parameters": {},
                }
            ]

            self.orchestrator.connectors = {
                "security": mock_security_connector,
                "knowledge": mock_knowledge_connector,
            }
            await self.orchestrator.initialize_connections()

            # Test getting all capabilities
            capabilities = await self.orchestrator.get_tool_capabilities()

            assert isinstance(capabilities, dict)
            assert len(capabilities) > 0

            # Check that capabilities are mapped to tools
            for capability, tools in capabilities.items():
                assert isinstance(tools, list)

    @pytest.mark.asyncio
    async def test_tool_usage_statistics_update(self):
        """Test tool usage statistics tracking"""
        with (
            patch.object(self.orchestrator, "_initialize_security_connector"),
            patch.object(self.orchestrator, "_initialize_knowledge_connector"),
            patch.object(self.orchestrator, "_initialize_api_connector"),
        ):
            mock_security_connector = AsyncMock()
            mock_security_connector.discover_tools.return_value = [
                {
                    "name": "test_tool",
                    "description": "A test tool for statistics",
                    "parameters": {},
                }
            ]

            self.orchestrator.connectors = {"security": mock_security_connector}
            await self.orchestrator.initialize_connections()

            # Update tool usage statistics
            self.orchestrator.update_tool_usage_stats(
                "test_tool", "security", 15.5, True
            )

            # Verify statistics were updated
            tool_metadata = self.orchestrator.tool_discovery.registry.tools.get(
                "security:test_tool"
            )
            assert tool_metadata is not None
            assert tool_metadata.usage_count == 1
            assert tool_metadata.success_rate == 1.0
            assert tool_metadata.average_execution_time == 15.5

            # Update with a failed execution
            self.orchestrator.update_tool_usage_stats(
                "test_tool", "security", 8.0, False
            )

            assert tool_metadata.usage_count == 2
            assert tool_metadata.success_rate == 0.5
            assert tool_metadata.average_execution_time == 11.75  # (15.5 + 8.0) / 2

    @pytest.mark.asyncio
    async def test_refresh_tool_discovery(self):
        """Test refreshing tool discovery"""
        with (
            patch.object(self.orchestrator, "_initialize_security_connector"),
            patch.object(self.orchestrator, "_initialize_knowledge_connector"),
            patch.object(self.orchestrator, "_initialize_api_connector"),
        ):
            mock_security_connector = AsyncMock()
            mock_security_connector.discover_tools.return_value = [
                {
                    "name": "initial_tool",
                    "description": "Initial tool",
                    "parameters": {},
                }
            ]

            self.orchestrator.connectors = {"security": mock_security_connector}
            await self.orchestrator.initialize_connections()

            # Verify initial tool
            tools = self.orchestrator.tool_discovery.registry.get_tools_by_server(
                "security"
            )
            assert len(tools) == 1
            assert tools[0].name == "initial_tool"

            # Update mock to return different tools
            mock_security_connector.discover_tools.return_value = [
                {
                    "name": "updated_tool",
                    "description": "Updated tool",
                    "parameters": {},
                }
            ]

            # Refresh discovery for specific server
            result = await self.orchestrator.refresh_tool_discovery("security")

            assert "security" in result
            assert result["security"].success is True

            # Verify tools were updated
            tools = self.orchestrator.tool_discovery.registry.get_tools_by_server(
                "security"
            )
            assert len(tools) == 1
            assert tools[0].name == "updated_tool"

    @pytest.mark.asyncio
    async def test_connection_stats_with_tool_discovery(self):
        """Test connection statistics include tool discovery information"""
        with (
            patch.object(self.orchestrator, "_initialize_security_connector"),
            patch.object(self.orchestrator, "_initialize_knowledge_connector"),
            patch.object(self.orchestrator, "_initialize_api_connector"),
        ):
            mock_security_connector = AsyncMock()
            mock_security_connector.discover_tools.return_value = [
                {"name": "tool1", "description": "Tool 1", "parameters": {}},
                {"name": "tool2", "description": "Tool 2", "parameters": {}},
            ]

            self.orchestrator.connectors = {"security": mock_security_connector}
            await self.orchestrator.initialize_connections()

            # Get connection statistics
            stats = await self.orchestrator.get_connection_stats()

            assert "tool_discovery_stats" in stats
            assert "total_tools" in stats
            assert "tools_by_server" in stats

            assert stats["total_tools"] == 2
            assert stats["tools_by_server"]["security"] == 2

            discovery_stats = stats["tool_discovery_stats"]
            assert "auto_discovery_enabled" in discovery_stats
            assert "discovery_interval" in discovery_stats
            assert "registry_statistics" in discovery_stats

    @pytest.mark.asyncio
    async def test_tool_discovery_error_handling(self):
        """Test error handling in tool discovery"""
        with (
            patch.object(self.orchestrator, "_initialize_security_connector"),
            patch.object(self.orchestrator, "_initialize_knowledge_connector"),
            patch.object(self.orchestrator, "_initialize_api_connector"),
        ):
            # Mock connector that fails discovery
            mock_failing_connector = AsyncMock()
            mock_failing_connector.discover_tools.side_effect = Exception(
                "Discovery failed"
            )

            # Mock successful connector
            mock_working_connector = AsyncMock()
            mock_working_connector.discover_tools.return_value = [
                {
                    "name": "working_tool",
                    "description": "Working tool",
                    "parameters": {},
                }
            ]

            self.orchestrator.connectors = {
                "security": mock_failing_connector,
                "knowledge": mock_working_connector,
            }

            await self.orchestrator.initialize_connections()

            # Verify that working connector still provides tools
            tools_registry = await self.orchestrator.discover_all_tools()

            assert "security" in tools_registry
            assert "knowledge" in tools_registry

            # Security should have no tools due to failure
            assert len(tools_registry["security"]) == 0

            # Knowledge should have tools
            assert len(tools_registry["knowledge"]) == 1
            assert tools_registry["knowledge"][0]["name"] == "working_tool"

    @pytest.mark.asyncio
    async def test_dynamic_capability_updates(self):
        """Test that capability mappings are updated dynamically"""
        with (
            patch.object(self.orchestrator, "_initialize_security_connector"),
            patch.object(self.orchestrator, "_initialize_knowledge_connector"),
            patch.object(self.orchestrator, "_initialize_api_connector"),
        ):
            mock_security_connector = AsyncMock()

            # Initial tools
            mock_security_connector.discover_tools.return_value = [
                {
                    "name": "vulnerability_scanner",
                    "description": "Scan for vulnerabilities",
                    "parameters": {},
                }
            ]

            self.orchestrator.connectors = {"security": mock_security_connector}
            await self.orchestrator.initialize_connections()

            # Check initial capabilities
            vuln_tools = await self.orchestrator.get_tools_by_capability(
                "vulnerability_scanning"
            )
            assert len(vuln_tools) >= 1

            # Add new tool with different capabilities
            mock_security_connector.discover_tools.return_value = [
                {
                    "name": "vulnerability_scanner",
                    "description": "Scan for vulnerabilities",
                    "parameters": {},
                },
                {
                    "name": "compliance_checker",
                    "description": "Check compliance with security standards",
                    "parameters": {},
                },
            ]

            # Refresh discovery
            await self.orchestrator.refresh_tool_discovery("security")

            # Check updated capabilities
            compliance_tools = await self.orchestrator.get_tools_by_capability(
                "compliance_checking"
            )
            assert len(compliance_tools) >= 1
            assert any(
                tool["name"] == "compliance_checker" for tool in compliance_tools
            )


if __name__ == "__main__":
    pytest.main([__file__])
