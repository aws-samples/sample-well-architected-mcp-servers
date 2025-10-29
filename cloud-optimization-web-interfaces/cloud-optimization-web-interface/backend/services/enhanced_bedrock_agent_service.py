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
Enhanced Bedrock Agent Service - Supports both Bedrock Agent and AgentCore Runtime
Provides unified interface for invoking different types of agents
"""

import json
import logging
import requests
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import ClientError
from models.chat_models import (
    BedrockResponse,
    ChatSession,
    ToolExecution,
    ToolExecutionStatus,
)
from services.config_service import get_config

logger = logging.getLogger(__name__)


class AgentType(Enum):
    """Supported agent types"""
    BEDROCK_AGENT = "bedrock-agent"
    BEDROCK_AGENTCORE = "bedrock-agentcore"


class AgentInfo:
    """Enhanced agent information with runtime type support"""

    def __init__(
        self,
        agent_type: str,
        agent_id: str,
        agent_alias_id: str = None,
        runtime_type: AgentType = AgentType.BEDROCK_AGENT,
        metadata: Dict[str, Any] = None,
        **kwargs,
    ):
        self.agent_type = agent_type
        self.agent_id = agent_id
        self.agent_alias_id = agent_alias_id
        self.runtime_type = runtime_type
        self.metadata = metadata or {}
        
        # AgentCore specific attributes
        self.endpoint_url = kwargs.get("endpoint_url")
        self.health_check_url = kwargs.get("health_check_url")
        self.agent_arn = kwargs.get("agent_arn")
        
        # Common attributes
        self.capabilities = self.metadata.get("capabilities", [])
        
        # Determine framework based on runtime type and metadata
        if self.runtime_type == AgentType.BEDROCK_AGENTCORE:
            self.framework = self.metadata.get("framework", "strands")  # Default to "strands" for AgentCore
        else:
            self.framework = self.metadata.get("framework", "bedrock")
            
        self.status = self.metadata.get("status", "UNKNOWN")
        self.model_id = self.metadata.get("model_id", "unknown")

    def is_agentcore(self) -> bool:
        """Check if this is an AgentCore runtime agent"""
        return self.runtime_type == AgentType.BEDROCK_AGENTCORE

    def is_bedrock_agent(self) -> bool:
        """Check if this is a standard Bedrock Agent"""
        return self.runtime_type == AgentType.BEDROCK_AGENT

    def __repr__(self):
        return f"AgentInfo(type={self.agent_type}, id={self.agent_id}, runtime={self.runtime_type.value}, status={self.status})"


class EnhancedBedrockAgentService:
    """Enhanced service supporting both Bedrock Agent and AgentCore runtime"""

    def __init__(self):
        self.region = get_config("AWS_DEFAULT_REGION", "us-east-1")

        # Initialize AWS clients (lazy loading)
        self._bedrock_agent_runtime = None
        self._bedrock_agent = None
        self._bedrock_runtime = None
        self._ssm_client = None
        self._session = None

        # Agent discovery and caching
        self.discovered_agents: Dict[str, AgentInfo] = {}
        self.agents_discovered_at = None
        self.discovery_cache_ttl = 300  # 5 minutes

        logger.info("Initialized Enhanced Bedrock Agent Service with dual runtime support")

        # Discover agents on initialization
        self._discover_agents()

    @property
    def bedrock_agent_runtime(self):
        """Lazy initialization of Bedrock Agent Runtime client"""
        if self._bedrock_agent_runtime is None:
            try:
                self._bedrock_agent_runtime = boto3.client(
                    "bedrock-agent-runtime", region_name=self.region
                )
            except Exception as e:
                logger.warning(f"Could not initialize Bedrock Agent Runtime client: {str(e)}")
                self._bedrock_agent_runtime = None
        return self._bedrock_agent_runtime

    @property
    def bedrock_agent(self):
        """Lazy initialization of Bedrock Agent client"""
        if self._bedrock_agent is None:
            try:
                self._bedrock_agent = boto3.client("bedrock-agent", region_name=self.region)
            except Exception as e:
                logger.warning(f"Could not initialize Bedrock Agent client: {str(e)}")
                self._bedrock_agent = None
        return self._bedrock_agent

    @property
    def ssm_client(self):
        """Lazy initialization of SSM client"""
        if self._ssm_client is None:
            try:
                self._ssm_client = boto3.client("ssm", region_name=self.region)
            except Exception as e:
                logger.warning(f"Could not initialize SSM client: {str(e)}")
                self._ssm_client = None
        return self._ssm_client

    @property
    def session(self):
        """Lazy initialization of boto3 session for credentials"""
        if self._session is None:
            self._session = boto3.Session()
        return self._session

    def _determine_runtime_type(self, params: Dict[str, Any], metadata: Dict[str, Any]) -> AgentType:
        """Determine the runtime type based on available parameters"""
        # Check for AgentCore specific indicators
        if any(key in params for key in ["endpoint_url", "health_check_url"]):
            return AgentType.BEDROCK_AGENTCORE
        
        # Check metadata for framework indicators
        framework = metadata.get("framework", "").lower()
        if framework in ["strands", "agentcore"]:
            return AgentType.BEDROCK_AGENTCORE
        
        # Check for ARN pattern
        agent_arn = params.get("agent_arn", "")
        if "bedrock-agentcore" in agent_arn:
            return AgentType.BEDROCK_AGENTCORE
        
        # Default to standard Bedrock Agent
        return AgentType.BEDROCK_AGENT

    def _discover_agents(self) -> None:
        """Discover all available agents from SSM Parameter Store"""
        try:
            if not self.ssm_client:
                logger.warning("SSM client not available, skipping agent discovery")
                return

            logger.info("Discovering agents from SSM Parameter Store...")

            # Get all parameters under both /coa/agent/ and /coa/agents/ with pagination
            all_parameters = []
            
            # Search paths using dynamic parameter prefix
            param_prefix = get_config('PARAM_PREFIX', 'coa')
            search_paths = [f"/{param_prefix}/agent/", f"/{param_prefix}/agentcore/", f"/{param_prefix}/agents/"]
            
            for search_path in search_paths:
                logger.info(f"Searching for agents in {search_path}")
                next_token = None

                while True:
                    params = {
                        "Path": search_path,
                        "Recursive": True,
                        "WithDecryption": True,
                    }
                    if next_token:
                        params["NextToken"] = next_token

                    try:
                        response = self.ssm_client.get_parameters_by_path(**params)
                        all_parameters.extend(response["Parameters"])
                        logger.info(f"Found {len(response['Parameters'])} parameters in {search_path}")

                        next_token = response.get("NextToken")
                        if not next_token:
                            break
                    except Exception as e:
                        logger.warning(f"Failed to search {search_path}: {e}")
                        break

            # Group parameters by agent type
            agent_params = {}
            for param in all_parameters:
                path_parts = param["Name"].split("/")
                # Handle /coa/agent/{agent_type}/{param_name}, /coa/agentcore/{agent_type}/{param_name}, and /coa/agents/{agent_type}/{param_name}
                if len(path_parts) >= 4:
                    if path_parts[2] in ["agent", "agentcore", "agents"]:
                        agent_type = path_parts[3]
                        param_name = path_parts[4] if len(path_parts) > 4 else "root"

                        if agent_type not in agent_params:
                            agent_params[agent_type] = {}

                        agent_params[agent_type][param_name] = param["Value"]

            # Create AgentInfo objects for each discovered agent
            self.discovered_agents = {}
            for agent_type, params in agent_params.items():
                try:
                    # Parse metadata if available
                    metadata = {}
                    if "metadata" in params:
                        try:
                            metadata = json.loads(params["metadata"])
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse metadata for agent {agent_type}")

                    # Determine agent ID and alias ID based on available parameters
                    agent_id = params.get("agent_id") or params.get("agent-id")
                    agent_alias_id = params.get("agent_alias_id") or params.get("alias-id")

                    # Fault tolerance: Use agent_type as agent_id if agent_id is missing
                    if not agent_id and agent_type:
                        agent_id = agent_type
                        logger.info(f"Using agent_type '{agent_type}' as agent_id (fault tolerance)")

                    if agent_id:
                        # Determine runtime type
                        runtime_type = self._determine_runtime_type(params, metadata)
                        
                        # Generate default ARN if missing (fault tolerance)
                        agent_arn = params.get("agent_arn")
                        if not agent_arn:
                            if runtime_type == AgentType.BEDROCK_AGENTCORE:
                                agent_arn = f"arn:aws:bedrock-agentcore:us-east-1:unknown:agent/{agent_id}"
                            else:
                                agent_arn = f"arn:aws:bedrock:us-east-1:unknown:agent/{agent_id}"
                            logger.info(f"Generated default ARN for agent '{agent_type}': {agent_arn}")
                        
                        agent_info = AgentInfo(
                            agent_type=agent_type,
                            agent_id=agent_id,
                            agent_alias_id=agent_alias_id,
                            runtime_type=runtime_type,
                            metadata=metadata,
                            endpoint_url=params.get("endpoint_url"),
                            health_check_url=params.get("health_check_url"),
                            agent_arn=agent_arn,
                        )

                        self.discovered_agents[agent_type] = agent_info
                        logger.info(f"Discovered agent: {agent_info}")
                    else:
                        logger.warning(f"Agent {agent_type} has no usable identifier - skipping")

                except Exception as e:
                    logger.error(f"Failed to process agent {agent_type}: {e}")
                    continue

            self.agents_discovered_at = datetime.utcnow()
            logger.info(f"Agent discovery completed. Found {len(self.discovered_agents)} agents")

        except Exception as e:
            logger.error(f"Agent discovery failed: {e}")
            self.discovered_agents = {}

    def _should_refresh_agents(self) -> bool:
        """Check if agent discovery cache should be refreshed"""
        if not self.agents_discovered_at:
            return True

        cache_age = (datetime.utcnow() - self.agents_discovered_at).total_seconds()
        return cache_age > self.discovery_cache_ttl

    def get_available_agents(self) -> Dict[str, AgentInfo]:
        """Get all available agents, refreshing cache if needed"""
        if self._should_refresh_agents():
            self._discover_agents()

        return self.discovered_agents.copy()

    def get_agent_by_type(self, agent_type: str) -> Optional[AgentInfo]:
        """Get a specific agent by type"""
        agents = self.get_available_agents()
        return agents.get(agent_type)

    def get_agents_by_runtime_type(self, runtime_type: AgentType) -> List[AgentInfo]:
        """Get agents by runtime type"""
        agents = self.get_available_agents()
        return [agent for agent in agents.values() if agent.runtime_type == runtime_type]

    async def invoke_bedrock_agent(
        self, 
        agent_info: AgentInfo, 
        message: str, 
        session: ChatSession
    ) -> BedrockResponse:
        """Invoke a standard Bedrock Agent"""
        try:
            logger.info(f"Invoking Bedrock Agent: {agent_info.agent_id}")

            # Prepare the request
            request_params = {
                "agentId": agent_info.agent_id,
                "agentAliasId": agent_info.agent_alias_id or "TSTALIASID",
                "inputText": message,
            }

            # Use session ID if available
            if session and session.session_id:
                request_params["sessionId"] = session.session_id

            # Invoke the agent
            response = self.bedrock_agent_runtime.invoke_agent(**request_params)

            # Process the streaming response
            response_text = ""
            tool_executions = []

            if "completion" in response:
                for event in response["completion"]:
                    if "chunk" in event:
                        chunk = event["chunk"]
                        if "bytes" in chunk:
                            chunk_text = chunk["bytes"].decode("utf-8")
                            response_text += chunk_text

                    # Handle trace events for tool executions
                    elif "trace" in event:
                        trace = event["trace"]["trace"]
                        if "orchestrationTrace" in trace:
                            orchestration = trace["orchestrationTrace"]
                            if "invocationInput" in orchestration:
                                # Tool invocation started
                                invocation = orchestration["invocationInput"]
                                if "actionGroupInvocationInput" in invocation:
                                    action_group = invocation["actionGroupInvocationInput"]
                                    tool_execution = ToolExecution(
                                        tool_name=action_group.get("actionGroupName", "unknown"),
                                        tool_input=action_group.get("parameters", {}),
                                        status=ToolExecutionStatus.RUNNING,
                                        timestamp=datetime.utcnow(),
                                    )
                                    tool_executions.append(tool_execution)

                            elif "observation" in orchestration:
                                # Tool execution completed
                                observation = orchestration["observation"]
                                if "actionGroupInvocationOutput" in observation and tool_executions:
                                    output = observation["actionGroupInvocationOutput"]
                                    tool_executions[-1].tool_output = output.get("text", "")
                                    tool_executions[-1].status = ToolExecutionStatus.COMPLETED

            # Update session if provided
            if session:
                session.session_id = response.get("sessionId", session.session_id)

            return BedrockResponse(
                response=response_text or f"Processed your request using {agent_info.agent_type} agent.",
                tool_executions=tool_executions,
                model_id=agent_info.model_id,
                session_id=response.get("sessionId"),
            )

        except Exception as e:
            logger.error(f"Error invoking Bedrock Agent: {e}")
            raise

    async def invoke_agentcore_runtime(
        self, 
        agent_info: AgentInfo, 
        message: str, 
        session: ChatSession
    ) -> BedrockResponse:
        """Invoke an AgentCore runtime agent via HTTP"""
        try:
            logger.info(f"Invoking AgentCore Runtime: {agent_info.agent_id}")

            if not agent_info.endpoint_url:
                raise ValueError(f"No endpoint URL configured for AgentCore agent {agent_info.agent_type}")

            # Prepare the payload
            payload = {
                "prompt": message,
                "sessionId": session.session_id if session else f"session-{datetime.utcnow().timestamp()}"
            }

            # Get AWS credentials for signing
            credentials = self.session.get_credentials()
            
            # Create signed request
            request = AWSRequest(
                method='POST',
                url=agent_info.endpoint_url,
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'}
            )
            SigV4Auth(credentials, 'bedrock-agentcore', self.region).add_auth(request)

            # Make the HTTP request
            response = requests.post(
                agent_info.endpoint_url,
                data=json.dumps(payload),
                headers=dict(request.headers),
                timeout=120  # 2 minute timeout for agent processing
            )

            if response.status_code == 200:
                try:
                    # Try to parse JSON response
                    result = response.json()
                    response_text = result if isinstance(result, str) else json.dumps(result, indent=2)
                except:
                    # Fallback to text response
                    response_text = response.text

                # Update session if provided
                if session:
                    session.session_id = payload["sessionId"]

                return BedrockResponse(
                    response=response_text,
                    tool_executions=[],  # AgentCore tools are handled internally
                    model_id=agent_info.model_id,
                    session_id=payload["sessionId"],
                )
            else:
                error_msg = f"AgentCore invocation failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)

        except Exception as e:
            logger.error(f"Error invoking AgentCore Runtime: {e}")
            raise

    async def process_message(
        self,
        message: str,
        session: ChatSession,
        agent_type: str = None,
        **kwargs
    ) -> BedrockResponse:
        """Process a chat message using the appropriate agent and runtime"""
        
        # Select agent
        if agent_type:
            selected_agent = self.get_agent_by_type(agent_type)
            if not selected_agent:
                return BedrockResponse(
                    response=f"Agent '{agent_type}' not found or not available.",
                    tool_executions=[],
                    model_id="no-agent-available",
                )
        else:
            selected_agent = self._select_best_agent(message, session)

        if not selected_agent:
            return BedrockResponse(
                response="No agents are currently available. Please check your agent configuration.",
                tool_executions=[],
                model_id="no-agent-available",
            )

        logger.info(f"Processing message with {selected_agent.runtime_type.value}: {selected_agent.agent_type}")

        try:
            # Route to appropriate invocation method based on runtime type
            if selected_agent.is_bedrock_agent():
                return await self.invoke_bedrock_agent(selected_agent, message, session)
            elif selected_agent.is_agentcore():
                return await self.invoke_agentcore_runtime(selected_agent, message, session)
            else:
                raise ValueError(f"Unsupported runtime type: {selected_agent.runtime_type}")

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            logger.error(f"AWS Client error: {error_code} - {error_message}")

            return BedrockResponse(
                response=f"I encountered an AWS error while processing your request: {error_message}",
                tool_executions=[],
                model_id=selected_agent.model_id,
            )

        except Exception as e:
            logger.error(f"Unexpected error processing message: {e}")
            return BedrockResponse(
                response="I encountered an unexpected error. Please try again.",
                tool_executions=[],
                model_id=selected_agent.model_id if selected_agent else "unknown",
            )

    def _select_best_agent(self, message: str, session: ChatSession = None) -> Optional[AgentInfo]:
        """Intelligently select the best agent for a given message"""
        agents = self.get_available_agents()

        if not agents:
            logger.warning("No agents available for selection")
            return None

        message_lower = message.lower()

        # Priority-based agent selection

        # 1. Multi-agent supervisor (highest priority if available)
        supervisor_agents = [
            agent for agent in agents.values() 
            if "supervisor" in agent.agent_type.lower() and agent.status == "DEPLOYED"
        ]
        if supervisor_agents:
            logger.info(f"Selected supervisor agent: {supervisor_agents[0].agent_type}")
            return supervisor_agents[0]

        # 2. Combined security and cost agents (for comprehensive analysis)
        combined_agents = [
            agent for agent in agents.values()
            if any(keyword in agent.agent_type.lower() for keyword in ["sec_cost", "security_cost", "wa_sec_cost"])
            and agent.status == "DEPLOYED"
        ]
        if combined_agents:
            logger.info(f"Selected combined agent: {combined_agents[0].agent_type}")
            return combined_agents[0]

        # 3. Security-related queries
        if any(word in message_lower for word in ["security", "secure", "vulnerability", "compliance", "encrypt"]):
            security_agents = [
                agent for agent in agents.values()
                if any(cap in agent.capabilities for cap in ["security_analysis", "aws_security_assessment"])
                and agent.status == "DEPLOYED"
            ]
            if security_agents:
                logger.info(f"Selected security agent: {security_agents[0].agent_type}")
                return security_agents[0]

        # 4. Cost-related queries
        if any(word in message_lower for word in ["cost", "billing", "expense", "budget", "price"]):
            cost_agents = [
                agent for agent in agents.values()
                if any(cap in agent.capabilities for cap in ["cost_analysis", "cost_optimization"])
                and agent.status == "DEPLOYED"
            ]
            if cost_agents:
                logger.info(f"Selected cost agent: {cost_agents[0].agent_type}")
                return cost_agents[0]

        # 5. Default to first available deployed agent
        for agent in agents.values():
            if agent.status == "DEPLOYED":
                logger.info(f"Selected default agent: {agent.agent_type}")
                return agent

        # 6. Fallback to any available agent
        if agents:
            agent = list(agents.values())[0]
            logger.info(f"Selected fallback agent: {agent.agent_type}")
            return agent

        return None

    async def health_check(self) -> str:
        """Check if the service and agents are healthy"""
        try:
            agents = self.get_available_agents()

            if not agents:
                logger.warning("No agents discovered")
                return "degraded"

            healthy_agents = 0
            total_agents = len(agents)

            for agent_type, agent_info in agents.items():
                try:
                    if agent_info.status == "DEPLOYED":
                        if agent_info.is_bedrock_agent() and self.bedrock_agent:
                            # Check Bedrock Agent health
                            response = self.bedrock_agent.get_agent(agentId=agent_info.agent_id)
                            if response["agent"]["agentStatus"] in ["PREPARED", "CREATING", "UPDATING"]:
                                healthy_agents += 1
                        elif agent_info.is_agentcore():
                            # For AgentCore, assume healthy if status is DEPLOYED
                            # Could add HTTP health check here if needed
                            healthy_agents += 1
                        else:
                            # For other frameworks, assume healthy if status is DEPLOYED
                            healthy_agents += 1
                except Exception as e:
                    logger.warning(f"Health check failed for agent {agent_type}: {e}")
                    continue

            if healthy_agents == 0:
                return "unhealthy"
            elif healthy_agents == total_agents:
                return "healthy"
            else:
                return "degraded"

        except Exception as e:
            logger.error(f"Enhanced Bedrock Agent service health check failed: {str(e)}")
            return "degraded"

    def get_agent_summary(self) -> Dict[str, Any]:
        """Get a summary of all discovered agents"""
        agents = self.get_available_agents()
        
        summary = {
            "total_agents": len(agents),
            "bedrock_agents": len([a for a in agents.values() if a.is_bedrock_agent()]),
            "agentcore_agents": len([a for a in agents.values() if a.is_agentcore()]),
            "deployed_agents": len([a for a in agents.values() if a.status == "DEPLOYED"]),
            "agents": {}
        }
        
        for agent_type, agent_info in agents.items():
            summary["agents"][agent_type] = {
                "runtime_type": agent_info.runtime_type.value,
                "status": agent_info.status,
                "framework": agent_info.framework,
                "capabilities": agent_info.capabilities,
                "model_id": agent_info.model_id
            }
        
        return summary