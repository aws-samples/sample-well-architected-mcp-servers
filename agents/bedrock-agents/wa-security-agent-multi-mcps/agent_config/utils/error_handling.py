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
Error handling utilities for Enhanced Security Agent
Provides comprehensive error handling and recovery mechanisms
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, List
from enum import Enum
from dataclasses import dataclass
import time
import random

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Types of errors that can occur"""
    CONNECTION_ERROR = "connection_error"
    AUTHENTICATION_ERROR = "authentication_error"
    TIMEOUT_ERROR = "timeout_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    PERMISSION_ERROR = "permission_error"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN_ERROR = "unknown_error"


class ErrorSeverity(Enum):
    """Severity levels for errors"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorResponse:
    """Standardized error response"""
    error_type: ErrorType
    severity: ErrorSeverity
    message: str
    details: Dict[str, Any]
    recovery_suggestions: List[str]
    retry_after: Optional[int] = None
    fallback_available: bool = False


class CircuitBreaker:
    """Circuit breaker pattern implementation for MCP servers"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    def can_execute(self) -> bool:
        """Check if execution is allowed"""
        if self.state == "closed":
            return True
        elif self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                return True
            return False
        else:  # half-open
            return True
    
    def record_success(self):
        """Record successful execution"""
        self.failure_count = 0
        self.state = "closed"
    
    def record_failure(self):
        """Record failed execution"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"


class RetryManager:
    """Manages retry logic with exponential backoff"""
    
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    async def execute_with_retry(self, 
                               func: Callable, 
                               *args, 
                               retryable_errors: List[Exception] = None,
                               **kwargs) -> Any:
        """Execute function with retry logic"""
        if retryable_errors is None:
            retryable_errors = [ConnectionError, TimeoutError, asyncio.TimeoutError]
        
        last_exception = None
        
        for attempt in range(self.max_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                # Check if error is retryable
                if not any(isinstance(e, error_type) for error_type in retryable_errors):
                    raise e
                
                if attempt < self.max_attempts - 1:
                    delay = min(
                        self.base_delay * (2 ** attempt) + random.uniform(0, 1),
                        self.max_delay
                    )
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {self.max_attempts} attempts failed")
        
        raise last_exception


class ErrorHandler:
    """Comprehensive error handler for Enhanced Security Agent"""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.retry_manager = RetryManager()
    
    def get_circuit_breaker(self, mcp_server: str) -> CircuitBreaker:
        """Get or create circuit breaker for MCP server"""
        if mcp_server not in self.circuit_breakers:
            self.circuit_breakers[mcp_server] = CircuitBreaker()
        return self.circuit_breakers[mcp_server]
    
    def handle_mcp_connection_error(self, server_name: str, error: Exception) -> ErrorResponse:
        """Handle MCP connection errors"""
        circuit_breaker = self.get_circuit_breaker(server_name)
        circuit_breaker.record_failure()
        
        return ErrorResponse(
            error_type=ErrorType.CONNECTION_ERROR,
            severity=ErrorSeverity.HIGH,
            message=f"Failed to connect to {server_name} MCP server",
            details={
                "server": server_name,
                "error": str(error),
                "circuit_breaker_state": circuit_breaker.state
            },
            recovery_suggestions=[
                "Check network connectivity",
                "Verify MCP server is running",
                "Check firewall and security group settings",
                "Validate server endpoint configuration"
            ],
            retry_after=60,
            fallback_available=True
        )
    
    def handle_authentication_error(self, server_name: str, error: Exception) -> ErrorResponse:
        """Handle authentication errors"""
        return ErrorResponse(
            error_type=ErrorType.AUTHENTICATION_ERROR,
            severity=ErrorSeverity.CRITICAL,
            message=f"Authentication failed for {server_name} MCP server",
            details={
                "server": server_name,
                "error": str(error)
            },
            recovery_suggestions=[
                "Check authentication credentials",
                "Verify bearer token is valid and not expired",
                "Check IAM permissions for the service role",
                "Refresh authentication tokens"
            ],
            fallback_available=False
        )
    
    def handle_rate_limit_error(self, server_name: str, error: Exception) -> ErrorResponse:
        """Handle rate limit errors"""
        return ErrorResponse(
            error_type=ErrorType.RATE_LIMIT_ERROR,
            severity=ErrorSeverity.MEDIUM,
            message=f"Rate limit exceeded for {server_name} MCP server",
            details={
                "server": server_name,
                "error": str(error)
            },
            recovery_suggestions=[
                "Reduce request frequency",
                "Implement request queuing",
                "Use exponential backoff",
                "Consider request batching"
            ],
            retry_after=300,
            fallback_available=True
        )
    
    def handle_timeout_error(self, server_name: str, error: Exception) -> ErrorResponse:
        """Handle timeout errors"""
        return ErrorResponse(
            error_type=ErrorType.TIMEOUT_ERROR,
            severity=ErrorSeverity.MEDIUM,
            message=f"Request timeout for {server_name} MCP server",
            details={
                "server": server_name,
                "error": str(error)
            },
            recovery_suggestions=[
                "Increase timeout values",
                "Check server performance",
                "Reduce request complexity",
                "Implement request streaming"
            ],
            retry_after=30,
            fallback_available=True
        )
    
    def handle_permission_error(self, server_name: str, error: Exception) -> ErrorResponse:
        """Handle permission errors"""
        return ErrorResponse(
            error_type=ErrorType.PERMISSION_ERROR,
            severity=ErrorSeverity.HIGH,
            message=f"Insufficient permissions for {server_name} MCP server",
            details={
                "server": server_name,
                "error": str(error)
            },
            recovery_suggestions=[
                "Check IAM role permissions",
                "Verify resource access policies",
                "Review service-specific permissions",
                "Contact administrator for access"
            ],
            fallback_available=False
        )
    
    def create_fallback_response(self, server_name: str, original_query: str) -> str:
        """Create fallback response when MCP server is unavailable"""
        return f"""⚠️ **{server_name.title()} MCP Server Unavailable**

The {server_name} MCP server is currently unavailable, but I can still provide general guidance.

**Your Query**: {original_query}

**General Security Recommendations**:
- Follow AWS Well-Architected Security Pillar principles
- Enable AWS security services (GuardDuty, Security Hub, Inspector)
- Implement defense in depth with multiple security layers
- Use least privilege access principles
- Enable comprehensive logging and monitoring

**Next Steps**:
1. Check the {server_name} MCP server status
2. Review connection and authentication settings
3. Try your query again once the service is restored

For immediate assistance, consult the AWS Security documentation or contact your security team."""
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of error states across all MCP servers"""
        return {
            "circuit_breakers": {
                server: {
                    "state": cb.state,
                    "failure_count": cb.failure_count,
                    "last_failure": cb.last_failure_time
                }
                for server, cb in self.circuit_breakers.items()
            },
            "total_servers": len(self.circuit_breakers),
            "healthy_servers": sum(1 for cb in self.circuit_breakers.values() if cb.state == "closed"),
            "failed_servers": sum(1 for cb in self.circuit_breakers.values() if cb.state == "open")
        }
    
    async def health_check_recovery(self, server_name: str, health_check_func: Callable) -> bool:
        """Attempt to recover a failed server through health checks"""
        try:
            circuit_breaker = self.get_circuit_breaker(server_name)
            
            if circuit_breaker.state == "open":
                # Try health check
                result = await health_check_func()
                if result:
                    circuit_breaker.record_success()
                    logger.info(f"Successfully recovered {server_name} MCP server")
                    return True
                else:
                    circuit_breaker.record_failure()
                    return False
            
            return circuit_breaker.state == "closed"
            
        except Exception as e:
            logger.error(f"Health check failed for {server_name}: {e}")
            return False