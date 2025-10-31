"""
BedrockAgent-specific data models for traditional Bedrock Agent integration.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field

from shared.models.base_models import BaseAgentModel, BaseResponseModel


class BedrockAgentStatus(str, Enum):
    """Bedrock agent status enumeration."""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    INITIALIZING = "initializing"


class MCPServerStatus(str, Enum):
    """MCP server status enumeration."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class AgentInvocationType(str, Enum):
    """Agent invocation type enumeration."""
    SYNC = "sync"
    ASYNC = "async"
    STREAMING = "streaming"


@dataclass
class BedrockAgentInfo(BaseAgentModel):
    """Information about a Bedrock agent."""
    agent_alias_id: str
    region: str
    model_id: Optional[str] = None
    description: str = ""
    mcp_servers: List[str] = field(default_factory=list)
    tool_count: int = 0
    status: BedrockAgentStatus = BedrockAgentStatus.AVAILABLE
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_alias_id": self.agent_alias_id,
            "region": self.region,
            "model_id": self.model_id,
            "description": self.description,
            "capabilities": self.capabilities,
            "mcp_servers": self.mcp_servers,
            "tool_count": self.tool_count,
            "status": self.status.value,
            "framework": self.framework,
            "created_at": self.created_at.isoformat(),
            "last_seen": self.last_seen.isoformat() if self.last_seen else None
        }


@dataclass
class MCPServerInfo:
    """Information about an MCP server."""
    name: str
    display_name: str
    agent_id: str
    agent_arn: Optional[str] = None
    region: str = "us-east-1"
    deployment_type: str = "agentcore_runtime"
    package_name: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    available_tools: List[str] = field(default_factory=list)
    supported_services: List[str] = field(default_factory=list)
    status: MCPServerStatus = MCPServerStatus.DISCONNECTED
    description: str = ""
    framework: str = "mcp"
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def capabilities_count(self) -> int:
        """Get count of capabilities."""
        return len(self.capabilities)
    
    @property
    def tools_count(self) -> int:
        """Get count of available tools."""
        return len(self.available_tools)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "agent_id": self.agent_id,
            "agent_arn": self.agent_arn,
            "region": self.region,
            "deployment_type": self.deployment_type,
            "package_name": self.package_name,
            "capabilities": self.capabilities,
            "capabilities_count": self.capabilities_count,
            "available_tools": self.available_tools,
            "tools_count": self.tools_count,
            "supported_services": self.supported_services,
            "status": self.status.value,
            "description": self.description,
            "framework": self.framework,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat()
        }


class BedrockAgentRequest(BaseModel):
    """Request model for Bedrock agent invocation."""
    agent_id: str = Field(..., description="Bedrock agent ID")
    agent_alias_id: str = Field(..., description="Agent alias ID")
    session_id: str = Field(..., description="Session ID for conversation continuity")
    input_text: str = Field(..., description="User input text")
    invocation_type: AgentInvocationType = Field(
        default=AgentInvocationType.SYNC,
        description="Type of invocation"
    )
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    
    class Config:
        use_enum_values = True


class BedrockAgentResponse(BaseResponseModel):
    """Response model for Bedrock agent invocation."""
    agent_id: str = Field(..., description="Bedrock agent ID")
    session_id: str = Field(..., description="Session ID")
    content: str = Field(..., description="Agent response content")
    tool_executions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of tool executions"
    )
    invocation_type: AgentInvocationType = Field(
        default=AgentInvocationType.SYNC,
        description="Type of invocation used"
    )
    response_time_ms: float = Field(default=0, description="Response time in milliseconds")
    streaming: bool = Field(default=False, description="Whether response was streamed")
    
    class Config:
        use_enum_values = True


class MCPToolRequest(BaseModel):
    """Request model for MCP tool execution."""
    tool_name: str = Field(..., description="Name of the MCP tool")
    tool_input: Dict[str, Any] = Field(..., description="Tool input parameters")
    server_name: str = Field(..., description="MCP server name")
    timeout_seconds: int = Field(default=30, description="Execution timeout")
    
    def validate_request(self) -> Dict[str, Any]:
        """Validate the tool request."""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        if not self.tool_name.strip():
            validation_result["errors"].append("Tool name cannot be empty")
            validation_result["valid"] = False
        
        if not self.server_name.strip():
            validation_result["errors"].append("Server name cannot be empty")
            validation_result["valid"] = False
        
        if self.timeout_seconds <= 0 or self.timeout_seconds > 300:
            validation_result["warnings"].append("Timeout should be between 1 and 300 seconds")
        
        return validation_result


class MCPToolResponse(BaseResponseModel):
    """Response model for MCP tool execution."""
    tool_name: str = Field(..., description="Name of the executed tool")
    server_name: str = Field(..., description="MCP server name")
    result: Any = Field(None, description="Tool execution result")
    execution_time_ms: float = Field(default=0, description="Execution time in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if execution failed")
    
    @property
    def success(self) -> bool:
        """Check if tool execution was successful."""
        return self.success and self.error_message is None


class AgentSessionInfo(BaseModel):
    """Information about an agent session."""
    session_id: str = Field(..., description="Session ID")
    agent_id: str = Field(..., description="Associated agent ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Session creation time")
    last_activity: datetime = Field(default_factory=datetime.utcnow, description="Last activity time")
    message_count: int = Field(default=0, description="Number of messages in session")
    context: Dict[str, Any] = Field(default_factory=dict, description="Session context")
    active: bool = Field(default=True, description="Whether session is active")
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()
    
    def increment_message_count(self):
        """Increment message count."""
        self.message_count += 1
        self.update_activity()
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BedrockAgentCapability(BaseModel):
    """Model for Bedrock agent capability."""
    name: str = Field(..., description="Capability name")
    description: str = Field(..., description="Capability description")
    category: str = Field(..., description="Capability category")
    tools: List[str] = Field(default_factory=list, description="Associated tools")
    
    @property
    def tool_count(self) -> int:
        """Get count of associated tools."""
        return len(self.tools)


class AgentHealthStatus(BaseModel):
    """Health status information for an agent."""
    agent_id: str = Field(..., description="Agent ID")
    status: BedrockAgentStatus = Field(..., description="Agent status")
    last_check: datetime = Field(default_factory=datetime.utcnow, description="Last health check time")
    response_time_ms: Optional[float] = Field(None, description="Last response time")
    error_message: Optional[str] = Field(None, description="Error message if unhealthy")
    consecutive_failures: int = Field(default=0, description="Number of consecutive failures")
    
    def mark_healthy(self, response_time_ms: float = 0):
        """Mark agent as healthy."""
        self.status = BedrockAgentStatus.AVAILABLE
        self.last_check = datetime.utcnow()
        self.response_time_ms = response_time_ms
        self.error_message = None
        self.consecutive_failures = 0
    
    def mark_unhealthy(self, error_message: str):
        """Mark agent as unhealthy."""
        self.status = BedrockAgentStatus.ERROR
        self.last_check = datetime.utcnow()
        self.error_message = error_message
        self.consecutive_failures += 1
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


@dataclass
class BedrockAgentSummary:
    """Summary information about BedrockAgent deployment."""
    total_agents: int = 0
    available_agents: int = 0
    unavailable_agents: int = 0
    total_mcp_servers: int = 0
    connected_mcp_servers: int = 0
    total_tools: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def agent_availability_rate(self) -> float:
        """Calculate agent availability rate."""
        if self.total_agents == 0:
            return 0.0
        return self.available_agents / self.total_agents
    
    @property
    def mcp_connection_rate(self) -> float:
        """Calculate MCP server connection rate."""
        if self.total_mcp_servers == 0:
            return 0.0
        return self.connected_mcp_servers / self.total_mcp_servers
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "total_agents": self.total_agents,
            "available_agents": self.available_agents,
            "unavailable_agents": self.unavailable_agents,
            "agent_availability_rate": self.agent_availability_rate,
            "total_mcp_servers": self.total_mcp_servers,
            "connected_mcp_servers": self.connected_mcp_servers,
            "mcp_connection_rate": self.mcp_connection_rate,
            "total_tools": self.total_tools,
            "last_updated": self.last_updated.isoformat()
        }