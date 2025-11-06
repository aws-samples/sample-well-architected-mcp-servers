"""
Strands Agent models for AgentCore integration.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field

from shared.models.base_models import BaseResponseModel


class StrandsAgentType(str, Enum):
    """Strands agent type enumeration."""
    WA_SECURITY = "wa_security_agent"
    COST_OPTIMIZATION = "cost_optimization_agent"
    AWS_API = "aws_api_agent"
    GENERAL_PURPOSE = "general_purpose_agent"


class StrandsAgentStatus(str, Enum):
    """Strands agent status enumeration."""
    DISCOVERED = "discovered"
    ACTIVE = "active"
    DEPLOYED = "deployed"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class StrandsRuntimeType(str, Enum):
    """Strands runtime type enumeration."""
    AGENTCORE_RUNTIME = "agentcore_runtime"
    BEDROCK_AGENTCORE = "bedrock_agentcore"


@dataclass
class StrandsAgentCapability:
    """Capability definition for Strands agents."""
    name: str
    description: str
    aws_services: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    confidence_level: float = 1.0
    
    def matches_requirement(self, requirement: str) -> float:
        """Check if this capability matches a requirement and return match score."""
        requirement_lower = requirement.lower()
        
        # Check exact name match
        if self.name.lower() == requirement_lower:
            return 1.0
        
        # Check keyword matches
        keyword_matches = sum(
            1 for keyword in self.keywords
            if keyword.lower() in requirement_lower
        )
        
        if keyword_matches > 0:
            return min(0.8, keyword_matches * 0.2)
        
        # Check partial name match
        if self.name.lower() in requirement_lower or requirement_lower in self.name.lower():
            return 0.6
        
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "aws_services": self.aws_services,
            "domains": self.domains,
            "keywords": self.keywords,
            "confidence_level": self.confidence_level
        }


@dataclass
class StrandsAgent:
    """Strands agent information with AgentCore runtime support."""
    agent_id: str
    agent_name: str
    agent_arn: str
    agent_type: StrandsAgentType = StrandsAgentType.GENERAL_PURPOSE
    runtime_type: StrandsRuntimeType = StrandsRuntimeType.AGENTCORE_RUNTIME
    status: StrandsAgentStatus = StrandsAgentStatus.DISCOVERED
    capabilities: List[StrandsAgentCapability] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    # AgentCore specific attributes
    endpoint_url: Optional[str] = None
    health_check_url: Optional[str] = None
    
    # Runtime attributes
    framework: str = "strands"
    model_id: str = "claude-3-5-sonnet-20241022-v2:0"
    supported_domains: List[str] = field(default_factory=list)
    supported_aws_services: List[str] = field(default_factory=list)
    
    # Performance attributes
    average_response_time_ms: Optional[float] = None
    success_rate: float = 1.0
    last_invocation: Optional[datetime] = None
    
    def is_healthy(self) -> bool:
        """Check if agent is in a healthy state."""
        return self.status in [StrandsAgentStatus.ACTIVE, StrandsAgentStatus.DEPLOYED]
    
    def is_agentcore_runtime(self) -> bool:
        """Check if this is an AgentCore runtime agent."""
        return self.runtime_type == StrandsRuntimeType.AGENTCORE_RUNTIME
    
    def add_capability(self, capability: StrandsAgentCapability):
        """Add a capability to the agent."""
        self.capabilities.append(capability)
    
    def has_capability(self, capability_name: str) -> bool:
        """Check if agent has a specific capability."""
        return any(cap.name == capability_name for cap in self.capabilities)
    
    def get_capability_match_score(self, requirements: List[str]) -> float:
        """Calculate overall capability match score for requirements."""
        if not requirements:
            return 0.5  # Default score for no specific requirements
        
        total_score = 0.0
        for requirement in requirements:
            best_score = max(
                (cap.matches_requirement(requirement) for cap in self.capabilities),
                default=0.0
            )
            total_score += best_score
        
        return min(total_score / len(requirements), 1.0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_arn": self.agent_arn,
            "agent_type": self.agent_type.value,
            "runtime_type": self.runtime_type.value,
            "status": self.status.value,
            "capabilities": [cap.to_dict() for cap in self.capabilities],
            "metadata": self.metadata,
            "last_updated": self.last_updated.isoformat(),
            "endpoint_url": self.endpoint_url,
            "health_check_url": self.health_check_url,
            "framework": self.framework,
            "model_id": self.model_id,
            "supported_domains": self.supported_domains,
            "supported_aws_services": self.supported_aws_services,
            "average_response_time_ms": self.average_response_time_ms,
            "success_rate": self.success_rate,
            "last_invocation": self.last_invocation.isoformat() if self.last_invocation else None,
            "is_healthy": self.is_healthy(),
            "is_agentcore_runtime": self.is_agentcore_runtime()
        }


@dataclass
class StrandsAgentResponse:
    """Response from Strands agent invocation."""
    agent_id: str
    agent_type: StrandsAgentType
    response_text: str
    session_id: str
    execution_time_ms: float
    status: str
    tool_executions: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def add_tool_execution(self, tool_name: str, tool_input: Dict[str, Any], tool_output: Any, success: bool):
        """Add a tool execution record."""
        self.tool_executions.append({
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_output": tool_output,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "response_text": self.response_text,
            "session_id": self.session_id,
            "execution_time_ms": self.execution_time_ms,
            "status": self.status,
            "tool_executions": self.tool_executions,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class AgentDiscoveryResult:
    """Result from Strands agent discovery operation."""
    agents_discovered: List[StrandsAgent] = field(default_factory=list)
    agents_updated: List[str] = field(default_factory=list)
    agents_removed: List[str] = field(default_factory=list)
    discovery_stats: 'StrandsDiscoveryStats' = field(default_factory=lambda: StrandsDiscoveryStats())
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def add_discovered_agent(self, agent: StrandsAgent):
        """Add a discovered agent."""
        self.agents_discovered.append(agent)
        self.discovery_stats.agents_found += 1
    
    def add_updated_agent(self, agent_id: str):
        """Record an updated agent."""
        self.agents_updated.append(agent_id)
        self.discovery_stats.agents_updated += 1
    
    def add_removed_agent(self, agent_id: str):
        """Record a removed agent."""
        self.agents_removed.append(agent_id)
        self.discovery_stats.agents_removed += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agents_discovered": [agent.to_dict() for agent in self.agents_discovered],
            "agents_updated": self.agents_updated,
            "agents_removed": self.agents_removed,
            "discovery_stats": self.discovery_stats.to_dict(),
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class StrandsDiscoveryStats:
    """Statistics about Strands agent discovery operations."""
    total_scanned: int = 0
    agents_found: int = 0
    agents_updated: int = 0
    agents_removed: int = 0
    scan_duration_ms: float = 0.0
    last_scan: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    
    def add_error(self, error: str):
        """Add an error to the stats."""
        self.errors.append(error)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_scanned": self.total_scanned,
            "agents_found": self.agents_found,
            "agents_updated": self.agents_updated,
            "agents_removed": self.agents_removed,
            "scan_duration_ms": self.scan_duration_ms,
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "errors": self.errors
        }


@dataclass
class StrandsRegistryStats:
    """Statistics about Strands agent registry operations."""
    total_agents: int = 0
    healthy_agents: int = 0
    agentcore_agents: int = 0
    agents_by_type: Dict[str, int] = field(default_factory=dict)
    last_updated: Optional[datetime] = None
    cache_hits: int = 0
    cache_misses: int = 0
    
    def update_agent_type_count(self, agent_type: StrandsAgentType):
        """Update count for a specific agent type."""
        type_str = agent_type.value
        if type_str not in self.agents_by_type:
            self.agents_by_type[type_str] = 0
        self.agents_by_type[type_str] += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_agents": self.total_agents,
            "healthy_agents": self.healthy_agents,
            "agentcore_agents": self.agentcore_agents,
            "agents_by_type": self.agents_by_type,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses
        }


@dataclass
class StrandsInvocationStats:
    """Statistics about Strands agent invocation operations."""
    total_invocations: int = 0
    successful_invocations: int = 0
    failed_invocations: int = 0
    average_response_time_ms: float = 0.0
    invocations_by_agent: Dict[str, int] = field(default_factory=dict)
    invocations_by_type: Dict[str, int] = field(default_factory=dict)
    last_invocation: Optional[datetime] = None
    
    def record_invocation(
        self,
        agent_id: str,
        agent_type: StrandsAgentType,
        success: bool,
        response_time_ms: float
    ):
        """Record an invocation."""
        self.total_invocations += 1
        
        if success:
            self.successful_invocations += 1
        else:
            self.failed_invocations += 1
        
        # Update averages
        if self.total_invocations == 1:
            self.average_response_time_ms = response_time_ms
        else:
            self.average_response_time_ms = (
                (self.average_response_time_ms * (self.total_invocations - 1) + response_time_ms)
                / self.total_invocations
            )
        
        # Update agent counts
        if agent_id not in self.invocations_by_agent:
            self.invocations_by_agent[agent_id] = 0
        self.invocations_by_agent[agent_id] += 1
        
        # Update type counts
        type_str = agent_type.value
        if type_str not in self.invocations_by_type:
            self.invocations_by_type[type_str] = 0
        self.invocations_by_type[type_str] += 1
        
        self.last_invocation = datetime.utcnow()
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_invocations == 0:
            return 0.0
        return self.successful_invocations / self.total_invocations
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_invocations": self.total_invocations,
            "successful_invocations": self.successful_invocations,
            "failed_invocations": self.failed_invocations,
            "success_rate": self.success_rate,
            "average_response_time_ms": self.average_response_time_ms,
            "invocations_by_agent": self.invocations_by_agent,
            "invocations_by_type": self.invocations_by_type,
            "last_invocation": self.last_invocation.isoformat() if self.last_invocation else None
        }


@dataclass
class StrandsAgentConfig:
    """Configuration for Strands agent integration."""
    ssm_prefix: str = "/coa/agents/strands/"
    discovery_interval_seconds: int = 300  # 5 minutes
    cache_ttl_seconds: int = 300  # 5 minutes
    max_retries: int = 3
    timeout_seconds: int = 120  # 2 minutes
    enable_health_checks: bool = True
    enable_metrics: bool = True
    enable_routing: bool = True
    default_model_id: str = "claude-3-5-sonnet-20241022-v2:0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "ssm_prefix": self.ssm_prefix,
            "discovery_interval_seconds": self.discovery_interval_seconds,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "enable_health_checks": self.enable_health_checks,
            "enable_metrics": self.enable_metrics,
            "enable_routing": self.enable_routing,
            "default_model_id": self.default_model_id
        }


class StrandsAgentHealthCheck(BaseModel):
    """Health check information for Strands agents."""
    agent_id: str = Field(..., description="Agent ID")
    status: StrandsAgentStatus = Field(..., description="Agent status")
    last_heartbeat: datetime = Field(..., description="Last heartbeat timestamp")
    response_time_ms: Optional[float] = Field(None, description="Average response time")
    error_rate: float = Field(default=0.0, description="Error rate (0-1)")
    active_sessions: int = Field(default=0, description="Number of active sessions")
    max_sessions: int = Field(default=10, description="Maximum concurrent sessions")
    
    @property
    def is_healthy(self) -> bool:
        """Check if agent is healthy."""
        return (
            self.status == StrandsAgentStatus.ACTIVE and
            self.error_rate < 0.1 and
            self.active_sessions < self.max_sessions
        )
    
    @property
    def load_percentage(self) -> float:
        """Calculate current load percentage."""
        if self.max_sessions == 0:
            return 0.0
        return (self.active_sessions / self.max_sessions) * 100


# Factory functions for creating common Strands agent types

def create_wa_security_agent(
    agent_id: str,
    agent_name: str,
    agent_arn: str,
    endpoint_url: Optional[str] = None
) -> StrandsAgent:
    """Create a Well-Architected Security Strands agent."""
    capabilities = [
        StrandsAgentCapability(
            name="security_assessment",
            description="AWS security posture assessment and analysis",
            aws_services=["guardduty", "inspector", "securityhub", "macie", "config"],
            domains=["security", "compliance"],
            keywords=["security", "vulnerability", "compliance", "threat", "assessment"]
        ),
        StrandsAgentCapability(
            name="compliance_checking",
            description="AWS compliance and configuration validation",
            aws_services=["config", "cloudtrail", "iam"],
            domains=["security", "compliance"],
            keywords=["compliance", "configuration", "policy", "audit"]
        )
    ]
    
    return StrandsAgent(
        agent_id=agent_id,
        agent_name=agent_name,
        agent_arn=agent_arn,
        agent_type=StrandsAgentType.WA_SECURITY,
        capabilities=capabilities,
        endpoint_url=endpoint_url,
        supported_domains=["security", "compliance"],
        supported_aws_services=["guardduty", "inspector", "securityhub", "macie", "config", "iam"]
    )


def create_cost_optimization_agent(
    agent_id: str,
    agent_name: str,
    agent_arn: str,
    endpoint_url: Optional[str] = None
) -> StrandsAgent:
    """Create a Cost Optimization Strands agent."""
    capabilities = [
        StrandsAgentCapability(
            name="cost_analysis",
            description="AWS cost analysis and optimization recommendations",
            aws_services=["ce", "budgets", "compute-optimizer"],
            domains=["cost_optimization"],
            keywords=["cost", "billing", "optimization", "savings", "budget"]
        ),
        StrandsAgentCapability(
            name="resource_rightsizing",
            description="AWS resource rightsizing recommendations",
            aws_services=["ec2", "rds", "compute-optimizer"],
            domains=["cost_optimization", "performance"],
            keywords=["rightsizing", "optimization", "instance", "performance"]
        )
    ]
    
    return StrandsAgent(
        agent_id=agent_id,
        agent_name=agent_name,
        agent_arn=agent_arn,
        agent_type=StrandsAgentType.COST_OPTIMIZATION,
        capabilities=capabilities,
        endpoint_url=endpoint_url,
        supported_domains=["cost_optimization"],
        supported_aws_services=["ce", "budgets", "compute-optimizer", "ec2", "rds"]
    )


def create_aws_api_agent(
    agent_id: str,
    agent_name: str,
    agent_arn: str,
    endpoint_url: Optional[str] = None
) -> StrandsAgent:
    """Create an AWS API Strands agent."""
    capabilities = [
        StrandsAgentCapability(
            name="aws_api_operations",
            description="AWS API operations and resource management",
            aws_services=["*"],  # Supports all AWS services
            domains=["general", "operations"],
            keywords=["list", "describe", "get", "create", "delete", "update", "api"]
        ),
        StrandsAgentCapability(
            name="resource_discovery",
            description="AWS resource discovery and inventory",
            aws_services=["*"],
            domains=["general", "operations"],
            keywords=["discover", "inventory", "resources", "list", "find"]
        )
    ]
    
    return StrandsAgent(
        agent_id=agent_id,
        agent_name=agent_name,
        agent_arn=agent_arn,
        agent_type=StrandsAgentType.AWS_API,
        capabilities=capabilities,
        endpoint_url=endpoint_url,
        supported_domains=["general", "operations"],
        supported_aws_services=["*"]  # Supports all AWS services
    )