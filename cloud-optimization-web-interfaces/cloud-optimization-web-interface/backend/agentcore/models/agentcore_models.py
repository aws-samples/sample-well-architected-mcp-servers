"""
AgentCore-specific data models for dynamic agent discovery and invocation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum


class AgentRuntimeType(str, Enum):
    """Agent runtime type enumeration."""
    BEDROCK_AGENT = "bedrock-agent"
    BEDROCK_AGENTCORE = "bedrock-agentcore"


class AgentDiscoveryStatus(str, Enum):
    """Agent discovery status enumeration."""
    DISCOVERED = "discovered"
    ACTIVE = "active"
    DEPLOYED = "deployed"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class CommandType(str, Enum):
    """AgentCore command type enumeration."""
    LIST = "list"
    DISCOVER = "discover"
    INVOKE = "invoke"
    STATUS = "status"


@dataclass
class AgentInfo:
    """Enhanced agent information with AgentCore runtime support."""
    agent_id: str
    agent_name: str
    agent_arn: str
    runtime_type: AgentRuntimeType = AgentRuntimeType.BEDROCK_AGENTCORE
    status: AgentDiscoveryStatus = AgentDiscoveryStatus.DISCOVERED
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    # AgentCore specific attributes
    endpoint_url: Optional[str] = None
    health_check_url: Optional[str] = None
    
    # Common attributes
    framework: str = "agentcore"
    model_id: str = "unknown"
    
    def is_healthy(self) -> bool:
        """Check if agent is in a healthy state."""
        return self.status in [AgentDiscoveryStatus.ACTIVE, AgentDiscoveryStatus.DEPLOYED]
    
    def is_agentcore(self) -> bool:
        """Check if this is an AgentCore runtime agent."""
        return self.runtime_type == AgentRuntimeType.BEDROCK_AGENTCORE
    
    def is_bedrock_agent(self) -> bool:
        """Check if this is a standard Bedrock Agent."""
        return self.runtime_type == AgentRuntimeType.BEDROCK_AGENT
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_arn": self.agent_arn,
            "runtime_type": self.runtime_type.value,
            "status": self.status.value,
            "capabilities": self.capabilities,
            "metadata": self.metadata,
            "last_updated": self.last_updated.isoformat(),
            "endpoint_url": self.endpoint_url,
            "health_check_url": self.health_check_url,
            "framework": self.framework,
            "model_id": self.model_id,
            "is_healthy": self.is_healthy(),
            "is_agentcore": self.is_agentcore()
        }


@dataclass
class AgentResponse:
    """Response from AgentCore agent invocation."""
    agent_id: str
    response_text: str
    session_id: str
    execution_time: float
    status: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_id": self.agent_id,
            "response_text": self.response_text,
            "session_id": self.session_id,
            "execution_time": self.execution_time,
            "status": self.status,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class CommandResponse:
    """Response from AgentCore command processing."""
    command: str
    status: str
    data: Dict[str, Any]
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "command": self.command,
            "status": self.status,
            "data": self.data,
            "message": self.message,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class DiscoveryStats:
    """Statistics about agent discovery operations."""
    total_scanned: int = 0
    agents_found: int = 0
    agents_updated: int = 0
    agents_removed: int = 0
    scan_duration: float = 0.0
    last_scan: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_scanned": self.total_scanned,
            "agents_found": self.agents_found,
            "agents_updated": self.agents_updated,
            "agents_removed": self.agents_removed,
            "scan_duration": self.scan_duration,
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "errors": self.errors
        }


@dataclass
class RegistryStats:
    """Statistics about agent registry operations."""
    total_agents: int = 0
    healthy_agents: int = 0
    agentcore_agents: int = 0
    bedrock_agents: int = 0
    agents_found: int = 0
    agents_updated: int = 0
    agents_removed: int = 0
    last_updated: Optional[datetime] = None
    cache_hits: int = 0
    cache_misses: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_agents": self.total_agents,
            "healthy_agents": self.healthy_agents,
            "agentcore_agents": self.agentcore_agents,
            "bedrock_agents": self.bedrock_agents,
            "agents_found": self.agents_found,
            "agents_updated": self.agents_updated,
            "agents_removed": self.agents_removed,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses
        }


@dataclass
class InvocationStats:
    """Statistics about agent invocation operations."""
    total_invocations: int = 0
    successful_invocations: int = 0
    failed_invocations: int = 0
    average_response_time: float = 0.0
    last_invocation: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_invocations": self.total_invocations,
            "successful_invocations": self.successful_invocations,
            "failed_invocations": self.failed_invocations,
            "average_response_time": self.average_response_time,
            "last_invocation": self.last_invocation.isoformat() if self.last_invocation else None
        }


@dataclass
class AgentCoreConfig:
    """Configuration for AgentCore integration."""
    ssm_prefix: str = "/coa/agents/"
    discovery_interval: int = 300  # 5 minutes
    cache_ttl: int = 300  # 5 minutes
    max_retries: int = 3
    timeout: int = 120  # 2 minutes
    enable_health_checks: bool = True
    enable_metrics: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "ssm_prefix": self.ssm_prefix,
            "discovery_interval": self.discovery_interval,
            "cache_ttl": self.cache_ttl,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "enable_health_checks": self.enable_health_checks,
            "enable_metrics": self.enable_metrics
        }