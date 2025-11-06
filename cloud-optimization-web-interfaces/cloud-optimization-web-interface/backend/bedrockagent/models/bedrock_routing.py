"""
BedrockAgent routing models for query routing and agent selection.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field

from shared.models.base_models import BaseResponseModel


class RouteType(str, Enum):
    """Route type enumeration for query routing."""
    AGENT = "agent"
    MODEL = "model"
    MCP_TOOL = "mcp_tool"


class RoutingStrategy(str, Enum):
    """Routing strategy enumeration."""
    KEYWORD_BASED = "keyword_based"
    CAPABILITY_BASED = "capability_based"
    LOAD_BALANCED = "load_balanced"
    PRIORITY_BASED = "priority_based"


class QueryComplexity(str, Enum):
    """Query complexity enumeration."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


@dataclass
class QueryRoute:
    """Information about how a query should be routed."""
    route_type: RouteType
    target: str  # agent_id, model_id, or tool_name
    reasoning: str
    confidence: float = 0.0
    requires_streaming: bool = False
    estimated_response_time_ms: Optional[int] = None
    fallback_options: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "route_type": self.route_type.value,
            "target": self.target,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "requires_streaming": self.requires_streaming,
            "estimated_response_time_ms": self.estimated_response_time_ms,
            "fallback_options": self.fallback_options
        }


class QueryAnalysis(BaseModel):
    """Analysis of a user query for routing decisions."""
    query: str = Field(..., description="Original user query")
    complexity: QueryComplexity = Field(..., description="Query complexity level")
    keywords: List[str] = Field(default_factory=list, description="Extracted keywords")
    intent: str = Field(..., description="Detected user intent")
    required_capabilities: List[str] = Field(
        default_factory=list,
        description="Required agent capabilities"
    )
    domain: str = Field(default="general", description="Query domain")
    urgency: str = Field(default="normal", description="Query urgency level")
    context_required: bool = Field(default=False, description="Whether context is required")
    
    def add_keyword(self, keyword: str):
        """Add a keyword to the analysis."""
        if keyword not in self.keywords:
            self.keywords.append(keyword)
    
    def add_capability(self, capability: str):
        """Add a required capability."""
        if capability not in self.required_capabilities:
            self.required_capabilities.append(capability)


class RoutingDecision(BaseResponseModel):
    """Routing decision with detailed information."""
    query_analysis: QueryAnalysis = Field(..., description="Query analysis results")
    selected_route: QueryRoute = Field(..., description="Selected routing option")
    alternative_routes: List[QueryRoute] = Field(
        default_factory=list,
        description="Alternative routing options"
    )
    routing_strategy: RoutingStrategy = Field(..., description="Strategy used for routing")
    decision_time_ms: float = Field(default=0, description="Time taken to make decision")
    
    def add_alternative_route(self, route: QueryRoute):
        """Add an alternative routing option."""
        self.alternative_routes.append(route)


class AgentCapabilityMatch(BaseModel):
    """Model for agent capability matching."""
    agent_id: str = Field(..., description="Agent ID")
    agent_name: str = Field(..., description="Agent name")
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
    
    @property
    def overall_score(self) -> float:
        """Calculate overall score combining match and availability."""
        return (self.match_score * 0.7) + (self.availability_score * 0.3)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "match_score": self.match_score,
            "matched_capabilities": self.matched_capabilities,
            "missing_capabilities": self.missing_capabilities,
            "availability_score": self.availability_score,
            "overall_score": self.overall_score
        }


class RoutingRule(BaseModel):
    """Model for routing rules configuration."""
    name: str = Field(..., description="Rule name")
    description: str = Field(..., description="Rule description")
    keywords: List[str] = Field(default_factory=list, description="Trigger keywords")
    domains: List[str] = Field(default_factory=list, description="Applicable domains")
    target_agent_id: Optional[str] = Field(None, description="Target agent ID")
    target_model_id: Optional[str] = Field(None, description="Target model ID")
    priority: int = Field(default=0, description="Rule priority (higher = more important)")
    enabled: bool = Field(default=True, description="Whether rule is enabled")
    conditions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional conditions"
    )
    
    def matches_query(self, query_analysis: QueryAnalysis) -> bool:
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
        
        # Check additional conditions
        for condition, value in self.conditions.items():
            if condition == "complexity" and query_analysis.complexity.value != value:
                return False
            elif condition == "urgency" and query_analysis.urgency != value:
                return False
        
        return True


@dataclass
class RoutingMetrics:
    """Metrics for routing performance."""
    total_queries: int = 0
    agent_routes: int = 0
    model_routes: int = 0
    mcp_tool_routes: int = 0
    successful_routes: int = 0
    failed_routes: int = 0
    average_decision_time_ms: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def success_rate(self) -> float:
        """Calculate routing success rate."""
        if self.total_queries == 0:
            return 0.0
        return self.successful_routes / self.total_queries
    
    @property
    def agent_route_percentage(self) -> float:
        """Calculate percentage of queries routed to agents."""
        if self.total_queries == 0:
            return 0.0
        return (self.agent_routes / self.total_queries) * 100
    
    def record_route(self, route_type: RouteType, success: bool, decision_time_ms: float):
        """Record a routing decision."""
        self.total_queries += 1
        
        if route_type == RouteType.AGENT:
            self.agent_routes += 1
        elif route_type == RouteType.MODEL:
            self.model_routes += 1
        elif route_type == RouteType.MCP_TOOL:
            self.mcp_tool_routes += 1
        
        if success:
            self.successful_routes += 1
        else:
            self.failed_routes += 1
        
        # Update average decision time
        if self.total_queries == 1:
            self.average_decision_time_ms = decision_time_ms
        else:
            self.average_decision_time_ms = (
                (self.average_decision_time_ms * (self.total_queries - 1) + decision_time_ms)
                / self.total_queries
            )
        
        self.last_updated = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "total_queries": self.total_queries,
            "agent_routes": self.agent_routes,
            "model_routes": self.model_routes,
            "mcp_tool_routes": self.mcp_tool_routes,
            "successful_routes": self.successful_routes,
            "failed_routes": self.failed_routes,
            "success_rate": self.success_rate,
            "agent_route_percentage": self.agent_route_percentage,
            "average_decision_time_ms": self.average_decision_time_ms,
            "last_updated": self.last_updated.isoformat()
        }


class RoutingConfiguration(BaseModel):
    """Configuration for routing behavior."""
    default_strategy: RoutingStrategy = Field(
        default=RoutingStrategy.CAPABILITY_BASED,
        description="Default routing strategy"
    )
    enable_fallback: bool = Field(default=True, description="Enable fallback routing")
    max_decision_time_ms: int = Field(
        default=1000,
        description="Maximum time for routing decision"
    )
    confidence_threshold: float = Field(
        default=0.7,
        description="Minimum confidence for routing decision"
    )
    rules: List[RoutingRule] = Field(
        default_factory=list,
        description="Custom routing rules"
    )
    
    def add_rule(self, rule: RoutingRule):
        """Add a routing rule."""
        self.rules.append(rule)
        # Sort by priority (descending)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    def get_matching_rules(self, query_analysis: QueryAnalysis) -> List[RoutingRule]:
        """Get rules that match the query analysis."""
        return [rule for rule in self.rules if rule.matches_query(query_analysis)]