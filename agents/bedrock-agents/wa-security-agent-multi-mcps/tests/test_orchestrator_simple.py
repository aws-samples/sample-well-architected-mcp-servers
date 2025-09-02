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
Simple test script for MCP Orchestrator without full agent dependencies
"""

import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from agent_config.orchestration.mcp_orchestrator import MCPOrchestratorImpl
from agent_config.interfaces import ToolCall, ToolPriority


async def test_orchestrator():
    """Simple test of orchestrator functionality"""
    print("Testing MCP Orchestrator...")
    
    # Create orchestrator
    orchestrator = MCPOrchestratorImpl(region="us-east-1")
    print(f"✅ Created orchestrator for region: {orchestrator.region}")
    
    # Test prioritization
    tool_calls = [
        ToolCall("tool1", "server1", {}, ToolPriority.LOW),
        ToolCall("tool2", "server2", {}, ToolPriority.HIGH),
        ToolCall("tool3", "server1", {}, ToolPriority.NORMAL),
    ]
    
    prioritized = orchestrator._prioritize_tool_calls(tool_calls)
    print(f"✅ Prioritized {len(tool_calls)} tool calls")
    print(f"   - LOW priority: {len(prioritized[ToolPriority.LOW])}")
    print(f"   - NORMAL priority: {len(prioritized[ToolPriority.NORMAL])}")
    print(f"   - HIGH priority: {len(prioritized[ToolPriority.HIGH])}")
    
    # Test connection stats (without actual connections)
    stats = await orchestrator.get_connection_stats()
    print(f"✅ Retrieved connection stats: {stats['total_connectors']} connectors")
    
    print("✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_orchestrator())