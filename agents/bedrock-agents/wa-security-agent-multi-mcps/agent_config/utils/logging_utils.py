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
Logging utilities for Enhanced Security Agent
Provides structured logging and monitoring capabilities
"""

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class MCPInteraction:
    """Represents an MCP server interaction for logging"""

    timestamp: str
    mcp_server: str
    tool_name: str
    arguments: Dict[str, Any]
    success: bool
    execution_time: float
    response_size: int
    error_message: Optional[str] = None


class StructuredLogger:
    """Structured logger for Enhanced Security Agent"""

    def __init__(self, name: str = "enhanced_security_agent"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

        # Create formatter for structured logging
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Add console handler if not already present
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

    def log_mcp_interaction(self, interaction: MCPInteraction):
        """Log MCP server interaction"""
        log_data = {"event_type": "mcp_interaction", "interaction": asdict(interaction)}

        if interaction.success:
            self.logger.info(f"MCP interaction successful: {json.dumps(log_data)}")
        else:
            self.logger.error(f"MCP interaction failed: {json.dumps(log_data)}")

    def log_agent_query(self, user_query: str, session_id: Optional[str] = None):
        """Log user query to agent"""
        log_data = {
            "event_type": "agent_query",
            "timestamp": datetime.utcnow().isoformat(),
            "user_query": user_query[:200] + "..."
            if len(user_query) > 200
            else user_query,
            "session_id": session_id,
        }
        self.logger.info(f"Agent query received: {json.dumps(log_data)}")

    def log_response_generation(
        self,
        response_length: int,
        processing_time: float,
        mcp_servers_used: list,
        session_id: Optional[str] = None,
    ):
        """Log response generation metrics"""
        log_data = {
            "event_type": "response_generation",
            "timestamp": datetime.utcnow().isoformat(),
            "response_length": response_length,
            "processing_time": processing_time,
            "mcp_servers_used": mcp_servers_used,
            "session_id": session_id,
        }
        self.logger.info(f"Response generated: {json.dumps(log_data)}")

    def log_health_check(self, mcp_server: str, status: bool, response_time: float):
        """Log health check results"""
        log_data = {
            "event_type": "health_check",
            "timestamp": datetime.utcnow().isoformat(),
            "mcp_server": mcp_server,
            "status": "healthy" if status else "unhealthy",
            "response_time": response_time,
        }

        if status:
            self.logger.info(f"Health check passed: {json.dumps(log_data)}")
        else:
            self.logger.warning(f"Health check failed: {json.dumps(log_data)}")

    def log_error(self, error_type: str, error_message: str, context: Dict[str, Any]):
        """Log error with context"""
        log_data = {
            "event_type": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error_type": error_type,
            "error_message": error_message,
            "context": context,
        }
        self.logger.error(f"Error occurred: {json.dumps(log_data)}")

    def log_performance_metrics(self, metrics: Dict[str, Any]):
        """Log performance metrics"""
        log_data = {
            "event_type": "performance_metrics",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": metrics,
        }
        self.logger.info(f"Performance metrics: {json.dumps(log_data)}")


class PerformanceTracker:
    """Tracks performance metrics for the Enhanced Security Agent"""

    def __init__(self):
        self.metrics = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "average_response_time": 0.0,
            "mcp_server_calls": {},
            "error_counts": {},
        }
        self.query_times = []

    def start_query(self) -> float:
        """Start tracking a query"""
        return time.time()

    def end_query(self, start_time: float, success: bool = True):
        """End tracking a query"""
        duration = time.time() - start_time
        self.query_times.append(duration)

        self.metrics["total_queries"] += 1
        if success:
            self.metrics["successful_queries"] += 1
        else:
            self.metrics["failed_queries"] += 1

        # Update average response time
        self.metrics["average_response_time"] = sum(self.query_times) / len(
            self.query_times
        )

    def record_mcp_call(self, mcp_server: str, success: bool = True):
        """Record MCP server call"""
        if mcp_server not in self.metrics["mcp_server_calls"]:
            self.metrics["mcp_server_calls"][mcp_server] = {
                "total": 0,
                "successful": 0,
                "failed": 0,
            }

        self.metrics["mcp_server_calls"][mcp_server]["total"] += 1
        if success:
            self.metrics["mcp_server_calls"][mcp_server]["successful"] += 1
        else:
            self.metrics["mcp_server_calls"][mcp_server]["failed"] += 1

    def record_error(self, error_type: str):
        """Record error occurrence"""
        if error_type not in self.metrics["error_counts"]:
            self.metrics["error_counts"][error_type] = 0
        self.metrics["error_counts"][error_type] += 1

    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        return self.metrics.copy()

    def reset_metrics(self):
        """Reset all metrics"""
        self.metrics = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "average_response_time": 0.0,
            "mcp_server_calls": {},
            "error_counts": {},
        }
        self.query_times = []


# Global instances
structured_logger = StructuredLogger()
performance_tracker = PerformanceTracker()


def get_logger() -> StructuredLogger:
    """Get the global structured logger instance"""
    return structured_logger


def get_performance_tracker() -> PerformanceTracker:
    """Get the global performance tracker instance"""
    return performance_tracker
