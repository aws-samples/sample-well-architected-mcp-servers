#!/usr/bin/env python3
"""
Runtime Orchestrator Service - Manages routing between Bedrock Agent and AgentCore Runtime
Provides intelligent orchestration based on environment configuration and request analysis
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from models.chat_models import BedrockResponse, ChatSession

logger = logging.getLogger(__name__)


class RuntimeType(Enum):
    """Enumeration of available runtime types"""
    BEDROCK_AGENT = "bedrock_agent"
    AGENTCORE_RUNTIME = "agentcore_runtime"


@dataclass
class RuntimeConfiguration:
    """Configuration for runtime orchestration"""
    bedrock_agent_enabled: bool
    agentcore_enabled: bool
    priority_runtime: RuntimeType
    fallback_enabled: bool
    keyword_analysis_enabled: bool = True
    health_check_interval: int = 30
    
    def get_enabled_runtimes(self) -> List[RuntimeType]:
        """Get list of enabled runtime types"""
        enabled = []
        if self.bedrock_agent_enabled:
            enabled.append(RuntimeType.BEDROCK_AGENT)
        if self.agentcore_enabled:
            enabled.append(RuntimeType.AGENTCORE_RUNTIME)
        return enabled
    
    def validate(self) -> bool:
        """Validate that at least one runtime is enabled"""
        return self.bedrock_agent_enabled or self.agentcore_enabled


@dataclass
class RoutingDecision:
    """Represents a routing decision made by the orchestrator"""
    selected_runtime: RuntimeType
    confidence_score: float
    reasoning: str
    keyword_matches: List[str]
    health_status: Dict[RuntimeType, bool]
    fallback_used: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "selected_runtime": self.selected_runtime.value,
            "confidence_score": self.confidence_score,
            "reasoning": self.reasoning,
            "keyword_matches": self.keyword_matches,
            "health_status": {rt.value: status for rt, status in self.health_status.items()},
            "fallback_used": self.fallback_used,
            "timestamp": self.timestamp.isoformat()
        }


class RuntimeUnavailableError(Exception):
    """Raised when no healthy runtime types are available"""
    def __init__(self, message: str, available_runtimes: List[RuntimeType] = None):
        super().__init__(message)
        self.available_runtimes = available_runtimes or []


class EnvironmentConfig:
    """Utility class for reading environment configuration"""
    
    @staticmethod
    def get_runtime_config() -> RuntimeConfiguration:
        """Read runtime configuration from environment variables"""
        return RuntimeConfiguration(
            bedrock_agent_enabled=EnvironmentConfig._get_env_bool("ENABLE_BEDROCK_AGENT", True),
            agentcore_enabled=EnvironmentConfig._get_env_bool("ENABLE_BEDROCK_AGENTCORE", True),
            priority_runtime=RuntimeType.AGENTCORE_RUNTIME,  # Default priority
            fallback_enabled=True,
            keyword_analysis_enabled=EnvironmentConfig._get_env_bool("ENABLE_KEYWORD_ANALYSIS", True),
            health_check_interval=int(os.getenv("RUNTIME_HEALTH_CHECK_INTERVAL", "30"))
        )
    
    @staticmethod
    def _get_env_bool(key: str, default: bool) -> bool:
        """Parse boolean environment variable"""
        value = os.getenv(key, str(default)).lower()
        return value in ("true", "1", "yes", "on")


class KeywordAnalyzer:
    """Analyzes user input to determine optimal runtime type"""
    
    def __init__(self):
        self.runtime_keywords = {
            RuntimeType.AGENTCORE_RUNTIME: {
                "high_confidence": [
                    "agentcore", "mcp", "tools", "discovery", "dynamic",
                    "comprehensive", "multi-tool", "orchestration", "runtime"
                ],
                "medium_confidence": [
                    "advanced", "complex", "detailed", "thorough", "complete"
                ],
                "low_confidence": [
                    "analysis", "assessment", "review", "check"
                ]
            },
            RuntimeType.BEDROCK_AGENT: {
                "high_confidence": [
                    "bedrock", "simple", "basic", "quick", "chat", "conversation"
                ],
                "medium_confidence": [
                    "standard", "traditional", "normal", "regular"
                ],
                "low_confidence": [
                    "help", "question", "ask", "tell"
                ]
            }
        }
    
    def calculate_confidence_score(self, message: str, runtime_type: RuntimeType) -> float:
        """Calculate confidence score (0.0 to 1.0) for runtime type selection"""
        message_lower = message.lower()
        keywords = self.runtime_keywords[runtime_type]
        
        score = 0.0
        total_weight = 0.0
        
        # High confidence keywords (weight: 1.0)
        for keyword in keywords["high_confidence"]:
            if keyword in message_lower:
                score += 1.0
                total_weight += 1.0
        
        # Medium confidence keywords (weight: 0.6)
        for keyword in keywords["medium_confidence"]:
            if keyword in message_lower:
                score += 0.6
                total_weight += 0.6
        
        # Low confidence keywords (weight: 0.3)
        for keyword in keywords["low_confidence"]:
            if keyword in message_lower:
                score += 0.3
                total_weight += 0.3
        
        return score / max(total_weight, 1.0) if total_weight > 0 else 0.0
    
    def analyze_message(self, message: str) -> Dict[RuntimeType, float]:
        """Analyze message and return confidence scores for each runtime type"""
        return {
            runtime_type: self.calculate_confidence_score(message, runtime_type)
            for runtime_type in RuntimeType
        }
    
    def get_keyword_matches(self, message: str, runtime_type: RuntimeType) -> List[str]:
        """Get list of matched keywords for a runtime type"""
        message_lower = message.lower()
        keywords = self.runtime_keywords[runtime_type]
        matches = []
        
        for category in ["high_confidence", "medium_confidence", "low_confidence"]:
            for keyword in keywords[category]:
                if keyword in message_lower:
                    matches.append(keyword)
        
        return matches


class RuntimeOrchestratorService:
    """
    Central orchestration service that manages routing between 
    Bedrock Agent Service and AgentCore Runtime Service
    """
    
    def __init__(self):
        # Load configuration from environment variables
        self.config = EnvironmentConfig.get_runtime_config()
        
        # Validate configuration
        if not self.config.validate():
            raise RuntimeUnavailableError("No runtime types are enabled")
        
        # Initialize service references (will be set during startup)
        self.bedrock_agent_service = None
        self.agentcore_service = None
        
        # Initialize keyword analyzer
        self.keyword_analyzer = KeywordAnalyzer()
        
        # Routing statistics
        self.routing_stats = {
            "total_requests": 0,
            "bedrock_agent_requests": 0,
            "agentcore_requests": 0,
            "fallback_requests": 0,
            "failed_requests": 0
        }
        
        # Health check cache
        self.health_cache = {}
        self.health_cache_ttl = self.config.health_check_interval
        
        logger.info(f"Runtime Orchestrator initialized with configuration: "
                   f"Bedrock Agent {'enabled' if self.config.bedrock_agent_enabled else 'disabled'}, "
                   f"AgentCore {'enabled' if self.config.agentcore_enabled else 'disabled'}")
    
    async def initialize_services(self) -> None:
        """Initialize runtime services based on configuration"""
        try:
            if self.config.bedrock_agent_enabled:
                # Import and initialize Bedrock Agent Service
                from services.enhanced_bedrock_agent_service import EnhancedBedrockAgentService
                self.bedrock_agent_service = EnhancedBedrockAgentService()
                logger.info("✓ Bedrock Agent Service initialized")
            
            if self.config.agentcore_enabled:
                # Import and initialize AgentCore services
                from services.strands_llm_orchestrator_service import StrandsLLMOrchestratorService
                self.agentcore_service = StrandsLLMOrchestratorService()
                logger.info("✓ AgentCore Runtime Service initialized")
            
            logger.info("Runtime services initialization complete")
            
        except Exception as e:
            logger.error(f"Failed to initialize runtime services: {e}")
            raise RuntimeUnavailableError(f"Service initialization failed: {e}")
    
    def get_enabled_runtimes(self) -> List[RuntimeType]:
        """Get list of enabled runtime types"""
        return self.config.get_enabled_runtimes()
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics"""
        return {
            **self.routing_stats,
            "configuration": {
                "bedrock_agent_enabled": self.config.bedrock_agent_enabled,
                "agentcore_enabled": self.config.agentcore_enabled,
                "priority_runtime": self.config.priority_runtime.value,
                "fallback_enabled": self.config.fallback_enabled,
                "keyword_analysis_enabled": self.config.keyword_analysis_enabled
            }
        }
    
    async def health_check(self) -> str:
        """Check overall orchestrator health"""
        try:
            enabled_runtimes = self.get_enabled_runtimes()
            
            if not enabled_runtimes:
                return "unhealthy"
            
            # Check health of enabled services
            health_statuses = []
            
            for runtime_type in enabled_runtimes:
                status = await self.check_runtime_health(runtime_type)
                health_statuses.append(status)
            
            # Determine overall health based on individual statuses
            if all(status == "healthy" for status in health_statuses):
                return "healthy"
            elif any(status in ["healthy", "degraded"] for status in health_statuses):
                return "degraded"
            else:
                return "unhealthy"
                
        except Exception as e:
            logger.error(f"Orchestrator health check failed: {e}")
            return "unhealthy"    

    async def check_runtime_health(self, runtime_type: RuntimeType) -> str:
        """Check health status of specified runtime type"""
        try:
            # Check cache first
            cache_key = f"{runtime_type.value}_health"
            now = datetime.utcnow()
            
            if cache_key in self.health_cache:
                cached_result, cached_time = self.health_cache[cache_key]
                if (now - cached_time).total_seconds() < self.health_cache_ttl:
                    return cached_result
            
            # Perform actual health check
            health_status = "unhealthy"
            
            if runtime_type == RuntimeType.AGENTCORE_RUNTIME:
                if not self.config.agentcore_enabled or not self.agentcore_service:
                    health_status = "unhealthy"
                else:
                    health_status = await self.agentcore_service.health_check()
            
            elif runtime_type == RuntimeType.BEDROCK_AGENT:
                if not self.config.bedrock_agent_enabled or not self.bedrock_agent_service:
                    health_status = "unhealthy"
                else:
                    health_status = await self.bedrock_agent_service.health_check()
            
            # Cache the result
            self.health_cache[cache_key] = (health_status, now)
            
            return health_status
            
        except Exception as e:
            logger.warning(f"Health check failed for {runtime_type.value}: {e}")
            return "unhealthy"
    
    def log_environment_config(self):
        """Log the current environment configuration"""
        logger.info(
            f"Runtime configuration: Bedrock Agent {'enabled' if self.config.bedrock_agent_enabled else 'disabled'}, "
            f"AgentCore {'enabled' if self.config.agentcore_enabled else 'disabled'}",
            extra={
                "bedrock_agent_enabled": self.config.bedrock_agent_enabled,
                "agentcore_enabled": self.config.agentcore_enabled,
                "priority_runtime": self.config.priority_runtime.value
            }
        )

    async def analyze_keywords(self, message: str) -> Dict[str, float]:
        """Analyze keywords in message and return confidence scores"""
        if not self.config.keyword_analysis_enabled:
            return {}
        
        try:
            scores = self.keyword_analyzer.analyze_message(message)
            return {rt.value: score for rt, score in scores.items()}
        except Exception as e:
            logger.warning(f"Keyword analysis failed: {e}")
            return {}
    
    async def select_runtime_type(self, message: str) -> RuntimeType:
        """
        Multi-stage runtime selection algorithm:
        1. Check environment configuration
        2. Analyze keywords for runtime preference
        3. Check runtime health status
        4. Apply priority routing rules
        5. Handle fallback scenarios
        """
        
        # Stage 1: Environment Configuration Check
        enabled_runtimes = self.get_enabled_runtimes()
        if len(enabled_runtimes) == 1:
            logger.info(f"Single runtime enabled: {enabled_runtimes[0].value}")
            return enabled_runtimes[0]
        
        # Stage 2: Keyword Analysis
        keyword_scores = await self.analyze_keywords(message)
        
        # Stage 3: Health Status Check
        agentcore_health = await self.check_runtime_health(RuntimeType.AGENTCORE_RUNTIME)
        bedrock_health = await self.check_runtime_health(RuntimeType.BEDROCK_AGENT)
        
        # Consider "healthy" and "degraded" as available for routing
        agentcore_available = agentcore_health in ["healthy", "degraded"]
        bedrock_available = bedrock_health in ["healthy", "degraded"]
        
        health_status = {
            RuntimeType.AGENTCORE_RUNTIME: agentcore_health,
            RuntimeType.BEDROCK_AGENT: bedrock_health
        }
        
        # Stage 4: Priority Routing Decision
        if self.config.agentcore_enabled and agentcore_available:
            # Check if keywords strongly favor Bedrock Agent
            agentcore_score = keyword_scores.get(RuntimeType.AGENTCORE_RUNTIME.value, 0)
            bedrock_score = keyword_scores.get(RuntimeType.BEDROCK_AGENT.value, 0)
            
            if (bedrock_score > agentcore_score + 0.3 and 
                self.config.bedrock_agent_enabled and bedrock_available):
                logger.info(f"Keyword analysis favors Bedrock Agent (score: {bedrock_score:.2f} vs {agentcore_score:.2f})")
                return RuntimeType.BEDROCK_AGENT
            
            logger.info(f"Priority routing to AgentCore Runtime (health: {agentcore_health})")
            return RuntimeType.AGENTCORE_RUNTIME
        
        # Stage 5: Fallback Logic
        if self.config.bedrock_agent_enabled and bedrock_available:
            logger.info(f"Fallback routing to Bedrock Agent (AgentCore health: {agentcore_health})")
            return RuntimeType.BEDROCK_AGENT
        
        # No healthy runtimes available
        raise RuntimeUnavailableError(
            "No healthy runtime types available",
            available_runtimes=enabled_runtimes
        )
    
    def create_routing_decision(
        self, 
        selected_runtime: RuntimeType, 
        message: str, 
        keyword_scores: Dict[str, float],
        health_status: Dict[RuntimeType, bool],
        reasoning: str,
        fallback_used: bool = False
    ) -> RoutingDecision:
        """Create a routing decision object with all relevant information"""
        
        # Get keyword matches for the selected runtime
        keyword_matches = self.keyword_analyzer.get_keyword_matches(message, selected_runtime)
        
        # Calculate confidence score for selected runtime
        confidence_score = keyword_scores.get(selected_runtime.value, 0.0)
        
        return RoutingDecision(
            selected_runtime=selected_runtime,
            confidence_score=confidence_score,
            reasoning=reasoning,
            keyword_matches=keyword_matches,
            health_status=health_status,
            fallback_used=fallback_used
        )
    
    async def process_request(self, message: str, session: ChatSession) -> BedrockResponse:
        """
        Main orchestration method that processes requests through the optimal runtime
        """
        self.routing_stats["total_requests"] += 1
        
        try:
            # Analyze keywords first
            keyword_scores = await self.analyze_keywords(message)
            
            # Select optimal runtime
            selected_runtime = await self.select_runtime_type(message)
            
            # Get health status for logging
            health_status = {
                RuntimeType.AGENTCORE_RUNTIME: await self.check_runtime_health(RuntimeType.AGENTCORE_RUNTIME),
                RuntimeType.BEDROCK_AGENT: await self.check_runtime_health(RuntimeType.BEDROCK_AGENT)
            }
            
            # Create routing decision
            routing_decision = self.create_routing_decision(
                selected_runtime=selected_runtime,
                message=message,
                keyword_scores=keyword_scores,
                health_status=health_status,
                reasoning="Primary runtime selection based on configuration and analysis"
            )
            
            # Log routing decision
            self.log_routing_decision(routing_decision, message)
            
            # Route to selected runtime
            if selected_runtime == RuntimeType.AGENTCORE_RUNTIME:
                return await self.route_to_agentcore(message, session)
            else:
                return await self.route_to_bedrock_agent(message, session)
                
        except RuntimeUnavailableError as e:
            # Try fallback routing
            return await self.attempt_fallback_routing(message, session, str(e))
        except Exception as e:
            self.routing_stats["failed_requests"] += 1
            logger.error(f"Orchestration failed: {e}")
            raise
    
    async def route_to_agentcore(self, message: str, session: ChatSession) -> BedrockResponse:
        """Route request to AgentCore Runtime Service"""
        if not self.agentcore_service:
            raise RuntimeUnavailableError("AgentCore service not initialized")
        
        try:
            self.routing_stats["agentcore_requests"] += 1
            logger.info(f"Routing request to AgentCore Runtime")
            
            response = await self.agentcore_service.process_message(message, session)
            return response
            
        except Exception as e:
            logger.error(f"AgentCore routing failed: {e}")
            # Try fallback if enabled
            if self.config.fallback_enabled:
                return await self.attempt_fallback_routing(message, session, f"AgentCore failed: {e}")
            raise
    
    async def route_to_bedrock_agent(self, message: str, session: ChatSession) -> BedrockResponse:
        """Route request to Bedrock Agent Service"""
        if not self.bedrock_agent_service:
            raise RuntimeUnavailableError("Bedrock Agent service not initialized")
        
        try:
            self.routing_stats["bedrock_agent_requests"] += 1
            logger.info(f"Routing request to Bedrock Agent")
            
            response = await self.bedrock_agent_service.process_message(message, session)
            return response
            
        except Exception as e:
            logger.error(f"Bedrock Agent routing failed: {e}")
            # Try fallback if enabled
            if self.config.fallback_enabled:
                return await self.attempt_fallback_routing(message, session, f"Bedrock Agent failed: {e}")
            raise
    
    async def attempt_fallback_routing(self, message: str, session: ChatSession, reason: str) -> BedrockResponse:
        """Attempt fallback routing when primary runtime fails"""
        if not self.config.fallback_enabled:
            raise RuntimeUnavailableError(f"Fallback disabled. {reason}")
        
        logger.warning(f"Attempting fallback routing. Reason: {reason}")
        self.routing_stats["fallback_requests"] += 1
        
        # Try alternative runtime
        enabled_runtimes = self.get_enabled_runtimes()
        
        for runtime_type in enabled_runtimes:
            try:
                health_status = await self.check_runtime_health(runtime_type)
                if health_status not in ["healthy", "degraded"]:
                    continue
                
                logger.info(f"Fallback routing to {runtime_type.value}")
                
                if runtime_type == RuntimeType.AGENTCORE_RUNTIME and self.agentcore_service:
                    return await self.agentcore_service.process_message(message, session)
                elif runtime_type == RuntimeType.BEDROCK_AGENT and self.bedrock_agent_service:
                    return await self.bedrock_agent_service.process_message(message, session)
                    
            except Exception as e:
                logger.warning(f"Fallback to {runtime_type.value} failed: {e}")
                continue
        
        # All fallback attempts failed
        raise RuntimeUnavailableError(f"All runtime types unavailable. Original reason: {reason}")
    
    def log_routing_decision(self, decision: RoutingDecision, message: str):
        """Log routing decision with comprehensive details"""
        import hashlib
        
        message_hash = hashlib.md5(message.encode()).hexdigest()[:8]
        
        logger.info(
            f"Runtime selection: {decision.selected_runtime.value} "
            f"(confidence: {decision.confidence_score:.2f}, "
            f"reasoning: {decision.reasoning})",
            extra={
                "runtime_type": decision.selected_runtime.value,
                "confidence_score": decision.confidence_score,
                "keyword_matches": decision.keyword_matches,
                "fallback_used": decision.fallback_used,
                "message_hash": message_hash,
                "health_status": {rt.value: status for rt, status in decision.health_status.items()}
            }
        )

    async def process_message(self, message: str, session: ChatSession) -> BedrockResponse:
        """
        Compatibility method that calls process_request
        Maintains compatibility with existing orchestrator interface
        """
        return await self.process_request(message, session)

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get available tools from all enabled runtime services"""
        available_tools = []
        
        try:
            # Get tools from AgentCore service if enabled and available
            if (self.config.agentcore_enabled and 
                self.agentcore_service and 
                hasattr(self.agentcore_service, 'get_available_tools')):
                try:
                    agentcore_tools = await self.agentcore_service.get_available_tools()
                    for tool in agentcore_tools:
                        tool_info = {
                            "name": tool.get("name", ""),
                            "description": tool.get("description", ""),
                            "parameters": tool.get("parameters", {}),
                            "runtime_type": "agentcore_runtime",
                            "server": tool.get("server", "agentcore"),
                            "agent_type": tool.get("agent_type", "unknown")
                        }
                        available_tools.append(tool_info)
                except Exception as e:
                    logger.warning(f"Failed to get tools from AgentCore service: {e}")
            
            # Get tools from Bedrock Agent service if enabled and available
            if (self.config.bedrock_agent_enabled and 
                self.bedrock_agent_service and 
                hasattr(self.bedrock_agent_service, 'get_available_tools')):
                try:
                    bedrock_tools = await self.bedrock_agent_service.get_available_tools()
                    for tool in bedrock_tools:
                        tool_info = {
                            "name": tool.get("name", ""),
                            "description": tool.get("description", ""),
                            "parameters": tool.get("parameters", {}),
                            "runtime_type": "bedrock_agent",
                            "server": tool.get("server", "bedrock"),
                            "agent_type": tool.get("agent_type", "unknown")
                        }
                        available_tools.append(tool_info)
                except Exception as e:
                    logger.warning(f"Failed to get tools from Bedrock Agent service: {e}")
            
            return available_tools
            
        except Exception as e:
            logger.error(f"Failed to get available tools: {e}")
            return []
    
    def get_detailed_health(self) -> Dict[str, Any]:
        """Get detailed health information for the orchestrator"""
        try:
            enabled_runtimes = self.get_enabled_runtimes()
            routing_stats = self.get_routing_stats()
            
            return {
                "orchestrator_type": "runtime_orchestrator",
                "configuration": routing_stats["configuration"],
                "enabled_runtimes": [rt.value for rt in enabled_runtimes],
                "runtime_count": len(enabled_runtimes),
                "routing_statistics": {
                    "total_requests": routing_stats["total_requests"],
                    "bedrock_agent_requests": routing_stats["bedrock_agent_requests"],
                    "agentcore_requests": routing_stats["agentcore_requests"],
                    "fallback_requests": routing_stats["fallback_requests"],
                    "failed_requests": routing_stats["failed_requests"]
                },
                "health_cache_size": len(self.health_cache),
                "health_cache_ttl": self.health_cache_ttl,
                "services_initialized": {
                    "bedrock_agent_service": self.bedrock_agent_service is not None,
                    "agentcore_service": self.agentcore_service is not None
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get detailed health: {e}")
            return {"error": str(e)}