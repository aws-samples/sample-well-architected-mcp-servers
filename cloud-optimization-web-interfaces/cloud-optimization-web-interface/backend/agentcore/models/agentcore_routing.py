"""
AgentCore routing models for Strands agent selection and orchestration.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field

from shared.models.base_models import BaseResponseModel


class StrandsRouteType(str, Enum):
    """Route type enumeration for Strands agent routing."""
    STRANDS_AGENT = "strands_agent"
    MODEL_FALLBACK = "model_fallback"
    AGENTCORE_RUNTIME = "agentcore_runtime"


class AgentSelectionStrategy(str, Enum):
    """Agent selection strategy enumeration."""
    CAPABILITY_MATCH = "capability_match"
    LOAD_BALANCED = "load_balanced"
    PRIORITY_BASED = "priority_based"
    ROUND_ROBIN = "round_robin"
    AVAILABILITY_BASED = "availability_based"


class QueryDomain(str, Enum):
    """Query domain enumeration for Strands agents."""
    SECURITY = "security"
    COST_OPTIMIZATION = "cost_optimization"
    RELIABILITY = "reliability"
    PERFORMANCE = "performance"
    SUSTAINABILITY = "sustainability"
    GENERAL = "general"


@dataclass
class StrandsAgentRoute:
    """Information about how a query should be routed to Strands agents."""
    route_type: StrandsRouteType
    target_agent: str  # agent_id or agent_name
    reasoning: str
    confidence: float = 0.0
    requires_context: bool = False
    estimated_response_time_ms: Optional[int] = None
    fallback_agents: List[str] = field(default_factory=list)
    parameter_prefix: str = "coa"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "route_type": self.route_type.value,
            "target_agent": self.target_agent,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "requires_context": self.requires_context,
            "estimated_response_time_ms": self.estimated_response_time_ms,
            "fallback_agents": self.fallback_agents,
            "parameter_prefix": self.parameter_prefix
        }


class StrandsQueryAnalysis(BaseModel):
    """Analysis of a user query for Strands agent routing."""
    query: str = Field(..., description="Original user query")
    domain: QueryDomain = Field(default=QueryDomain.GENERAL, description="Query domain")
    keywords: List[str] = Field(default_factory=list, description="Extracted keywords")
    intent: str = Field(..., description="Detected user intent")
    required_capabilities: List[str] = Field(
        default_factory=list,
        description="Required agent capabilities"
    )
    aws_services: List[str] = Field(
        default_factory=list,
        description="AWS services mentioned in query"
    )
    complexity_score: float = Field(default=0.5, description="Query complexity (0-1)")
    urgency_level: str = Field(default="normal", description="Query urgency level")
    context_required: bool = Field(default=False, description="Whether context is required")
    
    def add_keyword(self, keyword: str):
        """Add a keyword to the analysis."""
        if keyword not in self.keywords:
            self.keywords.append(keyword)
    
    def add_capability(self, capability: str):
        """Add a required capability."""
        if capability not in self.required_capabilities:
            self.required_capabilities.append(capability)
    
    def add_aws_service(self, service: str):
        """Add an AWS service to the analysis."""
        if service not in self.aws_services:
            self.aws_services.append(service)


class StrandsRoutingDecision(BaseResponseModel):
    """Routing decision for Strands agents with detailed information."""
    query_analysis: StrandsQueryAnalysis = Field(..., description="Query analysis results")
    selected_route: StrandsAgentRoute = Field(..., description="Selected routing option")
    alternative_routes: List[StrandsAgentRoute] = Field(
        default_factory=list,
        description="Alternative routing options"
    )
    selection_strategy: AgentSelectionStrategy = Field(..., description="Strategy used for selection")
    decision_time_ms: float = Field(default=0, description="Time taken to make decision")
    parameter_prefix: str = Field(default="coa", description="Parameter prefix used")
    
    def add_alternative_route(self, route: StrandsAgentRoute):
        """Add an alternative routing option."""
        self.alternative_routes.append(route)


class StrandsAgentMatch(BaseModel):
    """Model for Strands agent capability matching."""
    agent_id: str = Field(..., description="Agent ID")
    agent_name: str = Field(..., description="Agent name")
    agent_type: str = Field(..., description="Agent type")
    match_score: float = Field(..., description="Capability match score (0-1)")
    matched_capabilities: List[str] = Field(
        default_factory=list,
        description="Capabilities that matched"
    )
    missing_capabilities: List[str] = Field(
        default_factory=list,
        description="Required capabilities not available"
    )
    availability_score: float = Field(default=1.0, description="Agent availability score")
    last_used: Optional[datetime] = Field(None, description="Last time agent was used")
    
    @property
    def overall_score(self) -> float:
        """Calculate overall score combining match and availability."""
        return (self.match_score * 0.6) + (self.availability_score * 0.4)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "match_score": self.match_score,
            "matched_capabilities": self.matched_capabilities,
            "missing_capabilities": self.missing_capabilities,
            "availability_score": self.availability_score,
            "overall_score": self.overall_score,
            "last_used": self.last_used.isoformat() if self.last_used else None
        }


class StrandsRoutingRule(BaseModel):
    """Model for Strands agent routing rules configuration."""
    name: str = Field(..., description="Rule name")
    description: str = Field(..., description="Rule description")
    keywords: List[str] = Field(default_factory=list, description="Trigger keywords")
    domains: List[QueryDomain] = Field(default_factory=list, description="Applicable domains")
    aws_services: List[str] = Field(default_factory=list, description="Applicable AWS services")
    target_agent_type: Optional[str] = Field(None, description="Target agent type")
    target_agent_id: Optional[str] = Field(None, description="Specific target agent ID")
    priority: int = Field(default=0, description="Rule priority (higher = more important)")
    enabled: bool = Field(default=True, description="Whether rule is enabled")
    conditions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional conditions"
    )
    
    def matches_query(self, query_analysis: StrandsQueryAnalysis) -> bool:
        """Check if this rule matches the query analysis."""
        if not self.enabled:
            return False
        
        # Check keywords
        if self.keywords:
            keyword_match = any(
                keyword.lower() in query_analysis.query.lower()
                for keyword in self.keywords
            )
            if not keyword_match:
                return False
        
        # Check domains
        if self.domains and query_analysis.domain not in self.domains:
            return False
        
        # Check AWS services
        if self.aws_services:
            service_match = any(
                service in query_analysis.aws_services
                for service in self.aws_services
            )
            if not service_match:
                return False
        
        # Check additional conditions
        for condition, value in self.conditions.items():
            if condition == "complexity_min" and query_analysis.complexity_score < value:
                return False
            elif condition == "complexity_max" and query_analysis.complexity_score > value:
                return False
            elif condition == "urgency" and query_analysis.urgency_level != value:
                return False
        
        return True


@dataclass
class StrandsRoutingMetrics:
    """Metrics for Strands agent routing performance."""
    total_queries: int = 0
    strands_agent_routes: int = 0
    model_fallback_routes: int = 0
    successful_routes: int = 0
    failed_routes: int = 0
    average_decision_time_ms: float = 0.0
    routes_by_agent: Dict[str, int] = field(default_factory=dict)
    routes_by_domain: Dict[str, int] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def success_rate(self) -> float:
        """Calculate routing success rate."""
        if self.total_queries == 0:
            return 0.0
        return self.successful_routes / self.total_queries
    
    @property
    def strands_agent_percentage(self) -> float:
        """Calculate percentage of queries routed to Strands agents."""
        if self.total_queries == 0:
            return 0.0
        return (self.strands_agent_routes / self.total_queries) * 100
    
    @property
    def fallback_percentage(self) -> float:
        """Calculate percentage of queries that fell back to model."""
        if self.total_queries == 0:
            return 0.0
        return (self.model_fallback_routes / self.total_queries) * 100
    
    def record_route(
        self,
        route_type: StrandsRouteType,
        agent_id: str,
        success: bool,
        decision_time_ms: float,
        domain: QueryDomain = QueryDomain.GENERAL
    ):
        """Record a routing decision."""
        self.total_queries += 1
        
        if route_type == StrandsRouteType.STRANDS_AGENT:
            self.strands_agent_routes += 1
        elif route_type == StrandsRouteType.MODEL_FALLBACK:
            self.model_fallback_routes += 1
        
        if success:
            self.successful_routes += 1
        else:
            self.failed_routes += 1
        
        # Update averages
        if self.total_queries == 1:
            self.average_decision_time_ms = decision_time_ms
        else:
            self.average_decision_time_ms = (
                (self.average_decision_time_ms * (self.total_queries - 1) + decision_time_ms)
                / self.total_queries
            )
        
        # Update agent counts
        if agent_id not in self.routes_by_agent:
            self.routes_by_agent[agent_id] = 0
        self.routes_by_agent[agent_id] += 1
        
        # Update domain counts
        domain_str = domain.value
        if domain_str not in self.routes_by_domain:
            self.routes_by_domain[domain_str] = 0
        self.routes_by_domain[domain_str] += 1
        
        self.last_updated = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "total_queries": self.total_queries,
            "strands_agent_routes": self.strands_agent_routes,
            "model_fallback_routes": self.model_fallback_routes,
            "successful_routes": self.successful_routes,
            "failed_routes": self.failed_routes,
            "success_rate": self.success_rate,
            "strands_agent_percentage": self.strands_agent_percentage,
            "fallback_percentage": self.fallback_percentage,
            "average_decision_time_ms": self.average_decision_time_ms,
            "routes_by_agent": self.routes_by_agent,
            "routes_by_domain": self.routes_by_domain,
            "last_updated": self.last_updated.isoformat()
        }


class StrandsAgentCapability(BaseModel):
    """Model for Strands agent capabilities."""
    name: str = Field(..., description="Capability name")
    description: str = Field(..., description="Capability description")
    aws_services: List[str] = Field(default_factory=list, description="Supported AWS services")
    domains: List[QueryDomain] = Field(default_factory=list, description="Applicable domains")
    keywords: List[str] = Field(default_factory=list, description="Related keywords")
    confidence_level: float = Field(default=1.0, description="Confidence in capability (0-1)")
    
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


class StrandsAgentStatus(str, Enum):
    """Strands agent status enumeration."""
    AVAILABLE = "available"
    BUSY = "busy"
    UNAVAILABLE = "unavailable"
    MAINTENANCE = "maintenance"
    ERROR = "error"


class StrandsAgentHealth(BaseModel):
    """Model for Strands agent health information."""
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
            self.status == StrandsAgentStatus.AVAILABLE and
            self.error_rate < 0.1 and
            self.active_sessions < self.max_sessions
        )
    
    @property
    def load_percentage(self) -> float:
        """Calculate current load percentage."""
        if self.max_sessions == 0:
            return 0.0
        return (self.active_sessions / self.max_sessions) * 100