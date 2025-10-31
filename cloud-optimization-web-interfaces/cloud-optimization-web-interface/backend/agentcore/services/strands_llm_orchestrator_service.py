#!/usr/bin/env python3
"""
StrandsAgent LLM Orchestrator Service - Specialized for AgentCore Runtime
Orchestrates requests through StrandsAgents with intelligent routing
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from shared.models.chat_models import (
    BedrockResponse,
    ChatSession,
    ToolExecution,
    ToolExecutionStatus,
)
from shared.services.config_service import get_config
from agentcore.services.strands_agent_discovery_service import StrandsAgentDiscoveryService

logger = logging.getLogger(__name__)


class StrandsLLMOrchestratorService:
    """LLM Orchestrator specialized for StrandsAgent integration"""
    
    def __init__(self):
        self.region = get_config("AWS_DEFAULT_REGION", "us-east-1")
        
        # Initialize StrandsAgent Discovery Service with dynamic parameter prefix
        param_prefix = get_config('PARAM_PREFIX', 'coa')
        self.strands_discovery = StrandsAgentDiscoveryService(region=self.region, param_prefix=param_prefix)
        
        # Agent routing configuration
        self.agent_routing_rules = {
            "aws_api": {
                "keywords": [
                    "list", "describe", "get", "show", "display", "find", "search",
                    "ec2", "s3", "rds", "lambda", "vpc", "iam", "cloudformation",
                    "instances", "buckets", "databases", "functions", "users", "roles",
                    "resources", "infrastructure", "api", "cli", "aws cli",
                    "account", "region", "availability zone", "subnet", "security group",
                    "load balancer", "auto scaling", "cloudwatch", "logs", "metrics"
                ],
                "preferred_agent": "strands-aws-api",  # AWS API operations agent
                "fallback_agent": "strands-aws-api"
            },
            "security": {
                "keywords": [
                    "security", "vulnerability", "compliance", "encryption", "access",
                    "iam", "guardduty", "inspector", "security hub", "firewall", "vpc",
                    "ssl", "tls", "certificate", "audit", "threat", "malware", "findings",
                    "well-architected security", "security pillar", "security posture"
                ],
                "preferred_agent": "strands_aws_wa_sec_cost",  # Dual-domain agent
                "fallback_agent": "strands_security_specialist"
            },
            "cost": {
                "keywords": [
                    "cost", "billing", "expense", "budget", "savings", "optimization",
                    "rightsizing", "reserved instance", "spot instance", "pricing",
                    "spend", "financial", "money", "dollar", "cheap", "expensive",
                    "cost explorer", "billing dashboard", "cost anomaly"
                ],
                "preferred_agent": "strands_aws_wa_sec_cost",  # Dual-domain agent
                "fallback_agent": "strands_cost_specialist"
            },
            "cross_domain": {
                "keywords": [
                    "assessment", "review", "analysis", "comprehensive", "overall",
                    "complete", "full", "entire", "all", "everything", "summary",
                    "both security and cost", "security and cost", "multi-pillar",
                    "cost of security", "security cost impact", "optimization priority"
                ],
                "preferred_agent": "strands_aws_wa_sec_cost",  # Always use dual-domain
                "fallback_agent": "strands_supervisor"
            }
        }
        
        # Tool execution tracking
        self.tool_execution_history: Dict[str, List[Dict[str, Any]]] = {}
        
        logger.info("StrandsAgent LLM Orchestrator Service initialized")

    async def initialize_session(self, session: ChatSession) -> Dict[str, Any]:
        """Initialize session with StrandsAgent discovery"""
        try:
            logger.info(f"Initializing session {session.session_id} with StrandsAgent discovery")
            
            # Discover available StrandsAgents
            agents = await self.strands_discovery.discover_strands_agents()
            logger.info(f"Discovered {len(agents)} agents: {list(agents.keys())}")
            
            # Log detailed agent information
            for agent_type, agent in agents.items():
                logger.info(f"Agent {agent_type}: status={agent.status}, capabilities={agent.capabilities}, domains={list(agent.domains.keys())}")
            
            # Get available tools from all agents
            available_tools = await self.strands_discovery.get_available_tools()
            logger.info(f"Available tools: {len(available_tools)}")
            
            # Set up session context
            session.context["strands_agents"] = {
                agent_type: {
                    "status": agent.status,
                    "capabilities": agent.capabilities,
                    "domains": list(agent.domains.keys()),
                    "available_tools": agent.available_tools
                }
                for agent_type, agent in agents.items()
            }
            
            session.context["available_tools"] = available_tools
            session.context["orchestrator_type"] = "strands_specialized"
            session.context["discovery_time"] = datetime.utcnow().isoformat()
            
            # Generate system prompt for StrandsAgent integration
            system_prompt = self._generate_strands_system_prompt(agents, available_tools)
            session.context["system_prompt"] = system_prompt
            
            healthy_agents = sum(1 for agent in agents.values() if agent.status == "HEALTHY")
            logger.info(f"Session {session.session_id} initialized with {len(agents)} StrandsAgents ({healthy_agents} healthy) and {len(available_tools)} tools")
            
            return {
                "status": "initialized",
                "agents_count": len(agents),
                "tools_count": len(available_tools),
                "healthy_agents": healthy_agents,
                "available_domains": list(set(
                    domain for agent in agents.values() 
                    for domain in agent.domains.keys()
                )),
                "orchestrator_type": "strands_specialized"
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize StrandsAgent session: {e}")
            logger.exception("Full exception details:")
            return {"status": "error", "error": str(e)}

    def _generate_strands_system_prompt(
        self, 
        agents: Dict[str, Any], 
        available_tools: List[Dict[str, Any]]
    ) -> str:
        """Generate system prompt for StrandsAgent integration"""
        
        # Organize tools by domain
        tools_by_domain = {}
        for tool in available_tools:
            domain = tool.get("domain", "general")
            if domain not in tools_by_domain:
                tools_by_domain[domain] = []
            tools_by_domain[domain].append(tool)
        
        # Generate agent summary
        agent_summary = []
        for agent_type, agent in agents.items():
            status_emoji = "✅" if agent.status == "HEALTHY" else "⚠️"
            domains = ", ".join(agent.domains.keys())
            agent_summary.append(f"- **{agent_type}** {status_emoji}: {domains} ({len(agent.available_tools)} tools)")
        
        # Generate tool summary by domain
        tool_summary = []
        for domain, tools in tools_by_domain.items():
            tool_names = [tool["name"] for tool in tools]
            tool_summary.append(f"- **{domain.title()}**: {', '.join(tool_names)}")
        
        return f"""You are an AWS Cloud Optimization Assistant with specialized StrandsAgent integration for comprehensive AWS infrastructure analysis.

**StrandsAgent Architecture:**
You work with specialized StrandsAgents deployed to Amazon Bedrock AgentCore Runtime. Each agent has embedded MCP servers providing domain-specific capabilities.

**Available StrandsAgents:**
{chr(10).join(agent_summary)}

**Available Tools by Domain:**
{chr(10).join(tool_summary)}

**Your Capabilities:**
1. **Intelligent Agent Routing**: Automatically route queries to the most appropriate StrandsAgent
2. **Cross-Domain Analysis**: Leverage dual-domain agents for comprehensive assessments
3. **Tool Orchestration**: Coordinate multiple tool executions across different domains
4. **Contextual Understanding**: Maintain context across multi-step analyses
5. **Optimization Prioritization**: Provide prioritized recommendations based on impact and effort

**Routing Strategy:**
- **Security Queries**: Route to security-capable agents (security domain tools)
- **Cost Queries**: Route to cost-capable agents (cost optimization domain tools)
- **Comprehensive Analysis**: Use dual-domain agents for complete assessments
- **Cross-Domain Questions**: Leverage agents that can analyze both security and cost implications

**Response Guidelines:**
1. **Always determine the best StrandsAgent** for the user's query based on domain and complexity
2. **Use specific tools** through the selected agent to gather concrete data
3. **Provide structured analysis** with clear findings, risks, and recommendations
4. **Include cross-domain insights** when relevant (e.g., cost impact of security measures)
5. **Prioritize recommendations** by business impact and implementation effort

**Tool Execution Protocol:**
- Route tool calls through the appropriate StrandsAgent
- Maintain execution context across multiple tool calls
- Provide human-readable summaries of technical findings
- Include specific resource identifiers and configuration details

**Analysis Framework:**
- Start with broad assessment (CheckSecurityServices, GetCostAnalysis)
- Drill down into specific areas based on findings
- Cross-reference security and cost implications
- Provide actionable, prioritized recommendations

You should proactively suggest comprehensive analyses that span multiple domains when appropriate, leveraging the full capabilities of the StrandsAgent ecosystem."""

    async def process_message(
        self, 
        message: str, 
        session: ChatSession
    ) -> BedrockResponse:
        """Process message through StrandsAgent orchestration"""
        
        try:
            # Initialize session if needed
            if not session.context.get("strands_agents"):
                await self.initialize_session(session)
            
            # Determine the best StrandsAgent for this query
            selected_agent, routing_reason = await self._determine_best_strands_agent(message, session)
            
            if not selected_agent:
                return BedrockResponse(
                    response="I couldn't determine the appropriate StrandsAgent for your query. Please try rephrasing your question with more specific details about security, cost, or infrastructure analysis.",
                    tool_executions=[],
                    model_id="strands-orchestrator",
                    session_id=session.session_id
                )
            
            logger.info(f"Selected StrandsAgent: {selected_agent} (Reason: {routing_reason})")
            
            # Create tool execution record for the agent invocation
            agent_execution = ToolExecution(
                tool_name=f"StrandsAgent_{selected_agent}",
                parameters={"message": message, "routing_reason": routing_reason},
                status=ToolExecutionStatus.PENDING,
                timestamp=datetime.utcnow()
            )
            
            try:
                # Invoke the selected StrandsAgent
                agent_response = await self.strands_discovery.invoke_strands_agent(
                    agent_type=selected_agent,
                    prompt=message,
                    session_id=session.session_id
                )
                
                # Update execution status
                agent_execution.status = ToolExecutionStatus.SUCCESS
                agent_execution.result = agent_response
                
                # Extract structured data and human summary
                structured_data = self._extract_structured_data(agent_response)
                human_summary = self._generate_human_summary(agent_response, selected_agent)
                
                # Include tool execution results in structured data
                if "tool_execution_results" in agent_response:
                    if structured_data is None:
                        structured_data = {}
                    structured_data["tool_execution_results"] = agent_response["tool_execution_results"]
                
                logger.info(f"StrandsAgent {selected_agent} execution successful")
                
                # Enhance response with tool execution summary
                main_response = agent_response.get("response", "Analysis completed successfully.")
                
                # Add tool execution summary if available
                if "tool_execution_results" in agent_response:
                    tool_results = agent_response["tool_execution_results"]
                    if tool_results:
                        main_response += "\n\n## Tool Execution Results\n\n"
                        for tool_name, result in tool_results.items():
                            main_response += f"### {tool_name}\n"
                            if isinstance(result, dict):
                                # Format key findings from tool results
                                if "summary" in result:
                                    main_response += f"**Summary**: {result['summary']}\n\n"
                                if "recommendations" in result:
                                    main_response += "**Recommendations**:\n"
                                    for rec in result["recommendations"]:
                                        main_response += f"- {rec}\n"
                                    main_response += "\n"
                                if "service_statuses" in result:
                                    main_response += "**Service Status**:\n"
                                    for service, status in result["service_statuses"].items():
                                        status_emoji = "✅" if status.get("enabled") else "❌"
                                        main_response += f"- {service}: {status_emoji} {status.get('status', 'Unknown')}\n"
                                    main_response += "\n"
                
                return BedrockResponse(
                    response=main_response,
                    tool_executions=[agent_execution],
                    model_id=f"strands-agent-{selected_agent}",
                    session_id=session.session_id,
                    structured_data=structured_data,
                    human_summary=human_summary
                )
                
            except Exception as e:
                logger.error(f"StrandsAgent {selected_agent} execution failed: {e}")
                agent_execution.status = ToolExecutionStatus.ERROR
                agent_execution.error_message = str(e)
                
                return BedrockResponse(
                    response=f"I encountered an error while processing your request through the {selected_agent} agent: {str(e)}",
                    tool_executions=[agent_execution],
                    model_id="strands-orchestrator-error",
                    session_id=session.session_id
                )
                
        except Exception as e:
            logger.error(f"StrandsAgent orchestration failed: {e}")
            return BedrockResponse(
                response=f"I encountered an error in the orchestration process: {str(e)}",
                tool_executions=[],
                model_id="strands-orchestrator-error",
                session_id=session.session_id
            )

    async def _determine_best_strands_agent(
        self, 
        message: str, 
        session: ChatSession
    ) -> tuple[Optional[str], str]:
        """Determine the best StrandsAgent for processing the message using improved routing"""
        
        # Get available agents from session context
        available_agents_info = session.context.get("strands_agents", {})
        
        logger.info(f"Available agents: {list(available_agents_info.keys())}")
        logger.info(f"Message: {message}")
        
        if not available_agents_info:
            logger.warning("No StrandsAgents available in session context")
            return None, "No StrandsAgents available"
        
        # Convert agent info to StrandsAgent objects for routing utilities
        from agentcore.models.strands_models import StrandsAgent, StrandsAgentStatus, StrandsAgentType
        from agentcore.utils.strands_agent_utils import find_best_agent_match, normalize_agent_name
        
        available_agents = {}
        for agent_id, agent_info in available_agents_info.items():
            try:
                # Create a minimal StrandsAgent object for routing
                agent_status = StrandsAgentStatus.ACTIVE if agent_info.get("status") == "HEALTHY" else StrandsAgentStatus.UNAVAILABLE
                
                # Determine agent type from agent_id
                normalized_name = normalize_agent_name(agent_id)
                if "aws-api" in normalized_name:
                    agent_type = StrandsAgentType.AWS_API
                elif "security" in normalized_name or "wa-sec" in normalized_name:
                    agent_type = StrandsAgentType.WA_SECURITY
                elif "cost" in normalized_name:
                    agent_type = StrandsAgentType.COST_OPTIMIZATION
                else:
                    agent_type = StrandsAgentType.GENERAL_PURPOSE
                
                agent = StrandsAgent(
                    agent_id=agent_id,
                    agent_name=agent_id,
                    agent_arn=f"arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/{agent_id}",
                    agent_type=agent_type,
                    status=agent_status,
                    supported_domains=agent_info.get("domains", []),
                    capabilities=[]  # Will be populated if needed
                )
                
                available_agents[agent_id] = agent
                
            except Exception as e:
                logger.warning(f"Failed to create agent object for {agent_id}: {e}")
                continue
        
        # Log agent statuses for debugging
        for agent_id, agent in available_agents.items():
            logger.info(f"Agent {agent_id}: status={agent.status.value}, type={agent.agent_type.value}")
        
        # Use improved routing logic
        routing_result = find_best_agent_match(message, available_agents)
        
        if routing_result:
            selected_agent, reason, confidence = routing_result
            logger.info(f"Selected agent: {selected_agent} (confidence: {confidence:.2f}, reason: {reason})")
            return selected_agent, f"{reason} (confidence: {confidence:.2f})"
        
        # Fallback to original logic for backward compatibility
        logger.info("Improved routing failed, falling back to original logic")
        
        message_lower = message.lower()
        agent_scores = {}
        matched_keywords = []
        
        for domain, rules in self.agent_routing_rules.items():
            # Calculate keyword match score
            keyword_matches = []
            for keyword in rules["keywords"]:
                if keyword in message_lower:
                    keyword_matches.append(keyword)
            
            if keyword_matches:
                matched_keywords.extend(keyword_matches)
                logger.info(f"Domain '{domain}' matched keywords: {keyword_matches}")
                
                # Check if preferred agent is available and healthy
                preferred_agent = rules["preferred_agent"]
                if preferred_agent in available_agents_info:
                    agent_status = available_agents_info[preferred_agent]["status"]
                    logger.info(f"Preferred agent '{preferred_agent}' status: {agent_status}")
                    
                    if agent_status == "HEALTHY":
                        agent_scores[preferred_agent] = agent_scores.get(preferred_agent, 0) + len(keyword_matches) * 2
                        logger.info(f"Added score for preferred agent '{preferred_agent}': {len(keyword_matches) * 2}")
                
                # Check fallback agent
                fallback_agent = rules["fallback_agent"]
                if fallback_agent in available_agents_info:
                    agent_status = available_agents_info[fallback_agent]["status"]
                    logger.info(f"Fallback agent '{fallback_agent}' status: {agent_status}")
                    
                    if agent_status == "HEALTHY":
                        agent_scores[fallback_agent] = agent_scores.get(fallback_agent, 0) + len(keyword_matches)
                        logger.info(f"Added score for fallback agent '{fallback_agent}': {len(keyword_matches)}")
        
        logger.info(f"Agent scores: {agent_scores}")
        logger.info(f"Matched keywords: {matched_keywords}")
        
        # Select agent with highest score
        if agent_scores:
            best_agent = max(agent_scores.items(), key=lambda x: x[1])
            logger.info(f"Selected best agent: {best_agent[0]} with score {best_agent[1]}")
            return best_agent[0], f"Keyword matching (score: {best_agent[1]}, keywords: {matched_keywords})"
        
        # Fallback: select any healthy agent
        logger.info("No keyword matches, trying any healthy agent")
        for agent_id, agent_info in available_agents_info.items():
            if agent_info["status"] == "HEALTHY":
                logger.info(f"Selected healthy agent: {agent_id}")
                return agent_id, "Fallback to any healthy agent"
        
        # If no healthy agents, try any agent
        logger.warning("No healthy agents found, trying any available agent")
        if available_agents_info:
            first_agent = next(iter(available_agents_info.keys()))
            logger.info(f"Selected first available agent: {first_agent}")
            return first_agent, "Fallback to first available agent (may be unhealthy)"
        
        logger.error("No StrandsAgents available at all")
        return None, "No healthy StrandsAgents available"

    def _extract_structured_data(self, agent_response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract structured data from StrandsAgent response"""
        try:
            structured_data = {
                "agent_type": agent_response.get("agent_type"),
                "domains_analyzed": agent_response.get("domains_analyzed", []),
                "tools_used": agent_response.get("tools_used", []),
                "execution_time_ms": agent_response.get("execution_time_ms", 0),
                "session_id": agent_response.get("session_id"),
                "status": agent_response.get("status", "unknown")
            }
            
            # Add any additional structured data from the response
            if "structured_findings" in agent_response:
                structured_data["findings"] = agent_response["structured_findings"]
            
            if "recommendations" in agent_response:
                structured_data["recommendations"] = agent_response["recommendations"]
            
            return structured_data
            
        except Exception as e:
            logger.warning(f"Failed to extract structured data: {e}")
            return None

    def _generate_human_summary(
        self, 
        agent_response: Dict[str, Any], 
        agent_type: str
    ) -> Optional[str]:
        """Generate human-readable summary of StrandsAgent response"""
        try:
            summary_parts = []
            
            # Agent and execution info
            domains = agent_response.get("domains_analyzed", [])
            tools_used = agent_response.get("tools_used", [])
            execution_time = agent_response.get("execution_time_ms", 0)
            
            summary_parts.append(f"**Analysis by {agent_type.replace('_', ' ').title()}**")
            
            if domains:
                summary_parts.append(f"**Domains Analyzed:** {', '.join(domains)}")
            
            if tools_used:
                summary_parts.append(f"**Tools Used:** {', '.join(tools_used)}")
            
            if execution_time > 0:
                summary_parts.append(f"**Execution Time:** {execution_time}ms")
            
            # Status
            status = agent_response.get("status", "unknown")
            status_emoji = "✅" if status == "success" else "⚠️"
            summary_parts.append(f"**Status:** {status_emoji} {status.title()}")
            
            return "\n".join(summary_parts)
            
        except Exception as e:
            logger.warning(f"Failed to generate human summary: {e}")
            return None

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools from StrandsAgents"""
        try:
            return await self.strands_discovery.get_available_tools()
        except Exception as e:
            logger.error(f"Failed to get available tools: {e}")
            return []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool through the appropriate StrandsAgent"""
        try:
            return await self.strands_discovery.call_tool_via_strands_agent(tool_name, arguments)
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name}: {e}")
            return {
                "tool_name": tool_name,
                "arguments": arguments,
                "result": f"Error: {str(e)}",
                "status": "error",
                "error": str(e)
            }

    async def health_check(self) -> str:
        """Check health of StrandsAgent orchestration"""
        try:
            discovery_health = await self.strands_discovery.health_check()
            
            if discovery_health == "healthy":
                return "healthy"
            elif discovery_health == "degraded":
                return "degraded"
            else:
                return "unhealthy"
                
        except Exception as e:
            logger.error(f"StrandsAgent orchestrator health check failed: {e}")
            return "unhealthy"

    def get_detailed_health(self) -> Dict[str, Any]:
        """Get detailed health information"""
        try:
            service_summary = self.strands_discovery.get_service_summary()
            
            return {
                "orchestrator_type": "strands_specialized",
                "discovery_service": service_summary,
                "routing_rules": len(self.agent_routing_rules),
                "tool_execution_history_sessions": len(self.tool_execution_history)
            }
            
        except Exception as e:
            logger.error(f"Failed to get detailed health: {e}")
            return {"error": str(e)}

    def get_session_info(self, session: ChatSession) -> Dict[str, Any]:
        """Get session information including StrandsAgent context"""
        try:
            strands_agents = session.context.get("strands_agents", {})
            available_tools = session.context.get("available_tools", [])
            
            return {
                "session_id": session.session_id,
                "orchestrator_type": "strands_specialized",
                "agents_count": len(strands_agents),
                "healthy_agents": sum(
                    1 for agent in strands_agents.values() 
                    if agent.get("status") == "HEALTHY"
                ),
                "tools_count": len(available_tools),
                "available_domains": list(set(
                    domain for agent in strands_agents.values()
                    for domain in agent.get("domains", [])
                )),
                "discovery_time": session.context.get("discovery_time"),
                "agents": strands_agents
            }
            
        except Exception as e:
            logger.error(f"Failed to get session info: {e}")
            return {"error": str(e)}