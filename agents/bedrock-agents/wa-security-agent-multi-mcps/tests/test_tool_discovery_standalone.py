#!/usr/bin/env python3

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
Standalone test for Tool Discovery functionality
Tests the core tool discovery mechanism without external dependencies
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, Mock

# Add the current directory to the path to import modules directly
sys.path.insert(0, os.path.dirname(__file__))

# Import the tool discovery components directly without triggering agent imports
import importlib.util

# Load the tool discovery module directly
spec = importlib.util.spec_from_file_location(
    "tool_discovery",
    os.path.join(
        os.path.dirname(__file__), "agent_config", "orchestration", "tool_discovery.py"
    ),
)
tool_discovery_module = importlib.util.module_from_spec(spec)


# Mock the logging and error handling imports to avoid dependency issues
class MockLogger:
    def info(self, msg):
        print(f"INFO: {msg}")

    def debug(self, msg):
        print(f"DEBUG: {msg}")

    def warning(self, msg):
        print(f"WARNING: {msg}")

    def error(self, msg):
        print(f"ERROR: {msg}")


class MockErrorHandler:
    def handle_initialization_error(self, e):
        pass


# Patch the imports
sys.modules["agent_config.utils.logging_utils"] = type(
    "MockModule", (), {"get_logger": lambda name=None: MockLogger()}
)()
sys.modules["agent_config.utils.error_handling"] = type(
    "MockModule", (), {"ErrorHandler": MockErrorHandler}
)()

# Now load the module
spec.loader.exec_module(tool_discovery_module)

# Import the classes we need
UnifiedToolDiscovery = tool_discovery_module.UnifiedToolDiscovery
ToolRegistry = tool_discovery_module.ToolRegistry
ToolMetadata = tool_discovery_module.ToolMetadata
ToolCapability = tool_discovery_module.ToolCapability
ToolCategory = tool_discovery_module.ToolCategory
CapabilityMapping = tool_discovery_module.CapabilityMapping
DiscoveryResult = tool_discovery_module.DiscoveryResult


def test_tool_registry_basic_functionality():
    """Test basic tool registry functionality"""
    print("Testing ToolRegistry basic functionality...")

    registry = ToolRegistry()

    # Test initialization
    assert len(registry.tools) == 0
    assert len(registry.capabilities) == len(ToolCapability)
    print("✅ Registry initialization successful")

    # Test tool registration
    tool_metadata = ToolMetadata(
        name="test_security_tool",
        description="A test security tool for vulnerability scanning",
        mcp_server="security",
        category=ToolCategory.SECURITY,
        capabilities={
            ToolCapability.SECURITY_ASSESSMENT,
            ToolCapability.VULNERABILITY_SCANNING,
        },
    )

    result = registry.register_tool(tool_metadata)
    assert result is True

    tool_key = "security:test_security_tool"
    assert tool_key in registry.tools
    assert registry.tools[tool_key] == tool_metadata
    print("✅ Tool registration successful")

    # Test getting tools by capability
    security_tools = registry.get_tools_by_capability(
        ToolCapability.SECURITY_ASSESSMENT
    )
    assert len(security_tools) == 1
    assert security_tools[0].name == "test_security_tool"
    print("✅ Get tools by capability successful")

    # Test getting tools by server
    server_tools = registry.get_tools_by_server("security")
    assert len(server_tools) == 1
    assert server_tools[0].name == "test_security_tool"
    print("✅ Get tools by server successful")

    # Test search functionality
    search_results = registry.search_tools("security")
    assert len(search_results) == 1
    assert search_results[0].name == "test_security_tool"
    print("✅ Tool search successful")

    # Test usage statistics
    registry.update_tool_usage(tool_key, 15.5, True)
    tool = registry.tools[tool_key]
    assert tool.usage_count == 1
    assert tool.success_rate == 1.0
    assert tool.average_execution_time == 15.5
    print("✅ Usage statistics update successful")

    print("✅ All ToolRegistry tests passed!")


def test_unified_tool_discovery():
    """Test unified tool discovery functionality"""
    print("\nTesting UnifiedToolDiscovery functionality...")

    # Create mock orchestrator
    mock_orchestrator = Mock()
    mock_orchestrator._initialized = True
    mock_orchestrator.connectors = {
        "security": Mock(),
        "knowledge": Mock(),
        "api": Mock(),
    }

    discovery = UnifiedToolDiscovery(mock_orchestrator)

    # Test initialization
    assert discovery.orchestrator == mock_orchestrator
    assert isinstance(discovery.registry, ToolRegistry)
    assert discovery.discovery_interval == 300
    print("✅ Discovery initialization successful")

    # Test capability inference
    capabilities = discovery._infer_capabilities(
        "security_scanner", "Scans for security vulnerabilities"
    )
    assert ToolCapability.SECURITY_ASSESSMENT in capabilities
    assert ToolCapability.VULNERABILITY_SCANNING in capabilities
    print("✅ Capability inference successful")

    # Test category inference
    assert discovery._infer_category("security") == ToolCategory.SECURITY
    assert discovery._infer_category("knowledge") == ToolCategory.KNOWLEDGE
    assert discovery._infer_category("api") == ToolCategory.API
    print("✅ Category inference successful")

    # Test risk level inference
    assert (
        discovery._infer_risk_level("delete_resource", "Delete AWS resource") == "high"
    )
    assert (
        discovery._infer_risk_level("modify_config", "Modify configuration") == "medium"
    )
    assert discovery._infer_risk_level("list_buckets", "List S3 buckets") == "low"
    print("✅ Risk level inference successful")

    # Test execution time inference
    vuln_capabilities = {ToolCapability.VULNERABILITY_SCANNING}
    assert discovery._infer_execution_time("vuln_scan", vuln_capabilities) == 120

    doc_capabilities = {ToolCapability.DOCUMENTATION_SEARCH}
    assert discovery._infer_execution_time("doc_search", doc_capabilities) == 15
    print("✅ Execution time inference successful")

    # Test tool metadata creation
    tool_data = {
        "name": "test_scanner",
        "description": "Scans for security vulnerabilities in AWS resources",
        "parameters": {"region": {"type": "string", "description": "AWS region"}},
    }

    metadata = discovery._create_tool_metadata(tool_data, "security")
    assert metadata.name == "test_scanner"
    assert metadata.mcp_server == "security"
    assert metadata.category == ToolCategory.SECURITY
    assert ToolCapability.SECURITY_ASSESSMENT in metadata.capabilities
    print("✅ Tool metadata creation successful")

    print("✅ All UnifiedToolDiscovery tests passed!")


async def test_async_discovery_functionality():
    """Test async discovery functionality"""
    print("\nTesting async discovery functionality...")

    # Create mock orchestrator with async connectors
    mock_orchestrator = Mock()
    mock_orchestrator._initialized = True

    mock_connector = AsyncMock()
    mock_connector.discover_tools.return_value = [
        {
            "name": "async_test_tool",
            "description": "An async test tool for security assessment",
            "parameters": {"region": {"type": "string"}},
        }
    ]

    mock_orchestrator.connectors = {"security": mock_connector}

    discovery = UnifiedToolDiscovery(mock_orchestrator)

    # Test server tool discovery
    result = await discovery._discover_server_tools(
        "security", mock_connector, force_refresh=True
    )

    assert result.success is True
    assert result.server_name == "security"
    assert result.tools_discovered == 1
    assert result.tools_added == 1
    print("✅ Async server tool discovery successful")

    # Verify tool was registered
    tools = discovery.registry.get_tools_by_server("security")
    assert len(tools) == 1
    assert tools[0].name == "async_test_tool"
    print("✅ Tool registration from async discovery successful")

    # Test getting tools for query
    query_tools = await discovery.get_tools_for_query("security assessment")
    assert len(query_tools) >= 1
    assert any(tool.name == "async_test_tool" for tool in query_tools)
    print("✅ Query-based tool retrieval successful")

    print("✅ All async discovery tests passed!")


def test_capability_mapping():
    """Test capability mapping functionality"""
    print("\nTesting capability mapping...")

    registry = ToolRegistry()

    # Register multiple tools with overlapping capabilities
    tool1 = ToolMetadata(
        name="primary_scanner",
        description="Primary security scanner",
        mcp_server="security",
        category=ToolCategory.SECURITY,
        capabilities={
            ToolCapability.SECURITY_ASSESSMENT,
            ToolCapability.VULNERABILITY_SCANNING,
        },
    )

    tool2 = ToolMetadata(
        name="backup_scanner",
        description="Backup security scanner",
        mcp_server="security",
        category=ToolCategory.SECURITY,
        capabilities={ToolCapability.SECURITY_ASSESSMENT},
    )

    tool3 = ToolMetadata(
        name="compliance_tool",
        description="Compliance checking tool",
        mcp_server="security",
        category=ToolCategory.SECURITY,
        capabilities={
            ToolCapability.COMPLIANCE_CHECKING,
            ToolCapability.SECURITY_ASSESSMENT,
        },
    )

    registry.register_tool(tool1)
    registry.register_tool(tool2)
    registry.register_tool(tool3)

    # Test capability mapping
    security_assessment_tools = registry.get_tools_by_capability(
        ToolCapability.SECURITY_ASSESSMENT
    )
    assert len(security_assessment_tools) == 3
    print("✅ Multiple tools mapped to capability")

    vulnerability_tools = registry.get_tools_by_capability(
        ToolCapability.VULNERABILITY_SCANNING
    )
    assert len(vulnerability_tools) == 1
    assert vulnerability_tools[0].name == "primary_scanner"
    print("✅ Single tool mapped to specific capability")

    compliance_tools = registry.get_tools_by_capability(
        ToolCapability.COMPLIANCE_CHECKING
    )
    assert len(compliance_tools) == 1
    assert compliance_tools[0].name == "compliance_tool"
    print("✅ Compliance capability mapping successful")

    print("✅ All capability mapping tests passed!")


def test_tool_statistics():
    """Test tool statistics functionality"""
    print("\nTesting tool statistics...")

    registry = ToolRegistry()

    # Register tools from different servers and categories
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

    api_tool = ToolMetadata(
        name="api_tool",
        description="API tool",
        mcp_server="api",
        category=ToolCategory.API,
        capabilities={ToolCapability.RESOURCE_ANALYSIS},
    )

    registry.register_tool(security_tool)
    registry.register_tool(knowledge_tool)
    registry.register_tool(api_tool)

    # Get statistics
    stats = registry.get_tool_statistics()

    assert stats["total_tools"] == 3
    assert stats["tools_by_server"]["security"] == 1
    assert stats["tools_by_server"]["knowledge"] == 1
    assert stats["tools_by_server"]["api"] == 1
    assert stats["tools_by_category"]["security"] == 1
    assert stats["tools_by_category"]["knowledge"] == 1
    assert stats["tools_by_category"]["api"] == 1
    print("✅ Tool statistics calculation successful")

    # Test usage statistics
    registry.update_tool_usage("security:security_tool", 10.0, True)
    registry.update_tool_usage("security:security_tool", 20.0, False)

    tool = registry.tools["security:security_tool"]
    assert tool.usage_count == 2
    assert tool.success_rate == 0.5
    assert tool.average_execution_time == 15.0
    print("✅ Usage statistics tracking successful")

    print("✅ All statistics tests passed!")


async def run_all_tests():
    """Run all tests"""
    print("🚀 Starting Tool Discovery Tests...")
    print("=" * 60)

    try:
        # Run synchronous tests
        test_tool_registry_basic_functionality()
        test_unified_tool_discovery()
        test_capability_mapping()
        test_tool_statistics()

        # Run asynchronous tests
        await test_async_discovery_functionality()

        print("\n" + "=" * 60)
        print(
            "🎉 ALL TESTS PASSED! Tool Discovery implementation is working correctly."
        )
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Run the tests
    success = asyncio.run(run_all_tests())

    if success:
        print("\n✅ Tool Discovery implementation validated successfully!")
        print("Key features implemented:")
        print("  • Tool registry with capabilities mapping")
        print("  • Dynamic tool discovery and updates")
        print("  • Capability-based tool selection")
        print("  • Usage statistics tracking")
        print("  • Multi-server tool orchestration")
        print("  • Intelligent tool categorization")
        exit(0)
    else:
        print("\n❌ Tool Discovery tests failed!")
        exit(1)
