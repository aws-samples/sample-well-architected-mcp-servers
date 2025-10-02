"""
Interface definitions for core services.
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional
from datetime import datetime

from .data_models import AgentInfo, QueryRoute, CommandResponse, ChatSession


class AgentManagerInterface(ABC):
    """Interface for agent management operations."""
    
    @abstractmethod
    async def discover_agents(self) -> Dict[str, AgentInfo]:
        """Discover available agents from SSM Parameter Store."""
        pass
    
    @abstractmethod
    async def get_agent_info(self, agent_id: str) -> Optional[AgentInfo]:
        """Get information about a specific agent."""
        pass
    
    @abstractmethod
    async def get_agent_capabilities(self, agent_id: str) -> List[str]:
        """Get capabilities for a specific agent."""
        pass
    
    @abstractmethod
    async def get_agent_tool_count(self, agent_id: str) -> int:
        """Get the number of tools available for a specific agent."""
        pass
    
    @abstractmethod
    def select_agent_for_session(self, session_id: str, agent_id: str) -> None:
        """Select an agent for a specific session."""
        pass
    
    @abstractmethod
    def get_selected_agent(self, session_id: str) -> Optional[str]:
        """Get the selected agent for a session."""
        pass
    
    @abstractmethod
    def clear_agent_selection(self, session_id: str) -> None:
        """Clear agent selection for a session."""
        pass
    
    @abstractmethod
    async def refresh_agent_cache(self) -> None:
        """Force refresh of agent cache."""
        pass


class ModelResponse:
    """Response from a Bedrock model invocation."""
    def __init__(self, content: str, model_id: str, usage: Optional[Dict[str, Any]] = None):
        self.content = content
        self.model_id = model_id
        self.usage = usage or {}
        self.timestamp = datetime.utcnow()


class AgentResponse:
    """Response from a Bedrock agent invocation."""
    def __init__(self, content: str, agent_id: str, session_id: str, 
                 tool_executions: Optional[List[Dict[str, Any]]] = None):
        self.content = content
        self.agent_id = agent_id
        self.session_id = session_id
        self.tool_executions = tool_executions or []
        self.timestamp = datetime.utcnow()


class BedrockServiceInterface(ABC):
    """Interface for Bedrock communication operations."""
    
    @abstractmethod
    async def invoke_model(self, model_id: str, prompt: str, **kwargs) -> ModelResponse:
        """Invoke a Bedrock model directly."""
        pass
    
    @abstractmethod
    async def invoke_agent(self, agent_id: str, agent_alias_id: str, 
                          session_id: str, input_text: str) -> AgentResponse:
        """Invoke a Bedrock agent."""
        pass
    
    @abstractmethod
    async def stream_model_response(self, model_id: str, prompt: str, 
                                   **kwargs) -> AsyncIterator[str]:
        """Stream response from a Bedrock model."""
        pass
    
    @abstractmethod
    async def stream_agent_response(self, agent_id: str, agent_alias_id: str,
                                   session_id: str, input_text: str) -> AsyncIterator[str]:
        """Stream response from a Bedrock agent."""
        pass
    
    @abstractmethod
    async def check_model_availability(self, model_id: str) -> bool:
        """Check if a model is available."""
        pass
    
    @abstractmethod
    async def check_agent_availability(self, agent_id: str) -> bool:
        """Check if an agent is available."""
        pass


class QueryRouterInterface(ABC):
    """Interface for query routing operations."""
    
    @abstractmethod
    async def route_query(self, query: str, session_id: str, 
                         context: Dict[str, Any]) -> QueryRoute:
        """Determine how to route a query."""
        pass
    
    @abstractmethod
    def should_use_agent(self, query: str, selected_agent: Optional[str]) -> bool:
        """Determine if a query should use an agent."""
        pass
    
    @abstractmethod
    def select_model_for_query(self, query: str) -> str:
        """Select the best model for a direct model query."""
        pass
    
    @abstractmethod
    async def process_agent_command(self, command: str, session_id: str) -> CommandResponse:
        """Process agent selection commands."""
        pass
    
    @abstractmethod
    def is_agent_command(self, query: str) -> bool:
        """Check if a query is an agent command."""
        pass
    
    @abstractmethod
    def parse_agent_command(self, command: str) -> Dict[str, Any]:
        """Parse an agent command into components."""
        pass


class SessionManagerInterface(ABC):
    """Interface for session management operations."""
    
    @abstractmethod
    async def create_session(self, session_id: str) -> ChatSession:
        """Create a new chat session."""
        pass
    
    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get an existing chat session."""
        pass
    
    @abstractmethod
    async def update_session(self, session: ChatSession) -> None:
        """Update a chat session."""
        pass
    
    @abstractmethod
    async def delete_session(self, session_id: str) -> None:
        """Delete a chat session."""
        pass
    
    @abstractmethod
    async def cleanup_inactive_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up inactive sessions and return count of cleaned sessions."""
        pass
    
    @abstractmethod
    async def get_active_session_count(self) -> int:
        """Get count of active sessions."""
        pass