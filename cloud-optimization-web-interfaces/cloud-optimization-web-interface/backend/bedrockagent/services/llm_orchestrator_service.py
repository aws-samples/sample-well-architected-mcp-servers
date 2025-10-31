# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
LLM Orchestrator Service - Central intelligence for routing and tool execution
UPDATED: Now integrates with Multi-Agent Supervisor for specialized agent routing
Handles both direct MCP tools and multi-agent coordination
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List

import boto3
from shared.models.chat_models import (
    BedrockResponse,
    ChatSession,
    ToolExecution,
    ToolExecutionStatus,
)
from shared.services.config_service import get_config
# MCP tools are now accessed through agents and dynamic MCP service

logger = logging.getLogger(__name__)


class BedrockInitializationError(Exception):
    """Custom exception for Bedrock initialization failures"""

    pass


class LLMOrchestratorService:
    def __init__(self):
        self.region = get_config("AWS_DEFAULT_REGION", "us-east-1")
        self._bedrock_runtime = None
        
        # Initialize dynamic MCP service for agent-tool discovery
        logger.info("LLM Orchestrator initialized with dynamic MCP service")
        self._bedrock_initialization_error = None
        # MCP tools are now accessed through agents and dynamic MCP service
        self.available_tools = []
        self.tools_discovered = False

        # Multi-Agent Supervisor configuration
        self.use_multi_agent = (
            get_config("USE_MULTI_AGENT_SUPERVISOR", "true").lower() == "true"
        )
        self.supervisor_agent_id = get_config("MULTI_AGENT_SUPERVISOR_AGENT_ID")
        self.supervisor_agent_alias_id = get_config(
            "MULTI_AGENT_SUPERVISOR_AGENT_ALIAS_ID"
        )

        # Initialize Bedrock Agent client for multi-agent supervisor
        self._bedrock_agent_runtime = None

        # LLM configuration - use Claude 3 Haiku for faster responses
        self.model_id = "anthropic.claude-3-haiku-20240307-v1:0"

        logger.info(
            f"Initialized LLM Orchestrator Service (Multi-Agent: {self.use_multi_agent})"
        )
        if self.use_multi_agent:
            logger.info(
                f"Multi-Agent Supervisor: {self.supervisor_agent_id}/{self.supervisor_agent_alias_id}"
            )

    @property
    def bedrock_runtime(self):
        """Lazy initialization of Bedrock Runtime client with proper error handling"""
        if self._bedrock_runtime is None and self._bedrock_initialization_error is None:
            try:
                self._bedrock_runtime = boto3.client(
                    "bedrock-runtime", region_name=self.region
                )
                logger.info("Bedrock Runtime client initialized successfully")
            except Exception as e:
                error_msg = f"Failed to initialize Bedrock Runtime client: {str(e)}"
                logger.error(error_msg)
                self._bedrock_initialization_error = BedrockInitializationError(
                    error_msg
                )

        if self._bedrock_initialization_error:
            raise self._bedrock_initialization_error

        return self._bedrock_runtime

    @property
    def bedrock_agent_runtime(self):
        """Lazy initialization of Bedrock Agent Runtime client for multi-agent supervisor"""
        if self._bedrock_agent_runtime is None:
            try:
                self._bedrock_agent_runtime = boto3.client(
                    "bedrock-agent-runtime", region_name=self.region
                )
                logger.info("Bedrock Agent Runtime client initialized successfully")
            except Exception as e:
                logger.error(
                    f"Failed to initialize Bedrock Agent Runtime client: {str(e)}"
                )
                raise BedrockInitializationError(
                    f"Failed to initialize Bedrock Agent Runtime: {str(e)}"
                )

        return self._bedrock_agent_runtime

    def _is_bedrock_available(self) -> bool:
        """Check if Bedrock is available without raising exceptions"""
        try:
            _ = self.bedrock_runtime
            return True
        except BedrockInitializationError:
            return False

    async def health_check(self) -> str:
        """Check if the orchestrator service is healthy"""
        try:
            # MCP tools are now accessed through dynamic MCP service
            
            # Check dynamic MCP service
            dynamic_mcp_status = await self.dynamic_mcp_service.health_check()

            # Check Bedrock availability
            bedrock_available = self._is_bedrock_available()

            # Check Multi-Agent Supervisor availability
            multi_agent_available = False
            if (
                self.use_multi_agent
                and self.supervisor_agent_id
                and self.supervisor_agent_alias_id
            ):
                try:
                    # Test if we can access the Bedrock Agent Runtime
                    _ = self.bedrock_agent_runtime
                    multi_agent_available = True
                    logger.info("Multi-Agent Supervisor is available")
                except Exception as e:
                    logger.warning(f"Multi-Agent Supervisor not available: {e}")

            # Determine overall health
            if multi_agent_available and dynamic_mcp_status in ["healthy", "degraded"]:
                return "healthy"  # Multi-agent with dynamic MCP is the preferred mode
            elif bedrock_available and dynamic_mcp_status in ["healthy", "degraded"]:
                return "healthy"  # Direct agent mode with dynamic discovery works
            elif dynamic_mcp_status in ["healthy", "degraded"]:
                return "degraded"  # Some MCP functionality works
            else:
                return "unhealthy"
        except Exception as e:
            logger.error(f"Orchestrator health check failed: {str(e)}")
            return "unhealthy"

    def get_detailed_health(self) -> Dict[str, Any]:
        """Get detailed health information for the orchestrator service"""
        try:
            return {
                "bedrock_available": self._is_bedrock_available(),
                "multi_agent_enabled": self.use_multi_agent,
                "supervisor_agent_id": self.supervisor_agent_id,
                "supervisor_agent_alias_id": self.supervisor_agent_alias_id,
                "tools_discovered": self.tools_discovered,
                "available_tools_count": len(self.available_tools),
                "model_id": self.model_id,
                "region": self.region,
                "dynamic_mcp_initialized": self.dynamic_mcp_service is not None,
                "mcp_service_initialized": self.mcp_service is not None,
            }
        except Exception as e:
            logger.error(f"Failed to get detailed health: {e}")
            return {"error": str(e)}

    async def initialize_session(self, session: ChatSession) -> Dict[str, Any]:
        """Initialize session by discovering available tools and setting up context"""
        try:
            logger.info(f"Initializing session {session.session_id}")

            # Discover available MCP tools
            if not self.tools_discovered:
                await self._discover_tools()

            # Set up session context with available tools
            session.context["available_tools"] = self.available_tools
            session.context["tools_discovered_at"] = datetime.utcnow().isoformat()
            session.context["orchestrator_initialized"] = True
            session.context["bedrock_available"] = self._is_bedrock_available()
            session.context["multi_agent_enabled"] = self.use_multi_agent
            session.context["supervisor_agent_id"] = self.supervisor_agent_id

            # Generate initial system prompt with tool information
            system_prompt = self._generate_system_prompt()
            session.context["system_prompt"] = system_prompt

            logger.info(
                f"Session {session.session_id} initialized with {len(self.available_tools)} tools (Multi-Agent: {self.use_multi_agent})"
            )

            return {
                "status": "initialized",
                "tools_count": len(self.available_tools),
                "bedrock_available": session.context["bedrock_available"],
                "multi_agent_enabled": self.use_multi_agent,
                "supervisor_agent_id": self.supervisor_agent_id,
                "tools": [
                    {"name": tool["name"], "description": tool["description"]}
                    for tool in self.available_tools
                ],
            }

        except Exception as e:
            logger.error(f"Failed to initialize session: {e}")
            return {"status": "error", "error": str(e)}

    async def _discover_tools(self):
        """Discover all available MCP tools from both static and dynamic sources"""
        try:
            logger.info("Discovering available MCP tools...")
            
            # Get dynamic MCP tools (through agents)
            dynamic_tools = await self.dynamic_mcp_service.get_available_tools()
            
            self.available_tools = dynamic_tools
            self.tools_discovered = True
            logger.info(f"Discovered {len(self.available_tools)} MCP tools (0 static, {len(dynamic_tools)} dynamic)")

            # Log tool names for debugging
            tool_names = [tool["name"] for tool in self.available_tools]
            logger.info(f"Available tools: {', '.join(tool_names)}")

        except Exception as e:
            logger.error(f"Failed to discover tools: {e}")
            self.available_tools = []
    
    async def _determine_agent_type(self, message: str, session: ChatSession) -> str:
        """Determine the best agent type for processing this message"""
        message_lower = message.lower()
        
        # Security-related keywords
        security_keywords = [
            'security', 'vulnerability', 'compliance', 'encryption', 'access', 
            'iam', 'guardduty', 'inspector', 'security hub', 'firewall', 'vpc',
            'ssl', 'tls', 'certificate', 'audit', 'threat', 'malware', 'findings'
        ]
        
        # Cost-related keywords
        cost_keywords = [
            'cost', 'billing', 'expense', 'budget', 'savings', 'optimization',
            'rightsizing', 'reserved instance', 'spot instance', 'pricing',
            'spend', 'financial', 'money', 'dollar', 'cheap', 'expensive'
        ]
        
        # Multi-domain keywords (use supervisor)
        multi_keywords = [
            'assessment', 'review', 'analysis', 'comprehensive', 'overall',
            'complete', 'full', 'entire', 'all', 'everything', 'summary',
            'both security and cost', 'security and cost', 'multi-pillar'
        ]
        
        # Check for multi-domain requests first
        if any(keyword in message_lower for keyword in multi_keywords):
            return "strands_multi_agent_supervisor"
        
        # Check for security focus
        security_score = sum(1 for keyword in security_keywords if keyword in message_lower)
        cost_score = sum(1 for keyword in cost_keywords if keyword in message_lower)
        
        if security_score > cost_score and security_score > 0:
            return "strands_multi_mcp_security"
        elif cost_score > 0:
            return "strands_multi_mcp_cost"
        
        # Default to multi-agent supervisor for general infrastructure questions
        return "strands_multi_agent_supervisor"

    def _generate_system_prompt(self) -> str:
        """Generate system prompt with available tools information"""
        tools_info = []
        for tool in self.available_tools:
            tool_info = f"- **{tool['name']}**: {tool['description']}"
            if "inputSchema" in tool and "properties" in tool["inputSchema"]:
                params = list(tool["inputSchema"]["properties"].keys())
                tool_info += f" (Parameters: {', '.join(params)})"
            tools_info.append(tool_info)

        tools_text = (
            "\n".join(tools_info) if tools_info else "No tools currently available."
        )

        bedrock_status = "available" if self._is_bedrock_available() else "unavailable"
        multi_agent_status = (
            "enabled"
            if self.use_multi_agent and self.supervisor_agent_id
            else "disabled"
        )

        return f"""You are an AWS Cloud Optimization Assistant with access to specialized analysis capabilities for AWS infrastructure. Your role is to help users optimize their AWS environments across security, performance, cost, and operational excellence.

**System Status:**
- Bedrock LLM: {bedrock_status}
- Multi-Agent System: {multi_agent_status}
- Available Tools: {len(self.available_tools)}

**Available Tools:**
{tools_text}

**Your Capabilities:**
1. **Multi-Agent Coordination**: Route complex queries to specialized agents (security, cost optimization)
2. **Intelligent Analysis**: Analyze user requests and determine the best approach
3. **Comprehensive Assessment**: Combine multiple analysis types for complete insights
4. **Contextual Understanding**: Understand user intent and provide relevant recommendations
5. **Actionable Guidance**: Provide specific, implementable advice based on findings

**Guidelines:**
- Always analyze the user's request to determine the most appropriate tools to use
- Use multiple tools when needed to provide comprehensive analysis
- Present results in a clear, structured format with human-readable summaries
- Include specific recommendations and next steps
- If a request is unclear, ask clarifying questions
- For security-related queries, prioritize CheckSecurityServices and GetSecurityFindings
- For storage queries, use CheckStorageEncryption
- For network analysis, use CheckNetworkSecurity
- For general infrastructure overview, use ListServicesInRegion

**Response Format:**
- Provide a clear summary of findings
- Include structured data when available
- Offer specific, actionable recommendations
- Explain the significance of any issues found

You should be proactive in suggesting related analyses that might be valuable to the user."""

    async def process_message(
        self, message: str, session: ChatSession
    ) -> BedrockResponse:
        """Process user message using multi-agent orchestration or direct MCP tools"""

        try:
            # Handle special commands first
            message_lower = message.strip().lower()
            if message_lower.startswith("/mcp"):
                return await self._handle_mcp_command(session, message_lower)
            
            # Initialize session if not already done
            if not session.context.get("orchestrator_initialized"):
                await self.initialize_session(session)

            # Determine the best agent type for this message
            agent_type = await self._determine_agent_type(message, session)
            
            # Load dynamic MCP tools for the determined agent type
            if agent_type:
                try:
                    await self.dynamic_mcp_service.load_agent_tools(agent_type)
                    logger.info(f"Loaded dynamic MCP tools for agent type: {agent_type}")
                except Exception as e:
                    logger.warning(f"Failed to load dynamic MCP tools for {agent_type}: {e}")

            # Use Multi-Agent Supervisor if configured and available
            if (
                self.use_multi_agent
                and self.supervisor_agent_id
                and self.supervisor_agent_alias_id
            ):
                return await self._process_with_multi_agent_supervisor(message, session)

            # Fallback to direct MCP processing with dynamic tools
            logger.info(
                "Using direct MCP processing with dynamic tool discovery"
            )
            return await self._process_with_direct_mcp(message, session)

        except Exception as e:
            logger.error(f"Error in LLM orchestrator: {e}")
            return BedrockResponse(
                response=f"I encountered an error while processing your request: {str(e)}",
                tool_executions=[],
                model_id=self.model_id,
                session_id=session.session_id,
            )

    async def _process_with_multi_agent_supervisor(
        self, message: str, session: ChatSession
    ) -> BedrockResponse:
        """Process message using the Multi-Agent Supervisor"""

        try:
            logger.info(
                f"Processing message with Multi-Agent Supervisor: {self.supervisor_agent_id}"
            )

            # Create tool execution record for the supervisor call
            tool_execution = ToolExecution(
                tool_name="MultiAgentSupervisor",
                parameters={"message": message},
                status=ToolExecutionStatus.PENDING,
                timestamp=datetime.utcnow(),
            )

            # Invoke the Multi-Agent Supervisor
            response = self.bedrock_agent_runtime.invoke_agent(
                agentId=self.supervisor_agent_id,
                agentAliasId=self.supervisor_agent_alias_id,
                sessionId=session.session_id,
                inputText=message,
            )

            # Process the streaming response
            full_response = ""
            tool_calls = []

            for event in response["completion"]:
                if "chunk" in event:
                    chunk = event["chunk"]
                    if "bytes" in chunk:
                        chunk_text = chunk["bytes"].decode("utf-8")
                        full_response += chunk_text
                elif "trace" in event:
                    # Capture tool usage information from trace
                    trace = event["trace"]
                    if "orchestrationTrace" in trace:
                        orch_trace = trace["orchestrationTrace"]
                        if "invocationInput" in orch_trace:
                            tool_calls.append(orch_trace["invocationInput"])

            # Update tool execution status
            tool_execution.result = {
                "response": full_response,
                "tool_calls": tool_calls,
            }
            tool_execution.status = ToolExecutionStatus.SUCCESS

            logger.info(
                f"Multi-Agent Supervisor response received: {len(full_response)} characters"
            )

            return BedrockResponse(
                response=full_response,
                tool_executions=[tool_execution],
                model_id="multi-agent-supervisor",
                session_id=session.session_id,
                structured_data={"supervisor_response": True, "tool_calls": tool_calls},
                human_summary=None,
            )

        except Exception as e:
            logger.error(f"Multi-Agent Supervisor processing failed: {e}")
            tool_execution.status = ToolExecutionStatus.ERROR
            tool_execution.error_message = str(e)

            # Fallback to direct MCP processing
            logger.info("Falling back to direct MCP processing")
            return await self._process_with_direct_mcp(message, session)

    async def _process_with_direct_mcp(
        self, message: str, session: ChatSession
    ) -> BedrockResponse:
        """Process message using direct MCP tools or route to bedrock agents"""

        # Check if a specific agent is selected - if so, route to bedrock agent service
        if session and session.context.get("selected_agent"):
            return await self._process_with_bedrock_agent(message, session)

        # Check if Bedrock is available
        if not self._is_bedrock_available():
            return await self._process_message_without_bedrock(message, session)

        # Analyze the message and determine tool usage
        analysis = await self._analyze_user_request(message, session)

        # Execute tools if needed
        tool_results = []
        tool_executions = []

        if analysis.get("tools_to_use"):
            for tool_call in analysis["tools_to_use"]:
                tool_name = tool_call["name"]
                tool_args = tool_call.get("arguments", {})

                # Create tool execution record
                tool_execution = ToolExecution(
                    tool_name=tool_name,
                    parameters=tool_args,
                    status=ToolExecutionStatus.PENDING,
                    timestamp=datetime.utcnow(),
                )
                tool_executions.append(tool_execution)

                # Execute the tool using dynamic MCP service first, then fallback to regular MCP
                try:
                    # Try dynamic MCP service first
                    result = await self.dynamic_mcp_service.call_tool(tool_name, tool_args)
                    tool_execution.result = result
                    tool_execution.status = ToolExecutionStatus.SUCCESS
                    tool_results.append({"tool_name": tool_name, "result": result})
                    logger.info(f"Tool {tool_name} executed successfully via dynamic MCP service")
                    
                except Exception as dynamic_error:
                    logger.warning(f"Dynamic MCP service failed for {tool_name}: {dynamic_error}")
                    
                    # No fallback available - all tools are now through agents
                    tool_execution.status = ToolExecutionStatus.ERROR
                    tool_execution.error_message = f"Dynamic MCP service failed: {str(dynamic_error)}"
                    logger.error(f"Tool execution failed for {tool_name}: {dynamic_error}")

        # Generate final response using LLM with tool results
        final_response = await self._generate_final_response(
            message, analysis, tool_results, session
        )

        return BedrockResponse(
            response=final_response["response"],
            tool_executions=tool_executions,
            model_id=self.model_id,
            session_id=session.session_id,
            structured_data=final_response.get("structured_data"),
            human_summary=final_response.get("human_summary"),
        )

    async def _process_with_bedrock_agent(
        self, message: str, session: ChatSession
    ) -> BedrockResponse:
        """Process message by routing to the selected Bedrock agent"""
        
        try:
            # Import the enhanced bedrock agent service
            # TODO: Update to use BedrockAgent-specific service
            # from services.enhanced_bedrock_agent_service import EnhancedBedrockAgentService
            
            # Create enhanced bedrock agent service instance
            bedrock_agent_service = EnhancedBedrockAgentService()
            
            # Process message using the enhanced bedrock agent service
            logger.info("Routing message to Enhanced Bedrock Agent Service")
            response = await bedrock_agent_service.process_message(
                message=message,
                session=session
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to process with Bedrock agent: {e}")
            # Fallback to direct MCP processing
            logger.info("Falling back to direct MCP processing")
            
            # Temporarily remove selected agent to avoid infinite recursion
            original_selected_agent = session.context.get("selected_agent")
            if "selected_agent" in session.context:
                del session.context["selected_agent"]
            
            try:
                response = await self._process_with_direct_mcp(message, session)
                return response
            finally:
                # Restore selected agent
                if original_selected_agent:
                    session.context["selected_agent"] = original_selected_agent

    async def _process_message_without_bedrock(
        self, message: str, session: ChatSession
    ) -> BedrockResponse:
        """Fallback processing when Bedrock is not available"""

        logger.warning("Processing message without Bedrock - using rule-based routing")

        # Simple rule-based tool selection
        tool_executions = []
        tool_results = []

        # Basic keyword matching for tool selection
        message_lower = message.lower()

        if any(
            word in message_lower
            for word in ["security", "secure", "vulnerability", "compliance"]
        ):
            # Security-related query
            try:
                result = await self.dynamic_mcp_service.call_tool(
                    "CheckSecurityServices", {"region": "us-east-1"}
                )
                tool_execution = ToolExecution(
                    tool_name="CheckSecurityServices",
                    parameters={"region": "us-east-1"},
                    status=ToolExecutionStatus.SUCCESS,
                    result=result,
                    timestamp=datetime.utcnow(),
                )
                tool_executions.append(tool_execution)
                tool_results.append(
                    {"tool_name": "CheckSecurityServices", "result": result}
                )
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")

        elif any(
            word in message_lower for word in ["storage", "encrypt", "s3", "ebs", "rds"]
        ):
            # Storage-related query
            try:
                result = await self.dynamic_mcp_service.call_tool(
                    "CheckStorageEncryption", {"region": "us-east-1"}
                )
                tool_execution = ToolExecution(
                    tool_name="CheckStorageEncryption",
                    parameters={"region": "us-east-1"},
                    status=ToolExecutionStatus.SUCCESS,
                    result=result,
                    timestamp=datetime.utcnow(),
                )
                tool_executions.append(tool_execution)
                tool_results.append(
                    {"tool_name": "CheckStorageEncryption", "result": result}
                )
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")

        # Generate a basic response without LLM
        response_text = self._generate_fallback_response(message, tool_results)

        return BedrockResponse(
            response=response_text,
            tool_executions=tool_executions,
            model_id="fallback-mode",
            session_id=session.session_id,
            structured_data={"tool_results": tool_results} if tool_results else None,
        )

    def _generate_fallback_response(
        self, message: str, tool_results: List[Dict[str, Any]]
    ) -> str:
        """Generate a basic response without using Bedrock LLM"""

        if not tool_results:
            return f"""I understand you're asking about: "{message}"

Unfortunately, I'm currently operating in limited mode due to a service issue. I can still execute analysis tools, but my natural language processing capabilities are temporarily reduced.

Available capabilities:
- Security assessments (CheckSecurityServices)
- Storage encryption analysis (CheckStorageEncryption)
- Network security checks (CheckNetworkSecurity)
- Service discovery (ListServicesInRegion)

Please try rephrasing your request with specific keywords like "security", "storage", or "network" to trigger the appropriate analysis tools."""

        # Basic summary of tool results
        response_parts = [f'I\'ve analyzed your request: "{message}"\n']

        for tool_result in tool_results:
            tool_name = tool_result["tool_name"]
            result = tool_result["result"]

            response_parts.append(f"**{tool_name} Results:**")

            if isinstance(result, dict):
                # Extract key metrics
                if "resources_checked" in result:
                    response_parts.append(
                        f"- Resources checked: {result['resources_checked']}"
                    )
                if "compliant_resources" in result:
                    response_parts.append(
                        f"- Compliant resources: {result['compliant_resources']}"
                    )
                if "non_compliant_resources" in result:
                    response_parts.append(
                        f"- Non-compliant resources: {result['non_compliant_resources']}"
                    )
                if "all_enabled" in result:
                    status = (
                        "All services enabled"
                        if result["all_enabled"]
                        else "Some services not enabled"
                    )
                    response_parts.append(f"- Status: {status}")

            response_parts.append("")

        response_parts.append(
            "Note: I'm currently operating in limited mode. For detailed analysis and recommendations, please contact your system administrator about the Bedrock service configuration."
        )

        return "\n".join(response_parts)

    async def _analyze_user_request(
        self, message: str, session: ChatSession
    ) -> Dict[str, Any]:
        """Analyze user request to determine which tools to use"""

        system_prompt = session.context.get(
            "system_prompt", self._generate_system_prompt()
        )

        analysis_prompt = f"""Analyze the following user request and determine which tools should be used to provide a comprehensive response.

User Request: "{message}"

Based on the available tools, determine:
1. Which tools are most relevant to this request
2. What parameters should be passed to each tool
3. The order in which tools should be executed
4. Whether multiple tools are needed for a complete analysis

Respond with a JSON object containing:
{{
    "intent": "brief description of user intent",
    "tools_to_use": [
        {{
            "name": "tool_name",
            "arguments": {{"param1": "value1", "param2": "value2"}},
            "reason": "why this tool is needed"
        }}
    ],
    "analysis_approach": "description of how you'll analyze the results"
}}

If no tools are needed (e.g., for general questions), return an empty tools_to_use array."""

        try:
            response = self.bedrock_runtime.invoke_model(
                modelId=self.model_id,
                body=json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 1000,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": analysis_prompt}],
                    }
                ),
            )

            response_body = json.loads(response["body"].read())
            analysis_text = response_body["content"][0]["text"]

            # Extract JSON from the response
            try:
                # Find JSON in the response
                import re

                json_match = re.search(r"\{.*\}", analysis_text, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group())
                    return analysis
                else:
                    # Fallback if no JSON found
                    return {
                        "intent": "general query",
                        "tools_to_use": [],
                        "analysis_approach": "direct response",
                    }
            except json.JSONDecodeError:
                logger.warning("Failed to parse analysis JSON, using fallback")
                return {
                    "intent": "general query",
                    "tools_to_use": [],
                    "analysis_approach": "direct response",
                }

        except BedrockInitializationError:
            logger.warning("Bedrock not available, using rule-based analysis")
            return self._analyze_user_request_fallback(message)
        except Exception as e:
            logger.error(f"Failed to analyze user request: {e}")
            return self._analyze_user_request_fallback(message)

    def _analyze_user_request_fallback(self, message: str) -> Dict[str, Any]:
        """Fallback analysis when Bedrock is not available"""
        message_lower = message.lower()

        tools_to_use = []

        if any(
            word in message_lower
            for word in ["security", "secure", "vulnerability", "compliance"]
        ):
            tools_to_use.append(
                {
                    "name": "CheckSecurityServices",
                    "arguments": {"region": "us-east-1"},
                    "reason": "Security-related query detected",
                }
            )

        if any(
            word in message_lower for word in ["storage", "encrypt", "s3", "ebs", "rds"]
        ):
            tools_to_use.append(
                {
                    "name": "CheckStorageEncryption",
                    "arguments": {"region": "us-east-1"},
                    "reason": "Storage-related query detected",
                }
            )

        if any(
            word in message_lower
            for word in ["network", "vpc", "security group", "load balancer"]
        ):
            tools_to_use.append(
                {
                    "name": "CheckNetworkSecurity",
                    "arguments": {"region": "us-east-1"},
                    "reason": "Network-related query detected",
                }
            )

        return {
            "intent": "automated analysis based on keywords",
            "tools_to_use": tools_to_use,
            "analysis_approach": "rule-based tool selection",
        }

    async def _generate_final_response(
        self,
        original_message: str,
        analysis: Dict[str, Any],
        tool_results: List[Dict[str, Any]],
        session: ChatSession,
    ) -> Dict[str, Any]:
        """Generate final response using LLM with tool results"""

        # Check if Bedrock is available
        if not self._is_bedrock_available():
            return {
                "response": self._generate_fallback_response(
                    original_message, tool_results
                ),
                "structured_data": {"tool_results": tool_results}
                if tool_results
                else None,
                "human_summary": None,
            }

        system_prompt = session.context.get(
            "system_prompt", self._generate_system_prompt()
        )

        # Prepare tool results for the prompt - provide structured summary instead of raw JSON
        tool_results_text = ""
        structured_data = {}

        if tool_results:
            tool_results_text = "\n\n**Tool Execution Results:**\n"
            for tool_result in tool_results:
                tool_name = tool_result["tool_name"]
                result = tool_result["result"]

                # Just indicate tool execution without detailed summary
                tool_results_text += f"\n**{tool_name}:** Executed successfully\n"

                # Add key metrics if available
                if isinstance(result, dict):
                    key_metrics = []
                    for key in [
                        "resources_checked",
                        "compliant_resources",
                        "non_compliant_resources",
                        "services_checked",
                        "all_enabled",
                        "findings",
                        "enabled",
                    ]:
                        if key in result:
                            key_metrics.append(f"{key}: {result[key]}")
                    if key_metrics:
                        tool_results_text += f"Key metrics: {', '.join(key_metrics)}\n"

                # Collect structured data for frontend
                if tool_name not in structured_data:
                    structured_data[tool_name] = result

        response_prompt = f"""The user asked: "{original_message}"

Analysis determined: {analysis.get("intent", "general query")}
{tool_results_text}

Please provide a comprehensive response that:
1. Directly addresses the user's question
2. Summarizes key findings from the tool results (if any)
3. Provides actionable recommendations
4. Explains the significance of any issues found
5. Suggests related analyses that might be valuable

IMPORTANT: Do NOT include raw JSON data or code blocks in your response. The tool execution details are already shown separately to the user. Focus on providing human-readable insights, analysis, and recommendations.

Format your response in a clear, professional manner with:
- Executive summary of findings
- Detailed analysis with specific metrics (in plain text)
- Prioritized recommendations
- Next steps

Present all information in natural language format suitable for business stakeholders."""

        try:
            response = self.bedrock_runtime.invoke_model(
                modelId=self.model_id,
                body=json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 2000,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": response_prompt}],
                    }
                ),
            )

            response_body = json.loads(response["body"].read())
            final_response = response_body["content"][0]["text"]

            return {
                "response": final_response,
                "structured_data": structured_data if structured_data else None,
                "human_summary": None,  # The LLM response already includes human-readable summary
            }

        except BedrockInitializationError:
            logger.warning("Bedrock not available for final response generation")
            return {
                "response": self._generate_fallback_response(
                    original_message, tool_results
                ),
                "structured_data": structured_data if structured_data else None,
                "human_summary": None,
            }
        except Exception as e:
            logger.error(f"Failed to generate final response: {e}")
            return {
                "response": f"I was able to gather information but encountered an error generating the final response: {str(e)}",
                "structured_data": structured_data if structured_data else None,
                "human_summary": None,
            }

    def get_session_info(self, session: ChatSession) -> Dict[str, Any]:
        """Get information about the current session"""
        return {
            "session_id": session.session_id,
            "tools_available": len(self.available_tools),
            "initialized": session.context.get("orchestrator_initialized", False),
            "bedrock_available": session.context.get("bedrock_available", False),
            "multi_agent_enabled": session.context.get("multi_agent_enabled", False),
            "supervisor_agent_id": session.context.get("supervisor_agent_id"),
            "tools_discovered_at": session.context.get("tools_discovered_at"),
            "available_tools": [
                {"name": tool["name"], "description": tool["description"]}
                for tool in self.available_tools
            ],
        }
    def get_detailed_health(self) -> Dict[str, Any]:
        """Get detailed health information including dynamic MCP service status"""
        try:
            return {
                "orchestrator_status": "healthy",  # Will be updated by async health_check
                "bedrock_available": self._is_bedrock_available(),
                "multi_agent_enabled": self.use_multi_agent,
                "supervisor_agent_id": self.supervisor_agent_id,
                "tools_discovered": self.tools_discovered,
                "available_tools_count": len(self.available_tools),
                "mcp_service": self.mcp_service.get_detailed_health(),
                "dynamic_mcp_service": self.dynamic_mcp_service.get_detailed_health(),
                "model_id": self.model_id,
                "region": self.region
            }
        except Exception as e:
            return {
                "error": str(e),
                "orchestrator_status": "error"
            }

    async def _handle_mcp_command(self, session: ChatSession, command: str = "/mcp") -> BedrockResponse:
        """Handle MCP commands to show integrated MCP servers, tools, or status"""
        try:
            # Parse command variations
            command_parts = command.split()
            subcommand = command_parts[1] if len(command_parts) > 1 else ""
            
            logger.info(f"Processing MCP command: {command} (subcommand: {subcommand})")
            
            if subcommand == "tools":
                return await self._handle_mcp_tools_command(session)
            elif subcommand == "status":
                return await self._handle_mcp_status_command(session)
            elif subcommand == "help":
                return await self._handle_mcp_help_command(session)
            else:
                # Default /mcp command - show servers
                return await self._handle_mcp_servers_command(session)
                
        except Exception as e:
            logger.error(f"Error handling MCP command: {e}")
            return BedrockResponse(
                response=f"❌ **Error processing MCP command**\n\nFailed to process MCP command: {str(e)}",
                tool_executions=[],
                model_id=self.model_id,
                session_id=session.session_id,
            )

    async def _handle_mcp_servers_command(self, session: ChatSession) -> BedrockResponse:
        """Handle the /mcp command to show integrated MCP servers"""
        try:
            logger.info("Processing /mcp servers command")
            
            # Get MCP servers from SSM Parameter Store
            import boto3
            ssm_client = boto3.client("ssm")
            
            # Get all MCP server connection info parameters
            response = ssm_client.get_parameters_by_path(
                Path="/coa/components",
                Recursive=True
            )
            
            # Filter for connection_info parameters
            connection_info_params = [
                param for param in response.get('Parameters', [])
                if param['Name'].endswith('/connection_info')
            ]
            
            if not connection_info_params:
                return BedrockResponse(
                    response="🔍 **No MCP servers found**\n\nNo integrated MCP servers are currently deployed. Please deploy MCP servers first using the deployment scripts.",
                    tool_executions=[],
                    model_id=self.model_id,
                    session_id=session.session_id,
                )
            
            # Build MCP servers list
            mcp_servers_info = []
            total_tools = 0
            
            for param in connection_info_params:
                try:
                    # Parse the connection info
                    connection_info = json.loads(param['Value'])
                    
                    # Extract server name from parameter path
                    path_parts = param['Name'].split('/')
                    server_name = path_parts[-2] if len(path_parts) >= 3 else "unknown"
                    
                    # Get server details
                    server_info = {
                        "name": server_name,
                        "display_name": server_name.replace('_', ' ').title(),
                        "agent_id": connection_info.get("agent_id", "N/A"),
                        "region": connection_info.get("region", "N/A"),
                        "deployment_type": connection_info.get("deployment_type", "N/A"),
                        "package_name": connection_info.get("package_name"),
                        "capabilities": connection_info.get("capabilities", []),
                        "description": connection_info.get("description", f"{server_name} MCP server"),
                        "status": "🟢 Deployed"
                    }
                    
                    # Count tools if available
                    tools_count = len(connection_info.get("available_tools", []))
                    if tools_count > 0:
                        server_info["tools_count"] = tools_count
                        total_tools += tools_count
                    
                    mcp_servers_info.append(server_info)
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse connection info for {param['Name']}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Error processing MCP server {param['Name']}: {e}")
                    continue
            
            # Sort servers by name for consistent ordering
            mcp_servers_info.sort(key=lambda x: x["name"])
            
            # Build response message
            response_lines = [
                "🔧 **Integrated MCP Servers**",
                f"Found {len(mcp_servers_info)} deployed MCP server(s)",
                ""
            ]
            
            for i, server in enumerate(mcp_servers_info, 1):
                response_lines.extend([
                    f"**{i}. {server['display_name']}**",
                    f"   • Status: {server['status']}",
                    f"   • Agent ID: `{server['agent_id']}`",
                    f"   • Region: {server['region']}",
                    f"   • Type: {server['deployment_type']}"
                ])
                
                if server.get("package_name"):
                    response_lines.append(f"   • Package: {server['package_name']}")
                
                if server.get("tools_count"):
                    response_lines.append(f"   • Tools: {server['tools_count']} available")
                
                if server.get("capabilities"):
                    capabilities_str = ", ".join(server["capabilities"][:3])
                    if len(server["capabilities"]) > 3:
                        capabilities_str += f" (+{len(server['capabilities']) - 3} more)"
                    response_lines.append(f"   • Capabilities: {capabilities_str}")
                
                response_lines.append(f"   • Description: {server['description']}")
                response_lines.append("")  # Empty line between servers
            
            # Add summary
            response_lines.extend([
                "📊 **Summary**",
                f"• Total MCP Servers: {len(mcp_servers_info)}",
                f"• Total Available Tools: {total_tools if total_tools > 0 else 'Unknown'}",
                f"• All servers deployed via AgentCore Runtime",
                "",
                "💡 **Usage**",
                "These MCP servers provide specialized tools for AWS security analysis, cost optimization, and resource management. The chatbot automatically routes your requests to the appropriate MCP server based on your query.",
                "",
                "Try asking questions like:",
                "• \"Check my security services status\"",
                "• \"Analyze my storage encryption\"", 
                "• \"Show me cost breakdown by service\"",
                "• \"What are my security findings?\""
            ])
            
            response_text = "\n".join(response_lines)
            
            # Create structured data for the frontend
            structured_data = {
                "mcp_servers": mcp_servers_info,
                "total_servers": len(mcp_servers_info),
                "total_tools": total_tools,
                "command": "/mcp",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return BedrockResponse(
                response=response_text,
                tool_executions=[],
                model_id=self.model_id,
                session_id=session.session_id,
                structured_data=structured_data,
                human_summary=f"Listed {len(mcp_servers_info)} integrated MCP servers with {total_tools} total tools"
            )
            
        except Exception as e:
            logger.error(f"Error handling /mcp command: {e}")
            return BedrockResponse(
                response=f"❌ **Error retrieving MCP servers**\n\nFailed to retrieve MCP server information: {str(e)}\n\nThis might indicate that MCP servers are not properly deployed or SSM Parameter Store is not accessible.",
                tool_executions=[],
                model_id=self.model_id,
                session_id=session.session_id,
            )

    async def _handle_mcp_tools_command(self, session: ChatSession) -> BedrockResponse:
        """Handle the /mcp tools command to show available MCP tools"""
        try:
            logger.info("Processing /mcp tools command")
            
            # Get available tools from the MCP service
            available_tools = await self.mcp_service.get_available_tools()
            
            if not available_tools:
                return BedrockResponse(
                    response="🔍 **No MCP tools found**\n\nNo MCP tools are currently available. Please ensure MCP servers are properly deployed.",
                    tool_executions=[],
                    model_id=self.model_id,
                    session_id=session.session_id,
                )
            
            # Group tools by category
            tools_by_category = {}
            for tool in available_tools:
                category = self._get_tool_category(tool.get("name", ""))
                if category not in tools_by_category:
                    tools_by_category[category] = []
                tools_by_category[category].append(tool)
            
            # Build response
            response_lines = [
                "🛠️ **Available MCP Tools**",
                f"Found {len(available_tools)} available tool(s) across {len(tools_by_category)} categories",
                ""
            ]
            
            for category, tools in tools_by_category.items():
                response_lines.extend([
                    f"**{category.title()} Tools ({len(tools)})**",
                    ""
                ])
                
                for tool in tools:
                    tool_name = tool.get("name", "Unknown")
                    description = tool.get("description", "No description available")
                    server = tool.get("server", "unknown")
                    
                    response_lines.extend([
                        f"• **{tool_name}**",
                        f"  Description: {description}",
                        f"  Server: {server}",
                        ""
                    ])
            
            response_lines.extend([
                "💡 **Usage**",
                "These tools are automatically invoked when you ask relevant questions. For example:",
                "• Security tools activate for questions about security posture",
                "• Cost tools activate for questions about spending and optimization",
                "• Discovery tools help identify resources and configurations"
            ])
            
            response_text = "\n".join(response_lines)
            
            # Create structured data
            structured_data = {
                "tools": available_tools,
                "tools_by_category": tools_by_category,
                "total_tools": len(available_tools),
                "categories_count": len(tools_by_category),
                "command": "/mcp tools",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return BedrockResponse(
                response=response_text,
                tool_executions=[],
                model_id=self.model_id,
                session_id=session.session_id,
                structured_data=structured_data,
                human_summary=f"Listed {len(available_tools)} MCP tools across {len(tools_by_category)} categories"
            )
            
        except Exception as e:
            logger.error(f"Error handling /mcp tools command: {e}")
            return BedrockResponse(
                response=f"❌ **Error retrieving MCP tools**\n\nFailed to retrieve MCP tools: {str(e)}",
                tool_executions=[],
                model_id=self.model_id,
                session_id=session.session_id,
            )

    async def _handle_mcp_status_command(self, session: ChatSession) -> BedrockResponse:
        """Handle the /mcp status command to show MCP system status"""
        try:
            logger.info("Processing /mcp status command")
            
            # Get detailed health information
            orchestrator_health = self.get_detailed_health()
            mcp_health = await self.mcp_service.health_check()
            dynamic_mcp_health = await self.dynamic_mcp_service.health_check()
            
            # Build status response
            response_lines = [
                "📊 **MCP System Status**",
                f"Overall Status: {'🟢 Healthy' if mcp_health == 'healthy' else '🟡 Degraded' if mcp_health == 'degraded' else '🔴 Unhealthy'}",
                ""
            ]
            
            # Orchestrator status
            response_lines.extend([
                "**LLM Orchestrator Service**",
                f"• Status: {'🟢 Healthy' if orchestrator_health.get('orchestrator_status') == 'healthy' else '🔴 Error'}",
                f"• Bedrock Available: {'✅ Yes' if orchestrator_health.get('bedrock_available') else '❌ No'}",
                f"• Multi-Agent Enabled: {'✅ Yes' if orchestrator_health.get('multi_agent_enabled') else '❌ No'}",
                f"• Tools Discovered: {'✅ Yes' if orchestrator_health.get('tools_discovered') else '❌ No'}",
                f"• Available Tools: {orchestrator_health.get('available_tools_count', 0)}",
                f"• Model: {orchestrator_health.get('model_id', 'Unknown')}",
                f"• Region: {orchestrator_health.get('region', 'Unknown')}",
                ""
            ])
            
            # MCP Service status
            response_lines.extend([
                "**MCP Client Service**",
                f"• Status: {'🟢 Healthy' if mcp_health == 'healthy' else '🟡 Degraded' if mcp_health == 'degraded' else '🔴 Unhealthy'}",
                f"• Demo Mode: {'⚠️ Yes' if getattr(self.mcp_service, 'demo_mode', False) else '✅ No'}",
                ""
            ])
            
            # Dynamic MCP Service status
            response_lines.extend([
                "**Dynamic MCP Service**",
                f"• Status: {'🟢 Healthy' if dynamic_mcp_health == 'healthy' else '🟡 Degraded' if dynamic_mcp_health == 'degraded' else '🔴 Unhealthy'}",
                f"• Agent Discovery: {'✅ Active' if hasattr(self.dynamic_mcp_service, 'agents_discovered') else '❌ Inactive'}",
                ""
            ])
            
            # Multi-Agent Supervisor status
            if orchestrator_health.get('multi_agent_enabled'):
                supervisor_id = orchestrator_health.get('supervisor_agent_id')
                response_lines.extend([
                    "**Multi-Agent Supervisor**",
                    f"• Enabled: ✅ Yes",
                    f"• Agent ID: {supervisor_id if supervisor_id else '❌ Not configured'}",
                    ""
                ])
            else:
                response_lines.extend([
                    "**Multi-Agent Supervisor**",
                    f"• Enabled: ❌ No",
                    ""
                ])
            
            # Add troubleshooting tips if there are issues
            if mcp_health != 'healthy':
                response_lines.extend([
                    "🔧 **Troubleshooting**",
                    "If you're experiencing issues:",
                    "• Check that MCP servers are properly deployed",
                    "• Verify SSM Parameter Store connectivity", 
                    "• Ensure AWS credentials have proper permissions",
                    "• Try `/mcp` to see if servers are detected",
                    "• Try `/mcp tools` to see if tools are available"
                ])
            
            response_text = "\n".join(response_lines)
            
            # Create structured data
            structured_data = {
                "orchestrator_health": orchestrator_health,
                "mcp_health": mcp_health,
                "dynamic_mcp_health": dynamic_mcp_health,
                "overall_status": mcp_health,
                "command": "/mcp status",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return BedrockResponse(
                response=response_text,
                tool_executions=[],
                model_id=self.model_id,
                session_id=session.session_id,
                structured_data=structured_data,
                human_summary=f"MCP system status: {mcp_health}"
            )
            
        except Exception as e:
            logger.error(f"Error handling /mcp status command: {e}")
            return BedrockResponse(
                response=f"❌ **Error retrieving MCP status**\n\nFailed to retrieve MCP status: {str(e)}",
                tool_executions=[],
                model_id=self.model_id,
                session_id=session.session_id,
            )

    def _get_tool_category(self, tool_name: str) -> str:
        """Categorize tools based on their name and functionality"""
        tool_name_lower = tool_name.lower()
        
        if any(keyword in tool_name_lower for keyword in ["security", "check", "findings", "encryption", "network"]):
            return "security"
        elif any(keyword in tool_name_lower for keyword in ["cost", "usage", "rightsizing", "savings", "budget"]):
            return "cost_optimization"
        elif any(keyword in tool_name_lower for keyword in ["service", "region", "list", "discover"]):
            return "discovery"
        elif any(keyword in tool_name_lower for keyword in ["storage", "encryption"]):
            return "storage"
        elif any(keyword in tool_name_lower for keyword in ["network", "vpc", "elb"]):
            return "networking"
        else:
            return "general"

    async def _handle_mcp_help_command(self, session: ChatSession) -> BedrockResponse:
        """Handle the /mcp help command to show available MCP commands"""
        try:
            logger.info("Processing /mcp help command")
            
            response_lines = [
                "❓ **MCP Command Help**",
                "Available MCP commands for exploring the integrated MCP servers:",
                "",
                "**Basic Commands:**",
                "• `/mcp` - Show all integrated MCP servers",
                "• `/mcp tools` - List all available MCP tools",
                "• `/mcp status` - Show MCP system health status",
                "• `/mcp help` - Show this help message",
                "",
                "**What are MCP Servers?**",
                "MCP (Model Context Protocol) servers provide specialized tools for:",
                "• 🛡️ **Security Analysis** - Check security services, findings, encryption",
                "• 💰 **Cost Optimization** - Analyze spending, get recommendations",
                "• 🔍 **Resource Discovery** - Find and analyze AWS resources",
                "• 🌐 **Network Security** - Assess network configurations",
                "",
                "**How to Use:**",
                "Instead of using commands directly, just ask natural questions like:",
                "• \"What's my security posture?\"",
                "• \"Show me my AWS costs this month\"",
                "• \"Check if my S3 buckets are encrypted\"",
                "• \"Are my security services enabled?\"",
                "",
                "The chatbot automatically routes your questions to the appropriate MCP servers and tools.",
                "",
                "**Examples:**",
                "• Security: \"Analyze my security configuration\"",
                "• Cost: \"What are my top spending services?\"",
                "• Storage: \"Check encryption on my storage resources\"",
                "• Network: \"Review my network security settings\"",
                "",
                "💡 **Tip:** The MCP servers work behind the scenes - you don't need to call them directly!"
            ]
            
            response_text = "\n".join(response_lines)
            
            # Create structured data
            structured_data = {
                "available_commands": [
                    {"command": "/mcp", "description": "Show integrated MCP servers"},
                    {"command": "/mcp tools", "description": "List available MCP tools"},
                    {"command": "/mcp status", "description": "Show MCP system status"},
                    {"command": "/mcp help", "description": "Show help information"}
                ],
                "example_queries": [
                    "What's my security posture?",
                    "Show me my AWS costs this month",
                    "Check if my S3 buckets are encrypted",
                    "Are my security services enabled?"
                ],
                "command": "/mcp help",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return BedrockResponse(
                response=response_text,
                tool_executions=[],
                model_id=self.model_id,
                session_id=session.session_id,
                structured_data=structured_data,
                human_summary="Provided MCP command help and usage examples"
            )
            
        except Exception as e:
            logger.error(f"Error handling /mcp help command: {e}")
            return BedrockResponse(
                response=f"❌ **Error showing MCP help**\n\nFailed to show help information: {str(e)}",
                tool_executions=[],
                model_id=self.model_id,
                session_id=session.session_id,
            )