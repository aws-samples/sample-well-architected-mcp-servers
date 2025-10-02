"""
Core data models for the simplified backend refactor.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum


class RouteType(str, Enum):
    """Route type enumeration for query routing."""
    MODEL = "model"
    AGENT = "agent"


class AgentFramework(str, Enum):
    """Agent framework enumeration."""
    BEDROCK = "bedrock"
    AGENTCORE = "agentcore"


class AgentStatus(str, Enum):
    """Agent status enumeration."""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass
class AgentInfo:
    """Information about an available agent."""
    agent_id: str
    name: str
    description: str
    capabilities: List[str]
    tool_count: int
    framework: AgentFramework
    endpoint_url: Optional[str] = None
    status: AgentStatus = AgentStatus.AVAILABLE
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class QueryRoute:
    """Information about how a query should be routed."""
    route_type: RouteType
    target: str  # model_id or agent_id
    reasoning: str
    requires_streaming: bool = False
    confidence: float = 1.0


@dataclass
class ChatMessage:
    """Individual chat message in a conversation."""
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolExecution:
    """Information about a tool execution during query processing."""
    tool_name: str
    tool_input: Dict[str, Any]
    tool_output: Any
    execution_time_ms: int
    success: bool
    error_message: Optional[str] = None


@dataclass
class ChatSession:
    """Chat session with agent selection and conversation history."""
    session_id: str
    selected_agent: Optional[str] = None
    messages: List[ChatMessage] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CommandResponse:
    """Response from processing an agent command."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    command_type: Optional[str] = None