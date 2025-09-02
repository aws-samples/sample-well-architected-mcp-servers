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
Standalone test for parallel execution system
Tests the parallel execution engine without dependencies on the full agent
"""

import asyncio
import time
import sys
import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Any, Optional

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Define minimal interfaces for testing
class ToolPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3

@dataclass
class ToolCall:
    tool_name: str
    mcp_server: str
    arguments: Dict[str, Any]
    priority: ToolPriority = ToolPriority.NORMAL
    timeout: int = 120

@dataclass
class ToolResult:
    tool_name: str
    mcp_server: str
    success: bool
    data: Any
    error_message: Optional[str] = None
    execution_time: float = 0.0

# Import the parallel executor components directly
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agent_config', 'orchestration'))

from parallel_executor import (
    ParallelExecutionEngine, CircuitBreaker, CircuitBreakerConfig,
    CircuitBreakerState, RequestQueue, LoadBalancer
)


async def test_circuit_breaker():
    """Test circuit breaker functionality"""
    print("Testing Circuit Breaker...")
    
    config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=1)
    breaker = CircuitBreaker("test-server", config)
    
    # Test initial state
    assert breaker.state == CircuitBreakerState.CLOSED
    assert breaker.can_execute() is True
    
    # Test failure tracking
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitBreakerState.CLOSED
    
    breaker.record_failure()  # Should open circuit
    assert breaker.state == CircuitBreakerState.OPEN
    assert breaker.can_execute() is False
    
    # Test recovery
    await asyncio.sleep(1.1)  # Wait for recovery timeout
    assert breaker.can_execute() is True
    assert breaker.state == CircuitBreakerState.HALF_OPEN
    
    # Test success in half-open
    breaker.record_success()
    breaker.record_success()
    breaker.record_success()
    assert breaker.state == CircuitBreakerState.CLOSED
    
    print("✅ Circuit Breaker tests passed")


async def test_request_queue():
    """Test request queue functionality"""
    print("Testing Request Queue...")
    
    queue = RequestQueue(max_size=5)
    
    # Test priority ordering
    from parallel_executor import QueuedRequest
    
    low_call = ToolCall("low", "server", {}, ToolPriority.LOW)
    high_call = ToolCall("high", "server", {}, ToolPriority.HIGH)
    critical_call = ToolCall("critical", "server", {}, ToolPriority.CRITICAL)
    
    # Enqueue in random order
    await queue.enqueue(QueuedRequest(low_call, asyncio.Future()))
    await queue.enqueue(QueuedRequest(high_call, asyncio.Future()))
    await queue.enqueue(QueuedRequest(critical_call, asyncio.Future()))
    
    # Should dequeue in priority order
    request1 = await queue.dequeue()
    assert request1.tool_call.tool_name == "critical"
    
    request2 = await queue.dequeue()
    assert request2.tool_call.tool_name == "high"
    
    request3 = await queue.dequeue()
    assert request3.tool_call.tool_name == "low"
    
    print("✅ Request Queue tests passed")


async def test_load_balancer():
    """Test load balancer functionality"""
    print("Testing Load Balancer...")
    
    balancer = LoadBalancer()
    
    # Test server selection
    servers = ["server1", "server2", "server3"]
    selected = await balancer.select_server(servers)
    assert selected in servers
    
    # Test request tracking
    await balancer.record_request_result("server1", True, 1.0)
    await balancer.record_request_result("server1", False, 2.0)
    
    stats = await balancer.get_load_balancer_stats()
    assert stats["server1"]["total_requests"] == 2
    assert stats["server1"]["success_rate"] == 0.5
    
    print("✅ Load Balancer tests passed")


async def test_parallel_execution_engine():
    """Test parallel execution engine"""
    print("Testing Parallel Execution Engine...")
    
    engine = ParallelExecutionEngine(max_concurrent_requests=3)
    
    # Mock executor function
    async def mock_executor(tool_call):
        await asyncio.sleep(0.1)  # Simulate work
        return ToolResult(
            tool_name=tool_call.tool_name,
            mcp_server=tool_call.mcp_server,
            success=True,
            data={"result": f"success_{tool_call.tool_name}"}
        )
    
    engine.set_executor_function(mock_executor)
    
    # Test parallel execution
    tool_calls = [
        ToolCall(f"tool_{i}", "server", {}, ToolPriority.NORMAL, 10)
        for i in range(5)
    ]
    
    start_time = time.time()
    results = await engine.execute_parallel_calls(tool_calls)
    execution_time = time.time() - start_time
    
    # Should complete in roughly parallel time
    assert execution_time < 1.0  # Much less than sequential time
    assert len(results) == 5
    
    for i, result in enumerate(results):
        assert result.success is True
        assert result.tool_name == f"tool_{i}"
    
    # Test timeout handling
    async def slow_executor(tool_call):
        await asyncio.sleep(2.0)  # Longer than timeout
        return ToolResult(
            tool_name=tool_call.tool_name,
            mcp_server=tool_call.mcp_server,
            success=True,
            data={"result": "success"}
        )
    
    engine.set_executor_function(slow_executor)
    
    timeout_calls = [ToolCall("slow_tool", "server", {}, ToolPriority.NORMAL, 1)]
    timeout_results = await engine.execute_parallel_calls(timeout_calls)
    
    assert len(timeout_results) == 1
    assert timeout_results[0].success is False
    assert "timed out" in timeout_results[0].error_message.lower()
    
    # Test priority handling
    execution_order = []
    
    async def tracking_executor(tool_call):
        execution_order.append(tool_call.tool_name)
        await asyncio.sleep(0.1)
        return ToolResult(
            tool_name=tool_call.tool_name,
            mcp_server=tool_call.mcp_server,
            success=True,
            data={"result": "success"}
        )
    
    # Create new engine with limited concurrency to force ordering
    priority_engine = ParallelExecutionEngine(max_concurrent_requests=1)
    priority_engine.set_executor_function(tracking_executor)
    
    priority_calls = [
        ToolCall("low", "server", {}, ToolPriority.LOW, 10),
        ToolCall("critical", "server", {}, ToolPriority.CRITICAL, 10),
        ToolCall("normal", "server", {}, ToolPriority.NORMAL, 10),
        ToolCall("high", "server", {}, ToolPriority.HIGH, 10),
    ]
    
    await priority_engine.execute_parallel_calls(priority_calls)
    
    # Should execute in priority order
    expected_order = ["critical", "high", "normal", "low"]
    assert execution_order == expected_order
    
    # Get execution stats
    stats = await engine.get_execution_stats()
    assert "total_requests" in stats
    assert "success_rate" in stats
    assert "queue_stats" in stats
    
    await engine.stop()
    await priority_engine.stop()
    
    print("✅ Parallel Execution Engine tests passed")


async def test_circuit_breaker_integration():
    """Test circuit breaker integration with execution engine"""
    print("Testing Circuit Breaker Integration...")
    
    engine = ParallelExecutionEngine()
    
    # Mock executor that always fails
    async def failing_executor(tool_call):
        raise Exception("Simulated failure")
    
    engine.set_executor_function(failing_executor)
    
    # Create multiple tool calls to trigger circuit breaker
    tool_calls = [
        ToolCall(f"tool_{i}", "failing_server", {}, ToolPriority.NORMAL, 10)
        for i in range(8)
    ]
    
    results = await engine.execute_parallel_calls(tool_calls)
    
    # Some requests should fail due to circuit breaker
    failed_results = [r for r in results if not r.success]
    circuit_breaker_failures = [
        r for r in failed_results 
        if "circuit breaker" in r.error_message.lower()
    ]
    
    # Should have some circuit breaker failures after initial failures
    assert len(circuit_breaker_failures) > 0
    
    await engine.stop()
    
    print("✅ Circuit Breaker Integration tests passed")


async def main():
    """Run all tests"""
    print("🚀 Starting Parallel Execution System Tests")
    print("=" * 50)
    
    try:
        await test_circuit_breaker()
        await test_request_queue()
        await test_load_balancer()
        await test_parallel_execution_engine()
        await test_circuit_breaker_integration()
        
        print("=" * 50)
        print("🎉 All tests passed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)