"""
Request logging middleware for both BedrockAgent and AgentCore versions.
"""

import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""
    
    def __init__(self, app, version: str, log_body: bool = False, log_headers: bool = False):
        """
        Initialize request logging middleware.
        
        Args:
            app: FastAPI application instance
            version: Backend version ("bedrockagent" or "agentcore")
            log_body: Whether to log request/response bodies
            log_headers: Whether to log request/response headers
        """
        super().__init__(app)
        self.version = version
        self.log_body = log_body
        self.log_headers = log_headers
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request and log details.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response from next middleware/endpoint
        """
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Log request
        await self._log_request(request, request_id)
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response
            await self._log_response(request, response, request_id, duration_ms)
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Backend-Version"] = self.version
            
            return response
            
        except Exception as e:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log error
            await self._log_error(request, e, request_id, duration_ms)
            
            # Re-raise exception
            raise
    
    async def _log_request(self, request: Request, request_id: str):
        """Log incoming request details."""
        log_data = {
            "event": "request_start",
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent"),
            "backend_version": self.version,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add headers if enabled
        if self.log_headers:
            log_data["headers"] = dict(request.headers)
        
        # Add body if enabled and present
        if self.log_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    log_data["body_size"] = len(body)
                    # Only log first 1000 characters to avoid huge logs
                    log_data["body_preview"] = body.decode('utf-8')[:1000]
            except Exception as e:
                log_data["body_error"] = str(e)
        
        logger.info("HTTP request received", extra=log_data)
    
    async def _log_response(
        self, 
        request: Request, 
        response: Response, 
        request_id: str, 
        duration_ms: float
    ):
        """Log response details."""
        log_data = {
            "event": "request_complete",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "backend_version": self.version,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add response headers if enabled
        if self.log_headers:
            log_data["response_headers"] = dict(response.headers)
        
        # Determine log level based on status code
        if response.status_code >= 500:
            log_level = logging.ERROR
        elif response.status_code >= 400:
            log_level = logging.WARNING
        else:
            log_level = logging.INFO
        
        logger.log(log_level, "HTTP request completed", extra=log_data)
    
    async def _log_error(
        self, 
        request: Request, 
        error: Exception, 
        request_id: str, 
        duration_ms: float
    ):
        """Log request error details."""
        log_data = {
            "event": "request_error",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "duration_ms": round(duration_ms, 2),
            "backend_version": self.version,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.error("HTTP request failed", extra=log_data, exc_info=True)
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        # Check for forwarded headers first (for load balancers/proxies)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fall back to direct client IP
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"


class PerformanceLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging performance metrics."""
    
    def __init__(self, app, version: str, slow_request_threshold_ms: float = 1000):
        """
        Initialize performance logging middleware.
        
        Args:
            app: FastAPI application instance
            version: Backend version
            slow_request_threshold_ms: Threshold for logging slow requests
        """
        super().__init__(app)
        self.version = version
        self.slow_request_threshold_ms = slow_request_threshold_ms
    
    async def dispatch(self, request: Request, call_next):
        """Process request and log performance metrics."""
        start_time = time.time()
        
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            
            # Log performance metrics
            self._log_performance_metric(request, response.status_code, duration_ms, True)
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # Log performance metrics for failed requests
            self._log_performance_metric(request, 500, duration_ms, False)
            
            raise
    
    def _log_performance_metric(
        self, 
        request: Request, 
        status_code: int, 
        duration_ms: float, 
        success: bool
    ):
        """Log performance metric."""
        log_data = {
            "event": "performance_metric",
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "success": success,
            "backend_version": self.version,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add request ID if available
        if hasattr(request.state, 'request_id'):
            log_data["request_id"] = request.state.request_id
        
        # Log as warning if request is slow
        if duration_ms > self.slow_request_threshold_ms:
            log_data["slow_request"] = True
            logger.warning("Slow request detected", extra=log_data)
        else:
            logger.info("Performance metric", extra=log_data)


def setup_request_logging(
    app, 
    version: str, 
    log_body: bool = False, 
    log_headers: bool = False,
    enable_performance_logging: bool = True,
    slow_request_threshold_ms: float = 1000
):
    """
    Set up request logging middleware for FastAPI application.
    
    Args:
        app: FastAPI application instance
        version: Backend version
        log_body: Whether to log request/response bodies
        log_headers: Whether to log request/response headers
        enable_performance_logging: Whether to enable performance logging
        slow_request_threshold_ms: Threshold for slow request logging
    """
    # Add request logging middleware
    app.add_middleware(
        RequestLoggingMiddleware,
        version=version,
        log_body=log_body,
        log_headers=log_headers
    )
    
    # Add performance logging middleware if enabled
    if enable_performance_logging:
        app.add_middleware(
            PerformanceLoggingMiddleware,
            version=version,
            slow_request_threshold_ms=slow_request_threshold_ms
        )


def get_request_id(request: Request) -> Optional[str]:
    """
    Get request ID from request state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Request ID string or None
    """
    return getattr(request.state, 'request_id', None)


class RequestContext:
    """Context manager for request-scoped logging context."""
    
    def __init__(self, request: Request):
        """
        Initialize request context.
        
        Args:
            request: FastAPI request object
        """
        self.request = request
        self.request_id = get_request_id(request)
        self.logger = logging.getLogger(__name__)
    
    def __enter__(self):
        """Enter context and return logger with request context."""
        context = {
            "request_id": self.request_id,
            "method": self.request.method,
            "path": self.request.url.path
        }
        return logging.LoggerAdapter(self.logger, context)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        pass