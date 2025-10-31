"""
Tool execution models for BedrockAgent version.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field

from shared.models.base_models import BaseResponseModel


class ToolExecutionStatus(str, Enum):
    """Tool execution status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ToolType(str, Enum):
    """Tool type enumeration."""
    MCP_TOOL = "mcp_tool"
    BEDROCK_TOOL = "bedrock_tool"
    LAMBDA_FUNCTION = "lambda_function"
    API_CALL = "api_call"


@dataclass
class ToolExecutionResult:
    """Result of tool execution."""
    tool_name: str
    tool_type: ToolType
    status: ToolExecutionStatus
    input_parameters: Dict[str, Any]
    output_data: Any = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        """Check if execution was successful."""
        return self.status == ToolExecutionStatus.COMPLETED and self.error_message is None
    
    @property
    def duration_seconds(self) -> float:
        """Get execution duration in seconds."""
        return self.execution_time_ms / 1000.0
    
    def mark_completed(self, output_data: Any):
        """Mark execution as completed."""
        self.status = ToolExecutionStatus.COMPLETED
        self.output_data = output_data
        self.completed_at = datetime.utcnow()
        if self.completed_at:
            self.execution_time_ms = (self.completed_at - self.started_at).total_seconds() * 1000
    
    def mark_failed(self, error_message: str):
        """Mark execution as failed."""
        self.status = ToolExecutionStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.utcnow()
        if self.completed_at:
            self.execution_time_ms = (self.completed_at - self.started_at).total_seconds() * 1000
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "tool_name": self.tool_name,
            "tool_type": self.tool_type.value,
            "status": self.status.value,
            "success": self.success,
            "input_parameters": self.input_parameters,
            "output_data": self.output_data,
            "error_message": self.error_message,
            "execution_time_ms": self.execution_time_ms,
            "duration_seconds": self.duration_seconds,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata
        }


class ToolDefinition(BaseModel):
    """Definition of a tool available for execution."""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    tool_type: ToolType = Field(..., description="Type of tool")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters schema")
    required_parameters: List[str] = Field(default_factory=list, description="Required parameters")
    optional_parameters: List[str] = Field(default_factory=list, description="Optional parameters")
    category: str = Field(default="general", description="Tool category")
    server_name: Optional[str] = Field(None, description="MCP server name (for MCP tools)")
    endpoint_url: Optional[str] = Field(None, description="Endpoint URL (for API tools)")
    timeout_seconds: int = Field(default=30, description="Execution timeout")
    
    def validate_input(self, input_parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input parameters against tool definition."""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check required parameters
        for param in self.required_parameters:
            if param not in input_parameters:
                validation_result["errors"].append(f"Required parameter '{param}' is missing")
                validation_result["valid"] = False
        
        # Check for unknown parameters
        known_parameters = set(self.required_parameters + self.optional_parameters)
        for param in input_parameters:
            if param not in known_parameters:
                validation_result["warnings"].append(f"Unknown parameter '{param}'")
        
        return validation_result
    
    class Config:
        use_enum_values = True


class ToolExecutionRequest(BaseModel):
    """Request for tool execution."""
    tool_name: str = Field(..., description="Name of tool to execute")
    input_parameters: Dict[str, Any] = Field(..., description="Input parameters")
    timeout_seconds: Optional[int] = Field(None, description="Execution timeout override")
    context: Dict[str, Any] = Field(default_factory=dict, description="Execution context")
    async_execution: bool = Field(default=False, description="Whether to execute asynchronously")
    
    def validate_request(self, tool_definition: ToolDefinition) -> Dict[str, Any]:
        """Validate request against tool definition."""
        return tool_definition.validate_input(self.input_parameters)


class ToolExecutionResponse(BaseResponseModel):
    """Response from tool execution."""
    tool_name: str = Field(..., description="Name of executed tool")
    execution_id: str = Field(..., description="Unique execution ID")
    status: ToolExecutionStatus = Field(..., description="Execution status")
    result: ToolExecutionResult = Field(..., description="Execution result")
    
    class Config:
        use_enum_values = True


class ToolRegistry(BaseModel):
    """Registry of available tools."""
    tools: Dict[str, ToolDefinition] = Field(default_factory=dict, description="Available tools")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    
    def register_tool(self, tool: ToolDefinition):
        """Register a new tool."""
        self.tools[tool.name] = tool
        self.last_updated = datetime.utcnow()
    
    def unregister_tool(self, tool_name: str):
        """Unregister a tool."""
        if tool_name in self.tools:
            del self.tools[tool_name]
            self.last_updated = datetime.utcnow()
    
    def get_tool(self, tool_name: str) -> Optional[ToolDefinition]:
        """Get tool definition by name."""
        return self.tools.get(tool_name)
    
    def get_tools_by_category(self, category: str) -> List[ToolDefinition]:
        """Get tools by category."""
        return [tool for tool in self.tools.values() if tool.category == category]
    
    def get_tools_by_type(self, tool_type: ToolType) -> List[ToolDefinition]:
        """Get tools by type."""
        return [tool for tool in self.tools.values() if tool.tool_type == tool_type]
    
    @property
    def tool_count(self) -> int:
        """Get total number of registered tools."""
        return len(self.tools)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get registry summary."""
        categories = {}
        types = {}
        
        for tool in self.tools.values():
            # Count by category
            if tool.category not in categories:
                categories[tool.category] = 0
            categories[tool.category] += 1
            
            # Count by type
            tool_type = tool.tool_type.value
            if tool_type not in types:
                types[tool_type] = 0
            types[tool_type] += 1
        
        return {
            "total_tools": self.tool_count,
            "categories": categories,
            "types": types,
            "last_updated": self.last_updated.isoformat()
        }
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


@dataclass
class ToolExecutionMetrics:
    """Metrics for tool execution performance."""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    timeout_executions: int = 0
    cancelled_executions: int = 0
    total_execution_time_ms: float = 0.0
    executions_by_tool: Dict[str, int] = field(default_factory=dict)
    executions_by_category: Dict[str, int] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def success_rate(self) -> float:
        """Calculate execution success rate."""
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions
    
    @property
    def failure_rate(self) -> float:
        """Calculate execution failure rate."""
        if self.total_executions == 0:
            return 0.0
        return self.failed_executions / self.total_executions
    
    @property
    def average_execution_time_ms(self) -> float:
        """Calculate average execution time."""
        if self.successful_executions == 0:
            return 0.0
        return self.total_execution_time_ms / self.successful_executions
    
    def record_execution(self, result: ToolExecutionResult, category: str = "general"):
        """Record a tool execution."""
        self.total_executions += 1
        
        # Count by status
        if result.status == ToolExecutionStatus.COMPLETED:
            self.successful_executions += 1
            self.total_execution_time_ms += result.execution_time_ms
        elif result.status == ToolExecutionStatus.FAILED:
            self.failed_executions += 1
        elif result.status == ToolExecutionStatus.TIMEOUT:
            self.timeout_executions += 1
        elif result.status == ToolExecutionStatus.CANCELLED:
            self.cancelled_executions += 1
        
        # Count by tool
        if result.tool_name not in self.executions_by_tool:
            self.executions_by_tool[result.tool_name] = 0
        self.executions_by_tool[result.tool_name] += 1
        
        # Count by category
        if category not in self.executions_by_category:
            self.executions_by_category[category] = 0
        self.executions_by_category[category] += 1
        
        self.last_updated = datetime.utcnow()
    
    def get_top_tools(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most frequently used tools."""
        sorted_tools = sorted(
            self.executions_by_tool.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [
            {"tool_name": tool_name, "execution_count": count}
            for tool_name, count in sorted_tools[:limit]
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "timeout_executions": self.timeout_executions,
            "cancelled_executions": self.cancelled_executions,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "average_execution_time_ms": self.average_execution_time_ms,
            "executions_by_tool": self.executions_by_tool,
            "executions_by_category": self.executions_by_category,
            "top_tools": self.get_top_tools(),
            "last_updated": self.last_updated.isoformat()
        }