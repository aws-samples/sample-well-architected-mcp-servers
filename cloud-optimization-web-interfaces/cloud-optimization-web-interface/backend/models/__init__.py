"""
Core data models and interfaces for the simplified backend refactor.
"""

from .data_models import (
    AgentInfo as LegacyAgentInfo,
    QueryRoute,
    ChatSession,
    ChatMessage,
    ToolExecution,
    CommandResponse as LegacyCommandResponse,
    RouteType,
    AgentFramework,
    AgentStatus,
)

from .agentcore_models import (
    AgentInfo,
    AgentResponse,
    CommandResponse,
    DiscoveryStats,
    RegistryStats,
    InvocationStats,
    AgentCoreConfig,
    AgentRuntimeType,
    AgentDiscoveryStatus,
    CommandType,
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

from .agentcore_interfaces import (
    AgentRegistryInterface,
    AgentDiscoveryInterface,
    AgentInvocationInterface,
    CommandManagerInterface,
    AgentCoreServiceInterface,
    SessionManagerInterface,
)

from .exceptions import (
    COABaseException,
    AgentDiscoveryError,
    BedrockCommunicationError,
    SessionManagementError,
    CommandProcessingError,
    # AgentCore exceptions
    AgentCoreError,
    AgentRegistryError,
    AgentInvocationError,
    AgentCoreClientError,
    SSMParameterError,
    AgentConfigurationError,
)

__all__ = [
    # Legacy data models (for backward compatibility)
    "LegacyAgentInfo",
    "QueryRoute", 
    "ChatSession",
    "ChatMessage",
    "ToolExecution",
    "LegacyCommandResponse",
    # AgentCore data models
    "AgentInfo",
    "AgentResponse",
    "CommandResponse",
    "DiscoveryStats",
    "RegistryStats",
    "InvocationStats",
    "AgentCoreConfig",
    # Enums
    "RouteType",
    "AgentFramework", 
    "AgentStatus",
    "AgentRuntimeType",
    "AgentDiscoveryStatus",
    "CommandType",
    # Response models
    "ChatResponse",
    "AgentListResponse", 
    "HealthResponse",
    # Legacy interfaces
    "AgentManagerInterface",
    "BedrockServiceInterface",
    "QueryRouterInterface",
    # AgentCore interfaces
    "AgentRegistryInterface",
    "AgentDiscoveryInterface",
    "AgentInvocationInterface",
    "CommandManagerInterface",
    "AgentCoreServiceInterface",
    "SessionManagerInterface",
    # Exceptions
    "COABaseException",
    "AgentDiscoveryError",
    "BedrockCommunicationError",
    "SessionManagementError",
    "CommandProcessingError",
    "AgentCoreError",
    "AgentRegistryError",
    "AgentInvocationError",
    "AgentCoreClientError",
    "SSMParameterError",
    "AgentConfigurationError",
]