"""
Bedrock Chat Service for BedrockAgent version.
Handles chat functionality using traditional Bedrock Agents.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from shared.models.chat_models import ChatMessage, ToolExecution
from shared.models.exceptions import BedrockServiceError, AgentInvocationError
from shared.services.bedrock_model_service import BedrockModelService

logger = logging.getLogger(__name__)


class BedrockChatService:
    """Service for chat functionality using Bedrock Agents."""
    
    def __init__(self, region: str = "us-east-1"):
        """
        Initialize the Bedrock Chat Service.
        
        Args:
            region: AWS region for Bedrock services
        """
        self.region = region
        
        # Initialize AWS clients
        try:
            self.bedrock_agent_runtime = boto3.client('bedrock-agent-runtime', region_name=region)
            logger.info(f"BedrockChatService initialized for region {region}")
        except (NoCredentialsError, ClientError, Exception) as e:
            logger.error(f"Failed to initialize Bedrock agent runtime client: {e}")
            raise BedrockServiceError(f"Failed to initialize Bedrock agent runtime client: {e}")
        
        # Initialize shared model service for fallback
        self.model_service = BedrockModelService(region)
        
        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 1.0

    async def invoke_agent(
        self,
        agent_id: str,
        agent_alias_id: str,
        session_id: str,
        input_text: str,
        streaming: bool = False
    ) -> Dict[str, Any]:
        """
        Invoke a Bedrock agent with session management.
        
        Args:
            agent_id: The Bedrock agent identifier
            agent_alias_id: The agent alias identifier
            session_id: Session ID for conversation continuity
            input_text: User input text
            streaming: Whether to use streaming response
            
        Returns:
            Dictionary with agent response and metadata
            
        Raises:
            AgentInvocationError: If agent invocation fails
        """
        try:
            logger.debug(f"Invoking agent {agent_id} with session {session_id}")
            
            # Prepare agent request
            request_params = {
                'agentId': agent_id,
                'agentAliasId': agent_alias_id,
                'sessionId': session_id,
                'inputText': input_text
            }
            
            # Invoke agent with retry logic
            for attempt in range(self.max_retries):
                try:
                    if streaming:
                        return await self._invoke_agent_streaming(request_params)
                    else:
                        return await self._invoke_agent_sync(request_params)
                        
                except ClientError as e:
                    error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                    
                    if error_code in ['ThrottlingException', 'ServiceUnavailableException'] and attempt < self.max_retries - 1:
                        logger.warning(f"Retrying agent invocation due to {error_code} (attempt {attempt + 1})")
                        await self._wait_for_retry(attempt)
                        continue
                    else:
                        raise AgentInvocationError(f"Agent invocation failed: {e}")
                        
        except Exception as e:
            logger.error(f"Error invoking agent {agent_id}: {e}")
            if isinstance(e, AgentInvocationError):
                raise
            raise AgentInvocationError(f"Unexpected error during agent invocation: {e}")

    async def _invoke_agent_sync(self, request_params: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke agent synchronously."""
        start_time = datetime.utcnow()
        
        response = self.bedrock_agent_runtime.invoke_agent(**request_params)
        
        end_time = datetime.utcnow()
        response_time_ms = (end_time - start_time).total_seconds() * 1000
        
        # Parse agent response
        completion = ""
        tool_executions = []
        
        for event in response.get('completion', []):
            if 'chunk' in event:
                chunk = event['chunk']
                if 'bytes' in chunk:
                    chunk_data = json.loads(chunk['bytes'])
                    if chunk_data.get('type') == 'chunk':
                        completion += chunk_data.get('bytes', '').decode('utf-8')
                    elif chunk_data.get('type') == 'trace':
                        # Handle tool execution traces
                        trace_data = chunk_data.get('trace', {})
                        if 'orchestrationTrace' in trace_data:
                            orch_trace = trace_data['orchestrationTrace']
                            if 'invocationInput' in orch_trace:
                                tool_executions.append(self._parse_tool_execution(orch_trace))
        
        logger.debug(f"Agent {request_params['agentId']} responded in {response_time_ms:.1f}ms")
        
        return {
            "content": completion,
            "agent_id": request_params['agentId'],
            "session_id": request_params['sessionId'],
            "tool_executions": tool_executions,
            "response_time_ms": response_time_ms,
            "streaming": False,
            "timestamp": end_time.isoformat()
        }

    async def _invoke_agent_streaming(self, request_params: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke agent with streaming response."""
        start_time = datetime.utcnow()
        
        response = self.bedrock_agent_runtime.invoke_agent(**request_params)
        
        # For streaming, we'll return a generator function
        async def stream_generator():
            full_content = ""
            tool_executions = []
            
            for event in response.get('completion', []):
                if 'chunk' in event:
                    chunk = event['chunk']
                    if 'bytes' in chunk:
                        try:
                            chunk_data = json.loads(chunk['bytes'])
                            
                            if chunk_data.get('type') == 'chunk':
                                delta = chunk_data.get('bytes', '').decode('utf-8')
                                full_content += delta
                                yield {
                                    "type": "content_delta",
                                    "delta": delta,
                                    "full_content": full_content
                                }
                            elif chunk_data.get('type') == 'trace':
                                # Handle tool execution traces
                                trace_data = chunk_data.get('trace', {})
                                if 'orchestrationTrace' in trace_data:
                                    orch_trace = trace_data['orchestrationTrace']
                                    if 'invocationInput' in orch_trace:
                                        tool_exec = self._parse_tool_execution(orch_trace)
                                        tool_executions.append(tool_exec)
                                        yield {
                                            "type": "tool_execution",
                                            "tool_execution": tool_exec
                                        }
                        except json.JSONDecodeError:
                            # Handle non-JSON chunks
                            delta = chunk['bytes'].decode('utf-8')
                            full_content += delta
                            yield {
                                "type": "content_delta",
                                "delta": delta,
                                "full_content": full_content
                            }
            
            end_time = datetime.utcnow()
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            yield {
                "type": "stream_end",
                "full_content": full_content,
                "tool_executions": tool_executions,
                "response_time_ms": response_time_ms,
                "timestamp": end_time.isoformat()
            }
        
        return {
            "content": "",  # Will be populated through streaming
            "agent_id": request_params['agentId'],
            "session_id": request_params['sessionId'],
            "streaming": True,
            "stream_generator": stream_generator(),
            "timestamp": start_time.isoformat()
        }

    def _parse_tool_execution(self, orchestration_trace: Dict[str, Any]) -> ToolExecution:
        """Parse tool execution from orchestration trace."""
        try:
            invocation_input = orchestration_trace.get('invocationInput', {})
            tool_name = invocation_input.get('actionGroupInvocationInput', {}).get('actionGroupName', 'unknown')
            tool_input = invocation_input.get('actionGroupInvocationInput', {}).get('parameters', {})
            
            # Extract output if available
            tool_output = orchestration_trace.get('observation', {}).get('actionGroupInvocationOutput', {}).get('text', '')
            
            # Determine success based on presence of output
            success = bool(tool_output and 'error' not in tool_output.lower())
            error_message = None if success else tool_output
            
            return ToolExecution(
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=tool_output,
                execution_time_ms=0,  # Not available in trace
                success=success,
                error_message=error_message
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse tool execution: {e}")
            return ToolExecution(
                tool_name="unknown",
                tool_input={},
                tool_output="",
                execution_time_ms=0,
                success=False,
                error_message=f"Failed to parse tool execution: {e}"
            )

    async def _wait_for_retry(self, attempt: int) -> None:
        """Wait before retrying with exponential backoff."""
        import asyncio
        wait_time = self.retry_delay * (2 ** attempt)
        await asyncio.sleep(wait_time)

    async def chat_with_fallback(
        self,
        messages: List[ChatMessage],
        agent_id: Optional[str] = None,
        agent_alias_id: Optional[str] = None,
        session_id: Optional[str] = None,
        use_agent: bool = True
    ) -> Dict[str, Any]:
        """
        Chat with agent or fallback to direct model access.
        
        Args:
            messages: List of chat messages
            agent_id: Bedrock agent ID (optional)
            agent_alias_id: Agent alias ID (optional)
            session_id: Session ID (optional)
            use_agent: Whether to try agent first
            
        Returns:
            Chat response dictionary
        """
        # Try agent first if configured and requested
        if use_agent and agent_id and agent_alias_id and session_id:
            try:
                # Get the last user message
                user_message = next((msg.content for msg in reversed(messages) if msg.role == "user"), "")
                
                if user_message:
                    agent_response = await self.invoke_agent(
                        agent_id=agent_id,
                        agent_alias_id=agent_alias_id,
                        session_id=session_id,
                        input_text=user_message
                    )
                    
                    return {
                        "response_type": "agent",
                        "content": agent_response["content"],
                        "tool_executions": agent_response.get("tool_executions", []),
                        "metadata": {
                            "agent_id": agent_id,
                            "session_id": session_id,
                            "response_time_ms": agent_response.get("response_time_ms", 0)
                        }
                    }
            except Exception as e:
                logger.warning(f"Agent invocation failed, falling back to model: {e}")
        
        # Fallback to direct model access
        try:
            model_id = self.model_service.get_standard_model()
            model_response = await self.model_service.invoke_model(
                model_id=model_id,
                messages=messages
            )
            
            formatted_response = self.model_service.format_response(model_response)
            
            return {
                "response_type": "model_fallback",
                "content": formatted_response["content"],
                "tool_executions": [],
                "metadata": formatted_response["metadata"]
            }
            
        except Exception as e:
            logger.error(f"Model fallback also failed: {e}")
            raise BedrockServiceError(f"Both agent and model fallback failed: {e}")

    def extract_tool_results(self, response: Dict[str, Any]) -> List[ToolExecution]:
        """
        Extract tool execution results from agent response.
        
        Args:
            response: Agent response containing tool executions
            
        Returns:
            List of ToolExecution objects
        """
        try:
            tool_executions = response.get("tool_executions", [])
            if isinstance(tool_executions, list):
                return tool_executions
            else:
                logger.warning("Tool executions is not a list, returning empty list")
                return []
                
        except Exception as e:
            logger.error(f"Error extracting tool results: {e}")
            return []

    async def health_check(self) -> str:
        """
        Perform health check for Bedrock chat service.
        
        Returns:
            Health status string ("healthy", "degraded", "unhealthy")
        """
        try:
            # Test agent runtime connectivity
            # We can't easily test without invoking an agent, so just check client initialization
            if self.bedrock_agent_runtime:
                agent_health = "healthy"
            else:
                agent_health = "unhealthy"
            
            # Check model service health
            model_health = await self.model_service.health_check()
            
            # Determine overall health
            if agent_health == "healthy" and model_health == "healthy":
                return "healthy"
            elif agent_health == "unhealthy" and model_health == "unhealthy":
                return "unhealthy"
            else:
                return "degraded"
                
        except Exception as e:
            logger.error(f"Bedrock chat service health check failed: {e}")
            return "unhealthy"

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get service information and configuration.
        
        Returns:
            Dictionary with service information
        """
        return {
            "service": "bedrock_chat_service",
            "version": "bedrockagent",
            "region": self.region,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "model_service_info": self.model_service.get_service_info(),
            "timestamp": datetime.utcnow().isoformat()
        }