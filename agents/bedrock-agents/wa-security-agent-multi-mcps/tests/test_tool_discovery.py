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
Unit tests for Unified Tool Discovery mechanism
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from agent_config.orchestration.tool_discovery import (
    CapabilityMapping,
    DiscoveryResult,
    ToolCapability,
    ToolCategory,
    ToolMetadata,
    ToolRegistry,
    UnifiedToolDiscovery,
)


class TestToolRegistry:
    """Test cases for ToolRegistry"""

    def setup_method(self):
        """Set up test fixtures"""
        self.registry = ToolRegistry()

    def test_registry_initialization(self):
        """Test registry initialization"""
        assert len(self.registry.tools) == 0
        assert len(self.registry.capabilities) == len(ToolCapability)
        assert len(self.registry.server_tools) == 0

        # Check capability mappings are initialized
        for capability in ToolCapability:
            assert capability in self.registry.capabilities
            assert isinstance(self.registry.capabilities[capability], CapabilityMapping)

    def test_register_tool(self):
        """Test tool registration"""
        tool_metadata = ToolMetadata(
            name="test_tool",
            description="A test tool",
            mcp_server="security",
            category=ToolCategory.SECURITY,
            capabilities={
                ToolCapability.SECURITY_ASSESSMENT,
                ToolCapability.VULNERABILITY_SCANNING,
            },
        )

        result = self.registry.register_tool(tool_metadata)
        assert result is True

        # Check tool is registered
        tool_key = "security:test_tool"
        assert tool_key in self.registry.tools
        assert self.registry.tools[tool_key] == tool_metadata

        # Check server tools mapping
        assert "security" in self.registry.server_tools
        assert tool_key in self.registry.server_tools["security"]

        # Check capability mappings
        for capability in tool_metadata.capabilities:
            capability_mapping = self.registry.capabilities[capability]
            assert tool_key in capability_mapping.tools

    def test_register_duplicate_tool(self):
        """Test registering a tool that already exists"""
        tool_metadata = ToolMetadata(
            name="test_tool",
            description="A test tool",
            mcp_server="security",
            category=ToolCategory.SECURITY,
            capabilities={ToolCapability.SECURITY_ASSESSMENT},
        )

        # Register tool first time
        self.registry.register_tool(tool_metadata)

        # Register same tool with updated description
        updated_tool = ToolMetadata(
            name="test_tool",
            description="Updated test tool",
            mcp_server="security",
            category=ToolCategory.SECURITY,
            capabilities={
                ToolCapability.SECURITY_ASSESSMENT,
                ToolCapability.COMPLIANCE_CHECKING,
            },
        )

        result = self.registry.register_tool(updated_tool)
        assert result is True

        # Check tool is updated
        tool_key = "security:test_tool"
        assert self.registry.tools[tool_key].description == "Updated test tool"
        assert (
            ToolCapability.COMPLIANCE_CHECKING
            in self.registry.tools[tool_key].capabilities
        )

    def test_get_tools_by_capability(self):
        """Test getting tools by capability"""
        # Register tools with different capabilities
        tool1 = ToolMetadata(
            name="security_scan",
            description="Security scanning tool",
            mcp_server="security",
            category=ToolCategory.SECURITY,
            capabilities={
                ToolCapability.SECURITY_ASSESSMENT,
                ToolCapability.VULNERABILITY_SCANNING,
            },
        )

        tool2 = ToolMetadata(
            name="compliance_check",
            description="Compliance checking tool",
            mcp_server="security",
            category=ToolCategory.SECURITY,
            capabilities={ToolCapability.COMPLIANCE_CHECKING},
        )

        tool3 = ToolMetadata(
            name="doc_search",
            description="Documentation search tool",
            mcp_server="knowledge",
            category=ToolCategory.KNOWLEDGE,
            capabilities={ToolCapability.DOCUMENTATION_SEARCH},
        )

        self.registry.register_tool(tool1)
        self.registry.register_tool(tool2)
        self.registry.register_tool(tool3)

        # Test getting tools by capability
        security_tools = self.registry.get_tools_by_capability(
            ToolCapability.SECURITY_ASSESSMENT
        )
        assert len(security_tools) == 1
        assert security_tools[0].name == "security_scan"

        compliance_tools = self.registry.get_tools_by_capability(
            ToolCapability.COMPLIANCE_CHECKING
        )
        assert len(compliance_tools) == 1
        assert compliance_tools[0].name == "compliance_check"

        doc_tools = self.registry.get_tools_by_capability(
            ToolCapability.DOCUMENTATION_SEARCH
        )
        assert len(doc_tools) == 1
        assert doc_tools[0].name == "doc_search"

    def test_get_tools_by_server(self):
        """Test getting tools by server"""
        # Register tools for different servers
        security_tool = ToolMetadata(
            name="security_tool",
            description="Security tool",
            mcp_server="security",
            category=ToolCategory.SECURITY,
            capabilities={ToolCapability.SECURITY_ASSESSMENT},
        )

        knowledge_tool = ToolMetadata(
            name="knowledge_tool",
            description="Knowledge tool",
            mcp_server="knowledge",
            category=ToolCategory.KNOWLEDGE,
            capabilities={ToolCapability.DOCUMENTATION_SEARCH},
        )

        self.registry.register_tool(security_tool)
        self.registry.register_tool(knowledge_tool)

        # Test getting tools by server
        security_tools = self.registry.get_tools_by_server("security")
        assert len(security_tools) == 1
        assert security_tools[0].name == "security_tool"

        knowledge_tools = self.registry.get_tools_by_server("knowledge")
        assert len(knowledge_tools) == 1
        assert knowledge_tools[0].name == "knowledge_tool"

        # Test non-existent server
        api_tools = self.registry.get_tools_by_server("api")
        assert len(api_tools) == 0

    def test_get_tools_by_category(self):
        """Test getting tools by category"""
        # Register tools with different categories
        security_tool = ToolMetadata(
            name="security_tool",
            description="Security tool",
            mcp_server="security",
            category=ToolCategory.SECURITY,
            capabilities={ToolCapability.SECURITY_ASSESSMENT},
        )

        knowledge_tool = ToolMetadata(
            name="knowledge_tool",
            description="Knowledge tool",
            mcp_server="knowledge",
            category=ToolCategory.KNOWLEDGE,
            capabilities={ToolCapability.DOCUMENTATION_SEARCH},
        )

        self.registry.register_tool(security_tool)
        self.registry.register_tool(knowledge_tool)

        # Test getting tools by category
        security_tools = self.registry.get_tools_by_category(ToolCategory.SECURITY)
        assert len(security_tools) == 1
        assert security_tools[0].name == "security_tool"

        knowledge_tools = self.registry.get_tools_by_category(ToolCategory.KNOWLEDGE)
        assert len(knowledge_tools) == 1
        assert knowledge_tools[0].name == "knowledge_tool"

    def test_search_tools(self):
        """Test tool search functionality"""
        # Register tools with different names and descriptions
        tool1 = ToolMetadata(
            name="security_scanner",
            description="Scans for security vulnerabilities",
            mcp_server="security",
            category=ToolCategory.SECURITY,
            capabilities={ToolCapability.VULNERABILITY_SCANNING},
        )

        tool2 = ToolMetadata(
            name="compliance_checker",
            description="Checks compliance with security standards",
            mcp_server="security",
            category=ToolCategory.SECURITY,
            capabilities={ToolCapability.COMPLIANCE_CHECKING},
        )

        tool3 = ToolMetadata(
            name="doc_finder",
            description="Finds relevant documentation",
            mcp_server="knowledge",
            category=ToolCategory.KNOWLEDGE,
            capabilities={ToolCapability.DOCUMENTATION_SEARCH},
        )

        self.registry.register_tool(tool1)
        self.registry.register_tool(tool2)
        self.registry.register_tool(tool3)

        # Test search by name
        results = self.registry.search_tools("scanner")
        assert len(results) == 1
        assert results[0].name == "security_scanner"

        # Test search by description
        results = self.registry.search_tools("compliance")
        assert len(results) == 1
        assert results[0].name == "compliance_checker"

        # Test search with multiple matches
        results = self.registry.search_tools("security")
        assert len(results) == 2

        # Test search with no matches
        results = self.registry.search_tools("nonexistent")
        assert len(results) == 0

    def test_update_tool_usage(self):
        """Test tool usage statistics update"""
        tool_metadata = ToolMetadata(
            name="test_tool",
            description="A test tool",
            mcp_server="security",
            category=ToolCategory.SECURITY,
            capabilities={ToolCapability.SECURITY_ASSESSMENT},
        )

        self.registry.register_tool(tool_metadata)
        tool_key = "security:test_tool"

        # Initial state
        tool = self.registry.tools[tool_key]
        assert tool.usage_count == 0
        assert tool.success_rate == 1.0
        assert tool.average_execution_time == 0.0

        # Update with successful execution
        self.registry.update_tool_usage(tool_key, 10.5, True)

        assert tool.usage_count == 1
        assert tool.success_rate == 1.0
        assert tool.average_execution_time == 10.5

        # Update with failed execution
        self.registry.update_tool_usage(tool_key, 5.0, False)

        assert tool.usage_count == 2
        assert tool.success_rate == 0.5  # 1 success out of 2 executions
        assert tool.average_execution_time == 7.75  # (10.5 + 5.0) / 2

    def test_remove_server_tools(self):
        """Test removing all tools for a server"""
        # Register tools for multiple servers
        security_tool = ToolMetadata(
            name="security_tool",
            description="Security tool",
            mcp_server="security",
            category=ToolCategory.SECURITY,
            capabilities={ToolCapability.SECURITY_ASSESSMENT},
        )

        knowledge_tool = ToolMetadata(
            name="knowledge_tool",
            description="Knowledge tool",
            mcp_server="knowledge",
            category=ToolCategory.KNOWLEDGE,
            capabilities={ToolCapability.DOCUMENTATION_SEARCH},
        )

        self.registry.register_tool(security_tool)
        self.registry.register_tool(knowledge_tool)

        # Verify tools are registered
        assert len(self.registry.tools) == 2
        assert "security" in self.registry.server_tools
        assert "knowledge" in self.registry.server_tools

        # Remove security server tools
        removed_count = self.registry.remove_server_tools("security")

        assert removed_count == 1
        assert len(self.registry.tools) == 1
        assert "security" not in self.registry.server_tools
        assert "knowledge" in self.registry.server_tools

        # Verify capability mappings are updated
        security_tools = self.registry.get_tools_by_capability(
            ToolCapability.SECURITY_ASSESSMENT
        )
        assert len(security_tools) == 0

        knowledge_tools = self.registry.get_tools_by_capability(
            ToolCapability.DOCUMENTATION_SEARCH
        )
        assert len(knowledge_tools) == 1

    def test_get_tool_statistics(self):
        """Test getting tool statistics"""
        # Register tools
        security_tool = ToolMetadata(
            name="security_tool",
            description="Security tool",
            mcp_server="security",
            category=ToolCategory.SECURITY,
            capabilities={ToolCapability.SECURITY_ASSESSMENT},
        )

        knowledge_tool = ToolMetadata(
            name="knowledge_tool",
            description="Knowledge tool",
            mcp_server="knowledge",
            category=ToolCategory.KNOWLEDGE,
            capabilities={ToolCapability.DOCUMENTATION_SEARCH},
        )

        self.registry.register_tool(security_tool)
        self.registry.register_tool(knowledge_tool)

        stats = self.registry.get_tool_statistics()

        assert stats["total_tools"] == 2
        assert stats["tools_by_server"]["security"] == 1
        assert stats["tools_by_server"]["knowledge"] == 1
        assert stats["tools_by_category"]["security"] == 1
        assert stats["tools_by_category"]["knowledge"] == 1
        assert stats["capabilities_coverage"]["security_assessment"] == 1
        assert stats["capabilities_coverage"]["documentation_search"] == 1


class TestUnifiedToolDiscovery:
    """Test cases for UnifiedToolDiscovery"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_orchestrator = Mock()
        self.mock_orchestrator._initialized = True
        self.mock_orchestrator.connectors = {
            "security": Mock(),
            "knowledge": Mock(),
            "api": Mock(),
        }

        self.discovery = UnifiedToolDiscovery(self.mock_orchestrator)

    def test_discovery_initialization(self):
        """Test discovery system initialization"""
        assert self.discovery.orchestrator == self.mock_orchestrator
        assert isinstance(self.discovery.registry, ToolRegistry)
        assert self.discovery.discovery_interval == 300
        assert self.discovery.auto_discovery_enabled is True
        assert len(self.discovery.capability_inference_rules) > 0

    def test_infer_category(self):
        """Test category inference from server name"""
        assert self.discovery._infer_category("security") == ToolCategory.SECURITY
        assert self.discovery._infer_category("knowledge") == ToolCategory.KNOWLEDGE
        assert self.discovery._infer_category("api") == ToolCategory.API
        assert self.discovery._infer_category("unknown") == ToolCategory.ANALYSIS

    def test_infer_capabilities(self):
        """Test capability inference from tool name and description"""
        # Test security-related capabilities
        capabilities = self.discovery._infer_capabilities(
            "security_scan", "Scans for vulnerabilities"
        )
        assert ToolCapability.SECURITY_ASSESSMENT in capabilities
        assert ToolCapability.VULNERABILITY_SCANNING in capabilities

        # Test knowledge-related capabilities
        capabilities = self.discovery._infer_capabilities(
            "search_docs", "Search documentation"
        )
        assert ToolCapability.DOCUMENTATION_SEARCH in capabilities

        # Test API-related capabilities
        capabilities = self.discovery._infer_capabilities(
            "describe_instances", "Describe EC2 instances"
        )
        assert ToolCapability.RESOURCE_ANALYSIS in capabilities
        assert ToolCapability.CONFIGURATION_ANALYSIS in capabilities

        # Test remediation capabilities
        capabilities = self.discovery._infer_capabilities(
            "fix_security", "Fix security issues"
        )
        assert ToolCapability.AUTOMATED_REMEDIATION in capabilities

    def test_infer_risk_level(self):
        """Test risk level inference"""
        # High risk operations
        assert (
            self.discovery._infer_risk_level("delete_resource", "Delete AWS resource")
            == "high"
        )
        assert (
            self.discovery._infer_risk_level(
                "terminate_instance", "Terminate EC2 instance"
            )
            == "high"
        )

        # Medium risk operations
        assert (
            self.discovery._infer_risk_level("modify_config", "Modify configuration")
            == "medium"
        )
        assert (
            self.discovery._infer_risk_level("update_policy", "Update IAM policy")
            == "medium"
        )

        # Low risk operations
        assert (
            self.discovery._infer_risk_level("list_buckets", "List S3 buckets") == "low"
        )
        assert (
            self.discovery._infer_risk_level(
                "describe_instances", "Describe EC2 instances"
            )
            == "low"
        )

    def test_infer_execution_time(self):
        """Test execution time inference"""
        # Vulnerability scanning should take longer
        capabilities = {ToolCapability.VULNERABILITY_SCANNING}
        assert self.discovery._infer_execution_time("vuln_scan", capabilities) == 120

        # Compliance checking should be moderate
        capabilities = {ToolCapability.COMPLIANCE_CHECKING}
        assert (
            self.discovery._infer_execution_time("compliance_check", capabilities) == 90
        )

        # Documentation search should be quick
        capabilities = {ToolCapability.DOCUMENTATION_SEARCH}
        assert self.discovery._infer_execution_time("doc_search", capabilities) == 15

        # Remediation should take longer
        capabilities = {ToolCapability.AUTOMATED_REMEDIATION}
        assert self.discovery._infer_execution_time("auto_fix", capabilities) == 180

        # Default case
        capabilities = {ToolCapability.RESOURCE_ANALYSIS}
        assert self.discovery._infer_execution_time("analyze", capabilities) == 30

    def test_create_tool_metadata(self):
        """Test tool metadata creation"""
        tool_data = {
            "name": "security_scanner",
            "description": "Scans for security vulnerabilities in AWS resources",
            "parameters": {
                "region": {"type": "string", "description": "AWS region"},
                "resource_type": {
                    "type": "string",
                    "description": "Type of resource to scan",
                },
            },
        }

        metadata = self.discovery._create_tool_metadata(tool_data, "security")

        assert metadata.name == "security_scanner"
        assert (
            metadata.description
            == "Scans for security vulnerabilities in AWS resources"
        )
        assert metadata.mcp_server == "security"
        assert metadata.category == ToolCategory.SECURITY
        assert ToolCapability.SECURITY_ASSESSMENT in metadata.capabilities
        assert ToolCapability.VULNERABILITY_SCANNING in metadata.capabilities
        assert metadata.risk_level == "low"  # No high-risk keywords
        assert metadata.estimated_execution_time == 120  # Vulnerability scanning

    @pytest.mark.asyncio
    async def test_discover_server_tools(self):
        """Test discovering tools from a specific server"""
        # Mock connector
        mock_connector = AsyncMock()
        mock_connector.discover_tools.return_value = [
            {
                "name": "test_tool",
                "description": "A test tool for security scanning",
                "parameters": {"region": {"type": "string"}},
            }
        ]

        # Test discovery
        result = await self.discovery._discover_server_tools(
            "security", mock_connector, force_refresh=True
        )

        assert result.success is True
        assert result.server_name == "security"
        assert result.tools_discovered == 1
        assert result.tools_added == 1
        assert result.tools_updated == 0
        assert result.tools_removed == 0

        # Verify tool was registered
        tools = self.discovery.registry.get_tools_by_server("security")
        assert len(tools) == 1
        assert tools[0].name == "test_tool"

    @pytest.mark.asyncio
    async def test_discover_server_tools_error(self):
        """Test error handling during tool discovery"""
        # Mock connector that raises an exception
        mock_connector = AsyncMock()
        mock_connector.discover_tools.side_effect = Exception("Connection failed")

        # Test discovery
        result = await self.discovery._discover_server_tools(
            "security", mock_connector, force_refresh=True
        )

        assert result.success is False
        assert result.server_name == "security"
        assert result.tools_discovered == 0
        assert result.error_message == "Connection failed"

    @pytest.mark.asyncio
    async def test_get_tools_for_query(self):
        """Test getting tools for a specific query"""
        # Register some test tools
        security_tool = ToolMetadata(
            name="security_scanner",
            description="Scans for security vulnerabilities",
            mcp_server="security",
            category=ToolCategory.SECURITY,
            capabilities={
                ToolCapability.SECURITY_ASSESSMENT,
                ToolCapability.VULNERABILITY_SCANNING,
            },
        )

        knowledge_tool = ToolMetadata(
            name="doc_search",
            description="Search AWS documentation",
            mcp_server="knowledge",
            category=ToolCategory.KNOWLEDGE,
            capabilities={ToolCapability.DOCUMENTATION_SEARCH},
        )

        self.discovery.registry.register_tool(security_tool)
        self.discovery.registry.register_tool(knowledge_tool)

        # Test direct name match
        tools = await self.discovery.get_tools_for_query("scanner")
        assert len(tools) == 1
        assert tools[0].name == "security_scanner"

        # Test capability-based matching
        tools = await self.discovery.get_tools_for_query("security assessment")
        assert len(tools) >= 1
        assert any(tool.name == "security_scanner" for tool in tools)

        # Test documentation search
        tools = await self.discovery.get_tools_for_query("documentation")
        assert len(tools) >= 1
        assert any(tool.name == "doc_search" for tool in tools)

    def test_get_discovery_status(self):
        """Test getting discovery status"""
        status = self.discovery.get_discovery_status()

        assert "auto_discovery_enabled" in status
        assert "discovery_interval" in status
        assert "registry_statistics" in status
        assert "last_discovery_times" in status

        assert status["auto_discovery_enabled"] is True
        assert status["discovery_interval"] == 300

    def test_stop_auto_discovery(self):
        """Test stopping automatic discovery"""
        assert self.discovery.auto_discovery_enabled is True

        self.discovery.stop_auto_discovery()

        assert self.discovery.auto_discovery_enabled is False


class TestDiscoveryResult:
    """Test cases for DiscoveryResult dataclass"""

    def test_discovery_result_creation(self):
        """Test creating a discovery result"""
        result = DiscoveryResult(
            server_name="security",
            tools_discovered=5,
            tools_added=3,
            tools_updated=2,
            tools_removed=0,
            discovery_time=1.5,
            success=True,
        )

        assert result.server_name == "security"
        assert result.tools_discovered == 5
        assert result.tools_added == 3
        assert result.tools_updated == 2
        assert result.tools_removed == 0
        assert result.discovery_time == 1.5
        assert result.success is True
        assert result.error_message is None

    def test_discovery_result_with_error(self):
        """Test creating a discovery result with error"""
        result = DiscoveryResult(
            server_name="api",
            tools_discovered=0,
            tools_added=0,
            tools_updated=0,
            tools_removed=0,
            discovery_time=0.1,
            success=False,
            error_message="Connection timeout",
        )

        assert result.success is False
        assert result.error_message == "Connection timeout"


class TestCapabilityMapping:
    """Test cases for CapabilityMapping dataclass"""

    def test_capability_mapping_creation(self):
        """Test creating a capability mapping"""
        mapping = CapabilityMapping(
            capability=ToolCapability.SECURITY_ASSESSMENT,
            tools=["security:scan_tool", "security:assess_tool"],
            primary_tool="security:scan_tool",
            fallback_tools=["security:assess_tool"],
        )

        assert mapping.capability == ToolCapability.SECURITY_ASSESSMENT
        assert len(mapping.tools) == 2
        assert mapping.primary_tool == "security:scan_tool"
        assert len(mapping.fallback_tools) == 1


class TestToolMetadata:
    """Test cases for ToolMetadata dataclass"""

    def test_tool_metadata_creation(self):
        """Test creating tool metadata"""
        metadata = ToolMetadata(
            name="test_tool",
            description="A test tool",
            mcp_server="security",
            category=ToolCategory.SECURITY,
            capabilities={ToolCapability.SECURITY_ASSESSMENT},
            parameters={"region": {"type": "string"}},
            required_permissions=["ec2:DescribeInstances"],
            estimated_execution_time=60,
            risk_level="medium",
        )

        assert metadata.name == "test_tool"
        assert metadata.description == "A test tool"
        assert metadata.mcp_server == "security"
        assert metadata.category == ToolCategory.SECURITY
        assert ToolCapability.SECURITY_ASSESSMENT in metadata.capabilities
        assert metadata.parameters["region"]["type"] == "string"
        assert "ec2:DescribeInstances" in metadata.required_permissions
        assert metadata.estimated_execution_time == 60
        assert metadata.risk_level == "medium"
        assert metadata.usage_count == 0
        assert metadata.success_rate == 1.0
        assert metadata.average_execution_time == 0.0

    def test_tool_metadata_defaults(self):
        """Test tool metadata with default values"""
        metadata = ToolMetadata(
            name="simple_tool",
            description="A simple tool",
            mcp_server="api",
            category=ToolCategory.API,
        )

        assert len(metadata.capabilities) == 0
        assert len(metadata.parameters) == 0
        assert len(metadata.required_permissions) == 0
        assert metadata.estimated_execution_time == 30
        assert metadata.risk_level == "low"
        assert metadata.usage_count == 0
        assert metadata.success_rate == 1.0
        assert metadata.average_execution_time == 0.0
        assert isinstance(metadata.last_updated, datetime)


if __name__ == "__main__":
    pytest.main([__file__])
