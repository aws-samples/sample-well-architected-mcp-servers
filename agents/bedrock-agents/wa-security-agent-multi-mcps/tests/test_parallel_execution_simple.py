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
Simple test for parallel execution system
Tests core functionality without complex imports
"""

import asyncio
import time
import random
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from datetime import datetime, timedelta


class ToolPriority(Enum):
    """Priority levels for tool execution"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ToolCall:
    """Represents a tool call to an MCP server"""
    tool_name: str
    mcp_server: str
    arguments: Dict[str, Any]
    priority: ToolPriority = ToolPriority.NORMAL
    timeout: int = 120


@dataclass
class ToolResult:
    """Result from an MCP tool call"""
    tool_name: str
    mcp_server: str
    success: bool
    data: Any
    error_message: Optional[str] = None
    execution_time: float = 0.0


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5
    recovery_timeout: int = 60
    success_threshold: int = 3
    timeout_threshold: int = 30


@dataclass
class QueuedRequest:
    """Represents a queued tool call request"""
    tool_call: ToolCall
    future: asyncio.Future
    queued_at: datetime = field(default_factory=datetime.now)
    priority: ToolPriority = ToolPriority.NORMAL


class CircuitBreaker:
    """Circuit breaker implementation"""
    
    def __init__(self, server_name: str, config: CircuitBreakerConfig):
        self.server_name = server_name
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None
        
    def can_execute(self) -> bool:
        """Check if request can be executed"""
        now = datetime.now()
        
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if (self.last_failure_time and 
                now - self.last_failure_time > timedelta(seconds=self.config.recovery_timeout)):
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return True
        
        return False
    
    def record_success(self) -> None:
        """Record a successful request"""
        self.last_success_time = datetime.now()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = 0
    
    def record_failure(self) -> None:
        """Record a failed request"""
        self.last_failure_time = datetime.now()
        self.failure_count += 1
        
        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitBreakerState.OPEN
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN


class RequestQueue:
    """Priority-based request queue"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.queues: Dict[ToolPriority, deque] = {
            priority: deque() for priority in ToolPriority
        }
        self.total_size = 0
        self._lock = asyncio.Lock()
    
    async def enqueue(self, request: QueuedRequest) -> bool:
        """Add request to queue"""
        async with self._lock:
            if self.total_size >= self.max_size:
                return False
            
            self.queues[request.priority].append(request)
            self.total_size += 1
            return True
    
    async def dequeue(self) -> Optional[QueuedRequest]:
        """Dequeue highest priority request"""
        async with self._lock:
            for priority in reversed(list(ToolPriority)):
                if self.queues[priority]:
                    request = self.queues[priority].popleft()
                    self.total_size -= 1
                    return request
            return None


class SimpleParallelExecutor:
    """Simplified parallel execution engine for testing"""
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.request_queue = RequestQueue()
        self.executor_func: Optional[Callable] = None
        
    def set_executor_function(self, func: Callable):
        """Set the executor function"""
        self.executor_func = func
    
    def _get_circuit_breaker(self, server_name: str) -> CircuitBreaker:
        """Get or create circuit breaker"""
        if server_name not in self.circuit_breakers:
            config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=1)
            self.circuit_breakers[server_name] = CircuitBreaker(server_name, config)
        return self.circuit_breakers[server_name]
    
    async def execute_parallel_calls(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """Execute tool calls in parallel"""
        if not tool_calls:
            return []
        
        # Create tasks for parallel execution
        tasks = []
        for tool_call in tool_calls:
            task = asyncio.create_task(self._execute_with_circuit_breaker(tool_call))
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = ToolResult(
                    tool_name=tool_calls[i].tool_name,
                    mcp_server=tool_calls[i].mcp_server,
                    success=False,
                    data=None,
                    error_message=str(result)
                )
                processed_results.append(error_result)
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _execute_with_circuit_breaker(self, tool_call: ToolCall) -> ToolResult:
        """Execute tool call with circuit breaker protection"""
        circuit_breaker = self._get_circuit_breaker(tool_call.mcp_server)
        
        # Check circuit breaker
        if not circuit_breaker.can_execute():
            return ToolResult(
                tool_name=tool_call.tool_name,
                mcp_server=tool_call.mcp_server,
                success=False,
                data=None,
                error_message=f"Circuit breaker open for {tool_call.mcp_server}"
            )
        
        async with self.semaphore:
            start_time = time.time()
            
            try:
                # Execute with timeout
                if self.executor_func:
                    result = await asyncio.wait_for(
                        self.executor_func(tool_call),
                        timeout=tool_call.timeout
                    )
                else:
                    # Default simulation
                    await asyncio.sleep(0.1)
                    result = ToolResult(
                        tool_name=tool_call.tool_name,
                        mcp_server=tool_call.mcp_server,
                        success=True,
                        data={"simulated": True}
                    )
                
                result.execution_time = time.time() - start_time
                circuit_breaker.record_success()
                return result
                
            except asyncio.TimeoutError:
                execution_time = time.time() - start_time
                circuit_breaker.record_failure()
                return ToolResult(
                    tool_name=tool_call.tool_name,
                    mcp_server=tool_call.mcp_server,
                    success=False,
                    data=None,
                    error_message=f"Timed out after {execution_time:.1f}s",
                    execution_time=execution_time
                )
                
            except Exception as e:
                execution_time = time.time() - start_time
                circuit_breaker.record_failure()
                return ToolResult(
                    tool_name=tool_call.tool_name,
                    mcp_server=tool_call.mcp_server,
                    success=False,
                    data=None,
                    error_message=str(e),
                    execution_time=execution_time
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
    await asyncio.sleep(1.1)
    assert breaker.can_execute() is True
    assert breaker.state == CircuitBreakerState.HALF_OPEN
    
    print("✅ Circuit Breaker tests passed")


async def test_request_queue():
    """Test request queue functionality"""
    print("Testing Request Queue...")
    
    queue = RequestQueue(max_size=5)
    
    # Test priority ordering
    low_call = ToolCall("low", "server", {}, ToolPriority.LOW)
    high_call = ToolCall("high", "server", {}, ToolPriority.HIGH)
    critical_call = ToolCall("critical", "server", {}, ToolPriority.CRITICAL)
    
    # Enqueue in random order
    await queue.enqueue(QueuedRequest(low_call, asyncio.Future(), priority=ToolPriority.LOW))
    await queue.enqueue(QueuedRequest(high_call, asyncio.Future(), priority=ToolPriority.HIGH))
    await queue.enqueue(QueuedRequest(critical_call, asyncio.Future(), priority=ToolPriority.CRITICAL))
    
    # Should dequeue in priority order
    request1 = await queue.dequeue()
    assert request1.tool_call.tool_name == "critical"
    
    request2 = await queue.dequeue()
    assert request2.tool_call.tool_name == "high"
    
    request3 = await queue.dequeue()
    assert request3.tool_call.tool_name == "low"
    
    print("✅ Request Queue tests passed")


async def test_parallel_execution():
    """Test parallel execution"""
    print("Testing Parallel Execution...")
    
    executor = SimpleParallelExecutor(max_concurrent=3)
    
    # Mock executor function
    async def mock_executor(tool_call):
        await asyncio.sleep(0.1)
        return ToolResult(
            tool_name=tool_call.tool_name,
            mcp_server=tool_call.mcp_server,
            success=True,
            data={"result": f"success_{tool_call.tool_name}"}
        )
    
    executor.set_executor_function(mock_executor)
    
    # Test parallel execution
    tool_calls = [
        ToolCall(f"tool_{i}", "server", {}, ToolPriority.NORMAL, 10)
        for i in range(5)
    ]
    
    start_time = time.time()
    results = await executor.execute_parallel_calls(tool_calls)
    execution_time = time.time() - start_time
    
    # Should complete in roughly parallel time
    assert execution_time < 1.0
    assert len(results) == 5
    
    for i, result in enumerate(results):
        assert result.success is True
        assert result.tool_name == f"tool_{i}"
    
    print("✅ Parallel Execution tests passed")


async def test_timeout_handling():
    """Test timeout handling"""
    print("Testing Timeout Handling...")
    
    executor = SimpleParallelExecutor()
    
    # Mock executor that takes too long
    async def slow_executor(tool_call):
        await asyncio.sleep(2.0)
        return ToolResult(
            tool_name=tool_call.tool_name,
            mcp_server=tool_call.mcp_server,
            success=True,
            data={"result": "success"}
        )
    
    executor.set_executor_function(slow_executor)
    
    # Create tool call with short timeout
    tool_calls = [ToolCall("slow_tool", "server", {}, ToolPriority.NORMAL, 1)]
    
    results = await executor.execute_parallel_calls(tool_calls)
    
    assert len(results) == 1
    assert results[0].success is False
    assert "timed out" in results[0].error_message.lower()
    
    print("✅ Timeout Handling tests passed")


async def test_circuit_breaker_integration():
    """Test circuit breaker integration"""
    print("Testing Circuit Breaker Integration...")
    
    executor = SimpleParallelExecutor()
    
    # Mock executor that always fails
    async def failing_executor(tool_call):
        raise Exception("Simulated failure")
    
    executor.set_executor_function(failing_executor)
    
    # Create multiple tool calls to trigger circuit breaker
    # First batch to trigger circuit breaker
    first_batch = [
        ToolCall(f"tool_{i}", "failing_server", {}, ToolPriority.NORMAL, 10)
        for i in range(4)  # More than failure threshold
    ]
    
    await executor.execute_parallel_calls(first_batch)
    
    # Second batch should hit circuit breaker
    second_batch = [
        ToolCall(f"tool_{i}", "failing_server", {}, ToolPriority.NORMAL, 10)
        for i in range(3)
    ]
    
    results = await executor.execute_parallel_calls(second_batch)
    
    # Some requests should fail due to circuit breaker
    failed_results = [r for r in results if not r.success]
    circuit_breaker_failures = [
        r for r in failed_results 
        if "circuit breaker" in r.error_message.lower()
    ]
    
    # Should have some circuit breaker failures
    assert len(circuit_breaker_failures) > 0
    
    print("✅ Circuit Breaker Integration tests passed")


async def main():
    """Run all tests"""
    print("🚀 Starting Parallel Execution System Tests")
    print("=" * 50)
    
    try:
        await test_circuit_breaker()
        await test_request_queue()
        await test_parallel_execution()
        await test_timeout_handling()
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
    exit(exit_code)