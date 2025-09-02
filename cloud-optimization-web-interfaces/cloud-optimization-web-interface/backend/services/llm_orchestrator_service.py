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
Discovers available MCP tools and uses LLM to intelligently route user requests
FIXED VERSION: Handles Bedrock initialization failures gracefully
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List

import boto3
from models.chat_models import (
    BedrockResponse,
    ChatSession,
    ToolExecution,
    ToolExecutionStatus,
)
from services.config_service import get_config
from services.mcp_client_service import MCPClientService

logger = logging.getLogger(__name__)


class BedrockInitializationError(Exception):
    """Custom exception for Bedrock initialization failures"""

    pass


class LLMOrchestratorService:
    def __init__(self):
        self.region = get_config("AWS_DEFAULT_REGION", "us-east-1")
        self._bedrock_runtime = None
        self._bedrock_initialization_error = None
        self.mcp_service = MCPClientService(demo_mode=True)
        self.available_tools = []
        self.tools_discovered = False

        # LLM configuration - use Claude 3 Haiku for faster responses
        self.model_id = "anthropic.claude-3-haiku-20240307-v1:0"

        logger.info("Initialized LLM Orchestrator Service")

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
            # Check MCP service
            mcp_status = await self.mcp_service.health_check()

            # Check Bedrock availability
            bedrock_available = self._is_bedrock_available()

            if mcp_status == "healthy" and bedrock_available:
                return "healthy"
            elif mcp_status == "healthy":
                return "degraded"  # MCP works but Bedrock doesn't
            else:
                return "unhealthy"
        except Exception as e:
            logger.error(f"Orchestrator health check failed: {str(e)}")
            return "unhealthy"

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

            # Generate initial system prompt with tool information
            system_prompt = self._generate_system_prompt()
            session.context["system_prompt"] = system_prompt

            logger.info(
                f"Session {session.session_id} initialized with {len(self.available_tools)} tools"
            )

            return {
                "status": "initialized",
                "tools_count": len(self.available_tools),
                "bedrock_available": session.context["bedrock_available"],
                "tools": [
                    {"name": tool["name"], "description": tool["description"]}
                    for tool in self.available_tools
                ],
            }

        except Exception as e:
            logger.error(f"Failed to initialize session: {e}")
            return {"status": "error", "error": str(e)}

    async def _discover_tools(self):
        """Discover all available MCP tools"""
        try:
            logger.info("Discovering available MCP tools...")
            self.available_tools = await self.mcp_service.get_available_tools()
            self.tools_discovered = True
            logger.info(f"Discovered {len(self.available_tools)} MCP tools")

            # Log tool names for debugging
            tool_names = [tool["name"] for tool in self.available_tools]
            logger.info(f"Available tools: {', '.join(tool_names)}")

        except Exception as e:
            logger.error(f"Failed to discover tools: {e}")
            self.available_tools = []

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

        return f"""You are an AWS Cloud Optimization Assistant with access to specialized MCP (Model Context Protocol) tools for analyzing AWS infrastructure. Your role is to help users optimize their AWS environments across security, performance, cost, and operational excellence.

**System Status:**
- Bedrock LLM: {bedrock_status}
- Available Tools: {len(self.available_tools)}

**Available Tools:**
{tools_text}

**Your Capabilities:**
1. **Intelligent Routing**: Analyze user requests and determine which tools to use
2. **Multi-Tool Orchestration**: Combine multiple tools to provide comprehensive analysis
3. **Contextual Analysis**: Understand the user's intent and provide relevant insights
4. **Actionable Recommendations**: Provide specific, actionable advice based on findings

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
        """Process user message using LLM orchestration"""

        try:
            # Initialize session if not already done
            if not session.context.get("orchestrator_initialized"):
                await self.initialize_session(session)

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

                    # Execute the tool
                    try:
                        result = await self.mcp_service.call_tool(tool_name, tool_args)
                        tool_execution.result = result
                        tool_execution.status = ToolExecutionStatus.SUCCESS

                        # Tool executed successfully

                        tool_results.append({"tool_name": tool_name, "result": result})
                    except Exception as e:
                        tool_execution.status = ToolExecutionStatus.ERROR
                        tool_execution.error_message = str(e)
                        logger.error(f"Tool execution failed for {tool_name}: {e}")

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

        except Exception as e:
            logger.error(f"Error in LLM orchestrator: {e}")
            return BedrockResponse(
                response=f"I encountered an error while processing your request: {str(e)}",
                tool_executions=[],
                model_id=self.model_id,
                session_id=session.session_id,
            )

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
                result = await self.mcp_service.call_tool(
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
                result = await self.mcp_service.call_tool(
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
            "tools_discovered_at": session.context.get("tools_discovered_at"),
            "available_tools": [
                {"name": tool["name"], "description": tool["description"]}
                for tool in self.available_tools
            ],
        }
