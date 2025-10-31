"""
Response models for API endpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .data_models import AgentInfo, QueryRoute, ToolExecution


class ChatResponse(BaseModel):
    """Response model for chat interactions."""
    response: str
    session_id: str
    route_info: QueryRoute
    tool_executions: List[ToolExecution] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent_used: Optional[str] = None
    model_used: Optional[str] = None
    processing_time_ms: Optional[int] = None
    
    class Config:
        arbitrary_types_allowed = True


class AgentListResponse(BaseModel):
    """Response model for listing available agents."""
    agents: List[AgentInfo]
    total_count: int
    selected_agent: Optional[str] = None
    last_discovery: Optional[datetime] = None
    
    class Config:
        arbitrary_types_allowed = True


class ServiceStatus(BaseModel):
    """Status information for a service."""
    name: str
    status: str  # 'healthy', 'degraded', 'unhealthy'
    details: Optional[str] = None
    last_check: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str  # 'healthy', 'degraded', 'unhealthy'
    services: List[ServiceStatus]
    agent_count: int
    active_sessions: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    uptime_seconds: Optional[int] = None


class AgentSelectionResponse(BaseModel):
    """Response model for agent selection."""
    success: bool
    message: str
    selected_agent: Optional[str] = None
    session_id: str
    available_agents: Optional[List[str]] = None


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str
    error_code: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None