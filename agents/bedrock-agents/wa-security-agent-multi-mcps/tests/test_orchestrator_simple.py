#!/usr/bin/env python3
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