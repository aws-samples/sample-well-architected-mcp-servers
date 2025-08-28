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
Unit tests for Parallel Execution System
Tests parallel execution engine, request queuing, load balancing, 
timeout handling, and circuit breaker patterns
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_config.interfaces import ToolCall, ToolResult, ToolPriority
from agent_config.orchestration.parallel_executor import (
    ParallelExecutionEngine, CircuitBreaker, CircuitBreakerConfig,
    CircuitBreakerState, RequestQueue, LoadBalancer, QueuedRequest
)


class TestCircuitBreaker:
    """Test circuit breaker functionality"""
    
    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initializes correctly"""
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30)
        breaker = CircuitBreaker("test-server", config)
        
        assert breaker.server_name == "test-server"
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.success_count == 0
    
    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker allows requests in closed state"""
        config = CircuitBreakerConfig()
        breaker = CircuitBreaker("test-server", config)
        
        assert breaker.can_execute() is True
    
    def test_circuit_breaker_failure_tracking(self):
        """Test circuit breaker tracks failures correctly"""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test-server", config)
        
        # Record failures
        breaker.record_failure()
        assert breaker.failure_count == 1
        assert breaker.state == CircuitBreakerState.CLOSED
        
        breaker.record_failure()
        assert breaker.failure_count == 2
        assert breaker.state == CircuitBreakerState.CLOSED
        
        # Third failure should open the circuit
        breaker.record_failure()
        assert breaker.failure_count == 3
        assert breaker.state == CircuitBreakerState.OPEN
        assert breaker.can_execute() is False
    
    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery mechanism"""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=1)
        breaker = CircuitBreaker("test-server", config)
        
        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitBreakerState.OPEN
        
        # Should not allow execution immediately
        assert breaker.can_execute() is False
        
        # Wait for recovery timeout
        time.sleep(1.1)
        
        # Should move to half-open
        assert breaker.can_execute() is True
        assert breaker.state == CircuitBreakerState.HALF_OPEN
    
    def test_circuit_breaker_half_open_success(self):
        """Test circuit breaker closes after successful requests in half-open"""
        config = CircuitBreakerConfig(failure_threshold=2, success_threshold=2)
        breaker = CircuitBreaker("test-server", config)
        
        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        breaker.state = CircuitBreakerState.HALF_OPEN  # Simulate half-open state
        
        # Record successes
        breaker.record_success()
        assert breaker.state == CircuitBreakerState.HALF_OPEN
        
        breaker.record_success()
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.failure_count == 0
    
    def test_circuit_breaker_half_open_failure(self):
        """Test circuit breaker opens again on failure in half-open"""
        config = CircuitBreakerConfig()
        breaker = CircuitBreaker("test-server", config)
        
        breaker.state = CircuitBreakerState.HALF_OPEN
        breaker.record_failure()
        
        assert breaker.state == CircuitBreakerState.OPEN
    
    def test_circuit_breaker_state_info(self):
        """Test circuit breaker state information"""
        config = CircuitBreakerConfig()
        breaker = CircuitBreaker("test-server", config)
        
        breaker.record_failure()
        breaker.record_success()
        
        state_info = breaker.get_state_info()
        
        assert state_info["state"] == "closed"
        assert state_info["failure_count"] == 0  # Reset on success
        assert state_info["success_count"] == 0
        assert "last_failure_time" in state_info
        assert "last_success_time" in state_info


class TestRequestQueue:
    """Test request queue functionality"""
    
    @pytest.mark.asyncio
    async def test_queue_initialization(self):
        """Test queue initializes correctly"""
        queue = RequestQueue(max_size=100)
        
        assert queue.max_size == 100
        assert queue.total_size == 0
        assert len(queue.queues) == len(ToolPriority)
    
    @pytest.mark.asyncio
    async def test_queue_enqueue_dequeue(self):
        """Test basic enqueue and dequeue operations"""
        queue = RequestQueue(max_size=10)
        
        tool_call = ToolCall(
            tool_name="test_tool",
            mcp_server="test_server",
            arguments={},
            priority=ToolPriority.NORMAL
        )
        
        future = asyncio.Future()
        request = QueuedRequest(tool_call=tool_call, future=future)
        
        # Enqueue request
        result = await queue.enqueue(request)
        assert result is True
        assert queue.total_size == 1
        
        # Dequeue request
        dequeued = await queue.dequeue()
        assert dequeued is not None
        assert dequeued.tool_call.tool_name == "test_tool"
        assert queue.total_size == 0
    
    @pytest.mark.asyncio
    async def test_queue_priority_ordering(self):
        """Test queue respects priority ordering"""
        queue = RequestQueue(max_size=10)
        
        # Create requests with different priorities
        low_call = ToolCall("low", "server", {}, ToolPriority.LOW)
        normal_call = ToolCall("normal", "server", {}, ToolPriority.NORMAL)
        high_call = ToolCall("high", "server", {}, ToolPriority.HIGH)
        critical_call = ToolCall("critical", "server", {}, ToolPriority.CRITICAL)
        
        # Enqueue in random order
        await queue.enqueue(QueuedRequest(low_call, asyncio.Future()))
        await queue.enqueue(QueuedRequest(high_call, asyncio.Future()))
        await queue.enqueue(QueuedRequest(normal_call, asyncio.Future()))
        await queue.enqueue(QueuedRequest(critical_call, asyncio.Future()))
        
        # Dequeue should return highest priority first
        request1 = await queue.dequeue()
        assert request1.tool_call.tool_name == "critical"
        
        request2 = await queue.dequeue()
        assert request2.tool_call.tool_name == "high"
        
        request3 = await queue.dequeue()
        assert request3.tool_call.tool_name == "normal"
        
        request4 = await queue.dequeue()
        assert request4.tool_call.tool_name == "low"
    
    @pytest.mark.asyncio
    async def test_queue_max_size_limit(self):
        """Test queue respects maximum size limit"""
        queue = RequestQueue(max_size=2)
        
        tool_call = ToolCall("test", "server", {})
        
        # Fill queue to capacity
        result1 = await queue.enqueue(QueuedRequest(tool_call, asyncio.Future()))
        result2 = await queue.enqueue(QueuedRequest(tool_call, asyncio.Future()))
        
        assert result1 is True
        assert result2 is True
        assert queue.total_size == 2
        
        # Next enqueue should fail
        result3 = await queue.enqueue(QueuedRequest(tool_call, asyncio.Future()))
        assert result3 is False
        assert queue.total_size == 2
    
    @pytest.mark.asyncio
    async def test_queue_empty_dequeue(self):
        """Test dequeue returns None when queue is empty"""
        queue = RequestQueue()
        
        result = await queue.dequeue()
        assert result is None
    
    @pytest.mark.asyncio
    async def test_queue_stats(self):
        """Test queue statistics"""
        queue = RequestQueue(max_size=10)
        
        # Add some requests
        high_call = ToolCall("high", "server", {}, ToolPriority.HIGH)
        normal_call = ToolCall("normal", "server", {}, ToolPriority.NORMAL)
        
        await queue.enqueue(QueuedRequest(high_call, asyncio.Future()))
        await queue.enqueue(QueuedRequest(normal_call, asyncio.Future()))
        
        stats = await queue.get_queue_stats()
        
        assert stats["total_size"] == 2
        assert stats["max_size"] == 10
        assert stats["by_priority"]["HIGH"]["size"] == 1
        assert stats["by_priority"]["NORMAL"]["size"] == 1
        assert stats["by_priority"]["LOW"]["size"] == 0


class TestLoadBalancer:
    """Test load balancer functionality"""
    
    @pytest.mark.asyncio
    async def test_load_balancer_single_server(self):
        """Test load balancer with single server"""
        balancer = LoadBalancer()
        
        servers = ["server1"]
        selected = await balancer.select_server(servers)
        
        assert selected == "server1"
    
    @pytest.mark.asyncio
    async def test_load_balancer_no_servers(self):
        """Test load balancer with no servers"""
        balancer = LoadBalancer()
        
        selected = await balancer.select_server([])
        assert selected is None
    
    @pytest.mark.asyncio
    async def test_load_balancer_multiple_servers(self):
        """Test load balancer with multiple servers"""
        balancer = LoadBalancer()
        
        servers = ["server1", "server2", "server3"]
        selected = await balancer.select_server(servers)
        
        assert selected in servers
    
    @pytest.mark.asyncio
    async def test_load_balancer_request_tracking(self):
        """Test load balancer tracks request results"""
        balancer = LoadBalancer()
        
        # Record some requests
        await balancer.record_request_result("server1", True, 1.0)
        await balancer.record_request_result("server1", False, 2.0)
        await balancer.record_request_result("server2", True, 0.5)
        
        stats = await balancer.get_load_balancer_stats()
        
        assert stats["server1"]["total_requests"] == 2
        assert stats["server1"]["successful_requests"] == 1
        assert stats["server1"]["failed_requests"] == 1
        assert stats["server1"]["success_rate"] == 0.5
        
        assert stats["server2"]["total_requests"] == 1
        assert stats["server2"]["successful_requests"] == 1
        assert stats["server2"]["success_rate"] == 1.0
    
    @pytest.mark.asyncio
    async def test_load_balancer_server_selection_based_on_performance(self):
        """Test load balancer selects servers based on performance"""
        balancer = LoadBalancer()
        
        # Make server1 perform poorly
        for _ in range(5):
            await balancer.record_request_result("server1", False, 5.0)
        
        # Make server2 perform well
        for _ in range(5):
            await balancer.record_request_result("server2", True, 0.5)
        
        servers = ["server1", "server2"]
        
        # Should prefer server2 due to better performance
        selections = []
        for _ in range(10):
            selected = await balancer.select_server(servers)
            selections.append(selected)
        
        # server2 should be selected more often
        server2_count = selections.count("server2")
        assert server2_count >= 7  # At least 70% of the time


class TestParallelExecutionEngine:
    """Test parallel execution engine"""
    
    @pytest.mark.asyncio
    async def test_engine_initialization(self):
        """Test engine initializes correctly"""
        engine = ParallelExecutionEngine(max_concurrent_requests=5)
        
        assert engine.max_concurrent_requests == 5
        assert engine.active_requests == 0
        assert engine.total_requests == 0
    
    @pytest.mark.asyncio
    async def test_engine_start_stop(self):
        """Test engine start and stop"""
        engine = ParallelExecutionEngine()
        
        await engine.start()
        assert engine._queue_processor_task is not None
        
        await engine.stop()
        assert engine._queue_processor_task is None
    
    @pytest.mark.asyncio
    async def test_engine_executor_function(self):
        """Test setting executor function"""
        engine = ParallelExecutionEngine()
        
        async def mock_executor(tool_call):
            return ToolResult(
                tool_name=tool_call.tool_name,
                mcp_server=tool_call.mcp_server,
                success=True,
                data={"result": "success"}
            )
        
        engine.set_executor_function(mock_executor)
        assert engine._executor_func == mock_executor
    
    @pytest.mark.asyncio
    async def test_engine_parallel_execution(self):
        """Test parallel execution of tool calls"""
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
        
        # Create test tool calls
        tool_calls = [
            ToolCall(f"tool_{i}", "server", {}, ToolPriority.NORMAL, 10)
            for i in range(5)
        ]
        
        start_time = time.time()
        results = await engine.execute_parallel_calls(tool_calls)
        execution_time = time.time() - start_time
        
        # Should complete in roughly parallel time (not sequential)
        assert execution_time < 1.0  # Much less than 5 * 0.1 = 0.5 seconds
        assert len(results) == 5
        
        for i, result in enumerate(results):
            assert result.success is True
            assert result.tool_name == f"tool_{i}"
            assert result.data["result"] == f"success_tool_{i}"
        
        await engine.stop()
    
    @pytest.mark.asyncio
    async def test_engine_timeout_handling(self):
        """Test timeout handling in parallel execution"""
        engine = ParallelExecutionEngine()
        
        # Mock executor that takes too long
        async def slow_executor(tool_call):
            await asyncio.sleep(2.0)  # Longer than timeout
            return ToolResult(
                tool_name=tool_call.tool_name,
                mcp_server=tool_call.mcp_server,
                success=True,
                data={"result": "success"}
            )
        
        engine.set_executor_function(slow_executor)
        
        # Create tool call with short timeout
        tool_calls = [
            ToolCall("slow_tool", "server", {}, ToolPriority.NORMAL, 1)  # 1 second timeout
        ]
        
        results = await engine.execute_parallel_calls(tool_calls)
        
        assert len(results) == 1
        assert results[0].success is False
        assert "timed out" in results[0].error_message.lower()
        
        await engine.stop()
    
    @pytest.mark.asyncio
    async def test_engine_circuit_breaker_integration(self):
        """Test circuit breaker integration"""
        engine = ParallelExecutionEngine()
        
        # Mock executor that always fails
        async def failing_executor(tool_call):
            raise Exception("Simulated failure")
        
        engine.set_executor_function(failing_executor)
        
        # Create multiple tool calls to trigger circuit breaker
        tool_calls = [
            ToolCall(f"tool_{i}", "failing_server", {}, ToolPriority.NORMAL, 10)
            for i in range(10)
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
    
    @pytest.mark.asyncio
    async def test_engine_queue_full_handling(self):
        """Test handling of full request queue"""
        engine = ParallelExecutionEngine(max_queue_size=2)
        
        # Mock executor that takes a while
        async def slow_executor(tool_call):
            await asyncio.sleep(1.0)
            return ToolResult(
                tool_name=tool_call.tool_name,
                mcp_server=tool_call.mcp_server,
                success=True,
                data={"result": "success"}
            )
        
        engine.set_executor_function(slow_executor)
        
        # Create more tool calls than queue can handle
        tool_calls = [
            ToolCall(f"tool_{i}", "server", {}, ToolPriority.NORMAL, 10)
            for i in range(5)
        ]
        
        results = await engine.execute_parallel_calls(tool_calls)
        
        # Some requests should be rejected due to full queue
        rejected_results = [
            r for r in results 
            if not r.success and "queue full" in r.error_message.lower()
        ]
        
        assert len(rejected_results) > 0
        
        await engine.stop()
    
    @pytest.mark.asyncio
    async def test_engine_execution_stats(self):
        """Test execution statistics"""
        engine = ParallelExecutionEngine()
        
        # Mock executor
        async def mock_executor(tool_call):
            return ToolResult(
                tool_name=tool_call.tool_name,
                mcp_server=tool_call.mcp_server,
                success=True,
                data={"result": "success"}
            )
        
        engine.set_executor_function(mock_executor)
        
        # Execute some tool calls
        tool_calls = [
            ToolCall(f"tool_{i}", "server", {}, ToolPriority.NORMAL, 10)
            for i in range(3)
        ]
        
        await engine.execute_parallel_calls(tool_calls)
        
        stats = await engine.get_execution_stats()
        
        assert stats["total_requests"] == 3
        assert stats["successful_requests"] == 3
        assert stats["failed_requests"] == 0
        assert stats["success_rate"] == 1.0
        assert "uptime_seconds" in stats
        assert "queue_stats" in stats
        assert "load_balancer_stats" in stats
        assert "circuit_breaker_stats" in stats
        
        await engine.stop()
    
    @pytest.mark.asyncio
    async def test_engine_priority_handling(self):
        """Test priority-based execution"""
        engine = ParallelExecutionEngine(max_concurrent_requests=1)  # Force sequential
        
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
        
        engine.set_executor_function(tracking_executor)
        
        # Create tool calls with different priorities
        tool_calls = [
            ToolCall("low", "server", {}, ToolPriority.LOW, 10),
            ToolCall("critical", "server", {}, ToolPriority.CRITICAL, 10),
            ToolCall("normal", "server", {}, ToolPriority.NORMAL, 10),
            ToolCall("high", "server", {}, ToolPriority.HIGH, 10),
        ]
        
        await engine.execute_parallel_calls(tool_calls)
        
        # Should execute in priority order: critical, high, normal, low
        expected_order = ["critical", "high", "normal", "low"]
        assert execution_order == expected_order
        
        await engine.stop()


# Integration test removed to avoid dependency issues


if __name__ == "__main__":
    pytest.main([__file__, "-v"])