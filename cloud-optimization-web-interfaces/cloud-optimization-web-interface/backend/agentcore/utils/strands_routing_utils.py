"""
Utility functions for Strands agent routing and selection.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from agentcore.models.agentcore_routing import (
    QueryDomain,
    StrandsQueryAnalysis,
    StrandsAgentRoute,
    StrandsRouteType,
    AgentSelectionStrategy,
    StrandsAgentMatch,
    StrandsRoutingRule
)
from agentcore.models.strands_models import StrandsAgent

logger = logging.getLogger(__name__)


class StrandsQueryAnalyzer:
    """Analyzer for user queries to determine routing requirements."""
    
    def __init__(self):
        """Initialize the query analyzer with domain patterns."""
        self.domain_patterns = {
            QueryDomain.SECURITY: [
                r'\b(security|secure|vulnerability|threat|compliance|encryption|iam|access|permission|policy|audit|guard|inspector|macie)\b',
                r'\b(well.?architected.?security|wa.?security)\b',
                r'\b(security.?(group|hub|finding|assessment|posture))\b'
            ],
            QueryDomain.COST_OPTIMIZATION: [
                r'\b(cost|billing|price|pricing|budget|spend|saving|optimize|optimization|reserved|instance|ri|savings.?plan)\b',
                r'\b(well.?architected.?cost|wa.?cost)\b',
                r'\b(cost.?(explorer|optimization|anomaly|budget))\b'
            ],
            QueryDomain.RELIABILITY: [
                r'\b(reliability|reliable|availability|resilience|disaster|recovery|backup|failover|redundancy)\b',
                r'\b(well.?architected.?reliability|wa.?reliability)\b',
                r'\b(rto|rpo|sla|uptime|downtime)\b'
            ],
            QueryDomain.PERFORMANCE: [
                r'\b(performance|latency|throughput|speed|optimization|monitoring|metrics|cloudwatch)\b',
                r'\b(well.?architected.?performance|wa.?performance)\b',
                r'\b(performance.?(efficiency|optimization|monitoring))\b'
            ],
            QueryDomain.SUSTAINABILITY: [
                r'\b(sustainability|sustainable|carbon|energy|efficiency|green|environmental)\b',
                r'\b(well.?architected.?sustainability|wa.?sustainability)\b'
            ]
        }
        
        self.aws_service_patterns = {
            'ec2': r'\b(ec2|elastic.?compute|instance|ami|ebs|elastic.?block.?storage)\b',
            's3': r'\b(s3|simple.?storage|bucket)\b',
            'rds': r'\b(rds|relational.?database|aurora|mysql|postgresql|oracle|sql.?server)\b',
            'lambda': r'\b(lambda|serverless|function)\b',
            'iam': r'\b(iam|identity|access|management|user|role|policy|permission)\b',
            'vpc': r'\b(vpc|virtual.?private.?cloud|subnet|security.?group|nacl|route.?table)\b',
            'cloudformation': r'\b(cloudformation|cfn|stack|template)\b',
            'cloudwatch': r'\b(cloudwatch|monitoring|metrics|logs|alarms)\b',
            'guardduty': r'\b(guardduty|guard.?duty|threat.?detection)\b',
            'inspector': r'\b(inspector|vulnerability.?assessment)\b',
            'securityhub': r'\b(security.?hub|security.?findings)\b',
            'macie': r'\b(macie|data.?classification|pii)\b',
            'config': r'\b(config|configuration|compliance|rules)\b',
            'cloudtrail': r'\b(cloudtrail|audit.?log|api.?calls)\b'
        }
        
        self.capability_patterns = {
            'security_assessment': [
                r'\b(security.?(assessment|analysis|evaluation|review|audit))\b',
                r'\b(assess.?(security|compliance))\b',
                r'\b(security.?posture)\b'
            ],
            'cost_analysis': [
                r'\b(cost.?(analysis|breakdown|optimization|review))\b',
                r'\b(analyze.?cost|cost.?explorer)\b',
                r'\b(spending.?(analysis|optimization))\b'
            ],
            'resource_discovery': [
                r'\b(discover|find|list|inventory).*(resource|service|instance)\b',
                r'\b(resource.?(discovery|inventory))\b'
            ],
            'compliance_check': [
                r'\b(compliance|compliant|non.?compliant|violation)\b',
                r'\b(check.?compliance|compliance.?status)\b'
            ],
            'recommendation': [
                r'\b(recommend|suggestion|advice|best.?practice)\b',
                r'\b(optimization.?recommendation)\b'
            ]
        }
    
    def analyze_query(self, query: str) -> StrandsQueryAnalysis:
        """
        Analyze a user query to determine routing requirements.
        
        Args:
            query: User query string
            
        Returns:
            StrandsQueryAnalysis with extracted information
        """
        query_lower = query.lower()
        
        # Detect domain
        domain = self._detect_domain(query_lower)
        
        # Extract keywords
        keywords = self._extract_keywords(query_lower)
        
        # Detect intent
        intent = self._detect_intent(query_lower)
        
        # Extract required capabilities
        capabilities = self._extract_capabilities(query_lower)
        
        # Extract AWS services
        aws_services = self._extract_aws_services(query_lower)
        
        # Calculate complexity score
        complexity = self._calculate_complexity(query, keywords, capabilities, aws_services)
        
        # Determine urgency
        urgency = self._detect_urgency(query_lower)
        
        # Check if context is required
        context_required = self._requires_context(query_lower)
        
        analysis = StrandsQueryAnalysis(
            query=query,
            domain=domain,
            keywords=keywords,
            intent=intent,
            required_capabilities=capabilities,
            aws_services=aws_services,
            complexity_score=complexity,
            urgency_level=urgency,
            context_required=context_required
        )
        
        logger.debug(f"Query analysis completed: domain={domain}, capabilities={capabilities}")
        return analysis
    
    def _detect_domain(self, query_lower: str) -> QueryDomain:
        """Detect the primary domain of the query."""
        domain_scores = {}
        
        for domain, patterns in self.domain_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, query_lower, re.IGNORECASE))
                score += matches
            domain_scores[domain] = score
        
        # Return domain with highest score, default to GENERAL
        if domain_scores and max(domain_scores.values()) > 0:
            return max(domain_scores, key=domain_scores.get)
        
        return QueryDomain.GENERAL
    
    def _extract_keywords(self, query_lower: str) -> List[str]:
        """Extract relevant keywords from the query."""
        keywords = []
        
        # Extract AWS service keywords
        for service, pattern in self.aws_service_patterns.items():
            if re.search(pattern, query_lower, re.IGNORECASE):
                keywords.append(service)
        
        # Extract domain-specific keywords
        for domain, patterns in self.domain_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, query_lower, re.IGNORECASE)
                keywords.extend(matches)
        
        # Remove duplicates and return
        return list(set(keywords))
    
    def _detect_intent(self, query_lower: str) -> str:
        """Detect the user's intent from the query."""
        intent_patterns = {
            'analyze': r'\b(analyze|analysis|examine|review|assess|evaluate)\b',
            'list': r'\b(list|show|display|get|find|discover)\b',
            'check': r'\b(check|verify|validate|test|confirm)\b',
            'optimize': r'\b(optimize|improve|enhance|reduce|minimize)\b',
            'configure': r'\b(configure|setup|create|deploy|implement)\b',
            'troubleshoot': r'\b(troubleshoot|debug|fix|resolve|solve)\b',
            'monitor': r'\b(monitor|track|watch|observe|alert)\b'
        }
        
        for intent, pattern in intent_patterns.items():
            if re.search(pattern, query_lower, re.IGNORECASE):
                return intent
        
        return 'general_inquiry'
    
    def _extract_capabilities(self, query_lower: str) -> List[str]:
        """Extract required capabilities from the query."""
        capabilities = []
        
        for capability, patterns in self.capability_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    capabilities.append(capability)
                    break
        
        return capabilities
    
    def _extract_aws_services(self, query_lower: str) -> List[str]:
        """Extract AWS services mentioned in the query."""
        services = []
        
        for service, pattern in self.aws_service_patterns.items():
            if re.search(pattern, query_lower, re.IGNORECASE):
                services.append(service)
        
        return services
    
    def _calculate_complexity(
        self,
        query: str,
        keywords: List[str],
        capabilities: List[str],
        aws_services: List[str]
    ) -> float:
        """Calculate query complexity score (0-1)."""
        base_score = 0.3
        
        # Length factor
        length_factor = min(len(query) / 200, 0.3)
        
        # Keyword factor
        keyword_factor = min(len(keywords) / 10, 0.2)
        
        # Capability factor
        capability_factor = min(len(capabilities) / 5, 0.2)
        
        # AWS service factor
        service_factor = min(len(aws_services) / 5, 0.2)
        
        # Multi-domain queries are more complex
        multi_domain_factor = 0.1 if len(set(keywords)) > 3 else 0
        
        complexity = base_score + length_factor + keyword_factor + capability_factor + service_factor + multi_domain_factor
        return min(complexity, 1.0)
    
    def _detect_urgency(self, query_lower: str) -> str:
        """Detect urgency level from the query."""
        urgent_patterns = [
            r'\b(urgent|emergency|critical|immediate|asap|now|quickly)\b',
            r'\b(production.?(down|issue|problem))\b',
            r'\b(security.?(breach|incident|alert))\b'
        ]
        
        for pattern in urgent_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return 'high'
        
        return 'normal'
    
    def _requires_context(self, query_lower: str) -> bool:
        """Determine if the query requires additional context."""
        context_patterns = [
            r'\b(my|our|this|current|existing)\b.*\b(account|environment|setup|configuration)\b',
            r'\b(what.?is|how.?many|show.?me)\b.*\b(resource|service|instance|bucket)\b',
            r'\b(analyze|assess|review)\b.*\b(my|our|current)\b'
        ]
        
        for pattern in context_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return True
        
        return False


class StrandsAgentMatcher:
    """Matcher for finding the best Strands agent for a query."""
    
    def __init__(self):
        """Initialize the agent matcher."""
        self.last_used_agents = {}
        self.agent_load_balancer = {}
    
    def find_best_matches(
        self,
        query_analysis: StrandsQueryAnalysis,
        available_agents: List[StrandsAgent],
        max_matches: int = 3
    ) -> List[StrandsAgentMatch]:
        """
        Find the best matching agents for a query.
        
        Args:
            query_analysis: Analyzed query information
            available_agents: List of available Strands agents
            max_matches: Maximum number of matches to return
            
        Returns:
            List of StrandsAgentMatch objects sorted by score
        """
        matches = []
        
        for agent in available_agents:
            match = self._calculate_agent_match(query_analysis, agent)
            if match.match_score > 0:
                matches.append(match)
        
        # Sort by overall score and return top matches
        matches.sort(key=lambda x: x.overall_score, reverse=True)
        return matches[:max_matches]
    
    def _calculate_agent_match(
        self,
        query_analysis: StrandsQueryAnalysis,
        agent: StrandsAgent
    ) -> StrandsAgentMatch:
        """Calculate match score for a specific agent."""
        match_score = 0.0
        matched_capabilities = []
        missing_capabilities = []
        
        # Check capability matches
        for required_capability in query_analysis.required_capabilities:
            best_match_score = 0.0
            best_match_capability = None
            
            for agent_capability in agent.capabilities:
                capability_score = agent_capability.matches_requirement(required_capability)
                if capability_score > best_match_score:
                    best_match_score = capability_score
                    best_match_capability = agent_capability.name
            
            if best_match_score > 0.5:
                match_score += best_match_score
                if best_match_capability:
                    matched_capabilities.append(best_match_capability)
            else:
                missing_capabilities.append(required_capability)
        
        # Check domain match
        if hasattr(agent, 'supported_domains') and query_analysis.domain in agent.supported_domains:
            match_score += 0.3
        
        # Check AWS service support
        if hasattr(agent, 'supported_aws_services'):
            service_matches = len(set(query_analysis.aws_services) & set(agent.supported_aws_services))
            if service_matches > 0:
                match_score += min(service_matches * 0.1, 0.2)
        
        # Normalize match score
        if query_analysis.required_capabilities:
            match_score = match_score / len(query_analysis.required_capabilities)
        else:
            match_score = 0.5  # Default score for general queries
        
        match_score = min(match_score, 1.0)
        
        # Calculate availability score
        availability_score = self._calculate_availability_score(agent)
        
        return StrandsAgentMatch(
            agent_id=agent.agent_id,
            agent_name=agent.agent_name,
            agent_type=agent.agent_type,
            match_score=match_score,
            matched_capabilities=matched_capabilities,
            missing_capabilities=missing_capabilities,
            availability_score=availability_score,
            last_used=self.last_used_agents.get(agent.agent_id)
        )
    
    def _calculate_availability_score(self, agent: StrandsAgent) -> float:
        """Calculate availability score for an agent."""
        # Check if agent was used recently (load balancing)
        agent_id = agent.agent_id
        last_used = self.last_used_agents.get(agent_id)
        
        if last_used:
            time_since_use = datetime.utcnow() - last_used
            if time_since_use < timedelta(minutes=5):
                return 0.7  # Slightly lower score for recently used agents
        
        # Check agent health if available
        if hasattr(agent, 'health') and agent.health:
            if not agent.health.is_healthy:
                return 0.3
            
            # Factor in current load
            load_factor = 1.0 - (agent.health.load_percentage / 100) * 0.3
            return max(load_factor, 0.5)
        
        return 1.0  # Default availability score
    
    def record_agent_usage(self, agent_id: str):
        """Record that an agent was used."""
        self.last_used_agents[agent_id] = datetime.utcnow()


class StrandsRoutingRuleEngine:
    """Rule engine for Strands agent routing decisions."""
    
    def __init__(self):
        """Initialize the routing rule engine."""
        self.rules = []
        self._load_default_rules()
    
    def add_rule(self, rule: StrandsRoutingRule):
        """Add a routing rule."""
        self.rules.append(rule)
        # Sort rules by priority (higher priority first)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    def find_matching_rules(self, query_analysis: StrandsQueryAnalysis) -> List[StrandsRoutingRule]:
        """Find all rules that match the query analysis."""
        matching_rules = []
        
        for rule in self.rules:
            if rule.matches_query(query_analysis):
                matching_rules.append(rule)
        
        return matching_rules
    
    def _load_default_rules(self):
        """Load default routing rules."""
        # Security domain rules
        security_rule = StrandsRoutingRule(
            name="Security Assessment Rule",
            description="Route security-related queries to WA Security agent",
            keywords=["security", "compliance", "vulnerability", "threat"],
            domains=[QueryDomain.SECURITY],
            target_agent_type="wa_security_agent",
            priority=100,
            enabled=True
        )
        self.add_rule(security_rule)
        
        # Cost optimization rules
        cost_rule = StrandsRoutingRule(
            name="Cost Optimization Rule",
            description="Route cost-related queries to Cost Optimization agent",
            keywords=["cost", "billing", "optimization", "savings"],
            domains=[QueryDomain.COST_OPTIMIZATION],
            target_agent_type="cost_optimization_agent",
            priority=90,
            enabled=True
        )
        self.add_rule(cost_rule)
        
        # AWS API rules
        aws_api_rule = StrandsRoutingRule(
            name="AWS API Operations Rule",
            description="Route AWS API queries to AWS API agent",
            keywords=["list", "describe", "get", "create", "delete"],
            target_agent_type="aws_api_agent",
            priority=80,
            enabled=True,
            conditions={"complexity_max": 0.7}
        )
        self.add_rule(aws_api_rule)


def create_fallback_route(
    reasoning: str,
    parameter_prefix: str = "coa"
) -> StrandsAgentRoute:
    """
    Create a fallback route to model when no suitable agent is found.
    
    Args:
        reasoning: Reason for fallback
        parameter_prefix: Parameter prefix to use
        
    Returns:
        StrandsAgentRoute configured for model fallback
    """
    return StrandsAgentRoute(
        route_type=StrandsRouteType.MODEL_FALLBACK,
        target_agent="bedrock_model",
        reasoning=reasoning,
        confidence=0.5,
        requires_context=False,
        estimated_response_time_ms=2000,
        fallback_agents=[],
        parameter_prefix=parameter_prefix
    )


def create_strands_agent_route(
    agent_match: StrandsAgentMatch,
    reasoning: str,
    parameter_prefix: str = "coa",
    fallback_agents: Optional[List[str]] = None
) -> StrandsAgentRoute:
    """
    Create a Strands agent route from an agent match.
    
    Args:
        agent_match: Matched agent information
        reasoning: Reasoning for selection
        parameter_prefix: Parameter prefix to use
        fallback_agents: List of fallback agent IDs
        
    Returns:
        StrandsAgentRoute configured for the matched agent
    """
    return StrandsAgentRoute(
        route_type=StrandsRouteType.STRANDS_AGENT,
        target_agent=agent_match.agent_id,
        reasoning=reasoning,
        confidence=agent_match.overall_score,
        requires_context=True,
        estimated_response_time_ms=int(5000 * (1 - agent_match.availability_score) + 3000),
        fallback_agents=fallback_agents or [],
        parameter_prefix=parameter_prefix
    )


def format_routing_decision_summary(
    decision: 'StrandsRoutingDecision'
) -> str:
    """
    Format a routing decision into a human-readable summary.
    
    Args:
        decision: Routing decision to format
        
    Returns:
        Formatted summary string
    """
    route = decision.selected_route
    analysis = decision.query_analysis
    
    summary_parts = [
        f"Query Domain: {analysis.domain.value.title()}",
        f"Route Type: {route.route_type.value.replace('_', ' ').title()}",
        f"Target: {route.target_agent}",
        f"Confidence: {route.confidence:.2f}",
        f"Decision Time: {decision.decision_time_ms:.1f}ms"
    ]
    
    if analysis.aws_services:
        summary_parts.append(f"AWS Services: {', '.join(analysis.aws_services)}")
    
    if analysis.required_capabilities:
        summary_parts.append(f"Capabilities: {', '.join(analysis.required_capabilities)}")
    
    if route.reasoning:
        summary_parts.append(f"Reasoning: {route.reasoning}")
    
    return " | ".join(summary_parts)