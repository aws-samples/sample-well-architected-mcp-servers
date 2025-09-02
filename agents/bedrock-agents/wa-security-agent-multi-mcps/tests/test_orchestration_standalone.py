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
Standalone test for orchestration components without package imports
"""

import asyncio
import importlib.util
import os
import sys


def load_module_from_path(module_name, file_path):
    """Load a module directly from file path"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


async def test_orchestration():
    """Test orchestration components"""
    print("Testing MCP Orchestration Components (Standalone)...")

    # Get the base directory
    base_dir = os.path.dirname(__file__)

    # Load interfaces module
    interfaces_path = os.path.join(base_dir, "agent_config", "interfaces.py")
    interfaces = load_module_from_path("interfaces", interfaces_path)

    # Load utils modules
    logging_utils_path = os.path.join(
        base_dir, "agent_config", "utils", "logging_utils.py"
    )
    logging_utils = load_module_from_path("logging_utils", logging_utils_path)

    error_handling_path = os.path.join(
        base_dir, "agent_config", "utils", "error_handling.py"
    )
    error_handling = load_module_from_path("error_handling", error_handling_path)

    # Load connection pool
    connection_pool_path = os.path.join(
        base_dir, "agent_config", "orchestration", "connection_pool.py"
    )
    connection_pool = load_module_from_path("connection_pool", connection_pool_path)

    # Test Connection Pool Manager
    pool_manager = connection_pool.ConnectionPoolManager(max_connections_per_server=3)
    print(
        f"✅ Created connection pool manager with max {pool_manager.max_connections_per_server} connections per server"
    )

    # Test getting a connection
    connection = await pool_manager.get_connection("test_server")
    print(f"✅ Created connection: {connection.connection_id}")

    # Test returning connection
    await pool_manager.return_connection(connection, success=True)
    print("✅ Returned connection successfully")

    # Test pool stats
    stats = await pool_manager.get_stats()
    print(
        f"✅ Pool stats: {stats['overall']['total_servers']} servers, {stats['overall']['total_connections']} connections"
    )

    # Test connection info
    connection_info = connection_pool.ConnectionInfo(
        connection_id="test_id",
        server_name="test_server",
        created_at=connection_pool.datetime.now(),
        last_used=connection_pool.datetime.now(),
    )
    print(f"✅ Created connection info: {connection_info.connection_id}")

    # Test pool stats dataclass
    pool_stats = connection_pool.PoolStats()
    print(f"✅ Created pool stats: {pool_stats.total_connections} total connections")

    # Clean up
    await pool_manager.close_all()

    print("✅ All tests passed! Connection Pool Manager is working correctly.")

    # Test basic interfaces
    print("\nTesting interfaces...")

    # Test enums
    server_type = interfaces.MCPServerType.SECURITY
    print(f"✅ MCPServerType.SECURITY: {server_type.value}")

    priority = interfaces.ToolPriority.HIGH
    print(f"✅ ToolPriority.HIGH: {priority.value}")

    # Test dataclasses
    tool_call = interfaces.ToolCall(
        tool_name="test_tool",
        mcp_server="test_server",
        arguments={"arg": "value"},
        priority=priority,
    )
    print(f"✅ Created ToolCall: {tool_call.tool_name}")

    tool_result = interfaces.ToolResult(
        tool_name="test_tool", mcp_server="test_server", success=True, data="test_data"
    )
    print(f"✅ Created ToolResult: {tool_result.success}")

    config = interfaces.MCPServerConfig(
        name="test_server", server_type=server_type, connection_type="test"
    )
    print(f"✅ Created MCPServerConfig: {config.name}")

    print("✅ All interface tests passed!")


if __name__ == "__main__":
    asyncio.run(test_orchestration())
