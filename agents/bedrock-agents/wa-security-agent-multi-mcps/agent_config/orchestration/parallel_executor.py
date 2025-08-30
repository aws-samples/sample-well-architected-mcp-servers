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
Parallel Tool Execution System
Implements parallel execution engine for multiple MCP server calls with
request queuing, load balancing, timeout handling, and circuit breaker patterns
"""

import asyncio
import time
import random
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from datetime import datetime, timedelta

from agent_config.interfaces import ToolCall, ToolResult, ToolPriority
from agent_config.utils.logging_utils import get_logger

logger = get_logger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""

    failure_threshold: int = 5  # Number of failures before opening
    recovery_timeout: int = 60  # Seconds before trying half-open
    success_threshold: int = 3  # Successes needed to close from half-open
    timeout_threshold: int = 30  # Timeout in seconds to consider failure


@dataclass
class LoadBalancerStats:
    """Statistics for load balancer"""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    last_request_time: Optional[datetime] = None


@dataclass
class QueuedRequest:
    """Represents a queued tool call request"""

    tool_call: ToolCall
    future: asyncio.Future
    queued_at: datetime = field(default_factory=datetime.now)
    priority: ToolPriority = ToolPriority.NORMAL


class CircuitBreaker:
    """Circuit breaker implementation for MCP server resilience"""

    def __init__(self, server_name: str, config: CircuitBreakerConfig):
        self.server_name = server_name
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None

    def can_execute(self) -> bool:
        """Check if request can be executed based on circuit breaker state"""
        now = datetime.now()

        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time and now - self.last_failure_time > timedelta(
                seconds=self.config.recovery_timeout
            ):
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                logger.info(
                    f"Circuit breaker for {self.server_name} moved to HALF_OPEN"
                )
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
                logger.info(f"Circuit breaker for {self.server_name} moved to CLOSED")
        elif self.state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed request"""
        self.last_failure_time = datetime.now()
        self.failure_count += 1

        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                logger.warning(
                    f"Circuit breaker for {self.server_name} moved to OPEN after {self.failure_count} failures"
                )
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            logger.warning(f"Circuit breaker for {self.server_name} moved back to OPEN")

    def get_state_info(self) -> Dict[str, Any]:
        """Get current circuit breaker state information"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat()
            if self.last_failure_time
            else None,
            "last_success_time": self.last_success_time.isoformat()
            if self.last_success_time
            else None,
        }


class RequestQueue:
    """Priority-based request queue with load balancing"""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.queues: Dict[ToolPriority, deque] = {
            priority: deque() for priority in ToolPriority
        }
        self.total_size = 0
        self._lock = asyncio.Lock()

    async def enqueue(self, request: QueuedRequest) -> bool:
        """Add request to appropriate priority queue"""
        async with self._lock:
            if self.total_size >= self.max_size:
                logger.warning(
                    f"Request queue full ({self.max_size}), rejecting request"
                )
                return False

            self.queues[request.priority].append(request)
            self.total_size += 1
            logger.debug(
                f"Enqueued request with priority {request.priority.name}, queue size: {self.total_size}"
            )
            return True

    async def dequeue(self) -> Optional[QueuedRequest]:
        """Dequeue highest priority request"""
        async with self._lock:
            # Check queues in priority order (highest first)
            for priority in reversed(list(ToolPriority)):
                if self.queues[priority]:
                    request = self.queues[priority].popleft()
                    self.total_size -= 1
                    return request
            return None

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        async with self._lock:
            stats = {
                "total_size": self.total_size,
                "max_size": self.max_size,
                "by_priority": {},
            }

            for priority in ToolPriority:
                queue_size = len(self.queues[priority])
                oldest_request_age = None

                if queue_size > 0:
                    oldest_request = self.queues[priority][0]
                    oldest_request_age = (
                        datetime.now() - oldest_request.queued_at
                    ).total_seconds()

                stats["by_priority"][priority.name] = {
                    "size": queue_size,
                    "oldest_request_age_seconds": oldest_request_age,
                }

            return stats


class LoadBalancer:
    """Load balancer for distributing requests across MCP server instances"""

    def __init__(self):
        self.server_stats: Dict[str, LoadBalancerStats] = defaultdict(LoadBalancerStats)
        self.server_weights: Dict[str, float] = defaultdict(lambda: 1.0)
        self._lock = asyncio.Lock()

    async def select_server(self, available_servers: List[str]) -> Optional[str]:
        """Select best server based on load balancing algorithm"""
        if not available_servers:
            return None

        if len(available_servers) == 1:
            return available_servers[0]

        async with self._lock:
            # Weighted round-robin based on success rate and response time
            best_server = None
            best_score = float("-inf")

            for server in available_servers:
                stats = self.server_stats[server]
                weight = self.server_weights[server]

                # Calculate score based on success rate and response time
                if stats.total_requests > 0:
                    success_rate = stats.successful_requests / stats.total_requests
                    # Invert response time (lower is better)
                    response_time_score = 1.0 / (stats.average_response_time + 0.1)
                    score = (success_rate * 0.7 + response_time_score * 0.3) * weight
                else:
                    # New server gets neutral score
                    score = 0.5 * weight

                if score > best_score:
                    best_score = score
                    best_server = server

            return best_server

    async def record_request_result(
        self, server: str, success: bool, response_time: float
    ) -> None:
        """Record the result of a request for load balancing decisions"""
        async with self._lock:
            stats = self.server_stats[server]
            stats.total_requests += 1
            stats.last_request_time = datetime.now()

            if success:
                stats.successful_requests += 1
            else:
                stats.failed_requests += 1

            # Update average response time with exponential moving average
            if stats.average_response_time == 0:
                stats.average_response_time = response_time
            else:
                alpha = 0.1  # Smoothing factor
                stats.average_response_time = (
                    alpha * response_time + (1 - alpha) * stats.average_response_time
                )

    async def get_load_balancer_stats(self) -> Dict[str, Any]:
        """Get load balancer statistics"""
        async with self._lock:
            return {
                server: {
                    "total_requests": stats.total_requests,
                    "successful_requests": stats.successful_requests,
                    "failed_requests": stats.failed_requests,
                    "success_rate": (
                        stats.successful_requests / stats.total_requests
                        if stats.total_requests > 0
                        else 0
                    ),
                    "average_response_time": stats.average_response_time,
                    "weight": self.server_weights[server],
                    "last_request_time": stats.last_request_time.isoformat()
                    if stats.last_request_time
                    else None,
                }
                for server, stats in self.server_stats.items()
            }


class ParallelExecutionEngine:
    """
    Parallel execution engine for multiple MCP server calls with advanced features:
    - Request queuing with priority handling
    - Load balancing across server instances
    - Circuit breaker pattern for resilience
    - Timeout handling with exponential backoff
    - Concurrent execution limits
    """

    def __init__(
        self,
        max_concurrent_requests: int = 10,
        max_queue_size: int = 1000,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
    ):
        self.max_concurrent_requests = max_concurrent_requests
        self.request_queue = RequestQueue(max_queue_size)
        self.load_balancer = LoadBalancer()

        # Circuit breakers per MCP server
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()

        # Execution control
        self.active_requests = 0
        self.request_semaphore = asyncio.Semaphore(max_concurrent_requests)
        self._execution_lock = asyncio.Lock()

        # Statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.start_time = datetime.now()

        # Background task for processing queue
        self._queue_processor_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

        # Executor function for actual tool execution
        self._executor_func: Optional[Callable[[ToolCall], Any]] = None

        logger.info(
            f"Parallel execution engine initialized with max_concurrent={max_concurrent_requests}"
        )

    def set_executor_function(self, executor_func: Callable[[ToolCall], Any]) -> None:
        """Set the function used to execute tool calls"""
        self._executor_func = executor_func

    async def start(self) -> None:
        """Start the parallel execution engine"""
        if self._queue_processor_task is None:
            self._queue_processor_task = asyncio.create_task(self._process_queue())
            logger.info("Parallel execution engine started")

    async def stop(self) -> None:
        """Stop the parallel execution engine"""
        self._shutdown_event.set()

        if self._queue_processor_task:
            try:
                await asyncio.wait_for(self._queue_processor_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._queue_processor_task.cancel()
                logger.warning("Queue processor task cancelled due to timeout")

            self._queue_processor_task = None

        logger.info("Parallel execution engine stopped")

    def _get_circuit_breaker(self, server_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for server"""
        if server_name not in self.circuit_breakers:
            self.circuit_breakers[server_name] = CircuitBreaker(
                server_name, self.circuit_breaker_config
            )
        return self.circuit_breakers[server_name]

    async def execute_parallel_calls(
        self,
        tool_calls: List[ToolCall],
        executor_func: Optional[Callable[[ToolCall], asyncio.Task]] = None,
    ) -> List[ToolResult]:
        """
        Execute multiple tool calls in parallel with advanced features

        Args:
            tool_calls: List of tool calls to execute
            executor_func: Optional function that creates execution task for a tool call

        Returns:
            List of tool results
        """
        if not tool_calls:
            return []

        logger.info(f"Executing {len(tool_calls)} tool calls in parallel")

        # Start engine if not already started
        await self.start()

        # Set executor function if provided
        if executor_func:
            self.set_executor_function(executor_func)

        # Create futures for all requests
        request_futures = []

        for tool_call in tool_calls:
            future = asyncio.Future()
            request = QueuedRequest(
                tool_call=tool_call, future=future, priority=tool_call.priority
            )

            # Try to enqueue request
            if await self.request_queue.enqueue(request):
                request_futures.append(future)
            else:
                # Queue full, create immediate failure result
                error_result = ToolResult(
                    tool_name=tool_call.tool_name,
                    mcp_server=tool_call.mcp_server,
                    success=False,
                    data=None,
                    error_message="Request queue full, request rejected",
                    execution_time=0.0,
                )
                future.set_result(error_result)
                request_futures.append(future)

        # Wait for all requests to complete
        try:
            results = await asyncio.gather(*request_futures, return_exceptions=True)

            # Process results and handle exceptions
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    error_result = ToolResult(
                        tool_name=tool_calls[i].tool_name,
                        mcp_server=tool_calls[i].mcp_server,
                        success=False,
                        data=None,
                        error_message=f"Execution exception: {str(result)}",
                        execution_time=0.0,
                    )
                    processed_results.append(error_result)
                else:
                    processed_results.append(result)

            logger.info(
                f"Completed parallel execution: {len(processed_results)} results"
            )
            return processed_results

        except Exception as e:
            logger.error(f"Error in parallel execution: {e}")
            # Create error results for all calls
            error_results = []
            for tool_call in tool_calls:
                error_result = ToolResult(
                    tool_name=tool_call.tool_name,
                    mcp_server=tool_call.mcp_server,
                    success=False,
                    data=None,
                    error_message=f"Parallel execution failed: {str(e)}",
                    execution_time=0.0,
                )
                error_results.append(error_result)
            return error_results

    async def _process_queue(self) -> None:
        """Background task to process the request queue"""
        logger.info("Queue processor started")

        while not self._shutdown_event.is_set():
            try:
                # Get next request from queue
                request = await self.request_queue.dequeue()

                if request is None:
                    # No requests, wait a bit
                    await asyncio.sleep(0.1)
                    continue

                # Check if request has timed out while in queue
                queue_time = (datetime.now() - request.queued_at).total_seconds()
                if queue_time > request.tool_call.timeout:
                    logger.warning(
                        f"Request {request.tool_call.tool_name} timed out in queue after {queue_time}s"
                    )
                    timeout_result = ToolResult(
                        tool_name=request.tool_call.tool_name,
                        mcp_server=request.tool_call.mcp_server,
                        success=False,
                        data=None,
                        error_message=f"Request timed out in queue after {queue_time:.1f} seconds",
                        execution_time=queue_time,
                    )
                    request.future.set_result(timeout_result)
                    continue

                # Check circuit breaker
                circuit_breaker = self._get_circuit_breaker(
                    request.tool_call.mcp_server
                )
                if not circuit_breaker.can_execute():
                    logger.warning(
                        f"Circuit breaker open for {request.tool_call.mcp_server}, rejecting request"
                    )
                    circuit_breaker_result = ToolResult(
                        tool_name=request.tool_call.tool_name,
                        mcp_server=request.tool_call.mcp_server,
                        success=False,
                        data=None,
                        error_message=f"Circuit breaker open for {request.tool_call.mcp_server}",
                        execution_time=0.0,
                    )
                    request.future.set_result(circuit_breaker_result)
                    continue

                # Execute request with concurrency control
                asyncio.create_task(self._execute_request(request))

            except Exception as e:
                logger.error(f"Error in queue processor: {e}")
                await asyncio.sleep(1.0)  # Back off on error

        logger.info("Queue processor stopped")

    async def _execute_request(self, request: QueuedRequest) -> None:
        """Execute a single request with all safety mechanisms"""
        async with self.request_semaphore:
            start_time = time.time()
            circuit_breaker = self._get_circuit_breaker(request.tool_call.mcp_server)

            try:
                async with self._execution_lock:
                    self.active_requests += 1
                    self.total_requests += 1

                # Apply timeout with exponential backoff for retries
                remaining_timeout = request.tool_call.timeout - (
                    time.time() - start_time
                )

                if remaining_timeout <= 0:
                    raise asyncio.TimeoutError("No time remaining for execution")

                # Execute the actual tool call
                if self._executor_func:
                    # Use the provided executor function
                    result = await asyncio.wait_for(
                        self._executor_func(request.tool_call),
                        timeout=remaining_timeout,
                    )
                else:
                    # Fallback to simulation for testing
                    result = await self._simulate_tool_execution(
                        request.tool_call, remaining_timeout
                    )

                # Record success
                execution_time = time.time() - start_time
                result.execution_time = execution_time

                circuit_breaker.record_success()
                await self.load_balancer.record_request_result(
                    request.tool_call.mcp_server, True, execution_time
                )

                async with self._execution_lock:
                    self.successful_requests += 1

                request.future.set_result(result)

            except asyncio.TimeoutError:
                execution_time = time.time() - start_time
                logger.warning(
                    f"Tool call {request.tool_call.tool_name} timed out after {execution_time:.1f}s"
                )

                circuit_breaker.record_failure()
                await self.load_balancer.record_request_result(
                    request.tool_call.mcp_server, False, execution_time
                )

                timeout_result = ToolResult(
                    tool_name=request.tool_call.tool_name,
                    mcp_server=request.tool_call.mcp_server,
                    success=False,
                    data=None,
                    error_message=f"Tool call timed out after {execution_time:.1f} seconds",
                    execution_time=execution_time,
                )

                async with self._execution_lock:
                    self.failed_requests += 1

                request.future.set_result(timeout_result)

            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(
                    f"Error executing tool call {request.tool_call.tool_name}: {e}"
                )

                circuit_breaker.record_failure()
                await self.load_balancer.record_request_result(
                    request.tool_call.mcp_server, False, execution_time
                )

                error_result = ToolResult(
                    tool_name=request.tool_call.tool_name,
                    mcp_server=request.tool_call.mcp_server,
                    success=False,
                    data=None,
                    error_message=str(e),
                    execution_time=execution_time,
                )

                async with self._execution_lock:
                    self.failed_requests += 1

                request.future.set_result(error_result)

            finally:
                async with self._execution_lock:
                    self.active_requests -= 1

    async def _simulate_tool_execution(
        self, tool_call: ToolCall, timeout: float
    ) -> ToolResult:
        """
        Simulate tool execution - this would be replaced with actual MCP connector calls
        """
        # Simulate variable execution time
        execution_time = random.uniform(0.1, 2.0)
        await asyncio.sleep(min(execution_time, timeout))

        # Simulate occasional failures
        if random.random() < 0.1:  # 10% failure rate
            raise Exception(f"Simulated failure for {tool_call.tool_name}")

        return ToolResult(
            tool_name=tool_call.tool_name,
            mcp_server=tool_call.mcp_server,
            success=True,
            data={"simulated": True, "result": f"Success for {tool_call.tool_name}"},
            error_message=None,
        )

    async def get_execution_stats(self) -> Dict[str, Any]:
        """Get comprehensive execution statistics"""
        uptime = (datetime.now() - self.start_time).total_seconds()

        queue_stats = await self.request_queue.get_queue_stats()
        load_balancer_stats = await self.load_balancer.get_load_balancer_stats()

        circuit_breaker_stats = {
            server: breaker.get_state_info()
            for server, breaker in self.circuit_breakers.items()
        }

        return {
            "uptime_seconds": uptime,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                self.successful_requests / self.total_requests
                if self.total_requests > 0
                else 0
            ),
            "active_requests": self.active_requests,
            "max_concurrent_requests": self.max_concurrent_requests,
            "queue_stats": queue_stats,
            "load_balancer_stats": load_balancer_stats,
            "circuit_breaker_stats": circuit_breaker_stats,
        }
