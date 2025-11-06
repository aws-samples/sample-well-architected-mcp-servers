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
    ChatMessage,
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
        
        # Dynamic domain keywords for agent routing (no hard-coded agent names)
        self.domain_keywords = {
            "aws_api": [
                "list", "describe", "get", "show", "display", "find", "search",
                "ec2", "s3", "rds", "lambda", "vpc", "iam", "cloudformation",
                "instances", "buckets", "databases", "functions", "users", "roles",
                "resources", "infrastructure", "api", "cli", "aws cli",
                "account", "region", "availability zone", "subnet", "security group",
                "load balancer", "auto scaling", "cloudwatch", "logs", "metrics"
            ],
            "security": [
                "security", "vulnerability", "compliance", "encryption", "access",
                "iam", "guardduty", "inspector", "security hub", "firewall", "vpc",
                "ssl", "tls", "certificate", "audit", "threat", "malware", "findings",
                "well-architected security", "security pillar", "security posture"
            ],
            "cost": [
                "cost", "billing", "expense", "budget", "savings", "optimization",
                "rightsizing", "reserved instance", "spot instance", "pricing",
                "spend", "financial", "money", "dollar", "cheap", "expensive",
                "cost explorer", "billing dashboard", "cost anomaly"
            ],
            "performance": [
                "performance", "latency", "throughput", "response time", "optimization",
                "cloudwatch", "metrics", "monitoring", "scaling", "auto scaling",
                "load balancer", "cdn", "caching", "database performance"
            ],
            "reliability": [
                "reliability", "availability", "disaster recovery", "backup",
                "multi-az", "multi-region", "failover", "redundancy", "resilience"
            ],
            "cross_domain": [
                "assessment", "review", "analysis", "comprehensive", "overall",
                "complete", "full", "entire", "all", "everything", "summary",
                "multi-pillar", "well-architected", "best practices"
            ]
        }
        
        # Tool execution tracking
        self.tool_execution_history: Dict[str, List[Dict[str, Any]]] = {}
        
        logger.info("StrandsAgent LLM Orchestrator Service initialized")

    async def _generate_optimized_prompt(
        self,
        original_message: str,
        session: ChatSession,
        manual_agent_selection: Optional[str] = None
    ) -> tuple[str, str, str]:
        """
        Generate optimized prompt using LLM orchestration.
        
        Returns:
            Tuple of (optimized_prompt, selected_agent, reasoning)
        """
        try:
            # Get available agents and their capabilities
            available_agents = session.context.get("strands_agents", {})
            
            if not available_agents:
                logger.warning("No agents available - will provide direct LLM response")
                # Generate a general LLM response when no agents are available
                general_response = await self._generate_no_agent_response(original_message)
                return general_response, None, "No agents available - providing general guidance"
            
            # Log agent deployment scenario
            agent_count = len(available_agents)
            agent_names = list(available_agents.keys())
            
            if agent_count == 1:
                logger.info(f"Single agent deployment detected: {agent_names[0]}")
            elif agent_count > 1:
                logger.info(f"Multi-agent deployment detected: {agent_count} agents - {agent_names}")
            else:
                logger.warning("No agents detected in session context")
            
            # Build agent capabilities summary
            agent_capabilities_summary = self._build_agent_capabilities_summary(available_agents)
            
            # Create orchestration prompt for LLM
            orchestration_prompt = self._create_orchestration_prompt(
                original_message=original_message,
                agent_capabilities=agent_capabilities_summary,
                manual_selection=manual_agent_selection
            )
            
            logger.debug(f"Orchestration prompt: {orchestration_prompt}")
            
            # Invoke LLM for orchestration (using Bedrock model service)
            orchestration_response = await self._invoke_orchestration_llm(orchestration_prompt)
            
            # Parse LLM response to extract optimized prompt and agent selection
            optimized_prompt, selected_agent, reasoning = self._parse_orchestration_response(
                orchestration_response, available_agents, original_message
            )
            
            return optimized_prompt, selected_agent, reasoning
            
        except Exception as e:
            logger.error(f"LLM orchestration failed: {e}")
            # Fallback to simple agent selection logic
            selected_agent, fallback_reason = await self._determine_best_strands_agent(original_message, session)
            
            # If we have only one agent, create an optimized prompt even in fallback
            if selected_agent and len(available_agents) == 1:
                optimized_prompt = self._create_single_agent_optimized_prompt(original_message, selected_agent, available_agents[selected_agent])
                return optimized_prompt, selected_agent, f"Single agent optimized fallback: {fallback_reason}"
            
            return original_message, selected_agent, f"Fallback due to orchestration error: {fallback_reason}"

    async def _generate_no_agent_response(self, original_message: str) -> str:
        """Generate a general LLM response when no agents are available."""
        try:
            # Import Bedrock model service
            from shared.services.bedrock_model_service import BedrockModelService
            from shared.models.chat_models import ChatMessage
            
            # Initialize Bedrock model service
            bedrock_service = BedrockModelService(region=self.region)
            
            # Create prompt for general AWS guidance
            no_agent_prompt = f"""You are an AWS Cloud Architecture Expert providing general guidance to a customer. Currently, no specialized analysis agents are available, but you can still provide valuable AWS optimization advice based on your knowledge.

**Customer's Request:**
"{original_message}"

**Your Task:**
Provide helpful AWS optimization guidance including:
1. General best practices related to their request
2. Common AWS services and approaches that might be relevant
3. Recommended next steps they can take
4. Important considerations for their AWS architecture

**Important Note:**
- Clearly inform the customer that no specialized analysis agents are currently available
- Explain that for detailed analysis and specific recommendations, they would need access to specialized agents
- Provide general guidance that is still valuable and actionable
- Maintain a professional, helpful tone

**Response Guidelines:**
- Start by acknowledging their request
- Provide general AWS best practices and guidance
- Clearly state the limitation about agent availability
- Suggest what they could do with specialized agents when available
- End with encouragement and next steps they can take independently"""

            # Create message for LLM
            messages = [ChatMessage(role="user", content=no_agent_prompt)]
            
            # Use standard model for general guidance
            model_id = bedrock_service.get_standard_model()
            
            # Invoke model
            response = await bedrock_service.invoke_model(
                model_id=model_id,
                messages=messages,
                max_tokens=1500,
                temperature=0.3  # Slightly higher temperature for more conversational response
            )
            
            formatted_response = bedrock_service.format_response(response)
            
            # Add a clear notice about agent availability
            general_response = formatted_response["content"]
            general_response += "\n\n---\n\n**⚠️ Agent Status Notice:**\nNo specialized analysis agents are currently available for detailed AWS infrastructure analysis. The guidance above is based on general AWS best practices. For comprehensive analysis with specific findings and recommendations, specialized agents would need to be deployed and configured."
            
            return general_response
            
        except Exception as e:
            logger.error(f"Failed to generate no-agent response: {e}")
            # Ultimate fallback
            return f"""I understand you're looking for help with: "{original_message}"

**⚠️ Service Status:**
Currently, no specialized AWS analysis agents are available to provide detailed infrastructure analysis and recommendations.

**General Guidance:**
While I cannot perform specific AWS resource analysis at the moment, I recommend:

1. **Review AWS Well-Architected Framework** - Focus on the five pillars: Security, Reliability, Performance Efficiency, Cost Optimization, and Operational Excellence
2. **Use AWS Trusted Advisor** - If you have Business or Enterprise support, this provides automated recommendations
3. **Check AWS Config** - For compliance and configuration analysis
4. **Review CloudWatch metrics** - For performance and utilization insights
5. **Consider AWS Cost Explorer** - For cost analysis and optimization opportunities

**Next Steps:**
To get detailed, actionable recommendations for your specific AWS environment, specialized analysis agents would need to be deployed and configured. These agents can provide comprehensive analysis across security, cost, performance, and compliance domains.

Please contact your AWS administrator about deploying the Cloud Optimization Assistant agents for full functionality."""

    def _create_single_agent_optimized_prompt(self, original_message: str, agent_id: str, agent_info: Dict[str, Any]) -> str:
        """Create an optimized prompt for any single agent when LLM orchestration fails."""
        
        # Get agent capabilities and domains
        domains = agent_info.get("domains", [])
        capabilities = agent_info.get("capabilities", [])
        tools_count = len(agent_info.get("available_tools", []))
        
        # Format agent name
        agent_name = agent_id.replace("_", " ").replace("-", " ").title()
        
        # Analyze the message to determine the type of request
        message_lower = original_message.lower()
        
        # Determine the primary domain based on keywords
        primary_domain = self._determine_primary_domain(message_lower)
        
        # Create domain-specific guidance
        domain_guidance = self._get_domain_specific_guidance(primary_domain)
        
        return f"""As an AWS expert using the {agent_name} agent, please help with this request: "{original_message}"

**Agent Context:**
- **Available Domains**: {', '.join(domains) if domains else 'General AWS Operations'}
- **Capabilities**: {', '.join(capabilities) if capabilities else 'AWS Infrastructure Analysis'}
- **Available Tools**: {tools_count} specialized tools

**Request Analysis:**
This appears to be a {primary_domain}-focused request. Please provide analysis by:

{domain_guidance}

**Guidelines:**
- Leverage the agent's specific capabilities and available tools
- Provide actionable recommendations within the agent's domain expertise
- Include specific implementation steps and best practices
- Focus on measurable outcomes and clear next steps
- Maintain professional AWS consulting standards

Focus on delivering the most comprehensive analysis possible within this agent's capabilities."""

    def _determine_primary_domain(self, message_lower: str) -> str:
        """Determine the primary domain of a request based on keywords."""
        domain_scores = {}
        
        for domain, keywords in self.domain_keywords.items():
            score = sum(1 for keyword in keywords if keyword in message_lower)
            if score > 0:
                domain_scores[domain] = score
        
        if domain_scores:
            return max(domain_scores.items(), key=lambda x: x[1])[0]
        else:
            return "general"

    def _get_domain_specific_guidance(self, domain: str) -> str:
        """Get domain-specific guidance for prompt optimization."""
        guidance_map = {
            "security": """1. Examining IAM users, roles, and policies for security risks
2. Analyzing security groups and network access controls
3. Reviewing VPC configurations and network security
4. Checking encryption settings and data protection measures
5. Identifying publicly accessible resources and vulnerabilities
6. Providing specific remediation steps and security improvements""",
            
            "cost": """1. Analyzing resource utilization and identifying underutilized resources
2. Reviewing instance types and sizes for rightsizing opportunities
3. Examining storage usage and optimization opportunities
4. Checking for unused resources and cost optimization potential
5. Analyzing pricing models and Reserved Instance opportunities
6. Providing cost reduction recommendations with estimated savings""",
            
            "performance": """1. Analyzing performance metrics and resource utilization patterns
2. Reviewing configurations for performance optimization
3. Examining network configurations and potential bottlenecks
4. Checking scaling configurations and auto-scaling opportunities
5. Identifying performance improvement opportunities
6. Providing optimization recommendations with measurable impact""",
            
            "reliability": """1. Analyzing availability and disaster recovery configurations
2. Reviewing backup and redundancy implementations
3. Examining multi-AZ and multi-region setups
4. Checking failover and recovery mechanisms
5. Identifying reliability improvement opportunities
6. Providing resilience recommendations and best practices""",
            
            "aws_api": """1. Conducting comprehensive resource inventory and analysis
2. Examining configurations across multiple AWS services
3. Analyzing resource relationships and dependencies
4. Checking compliance with AWS best practices
5. Identifying optimization opportunities across all domains
6. Providing prioritized recommendations with implementation guidance""",
            
            "general": """1. Conducting a comprehensive analysis of the request
2. Examining relevant AWS resources and configurations
3. Analyzing current state and identifying improvement opportunities
4. Checking alignment with AWS best practices
5. Identifying actionable optimization opportunities
6. Providing prioritized recommendations with clear implementation steps"""
        }
        
        return guidance_map.get(domain, guidance_map["general"])

    def _build_agent_capabilities_summary(self, available_agents: Dict[str, Any]) -> str:
        """Build a dynamic summary of available agents and their capabilities."""
        if not available_agents:
            return "No specialized agents currently available."
        
        agent_summaries = []
        agent_count = len(available_agents)
        
        for agent_id, agent_info in available_agents.items():
            status_emoji = "✅" if agent_info.get("status") == "HEALTHY" else "⚠️"
            domains = agent_info.get("domains", [])
            capabilities = agent_info.get("capabilities", [])
            tools_count = len(agent_info.get("available_tools", []))
            
            # Format agent name for display
            agent_name = agent_id.replace("_", " ").replace("-", " ").title()
            
            # Dynamic description based on actual agent capabilities
            summary = f"- **{agent_name}** {status_emoji}\n"
            
            # Add domain information
            if domains:
                if isinstance(domains, dict):
                    active_domains = [domain for domain, active in domains.items() if active]
                    summary += f"  - **Domains**: {', '.join(active_domains) if active_domains else 'General'}\n"
                else:
                    summary += f"  - **Domains**: {', '.join(domains)}\n"
            else:
                summary += f"  - **Domains**: General AWS Operations\n"
            
            # Add capabilities information
            if capabilities:
                summary += f"  - **Capabilities**: {', '.join(capabilities)}\n"
            else:
                summary += f"  - **Capabilities**: AWS Infrastructure Analysis\n"
            
            # Add tools information
            summary += f"  - **Available Tools**: {tools_count} specialized tools\n"
            
            # Add scope information for single agent scenarios
            if agent_count == 1:
                summary += f"  - **Analysis Scope**: Primary agent for all AWS optimization requests\n"
            
            agent_summaries.append(summary)
        
        return "\n".join(agent_summaries)

    def _create_orchestration_prompt(
        self,
        original_message: str,
        agent_capabilities: str,
        manual_selection: Optional[str] = None
    ) -> str:
        """Create a dynamic orchestration prompt for LLM."""
        
        # Count available agents dynamically
        agent_count = agent_capabilities.count("- **") if agent_capabilities else 0
        is_single_agent = agent_count == 1
        
        if is_single_agent:
            # Optimized prompt for single agent scenario (any agent type)
            base_prompt = f"""You are an AWS Cloud Architecture Expert helping customers optimize their infrastructure. You have access to a specialized agent that can provide AWS analysis and recommendations.

**Your Role:**
- Analyze the customer's request and understand their optimization needs
- Rewrite the customer's request to maximize the available agent's capabilities
- Guide the agent to provide the most comprehensive analysis possible within its domain expertise

**Available Agent:**
{agent_capabilities}

**Customer's Original Request:**
"{original_message}"

**Your Task:**
Rewrite the customer's request into an optimized prompt that:
1. Clearly explains what the customer wants to achieve
2. Leverages the agent's specific domains and capabilities
3. Requests analysis within the agent's expertise area
4. Asks for actionable recommendations with implementation steps
5. Guides toward comprehensive analysis using the agent's available tools

**Response Format (JSON):**
```json
{{
    "selected_agent": "agent_name_from_available_list",
    "reasoning": "How this agent will approach the optimization request based on its capabilities",
    "optimized_prompt": "Enhanced prompt that guides the agent to provide the best possible analysis and recommendations"
}}
```

**Guidelines for Single Agent Optimization:**
- Focus on the agent's specific domain expertise and capabilities
- Request analysis that aligns with the agent's available tools
- Ask for actionable recommendations within the agent's scope
- Request specific implementation steps and best practices
- Maintain professional AWS consulting tone"""
        else:
            # Multi-agent scenario prompt
            base_prompt = f"""You are an AWS Cloud Architecture Expert helping customers optimize their infrastructure design. You have access to multiple specialized AI agents, each with specific capabilities and tools.

**Your Role:**
- Analyze the customer's request and understand their optimization needs
- Select the most appropriate agent based on their capabilities and domains
- Rewrite the customer's request into a clear, specific prompt that will help the selected agent provide the best possible assistance

**Available Specialized Agents:**
{agent_capabilities}

**Customer's Original Request:**
"{original_message}"

**Your Task:**
1. Analyze what the customer is trying to achieve
2. Determine which agent is best suited for this request (consider domains, capabilities, and available tools)
3. Rewrite the customer's request into an optimized prompt that:
   - Is clear and specific
   - Includes relevant context about AWS optimization goals
   - Guides the agent toward providing actionable recommendations
   - Maintains the customer's original intent while being more precise

**Response Format (JSON):**
```json
{{
    "selected_agent": "agent_name_here",
    "reasoning": "Brief explanation of why this agent was selected and what optimization approach will be used",
    "optimized_prompt": "The rewritten, enhanced prompt that will be sent to the selected agent"
}}
```

**Guidelines for Multi-Agent Optimization:**
- Match the request to the agent with the most relevant domain expertise
- Be specific about what AWS resources or services are involved
- Include context about optimization goals (cost, security, performance, reliability)
- Ask for actionable recommendations with implementation steps
- Request specific metrics or findings when relevant
- Maintain professional AWS consulting tone"""

        if manual_selection:
            base_prompt += f"\n\n**Note:** The customer has manually selected the '{manual_selection}' agent. Please optimize the prompt for this specific agent's capabilities."
        
        return base_prompt

    async def _invoke_orchestration_llm(self, orchestration_prompt: str) -> str:
        """Invoke LLM for orchestration decision."""
        try:
            # Import Bedrock model service
            from shared.services.bedrock_model_service import BedrockModelService
            from shared.models.chat_models import ChatMessage
            
            # Initialize Bedrock model service
            bedrock_service = BedrockModelService(region=self.region)
            
            # Create message for LLM
            messages = [ChatMessage(role="user", content=orchestration_prompt)]
            
            # Use lightweight model for orchestration (faster response)
            model_id = bedrock_service.get_lightweight_model()
            
            # Invoke model
            response = await bedrock_service.invoke_model(
                model_id=model_id,
                messages=messages,
                max_tokens=1000,
                temperature=0.1  # Low temperature for consistent orchestration
            )
            
            formatted_response = bedrock_service.format_response(response)
            return formatted_response["content"]
            
        except Exception as e:
            logger.error(f"Failed to invoke orchestration LLM: {e}")
            raise

    def _parse_orchestration_response(
        self,
        llm_response: str,
        available_agents: Dict[str, Any],
        original_message: str
    ) -> tuple[str, str, str]:
        """Parse LLM orchestration response."""
        try:
            import json
            import re
            
            # Extract JSON from response
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', llm_response, re.DOTALL)
            if not json_match:
                # Try to find JSON without code blocks
                json_match = re.search(r'(\{.*?\})', llm_response, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                orchestration_data = json.loads(json_str)
                
                selected_agent = orchestration_data.get("selected_agent", "")
                reasoning = orchestration_data.get("reasoning", "LLM orchestration")
                optimized_prompt = orchestration_data.get("optimized_prompt", original_message)
                
                # Validate selected agent exists and is available
                if selected_agent not in available_agents:
                    logger.warning(f"LLM selected unavailable agent '{selected_agent}', falling back")
                    # Find the first healthy agent as fallback
                    for agent_id, agent_info in available_agents.items():
                        if agent_info.get("status") == "HEALTHY":
                            selected_agent = agent_id
                            reasoning += f" (Fallback to {agent_id} - original selection unavailable)"
                            break
                
                return optimized_prompt, selected_agent, reasoning
            
            else:
                logger.warning("Could not parse JSON from LLM orchestration response")
                # Fallback parsing - extract key information
                selected_agent = self._extract_agent_from_text(llm_response, available_agents)
                reasoning = "Text-based parsing (JSON parsing failed)"
                optimized_prompt = original_message  # Use original if can't extract optimized
                
                return optimized_prompt, selected_agent, reasoning
                
        except Exception as e:
            logger.error(f"Failed to parse orchestration response: {e}")
            # Ultimate fallback
            first_healthy_agent = None
            for agent_id, agent_info in available_agents.items():
                if agent_info.get("status") == "HEALTHY":
                    first_healthy_agent = agent_id
                    break
            
            return original_message, first_healthy_agent, f"Parsing error fallback: {str(e)}"

    def _extract_agent_from_text(self, text: str, available_agents: Dict[str, Any]) -> str:
        """Extract agent name from text response as fallback."""
        text_lower = text.lower()
        
        # Look for agent names in the response
        for agent_id in available_agents.keys():
            agent_variations = [
                agent_id.lower(),
                agent_id.replace("_", " ").lower(),
                agent_id.replace("-", " ").lower(),
                agent_id.replace("strands", "").replace("_", "").replace("-", "").lower()
            ]
            
            for variation in agent_variations:
                if variation in text_lower:
                    return agent_id
        
        # If no agent found, return first healthy one
        for agent_id, agent_info in available_agents.items():
            if agent_info.get("status") == "HEALTHY":
                return agent_id
        
        # Last resort - return first available
        return next(iter(available_agents.keys())) if available_agents else None

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
2. **Tool Orchestration**: Coordinate multiple tool executions across different domains
3. **Contextual Understanding**: Maintain context across multi-step analyses
4. **Optimization Prioritization**: Provide prioritized recommendations based on impact and effort

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
- Drill down into specific areas based on findings
- Provide actionable, prioritized recommendations

You should proactively suggest comprehensive analyses that span multiple domains when appropriate, leveraging the full capabilities of the StrandsAgent ecosystem."""

    async def process_message(
        self, 
        message: str, 
        session_id: str,
        selected_agent: Optional[str] = None,
        agent_selection_mode: str = "auto",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process message through enhanced LLM-powered orchestration"""
        
        try:
            # Create a temporary session object for compatibility
            session = ChatSession(
                session_id=session_id,
                created_at=datetime.utcnow(),
                messages=[ChatMessage(role="user", content=message)],
                context=context or {}
            )
            
            # Initialize session if needed
            if not session.context.get("strands_agents"):
                await self.initialize_session(session)
            
            # ENHANCED ORCHESTRATION FLOW
            # Step 1: Generate optimized prompt using LLM
            optimized_prompt, selected_agent, orchestration_reasoning = await self._generate_optimized_prompt(
                original_message=message,
                session=session,
                manual_agent_selection=selected_agent if agent_selection_mode == "manual" else None
            )
            
            logger.info(f"\n======================\nOriginal message: {message}")
            logger.info(f"\n======================\nOptimized prompt: {optimized_prompt}")
            logger.info(f"\n======================\nSelected agent: {selected_agent}")
            logger.info(f"\n======================\nOrchestration reasoning: {orchestration_reasoning}")
            
            routing_reason = f"LLM-optimized routing: {orchestration_reasoning}"
            
            if not selected_agent:
                # Handle no-agent scenario - return the general LLM response
                return {
                    "content": optimized_prompt,  # This contains the no-agent response
                    "agent_id": "no-agent-available",
                    "metadata": {
                        "orchestration": {
                            "original_message": message,
                            "no_agents_available": True,
                            "general_guidance_provided": True,
                            "llm_enhanced": True
                        }
                    }
                }
            
            logger.info(f"Selected StrandsAgent: {selected_agent} (Reason: {routing_reason})")
            
            # Create tool execution record for the agent invocation
            agent_execution = ToolExecution(
                tool_name=f"StrandsAgent_{selected_agent}",
                parameters={
                    "original_message": message, 
                    "optimized_prompt": optimized_prompt,
                    "routing_reason": routing_reason
                },
                status=ToolExecutionStatus.PENDING,
                timestamp=datetime.utcnow()
            )
            
            try:
                # Check if invoke method exists, otherwise create a mock response
                if hasattr(self.strands_discovery, 'invoke_strands_agent'):
                    # Invoke the selected StrandsAgent with OPTIMIZED PROMPT
                    logger.info(f"\n********************\n Invoke {selected_agent} \n*******************\n")
                    logger.info(optimized_prompt)
                    logger.info("\n*********************")
                    agent_response = await self.strands_discovery.invoke_strands_agent(
                        agent_type=selected_agent,
                        prompt=optimized_prompt,  # Use LLM-optimized prompt instead of original
                        session_id=session.session_id
                    )
                else:
                    # Mock response for development/testing
                    logger.warning(f"invoke_strands_agent method not available, creating mock response for {selected_agent}")
                    agent_response = {
                        "response": f"Mock response from {selected_agent} agent.\n\n**Original Request:** {message}\n\n**Optimized Prompt:** {optimized_prompt}\n\n**Orchestration Reasoning:** {orchestration_reasoning}",
                        "agent_type": selected_agent,
                        "status": "success",
                        "domains_analyzed": ["mock_domain"],
                        "tools_used": ["mock_tool"],
                        "execution_time_ms": 100,
                        "session_id": session.session_id
                    }
                
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
                
                return {
                    "content": main_response,
                    "agent_id": selected_agent,
                    "metadata": {
                        "tool_executions": [agent_execution],
                        "structured_data": structured_data,
                        "human_summary": human_summary,
                        "routing_reason": routing_reason,
                        "agent_selection_mode": agent_selection_mode,
                        "orchestration": {
                            "original_message": message,
                            "optimized_prompt": optimized_prompt,
                            "orchestration_reasoning": orchestration_reasoning,
                            "llm_enhanced": True
                        }
                    }
                }
                
            except Exception as e:
                logger.error(f"StrandsAgent {selected_agent} execution failed: {e}")
                agent_execution.status = ToolExecutionStatus.ERROR
                agent_execution.error_message = str(e)
                
                return {
                    "content": f"I encountered an error while processing your request through the {selected_agent} agent: {str(e)}",
                    "agent_id": "strands-orchestrator-error",
                    "metadata": {
                        "tool_executions": [agent_execution],
                        "error": str(e),
                        "routing_reason": routing_reason,
                        "agent_selection_mode": agent_selection_mode
                    }
                }
                
        except Exception as e:
            logger.error(f"StrandsAgent orchestration failed: {e}")
            return {
                "content": f"I encountered an error in the orchestration process: {str(e)}",
                "agent_id": "strands-orchestrator-error",
                "metadata": {
                    "error": str(e),
                    "agent_selection_mode": agent_selection_mode
                }
            }

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
            if hasattr(self.strands_discovery, 'get_available_tools'):
                return await self.strands_discovery.get_available_tools()
            else:
                # Mock response for development/testing
                logger.warning("get_available_tools method not available, returning mock tools")
                return [
                    {
                        "name": "mock_security_tool",
                        "description": "Mock security analysis tool",
                        "domain": "security",
                        "parameters": {}
                    },
                    {
                        "name": "mock_cost_tool", 
                        "description": "Mock cost analysis tool",
                        "domain": "cost",
                        "parameters": {}
                    }
                ]
        except Exception as e:
            logger.error(f"Failed to get available tools: {e}")
            return []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool through the appropriate StrandsAgent"""
        try:
            if hasattr(self.strands_discovery, 'call_tool_via_strands_agent'):
                return await self.strands_discovery.call_tool_via_strands_agent(tool_name, arguments)
            else:
                # Mock response for development/testing
                logger.warning(f"call_tool_via_strands_agent method not available, creating mock response for {tool_name}")
                return {
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "result": f"Mock result for {tool_name} with arguments: {arguments}",
                    "status": "success",
                    "mock": True
                }
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
            if hasattr(self.strands_discovery, 'health_check'):
                discovery_health = await self.strands_discovery.health_check()
                
                if discovery_health == "healthy":
                    return "healthy"
                elif discovery_health == "degraded":
                    return "degraded"
                else:
                    return "unhealthy"
            else:
                # Mock health check for development/testing
                logger.warning("health_check method not available on discovery service, returning mock health")
                return "healthy"
                
        except Exception as e:
            logger.error(f"StrandsAgent orchestrator health check failed: {e}")
            return "unhealthy"

    def get_detailed_health(self) -> Dict[str, Any]:
        """Get detailed health information"""
        try:
            if hasattr(self.strands_discovery, 'get_service_summary'):
                service_summary = self.strands_discovery.get_service_summary()
            else:
                # Mock service summary for development/testing
                logger.warning("get_service_summary method not available, using mock summary")
                service_summary = {
                    "status": "mock",
                    "agents_discovered": 2,
                    "tools_available": 4
                }
            
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