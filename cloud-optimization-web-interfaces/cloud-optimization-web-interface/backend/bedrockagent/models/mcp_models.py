"""
MCP (Model Context Protocol) client models for BedrockAgent version.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field

from shared.models.base_models import BaseResponseModel


class MCPConnectionStatus(str, Enum):
    """MCP connection status enumeration."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"


class MCPToolCategory(str, Enum):
    """MCP tool category enumeration."""
    SECURITY = "security"
    COST_OPTIMIZATION = "cost_optimization"
    DISCOVERY = "discovery"
    STORAGE = "storage"
    NETWORKING = "networking"
    COMPUTE = "compute"
    DATABASE = "database"
    GENERAL = "general"


@dataclass
class MCPConnection:
    """MCP server connection information."""
    server_name: str
    agent_id: str
    agent_arn: Optional[str] = None
    endpoint_url: Optional[str] = None
    status: MCPConnectionStatus = MCPConnectionStatus.DISCONNECTED
    last_connected: Optional[datetime] = None
    connection_attempts: int = 0
    error_message: Optional[str] = None
    
    def mark_connected(self):
        """Mark connection as successful."""
        self.status = MCPConnectionStatus.CONNECTED
        self.last_connected = datetime.utcnow()
        self.error_message = None
    
    def mark_disconnected(self, error_message: Optional[str] = None):
        """Mark connection as disconnected."""
        self.status = MCPConnectionStatus.DISCONNECTED
        self.error_message = error_message
    
    def mark_error(self, error_message: str):
        """Mark connection as error."""
        self.status = MCPConnectionStatus.ERROR
        self.error_message = error_message
        self.connection_attempts += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "server_name": self.server_name,
            "agent_id": self.agent_id,
            "agent_arn": self.agent_arn,
            "endpoint_url": self.endpoint_url,
            "status": self.status.value,
            "last_connected": self.last_connected.isoformat() if self.last_connected else None,
            "connection_attempts": self.connection_attempts,
            "error_message": self.error_message
        }


class MCPTool(BaseModel):
    """Model for MCP tool information."""
    name: str = Field(..., description="Tool name")
    description: str = Field(default="", description="Tool description")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    server_name: str = Field(..., description="MCP server name")
    server_display_name: str = Field(..., description="MCP server display name")
    category: MCPToolCategory = Field(default=MCPToolCategory.GENERAL, description="Tool category")
    status: str = Field(default="available", description="Tool status")
    
    def categorize_by_name(self) -> MCPToolCategory:
        """Categorize tool based on name and description."""
        combined_text = f"{self.name} {self.description}".lower()
        
        if any(keyword in combined_text for keyword in ["security", "check", "findings", "encryption"]):
            return MCPToolCategory.SECURITY
        elif any(keyword in combined_text for keyword in ["cost", "usage", "billing", "savings"]):
            return MCPToolCategory.COST_OPTIMIZATION
        elif any(keyword in combined_text for keyword in ["list", "describe", "get", "discover"]):
            return MCPToolCategory.DISCOVERY
        elif any(keyword in combined_text for keyword in ["storage", "s3", "ebs", "efs"]):
            return MCPToolCategory.STORAGE
        elif any(keyword in combined_text for keyword in ["network", "vpc", "elb"]):
            return MCPToolCategory.NETWORKING
        elif any(keyword in combined_text for keyword in ["compute", "ec2", "lambda"]):
            return MCPToolCategory.COMPUTE
        elif any(keyword in combined_text for keyword in ["database", "rds", "dynamodb"]):
            return MCPToolCategory.DATABASE
        else:
            return MCPToolCategory.GENERAL
    
    class Config:
        use_enum_values = True


class MCPToolExecution(BaseResponseModel):
    """Model for MCP tool execution."""
    tool_name: str = Field(..., description="Name of executed tool")
    server_name: str = Field(..., description="MCP server name")
    input_parameters: Dict[str, Any] = Field(..., description="Input parameters")
    result: Any = Field(None, description="Execution result")
    execution_time_ms: float = Field(default=0, description="Execution time in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    started_at: datetime = Field(default_factory=datetime.utcnow, description="Execution start time")
    completed_at: Optional[datetime] = Field(None, description="Execution completion time")
    
    def mark_completed(self, result: Any):
        """Mark execution as completed."""
        self.result = result
        self.completed_at = datetime.utcnow()
        self.execution_time_ms = (self.completed_at - self.started_at).total_seconds() * 1000
        self.success = True
    
    def mark_failed(self, error_message: str):
        """Mark execution as failed."""
        self.error_message = error_message
        self.completed_at = datetime.utcnow()
        self.execution_time_ms = (self.completed_at - self.started_at).total_seconds() * 1000
        self.success = False
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MCPServerSummary(BaseModel):
    """Summary information about MCP servers."""
    total_servers: int = Field(default=0, description="Total number of servers")
    connected_servers: int = Field(default=0, description="Number of connected servers")
    total_tools: int = Field(default=0, description="Total number of tools")
    tools_by_category: Dict[str, int] = Field(
        default_factory=dict,
        description="Tool count by category"
    )
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update time"
    )
    
    @property
    def connection_rate(self) -> float:
        """Calculate server connection rate."""
        if self.total_servers == 0:
            return 0.0
        return self.connected_servers / self.total_servers
    
    def add_server_tools(self, tools: List[MCPTool]):
        """Add tools from a server to the summary."""
        for tool in tools:
            category = tool.category.value
            if category not in self.tools_by_category:
                self.tools_by_category[category] = 0
            self.tools_by_category[category] += 1
        
        self.total_tools += len(tools)
        self.last_updated = datetime.utcnow()
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MCPClientConfiguration(BaseModel):
    """Configuration for MCP client."""
    connection_timeout_seconds: int = Field(default=30, description="Connection timeout")
    request_timeout_seconds: int = Field(default=60, description="Request timeout")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay_seconds: float = Field(default=1.0, description="Delay between retries")
    enable_connection_pooling: bool = Field(default=True, description="Enable connection pooling")
    max_concurrent_requests: int = Field(default=10, description="Maximum concurrent requests")
    
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate configuration parameters."""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        if self.connection_timeout_seconds <= 0:
            validation_result["errors"].append("Connection timeout must be positive")
            validation_result["valid"] = False
        
        if self.request_timeout_seconds <= 0:
            validation_result["errors"].append("Request timeout must be positive")
            validation_result["valid"] = False
        
        if self.max_retries < 0:
            validation_result["errors"].append("Max retries cannot be negative")
            validation_result["valid"] = False
        
        if self.retry_delay_seconds < 0:
            validation_result["errors"].append("Retry delay cannot be negative")
            validation_result["valid"] = False
        
        if self.max_concurrent_requests <= 0:
            validation_result["errors"].append("Max concurrent requests must be positive")
            validation_result["valid"] = False
        
        # Warnings for potentially problematic values
        if self.connection_timeout_seconds > 60:
            validation_result["warnings"].append("Connection timeout is very high")
        
        if self.max_concurrent_requests > 50:
            validation_result["warnings"].append("High concurrent request limit may cause issues")
        
        return validation_result


@dataclass
class MCPClientMetrics:
    """Metrics for MCP client performance."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_execution_time_ms: float = 0.0
    connection_attempts: int = 0
    successful_connections: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def success_rate(self) -> float:
        """Calculate request success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests
    
    @property
    def average_execution_time_ms(self) -> float:
        """Calculate average execution time."""
        if self.successful_requests == 0:
            return 0.0
        return self.total_execution_time_ms / self.successful_requests
    
    @property
    def connection_success_rate(self) -> float:
        """Calculate connection success rate."""
        if self.connection_attempts == 0:
            return 0.0
        return self.successful_connections / self.connection_attempts
    
    def record_request(self, success: bool, execution_time_ms: float):
        """Record a request execution."""
        self.total_requests += 1
        
        if success:
            self.successful_requests += 1
            self.total_execution_time_ms += execution_time_ms
        else:
            self.failed_requests += 1
        
        self.last_updated = datetime.utcnow()
    
    def record_connection_attempt(self, success: bool):
        """Record a connection attempt."""
        self.connection_attempts += 1
        
        if success:
            self.successful_connections += 1
        
        self.last_updated = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.success_rate,
            "average_execution_time_ms": self.average_execution_time_ms,
            "connection_attempts": self.connection_attempts,
            "successful_connections": self.successful_connections,
            "connection_success_rate": self.connection_success_rate,
            "last_updated": self.last_updated.isoformat()
        }