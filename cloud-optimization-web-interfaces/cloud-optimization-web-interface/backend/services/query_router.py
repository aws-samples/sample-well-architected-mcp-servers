"""
Query Router for intelligent routing between models and agents.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

from models.data_models import QueryRoute, RouteType, ChatMessage, CommandResponse
from models.exceptions import QueryRouterError
from services.agent_manager import AgentManager


logger = logging.getLogger(__name__)


class QueryRouter:
    """Routes queries between Bedrock models and agents based on content analysis."""
    
    def __init__(self, agent_manager: AgentManager):
        """
        Initialize the Query Router.
        
        Args:
            agent_manager: AgentManager instance for agent operations
        """
        self.agent_manager = agent_manager
        
        # Patterns that indicate agent usage
        self.agent_patterns = [
            r'\b(analyze|analysis|assessment|evaluate|check|scan|audit|review)\b',
            r'\b(security|cost|performance|reliability|operational)\b',
            r'\b(aws|amazon|cloud|infrastructure|resource)\b',
            r'\b(optimize|optimization|recommend|suggestion|best practice)\b',
            r'\b(compliance|policy|governance|risk)\b',
            r'\b(s3|ec2|lambda|rds|vpc|iam|cloudformation)\b'
        ]
        
        # Patterns that indicate simple queries
        self.simple_patterns = [
            r'^\s*(hi|hello|hey|good morning|good afternoon|good evening)\b',
            r'^\s*(what is|what are|who is|who are|when is|when are|where is|where are|why is|why are|how is|how are)\b',
            r'^\s*(thank you|thanks|bye|goodbye|see you)\b',
            r'^\s*(yes|no|ok|okay|sure|fine)\s*$',
            r'^\s*\?\s*$'
        ]
        
        # Agent command patterns
        self.command_patterns = {
            'select': r'^/agent\s+select\s+(\S+)(?:\s+(.*))?$',
            'list': r'^/agent\s+list\s*$',
            'clear': r'^/agent\s+clear\s*$',
            'help': r'^/agent\s+help\s*$'
        }
        
        logger.info("QueryRouter initialized")

    async def route_query(
        self, 
        query: str, 
        session_id: str, 
        conversation_history: List[ChatMessage] = None
    ) -> QueryRoute:
        """
        Determine how to route a query based on content analysis.
        
        Args:
            query: User query text
            session_id: Session identifier
            conversation_history: Previous conversation messages
            
        Returns:
            QueryRoute object with routing decision
        """
        try:
            logger.debug(f"Routing query for session {session_id}: {query[:100]}...")
            
            # Check if it's an agent command
            if query.strip().startswith('/agent'):
                return QueryRoute(
                    route_type=RouteType.AGENT,
                    target="command_processor",
                    reasoning="Agent command detected",
                    requires_streaming=False,
                    confidence=1.0
                )
            
            # Check for selected agent
            selected_agent = self.agent_manager.get_selected_agent(session_id)
            if selected_agent:
                # Route to selected agent
                return QueryRoute(
                    route_type=RouteType.AGENT,
                    target=selected_agent,
                    reasoning=f"Using selected agent: {selected_agent}",
                    requires_streaming=True,
                    confidence=1.0
                )
            
            # Analyze query complexity and content
            should_use_agent, confidence, reasoning = await self.should_use_agent(
                query, conversation_history
            )
            
            if should_use_agent:
                # Select best agent for the query
                agent_id = await self.select_best_agent(query, conversation_history)
                return QueryRoute(
                    route_type=RouteType.AGENT,
                    target=agent_id,
                    reasoning=reasoning,
                    requires_streaming=True,
                    confidence=confidence
                )
            else:
                # Route to appropriate model
                model_id = self.select_model_for_query(query, conversation_history)
                return QueryRoute(
                    route_type=RouteType.MODEL,
                    target=model_id,
                    reasoning=reasoning,
                    requires_streaming=False,
                    confidence=confidence
                )
                
        except Exception as e:
            logger.error(f"Error routing query: {e}")
            # Fallback to lightweight model
            return QueryRoute(
                route_type=RouteType.MODEL,
                target="anthropic.claude-3-haiku-20240307-v1:0",
                reasoning=f"Fallback due to routing error: {e}",
                requires_streaming=False,
                confidence=0.5
            )

    async def should_use_agent(
        self, 
        query: str, 
        conversation_history: List[ChatMessage] = None
    ) -> Tuple[bool, float, str]:
        """
        Determine if query should be routed to an agent.
        
        Args:
            query: User query text
            conversation_history: Previous conversation messages
            
        Returns:
            Tuple of (should_use_agent, confidence, reasoning)
        """
        try:
            query_lower = query.lower()
            
            # Check for simple patterns first
            for pattern in self.simple_patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    return False, 0.9, "Simple greeting or basic question detected"
            
            # Check for agent-indicating patterns
            agent_score = 0
            matched_patterns = []
            
            for pattern in self.agent_patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    agent_score += 1
                    matched_patterns.append(pattern)
            
            # Consider query length and complexity
            word_count = len(query.split())
            if word_count > 20:
                agent_score += 0.5
            
            # Consider conversation context
            if conversation_history:
                recent_messages = conversation_history[-3:]  # Last 3 messages
                for msg in recent_messages:
                    if msg.role == "user":
                        for pattern in self.agent_patterns:
                            if re.search(pattern, msg.content.lower(), re.IGNORECASE):
                                agent_score += 0.3
                                break
            
            # Determine if should use agent
            if agent_score >= 1.5:
                confidence = min(0.9, 0.6 + (agent_score * 0.1))
                reasoning = f"Complex query detected (score: {agent_score:.1f}, patterns: {len(matched_patterns)})"
                return True, confidence, reasoning
            else:
                confidence = 0.8 - (agent_score * 0.2)
                reasoning = f"Simple query detected (score: {agent_score:.1f})"
                return False, confidence, reasoning
                
        except Exception as e:
            logger.error(f"Error in should_use_agent analysis: {e}")
            return False, 0.5, f"Analysis error: {e}"

    def select_model_for_query(
        self, 
        query: str, 
        conversation_history: List[ChatMessage] = None
    ) -> str:
        """
        Select appropriate Bedrock model for direct invocation.
        
        Args:
            query: User query text
            conversation_history: Previous conversation messages
            
        Returns:
            Model ID string
        """
        try:
            query_lower = query.lower()
            word_count = len(query.split())
            
            # Use lightweight model for simple queries
            if word_count <= 10:
                for pattern in self.simple_patterns:
                    if re.search(pattern, query_lower, re.IGNORECASE):
                        return "anthropic.claude-3-haiku-20240307-v1:0"
            
            # Use standard model for more complex queries
            if word_count > 50 or any(keyword in query_lower for keyword in 
                                    ['explain', 'describe', 'compare', 'analyze', 'detailed']):
                return "anthropic.claude-3-5-sonnet-20241022-v2:0"
            
            # Default to lightweight model
            return "anthropic.claude-3-haiku-20240307-v1:0"
            
        except Exception as e:
            logger.error(f"Error selecting model: {e}")
            return "anthropic.claude-3-haiku-20240307-v1:0"

    async def select_best_agent(
        self, 
        query: str, 
        conversation_history: List[ChatMessage] = None
    ) -> str:
        """
        Select the best agent for a given query.
        
        Args:
            query: User query text
            conversation_history: Previous conversation messages
            
        Returns:
            Agent ID string
        """
        try:
            # Get available agents
            agents = await self.agent_manager.discover_agents()
            
            if not agents:
                logger.warning("No agents available, this should not happen in agent routing")
                raise QueryRouterError("No agents available for routing")
            
            query_lower = query.lower()
            
            # Score agents based on query content
            agent_scores = {}
            
            for agent_id, agent_info in agents.items():
                score = 0
                
                # Score based on capabilities
                for capability in agent_info.capabilities:
                    if capability.lower() in query_lower:
                        score += 2
                    
                    # Partial matches
                    capability_words = capability.lower().split('_')
                    for word in capability_words:
                        if word in query_lower:
                            score += 0.5
                
                # Score based on agent name/description
                if agent_info.name.lower() in query_lower:
                    score += 1
                
                name_words = agent_info.name.lower().split()
                for word in name_words:
                    if word in query_lower:
                        score += 0.3
                
                # Score based on tool count (more tools = more versatile)
                score += agent_info.tool_count * 0.1
                
                agent_scores[agent_id] = score
            
            # Select agent with highest score
            if agent_scores:
                best_agent = max(agent_scores, key=agent_scores.get)
                logger.debug(f"Selected agent {best_agent} with score {agent_scores[best_agent]:.1f}")
                return best_agent
            else:
                # Fallback to first available agent
                return list(agents.keys())[0]
                
        except Exception as e:
            logger.error(f"Error selecting best agent: {e}")
            # Fallback to first available agent
            agents = await self.agent_manager.discover_agents()
            if agents:
                return list(agents.keys())[0]
            else:
                raise QueryRouterError(f"No agents available: {e}")

    async def process_agent_command(self, command: str, session_id: str) -> CommandResponse:
        """
        Process agent-related commands.
        
        Args:
            command: Command string (e.g., "/agent select wa-security-agent")
            session_id: Session identifier
            
        Returns:
            CommandResponse with command result
        """
        try:
            command = command.strip()
            logger.debug(f"Processing agent command: {command}")
            
            # Parse command
            for cmd_type, pattern in self.command_patterns.items():
                match = re.match(pattern, command, re.IGNORECASE)
                if match:
                    if cmd_type == 'select':
                        agent_id = match.group(1)
                        return self.agent_manager.select_agent_for_session(session_id, agent_id)
                    
                    elif cmd_type == 'list':
                        return await self.agent_manager.list_agents(session_id)
                    
                    elif cmd_type == 'clear':
                        return self.agent_manager.clear_agent_selection(session_id)
                    
                    elif cmd_type == 'help':
                        return self._get_agent_help()
            
            # Unknown command
            return CommandResponse(
                success=False,
                message="Unknown agent command. Use '/agent help' for available commands.",
                command_type="unknown"
            )
            
        except Exception as e:
            logger.error(f"Error processing agent command: {e}")
            return CommandResponse(
                success=False,
                message="An error occurred while processing the agent command.",
                command_type="error"
            )

    def _get_agent_help(self) -> CommandResponse:
        """Get help information for agent commands."""
        help_text = """Available agent commands:

/agent list - List all available agents
/agent select <agent_id> - Select a specific agent for this session
/agent clear - Clear agent selection (use intelligent routing)
/agent help - Show this help message

Examples:
/agent list
/agent select wa-security-agent
/agent clear"""
        
        return CommandResponse(
            success=True,
            message=help_text,
            command_type="help"
        )

    def get_routing_stats(self) -> Dict[str, any]:
        """
        Get routing statistics and metrics.
        
        Returns:
            Dictionary with routing statistics
        """
        # This would be enhanced with actual metrics tracking
        return {
            "total_routes": 0,
            "model_routes": 0,
            "agent_routes": 0,
            "command_routes": 0,
            "average_confidence": 0.0,
            "routing_patterns": {
                "agent_patterns": len(self.agent_patterns),
                "simple_patterns": len(self.simple_patterns),
                "command_patterns": len(self.command_patterns)
            }
        }