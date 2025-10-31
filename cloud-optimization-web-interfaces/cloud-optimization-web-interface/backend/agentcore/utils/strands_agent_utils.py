"""
Strands Agent utilities for AgentCore integration.
"""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime

from agentcore.models.strands_models import (
    StrandsAgent,
    StrandsAgentType,
    StrandsAgentStatus,
    StrandsAgentCapability
)

logger = logging.getLogger(__name__)


def normalize_agent_name(agent_name: str) -> str:
    """
    Normalize agent name for consistent routing.
    
    Args:
        agent_name: Original agent name
        
    Returns:
        Normalized agent name
    """
    # Convert to lowercase and replace common separators
    normalized = agent_name.lower()
    normalized = re.sub(r'[-_\s]+', '-', normalized)
    
    # Remove common prefixes/suffixes
    normalized = re.sub(r'^(strands?[-_]?)', '', normalized)
    normalized = re.sub(r'[-_]?(agent|service)$', '', normalized)
    
    # Standardize common patterns
    replacements = {
        'aws-api': 'aws-api',
        'awsapi': 'aws-api',
        'api': 'aws-api',
        'wa-sec': 'wa-security',
        'wa-security': 'wa-security',
        'security': 'wa-security',
        'cost-opt': 'cost-optimization',
        'cost-optimization': 'cost-optimization',
        'cost': 'cost-optimization'
    }
    
    for pattern, replacement in replacements.items():
        if pattern in normalized:
            normalized = replacement
            break
    
    return normalized


def match_agent_by_capability(
    query: str,
    available_agents: Dict[str, StrandsAgent]
) -> Optional[Tuple[str, float]]:
    """
    Match agent by capability analysis.
    
    Args:
        query: User query
        available_agents: Available agents
        
    Returns:
        Tuple of (agent_id, confidence_score) or None
    """
    query_lower = query.lower()
    best_match = None
    best_score = 0.0
    
    # Define capability keywords
    capability_keywords = {
        'aws_api': [
            'list', 'describe', 'get', 'show', 'display', 'find', 'search',
            'ec2', 's3', 'rds', 'lambda', 'vpc', 'iam', 'instances', 'buckets',
            'resources', 'api', 'cli', 'aws cli', 'account', 'region'
        ],
        'security': [
            'security', 'vulnerability', 'compliance', 'encryption', 'access',
            'guardduty', 'inspector', 'security hub', 'firewall', 'ssl', 'tls',
            'audit', 'threat', 'malware', 'findings', 'well-architected security'
        ],
        'cost_optimization': [
            'cost', 'billing', 'expense', 'budget', 'savings', 'optimization',
            'rightsizing', 'reserved instance', 'spot instance', 'pricing',
            'spend', 'financial', 'cost explorer', 'billing dashboard'
        ]
    }
    
    for agent_id, agent in available_agents.items():
        if agent.status != StrandsAgentStatus.ACTIVE:
            continue
        
        agent_score = 0.0
        
        # Score based on agent type
        agent_type_str = agent.agent_type.value
        if 'aws_api' in agent_type_str:
            for keyword in capability_keywords['aws_api']:
                if keyword in query_lower:
                    agent_score += 2.0
        elif 'security' in agent_type_str:
            for keyword in capability_keywords['security']:
                if keyword in query_lower:
                    agent_score += 2.0
        elif 'cost' in agent_type_str:
            for keyword in capability_keywords['cost_optimization']:
                if keyword in query_lower:
                    agent_score += 2.0
        
        # Score based on capabilities
        for capability in agent.capabilities:
            capability_score = capability.matches_requirement(query)
            agent_score += capability_score
        
        # Score based on supported domains
        for domain in agent.supported_domains:
            if domain in query_lower:
                agent_score += 1.0
        
        # Score based on supported AWS services
        for service in agent.supported_aws_services:
            if service in query_lower:
                agent_score += 1.5
        
        if agent_score > best_score:
            best_score = agent_score
            best_match = agent_id
    
    return (best_match, best_score) if best_match else None


def get_agent_routing_preferences() -> Dict[str, Dict[str, any]]:
    """
    Get agent routing preferences configuration.
    
    Returns:
        Dictionary of routing preferences
    """
    return {
        "aws_api": {
            "keywords": [
                "list", "describe", "get", "show", "display", "find", "search",
                "ec2", "s3", "rds", "lambda", "vpc", "iam", "cloudformation",
                "instances", "buckets", "databases", "functions", "users", "roles",
                "resources", "infrastructure", "api", "cli", "aws cli",
                "account", "region", "availability zone", "subnet", "security group",
                "load balancer", "auto scaling", "cloudwatch", "logs", "metrics"
            ],
            "agent_patterns": ["aws-api", "api", "strands-aws-api"],
            "priority": 1
        },
        "security": {
            "keywords": [
                "security", "vulnerability", "compliance", "encryption", "access",
                "iam", "guardduty", "inspector", "security hub", "firewall", "vpc",
                "ssl", "tls", "certificate", "audit", "threat", "malware", "findings",
                "well-architected security", "security pillar", "security posture"
            ],
            "agent_patterns": ["wa-security", "security", "strands-wa-sec"],
            "priority": 2
        },
        "cost_optimization": {
            "keywords": [
                "cost", "billing", "expense", "budget", "savings", "optimization",
                "rightsizing", "reserved instance", "spot instance", "pricing",
                "spend", "financial", "money", "dollar", "cheap", "expensive",
                "cost explorer", "billing dashboard", "cost anomaly"
            ],
            "agent_patterns": ["cost-optimization", "cost", "strands-cost"],
            "priority": 3
        },
        "cross_domain": {
            "keywords": [
                "assessment", "review", "analysis", "comprehensive", "overall",
                "complete", "full", "entire", "all", "everything", "summary",
                "both security and cost", "security and cost", "multi-pillar"
            ],
            "agent_patterns": ["wa-sec-cost", "multi", "comprehensive"],
            "priority": 4
        }
    }


def find_best_agent_match(
    query: str,
    available_agents: Dict[str, StrandsAgent],
    routing_preferences: Optional[Dict[str, Dict[str, any]]] = None
) -> Optional[Tuple[str, str, float]]:
    """
    Find the best agent match for a query.
    
    Args:
        query: User query
        available_agents: Available agents
        routing_preferences: Optional routing preferences
        
    Returns:
        Tuple of (agent_id, reason, confidence_score) or None
    """
    if not available_agents:
        return None
    
    if not routing_preferences:
        routing_preferences = get_agent_routing_preferences()
    
    query_lower = query.lower()
    best_matches = []
    
    # Score agents based on routing preferences
    for domain, prefs in routing_preferences.items():
        domain_score = 0.0
        matched_keywords = []
        
        # Calculate keyword matches
        for keyword in prefs["keywords"]:
            if keyword in query_lower:
                domain_score += 1.0
                matched_keywords.append(keyword)
        
        if domain_score > 0:
            # Find agents matching this domain
            for agent_id, agent in available_agents.items():
                if agent.status != StrandsAgentStatus.ACTIVE:
                    continue
                
                agent_match_score = 0.0
                
                # Check if agent matches domain patterns
                normalized_name = normalize_agent_name(agent_id)
                for pattern in prefs["agent_patterns"]:
                    if pattern in normalized_name or pattern in agent.agent_name.lower():
                        agent_match_score += 2.0
                        break
                
                # Check agent type compatibility
                agent_type_str = agent.agent_type.value
                if domain == "aws_api" and "aws_api" in agent_type_str:
                    agent_match_score += 3.0
                elif domain == "security" and "security" in agent_type_str:
                    agent_match_score += 3.0
                elif domain == "cost_optimization" and "cost" in agent_type_str:
                    agent_match_score += 3.0
                
                # Check capabilities
                for capability in agent.capabilities:
                    cap_score = capability.matches_requirement(query)
                    agent_match_score += cap_score
                
                if agent_match_score > 0:
                    total_score = domain_score * agent_match_score * prefs["priority"]
                    reason = f"Domain: {domain}, Keywords: {matched_keywords}, Agent match: {agent_match_score:.1f}"
                    best_matches.append((agent_id, reason, total_score))
    
    # Sort by score and return best match
    if best_matches:
        best_matches.sort(key=lambda x: x[2], reverse=True)
        return best_matches[0]
    
    # Fallback to capability-based matching
    capability_match = match_agent_by_capability(query, available_agents)
    if capability_match:
        agent_id, score = capability_match
        return (agent_id, f"Capability-based match (score: {score:.1f})", score)
    
    # Last resort: any healthy agent
    for agent_id, agent in available_agents.items():
        if agent.status == StrandsAgentStatus.ACTIVE:
            return (agent_id, "Fallback to healthy agent", 0.1)
    
    return None


def validate_agent_health(agent: StrandsAgent) -> Dict[str, any]:
    """
    Validate agent health and return status.
    
    Args:
        agent: Agent to validate
        
    Returns:
        Health validation result
    """
    issues = []
    warnings = []
    
    # Check basic agent properties
    if not agent.agent_id:
        issues.append("Missing agent ID")
    
    if not agent.agent_name:
        issues.append("Missing agent name")
    
    if not agent.agent_arn:
        issues.append("Missing agent ARN")
    
    # Check agent status
    if agent.status not in [StrandsAgentStatus.ACTIVE, StrandsAgentStatus.DEPLOYED]:
        warnings.append(f"Agent status is {agent.status.value}")
    
    # Check capabilities
    if not agent.capabilities:
        warnings.append("Agent has no capabilities defined")
    
    # Check supported services
    if not agent.supported_aws_services:
        warnings.append("Agent has no supported AWS services defined")
    
    # Check last update time
    if agent.last_updated:
        time_since_update = datetime.utcnow() - agent.last_updated
        if time_since_update.total_seconds() > 3600:  # 1 hour
            warnings.append(f"Agent not updated for {time_since_update}")
    
    return {
        "healthy": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "status": agent.status.value,
        "last_updated": agent.last_updated.isoformat() if agent.last_updated else None
    }


def get_agent_compatibility_matrix() -> Dict[str, List[str]]:
    """
    Get agent compatibility matrix for different query types.
    
    Returns:
        Dictionary mapping query types to compatible agent types
    """
    return {
        "list_resources": ["aws_api_agent", "general_purpose_agent"],
        "security_assessment": ["wa_security_agent", "general_purpose_agent"],
        "cost_analysis": ["cost_optimization_agent", "general_purpose_agent"],
        "compliance_check": ["wa_security_agent", "general_purpose_agent"],
        "resource_optimization": ["cost_optimization_agent", "aws_api_agent"],
        "infrastructure_query": ["aws_api_agent", "general_purpose_agent"],
        "multi_domain_analysis": ["general_purpose_agent"]
    }


def classify_query_type(query: str) -> str:
    """
    Classify query type for agent routing.
    
    Args:
        query: User query
        
    Returns:
        Query type classification
    """
    query_lower = query.lower()
    
    # Security-related queries
    security_keywords = ["security", "vulnerability", "compliance", "threat", "audit"]
    if any(keyword in query_lower for keyword in security_keywords):
        return "security_assessment"
    
    # Cost-related queries
    cost_keywords = ["cost", "billing", "budget", "savings", "optimization", "pricing"]
    if any(keyword in query_lower for keyword in cost_keywords):
        return "cost_analysis"
    
    # Resource listing queries
    list_keywords = ["list", "show", "display", "get", "describe", "find"]
    if any(keyword in query_lower for keyword in list_keywords):
        return "list_resources"
    
    # Compliance queries
    compliance_keywords = ["compliance", "compliant", "policy", "rule", "standard"]
    if any(keyword in query_lower for keyword in compliance_keywords):
        return "compliance_check"
    
    # Optimization queries
    optimization_keywords = ["optimize", "improve", "rightsizing", "recommendation"]
    if any(keyword in query_lower for keyword in optimization_keywords):
        return "resource_optimization"
    
    # Infrastructure queries
    infra_keywords = ["infrastructure", "architecture", "deployment", "configuration"]
    if any(keyword in query_lower for keyword in infra_keywords):
        return "infrastructure_query"
    
    # Multi-domain queries
    multi_keywords = ["comprehensive", "complete", "overall", "analysis", "assessment"]
    if any(keyword in query_lower for keyword in multi_keywords):
        return "multi_domain_analysis"
    
    return "general_query"


def create_agent_routing_report(
    available_agents: Dict[str, StrandsAgent],
    query: str,
    selected_agent: Optional[str] = None
) -> Dict[str, any]:
    """
    Create a detailed agent routing report.
    
    Args:
        available_agents: Available agents
        query: User query
        selected_agent: Selected agent ID
        
    Returns:
        Routing report
    """
    query_type = classify_query_type(query)
    compatibility_matrix = get_agent_compatibility_matrix()
    compatible_agents = compatibility_matrix.get(query_type, [])
    
    agent_analysis = {}
    for agent_id, agent in available_agents.items():
        health = validate_agent_health(agent)
        capability_match = match_agent_by_capability(query, {agent_id: agent})
        
        agent_analysis[agent_id] = {
            "agent_type": agent.agent_type.value,
            "status": agent.status.value,
            "health": health,
            "capability_match": capability_match[1] if capability_match else 0.0,
            "compatible": agent.agent_type.value in compatible_agents,
            "capabilities_count": len(agent.capabilities),
            "supported_services_count": len(agent.supported_aws_services)
        }
    
    return {
        "query": query,
        "query_type": query_type,
        "compatible_agent_types": compatible_agents,
        "selected_agent": selected_agent,
        "available_agents_count": len(available_agents),
        "healthy_agents_count": sum(1 for a in agent_analysis.values() if a["health"]["healthy"]),
        "agent_analysis": agent_analysis,
        "routing_timestamp": datetime.utcnow().isoformat()
    }