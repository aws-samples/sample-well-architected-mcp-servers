"""
Interface definitions for AgentCore services.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime

from .agentcore_models import (
    AgentInfo, AgentResponse, CommandResponse, DiscoveryStats, 
    RegistryStats, InvocationStats, AgentCoreConfig
)


class AgentRegistryInterface(ABC):
    """Interface for agent registry operations."""
    
    @abstractmethod
    async def register_agent(self, agent_info: AgentInfo) -> bool:
        """Register a new agent in the registry."""
        pass
    
    @abstractmethod
    async def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent information by ID."""
        pass
    
    @abstractmethod
    async def get_all_agents(self) -> Dict[str, AgentInfo]:
        """Get all registered agents."""
        pass
    
    @abstractmethod
    async def remove_agent(self, agent_id: str) -> bool:
        """Remove an agent from the registry."""
        pass
    
    @abstractmethod
    async def update_agent_status(self, agent_id: str, status: str) -> bool:
        """Update agent status."""
        pass
    
    @abstractmethod
    async def clear_registry(self) -> None:
        """Clear all agents from the registry."""
        pass
    
    @abstractmethod
    def get_registry_stats(self) -> RegistryStats:
        """Get registry statistics."""
        pass
    
    @abstractmethod
    async def health_check(self) -> str:
        """Check registry health status."""
        pass


class AgentDiscoveryInterface(ABC):
    """Interface for agent discovery operations."""
    
    @abstractmethod
    async def discover_agents(self) -> List[AgentInfo]:
        """Discover agents from SSM Parameter Store."""
        pass
    
    @abstractmethod
    async def scan_ssm_parameters(self) -> List[Dict[str, Any]]:
        """Scan SSM parameters for agent configurations."""
        pass
    
    @abstractmethod
    async def parse_agent_config(self, param_data: Dict) -> Optional[AgentInfo]:
        """Parse agent configuration from SSM parameter data."""
        pass
    
    @abstractmethod
    async def validate_agent_config(self, config: Dict) -> bool:
        """Validate agent configuration data."""
        pass
    
    @abstractmethod
    def get_discovery_stats(self) -> DiscoveryStats:
        """Get discovery statistics."""
        pass
    
    @abstractmethod
    async def start_periodic_discovery(self) -> None:
        """Start periodic agent discovery."""
        pass
    
    @abstractmethod
    async def stop_periodic_discovery(self) -> None:
        """Stop periodic agent discovery."""
        pass
    
    @abstractmethod
    async def health_check(self) -> str:
        """Check discovery service health status."""
        pass


class AgentInvocationInterface(ABC):
    """Interface for agent invocation operations."""
    
    @abstractmethod
    async def initialize_client(self) -> bool:
        """Initialize the AgentCore client."""
        pass
    
    @abstractmethod
    async def invoke_agent(self, agent_info: AgentInfo, prompt: str, session_id: str) -> AgentResponse:
        """Invoke an AgentCore agent."""
        pass
    
    @abstractmethod
    async def format_prompt(self, prompt: str, agent_type: str) -> Dict[str, Any]:
        """Format prompt for specific agent type."""
        pass
    
    @abstractmethod
    async def validate_response(self, response: Dict) -> bool:
        """Validate agent response."""
        pass
    
    @abstractmethod
    def get_client_status(self) -> Dict[str, Any]:
        """Get client status information."""
        pass
    
    @abstractmethod
    def get_invocation_stats(self) -> InvocationStats:
        """Get invocation statistics."""
        pass
    
    @abstractmethod
    async def health_check(self) -> str:
        """Check invocation service health status."""
        pass


class CommandManagerInterface(ABC):
    """Interface for command management operations."""
    
    @abstractmethod
    async def process_command(self, command: str, session_id: str) -> CommandResponse:
        """Process an AgentCore command."""
        pass
    
    @abstractmethod
    async def handle_list_command(self, args: List[str]) -> Dict[str, Any]:
        """Handle /agentcore list command."""
        pass
    
    @abstractmethod
    async def handle_discover_command(self, args: List[str]) -> Dict[str, Any]:
        """Handle /agentcore discover command."""
        pass
    
    @abstractmethod
    def validate_command(self, command: str) -> bool:
        """Validate command syntax."""
        pass
    
    @abstractmethod
    def parse_command(self, command: str) -> Dict[str, Any]:
        """Parse command into components."""
        pass
    
    @abstractmethod
    def is_agentcore_command(self, text: str) -> bool:
        """Check if text is an AgentCore command."""
        pass
    
    @abstractmethod
    async def health_check(self) -> str:
        """Check command manager health status."""
        pass


class AgentCoreServiceInterface(ABC):
    """Main interface for AgentCore service operations."""
    
    @abstractmethod
    async def initialize(self, config: AgentCoreConfig) -> bool:
        """Initialize the AgentCore service."""
        pass
    
    @abstractmethod
    async def discover_and_register_agents(self) -> int:
        """Discover and register all available agents."""
        pass
    
    @abstractmethod
    async def get_available_agents(self) -> Dict[str, AgentInfo]:
        """Get all available agents."""
        pass
    
    @abstractmethod
    async def invoke_agent_by_id(self, agent_id: str, prompt: str, session_id: str) -> AgentResponse:
        """Invoke agent by ID."""
        pass
    
    @abstractmethod
    async def process_user_command(self, command: str, session_id: str) -> CommandResponse:
        """Process user command."""
        pass
    
    @abstractmethod
    async def refresh_agents(self) -> int:
        """Refresh agent registry."""
        pass
    
    @abstractmethod
    def get_service_stats(self) -> Dict[str, Any]:
        """Get comprehensive service statistics."""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, str]:
        """Check health of all service components."""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the service gracefully."""
        pass


class SessionManagerInterface(ABC):
    """Interface for session management with AgentCore support."""
    
    @abstractmethod
    async def create_session(self, session_id: str) -> Dict[str, Any]:
        """Create a new session."""
        pass
    
    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information."""
        pass
    
    @abstractmethod
    async def update_session_context(self, session_id: str, context: Dict[str, Any]) -> bool:
        """Update session context."""
        pass
    
    @abstractmethod
    async def set_selected_agent(self, session_id: str, agent_id: str) -> bool:
        """Set selected agent for session."""
        pass
    
    @abstractmethod
    async def get_selected_agent(self, session_id: str) -> Optional[str]:
        """Get selected agent for session."""
        pass
    
    @abstractmethod
    async def clear_selected_agent(self, session_id: str) -> bool:
        """Clear selected agent for session."""
        pass
    
    @abstractmethod
    async def cleanup_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up old sessions."""
        pass