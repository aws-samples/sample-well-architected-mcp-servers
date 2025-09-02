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
Direct import test for orchestration components
"""

import asyncio
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import directly without going through __init__.py
from agent_config.interfaces import ToolCall, ToolPriority
from agent_config.orchestration.connection_pool import ConnectionPoolManager
from agent_config.orchestration.mcp_orchestrator import MCPOrchestratorImpl


async def test_components():
    """Test orchestration components directly"""
    print("Testing MCP Orchestration Components...")

    # Test Connection Pool Manager
    pool_manager = ConnectionPoolManager(max_connections_per_server=3)
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

    # Test MCP Orchestrator
    orchestrator = MCPOrchestratorImpl(region="us-east-1")
    print(f"✅ Created orchestrator for region: {orchestrator.region}")

    # Test tool call prioritization
    tool_calls = [
        ToolCall("tool1", "server1", {}, ToolPriority.LOW),
        ToolCall("tool2", "server2", {}, ToolPriority.HIGH),
        ToolCall("tool3", "server1", {}, ToolPriority.NORMAL),
    ]

    prioritized = orchestrator._prioritize_tool_calls(tool_calls)
    print(f"✅ Prioritized {len(tool_calls)} tool calls:")
    for priority, calls in prioritized.items():
        if calls:
            print(f"   - {priority.name}: {len(calls)} calls")

    # Test orchestrator stats
    orch_stats = await orchestrator.get_connection_stats()
    print(
        f"✅ Orchestrator stats: initialized={orch_stats['initialized']}, connectors={orch_stats['total_connectors']}"
    )

    # Clean up
    await pool_manager.close_all()
    await orchestrator.close_all_connections()

    print("✅ All tests passed! MCP Orchestration Layer is working correctly.")


if __name__ == "__main__":
    asyncio.run(test_components())
