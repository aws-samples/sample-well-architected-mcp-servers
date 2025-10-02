"""
Core data models and interfaces for the simplified backend refactor.
"""

from .data_models import (
    AgentInfo,
    QueryRoute,
    ChatSession,
    ChatMessage,
    ToolExecution,
    CommandResponse,
    RouteType,
    AgentFramework,
    AgentStatus,
)

from .response_models import (
    ChatResponse,
    AgentListResponse,
    HealthResponse,
)

from .interfaces import (
    AgentManagerInterface,
    BedrockServiceInterface,
    QueryRouterInterface,
)

from .exceptions import (
    COABaseException,
    AgentDiscoveryError,
    BedrockCommunicationError,
    SessionManagementError,
    CommandProcessingError,
)

__all__ = [
    # Data models
    "AgentInfo",
    "QueryRoute", 
    "ChatSession",
    "ChatMessage",
    "ToolExecution",
    "CommandResponse",
    # Enums
    "RouteType",
    "AgentFramework", 
    "AgentStatus",
    # Response models
    "ChatResponse",
    "AgentListResponse", 
    "HealthResponse",
    # Interfaces
    "AgentManagerInterface",
    "BedrockServiceInterface",
    "QueryRouterInterface",
    # Exceptions
    "COABaseException",
    "AgentDiscoveryError",
    "BedrockCommunicationError",
    "SessionManagementError",
    "CommandProcessingError",
]